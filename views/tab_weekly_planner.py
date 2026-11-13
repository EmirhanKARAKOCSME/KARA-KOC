"""Sekme 6 - Haftalık Çalışma Programı."""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from config.database import get_connection, log_islem
from config.settings import GUN_ADLARI_LISTE, get_tr_now
from data.pedagogy import get_konu_pedagoji_turu
from data.prerequisites import ON_KOSULLAR
from data.weights_and_times import SORU_AGIRLIKLARI
from services import planner
from services.program_motoru import (
    haftalik_program_gorevleri_uret,
    hesapla_hiz_katsayisi,
    hiz_gecmisi_kaydet,
    planlama_baglami_olustur,
)
from services import programs as program_service
from services import task_steps
from services.topic_progress import (
    gorev_alt_konu_isle,
    gorev_chk_durum_senkron,
    makro_unite_ilerleme_durumu,
)
from views.shared import (
    _gorev_adimlari_senkron,
    _onceki_programlar_bolumu,
    set_flash_message,
)


def render(ctx):
    st.header("📅 Haftalık Çalışma Programı Motoru")
    # v2.5: iki sütunlu dar düzen yerine tam genişlik. Sağdaki simülatör
    # bilgilendirme kartı kaldırıldı (simülatör kendi sekmesinde).
    col_p1 = st.container()

    with col_p1:
        st.subheader("⚙️ Program Oluşturma Ayarları")
        # FAZ 5C: haftanın her günü için ayrı müsaitlik (0 = dinlenme günü).
        kayitli_musaitlik = planner.musaitlik_yukle(ctx.user["id"])
        musaitlik_saat = {}
        with st.expander("🗓️ Haftalık müsaitlik (saat)", expanded=True):
            st.caption(
                "Her gün için ayırabileceğin süreyi seç. **0 saat = dinlenme"
                " günü.** Bu tercihler kaydedilir ve yeni programlarda tekrar"
                " sorulmaz."
            )
            gun_kolonlari = st.columns(4)
            for gun_no, gun_adi in enumerate(GUN_ADLARI_LISTE, start=1):
                with gun_kolonlari[(gun_no - 1) % 4]:
                    musaitlik_saat[gun_no] = st.number_input(
                        gun_adi,
                        min_value=0,
                        max_value=12,
                        value=int(round(kayitli_musaitlik.get(gun_no, 360) / 60)),
                        step=1,
                        key=f"musaitlik_saat_{gun_no}",
                        help="%s günü kaç saat çalışabilirsin?" % gun_adi,
                    )
            if st.button("💾 Müsaitliği kaydet", key="musaitlik_kaydet_btn"):
                try:
                    planner.musaitlik_kaydet(
                        ctx.user["id"],
                        {gun: int(saat) * 60 for gun, saat in musaitlik_saat.items()},
                    )
                except planner.PlanHatasi as hata:
                    st.error("⚠️ %s" % hata)
                else:
                    set_flash_message("success", "🗓️ Haftalık müsaitlik kaydedildi.")
                    st.rerun()

        gunluk_saat = int(round(sum(musaitlik_saat.values()) / 7.0))
        gunluk_saat = max(1, min(12, gunluk_saat or 6))
        st.caption(
            "Haftalık ortalama: **%d saat/gün** · Toplam: **%d saat**"
            % (gunluk_saat, sum(musaitlik_saat.values()))
        )

        toplam_gunluk_dakika = gunluk_saat * 60
        maks_soru_kapasitesi = int(toplam_gunluk_dakika / 1.5)

        if gunluk_saat <= 4:
            ana_gorev_blok_sayisi = 2
        elif 5 <= gunluk_saat <= 7:
            ana_gorev_blok_sayisi = 4
        else:
            ana_gorev_blok_sayisi = 6

        günlük_paragraf_hedef = min(30, 10 + (gunluk_saat * 2))
        kalan_soru_kapasitesi = max(
            20, maks_soru_kapasitesi - günlük_paragraf_hedef
        )
        blok_basi_soru_bütcesi = int(
            kalan_soru_kapasitesi / ana_gorev_blok_sayisi
        )

        st.info(
            f"📊 Günlük **{gunluk_saat} Saat** ({toplam_gunluk_dakika} dk) çalışma planı ➔"
            f" **{ana_gorev_blok_sayisi} Ana Çalışma Bloğu** ve ön koşul kilitli sıralama ile oluşturulacaktır."
        )

        # v2.2 (FAZ 4): simülatör/test için opsiyonel referans tarihi. Verilirse
        # motor `1 Mayıs` çift motor geçişini bu tarihe göre uygular.
        with st.expander("🗓️ Referans tarihi (simülasyon)", expanded=False):
            sim_kullan = st.checkbox(
                "Simülasyon tarihi kullan (1 Mayıs çift motor testi)",
                key="sim_tarih_kullan",
            )
            sim_tarih = st.date_input(
                "Referans tarihi",
                value=get_tr_now().date(),
                key="sim_referans_tarihi",
                disabled=not sim_kullan,
            )
        referans_tarihi = sim_tarih if sim_kullan else None

        if st.button("🚀 Akıllı Haftalık Programımı Oluştur", type="primary"):
            hiz_gecmisi_kaydet(ctx.user["id"])
            with get_connection() as conn:
                # FAZ 5A: eski program/görevler SİLİNMEZ. Yeni program ayrı bir
                # sürüm olarak eklenir; eskisi arşivlenir (tek transaction).
                gunler = [
                    "Pazartesi",
                    "Salı",
                    "Çarşamba",
                    "Perşembe",
                    "Cuma",
                    "Cumartesi",
                    "Pazar",
                ]

                backlog_pekistirme = []
                backlog_ezber = []

                # 1. Yanlışlar ve Alarmlardan Gelen Konular
                for cat_name, val_list in ctx.alarmlar.items():
                    alarm_skor = (
                        100.0
                        if cat_name == "siyah"
                        else (
                            80.0
                            if cat_name == "kirmizi"
                            else (10.0 if cat_name == "mor" else 40.0)
                        )
                    )
                    for item in val_list:
                        # "Temel Eksik" uyarılarında konu metni birleşik
                        # etikettir ("Konu - Eksikler: A, B"); puanlama ve
                        # pedagoji için HEDEF KONU kullanılır.
                        temel_konu = item.get("hedef_konu") or item["konu"]
                        kredi = SORU_AGIRLIKLARI.get(temel_konu, 10.0)
                        p_score = (kredi * 0.8) + (alarm_skor * 0.2)
                        p_tip = get_konu_pedagoji_turu(
                            item["ders"], temel_konu
                        )
                        obj = {
                            "p_score": p_score,
                            "ders": item["ders"],
                            "makro": "Deneme Tekrarı",
                            "mikro": item["konu"],
                            "neden": item.get("neden", "Deneme Eksiği"),
                            "pedagoji": p_tip,
                        }
                        if p_tip == "Pekiştirme":
                            backlog_pekistirme.append(obj)
                        else:
                            backlog_ezber.append(obj)

                # 2. Müfredatta Eksik Olan Konular
                df_bilinen_tab4 = pd.read_sql_query(
                    "SELECT ders, mikro_konu FROM konu_durumlari_detay WHERE"
                    " ogrenci_id = ? AND durum = 'Biliyorum'",
                    conn,
                    params=(ctx.user["id"],),
                )
                bilinen_mikro_set = set(df_bilinen_tab4["mikro_konu"].tolist())

                for d_ad, m_dict in ctx.mufredat.items():
                    if isinstance(m_dict, dict):
                        for mak_ad, mik_l in m_dict.items():
                            if isinstance(mik_l, list):
                                for mik_ad in mik_l:
                                    if mik_ad not in bilinen_mikro_set:
                                        kredi = SORU_AGIRLIKLARI.get(
                                            mak_ad, 8.0
                                        )
                                        p_score = kredi
                                        p_tip = get_konu_pedagoji_turu(
                                            d_ad, mik_ad
                                        )
                                        obj = {
                                            "p_score": p_score,
                                            "ders": d_ad,
                                            "makro": mak_ad,
                                            "mikro": mik_ad,
                                            "neden": "Sıradaki Konu",
                                            "pedagoji": p_tip,
                                        }
                                        if p_tip == "Pekiştirme":
                                            backlog_pekistirme.append(obj)
                                        else:
                                            backlog_ezber.append(obj)

                # ÖN KOŞUL KİLİDİ (DEPENDENCY TREE) FİLTRESİ
                def on_kosul_uygun_mu(item):
                    mik_konu = item["mikro"]
                    if mik_konu in ON_KOSULLAR:
                        gerekenler = ON_KOSULLAR[mik_konu]["on_kosul"]
                        for g in gerekenler:
                            if g not in bilinen_mikro_set:
                                return False
                    return True

                filtered_pekistirme = [x for x in backlog_pekistirme if on_kosul_uygun_mu(x)]
                filtered_ezber = [x for x in backlog_ezber if on_kosul_uygun_mu(x)]

                filtered_pekistirme.sort(key=lambda x: x["p_score"], reverse=True)
                filtered_ezber.sort(key=lambda x: x["p_score"], reverse=True)

                gorevler, motor_adi, uyarilar = haftalik_program_gorevleri_uret(
                    ctx.user["id"],
                    ctx.mufredat,
                    ctx.alarmlar,
                    ana_gorev_blok_sayisi,
                    blok_basi_soru_bütcesi,
                    günlük_paragraf_hedef,
                    gunler,
                    filtered_pekistirme,
                    filtered_ezber,
                    plan_baglami=planlama_baglami_olustur(
                        ctx.user["id"],
                        ctx.mufredat,
                        ctx.alarmlar,
                        paragraf_soru=günlük_paragraf_hedef,
                        referans_tarihi=referans_tarihi,
                    ),
                    referans_tarihi=referans_tarihi,
                )

            # FAZ 5A: program TEK transaction'da yazılır ve hiçbir görev silinmez.
            # Motor hata verse bile eski program/görevler/oturumlar korunur.
            baslangic_tarih = get_tr_now().strftime("%Y-%m-%d")
            bitis_tarih = (get_tr_now() + timedelta(days=6)).strftime("%Y-%m-%d")
            try:
                yeni_program = program_service.program_olustur(
                    ctx.user["id"],
                    baslangic_tarih,
                    bitis_tarih,
                    gorevler,
                    gunluk_hedef_dakika=toplam_gunluk_dakika,
                    program_notu=motor_adi,
                )
            except program_service.ProgramHatasi as program_hata:
                set_flash_message(
                    "error",
                    "Program oluşturulamadı: %s Mevcut programınız, eski"
                    " görevleriniz ve çalışma kayıtlarınız korunuyor."
                    % program_hata,
                )
                st.rerun()
            else:
                plan_soru = sum(
                    int(g.get("hedef_soru") or 0)
                    for g in gorevler
                    if g.get("pedagoji_turu") != "Tekrar"
                )
                try:
                    with get_connection() as kayit_conn:
                        kayit_conn.execute(
                            "INSERT INTO ogrenci_hiz_gecmisi (ogrenci_id, tarih,"
                            " planlanan_gorev, planlanan_soru, kullanilan_katsayi)"
                            " VALUES (?, ?, ?, ?, ?)",
                            (
                                ctx.user["id"],
                                baslangic_tarih,
                                len(gorevler),
                                plan_soru,
                                hesapla_hiz_katsayisi(ctx.user["id"]),
                            ),
                        )
                        kayit_conn.commit()
                except Exception:
                    pass
                log_islem(
                    ctx.user["id"],
                    "CREATE_PROGRAM",
                    "Haftalık program oluşturuldu (#%s, %s, %s görev)."
                    % (yeni_program["id"], motor_adi, len(gorevler)),
                )
                uyari_metni = (" " + " ".join(uyarilar)) if uyarilar else ""
                set_flash_message(
                    "success",
                    "🎉 Haftalık programınız oluşturuldu (#%s). Toplam %s görev"
                    " planlandı.%s" % (yeni_program["id"], len(gorevler), uyari_metni),
                )
                if uyarilar:
                    set_flash_message("warning", uyari_metni.strip())
                st.rerun()

    st.markdown("---")
    _onceki_programlar_bolumu(ctx.user["id"])
    st.subheader("📋 7 Günlük Genel Çalışma Çizelgesi")
    # FAZ 5A: çizelge yalnızca AKTİF programın görevlerini gösterir (aktif
    # program yoksa program bağlantısı olmayan eski kayıtlar gösterilir).
    df_program_full = pd.DataFrame(
        program_service.gorunur_gorevler(ctx.user["id"]),
        columns=[
            "id",
            "gun",
            "ders",
            "makro_konu",
            "mikro_konu",
            "gorev_tanimi",
            "hedef_soru",
            "tahmini_sure_dk",
            "pedagoji_turu",
            "durum",
            "tarih",
            "program_id",
            # v2.2 (FAZ 2-3): görev tipi + ayrıştırılmış anlatım/soru dakikaları.
            "gorev_tipi",
            "konu_anlatim_dk",
            "soru_cozum_dk",
        ],
    )

    if not df_program_full.empty:
        # FAZ 5B: tamamlanma alt adımlardan türetilir (soru adımları gerçek
        # çalışma kayıtlarından gelir).
        hafta_adimlari = {
            int(satir["id"]): _gorev_adimlari_senkron(int(satir["id"]), satir["durum"])
            for _, satir in df_program_full.iterrows()
        }
        biten_gorev = 0
        for _, satir in df_program_full.iterrows():
            adimlar = hafta_adimlari.get(int(satir["id"])) or []
            bitti = all(a["tamam"] for a in adimlar) if adimlar else bool(satir["durum"])
            biten_gorev += 1 if bitti else 0
        toplam_gorev = len(df_program_full)
        p_yuzde = (
            int((biten_gorev / toplam_gorev) * 100) if toplam_gorev > 0 else 0
        )

        st.write(
            f"**Tamamlanan Görev Oranı:** %{p_yuzde} ({biten_gorev}/{toplam_gorev}"
            " Görev Bitti)"
        )
        st.progress(p_yuzde / 100.0)

        # v2.3 (FAZ 1.4): gün sekmeleri SABİT Pzt-Paz değil, programdaki GERÇEK
        # tarih sırasıdır; "Gün 1: Perşembe (12 Kasım)" biçiminde etiketlenir.
        gun_adlari_tr = {
            "Monday": "Pazartesi", "Tuesday": "Salı", "Wednesday": "Çarşamba",
            "Thursday": "Perşembe", "Friday": "Cuma", "Saturday": "Cumartesi",
            "Sunday": "Pazar",
        }
        ay_adlari_tr = {
            1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs",
            6: "Haziran", 7: "Temmuz", 8: "Ağustos", 9: "Eylül",
            10: "Ekim", 11: "Kasım", 12: "Aralık",
        }
        _tarihler = sorted(
            {str(t)[:10] for t in df_program_full["tarih"].tolist()
             if pd.notna(t)}
        )
        gun_etiketleri = []
        for _i, _t in enumerate(_tarihler, 1):
            try:
                _dt = datetime.strptime(_t, "%Y-%m-%d")
                _ad = gun_adlari_tr.get(_dt.strftime("%A"), _dt.strftime("%A"))
                _etiket = "Gün %d: %s (%d %s)" % (
                    _i, _ad, _dt.day, ay_adlari_tr.get(_dt.month, "")
                )
            except (ValueError, TypeError):
                _etiket = "Gün %d" % _i
            gun_etiketleri.append((_t, _etiket))
        gun_tablari = st.tabs(
            [e[1] for e in gun_etiketleri],
            key="kt_program_gun_tabs",
            on_change="rerun",
        )

        for g_idx, (_tarih, _etiket) in enumerate(gun_etiketleri):
            with gun_tablari[g_idx]:
                df_gunluk = df_program_full[
                    df_program_full["tarih"].astype(str).str[:10] == _tarih
                ]
                if not df_gunluk.empty:
                    for _, row in df_gunluk.iterrows():
                        p_turu = row["pedagoji_turu"]

                        if p_turu == "Tekrar":
                            st.markdown(
                                '<div class="alarm-card-info">🔄 <b>[3 GÜNLÜK'
                                f" ARALIKLI TEKRAR GÖREVİ]</b> {row['ders']} -"
                                f" {row['mikro_konu']}<br>•"
                                f" {row['gorev_tanimi']}</div>",
                                unsafe_allow_html=True,
                            )
                        else:
                            _gtip = row.get("gorev_tipi")
                            _kdk = row.get("konu_anlatim_dk")
                            _karma = isinstance(_gtip, str) and _gtip == "karma_tarama"
                            st.markdown(
                                ('<div class="sim-card">🎯 <b>'
                                 if _karma else
                                 '<div class="sim-card">📌 <b>')
                                + f" {row['ders']} - {row['mikro_konu']}</b><br>•"
                                f" {row['gorev_tanimi']}</div>",
                                unsafe_allow_html=True,
                            )
                            # v2.2 (FAZ 3): %0 konu -> Konu Anlatımı rozeti + ilk adım.
                            if (
                                isinstance(_gtip, str)
                                and _gtip == "konu_anlatimi"
                            ) or (pd.notna(_kdk) and int(_kdk or 0) > 0):
                                st.markdown(
                                    '<div class="alarm-card-info">📖 <b>Konu'
                                    " Anlatımı + İlk Kavrama</b> — ayrılan anlatım:"
                                    " %d dk</div>" % int(_kdk or 0),
                                    unsafe_allow_html=True,
                                )
                                _kt_adimlar = hafta_adimlari.get(int(row["id"])) or []
                                if _kt_adimlar:
                                    st.caption(
                                        "1. " + str(_kt_adimlar[0]["baslik"])
                                    )

                        col_g1, col_g2 = st.columns([3, 1])
                        with col_g1:
                            st.write(
                                f"📌 **{row['makro_konu']}** ➔"
                                f" *{row['mikro_konu']}*"
                            )
                            sure_dk = row.get("tahmini_sure_dk")
                            if pd.notna(sure_dk) and int(sure_dk or 0) > 0:
                                st.caption(
                                    "⏱️ " + task_steps.sure_metni(int(sure_dk))
                                )
                        with col_g2:
                            prog_adimlar = hafta_adimlari.get(int(row["id"])) or []
                            is_t = (
                                all(a["tamam"] for a in prog_adimlar)
                                if prog_adimlar
                                else bool(row["durum"])
                            )
                            if prog_adimlar:
                                # Soru adımları gerçek oturumlardan geldiği için
                                # bu görevler elle işaretlenmez.
                                ilerleme = task_steps.gorev_ilerleme(int(row["id"]))
                                st.caption(
                                    "✅ Tamamlandı"
                                    if is_t
                                    else "⏳ %d/%d adım"
                                    % (
                                        ilerleme["tamamlanan_adim"],
                                        ilerleme["adim_sayisi"],
                                    )
                                )
                            else:
                                prog_anahtar = f"prog_chk_{row['id']}"
                                # FAZ 4: iki sekme arasındaki checkbox değeri
                                # çakışmasını (sonsuz rerun) önler.
                                gorev_chk_durum_senkron(prog_anahtar, is_t)
                                chk_g = st.checkbox(
                                    "Tamamlandı",
                                    key=prog_anahtar,
                                )
                                if chk_g != is_t:
                                    # v2.3 (FAZ 1.4): genel ders yüzdesi yerine
                                    # görevin bağlı olduğu MAKRO ÜNİTENİN ilerleme
                                    # yüzdesi "onceki ➔ sonraki" olarak bildirilir.
                                    _unite_once = None
                                    if chk_g:
                                        try:
                                            _unite_once = makro_unite_ilerleme_durumu(
                                                ctx.user["id"], row["ders"],
                                                row.get("makro_konu"), ctx.mufredat,
                                            )
                                        except Exception:  # noqa: BLE001
                                            _unite_once = None
                                    with get_connection() as conn:
                                        # FAZ 4: planlanan soru ilerlemeye eklenmez.
                                        gorev_alt_konu_isle(row["id"], chk_g)
                                        cursor = conn.cursor()
                                        cursor.execute(
                                            "UPDATE calisma_programi_gorevler SET"
                                            " durum = ? WHERE id = ?",
                                            (1 if chk_g else 0, row["id"]),
                                        )
                                        conn.commit()
                                    if _unite_once is not None:
                                        try:
                                            _unite_sonra = makro_unite_ilerleme_durumu(
                                                ctx.user["id"], row["ders"],
                                                row.get("makro_konu"), ctx.mufredat,
                                            )
                                        except Exception:  # noqa: BLE001
                                            _unite_sonra = _unite_once
                                        set_flash_message(
                                            "info",
                                            "Ünite İlerlemesi: %%%d ➔ %%%d (%s)"
                                            % (
                                                int(_unite_once),
                                                int(_unite_sonra),
                                                str(row.get("makro_konu") or ""),
                                            ),
                                        )
                                    st.rerun()
                        st.markdown("---")
                else:
                    st.info("Bu gün için planlanmış bir çalışma görevi bulunmuyor.")
