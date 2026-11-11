"""Sekme 3 - Deneme Analizi."""


import pandas as pd
import streamlit as st

from config.database import get_connection, log_islem
from config.settings import get_tr_now
from services.exam_service import (
    DERS_SONUC_MAKS_SORU,
    DERS_SONUC_MIN_SORU,
    baglanmamis_yanlis_sayisi,
    deneme_ders_sonuclari_getir,
    deneme_kaydet,
    denemeleri_getir,
    ders_net_serisi,
    ders_seri_listesi,
    ders_sonucu_dogrula,
    ders_toplam_neti,
    genel_ders_secenekleri,
    grafik_seri_secenekleri,
    net_ozeti,
    seri_filtrele,
)
from services import wrong_questions
from views.shared import sanitize_key, set_flash_message


def render(ctx):
    st.header("📝 Deneme Analizi ve Net Girişi")
    if "wiz_step" not in st.session_state:
        st.session_state.wiz_step = 1
    if "wiz_kategori" not in st.session_state:
        st.session_state.wiz_kategori = "Genel Deneme"
    if "wiz_brans_dersi" not in st.session_state:
        st.session_state.wiz_brans_dersi = ""
    if "wiz_tur" not in st.session_state:
        st.session_state.wiz_tur = "TYT"
    if "wiz_adi" not in st.session_state:
        st.session_state.wiz_adi = ""
    if "wiz_net" not in st.session_state:
        st.session_state.wiz_net = 0.0
    if "wiz_selected_dersler" not in st.session_state:
        st.session_state.wiz_selected_dersler = []
    if "wiz_card_idx" not in st.session_state:
        st.session_state.wiz_card_idx = 0
    if "wiz_queue" not in st.session_state:
        st.session_state.wiz_queue = []
    if "wiz_draft_mistakes" not in st.session_state:
        st.session_state.wiz_draft_mistakes = []
    if "wiz_show_details" not in st.session_state:
        st.session_state.wiz_show_details = False
    if "wiz_tarih" not in st.session_state:
        st.session_state.wiz_tarih = get_tr_now().date()
    if "wiz_kayit_sonuc" not in st.session_state:
        st.session_state.wiz_kayit_sonuc = None

    ogrenci_alan = ctx.user["hedef_alan"]
    if ogrenci_alan == "Dil":
        izinli_sinav_turleri = ["TYT", "YDT"]
    elif ctx.user["sinif_seviyesi"] in ["9. Sınıf", "10. Sınıf"]:
        izinli_sinav_turleri = ["TYT"]
    else:
        izinli_sinav_turleri = ["TYT", "AYT"]

    if st.session_state.wiz_step == 1:
        st.markdown(
            '<div class="sim-card"><h3>1. Adım: Sınav Bilgileri</h3><p>Analiz'
            " etmek istediğiniz <b>Genel Deneme</b> veya <b>Branş"
            " Denemesi</b> bilgilerini giriniz.</p></div>",
            unsafe_allow_html=True,
        )
        col_w1, col_w2 = st.columns(2)
        ders_girdileri = []
        ders_hatalari = []
        with col_w1:
            st.session_state.wiz_kategori = st.radio(
                "Deneme Türü:", ["Genel Deneme", "Branş Denemesi"], horizontal=True
            )
            st.session_state.wiz_tur = st.radio(
                "Sınav Kategorisi:",
                options=izinli_sinav_turleri,
                horizontal=True,
            )
            st.session_state.wiz_adi = st.text_input(
                "Deneme Sınavının Adı veya Yayın Evi:",
                placeholder="Örn: 3D TYT 2. Deneme",
            )
            # FAZ 2: Denemenin GERÇEK tarihi. Grafik ve alarm sıralaması giriş
            # sırasına değil bu tarihe göre yapılır.
            st.session_state.wiz_tarih = st.date_input(
                "Deneme Tarihi:",
                value=st.session_state.wiz_tarih,
                max_value=get_tr_now().date(),
                format="DD/MM/YYYY",
            )
        with col_w2:
            if st.session_state.wiz_kategori == "Branş Denemesi":
                uyumlu_dersler = [
                    d
                    for d in ctx.mufredat.keys()
                    if (
                        st.session_state.wiz_tur == "TYT"
                        and (
                            d.startswith("TYT")
                            or d
                            in [
                                "Matematik ve Veri",
                                "Gramer ve Kelime",
                                "Soru Tipleri",
                            ]
                        )
                    )
                    or (
                        st.session_state.wiz_tur == "AYT"
                        and d.startswith("AYT")
                    )
                    or (
                        st.session_state.wiz_tur == "YDT"
                        and ("YDT" in d or "İngilizce" in d)
                    )
                ]
                if not uyumlu_dersler:
                    uyumlu_dersler = list(ctx.mufredat.keys())
                # FAZ 2: TEK branş dersi seçimi. Widget anahtarı ayrı tutulur,
                # seçim `wiz_brans_dersi` state'ine yazılır; böylece sihirbazın
                # sonraki adımlarında (widget ekranda yokken) değer korunur.
                secilen_brans = st.selectbox(
                    "Branş Dersi Seçimi:",
                    options=uyumlu_dersler,
                    key="wiz_brans_secim",
                )
                st.session_state.wiz_brans_dersi = secilen_brans
                max_net_val = (
                    40.0
                    if "Matematik" in secilen_brans or "Türkçe" in secilen_brans
                    else 80.0
                )
                st.session_state.wiz_net = st.number_input(
                    "Branş Netiniz:",
                    min_value=0.0,
                    max_value=max_net_val,
                    value=min(25.0, max_net_val),
                    step=0.25,
                )
                # FAZ 3: branş sonucu ders tablosuna bağlanır. Doğru/yanlış
                # girilirse net otomatik hesaplanır ve başlığa o değer yazılır.
                wiz_brans_detay = None
                with st.expander("🔍 Ders Detayı (opsiyonel)", expanded=False):
                    st.caption(
                        "Doğru / yanlış sayılarınızı girerseniz net"
                        " **Doğru − Yanlış/4** olarak otomatik hesaplanır ve"
                        " ders bazlı grafikte görünür. Girmezseniz yalnızca"
                        " toplam branş neti kaydedilir."
                    )
                    detay_col1, detay_col2 = st.columns(2)
                    with detay_col1:
                        detay_soru = st.number_input(
                            "Soru Sayısı:",
                            min_value=DERS_SONUC_MIN_SORU,
                            max_value=DERS_SONUC_MAKS_SORU,
                            value=40 if st.session_state.wiz_tur != "YDT" else 80,
                            step=1,
                            key="wiz_brans_soru",
                        )
                        detay_dogru = st.number_input(
                            "Doğru:",
                            min_value=0,
                            max_value=DERS_SONUC_MAKS_SORU,
                            value=0,
                            step=1,
                            key="wiz_brans_dogru",
                        )
                    with detay_col2:
                        detay_yanlis = st.number_input(
                            "Yanlış:",
                            min_value=0,
                            max_value=DERS_SONUC_MAKS_SORU,
                            value=0,
                            step=1,
                            key="wiz_brans_yanlis",
                        )
                        detay_bos = st.number_input(
                            "Boş:",
                            min_value=0,
                            max_value=DERS_SONUC_MAKS_SORU,
                            value=0,
                            step=1,
                            key="wiz_brans_bos",
                        )
                    if detay_dogru + detay_yanlis > 0:
                        try:
                            wiz_brans_detay = ders_sonucu_dogrula(
                                secilen_brans,
                                detay_dogru,
                                detay_yanlis,
                                detay_bos,
                                detay_soru,
                            )
                        except ValueError as detay_hata:
                            st.error(f"⚠️ {detay_hata}")
                            wiz_brans_detay = None
                        if wiz_brans_detay:
                            st.session_state.wiz_net = wiz_brans_detay["net"]
                            st.info(
                                "Doğru/yanlışa göre hesaplanan net:"
                                f" **{wiz_brans_detay['net']:.2f}** — kayıtta bu"
                                " değer kullanılacak."
                            )
                st.session_state.wiz_brans_detay = wiz_brans_detay
                st.session_state.wiz_ders_sonuclari = (
                    [wiz_brans_detay] if wiz_brans_detay else []
                )
            else:
                st.session_state.wiz_brans_dersi = None
                st.session_state.wiz_brans_detay = None
                ders_secenekleri = genel_ders_secenekleri(
                    st.session_state.wiz_tur, ogrenci_alan
                )
                mod_secenekleri = ["Ders Bazlı", "Sadece Toplam Net"]
                if not ders_secenekleri:
                    mod_secenekleri = ["Sadece Toplam Net"]
                if st.session_state.get("wiz_ders_modu") not in mod_secenekleri:
                    st.session_state.wiz_ders_modu = mod_secenekleri[0]
                # FAZ 3: genel denemenin ders bazlı netleri. Net her zaman
                # doğru/yanlıştan hesaplanır; aynı bilgi ikinci kez sorulmaz.
                st.radio(
                    "Genel Deneme Giriş Yöntemi:",
                    options=mod_secenekleri,
                    horizontal=True,
                    key="wiz_ders_modu",
                    help=(
                        "Ders bazlı sonuçlarınız varsa her ders için doğru /"
                        " yanlış / boş girin. Elinizde ders kırılımı yoksa"
                        " 'Sadece Toplam Net' seçeneğini kullanın."
                    ),
                )
                if st.session_state.wiz_ders_modu == "Ders Bazlı":
                    st.caption(
                        "Her ders için doğru / yanlış / boş sayısını girin."
                        " Netler otomatik hesaplanır; boş bıraktığınız ders"
                        " kaydedilmez."
                    )
                    if st.session_state.wiz_tur == "AYT":
                        st.caption(
                            "ℹ️ ÖSYM düzeninde AYT Geometri soruları Matematik"
                            " Testinin içindedir (toplam 40 soru); bu yüzden"
                            " ayrı geometri satırı yoktur. Geometriyi ayrı"
                            " takip etmek isterseniz branş denemesi girin."
                        )
                    varsayilan_satirlar = [
                        {
                            "Ders": d_ad,
                            "Soru Sayısı": int(soru),
                            "Doğru": 0,
                            "Yanlış": 0,
                            "Boş": 0,
                        }
                        for d_ad, soru in ders_secenekleri
                    ]
                    duzenlenen = st.data_editor(
                        pd.DataFrame(varsayilan_satirlar),
                        key=(
                            "wiz_ders_editor_"
                            + sanitize_key(st.session_state.wiz_tur)
                            + "_"
                            + sanitize_key(
                                ders_secenekleri[0][0] if ders_secenekleri else "x"
                            )
                        ),
                        hide_index=True,
                        disabled=["Ders"],
                        column_config={
                            "Ders": st.column_config.TextColumn("Ders"),
                            "Soru Sayısı": st.column_config.NumberColumn(
                                "Soru Sayısı",
                                min_value=DERS_SONUC_MIN_SORU,
                                max_value=DERS_SONUC_MAKS_SORU,
                                step=1,
                                help="Dersin toplam soru sayısı",
                            ),
                            "Doğru": st.column_config.NumberColumn(
                                "Doğru", min_value=0, max_value=DERS_SONUC_MAKS_SORU, step=1
                            ),
                            "Yanlış": st.column_config.NumberColumn(
                                "Yanlış", min_value=0, max_value=DERS_SONUC_MAKS_SORU, step=1
                            ),
                            "Boş": st.column_config.NumberColumn(
                                "Boş", min_value=0, max_value=DERS_SONUC_MAKS_SORU, step=1
                            ),
                        },
                    )
                    for _, satir in duzenlenen.iterrows():
                        try:
                            kayit = ders_sonucu_dogrula(
                                satir.get("Ders"),
                                satir.get("Doğru"),
                                satir.get("Yanlış"),
                                satir.get("Boş"),
                                satir.get("Soru Sayısı"),
                            )
                        except ValueError as satir_hata:
                            ders_hatalari.append(str(satir_hata))
                            continue
                        if kayit["dogru"] + kayit["yanlis"] + kayit["bos"] == 0:
                            continue
                        ders_girdileri.append(kayit)
                    toplam_ders_neti = ders_toplam_neti(ders_girdileri)
                    olcu1, olcu2 = st.columns(2)
                    olcu1.metric(
                        "Derslerden Hesaplanan Toplam Net",
                        f"{toplam_ders_neti:.2f}",
                    )
                    olcu2.metric(
                        "Sonuç Girilen Ders",
                        f"{len(ders_girdileri)} / {len(ders_secenekleri)}",
                    )
                    if ders_girdileri:
                        st.caption(
                            "Ders netleri: "
                            + " • ".join(
                                f"{g['ders']} {g['net']:.2f}"
                                for g in ders_girdileri
                            )
                        )
                    for hata_metni in ders_hatalari:
                        st.error(f"⚠️ {hata_metni}")
                    st.session_state.wiz_net = toplam_ders_neti
                    st.session_state.wiz_ders_sonuclari = ders_girdileri
                else:
                    max_genel_net = (
                        120.0 if st.session_state.wiz_tur == "TYT" else 80.0
                    )
                    st.session_state.wiz_net = st.number_input(
                        "Toplam Netiniz:",
                        min_value=0.0,
                        max_value=max_genel_net,
                        value=min(75.0, max_genel_net),
                        step=0.25,
                    )
                    st.session_state.wiz_ders_sonuclari = []
        if st.button("İleri ➔ Ders Seçimine Geç", type="primary"):
            if not st.session_state.wiz_adi.strip():
                st.error("Lütfen denemenin adını giriniz!")
            elif ders_hatalari:
                st.error(
                    "Ders sonuçlarında hata var, lütfen düzeltiniz: "
                    + " | ".join(ders_hatalari)
                )
            elif (
                st.session_state.wiz_kategori == "Genel Deneme"
                and st.session_state.get("wiz_ders_modu") == "Ders Bazlı"
                and not st.session_state.wiz_ders_sonuclari
            ):
                st.error(
                    "Ders bazlı giriş seçtiniz ancak hiçbir derse sonuç"
                    " girmediniz. En az bir ders için doğru/yanlış girin ya da"
                    " 'Sadece Toplam Net' seçeneğine geçin."
                )
            elif st.session_state.wiz_kategori == "Branş Denemesi":
                st.session_state.wiz_selected_dersler = [
                    st.session_state.wiz_brans_dersi
                ]
                queue = []
                mak_dict = ctx.mufredat.get(
                    st.session_state.wiz_brans_dersi, {}
                )
                if isinstance(mak_dict, dict):
                    for mak_k, mik_v in mak_dict.items():
                        queue.append({
                            "ders": st.session_state.wiz_brans_dersi,
                            "makro": mak_k,
                            "mikro_listesi": mik_v,
                        })
                st.session_state.wiz_queue = queue
                st.session_state.wiz_card_idx = 0
                st.session_state.wiz_show_details = False
                st.session_state.wiz_step = 3
                st.rerun()
            else:
                st.session_state.wiz_step = 2
                st.rerun()

    elif st.session_state.wiz_step == 2:
        st.markdown(
            '<div class="sim-card"><h3>2. Adım: Yanlış Yapılan Dersler</h3><p>Bu'
            " denemede yanlış veya boş bıraktığınız dersleri seçiniz.</p></div>",
            unsafe_allow_html=True,
        )
        secilen_tur = st.session_state.wiz_tur
        filtrated_dersler = [
            d
            for d in ctx.mufredat.keys()
            if (
                secilen_tur == "TYT"
                and (
                    d.startswith("TYT")
                    or d
                    in [
                        "Matematik ve Veri",
                        "Gramer ve Kelime",
                        "Soru Tipleri",
                    ]
                )
            )
            or (secilen_tur == "AYT" and d.startswith("AYT"))
            or (secilen_tur == "YDT" and ("YDT" in d or "İngilizce" in d))
        ]
        if not filtrated_dersler:
            filtrated_dersler = list(ctx.mufredat.keys())

        seçilen_dersler = st.multiselect(
            f"Yanlış Bulunan {secilen_tur} Dersleri:",
            options=filtrated_dersler,
            default=(
                filtrated_dersler[:2]
                if len(filtrated_dersler) >= 2
                else filtrated_dersler
            ),
        )
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("⬅️ Geri Dön"):
                st.session_state.wiz_step = 1
                st.rerun()
        with col_b2:
            if st.button("İleri ➔ Konu İncelemesine Başla 🚀", type="primary"):
                if seçilen_dersler:
                    st.session_state.wiz_selected_dersler = seçilen_dersler
                    queue = []
                    for d_ad in seçilen_dersler:
                        mak_dict = ctx.mufredat.get(d_ad, {})
                        if isinstance(mak_dict, dict):
                            for mak_k, mik_v in mak_dict.items():
                                queue.append({
                                    "ders": d_ad,
                                    "makro": mak_k,
                                    "mikro_listesi": mik_v,
                                })
                    st.session_state.wiz_queue = queue
                    st.session_state.wiz_card_idx = 0
                    st.session_state.wiz_show_details = False
                    st.session_state.wiz_step = 3
                    st.rerun()
                else:
                    st.warning("En az 1 ders seçmelisiniz!")

    elif st.session_state.wiz_step == 3:
        queue = st.session_state.wiz_queue
        card_idx = st.session_state.wiz_card_idx
        if card_idx >= len(queue):
            # FAZ 2: Deneme başlığı + yanlış detayları TEK transaction'da ve
            # YALNIZCA BİR KEZ burada yazılır. (Eski akışta 4. adım her
            # rerun'unda yeniden INSERT ediyordu -> çift kayıt.)
            kayit_sonuc = {"deneme_id": None, "hata": None}
            try:
                with get_connection() as _conn:
                    kayit_sonuc["deneme_id"] = deneme_kaydet(
                        _conn,
                        ogrenci_id=ctx.user["id"],
                        deneme_adi=st.session_state.wiz_adi,
                        deneme_kategorisi=st.session_state.wiz_kategori,
                        deneme_turu=st.session_state.wiz_tur,
                        brans_dersi=st.session_state.wiz_brans_dersi,
                        net_bilgisi=float(st.session_state.wiz_net or 0.0),
                        tarih=st.session_state.wiz_tarih,
                        yanlislar=st.session_state.wiz_draft_mistakes,
                        ders_sonuclari=list(
                            st.session_state.get("wiz_ders_sonuclari") or []
                        ),
                    )
            except Exception as kayit_hatasi:
                kayit_sonuc["hata"] = str(kayit_hatasi)
            st.session_state.wiz_kayit_sonuc = kayit_sonuc
            if kayit_sonuc["hata"] is None:
                log_islem(
                    ctx.user["id"],
                    "FINISH_EXAM_ANALYSIS",
                    f"{st.session_state.wiz_adi}:"
                    f" {len(st.session_state.wiz_draft_mistakes)} yanlış"
                    f" kaydedildi (deneme_id={kayit_sonuc['deneme_id']}).",
                )
            st.session_state.wiz_step = 4
            st.rerun()

        current_card = queue[card_idx]
        toplam_kart = len(queue)
        progress_val = (card_idx + 1) / toplam_kart
        st.progress(progress_val)
        st.caption(
            f"Konu Kontrolü: {card_idx + 1} / {toplam_kart} ➔"
            f" **{current_card['ders']}**"
        )

        col_hdr1, col_hdr2 = st.columns([3, 1])
        with col_hdr1:
            st.markdown(
                f'<div class="card-ders-title">📘 {current_card["ders"]}</div>',
                unsafe_allow_html=True,
            )
        with col_hdr2:
            if st.button(
                "⚡ Kalan Konuları Temiz Geç", key=f"btn_fp_{card_idx}"
            ):
                cur_ders = current_card["ders"]
                while (
                    st.session_state.wiz_card_idx < len(queue)
                    and queue[st.session_state.wiz_card_idx]["ders"]
                    == cur_ders
                ):
                    st.session_state.wiz_card_idx += 1
                st.session_state.wiz_show_details = False
                set_flash_message(
                    "success", f"{cur_ders} dersinin kalan konuları geçildi."
                )
                st.rerun()

        st.markdown(
            f'<div class="single-card-container"><div'
            f' class="card-konu-title">{current_card["makro"]}</div><p'
            ' style="font-size: 1.1rem; color: #374151;">Bu konuda yanlış'
            " veya boşunuz var mı?</p></div>",
            unsafe_allow_html=True,
        )

        if not st.session_state.wiz_show_details:
            st.markdown(
                '<div class="card-mega-buttons">', unsafe_allow_html=True
            )
            col_no, col_yes = st.columns(2)
            with col_no:
                if st.button("🟢 HAYIR (SORUN YOK)", key=f"btn_mega_no_{card_idx}"):
                    st.session_state.wiz_card_idx += 1
                    st.session_state.wiz_show_details = False
                    st.rerun()
            with col_yes:
                if st.button("🔴 EVET (YANLIŞ VAR)", key=f"btn_mega_yes_{card_idx}"):
                    st.session_state.wiz_show_details = True
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning(
                f"⚠️ **{current_card['makro']}** konusu detaylarını seçin:"
            )
            secili_mikrolar = st.multiselect(
                "Hangi Alt Konuda Yanlış Yaşadınız?",
                options=current_card["mikro_listesi"],
                key=f"card_mikro_{card_idx}",
            )

            # ÇARPAN BUG'I ÇÖZÜMÜ: Alt konulara özel yanlış sayısı girilmesi
            mikro_yanlis_map = {}
            if secili_mikrolar:
                st.write("**Seçilen Her Alt Konunun Yanlış Sayısını Giriniz:**")
                for mik_item in secili_mikrolar:
                    mikro_yanlis_map[mik_item] = st.number_input(
                        f"• '{mik_item}' Yanlış Sayısı:",
                        min_value=1,
                        max_value=20,
                        value=1,
                        key=f"card_y_num_{card_idx}_{mik_item}",
                    )

            nedenler = st.multiselect(
                "Hata Nedeni:",
                [
                    "Konu Eksikliği",
                    "İşlem / Dikkat Hatası",
                    "Süre Yetişmedi",
                    "İki Şık Arasında Kaldım",
                    "Soruyu Yanlış Okudum",
                ],
                default=["Konu Eksikliği"],
                key=f"card_neden_{card_idx}",
            )
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                if st.button("⬅️ İptal Et (Hayır Say)"):
                    st.session_state.wiz_show_details = False
                    st.rerun()
            with col_c2:
                if st.button(
                    "Kaydet ve Devam Et ➔", type="primary"
                ):
                    if secili_mikrolar:
                        for mik in secili_mikrolar:
                            st.session_state.wiz_draft_mistakes.append({
                                "ders": current_card["ders"],
                                "makro": current_card["makro"],
                                "mikro": mik,
                                "yanlis_adedi": mikro_yanlis_map[mik],
                                "nedenler": ", ".join(nedenler),
                            })
                        st.session_state.wiz_card_idx += 1
                        st.session_state.wiz_show_details = False
                        st.rerun()
                    else:
                        st.error("En az 1 alt konu seçiniz!")

    elif st.session_state.wiz_step == 4:
        kayit_sonuc = st.session_state.wiz_kayit_sonuc or {}
        drafts = st.session_state.wiz_draft_mistakes
        if kayit_sonuc.get("hata"):
            st.error(
                "❌ Deneme kaydı oluşturulamadı: " + str(kayit_sonuc["hata"])
            )
        else:
            st.markdown(
                '<div class="sim-card"><h3>🎉 Deneme Analiziniz'
                " Kaydedildi!</h3><p><b>"
                f"[{st.session_state.wiz_kategori}] {st.session_state.wiz_tur} -"
                f" {st.session_state.wiz_adi}"
                f" ({st.session_state.wiz_net} Net)</b>"
                " kaydı oluşturuldu.</p></div>",
                unsafe_allow_html=True,
            )
            st.caption(
                f"Deneme ID: {kayit_sonuc.get('deneme_id')} • Tarih:"
                f" {st.session_state.wiz_tarih}"
            )
            kaydedilen_dersler = list(
                st.session_state.get("wiz_ders_sonuclari") or []
            )
            if kaydedilen_dersler:
                st.caption(
                    f"Ders bazlı {len(kaydedilen_dersler)} sonuç kaydedildi: "
                    + " • ".join(
                        f"{d['ders']} {float(d['net']):.2f}"
                        for d in kaydedilen_dersler
                    )
                )
        if drafts:
            st.subheader("📌 Çalışma Listesine Eklenen Konular:")
            st.dataframe(pd.DataFrame(drafts), width="stretch")
        else:
            st.info(
                "Bu denemede yanlış konusu bulunmuyor. Deneme kaydı yine de"
                " oluşturuldu. Tebrikler!"
            )

        # FAZ 6B: toplu yanlış sayılarından bağımsız olarak, hatırlanan tek
        # tek soruların yanlış soru defterine hızlı eklenmesi.
        if drafts and not kayit_sonuc.get("hata"):
            with st.expander("📕 Bu denemenin yanlışlarını deftere ekle"):
                st.caption(
                    "Konu bazlı yanlış sayısı deneme analizinde tutulur. Burada"
                    " tek tek hatırladığınız soruları deftere işleyebilirsiniz;"
                    " tekrar zamanı gelen sorular programa görev olarak eklenir."
                )
                hizli_etiketler = [
                    "%s › %s" % (d["ders"], d["mikro"]) for d in drafts
                ]
                with st.form("defter_deneme_hizli_ekle"):
                    hizli_secim = st.selectbox(
                        "Konu", hizli_etiketler, key="wiz_defter_konu"
                    )
                    hizli_hata = st.selectbox(
                        "Hata türü",
                        wrong_questions.HATA_TURLERI,
                        key="wiz_defter_hata",
                    )
                    hizli_soru = st.text_area(
                        "Soru metni / kısa açıklama",
                        key="wiz_defter_soru",
                        height=80,
                    )
                    hizli_no = st.text_input(
                        "Soru numarası", key="wiz_defter_no"
                    )
                    if st.form_submit_button("📕 Deftere Ekle"):
                        hizli_draft = drafts[hizli_etiketler.index(hizli_secim)]
                        try:
                            hizli_kayit = wrong_questions.yanlis_soru_ekle(
                                ctx.user["id"],
                                hizli_draft["ders"],
                                hizli_draft["mikro"],
                                makro_konu=hizli_draft.get("makro"),
                                hata_turu=hizli_hata,
                                soru_metni=hizli_soru,
                                soru_no=hizli_no,
                                deneme_id=kayit_sonuc.get("deneme_id"),
                                deneme_tarihi=st.session_state.wiz_tarih,
                            )
                        except wrong_questions.YanlisSoruHatasi as hizli_hatasi:
                            st.error(str(hizli_hatasi))
                        else:
                            log_islem(
                                ctx.user["id"],
                                "WRONG_QUESTION_ADD",
                                "#%d %s › %s (deneme %s)"
                                % (
                                    hizli_kayit["id"],
                                    hizli_draft["ders"],
                                    hizli_draft["mikro"],
                                    kayit_sonuc.get("deneme_id"),
                                ),
                            )
                            set_flash_message(
                                "success",
                                "📕 Soru deftere eklendi (#%d)."
                                % hizli_kayit["id"],
                            )
                            st.rerun()

        if st.button("🚀 Yeni Deneme Ekle", type="primary"):
            st.session_state.wiz_step = 1
            st.session_state.wiz_draft_mistakes = []
            st.session_state.wiz_selected_dersler = []
            st.session_state.wiz_card_idx = 0
            st.session_state.wiz_show_details = False
            st.session_state.wiz_kayit_sonuc = None
            st.session_state.wiz_brans_dersi = ""
            st.session_state.wiz_brans_detay = None
            st.session_state.wiz_ders_sonuclari = []
            st.session_state.wiz_ders_modu = "Ders Bazlı"
            st.rerun()

    st.markdown("---")
    st.subheader("📊 Net Gelişim Grafikleri ve Filtreleme")

    # FAZ 2: Grafikler `denemeler` tablosundan, FAZ 3 ders bazlı seriler
    # `deneme_ders_sonuclari` tablosundan beslenir. Genel deneme (TYT / AYT),
    # genel denemenin ders netleri ve her branş denemesi AYRI seridir.
    with get_connection() as conn:
        df_denemeler = denemeleri_getir(conn, ctx.user["id"])
        df_ders_sonuclari = deneme_ders_sonuclari_getir(conn, ctx.user["id"])
        baglanmamis_adet = baglanmamis_yanlis_sayisi(conn, ctx.user["id"])

    if baglanmamis_adet:
        st.warning(
            f"⚠️ {baglanmamis_adet} eski yanlış kaydı bir deneme başlığına"
            " bağlanamadığı için grafik ve alarm hesaplarına dahil edilmedi."
            " Kayıtlar silinmedi; koçunuzla birlikte kontrol edebilirsiniz."
        )

    hedef_ayt_turu = "YDT" if ctx.user["hedef_alan"] == "Dil" else "AYT"

    grafik_tab1, grafik_tab2, grafik_tab3 = st.tabs(
        [
            "📈 TYT Denemeleri",
            f"📈 {hedef_ayt_turu} Denemeleri",
            "🔍 Hata Nedenleri",
        ],
        key="kt_deneme_grafik_tabs",
        on_change="rerun",
    )

    def _deneme_grafigi(df_kaynak, df_ders, sinav_turu, selectbox_key):
        """Tek bir seriyi (genel toplam / ders bazlı / branş) kronolojik çizer."""
        secenekler = grafik_seri_secenekleri(df_kaynak, sinav_turu, df_ders)
        if not secenekler:
            st.info(f"Henüz {sinav_turu} denemesi kaydı bulunmuyor.")
            return
        etiket = st.selectbox(
            "İncelenecek Seri:",
            [s["etiket"] for s in secenekler],
            key=selectbox_key,
        )
        secenek = next(
            (s for s in secenekler if s["etiket"] == etiket), secenekler[0]
        )
        if secenek.get("kaynak") == "ders":
            seri = ders_net_serisi(
                df_ders, sinav_turu, secenek["ders"], secenek["kategori"]
            )
            net_kolonu = "net"
        else:
            seri = seri_filtrele(
                df_kaynak, secenek["kategori"], secenek["brans_dersi"]
            )
            net_kolonu = "net_bilgisi"
        if seri is None or seri.empty:
            st.info("Bu seride gösterilecek deneme bulunamadı.")
            return
        grafik_df = seri[["tarih", net_kolonu]].rename(
            columns={net_kolonu: secenek["etiket"]}
        )
        st.line_chart(grafik_df.set_index("tarih"))

        # FAZ 3: özet metrikler. Yetersiz veride ortalama/gelişim gösterilmez.
        ozet = net_ozeti(seri[net_kolonu].tolist())
        olcu1, olcu2, olcu3, olcu4 = st.columns(4)
        olcu1.metric("Deneme Sayısı", ozet["adet"])
        olcu2.metric(
            "Son Net", "—" if ozet["son"] is None else f"{ozet['son']:.2f}"
        )
        olcu3.metric(
            "En Yüksek Net",
            "—" if ozet["en_yuksek"] is None else f"{ozet['en_yuksek']:.2f}",
        )
        olcu4.metric(
            "Son 3 Ortalama",
            "—"
            if ozet["son_uc_ortalama"] is None
            else f"{ozet['son_uc_ortalama']:.2f}",
        )
        if ozet["adet"] < 3:
            st.caption(
                "ℹ️ Son 3 deneme ortalaması için en az 3 deneme gerekir"
                f" (şu an {ozet['adet']})."
            )
        elif ozet["gelisim"] is None:
            st.caption(
                "ℹ️ Gelişim yorumu için en az 6 deneme gerekir"
                f" (şu an {ozet['adet']})."
            )
        else:
            yon = "▲" if ozet["gelisim"] >= 0 else "▼"
            st.caption(
                f"Gelişim: son 3 ortalama, önceki 3 ortalamaya göre"
                f" {yon} {abs(ozet['gelisim']):.2f} net."
            )
        st.caption(
            f"{len(seri)} deneme • X ekseni deneme tarihi • aynı adlı"
            " denemeler ayrı nokta olarak gösterilir."
        )
        with st.expander("📋 Grafik Noktaları (Tarih • Deneme Adı • Net)"):
            id_kolonu = "deneme_id" if secenek.get("kaynak") == "ders" else "id"
            tablo = seri[[id_kolonu, "tarih", "deneme_adi", net_kolonu]].copy()
            tablo.columns = ["Deneme ID", "Tarih", "Deneme Adı", "Net"]
            if secenek.get("kaynak") == "ders":
                tablo.insert(3, "Ders", secenek["ders"])
            st.dataframe(tablo, width="stretch", hide_index=True)

    # FAZ 3: ders bazlı performans özeti (genel denemeler).
    if df_ders_sonuclari is not None and not df_ders_sonuclari.empty:
        with st.expander("📚 Ders Bazlı Performans Özeti", expanded=False):
            ozet_satirlari = []
            for ozet_tur in ("TYT", hedef_ayt_turu):
                for ozet_ders in ders_seri_listesi(df_ders_sonuclari, ozet_tur):
                    alt_seri = ders_net_serisi(df_ders_sonuclari, ozet_tur, ozet_ders)
                    alt_ozet = net_ozeti(alt_seri["net"].tolist())
                    ozet_satirlari.append({
                        "Sınav": ozet_tur,
                        "Ders": ozet_ders,
                        "Deneme": alt_ozet["adet"],
                        "Son Net": alt_ozet["son"],
                        "Son 3 Ort.": alt_ozet["son_uc_ortalama"],
                        "En Yüksek": alt_ozet["en_yuksek"],
                    })
            if ozet_satirlari:
                st.dataframe(
                    pd.DataFrame(ozet_satirlari),
                    width="stretch",
                    hide_index=True,
                )
                st.caption(
                    "Ortalama ve gelişim yalnızca yeterli deneme sayısına"
                    " ulaşıldığında gösterilir."
                )
            else:
                st.info(
                    "Genel denemelerde ders bazlı sonuç bulunmuyor. Yeni"
                    " denemeleri ders bazlı girerek burada gelişimi"
                    " izleyebilirsiniz."
                )

    with grafik_tab1:
        _deneme_grafigi(df_denemeler, df_ders_sonuclari, "TYT", "kt_tyt_seri")

    with grafik_tab2:
        _deneme_grafigi(
            df_denemeler, df_ders_sonuclari, hedef_ayt_turu, "kt_ayt_seri"
        )

    with grafik_tab3:
        with get_connection() as conn:
            df_nedenler = pd.read_sql_query(
                "SELECT yanlis_nedeni, SUM(yanlis_adedi) as toplam_yanlis FROM"
                " deneme_konu_yanlislari WHERE ogrenci_id = ? GROUP BY"
                " yanlis_nedeni",
                conn,
                params=(ctx.user["id"],),
            )
        if not df_nedenler.empty:
            st.bar_chart(df_nedenler.set_index("yanlis_nedeni")["toplam_yanlis"])
        else:
            st.info("Henüz hata verisi bulunmuyor.")
