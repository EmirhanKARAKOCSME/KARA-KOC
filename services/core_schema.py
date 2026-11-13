"""Çekirdek şema: öğrenciler, konu durumları, denemeler, loglar.

Tablo oluşturma tamamen idempotenttir (`CREATE TABLE IF NOT EXISTS`);
mevcut veri silinmez. Varsayılan yönetici hesabı yalnızca hiç yoksa
eklenir. Başlangıç sırası `config/database.py` tarafından yönetilir."""


from config.database import get_connection
from config.settings import admin_kimlik_bilgisi, get_tr_now
from services.auth_service import hash_password, verify_password
from services.exam_service import migrasyon_denemeleri


def _bootstrap_uyari(cursor, mesaj):
    """Yönetici bootstrap uyarısını `sistem_loglari`'na yazar (parola yok)."""
    try:
        cursor.execute(
            "INSERT INTO sistem_loglari (ogrenci_id, islem, detay, tarih)"
            " VALUES (NULL, 'ADMIN_BOOTSTRAP_UYARI', ?, ?)",
            (str(mesaj)[:300], get_tr_now().strftime("%Y-%m-%d %H:%M:%S")),
        )
    except Exception:  # noqa: BLE001 - log yazımı başlangıcı durdurmaz
        pass


def init_db(db_path=None):
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ogrenciler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tc_no TEXT UNIQUE,
                kullanici_adi TEXT UNIQUE,
                sifre_hash TEXT,
                ad TEXT,
                hedef_alan TEXT DEFAULT 'Sayısal',
                sinif_seviyesi TEXT DEFAULT '12. Sınıf',
                alan_kilitli INTEGER DEFAULT 0,
                son_sinif_atlatma_yili INTEGER DEFAULT 0,
                rol TEXT DEFAULT 'ogrenci',
                hesap_durumu TEXT DEFAULT 'Aktif',
                lisans_bitis TEXT,
                streak_count INTEGER DEFAULT 1,
                son_aktif_tarih TEXT,
                diploma_notu REAL DEFAULT 100.0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS konu_durumlari_detay (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                ders TEXT,
                makro_konu TEXT,
                mikro_konu TEXT,
                durum TEXT DEFAULT 'Başlanmadı',
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_konu_detay_unique 
            ON konu_durumlari_detay(ogrenci_id, ders, makro_konu, mikro_konu)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deneme_konu_yanlislari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                deneme_kategorisi TEXT DEFAULT 'Genel Deneme',
                brans_dersi TEXT,
                deneme_turu TEXT,
                deneme_adi TEXT,
                net_bilgisi REAL,
                ders TEXT,
                makro_konu TEXT,
                konu_adi TEXT,
                yanlis_adedi INTEGER,
                yanlis_nedeni TEXT DEFAULT 'Konu Eksikliği',
                durum TEXT DEFAULT 'Aktif',
                tarih TEXT,
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calisma_programi_gorevler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                gun TEXT,
                ders TEXT,
                makro_konu TEXT,
                mikro_konu TEXT,
                gorev_tanimi TEXT,
                hedef_soru INTEGER,
                pedagoji_turu TEXT DEFAULT 'Pekiştirme',
                durum INTEGER DEFAULT 0,
                tarih TEXT,
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pazaryeri_talepler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                ders TEXT,
                konu TEXT,
                alarm_turu TEXT,
                talep_tarihi TEXT,
                durum TEXT DEFAULT 'Talep Alındı',
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sistem_loglari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                islem TEXT,
                detay TEXT,
                tarih TEXT,
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)

        # FAZ 2: Deneme başlığı ayrı bir varlık olarak tutulur. Yanlış detayları
        # bu başlığa `deneme_id` ile bağlanır; böylece aynı adı taşıyan iki
        # deneme asla tek kayıt gibi değerlendirilmez.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS denemeler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                tarih TEXT,
                deneme_adi TEXT,
                deneme_kategorisi TEXT DEFAULT 'Genel Deneme',
                deneme_turu TEXT,
                brans_dersi TEXT,
                net_bilgisi REAL,
                dogru_adedi INTEGER,
                yanlis_adedi INTEGER,
                bos_adedi INTEGER,
                sure_dk INTEGER,
                kayit_kaynagi TEXT DEFAULT 'wizard',
                legacy_signature TEXT,
                olusturma_zamani TEXT,
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)

        # Migrasyonun idempotent olmasını sağlayan kısmi tekil indeks.
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_denemeler_legacy
            ON denemeler(legacy_signature)
            WHERE legacy_signature IS NOT NULL
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_denemeler_ogrenci
            ON denemeler(ogrenci_id, deneme_turu, deneme_kategorisi, brans_dersi)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_denemeler_tarih
            ON denemeler(ogrenci_id, tarih)
        """)

        # FAZ 3: genel denemenin ders bazlı sonuçları. Eski denemeler için
        # geriye dönük kayıt ÜRETİLMEZ; tablo yalnızca yeni girişleri tutar.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deneme_ders_sonuclari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deneme_id INTEGER NOT NULL,
                ders TEXT NOT NULL,
                soru_sayisi INTEGER,
                dogru INTEGER DEFAULT 0,
                yanlis INTEGER DEFAULT 0,
                bos INTEGER DEFAULT 0,
                net REAL DEFAULT 0,
                sure_dk INTEGER,
                FOREIGN KEY(deneme_id) REFERENCES denemeler(id)
                    ON DELETE CASCADE
            )
        """)

        # Aynı denemede aynı ders için ikinci sonuç kaydını engeller.
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_deneme_ders_tekil
            ON deneme_ders_sonuclari(deneme_id, ders)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deneme_ders_ders
            ON deneme_ders_sonuclari(ders, deneme_id)
        """)

        mevcut_kolonlar = [
            satir[1] for satir in cursor.execute(
                "PRAGMA table_info(deneme_konu_yanlislari)"
            )
        ]
        if "deneme_id" not in mevcut_kolonlar:
            cursor.execute(
                "ALTER TABLE deneme_konu_yanlislari"
                " ADD COLUMN deneme_id INTEGER REFERENCES denemeler(id)"
            )
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deneme_yanlis_deneme_id
            ON deneme_konu_yanlislari(deneme_id)
        """)

        # FAZ 2: Eski yanlış kayıtlarını güvenilir imza eşleşmesiyle başlıklara
        # bağla. Idempotenttir; başarısız olursa hiçbir yarım veri bırakmaz.
        try:
            migrasyon_denemeleri(conn)
        except Exception as hata:
            cursor.execute(
                "INSERT INTO sistem_loglari (ogrenci_id, islem, detay, tarih)"
                " VALUES (NULL, 'DENEME_MIGRASYON_HATA', ?, ?)",
                (str(hata), get_tr_now().strftime("%Y-%m-%d %H:%M:%S")),
            )

        # ------------------------------------------------------------------
        # YÖNETİCİ HESABI — GÜVENLİ / IDEMPOTENT BOOTSTRAP
        # ------------------------------------------------------------------
        # Parola KODDA TUTULMAZ. `KARAKOC_ADMIN_USERNAME` ve
        # `KARAKOC_ADMIN_PASSWORD` ortam değişkeni veya Streamlit secrets'tan
        # okunur. Parola tanımlıysa hesap bu parolayla eşitlenir (idempotent);
        # tanımlı değilse BİLİNEN BİR VARSAYILAN PAROLA OLUŞTURULMAZ.
        bilgi = admin_kimlik_bilgisi()
        admin_kullanici = bilgi["kullanici_adi"]
        admin_parola = bilgi["parola"]

        cursor.execute(
            "SELECT id, kullanici_adi, sifre_hash, hesap_durumu FROM ogrenciler"
            " WHERE kullanici_adi = ? OR tc_no = '99999999999' OR rol = 'admin'"
            " ORDER BY CASE WHEN rol = 'admin' THEN 0 ELSE 1 END, id ASC LIMIT 1",
            (admin_kullanici,),
        )
        admin_user = cursor.fetchone()

        if admin_parola:
            yeni_hash = hash_password(admin_parola)
            if not admin_user:
                cursor.execute(
                    """INSERT INTO ogrenciler
                       (tc_no, kullanici_adi, sifre_hash, ad, hedef_alan,
                        sinif_seviyesi, alan_kilitli, rol, hesap_durumu,
                        diploma_notu)
                       VALUES ('99999999999', ?, ?, 'Yönetici (Koç)', 'Yönetim',
                               'Koç', 1, 'admin', 'Aktif', 100.0)""",
                    (admin_kullanici, yeni_hash),
                )
            else:
                admin_id = admin_user[0]
                mevcut_hash = admin_user[2]
                # Parola yalnızca secret ile UYUŞMUYORSA güncellenir; böylece
                # her başlangıçta kontrolsüz sıfırlama olmaz.
                if not verify_password(mevcut_hash, admin_parola):
                    cursor.execute(
                        "UPDATE ogrenciler SET sifre_hash = ? WHERE id = ?",
                        (yeni_hash, admin_id),
                    )
                cursor.execute(
                    "UPDATE ogrenciler SET kullanici_adi = ?, rol = 'admin',"
                    " hesap_durumu = 'Aktif', alan_kilitli = 1 WHERE id = ?",
                    (admin_kullanici, admin_id),
                )
        else:
            if admin_user:
                # Secret yok; eski PBKDF2 biçimli yönetici parolası artık
                # güvenilir kabul edilmez. Secret tanımlanana kadar hesap
                # pasifleştirilir (bilinen varsayılan parola koda gömülmez).
                if not (admin_user[2] or "").startswith("scrypt$"):
                    import secrets as _secrets

                    cursor.execute(
                        "UPDATE ogrenciler SET sifre_hash = ?,"
                        " hesap_durumu = 'Pasif' WHERE id = ?",
                        (hash_password(_secrets.token_urlsafe(32)), admin_user[0]),
                    )
                    _bootstrap_uyari(
                        cursor,
                        "Yönetici parolası secret tanımlı olmadığı için geçersiz"
                        " kılındı; KARAKOC_ADMIN_PASSWORD ayarlayın.",
                    )
            else:
                # Hiç admin yok ve secret yok: giriş yapılamayan (Pasif) kayıt.
                # Testlerin "admin kaydı var" beklentisini karşılar; bilinen
                # parola oluşturmaz.
                import secrets as _secrets

                cursor.execute(
                    """INSERT INTO ogrenciler
                       (tc_no, kullanici_adi, sifre_hash, ad, hedef_alan,
                        sinif_seviyesi, alan_kilitli, rol, hesap_durumu,
                        diploma_notu)
                       VALUES ('99999999999', ?, ?, 'Yönetici (Koç)', 'Yönetim',
                               'Koç', 1, 'admin', 'Pasif', 100.0)""",
                    (admin_kullanici, hash_password(_secrets.token_urlsafe(32))),
                )
                _bootstrap_uyari(
                    cursor,
                    "Yönetici hesabı için KARAKOC_ADMIN_PASSWORD tanımlayın.",
                )
        conn.commit()
