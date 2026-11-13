"""v2.5 — Yönetici kimliği, parola hash'i ve sunucu taraflı yetki testleri.

Doğrulananlar:
- Admin parolası koda gömülü DEĞİL; secret'tan gelir.
- Yeni parola hash'i scrypt; eski PBKDF2 kayıtları hâlâ doğrulanır.
- Bootstrap idempotenttir; parola yalnızca secret değişince güncellenir.
- Secret yoksa bilinen varsayılan parola OLUŞMAZ; eski PBKDF2 admin pasifleşir.
- Öğrenci admin sayılmaz; yetkisiz girişim loglanır.
- `kullanici_rolu` pasif hesap için None döner.

Tüm testler geçici SQLite üzerinde çalışır; gerçek DB'ye dokunulmaz.
"""
import hashlib
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(TEST_KOK)
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from services import auth_service, core_schema  # noqa: E402
from services.auth_service import hash_password, verify_password  # noqa: E402

_TEST_PAROLA = "Pilot-Admin-Guvenli-2026!"
# Eski varsayılan parola; ürün kodunda literal olarak tutulmaz.
_ESKI_VARSAYILAN = "karakoc" + "123"


def _eski_pbkdf2(parola):
    tuz = os.urandom(16)
    ozet = hashlib.pbkdf2_hmac("sha256", parola.encode(), tuz, 100000)
    return tuz.hex() + ":" + ozet.hex()


class _Temel(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="karakoc_admin_")
        self.db = os.path.join(self.klasor, "test.db")
        self.onceki_env = os.environ.get("KARAKOC_DB_PATH")
        os.environ["KARAKOC_DB_PATH"] = self.db

    def tearDown(self):
        if self.onceki_env is None:
            os.environ.pop("KARAKOC_DB_PATH", None)
        else:
            os.environ["KARAKOC_DB_PATH"] = self.onceki_env
        shutil.rmtree(self.klasor, ignore_errors=True)

    def _bootstrap(self, parola=_TEST_PAROLA, kullanici="admin"):
        bilgi = {
            "kullanici_adi": kullanici,
            "parola": parola,
            "parola_tanimli": bool(parola),
        }
        with mock.patch.object(core_schema, "admin_kimlik_bilgisi", lambda: bilgi):
            core_schema.init_db(self.db)

    def _admin(self):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(
                "SELECT id, kullanici_adi, sifre_hash, rol, hesap_durumu"
                " FROM ogrenciler WHERE rol = 'admin' ORDER BY id ASC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()

    def _ogrenci_ekle(self, kullanici="ogrenci1", durum="Aktif"):
        conn = sqlite3.connect(self.db)
        try:
            imlec = conn.execute(
                "INSERT INTO ogrenciler (tc_no, kullanici_adi, sifre_hash, ad,"
                " rol, hesap_durumu) VALUES (?, ?, ?, 'Öğrenci', 'ogrenci', ?)",
                ("12345678901", kullanici, hash_password("ogrenci-parola"), durum),
            )
            conn.commit()
            return int(imlec.lastrowid)
        finally:
            conn.close()


class ParolaHashTestleri(unittest.TestCase):
    def test_scrypt_hash_ve_dogrulama(self):
        h = hash_password("gizli")
        self.assertTrue(h.startswith("scrypt$"))
        self.assertTrue(verify_password(h, "gizli"))
        self.assertFalse(verify_password(h, "yanlis"))

    def test_eski_pbkdf2_dogrulanir(self):
        h = _eski_pbkdf2("eski-parola")
        self.assertTrue(verify_password(h, "eski-parola"))
        self.assertFalse(verify_password(h, "baska"))


class BootstrapTestleri(_Temel):
    def test_secret_ile_admin_olusturulur(self):
        self._bootstrap()
        admin = self._admin()
        self.assertIsNotNone(admin)
        self.assertEqual(admin[1], "admin")
        self.assertEqual(admin[3], "admin")
        self.assertEqual(admin[4], "Aktif")
        self.assertTrue(verify_password(admin[2], _TEST_PAROLA))
        self.assertFalse(verify_password(admin[2], _ESKI_VARSAYILAN))
        self.assertTrue(auth_service.admin_mi(admin[0]))

    def test_idempotent_tekrar_calistirma(self):
        self._bootstrap()
        ilk = self._admin()
        self._bootstrap()
        ikinci = self._admin()
        self.assertEqual(ilk[0], ikinci[0])
        self.assertEqual(ilk[2], ikinci[2])  # hash değişmedi
        conn = sqlite3.connect(self.db)
        try:
            adet = conn.execute(
                "SELECT COUNT(*) FROM ogrenciler WHERE kullanici_adi = 'admin'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(adet, 1)

    def test_parola_rotasyonu(self):
        self._bootstrap(parola="ilk-parola")
        self._bootstrap(parola="yeni-parola")
        admin = self._admin()
        self.assertTrue(verify_password(admin[2], "yeni-parola"))
        self.assertFalse(verify_password(admin[2], "ilk-parola"))

    def test_secret_yoksa_bilinen_parola_yok(self):
        self._bootstrap(parola=None)
        admin = self._admin()
        self.assertIsNotNone(admin)
        self.assertEqual(admin[4], "Pasif")
        self.assertFalse(verify_password(admin[2], _ESKI_VARSAYILAN))
        self.assertFalse(auth_service.admin_mi(admin[0]))

    def test_eski_pbkdf2_admin_secret_yoksa_pasif(self):
        # Önce eski biçimli (PBKDF2) admin içeren bir DB oluştur.
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                "CREATE TABLE ogrenciler (id INTEGER PRIMARY KEY, tc_no TEXT,"
                " kullanici_adi TEXT, sifre_hash TEXT, ad TEXT,"
                " hedef_alan TEXT, sinif_seviyesi TEXT, alan_kilitli INTEGER,"
                " rol TEXT, hesap_durumu TEXT, lisans_bitis TEXT,"
                " streak_count INTEGER, son_aktif_tarih TEXT, diploma_notu REAL)"
            )
            conn.execute(
                "INSERT INTO ogrenciler (tc_no, kullanici_adi, sifre_hash, ad,"
                " rol, hesap_durumu) VALUES ('99999999999', 'admin', ?, 'Y',"
                " 'admin', 'Aktif')",
                (_eski_pbkdf2("eski-admin"),),
            )
            conn.commit()
        finally:
            conn.close()
        self._bootstrap(parola=None)
        admin = self._admin()
        self.assertEqual(admin[4], "Pasif")
        self.assertFalse(verify_password(admin[2], "eski-admin"))


class YetkiTestleri(_Temel):
    def test_ogrenci_admin_degil(self):
        self._bootstrap()
        ogr = self._ogrenci_ekle()
        self.assertEqual(auth_service.kullanici_rolu(ogr), "ogrenci")
        self.assertFalse(auth_service.admin_mi(ogr))
        self.assertFalse(auth_service.yetki_dogrula(ogr, "admin_panel"))

    def test_yetkisiz_girisim_loglanir(self):
        self._bootstrap()
        ogr = self._ogrenci_ekle()
        auth_service.yetki_dogrula(ogr, "veritabani_yedek")
        conn = sqlite3.connect(self.db)
        try:
            adet = conn.execute(
                "SELECT COUNT(*) FROM sistem_loglari WHERE islem = 'YETKISIZ_ERISIM'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertGreaterEqual(adet, 1)

    def test_pasif_hesap_rolsuz(self):
        self._bootstrap()
        ogr = self._ogrenci_ekle(durum="Pasif")
        self.assertIsNone(auth_service.kullanici_rolu(ogr))
        self.assertFalse(auth_service.admin_mi(ogr))


if __name__ == "__main__":
    unittest.main(verbosity=2)
