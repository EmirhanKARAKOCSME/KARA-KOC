"""Sekme 9 - YKS Puan ve Sıralama Simülatörü."""


import pandas as pd
import streamlit as st

from config.database import log_islem
from services import osym_verisi
from services import ranking_engine
from views.shared import sanitize_key, set_flash_message


SIM_KAYNAK_OTO = "Son denemelerimden otomatik"


SIM_KAYNAK_MANUEL = "Manuel giriş"


SIM_KAYNAK_HEDEF = "Hedef netlerim"


SIM_DURUM_ETIKETLERI = {
    "hedefte": "✅ Hedefte",
    "hedefin_altinda": "⬇️ Hedefin altında",
    "hedef_yok": "— Hedef yok",
    "mevcut_yok": "— Deneme yok",
    "veri_yok": "— Veri yok",
}


SIM_SIRALAMA_NOTLARI = {
    "veri_yok": (
        "Sıralama tahmini üretilmedi: seçilen yıl ve puan türü için"
        " doğrulanmış puan–sıra referans verisi yok."
    ),
    "veri_yetersiz": (
        "Sıralama tahmini üretilmedi: referans noktası sayısı yetersiz."
    ),
    "aralik_disi": (
        "Sıralama tahmini üretilmedi: puan, girilen referans noktalarının"
        " puan aralığının dışında."
    ),
}


def sim_puan_turu_varsayilani(hedef_alan):
    """Öğrencinin hedef alanını puan türüne çevirir (geçersizse Sayısal)."""
    try:
        return osym_verisi.puan_turu_kontrol(hedef_alan)
    except osym_verisi.VeriHatasi:
        return "Sayısal"


def sim_sira_metni(sira):
    """18000 -> '~18.000' (okunur biçim)."""
    if sira is None:
        return "—"
    return "~{:,}".format(int(sira)).replace(",", ".")


def render(ctx):
    st.header("🎯 YKS Puan ve Sıralama Simülatörü")
    st.caption(
        "Netlerinizden **model puan** hesaplanır. Sıralama tahmini yalnızca"
        " doğrulanmış puan–sıra referans verisi varsa üretilir; bu ekran resmî"
        " ÖSYM sonucu göstermez."
    )

    sim_veri = ranking_engine.veri_durumu()
    sim_model = sim_veri["model"]

    with st.expander("ℹ️ Nasıl hesaplanıyor? Kaynak, yöntem ve sınırlar"):
        st.markdown(
            "**Puan (model):** 100 taban puan + her testin neti × test katsayısı"
            " + OBP katkısı. Net = doğru − yanlış / 4."
        )
        st.markdown(
            "**OBP:** OBP = diploma notu × 5, katkı = OBP × 0.12 (en fazla 60"
            " puan). OBP'yi puana ekleyip eklememek sizin seçiminizdir."
        )
        st.markdown(
            "**Sıralama:** yalnızca `data/osym_puan_sira.json` içindeki"
            " doğrulanmış puan–sıra noktaları kullanılır. Noktalar arasında"
            " doğrusal tahmin yapılır; aralık dışına tahmin üretilmez."
        )
        st.warning(sim_model["kaynak"]["sinirlilik"], icon="⚠️")
        st.caption(
            "Kural kaynağı: %s · %s"
            % (sim_model["kaynak"]["kurum"], sim_model["kaynak"]["belge"])
        )
        st.caption(
            "Desteklenen sınav yılları: %s – %s · Katsayı seti doğrulama durumu:"
            " **%s**"
            % (
                sim_model["yillar"][0],
                sim_model["yillar"][-1],
                sim_model["dogrulama_durumu"],
            )
        )

    sim_puan_turu_varsayilan = sim_puan_turu_varsayilani(
        ctx.user.get("hedef_alan")
    )
    sim_puan_turu_listesi = list(osym_verisi.PUAN_TURLERI)
    # Mobilde sıkışmasın diye kontroller iki satıra bölünür.
    sim_kol_puan, sim_kol_yil = st.columns(2)
    with sim_kol_puan:
        sim_puan_turu = st.selectbox(
            "Puan türü",
            sim_puan_turu_listesi,
            index=sim_puan_turu_listesi.index(sim_puan_turu_varsayilan),
            key="sim_puan_turu",
        )
    with sim_kol_yil:
        sim_yil_listesi = list(reversed(osym_verisi.desteklenen_yillar()))
        sim_yil = st.selectbox(
            "Sınav yılı", sim_yil_listesi, index=0, key="sim_yil"
        )
    sim_kol_obp, sim_kol_obp_secim = st.columns(2)
    with sim_kol_obp:
        sim_diploma = st.number_input(
            "Diploma notu (OBP)",
            min_value=50.0,
            max_value=100.0,
            value=float(ctx.user.get("diploma_notu") or 85.0),
            step=0.1,
            key="sim_diploma",
        )
    with sim_kol_obp_secim:
        sim_obp_dahil = st.toggle(
            "OBP'yi puana ekle", value=True, key="sim_obp_dahil"
        )

    st.caption(
        "OBP %.0f → katkı +%.2f puan (diploma notunu değiştirmek için kenar"
        " çubuğundaki **Profili Güncelle** formunu kullanın)."
        % (
            osym_verisi.obp_puani(sim_diploma),
            osym_verisi.obp_katkisi(sim_diploma, sim_yil),
        )
    )

    sim_mevcut = ranking_engine.mevcut_netler(ctx.user["id"])
    sim_hedefler = ranking_engine.hedef_netleri_getir(
        ctx.user["id"], sim_puan_turu
    )

    sim_kaynak_listesi = [SIM_KAYNAK_OTO, SIM_KAYNAK_MANUEL]
    if sim_hedefler:
        sim_kaynak_listesi.append(SIM_KAYNAK_HEDEF)
    sim_varsayilan_kaynak = (
        SIM_KAYNAK_OTO if sim_mevcut["kayit_var"] else SIM_KAYNAK_MANUEL
    )
    sim_kaynak = st.radio(
        "Netler nereden gelsin?",
        sim_kaynak_listesi,
        index=sim_kaynak_listesi.index(sim_varsayilan_kaynak),
        horizontal=True,
        key="sim_kaynak_%s" % sanitize_key(sim_puan_turu),
    )

    if sim_kaynak == SIM_KAYNAK_OTO:
        if not sim_mevcut["kayit_var"]:
            st.info(
                "Ders bazlı net içeren genel denemeniz henüz yok. Netleri"
                " **Manuel giriş** ile girebilirsiniz; **Deneme Analizi**"
                " sekmesinde ders detayı girerseniz bu alan otomatik dolar.",
                icon="ℹ️",
            )
            sim_son_deneme = ranking_engine.VARSAYILAN_SON_DENEME
        else:
            sim_son_deneme = st.slider(
                "Kaç son genel denemenin ortalaması alınsın?",
                min_value=1,
                max_value=ranking_engine.MAKS_SON_DENEME,
                value=ranking_engine.VARSAYILAN_SON_DENEME,
                key="sim_son_deneme",
            )
            if sim_son_deneme != ranking_engine.VARSAYILAN_SON_DENEME:
                sim_mevcut = ranking_engine.mevcut_netler(
                    ctx.user["id"], son_deneme=sim_son_deneme
                )

            sim_deneme_ozeti = ", ".join(
                "%s: %d" % (tur, adet)
                for tur, adet in sim_mevcut["deneme_sayisi"].items()
                if adet
            )
            st.caption(
                "%s · %s"
                % (
                    sim_mevcut["yontem"] or "Deneme verisi yok",
                    sim_deneme_ozeti or "—",
                )
            )
            for sim_uyari in sim_mevcut["uyarilar"]:
                st.caption("• %s" % sim_uyari)
    elif sim_kaynak == SIM_KAYNAK_HEDEF:
        st.caption(
            "Netler kaydettiğiniz hedef netlerden geliyor. Hedef netler ayrı"
            " saklanır ve mevcut deneme netlerinizin üzerine yazılmaz."
        )
        sim_eksik_hedef_netler = [
            sim_test
            for sim_test in ranking_engine.gereken_testler(sim_puan_turu)
            if sim_test not in sim_hedefler
        ]
        if sim_eksik_hedef_netler:
            st.warning(
                "Bu puan türünde hedef net girmediğiniz testler var: %s."
                " Bu testler 0 kabul edilir; sonuç hedefinizin altında"
                " görünebilir. Aşağıdaki formdan tamamlayabilirsiniz."
                % ", ".join(sim_eksik_hedef_netler)
            )

    else:
        st.caption(
            "Netleri kendiniz girin. Girdiğiniz değerler otomatik olarak"
            " kaydedilmez; yalnızca bu ekrandaki tahmin için kullanılır."
        )

    sim_kaynak_kodu = {
        SIM_KAYNAK_OTO: "oto",
        SIM_KAYNAK_MANUEL: "manuel",
        SIM_KAYNAK_HEDEF: "hedef",
    }[sim_kaynak]
    sim_on_dolu = {}
    if sim_kaynak_kodu == "oto":
        sim_on_dolu.update(sim_mevcut["tyt"])
        sim_on_dolu.update(sim_mevcut["ayt"])
    elif sim_kaynak_kodu == "hedef":
        sim_on_dolu.update(sim_hedefler)

    sim_netler = {}
    with st.expander(
        "📊 Test netleri (düzenlenebilir)",
        expanded=(sim_kaynak_kodu == "manuel"),
    ):
        st.caption(
            "Net = doğru − yanlış / 4. Değerler 0 ile testin soru sayısı"
            " arasında olmalıdır."
        )
        sim_test_kolonlari = st.columns(2)
        for sim_indeks, sim_test in enumerate(
            ranking_engine.gereken_testler(sim_puan_turu)
        ):
            sim_soru_sayisi = osym_verisi.test_soru_sayisi(sim_test) or 40
            sim_net_anahtari = "sim_net_%s_%s" % (
                sim_kaynak_kodu,
                sanitize_key(sim_test),
            )
            if sim_net_anahtari not in st.session_state:
                st.session_state[sim_net_anahtari] = round(
                    float(sim_on_dolu.get(sim_test, 0.0)), 2
                )
            with sim_test_kolonlari[sim_indeks % 2]:
                sim_netler[sim_test] = st.number_input(
                    "%s (0–%d)" % (sim_test, sim_soru_sayisi),
                    min_value=0.0,
                    max_value=float(sim_soru_sayisi),
                    step=0.25,
                    key=sim_net_anahtari,
                )

    try:
        sim_paket = ranking_engine.simulasyon(
            sim_netler, sim_puan_turu, sim_yil, sim_diploma, sim_obp_dahil
        )
    except (osym_verisi.VeriHatasi, ranking_engine.SimulatorHatasi) as sim_hata:
        st.error("Simülasyon hesaplanamadı: %s" % sim_hata)
        sim_paket = None

    sim_puan = None
    sim_siralama = None
    if sim_paket is not None:
        sim_puan = sim_paket["puan"]
        sim_siralama = sim_paket["siralama"]
        if sim_puan["durum"] != ranking_engine.DURUM_OK:
            st.error(
                "Puan hesaplanamadı: %s"
                % "; ".join(sim_puan.get("uyarilar") or ["eksik veri"])
            )
            sim_puan = None

    if sim_puan is not None:
        sim_k1, sim_k2, sim_k3 = st.columns(3)
        with sim_k1:
            st.metric(
                "Model yerleştirme puanı",
                "%.2f" % sim_puan["puan"],
                help="Resmî ÖSYM puanı değildir; doğrusal model tahminidir.",
            )
            st.caption(
                "OBP hariç: %.2f · OBP katkısı: +%.2f"
                % (sim_puan["puan_obp_haric"], sim_puan["obp_katkisi"])
            )
        with sim_k2:
            st.metric("TYT neti", "%.2f" % sim_puan["tyt_net"])
            if sim_puan_turu == "TYT":
                st.caption("TYT puan türünde alan testi kullanılmaz.")
            else:
                st.caption("Alan neti: %.2f" % sim_puan["alan_net"])
        with sim_k3:
            st.metric(
                "Tahmini sıralama",
                sim_sira_metni(
                    sim_siralama.get("sira") if sim_siralama else None
                ),
            )
            st.caption(
                (
                    "Senaryo aralığı: %s – %s"
                    % (
                        sim_sira_metni(sim_siralama["aralik"][0]),
                        sim_sira_metni(sim_siralama["aralik"][1]),
                    )
                )
                if sim_siralama and sim_siralama.get("aralik")
                else "Sıralama aralığı bu veriyle hesaplanamıyor."
            )

        with st.expander("📐 Puan katkıları (test bazında)"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Test": sim_satir["test"],
                            "Net": "%.2f" % sim_satir["net"],
                            "Katsayı": "%.2f" % sim_satir["katsayi"],
                            "Puan katkısı": "%.2f" % sim_satir["katki"],
                        }
                        for sim_satir in sim_puan["test_katkilari"]
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            st.caption(
                "Taban puan %.0f + katkılar = %.2f (ham puan). OBP %s."
                % (
                    sim_puan["kural"]["taban_puan"],
                    sim_puan["ham_puan"],
                    ("eklendi (+%.2f)" % sim_puan["obp_katkisi"])
                    if sim_puan["obp_dahil"]
                    else "eklenmedi",
                )
            )

    st.divider()
    st.subheader("🏆 Başarı sıralaması tahmini")
    if sim_siralama is None:
        st.info("Puan hesaplanmadan sıralama tahmini yapılamaz.")
    elif sim_siralama["durum"] == ranking_engine.DURUM_OK:
        sim_sol, sim_sag = st.columns([1, 2])
        with sim_sol:
            st.metric("Tahmini sıra", sim_sira_metni(sim_siralama["sira"]))
            if sim_siralama.get("aralik"):
                st.caption(
                    "Senaryo aralığı: %s – %s"
                    % (
                        sim_sira_metni(sim_siralama["aralik"][0]),
                        sim_sira_metni(sim_siralama["aralik"][1]),
                    )
                )
        with sim_sag:
            for sim_not in sim_siralama.get("notlar") or []:
                st.caption("• %s" % sim_not)
            st.caption(
                "Referans verisi olan yıllar (%s): %s"
                % (
                    sim_puan_turu,
                    ", ".join(sim_siralama.get("kapsanan_yillar") or []) or "—",
                )
            )
            sim_veri_kaynagi = sim_siralama.get("kaynak") or {}
            if sim_veri_kaynagi:
                st.caption(
                    "Kaynak: %s · %s · Erişim: %s"
                    % (
                        sim_veri_kaynagi.get("kurum") or "—",
                        sim_veri_kaynagi.get("belge") or "—",
                        sim_veri_kaynagi.get("erisim_tarihi") or "belirtilmemiş",
                    )
                )
                if sim_veri_kaynagi.get("url"):
                    st.caption("Bağlantı: %s" % sim_veri_kaynagi["url"])
        if sim_siralama.get("yil_tahminleri"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Yıl": sim_yil_satiri["yil"],
                            "Tahmini sıra": sim_sira_metni(
                                sim_yil_satiri["sira"]
                            ),
                        }
                        for sim_yil_satiri in sim_siralama["yil_tahminleri"]
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
    else:
        st.info(
            SIM_SIRALAMA_NOTLARI.get(
                sim_siralama["durum"], SIM_SIRALAMA_NOTLARI["veri_yok"]
            ),
            icon="ℹ️",
        )
        for sim_eksik in sim_siralama.get("eksik_veri") or []:
            st.caption("• Eksik: %s" % sim_eksik)
        sim_kapsanan_yillar = sim_siralama.get("kapsanan_yillar") or []
        st.caption(
            "Bu puan türü için referans verisi olan yıllar: %s"
            % (", ".join(sim_kapsanan_yillar) if sim_kapsanan_yillar else "yok")
        )
        st.caption(
            "Referans verisi eklendiğinde (yönetici: bu sekmenin altındaki"
            " bölüm) sıralama tahmini otomatik görünür."
        )

    st.divider()
    st.subheader("🎯 Hedef netlerimle karşılaştırma")
    st.caption(
        "Hedef netler ayrı saklanır; mevcut deneme netlerinizin üzerine"
        " yazılmaz. Fark = mevcut − hedef (negatifse hedefin altındasınız)."
    )
    sim_hedef_satirlar = ranking_engine.hedef_karsilastirma(
        ctx.user["id"], sim_puan_turu, sim_mevcut
    )
    sim_hedef_var = [s for s in sim_hedef_satirlar if s["hedef"] is not None]
    sim_mevcut_var = [s for s in sim_hedef_satirlar if s["mevcut"] is not None]
    if not sim_hedef_var and not sim_mevcut_var:
        st.info(
            "Ne kayıtlı hedef netiniz ne de ders bazlı deneme netiniz var."
            " Aşağıdaki formdan hedef netlerinizi girebilirsiniz.",
            icon="ℹ️",
        )
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Test": sim_satir["test"],
                        "Mevcut net": (
                            "%.2f" % sim_satir["mevcut"]
                            if sim_satir["mevcut"] is not None
                            else "—"
                        ),
                        "Hedef net": (
                            "%.2f" % sim_satir["hedef"]
                            if sim_satir["hedef"] is not None
                            else "—"
                        ),
                        "Fark": (
                            "%+.2f" % sim_satir["fark"]
                            if sim_satir["fark"] is not None
                            else "—"
                        ),
                        "Durum": SIM_DURUM_ETIKETLERI.get(
                            sim_satir["durum"], sim_satir["durum"]
                        ),
                    }
                    for sim_satir in sim_hedef_satirlar
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    sim_gereken_testler = ranking_engine.gereken_testler(sim_puan_turu)
    sim_eksik_hedefler = [
        sim_test for sim_test in sim_gereken_testler if sim_test not in sim_hedefler
    ]
    if sim_hedef_var:
        if sim_eksik_hedefler:
            st.caption(
                "Hedef puan karşılığı için eksik hedef netler: %s"
                % ", ".join(sim_eksik_hedefler)
            )
        else:
            sim_hedef_puan = ranking_engine.puan_hesapla(
                sim_hedefler,
                sim_puan_turu,
                sim_yil,
                sim_diploma,
                sim_obp_dahil,
            )
            if sim_hedef_puan["durum"] == ranking_engine.DURUM_OK:
                sim_h1, sim_h2 = st.columns(2)
                with sim_h1:
                    st.metric(
                        "Hedef netlerin model puanı",
                        "%.2f" % sim_hedef_puan["puan"],
                    )
                with sim_h2:
                    if sim_puan is not None:
                        st.metric(
                            "Mevcuttan fark",
                            "%+.2f puan"
                            % (sim_hedef_puan["puan"] - sim_puan["puan"]),
                        )
                    else:
                        st.metric("Mevcuttan fark", "—")

    with st.form("sim_hedef_formu"):
        st.markdown("**Hedef netleri kaydet / güncelle**")
        st.caption(
            "Sıfır girilen testler hedef olarak saklanmaz. Hedef netler yalnızca"
            " karşılaştırma ve hedef puan hesabı için kullanılır."
        )
        sim_hedef_girdiler = {}
        sim_hedef_kolonlari = st.columns(2)
        for sim_indeks, sim_test in enumerate(sim_gereken_testler):
            sim_soru_sayisi = osym_verisi.test_soru_sayisi(sim_test) or 40
            sim_hedef_anahtari = "sim_hedef_%s_%s" % (
                sanitize_key(sim_puan_turu),
                sanitize_key(sim_test),
            )
            if sim_hedef_anahtari not in st.session_state:
                st.session_state[sim_hedef_anahtari] = float(
                    sim_hedefler.get(sim_test, 0.0)
                )
            with sim_hedef_kolonlari[sim_indeks % 2]:
                sim_hedef_girdiler[sim_test] = st.number_input(
                    "%s hedefi (0–%d)" % (sim_test, sim_soru_sayisi),
                    min_value=0.0,
                    max_value=float(sim_soru_sayisi),
                    step=0.25,
                    key=sim_hedef_anahtari,
                )
        if st.form_submit_button("💾 Hedef netleri kaydet"):
            sim_kayit_netler = {
                test: net
                for test, net in sim_hedef_girdiler.items()
                if net and net > 0
            }
            try:
                if sim_kayit_netler:
                    ranking_engine.hedef_netleri_kaydet(
                        ctx.user["id"], sim_puan_turu, sim_kayit_netler
                    )
                else:
                    ranking_engine.hedef_netleri_sil(
                        ctx.user["id"], sim_puan_turu
                    )
            except ranking_engine.SimulatorHatasi as sim_hedef_hata:
                st.error("Hedef netler kaydedilemedi: %s" % sim_hedef_hata)
            else:
                log_islem(
                    ctx.user["id"],
                    "SAVE_TARGET_NETS",
                    "%s: %d test" % (sim_puan_turu, len(sim_kayit_netler)),
                )
                set_flash_message(
                    "success",
                    "%s için hedef netler kaydedildi (%d test)."
                    % (sim_puan_turu, len(sim_kayit_netler)),
                )
                st.rerun()

    if sim_hedefler:
        if st.button("🗑️ Hedef netleri temizle", key="sim_hedef_temizle"):
            ranking_engine.hedef_netleri_sil(ctx.user["id"], sim_puan_turu)
            for sim_test in sim_gereken_testler:
                st.session_state.pop(
                    "sim_hedef_%s_%s"
                    % (sanitize_key(sim_puan_turu), sanitize_key(sim_test)),
                    None,
                )
            log_islem(
                ctx.user["id"], "CLEAR_TARGET_NETS", str(sim_puan_turu)
            )
            set_flash_message(
                "info", "%s hedef netleri temizlendi." % sim_puan_turu
            )
            st.rerun()

    st.divider()
    st.subheader("📅 Yıllara göre karşılaştırma")
    st.caption(
        "Aynı netlerle her yılın kural setine göre model puanı hesaplanır."
        " Sıralama yalnızca o yıl için doğrulanmış referans verisi varsa görünür."
    )
    sim_yil_satirlari = ranking_engine.yil_karsilastirmasi(
        sim_netler,
        sim_puan_turu,
        sim_diploma,
        sim_obp_dahil,
        yillar=list(reversed(osym_verisi.desteklenen_yillar())),
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Yıl": sim_satir["yil"],
                    "Model puanı": (
                        "%.2f" % sim_satir["puan"]
                        if sim_satir["puan"] is not None
                        else "—"
                    ),
                    "Tahmini sıra": (
                        sim_sira_metni(sim_satir["sira"])
                        if sim_satir["sira"] is not None
                        else "veri yok"
                    ),
                    "Senaryo aralığı": (
                        "%s – %s"
                        % (
                            sim_sira_metni(sim_satir["aralik"][0]),
                            sim_sira_metni(sim_satir["aralik"][1]),
                        )
                        if sim_satir["aralik"]
                        else "—"
                    ),
                }
                for sim_satir in sim_yil_satirlari
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Bu ekran bir ÖSYM sonucu açıklama sistemi değildir. Gerçek sıralama;"
        " sınavın zorluğu, adayların performansı ve ilgili yılın koşullarına"
        " göre değişebilir. Sıralama tahmini yalnızca girilen referans"
        " verisiyle sınırlıdır."
    )

    st.caption(
        "Referans verisi (hangi yıl ve puan türü için puan–sıra noktaları"
        " bulunduğu) yönetici panelinden yönetilir: **👑 Yönetim → 4. YKS"
        " Referans Verisi**."
    )
