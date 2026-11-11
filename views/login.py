"""Giriş ekranı. Başarılı girişte `st.session_state.active_user` dolar."""

from datetime import datetime

import streamlit as st

from config.database import get_connection, log_islem
from config.settings import get_tr_now
from services.auth_service import update_user_streak, verify_password
from views.shared import set_flash_message


def render():
    st.title("🎯 KARAKOÇ YKS Akıllı Koçluk Sistemi")
    st.markdown("Kullanıcı adınız ve şifrenizle giriş yapabilirsiniz.")

    with st.form("login_form"):
        user_input = st.text_input(
            "Kullanıcı Adı veya T.C. Kimlik No:", placeholder="Örn: emirhan_k"
        )
        pass_input = st.text_input(
            "Şifre:", type="password", placeholder="••••••••"
        )
        submit_btn = st.form_submit_button(
            "Sisteme Giriş Yap", type="primary"
        )

        if submit_btn:
            if not user_input.strip() or not pass_input.strip():
                st.error("Lütfen tüm alanları doldurunuz!")
            else:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """SELECT id, tc_no, kullanici_adi, sifre_hash, ad, hedef_alan, sinif_seviyesi, 
                                   alan_kilitli, rol, hesap_durumu, lisans_bitis, streak_count, diploma_notu 
                           FROM ogrenciler 
                           WHERE kullanici_adi = ? OR tc_no = ?""",
                        (user_input.strip(), user_input.strip()),
                    )
                    user = cursor.fetchone()

                if user:
                    stored_hash = user[3]
                    hesap_durumu = user[9]
                    lisans_bitis_str = user[10]

                    if hesap_durumu == "Pasif":
                        st.error(
                            "🚫 Hesabınız dondurulmuştur/pasif durumdadır."
                            " Lütfen koçunuzla iletişime geçin."
                        )
                    elif hesap_durumu == "İptal Edildi":
                        st.error(
                            "❌ Üyeliğiniz iptal edilmiştir. Sisteme giriş"
                            " yapamazsınız."
                        )
                    elif (
                        lisans_bitis_str
                        and datetime.strptime(
                            lisans_bitis_str, "%Y-%m-%d"
                        ).date()
                        < get_tr_now().date()
                    ):
                        st.error(
                            "⏳ Üyelik süreniz dolmuştur! Lütfen koçunuzla"
                            " iletişime geçin."
                        )
                    elif stored_hash and verify_password(
                        stored_hash, pass_input.strip()
                    ):
                        updated_streak = update_user_streak(user[0])
                        st.session_state.active_user = {
                            "id": user[0],
                            "tc_no": user[1],
                            "kullanici_adi": user[2],
                            "ad": user[4],
                            "hedef_alan": user[5],
                            "sinif_seviyesi": user[6],
                            "alan_kilitli": user[7],
                            "rol": user[8],
                            "streak_count": updated_streak,
                            "diploma_notu": user[12] if user[12] else 85.0,
                        }
                        log_islem(
                            user[0], "LOGIN", "Kullanıcı başarıyla giriş yaptı."
                        )
                        set_flash_message(
                            "success", f"Hoş geldin, {user[4]}."
                        )
                        st.rerun()
                    else:
                        st.error("❌ Hatalı şifre veya kullanıcı adı!")
                else:
                    st.error("❌ Böyle bir kullanıcı bulunamadı.")
    st.stop()
