"""Yönetici (koç) paneli.

Öğrenci hesapları, lisans, ders/konu ve YKS referans verisi yönetimi.
Panel `st.stop()` ile biter: yönetici öğrenci kokpitine düşmez."""

from datetime import timedelta
from pathlib import Path
import shutil
import sqlite3

import pandas as pd
import streamlit as st

from config.database import (
    bootstrap_onbellegini_temizle,
    get_connection,
    log_islem,
)
from config.settings import get_tr_now, varsayilan_db_yolu
from services.auth_service import hash_password
from services import osym_verisi
from views.shared import set_flash_message

# SQLite dosya imzası: geri yükleme öncesi geçerlilik denetimi.
_SQLITE_BASLIK = b"SQLite format 3\x00"


def yks_referans_verisi_yonetimi(yonetici_id):
    """Yönetici için referans verisi ekleme/silme arayüzü."""
    try:
        ozet = osym_verisi.veri_ozeti()
    except osym_verisi.VeriHatasi as hata:
        st.error("Referans verisi okunamadı: %s" % hata)
        st.caption("Dosya: `%s`" % osym_verisi.veri_dosyasi())
        return

    st.subheader("🎯 YKS Puan–Sıra Referans Verisi")
    st.caption(
        "Simülatörün sıralama tahmini yalnızca buradaki doğrulanmış noktaları"
        " kullanır. Dosya: `%s` · Kayıt: %d · Hatalı: %d · Güncelleme: %s"
        % (
            ozet.get("dosya"),
            ozet.get("kayit_sayisi") or 0,
            ozet.get("hatali_kayit_sayisi") or 0,
            ozet.get("guncelleme") or "—",
        )
    )

    kayitlar = ozet.get("kaynaklar") or []
    if kayitlar:
        st.dataframe(
            pd.DataFrame(kayitlar), width="stretch", hide_index=True
        )
    else:
        st.info(
            "Henüz referans verisi yok. Resmî kaynağa dayanan puan–sıra"
            " noktalarını aşağıdaki formdan ekleyebilirsiniz."
        )

    with st.form("yks_referans_ekle_formu"):
        st.markdown("**Referans kaydı ekle / güncelle**")
        kol1, kol2 = st.columns(2)
        with kol1:
            veri_yil = st.selectbox(
                "Sınav yılı",
                list(reversed(osym_verisi.desteklenen_yillar())),
                key="yks_ref_yil",
            )
            veri_kurum = st.text_input(
                "Kaynak kurum", value="", key="yks_ref_kurum"
            )
            veri_url = st.text_input(
                "Kaynak bağlantısı (URL)", value="", key="yks_ref_url"
            )
        with kol2:
            veri_tur = st.selectbox(
                "Puan türü",
                list(osym_verisi.PUAN_TURLERI),
                key="yks_ref_tur",
            )
            veri_belge = st.text_input(
                "Kaynak belge / tablo adı", value="", key="yks_ref_belge"
            )
            veri_erisim = st.text_input(
                "Erişim tarihi (YYYY-AA-GG)",
                value="",
                placeholder="2026-11-11",
                key="yks_ref_erisim",
            )
        veri_noktalar = st.text_area(
            "Noktalar (her satır: puan;sıra)",
            value="",
            height=120,
            placeholder="500;500\n450;6000\n400;30000",
            key="yks_ref_noktalar",
        )
        veri_not = st.text_input(
            "Not (kapsam / sınırlılık)", value="", key="yks_ref_not"
        )
        if st.form_submit_button("💾 Referans kaydını yaz"):
            try:
                osym_verisi.kayit_ekle(
                    veri_yil,
                    veri_tur,
                    osym_verisi.metinden_noktalar(veri_noktalar),
                    {
                        "kurum": veri_kurum,
                        "belge": veri_belge,
                        "url": veri_url,
                        "erisim_tarihi": veri_erisim or None,
                    },
                    not_metni=veri_not,
                )
            except (ValueError, osym_verisi.VeriHatasi) as hata:
                st.error("Kayıt yazılamadı: %s" % hata)
            else:
                log_islem(
                    yonetici_id,
                    "SAVE_RANK_DATA",
                    "%s / %s" % (veri_yil, veri_tur),
                )
                set_flash_message(
                    "success",
                    "Referans kaydı yazıldı (%s / %s)."
                    % (veri_yil, veri_tur),
                )
                st.rerun()

    if kayitlar:
        with st.form("yks_referans_sil_formu"):
            st.markdown("**Referans kaydı sil**")
            sil_secenekleri = [
                "%s / %s" % (kayit["yil"], kayit["puan_turu"])
                for kayit in kayitlar
            ]
            sil_secim = st.selectbox(
                "Silinecek kayıt", sil_secenekleri, key="yks_ref_sil"
            )
            if st.form_submit_button("🗑️ Seçili kaydı sil"):
                sil_yil, sil_tur = sil_secim.split(" / ")
                osym_verisi.kayit_sil(sil_yil, sil_tur)
                log_islem(yonetici_id, "DELETE_RANK_DATA", sil_secim)
                set_flash_message(
                    "info", "Referans kaydı silindi: %s" % sil_secim
                )
                st.rerun()


def veritabani_yedek_geri_yukle(yonetici_id):
    """SQLite veritabanı yedekleme / geri yükleme arayüzü.

    - Yedek indirme: mevcut `.db` dosyası (WAL checkpoint alındıktan sonra)
      bayt olarak indirilir.
    - Geri yükleme: `file_uploader` değişince OTOMATİK TETİKLENMEZ; yalnızca
      açık "Yedeği Geri Yükle ve Yenile" butonuna basılınca çalışır. Böylece
      sonsuz rerun döngüsü oluşmaz.
    - Yüklenen dosyanın ilk 16 baytı geçerli SQLite başlığı değilse işlem
      reddedilir; geçerliyse mevcut veritabanı `.bak` güvenlik kopyasına
      alınıp yeni dosya üzerine yazılır.
    """
    st.subheader("💾 Veritabanı Yedekleme ve Kurtarma (SQLite)")
    st.caption(
        "Streamlit Community Cloud konteyneri uykuya geçtiğinde yerel "
        "`yks_veritabani.db` dosyası sıfırlanabilir. Düzenli yedek indirip "
        "gerektiğinde buradan geri yükleyebilirsiniz."
    )

    db_yolu = Path(varsayilan_db_yolu())

    # --- 1) Yedek indir -----------------------------------------------------
    if not db_yolu.exists():
        st.warning("Veritabanı dosyası bulunamadı: `%s`" % db_yolu)
    else:
        # WAL modundaki son commit'leri ana dosyaya aktar (tutarlı yedek).
        try:
            with get_connection() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except Exception:  # noqa: BLE001 - checkpoint başarısızsa okuyabildiğimizi alırız
            pass
        try:
            veri = db_yolu.read_bytes()
        except OSError as hata:
            st.error("Veritabanı okunamadı: %s" % hata)
            veri = None
        if veri:
            dosya_adi = "karakoc_yks_yedek_%s.db" % get_tr_now().strftime(
                "%Y%m%d_%H%M"
            )
            st.download_button(
                "⬇️ Yedeği İndir (.db)",
                data=veri,
                file_name=dosya_adi,
                mime="application/octet-stream",
                key="db_yedek_indir_btn",
            )
            st.caption(
                "Önerilen yedek adı: `%s` · Boyut: %d bayt" % (dosya_adi, len(veri))
            )

    st.markdown("---")

    # --- 2) Yedekten geri yükle --------------------------------------------
    st.markdown("**Yedekten Geri Yükle**")
    yuklenen = st.file_uploader(
        "Yedek veritabanı dosyasını seç (.db)",
        type=["db"],
        accept_multiple_files=False,
        key="db_yedek_uploader",
    )
    if st.button(
        "♻️ Yedeği Geri Yükle ve Yenile",
        key="db_yedek_geri_yukle_btn",
        type="primary",
    ):
        if yuklenen is None:
            st.error("Önce bir `.db` yedek dosyası yüklemelisiniz.")
            return
        try:
            icerik = yuklenen.getvalue()
        except Exception as hata:  # noqa: BLE001
            st.error("Dosya okunamadı: %s" % hata)
            return
        if not icerik.startswith(_SQLITE_BASLIK):
            st.error(
                "❌ Geçersiz dosya: bu bir SQLite veritabanı değil. "
                "Geri yükleme reddedildi."
            )
            return
        try:
            # Güvenlik kopyası: mevcut veritabanını bozmadan sakla.
            if db_yolu.exists():
                guvenlik = db_yolu.with_name(db_yolu.name + ".bak")
                shutil.copy2(db_yolu, guvenlik)
            db_yolu.parent.mkdir(parents=True, exist_ok=True)
            db_yolu.write_bytes(icerik)
            # Eski WAL/SHM artıkları geri yüklenen dosyayı bozmasın.
            for uzanti in ("-wal", "-shm"):
                artik = db_yolu.with_name(db_yolu.name + uzanti)
                if artik.exists():
                    try:
                        artik.unlink()
                    except OSError:
                        pass
        except OSError as hata:
            st.error("Geri yükleme başarısız: %s" % hata)
            return
        # Şema/migrasyon yeniden çalışsın; arayüz yenilensin.
        bootstrap_onbellegini_temizle()
        log_islem(
            yonetici_id,
            "DB_RESTORE",
            "Yedekten geri yükleme: %d bayt" % len(icerik),
        )
        set_flash_message("success", "✅ Veritabanı yedekten geri yüklendi.")
        st.rerun()


def render(ctx):
    st.title("👑 KARAKOÇ KOÇLUK YÖNETİCİ PANELİ")
    st.markdown(
        f"Hoş Geldiniz, **{ctx.user['ad']}**. Tüm öğrencileri buradan"
        " yönetebilir, düzenleyebilir ve ders taleplerini inceleyebilirsiniz."
    )

    admin_tab1, admin_tab2, admin_tab3, admin_tab4, admin_tab5 = st.tabs(
        [
            "➕ 1. Yeni Öğrenci Ekle",
            "👥 2. Öğrenci Düzenleme & Yönetim",
            "🛒 3. Özel Ders Talepleri",
            "🎯 4. YKS Referans Verisi",
            "💾 5. Veritabanı Yedekleme",
        ],
        key="kt_admin_tabs",
        on_change="rerun",
    )


    with admin_tab1:
        st.subheader("📝 Yeni Öğrenci Kaydı")
        with st.form("admin_create_user_form"):
            col_u1, col_u2 = st.columns(2)
            with col_u1:
                new_ad = st.text_input(
                    "Ad Soyad:", placeholder="Örn: Ahmet Yılmaz"
                )
                new_username = st.text_input(
                    "Kullanıcı Adı:", placeholder="Örn: ahmet_yilmaz"
                )
                new_pass = st.text_input(
                    "Şifre:", type="password", placeholder="••••••••"
                )
                new_tc = st.text_input(
                    "T.C. Kimlik No:", max_chars=11, placeholder="11 Haneli TC"
                )
            with col_u2:
                new_alan = st.selectbox(
                    "YKS Alanı:", ["Sayısal", "Eşit Ağırlık", "Sözel", "Dil"]
                )
                new_sinif = st.selectbox(
                    "Sınıf Seviyesi:",
                    ["9. Sınıf", "10. Sınıf", "11. Sınıf", "12. Sınıf", "Mezun"],
                )
                new_obp = st.number_input(
                    "Diploma Notu (OBP):",
                    min_value=50.0,
                    max_value=100.0,
                    value=85.0,
                    step=0.1,
                )
                new_lisans_gun = st.number_input(
                    "Lisans Süresi (Gün):",
                    min_value=7,
                    max_value=730,
                    value=30,
                )

            if st.form_submit_button(
                "🚀 Öğrenci Kaydını Oluştur", type="primary"
            ):
                if (
                    not new_ad.strip()
                    or not new_username.strip()
                    or not new_pass.strip()
                    or not new_tc.strip()
                ):
                    st.error("Lütfen zorunlu alanları doldurunuz!")
                else:
                    lisans_tarihi = (
                        get_tr_now() + timedelta(days=new_lisans_gun)
                    ).strftime("%Y-%m-%d")
                    pass_h = hash_password(new_pass.strip())
                    try:
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                """INSERT INTO ogrenciler 
                                   (tc_no, kullanici_adi, sifre_hash, ad, hedef_alan, sinif_seviyesi, alan_kilitli, rol, hesap_durumu, lisans_bitis, streak_count, son_aktif_tarih, diploma_notu) 
                                   VALUES (?, ?, ?, ?, ?, ?, 1, 'ogrenci', 'Aktif', ?, 1, ?, ?)""",
                                (
                                    new_tc.strip(),
                                    new_username.strip(),
                                    pass_h,
                                    new_ad.strip(),
                                    new_alan,
                                    new_sinif,
                                    lisans_tarihi,
                                    get_tr_now().strftime("%Y-%m-%d"),
                                    new_obp,
                                ),
                            )
                            conn.commit()
                        log_islem(
                            ctx.user["id"],
                            "ADMIN_CREATE_USER",
                            f"Kullanıcı eklendi: {new_username}",
                        )
                        set_flash_message(
                            "success",
                            f"🎉 '{new_ad}' kaydı başarıyla oluşturuldu!",
                        )
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error(
                            "⚠️ Bu Kullanıcı Adı veya T.C. Kimlik Numarası"
                            " sistemde zaten var!"
                        )

    with admin_tab2:
        st.subheader("👥 Öğrenci Listesi ve Tam Yetkili Düzenleme")
        with get_connection() as conn:
            df_ogrenciler = pd.read_sql_query(
                "SELECT id, kullanici_adi, tc_no, ad, hedef_alan, sinif_seviyesi,"
                " diploma_notu, hesap_durumu, lisans_bitis FROM ogrenciler"
                " WHERE rol != 'admin'",
                conn,
            )

        if not df_ogrenciler.empty:
            st.dataframe(df_ogrenciler, width="stretch")

            st.markdown("---")
            st.subheader("🛠️ Seçili Öğrenci Bilgilerini Düzenle")
            selected_user_id = st.selectbox(
                "İşlem Yapılacak Öğrenciyi Seçin:",
                options=df_ogrenciler["id"].tolist(),
                format_func=lambda x: (
                    f"{df_ogrenciler[df_ogrenciler['id']==x]['ad'].values[0]}"
                    " ("
                    f"{df_ogrenciler[df_ogrenciler['id']==x]['kullanici_adi'].values[0]}"
                    ")"
                ),
            )

            ogr_row = df_ogrenciler[
                df_ogrenciler["id"] == selected_user_id
            ].iloc[0]

            with st.form("admin_edit_full_user_form"):
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    edit_ad = st.text_input("Ad Soyad:", value=ogr_row["ad"])
                    edit_username = st.text_input(
                        "Kullanıcı Adı:", value=ogr_row["kullanici_adi"]
                    )
                    edit_tc = st.text_input(
                        "T.C. Kimlik No:", value=ogr_row["tc_no"], max_chars=11
                    )
                    edit_pass = st.text_input(
                        "Yeni Şifre (Boş bırakılırsa değişmez):",
                        type="password",
                    )
                with col_e2:
                    edit_alan = st.selectbox(
                        "Hedef Alan:",
                        ["Sayısal", "Eşit Ağırlık", "Sözel", "Dil"],
                        index=[
                            "Sayısal",
                            "Eşit Ağırlık",
                            "Sözel",
                            "Dil",
                        ].index(ogr_row["hedef_alan"]),
                    )
                    edit_sinif = st.selectbox(
                        "Sınıf Seviyesi:",
                        [
                            "9. Sınıf",
                            "10. Sınıf",
                            "11. Sınıf",
                            "12. Sınıf",
                            "Mezun",
                        ],
                        index=[
                            "9. Sınıf",
                            "10. Sınıf",
                            "11. Sınıf",
                            "12. Sınıf",
                            "Mezun",
                        ].index(ogr_row["sinif_seviyesi"]),
                    )
                    edit_obp = st.number_input(
                        "Diploma Notu (OBP):",
                        min_value=50.0,
                        max_value=100.0,
                        value=float(ogr_row["diploma_notu"]),
                        step=0.1,
                    )
                    edit_durum = st.selectbox(
                        "Üyelik / Hesap Durumu:",
                        ["Aktif", "Pasif", "İptal Edildi"],
                        index=["Aktif", "Pasif", "İptal Edildi"].index(
                            ogr_row["hesap_durumu"]
                        ),
                    )

                col_sub1, col_sub2 = st.columns(2)
                with col_sub1:
                    save_btn = st.form_submit_button(
                        "💾 Değişiklikleri Kaydet", type="primary"
                    )
                with col_sub2:
                    delete_btn = st.form_submit_button(
                        "🗑️ Öğrenci Kaydını Tamamen Sil"
                    )

                if save_btn:
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        if edit_pass.strip():
                            new_h = hash_password(edit_pass.strip())
                            cursor.execute(
                                """UPDATE ogrenciler 
                                   SET ad=?, kullanici_adi=?, tc_no=?, hedef_alan=?, sinif_seviyesi=?, diploma_notu=?, hesap_durumu=?, sifre_hash=? 
                                   WHERE id=?""",
                                (
                                    edit_ad.strip(),
                                    edit_username.strip(),
                                    edit_tc.strip(),
                                    edit_alan,
                                    edit_sinif,
                                    edit_obp,
                                    edit_durum,
                                    new_h,
                                    selected_user_id,
                                ),
                            )
                        else:
                            cursor.execute(
                                """UPDATE ogrenciler 
                                   SET ad=?, kullanici_adi=?, tc_no=?, hedef_alan=?, sinif_seviyesi=?, diploma_notu=?, hesap_durumu=? 
                                   WHERE id=?""",
                                (
                                    edit_ad.strip(),
                                    edit_username.strip(),
                                    edit_tc.strip(),
                                    edit_alan,
                                    edit_sinif,
                                    edit_obp,
                                    edit_durum,
                                    selected_user_id,
                                ),
                            )
                        conn.commit()
                    log_islem(
                        ctx.user["id"],
                        "ADMIN_UPDATE_USER",
                        f"ID {selected_user_id} güncellendi.",
                    )
                    set_flash_message(
                        "success", "Öğrenci bilgileri güncellendi!"
                    )
                    st.rerun()

                if delete_btn:
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "DELETE FROM ogrenciler WHERE id = ?",
                            (selected_user_id,),
                        )
                        conn.commit()
                    log_islem(
                        ctx.user["id"],
                        "ADMIN_DELETE_USER",
                        f"ID {selected_user_id} silindi.",
                    )
                    set_flash_message("warning", "Öğrenci kaydı silindi!")
                    st.rerun()
        else:
            st.info("Sistemde henüz kayıtlı öğrenci bulunmuyor.")

    with admin_tab3:
        st.subheader("📜 Öğrenci Özel Ders Talepleri")
        with get_connection() as conn:
            df_all_talepler = pd.read_sql_query(
                "SELECT t.id, o.ad as ogrenci_adi, t.ders, t.konu, t.alarm_turu,"
                " t.talep_tarihi, t.durum FROM pazaryeri_talepler t JOIN"
                " ogrenciler o ON t.ogrenci_id = o.id ORDER BY t.id DESC",
                conn,
            )
        if not df_all_talepler.empty:
            for idx, r in df_all_talepler.iterrows():
                col_adm1, col_adm2 = st.columns([4, 1])
                with col_adm1:
                    st.write(
                        f"👤 **{r['ogrenci_adi']}** | 📘 **{r['ders']} -"
                        f" {r['konu']}** | Tarih: `{r['talep_tarihi']}` | Durum:"
                        f" `{r['durum']}`"
                    )
                with col_adm2:
                    if r["durum"] != "Tamamlandı":
                        if st.button(
                            "✔️ Talebi Onayla", key=f"adm_btn_{r['id']}"
                        ):
                            with get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "UPDATE pazaryeri_talepler SET durum ="
                                    " 'Tamamlandı' WHERE id = ?",
                                    (r["id"],),
                                )
                                conn.commit()
                            log_islem(
                                ctx.user["id"],
                                "ADMIN_APPROVE",
                                f"Talep ID {r['id']} onaylandı.",
                            )
                            set_flash_message("success", "Talep tamamlandı!")
                            st.rerun()
                st.markdown("---")
        else:
            st.info("Henüz özel ders talebi yok.")

    with admin_tab4:
        yks_referans_verisi_yonetimi(ctx.user["id"])

    with admin_tab5:
        veritabani_yedek_geri_yukle(ctx.user["id"])

    st.markdown("---")
    if st.button("🚪 Yönetici Oturumunu Kapat"):

        st.session_state.active_user = None
        st.rerun()
    st.stop()
