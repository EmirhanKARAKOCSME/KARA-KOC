"""v2.6 — Veritabanı yedekleme güvenliği ve geri yükleme kanıtları.

Kapsam:
- WAL etkinken (açık bağlantı varken) tutarlı yedek.
- Boş olmayan ve boş veritabanı yedekleme.
- Zaman damgalı yedek + saklama sınırı.
- Yedeği GEÇİCİ kopyaya açıp geri yüklenebilirliği kanıtlama.
- Bozuk/eksik yedeğin reddedilmesi ve canlı DB'nin korunması.

Gerçek `yks_veritabani.db` dosyasına DOKUNULMAZ.
"""
import hashlib
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


def _ozet(yol):
    with open(yol, "rb") as dosya:
        return hashlib.sha256(dosya.read()).hexdigest()


class YedekGuvenligiTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="karakoc_yedek_v26_")
        self.db = os.path.join(self.klasor, "canli.db")
        conn = sqlite3.connect(self.db)
        conn.executescript(
            "PRAGMA journal_mode=WAL;"
            "CREATE TABLE ogrenciler (id INTEGER PRIMARY KEY, ad TEXT);"
            "CREATE TABLE denemeler (id INTEGER PRIMARY KEY, net REAL);"
            "INSERT INTO ogrenciler (ad) VALUES ('Öğrenci 1');"
            "INSERT INTO ogrenciler (ad) VALUES ('Öğrenci 2');"
            "INSERT INTO denemeler (net) VALUES (42.5);"
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.klasor, ignore_errors=True)

    def test_wal_acikken_tutarli_yedek(self):
        # WAL'de commit edilmiş ama checkpoint edilmemiş veri yedekte olmalı.
        acik = sqlite3.connect(self.db)
        acik.execute("PRAGMA journal_mode=WAL;")
        acik.execute("INSERT INTO ogrenciler (ad) VALUES ('WAL Öğrencisi')")
        acik.commit()
        hedef = os.path.join(self.klasor, "wal_yedek.db")
        database.yedek_al(hedef, db_path=self.db)
        acik.close()

        kontrol = sqlite3.connect(hedef)
        try:
            adlar = [r[0] for r in kontrol.execute("SELECT ad FROM ogrenciler")]
        finally:
            kontrol.close()
        self.assertIn("WAL Öğrencisi", adlar)
        self.assertEqual(len(adlar), 3)

    def test_bos_veritabani_yedeklenir(self):
        bos = os.path.join(self.klasor, "bos.db")
        conn = sqlite3.connect(bos)
        conn.execute("CREATE TABLE ogrenciler (id INTEGER PRIMARY KEY, ad TEXT)")
        conn.commit()
        conn.close()
        hedef = os.path.join(self.klasor, "bos_yedek.db")
        database.yedek_al(hedef, db_path=bos)
        self.assertEqual(database.butunluk_kontrol(db_path=hedef), "ok")
        self.assertEqual(database.ogrenci_sayisi(db_path=hedef), 0)

    def test_zaman_damgali_yedek_ve_saklama_siniri(self):
        ilk = database.zaman_damgali_yedek(db_path=self.db)
        self.assertTrue(ilk["saglikli"], ilk)
        self.assertRegex(ilk["dosya_adi"], r"^karakoc_yks_yedek_\d{8}_\d{6}")
        self.assertEqual(database.ogrenci_sayisi(db_path=ilk["yol"]), 2)

        # 12 yedek üret: en fazla YEDEK_SAKLAMA_ADEDI tutulmalı.
        for _ in range(11):
            database.zaman_damgali_yedek(db_path=self.db)
        liste = database.yedek_listesi(db_path=self.db)
        self.assertLessEqual(len(liste), database.YEDEK_SAKLAMA_ADEDI)
        self.assertGreaterEqual(len(liste), 1)
        self.assertTrue(
            database.son_yedek_bilgisi(db_path=self.db)["dosya_adi"].startswith(
                database.YEDEK_DOSYA_ONEKI
            )
        )

    def test_yedek_gecici_kopyaya_geri_yuklenebilir(self):
        yedek = database.zaman_damgali_yedek(db_path=self.db)
        sonuc = database.yedekten_gecici_dogrula(
            yedek["yol"], kaynak_db_path=self.db
        )
        self.assertTrue(sonuc["geri_yuklenebilir"], sonuc)
        self.assertTrue(sonuc["ogrenci_sayisi_esit"])
        self.assertEqual(sonuc["ogrenci_sayisi"], 2)

    def test_bozuk_yedek_reddedilir_ve_canli_db_korunur(self):
        onceki = _ozet(self.db)
        with self.assertRaises(sqlite3.DatabaseError):
            database.geri_yukle(b"SQLite format 3\x00" + b"bozuk" * 30,
                                db_path=self.db)
        self.assertEqual(_ozet(self.db), onceki)

        bozuk = os.path.join(self.klasor, "bozuk.db")
        with open(bozuk, "wb") as dosya:
            dosya.write(b"kesinlikle sqlite degil")
        with self.assertRaises(sqlite3.DatabaseError):
            database.yedekten_gecici_dogrula(bozuk)

    def test_eksik_yedek_dosyasi_reddedilir(self):
        with self.assertRaises(FileNotFoundError):
            database.yedekten_gecici_dogrula(
                os.path.join(self.klasor, "yok.db")
            )

    def test_geri_yukleme_sonrasi_tablolar_ve_ogrenciler_korunur(self):
        yedek = database.zaman_damgali_yedek(db_path=self.db)
        # Canlı DB'de veriyi değiştir.
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM ogrenciler")
        conn.commit()
        conn.close()
        self.assertEqual(database.ogrenci_sayisi(db_path=self.db), 0)

        with open(yedek["yol"], "rb") as dosya:
            icerik = dosya.read()
        sonuc = database.geri_yukle(icerik, db_path=self.db)
        self.assertEqual(sonuc["butunluk"], "ok")
        self.assertEqual(sonuc["ogrenci_sayisi"], 2)
        self.assertIsNotNone(sonuc["guvenlik_kopyasi"])
        self.assertTrue(os.path.exists(sonuc["guvenlik_kopyasi"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
