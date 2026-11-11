"""Sekme 5 - Konu Uyarıları & Alarmlar.

Alarm çözümleme (uyarıyı 'Çözüldü' işaretleme) buradadır; alarm
hesaplaması `services.alarm_service` içindedir."""


import streamlit as st

from config.database import get_connection
from config.settings import get_tr_now
from views.shared import set_flash_message


def resolve_alarm(id_list):
    if not id_list:
        return
    with get_connection() as c:
        cur = c.cursor()
        placeholders = ",".join("?" * len(id_list))
        cur.execute(
            "UPDATE deneme_konu_yanlislari SET durum = 'Çözüldü' WHERE id IN"
            f" ({placeholders})",
            id_list,
        )
        c.commit()


def render(ctx):
    st.header("🚨 Konu Uyarıları ve Risk Listesi")
    col_al1, col_al2 = st.columns(2)
    with col_al1:
        st.subheader("⚠️ Öncelikli Yanlış Uyarıları")
        if (
            not ctx.alarmlar["siyah"]
            and not ctx.alarmlar["kirmizi"]
            and not ctx.alarmlar["mor"]
        ):
            st.success("Tebrikler! Öncelikli bir uyarınız bulunmuyor.")
        else:
            for idx, a in enumerate(ctx.alarmlar["siyah"]):
                st.markdown(
                    f'<div class="alarm-card-black"><b>⬛ [KRİTİK İVMELENEN YANLIŞ]</b> {a["ders"]} ➔ {a["konu"]}<br>'
                    f'• {a["detay"]}<br><br>'
                    f'<b>👉 {a["aksiyon"]}</b></div>',
                    unsafe_allow_html=True,
                )
                col_btn_a, col_btn_b = st.columns(2)
                with col_btn_a:
                    if st.button("🛒 Özel Ders İste", key=f"btn_cta_siyah_{idx}"):
                        simdi_str = get_tr_now().strftime("%Y-%m-%d %H:%M:%S")
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO pazaryeri_talepler (ogrenci_id, ders, konu, alarm_turu, talep_tarihi) VALUES (?, ?, ?, 'Siyah Alarm', ?)",
                                (ctx.user["id"], a["ders"], a["konu"], simdi_str),
                            )
                            conn.commit()
                        set_flash_message("success", "Özel ders talebiniz koçunuza iletildi!")
                        st.rerun()
                with col_btn_b:
                    if st.button("✅ Eksik Kapatıldı", key=f"siyah_clr_{idx}"):
                        resolve_alarm(a["id_list"])
                        set_flash_message("success", "Uyarı kaldırıldı.")
                        st.rerun()

            for idx, a in enumerate(ctx.alarmlar["kirmizi"]):
                st.markdown(
                    f'<div class="alarm-card-danger"><b>🔴 [BİLİNEN KONUDA YANLIŞ]</b> {a["ders"]} ➔ {a["konu"]}<br>'
                    f'• {a["detay"]}<br><br>'
                    f'<b>👉 {a["aksiyon"]}</b></div>',
                    unsafe_allow_html=True,
                )
                col_btn_a, col_btn_b = st.columns(2)
                with col_btn_a:
                    if st.button("🛒 Özel Ders İste", key=f"btn_cta_kirmizi_{idx}"):
                        simdi_str = get_tr_now().strftime("%Y-%m-%d %H:%M:%S")
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO pazaryeri_talepler (ogrenci_id, ders, konu, alarm_turu, talep_tarihi) VALUES (?, ?, ?, 'Kırmızı Alarm', ?)",
                                (ctx.user["id"], a["ders"], a["konu"], simdi_str),
                            )
                            conn.commit()
                        set_flash_message("success", "Özel ders talebiniz koçunuza iletildi!")
                        st.rerun()
                with col_btn_b:
                    if st.button("✅ Tekrar Edildi", key=f"kirmizi_clr_{idx}"):
                        resolve_alarm(a["id_list"])
                        set_flash_message("success", "Uyarı kaldırıldı.")
                        st.rerun()

            for idx, a in enumerate(ctx.alarmlar["mor"]):
                st.markdown(
                    f'<div class="alarm-card-purple"><b>🟣 [3 DENEMEDİR TEKRAR EDEN HATA]</b> {a["ders"]} ➔ {a["konu"]}<br>'
                    f'• {a["detay"]}<br><br>'
                    f'<b>👉 {a["aksiyon"]}</b></div>',
                    unsafe_allow_html=True,
                )
                col_btn_a, col_btn_b = st.columns(2)
                with col_btn_a:
                    if st.button("🛒 Özel Ders İste", key=f"btn_cta_mor_{idx}"):
                        simdi_str = get_tr_now().strftime("%Y-%m-%d %H:%M:%S")
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO pazaryeri_talepler (ogrenci_id, ders, konu, alarm_turu, talep_tarihi) VALUES (?, ?, ?, 'Mor Alarm', ?)",
                                (ctx.user["id"], a["ders"], a["konu"], simdi_str),
                            )
                            conn.commit()
                        set_flash_message("success", "Özel ders talebiniz koçunuza iletildi!")
                        st.rerun()
                with col_btn_b:
                    if st.button("✅ Çözüldü", key=f"mor_clr_{idx}"):
                        resolve_alarm(a["id_list"])
                        set_flash_message("success", "Uyarı kaldırıldı.")
                        st.rerun()

    with col_al2:
        st.subheader("📙 Temel Eksik ve Takvim Uyarıları")
        if not ctx.alarmlar["turuncu"] and not ctx.alarmlar["mavi"]:
            st.success("Müfredat akışınızda bir aksama bulunmuyor.")
        else:
            for a in ctx.alarmlar["turuncu"]:
                st.markdown(
                    '<div class="alarm-card-warning"><h4>📙 [ÖN KOŞUL KİLİDİ]'
                    f" {a['konu']}</h4><p><b>Detay:</b>"
                    f" {a['detay']}</p><p>👉 <b>{a['aksiyon']}</b></p></div>",
                    unsafe_allow_html=True,
                )
            for a in ctx.alarmlar["mavi"]:
                st.markdown(
                    '<div class="alarm-card-info"><h4>🔵 [TAKVİM GECİKMESİ]'
                    f" {a['konu']}</h4><p><b>Detay:</b>"
                    f" {a['detay']}</p><p>👉 <b>{a['aksiyon']}</b></p></div>",
                    unsafe_allow_html=True,
                )
