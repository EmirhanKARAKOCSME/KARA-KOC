"""Sekme 1 - Bugünün Görevleri."""


import pandas as pd
import streamlit as st

from config.database import get_connection, log_islem
from config.settings import get_tr_now
from services import programs as program_service
from services import study_sessions
from services import task_steps
from services.topic_progress import (
    gorev_alt_konu_isle,
    gorev_chk_durum_senkron,
)
from views.shared import (
    _calisma_basla_butonu,
    _gercek_calisma_ozeti,
    _gorev_adim_listesi,
    _gorev_adimlari_senkron,
    _gorev_gercek_soru_ozeti,
    _oturum_paneli_veya_form,
)


def render(ctx):
    st.header("🎯 Bugünün Görevleri")
    st.markdown(
        "Gününüzü dağıtmadan tam odakla bitirmeniz gereken **3-4 net çalışma görevi** aşağıdadır."
    )

    bugun_dt = get_tr_now()
    bugun_str = bugun_dt.strftime("%Y-%m-%d")
    gun_adlari_tr = {
        "Monday": "Pazartesi",
        "Tuesday": "Salı",
        "Wednesday": "Çarşamba",
        "Thursday": "Perşembe",
        "Friday": "Cuma",
        "Saturday": "Cumartesi",
        "Sunday": "Pazar",
    }
    bugun_gun_adi = gun_adlari_tr.get(bugun_dt.strftime("%A"), "Pazartesi")

    # FAZ 5A: günün görevleri TAM TARİH + aktif program + öğrenci üzerinden
    # filtrelenir. Eski `(tarih = ? OR gun = ?)` birleşimi kaldırıldı; böylece
    # geçen haftaların aynı gün adına ait görevleri bugüne sızmaz. Program
    # bağlantısı olmayan eski kayıtlar yalnızca aktif program yokken gösterilir.
    BUGUN_GOREV_SUTUNLARI = [
        "id",
        "ders",
        "makro_konu",
        "mikro_konu",
        "alt_konu",
        "gorev_tanimi",
        "hedef_soru",
        "tahmini_sure_dk",
        "pedagoji_turu",
        "durum",
        "program_id",
        "kaynak_gorev_id",
    ]
    df_bugun = pd.DataFrame(
        program_service.gun_gorevleri(ctx.user["id"], bugun_str),
        columns=BUGUN_GOREV_SUTUNLARI,
    )

    # FAZ 4: aktif çalışma oturumu veritabanından okunur; sayfa yenilense,
    # başka sekmeye geçilse veya uygulama kapansa da kaybolmaz.
    ogrenci_id = ctx.user["id"]
    aktif_oturum = study_sessions.aktif_oturum_getir(ogrenci_id)
    gosterilen_gorevler = set()

    st.markdown("#### ⏱️ Gerçek Çalışma Özeti")
    _gercek_calisma_ozeti(ogrenci_id, aktif_oturum)
    st.markdown("---")

    # FAZ 5B: adımlar bir kez okunur; görev tamamlanması adımlardan türetilir.
    adim_onbellek = {
        int(satir["id"]): _gorev_adimlari_senkron(int(satir["id"]), satir["durum"])
        for _, satir in df_bugun.iterrows()
    }

    if not df_bugun.empty:
        biten_cnt = 0
        for _, satir in df_bugun.iterrows():
            adimlar = adim_onbellek.get(int(satir["id"])) or []
            bitti = all(a["tamam"] for a in adimlar) if adimlar else bool(satir["durum"])
            biten_cnt += 1 if bitti else 0
        toplam_cnt = len(df_bugun)
        yuzde_bugun = int((biten_cnt / toplam_cnt) * 100) if toplam_cnt > 0 else 0

        col_t1, col_t2 = st.columns([3, 1])
        with col_t1:
            st.subheader(f"📅 Bugüne Ait İlerleme (%{yuzde_bugun})")
            st.progress(yuzde_bugun / 100.0)
        with col_t2:
            st.metric("Tamamlanan Görev", f"{biten_cnt} / {toplam_cnt}")

        st.markdown("---")

        for _, g_row in df_bugun.iterrows():
            g_id = int(g_row["id"])
            ped = g_row["pedagoji_turu"]
            # FAZ 5B: alt adımları olan görevlerde tamamlanma adımlardan türetilir.
            adimlar = adim_onbellek.get(g_id) or []
            is_done = (
                all(a["tamam"] for a in adimlar) if adimlar else bool(g_row["durum"])
            )
            sure_dk = g_row.get("tahmini_sure_dk")
            try:
                sure_dk = int(sure_dk) if sure_dk == sure_dk else 0
            except (TypeError, ValueError):
                sure_dk = 0
            alt_konu = g_row.get("alt_konu")
            mikro_satiri = (
                f'<p style="margin:2px 0 6px 0; color:#475569;">'
                f"<b>Mikro konu:</b> {alt_konu}</p>"
                if isinstance(alt_konu, str) and alt_konu.strip()
                else ""
            )
            sure_etiketi = (
                f'<span style="background-color:#dcfce7; color:#166534;'
                f" padding:2px 8px; border-radius:6px; font-size:0.85rem;"
                f' font-weight:600;">⏱️ {task_steps.sure_metni(sure_dk)}</span> '
                if sure_dk > 0
                else ""
            )

            st.markdown(
                f'<div class="focus-task-card">'
                f'<h4>{"✅" if is_done else "📌"} {g_row["ders"]} — {g_row["mikro_konu"]}</h4>'
                f"{mikro_satiri}"
                f'<p style="font-size: 1.05rem; margin-bottom: 8px;">{g_row["gorev_tanimi"]}</p>'
                f"{sure_etiketi}"
                f'<span style="background-color:#e0e7ff; color:#3730a3; padding:2px 8px; border-radius:6px; font-size:0.85rem; font-weight:600;">{ped}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

            if adimlar:
                # FAZ 5B: mikro görev checklist'i (soru blokları salt okunur)
                _gorev_adim_listesi(adimlar)
            else:
                col_chk1, col_chk2 = st.columns([4, 1])
                with col_chk2:
                    chk_anahtar = f"focus_chk_{g_id}"
                    # FAZ 4: aynı görev haftalık program sekmesinde de
                    # işaretlenebildiği için oturum değeri veritabanıyla eşitlenir.
                    gorev_chk_durum_senkron(chk_anahtar, is_done)
                    chk_val = st.checkbox(
                        "Tamamladım",
                        key=chk_anahtar,
                    )
                    if chk_val != is_done:
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "UPDATE calisma_programi_gorevler SET durum = ?"
                                " WHERE id = ?",
                                (1 if chk_val else 0, g_id),
                            )
                            conn.commit()
                        log_islem(
                            ctx.user["id"],
                            "TASK_TOGGLE_FOCUS",
                            f"Gorev ID {g_id} -> {chk_val}",
                        )
                        # FAZ 4: checkbox yalnızca görev durumunu değiştirir.
                        # Soru ilerlemesi planlanan sorudan DEĞİL, gerçek çalışma
                        # oturumlarından hesaplanır (soru_ilerleme_isle kaldırıldı).
                        gorev_alt_konu_isle(g_id, chk_val)
                        st.rerun()

            # FAZ 4: görev kartının altında çalışma zamanlayıcısı
            gosterilen_gorevler.add(int(g_id))
            if aktif_oturum and int(aktif_oturum.get("gorev_id") or 0) == int(g_id):
                _oturum_paneli_veya_form(
                    aktif_oturum, int(g_row.get("hedef_soru") or 0)
                )
            else:
                _gorev_gercek_soru_ozeti(g_row, ogrenci_id)
                _calisma_basla_butonu(g_row, ogrenci_id)
                if aktif_oturum:
                    st.caption(
                        "⏳ Başka bir görevde çalışma sürüyor; önce onu"
                        " bitirin veya iptal edin."
                    )

        # Aktif oturum bugünün listesinde olmayan bir göreve aitse yine
        # görünür olsun (görev silinse bile çalışma kaybolmaz).
        if (
            aktif_oturum
            and int(aktif_oturum.get("gorev_id") or 0) not in gosterilen_gorevler
        ):
            st.markdown("---")
            st.markdown("#### ⏳ Devam eden çalışma")
            _oturum_paneli_veya_form(aktif_oturum)
    else:
        if aktif_oturum:
            st.markdown("#### ⏳ Devam eden çalışma")
            _oturum_paneli_veya_form(aktif_oturum)
            st.markdown("---")
        st.info("💡 Bugüne tanımlanmış henüz bir çalışma görevi bulunmuyor. **📅 Haftalık Çalışma Programı** sekmesinden akıllı programınızı tek tıkla oluşturabilirsiniz.")
