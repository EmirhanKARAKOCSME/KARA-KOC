"""Sekme 2 - Konu Takip & İlerleme.

Mikro konu ve alt başlık işaretleme geri çağrıları (callback) buradadır;
veritabanı işini `services.topic_progress` yapar."""


import pandas as pd
import streamlit as st

from config.database import get_connection, log_islem
from data.subtopics import MIKRO_ALT_KONULAR
from data.weights_and_times import KONU_SURELERI_DK
from services.topic_progress import (
    alt_durumlari_yukle,
    alt_konu_isaretle,
    alt_konulari_senkronla,
    soru_borcu_baslat,
)
from views.shared import aktif_ogrenci_id, set_flash_message


def alt_konu_degisti(ders, makro, mikro, alt, key_name):
    uid = (st.session_state.get("active_user") or {}).get("id")
    if not uid:
        return
    val = bool(st.session_state.get(key_name, False))
    alt_konu_isaretle(uid, ders, makro, mikro, alt, val)
    st.session_state.pop(f"chk_{ders}_{makro}_{mikro}", None)   # mikro kutusu DB'den yeniden okunsun
    st.session_state.pop(f"toplu_{ders}_{makro}", None)
    log_islem(uid, "SUBTOPIC_TOGGLE", f"{ders} -> {mikro} -> {alt}")


def alt_konu_arayuzu_ciz(ders_adi, makro_adi, mikro_ad, alt_set):
    """Konu Takip & İlerleme sekmesinde her mikro konunun alt başlıklarını çizer."""
    alts = MIKRO_ALT_KONULAR.get(mikro_ad, [])
    if not alts:
        return
    biten = sum(1 for a in alts if (ders_adi, mikro_ad, a) in alt_set)
    goster = st.checkbox(
        f"🔽 Alt başlıkları göster ({biten}/{len(alts)})",
        key=f"goster_{ders_adi}_{makro_adi}_{mikro_ad}",
    )
    if not goster:
        return
    for a in alts:
        key = f"alt_{ders_adi}_{makro_adi}_{mikro_ad}_{a}"
        if key not in st.session_state:
            st.session_state[key] = (ders_adi, mikro_ad, a) in alt_set
        st.checkbox(
            f"▫️ {a}",
            key=key,
            on_change=alt_konu_degisti,
            args=(ders_adi, makro_adi, mikro_ad, a, key),
        )


def on_mikro_change(ders_adi, makro_adi, mikro_ad, key_name):
    val = st.session_state.get(key_name, False)
    with get_connection() as c:
        cur = c.cursor()
        if val:
            cur.execute(
                "INSERT INTO konu_durumlari_detay (ogrenci_id, ders,"
                " makro_konu, mikro_konu, durum) VALUES (?, ?, ?, ?,"
                " 'Biliyorum') ON CONFLICT DO UPDATE SET durum='Biliyorum'",
                (aktif_ogrenci_id(), ders_adi, makro_adi, mikro_ad),
            )
        else:
            cur.execute(
                "DELETE FROM konu_durumlari_detay WHERE ogrenci_id = ? AND"
                " ders = ? AND makro_konu = ? AND mikro_konu = ?",
                (aktif_ogrenci_id(), ders_adi, makro_adi, mikro_ad),
            )
        c.commit()
    log_islem(aktif_ogrenci_id(), "TOPIC_TOGGLE", f"{ders_adi} -> {mikro_ad}")
    if val:
        soru_borcu_baslat(aktif_ogrenci_id(), ders_adi, [mikro_ad])
        alt_konulari_senkronla(aktif_ogrenci_id(), ders_adi, makro_adi, [mikro_ad], val)


def on_toplu_change(ders_adi, makro_adi, mikro_listesi, toplu_key):
    val = st.session_state.get(toplu_key, False)
    with get_connection() as c:
        cur = c.cursor()
        cur.execute(
            "DELETE FROM konu_durumlari_detay WHERE ogrenci_id = ? AND ders = ?"
            " AND makro_konu = ?",
            (aktif_ogrenci_id(), ders_adi, makro_adi),
        )
        if val:
            for m in mikro_listesi:
                cur.execute(
                    "INSERT INTO konu_durumlari_detay (ogrenci_id, ders,"
                    " makro_konu, mikro_konu, durum) VALUES (?, ?, ?, ?,"
                    " 'Biliyorum')",
                    (aktif_ogrenci_id(), ders_adi, makro_adi, m),
                )
        c.commit()
        if val:
            soru_borcu_baslat(aktif_ogrenci_id(), ders_adi, mikro_listesi)
    for m in mikro_listesi:
        st.session_state.pop(f"chk_{ders_adi}_{makro_adi}_{m}", None)
        alt_konulari_senkronla(aktif_ogrenci_id(), ders_adi, makro_adi, mikro_listesi, val)


def on_ders_tamamen_bitir(ders_adi, makro_dict, bitir_mi=True):
    with get_connection() as c:
        cur = c.cursor()
        cur.execute(
            "DELETE FROM konu_durumlari_detay WHERE ogrenci_id = ? AND ders ="
            " ?",
            (aktif_ogrenci_id(), ders_adi),
        )
        if bitir_mi:
            for makro_ad, mikro_listesi in makro_dict.items():
                if isinstance(mikro_listesi, list):
                    for mik_ad in mikro_listesi:
                        cur.execute(
                            "INSERT INTO konu_durumlari_detay (ogrenci_id,"
                            " ders, makro_konu, mikro_konu, durum) VALUES (?,"
                            " ?, ?, ?, 'Biliyorum')",
                            (aktif_ogrenci_id(), ders_adi, makro_ad, mik_ad),
                        )
        c.commit()

    for makro_ad, mikro_listesi in makro_dict.items():
        if isinstance(mikro_listesi, list):
            for mik_ad in mikro_listesi:
                st.session_state.pop(
                    f"chk_{ders_adi}_{makro_ad}_{mik_ad}", None
                )
            st.session_state.pop(f"toplu_{ders_adi}_{makro_ad}", None)
    for makro_ad, mikro_listesi in makro_dict.items():
        if isinstance(mikro_listesi, list):
            alt_konulari_senkronla(
                aktif_ogrenci_id(), ders_adi, makro_ad, mikro_listesi, bitir_mi
            )


def render(ctx):
    st.header("📚 Konu Takip Listesi")
    with get_connection() as conn:
        df_tum_bilinenler = pd.read_sql_query(
            "SELECT ders, makro_konu, mikro_konu FROM konu_durumlari_detay"
            " WHERE ogrenci_id = ? AND durum = 'Biliyorum'",
            conn,
            params=(ctx.user["id"],),
        )
    bilinen_pairs_set = set(
        zip(df_tum_bilinenler["ders"], df_tum_bilinenler["mikro_konu"])
    )
    alt_durum_seti = set(alt_durumlari_yukle(ctx.user["id"]))

    if ctx.mufredat:
        ders_tablari = st.tabs(
            list(ctx.mufredat.keys()),
            key="kt_ders_tabs",
            on_change="rerun",
        )

        for i, (ders_adi, makro_konular) in enumerate(
            ctx.mufredat.items()
        ):
            with ders_tablari[i]:
                st.subheader(f"📖 {ders_adi}")
                col_btn1, col_btn2 = st.columns([3, 1])
                with col_btn1:
                    if st.button(
                        f"🚀 {ders_adi} Dersinin Tümünü Tamamla",
                        key=f"btn_full_finish_{ders_adi}",
                        type="primary",
                    ):
                        on_ders_tamamen_bitir(
                            ders_adi, makro_konular, bitir_mi=True
                        )
                        set_flash_message(
                            "success",
                            f"🎉 {ders_adi} dersinin tüm konuları tamamlandı!",
                        )
                        st.rerun()
                with col_btn2:
                    if st.button(
                        f"🧹 {ders_adi} Sıfırla",
                        key=f"btn_full_reset_{ders_adi}",
                        type="secondary",
                    ):
                        on_ders_tamamen_bitir(
                            ders_adi, makro_konular, bitir_mi=False
                        )
                        set_flash_message(
                            "warning", f"{ders_adi} dersi konuları sıfırlandı."
                        )
                        st.rerun()

                st.markdown("---")

                if isinstance(makro_konular, dict):
                    for makro_adi, mikro_listesi in makro_konular.items():
                        if isinstance(mikro_listesi, list):
                            tamamlananlar = [
                                m
                                for m in mikro_listesi
                                if (ders_adi, m) in bilinen_pairs_set
                            ]
                            toplam_mikro = len(mikro_listesi)
                            tamamlanan_sayi = len(tamamlananlar)
                            yuzde = (
                                int((tamamlanan_sayi / toplam_mikro) * 100)
                                if toplam_mikro > 0
                                else 0
                            )

                            expander_baslik = (
                                f"{'✅' if yuzde == 100 else '📌'} {makro_adi}"
                                f" (%{yuzde} Tamamlandı)"
                            )
                            with st.expander(
                                expander_baslik, expanded=(yuzde < 100)
                            ):
                                st.progress(yuzde / 100.0)
                                col_ak1, col_ak2 = st.columns([3, 1])
                                with col_ak1:
                                    st.write("**Alt Konular:**")
                                    for mikro_ad in mikro_listesi:
                                        key_name = (
                                            f"chk_{ders_adi}_{makro_adi}_{mikro_ad}"
                                        )
                                        is_completed = (
                                            ders_adi,
                                            mikro_ad,
                                        ) in bilinen_pairs_set
                                        if key_name not in st.session_state:
                                            st.session_state[key_name] = (
                                                is_completed
                                            )

                                        sure_dk = KONU_SURELERI_DK.get(
                                            mikro_ad, 60
                                        )
                                        label_str = (
                                            f"{mikro_ad} ⏱️ (~{sure_dk} dk"
                                            " Çalışma Süresi)"
                                        )

                                        st.checkbox(
                                            label_str,
                                            key=key_name,
                                            on_change=on_mikro_change,
                                            args=(
                                                ders_adi,
                                                makro_adi,
                                                mikro_ad,
                                                key_name,
                                            ),
                                        )
                                        alt_konu_arayuzu_ciz(
                                            ders_adi, makro_adi, mikro_ad, alt_durum_seti
                                        )

                                with col_ak2:
                                    st.write("**Hızlı Seçim:**")
                                    toplu_key = f"toplu_{ders_adi}_{makro_adi}"
                                    if toplu_key not in st.session_state:
                                        st.session_state[toplu_key] = (
                                            yuzde == 100 and toplam_mikro > 0
                                        )
                                    st.checkbox(
                                        "Tümünü Tamamla",
                                        key=toplu_key,
                                        on_change=on_toplu_change,
                                        args=(
                                            ders_adi,
                                            makro_adi,
                                            mikro_listesi,
                                            toplu_key,
                                        ),
                                    )
