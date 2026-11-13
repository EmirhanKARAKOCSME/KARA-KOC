"""v2.5 — SQLite yedekleme / bütünlük / geri yükleme testleri.

- Backup API ile tutarlı yedek üretilir ve `integrity_check` geçer.
- Geçersiz dosya geri yüklemesi reddedilir.
- Geri yükleme sonrası bütünlük, tablo ve öğrenci sayısı doğrulanır.
- Gerçek `yks_veritabani.db` dosyasına DOKUNULMAZ (yalnızca geçici DB).
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(TEST_KOK)
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from config import database  # noqa: E402


class YedekTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="karakoc_yedek_")
        self.db = os.path.join(self.klasor, "canli.db")
        conn = sqlite3.connect(self.db)
        conn.executescript(
            "CREATE TABLE ogrenciler (id INTEGER PRIMARY KEY, ad TEXT);"
            "CREATE TABLE denemeler (id INTEGER PRIMARY KEY);"
            "INSERT INTO ogrenciler (ad) VALUES ('Test');"
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.klasor, ignore_errors=True)

    def test_yedek_al_ve_butunluk(self):
        hedef = os.path.join(self.klasor, "yedek.db")
        database.yedek_al(hedef, db_path=self.db)
        self.assertTrue(os.path.exists(hedef))
        self.assertEqual(database.butunluk_kontrol(db_path=hedef), "ok")
        self.assertEqual(database.ogrenci_sayisi(db_path=hedef), 1)
        self.assertGreaterEqual(database.tablo_sayisi(db_path=hedef), 2)

    def test_gecersiz_geri_yukleme_reddedilir(self):
        with self.assertRaises(Exception):
            database.geri_yukle(b"bu bir sqlite dosyasi degil", db_path=self.db)

    def test_geri_yukleme_ve_dogrulama(self):
        hedef = os.path.join(self.klasor, "yedek.db")
        database.yedek_al(hedef, db_path=self.db)
        # Canlı DB'yi boz: öğrenciyi sil.
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM ogrenciler")
        conn.commit()
        conn.close()
        self.assertEqual(database.ogrenci_sayisi(db_path=self.db), 0)

        with open(hedef, "rb") as dosya:
            icerik = dosya.read()
        sonuc = database.geri_yukle(icerik, db_path=self.db)
        self.assertEqual(sonuc["butunluk"], "ok")
        self.assertEqual(sonuc["ogrenci_sayisi"], 1)
        self.assertIsNotNone(sonuc["guvenlik_kopyasi"])

    def test_yedek_dogrula_ve_gecici_kopyaya_geri_yukle(self):
        hedef = os.path.join(self.klasor, "yedek.db")
        database.yedek_al(hedef, db_path=self.db)

        # 1) Yedek tüm tabloları ve öğrenci kayıtlarını içeriyor mu?
        dog = database.yedek_dogrula(hedef, kaynak_db_path=self.db)
        self.assertTrue(dog["saglikli"], dog)
        self.assertEqual(dog["butunluk"], "ok")
        self.assertTrue(dog["tablolar_esit"])
        self.assertTrue(dog["ogrenci_sayisi_esit"])
        self.assertEqual(dog["ogrenci_sayisi"], 1)

        # 2) Geri yüklemeyi GERÇEK/üretim DB'sine değil, ayrı geçici kopyaya yap.
        kopya = os.path.join(self.klasor, "test_kopya.db")
        with open(hedef, "rb") as dosya:
            icerik = dosya.read()
        sonuc = database.geri_yukle(icerik, db_path=kopya)
        self.assertEqual(sonuc["butunluk"], "ok")
        self.assertEqual(database.ogrenci_sayisi(db_path=kopya), 1)
        self.assertEqual(
            database.tablo_sayisi(db_path=kopya),
            database.tablo_sayisi(db_path=self.db),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
