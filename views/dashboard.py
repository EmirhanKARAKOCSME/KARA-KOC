"""Öğrenci kokpiti: profil kenar çubuğu, üst metrikler ve alarm
bannerları. Sekme tanımları burada değil, `main.py` içindedir."""


import streamlit as st

from config.database import get_connection, log_islem
from services import osym_verisi
from services.topic_progress import get_aylik_mufredat_hedevi
from views.shared import set_flash_message


def render(ctx, saglik_skoru, delta_yuzde, gercek_orand, tyt_orani, ayt_orani,
           hedef_yuzd=None):
    is_maarif = ctx.user["sinif_seviyesi"] in ["9. Sınıf", "10. Sınıf"]
    with st.sidebar:
        st.title("🎓 Öğrenci Profili")
        st.write(f"**Öğrenci:** {ctx.user['ad']}")
        st.write(f"**Kullanıcı Adı:** `{ctx.user['kullanici_adi']}`")
        st.write(f"**Alan:** `{ctx.user['hedef_alan']}`")
        st.write(f"**Sınıf:** `{ctx.user['sinif_seviyesi']}`")
        st.write(
            "**Diploma Notu (OBP):**"
            f" `{ctx.user.get('diploma_notu', 85.0)}`"
        )
        st.caption(
            "OBP katkısı: +%.1f puan (OBP = diploma notu × 5, katkı = OBP × 0.12)"
            % osym_verisi.obp_katkisi(ctx.user.get("diploma_notu") or 85.0)
        )

        st.markdown(
            """<div class="streak-card">🔥 <b>Çalışma Serisi:"""
            f" {ctx.user['streak_count']} Gün</b></div>",
            unsafe_allow_html=True,
        )

        st.markdown(f"**TYT Müfredatı:** `%{tyt_orani}`")
        st.markdown(f"**AYT Müfredatı:** `%{ayt_orani}`")

        if is_maarif:
            st.markdown(
                '<span class="maarif-rozet">📘 Türkiye Yüzyılı Maarif Modeli</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span class="klasik-rozet">📕 YKS Müfredat Sistemi</span>',
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.subheader("⚙️ Profil Bilgileri")
        with st.form("sidebar_profil_guncelle_form"):
            yeni_alan = st.selectbox(
                "Hedef Alan:",
                ["Sayısal", "Eşit Ağırlık", "Sözel", "Dil"],
                index=(
                    ["Sayısal", "Eşit Ağırlık", "Sözel", "Dil"].index(
                        ctx.user["hedef_alan"]
                    )
                    if ctx.user["hedef_alan"]
                    in ["Sayısal", "Eşit Ağırlık", "Sözel", "Dil"]
                    else 0
                ),
            )
            yeni_sinif = st.selectbox(
                "Sınıf Seviyesi:",
                ["9. Sınıf", "10. Sınıf", "11. Sınıf", "12. Sınıf", "Mezun"],
                index=(
                    [
                        "9. Sınıf",
                        "10. Sınıf",
                        "11. Sınıf",
                        "12. Sınıf",
                        "Mezun",
                    ].index(ctx.user["sinif_seviyesi"])
                    if ctx.user["sinif_seviyesi"]
                    in ["9. Sınıf", "10. Sınıf", "11. Sınıf", "12. Sınıf", "Mezun"]
                    else 3
                ),
            )
            yeni_obp = st.number_input(
                "Diploma Notu (OBP):",
                min_value=50.0,
                max_value=100.0,
                value=float(ctx.user.get("diploma_notu", 85.0)),
                step=0.1,
            )

            if st.form_submit_button("Profili Güncelle", type="secondary"):
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE ogrenciler SET hedef_alan = ?, sinif_seviyesi = ?,"
                        " diploma_notu = ? WHERE id = ?",
                        (yeni_alan, yeni_sinif, yeni_obp, ctx.user["id"]),
                    )
                    conn.commit()
                st.session_state.active_user["hedef_alan"] = yeni_alan
                st.session_state.active_user["sinif_seviyesi"] = yeni_sinif
                st.session_state.active_user["diploma_notu"] = yeni_obp
                log_islem(
                    ctx.user["id"],
                    "UPDATE_PROFILE",
                    f"Alan: {yeni_alan}, OBP: {yeni_obp}",
                )
                set_flash_message("success", "Profiliniz güncellendi!")
                st.rerun()

        st.markdown("---")
        if st.button("🚪 Oturumu Kapat"):
            st.session_state.active_user = None
            st.rerun()

    _baslik_col, _kamp_col = st.columns([4, 1])
    with _baslik_col:
        st.title(
            "🎯 KARAKOÇ YKS Akıllı Koçluk Paneli ("
            f"{ctx.user['hedef_alan']} - {ctx.user['sinif_seviyesi']})"
        )
    with _kamp_col:
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        # v2.3: sade metalik çerçeveli KAMP MODU giriş butonu.
        if st.button(
            "KAMP MODU",
            key="kamp_modu_giris",
            help="Bildirimler kapalı, tam odak: KARAKOÇ YKS KAMP",
            use_container_width=True,
        ):
            st.session_state["kamp_aktif"] = True
            st.rerun()

    toplam_alarm_sayisi = sum(len(v) for v in ctx.alarmlar.values())
    ay_adi_kokpit, _ = get_aylik_mufredat_hedevi(ctx.user["sinif_seviyesi"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🏥 Genel İlerleme Skoru", f"%{saglik_skoru}")
    m2.metric("🔥 Çalışma Serisi", f"{ctx.user['streak_count']} Gün")
    m3.metric("🚨 Dikkat Edilecek Konu", f"{toplam_alarm_sayisi} Adet")
    # v2.6: "-%40" gibi negatif görünen değerler İLERLEME DEĞİLDİR; bunlar
    # aylık hedefe göre FARKTIR. Ekranda eksi işaretiyle "ilerleme" gibi
    # gösterilmez; hedef ve gerçek oran ayrı, fark ise açık metinle verilir.
    fark = round(float(delta_yuzde or 0), 1)
    if fark >= 0:
        delta_label = "Hedefin %.1f puan önünde" % fark
        delta_renk = "normal"
    else:
        delta_label = "Hedefin %.1f puan gerisinde" % abs(fark)
        delta_renk = "inverse"
    m4.metric(
        f"📅 {ay_adi_kokpit} Ayı Takvimi",
        f"%{round(gercek_orand, 1)}",
        delta=delta_label,
        delta_color=delta_renk,
        help=(
            "Bu değer aylık müfredat hedefine göre FARKTIR; konu ilerlemesi "
            "değildir. Hedef: %%%s" % (round(hedef_yuzd, 1) if hedef_yuzd is not None else "—")
        ),
    )
    st.caption(
        "ℹ️ Takvim farkı eksi bir ilerleme değildir; gerçek ilerleme her zaman"
        " %%0–100 arasındadır (Hedef: %%%s)."
        % (round(hedef_yuzd, 1) if hedef_yuzd is not None else "—")
    )

    st.markdown("---")

    # KRİTİK ALARMLAR BANNERLARI
    if ctx.alarmlar["siyah"]:
        for a in ctx.alarmlar["siyah"]:
            st.markdown(
                '<div class="alarm-card-black"><b>⬛ [KRİTİK İVMELENEN YANLIŞ UYARISI]'
                f" {a['ders']} - {a['konu']}</b><br>• {a['detay']}<br>👉"
                f" <b>{a['aksiyon']}</b></div>",
                unsafe_allow_html=True,
            )

    if ctx.alarmlar["kirmizi"]:
        for a in ctx.alarmlar["kirmizi"]:
            st.error(
                f"🔴 **[DİKKAT - TAMAMLANAN KONUDA YANLIŞ]** **{a['ders']} - {a['konu']}** | {a['detay']}\n\n👉"
                f" **{a['aksiyon']}**"
            )
