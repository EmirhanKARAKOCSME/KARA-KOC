"""Sekme 7 - Özel Ders & Talepler."""


import pandas as pd
import streamlit as st

from config.database import get_connection, log_islem
from config.settings import get_tr_now
from views.shared import set_flash_message


def render(ctx):
    st.header("🤝 Özel Ders Talepleri & Çalışma Raporları")
    
    rep_tab1, rep_tab2 = st.tabs(
        [
            "🛒 Özel Ders Taleplerim",
            "📊 Detaylı Performans & İletişim Logları",
        ],
        key="kt_rapor_tabs",
        on_change="rerun",
    )
    
    with rep_tab1:
        st.subheader("📌 Mevcut Özel Ders Talepleri")
        with get_connection() as conn:
            df_taleplerim = pd.read_sql_query(
                "SELECT id, ders, konu, alarm_turu, talep_tarihi, durum FROM pazaryeri_talepler WHERE ogrenci_id = ? ORDER BY id DESC",
                conn,
                params=(ctx.user["id"],),
            )
        
        if not df_taleplerim.empty:
            st.dataframe(df_taleplerim, width="stretch")
        else:
            st.info("Henüz oluşturulmuş bir özel ders talebiniz bulunmuyor.")
            
        st.markdown("---")
        st.subheader("➕ Yeni Özel Ders / Birebir Seans Talebi Oluştur")
        with st.form("yeni_ozel_ders_talep_formu"):
            talep_ders = st.selectbox("Ders Seçiniz:", list(ctx.mufredat.keys()))
            
            secili_ders_dict = ctx.mufredat.get(talep_ders, {})
            konu_listesi = []
            if isinstance(secili_ders_dict, dict):
                for k, v in secili_ders_dict.items():
                    if isinstance(v, list):
                        konu_listesi.extend(v)
                    else:
                        konu_listesi.append(k)
            if not konu_listesi:
                konu_listesi = ["Genel Soru Çözümü / Birebir Koçluk"]
                
            talep_konu = st.selectbox("Destek Almak İstediğiniz Konu:", konu_listesi)
            talep_notu = st.text_area("Koçunuza İletmek İstediğiniz Not (Opsiyonel):", placeholder="Örn: Bu konuda çıkmış soruları birlikte çözmek istiyorum.")
            
            if st.form_submit_button("📩 Özel Ders Talebini Gönder", type="primary"):
                simdi_str = get_tr_now().strftime("%Y-%m-%d %H:%M:%S")
                konu_full = f"{talep_konu} ({talep_notu})" if talep_notu.strip() else talep_konu
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO pazaryeri_talepler (ogrenci_id, ders, konu, alarm_turu, talep_tarihi, durum) VALUES (?, ?, ?, 'Birebir Talep', ?, 'Talep Alındı')",
                        (ctx.user["id"], talep_ders, konu_full, simdi_str),
                    )
                    conn.commit()
                log_islem(ctx.user["id"], "PRIVATE_LESSON_REQUEST", f"{talep_ders} - {talep_konu}")
                set_flash_message("success", "🎉 Özel ders talebiniz koçunuza iletildi!")
                st.rerun()

    with rep_tab2:
        st.subheader("📜 Sistem İletişim ve Aktivite Logları")
        with get_connection() as conn:
            df_loglar = pd.read_sql_query(
                "SELECT islem, detay, tarih FROM sistem_loglari WHERE ogrenci_id = ? ORDER BY id DESC LIMIT 50",
                conn,
                params=(ctx.user["id"],),
            )
        if not df_loglar.empty:
            st.dataframe(df_loglar, width="stretch")
        else:
            st.info("Henüz sistem aktivite kaydı oluşmadı.")
