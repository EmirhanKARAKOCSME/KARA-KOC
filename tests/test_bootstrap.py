"""Veritabanı bootstrap testleri (FAZ D kabul kriterleri).

Tüm testler **geçici** veritabanlarında çalışır; gerçek `yks_veritabani.db`
dosyasına dokunulmaz.

Kapsam:
01 İlk bootstrap şemayı kurar (çekirdek + servis tabloları + admin).
02 Aynı (yol, sürüm) için ikinci çağrı cache'ten döner; migration tekrar etmez.
03 Farklı DB yolu için ayrı bootstrap çalışır.
04 Şema sürümü değişince bootstrap yeniden çalışır.
05 Bootstrap hata verirse başarı cache'lenmez.
06 Cache'lenen değer SQLite bağlantısı değildir.
07 Cache temizlendiğinde başlangıç yeniden çalışır.
08 foreign_keys ve WAL davranışı korunur.
09 Mevcut veriler ve admin kaydı idempotent kalır.
10 Bootstrap sonunda tüm servisler aynı DB dosyasını gösterir.

Çalıştırma:
    python tests/test_bootstrap.py
    python -m unittest discover -s tests -v
"""
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

from config import database  # noqa: E402
from services import (  # noqa: E402
    core_schema,
    gorev_kaynaklari,
    planner,
    programs,
    ranking_engine,
    spaced_repetition,
    study_sessions,
    task_steps,
    weekly_report,
    wrong_questions,
)

SERVISLER = (
    study_sessions,
    programs,
    task_steps,
    planner,
    spaced_repetition,
    wrong_questions,
    gorev_kaynaklari,
    weekly_report,
    ranking_engine,
)


class BootstrapTestleri(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp(prefix="karakoc_bootstrap_")
        self.db = os.path.join(self.dizin, "test.db")
        database.bootstrap_onbellegini_temizle()

    def tearDown(self):
        database.bootstrap_onbellegini_temizle()
        # Servisleri varsayılan yola geri al (diğer testler etkilenmesin).
        for servis in SERVISLER:
            servis.db_yolu_ayarla(None)
        shutil.rmtree(self.dizin, ignore_errors=True)

    def tablolar(self, yol):
        """Verilen DB dosyasındaki tablo adları."""
        conn = sqlite3.connect(yol)
        try:
            return {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        finally:
            conn.close()

    def test_01_ilk_bootstrap_semayi_kurar(self):
        self.assertTrue(database.bootstrap_database(self.db))
        tablolar = self.tablolar(self.db)
        for beklenen in (
            "ogrenciler",
            "konu_durumlari_detay",
            "deneme_konu_yanlislari",
            "konu_soru_ilerleme",
            "alt_konu_durumlari",
            "sistem_loglari",
        ):
            self.assertIn(beklenen, tablolar)
        conn = sqlite3.connect(self.db)
        try:
            admin = conn.execute(
                "SELECT COUNT(*) FROM ogrenciler WHERE kullanici_adi = 'admin'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(admin, 1, "Varsayılan yönetici bir kez eklenir")

    def test_02_ayni_yol_ikinci_cagrida_cache_kullanilir(self):
        sayac = {"n": 0}
        gercek = core_schema.init_db

        def sayan(db_path=None):
            sayac["n"] += 1
            return gercek(db_path)

        with mock.patch.object(core_schema, "init_db", sayan):
            self.assertTrue(database.bootstrap_database(self.db))
            self.assertTrue(database.bootstrap_database(self.db))
        self.assertEqual(sayac["n"], 1, "Aynı anahtar için migration tekrar etmez")

    def test_03_farkli_db_yolu_ayri_bootstrap(self):
        diger = os.path.join(self.dizin, "diger.db")
        self.assertTrue(database.bootstrap_database(self.db))
        self.assertTrue(database.bootstrap_database(diger))
        self.assertTrue(os.path.exists(diger))
        self.assertIn("ogrenciler", self.tablolar(diger))

    def test_04_sema_surumu_degisince_yeniden_calisir(self):
        sayac = {"n": 0}
        gercek = core_schema.init_db

        def sayan(db_path=None):
            sayac["n"] += 1
            return gercek(db_path)

        with mock.patch.object(core_schema, "init_db", sayan):
            database.bootstrap_database(self.db)
            database.bootstrap_database(self.db)
            database.bootstrap_database(self.db, schema_version="2")
        self.assertEqual(sayac["n"], 2)

    def test_05_hata_basari_cache_lemez(self):
        gercek = task_steps.init_db
        cagri = {"n": 0}

        def patlayan():
            cagri["n"] += 1
            if cagri["n"] == 1:
                raise RuntimeError("şema hatası")
            return gercek()

        with mock.patch.object(task_steps, "init_db", patlayan):
            with self.assertRaises(RuntimeError):
                database.bootstrap_database(self.db)
            # Hata cache'lenmediği için ikinci çağrı yeniden dener ve başarılı olur.
            self.assertTrue(database.bootstrap_database(self.db))
        self.assertEqual(cagri["n"], 2)

    def test_06_cache_lenen_deger_baglanti_degildir(self):
        sonuc = database.bootstrap_database(self.db)
        self.assertIsInstance(sonuc, bool)
        self.assertNotIsInstance(sonuc, sqlite3.Connection)

    def test_07_cache_temizlenince_yeniden_calisir(self):
        sayac = {"n": 0}
        gercek = core_schema.init_db

        def sayan(db_path=None):
            sayac["n"] += 1
            return gercek(db_path)

        with mock.patch.object(core_schema, "init_db", sayan):
            database.bootstrap_database(self.db)
            database.bootstrap_onbellegini_temizle()
            database.bootstrap_database(self.db)
        self.assertEqual(sayac["n"], 2)

    def test_08_foreign_key_ve_wal_korunuyor(self):
        database.bootstrap_database(self.db)
        conn = database.get_connection(self.db)
        try:
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(
                conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal"
            )
        finally:
            conn.close()

    def test_09_mevcut_veri_korunur_ve_idempotent(self):
        database.bootstrap_database(self.db)
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                "INSERT INTO ogrenciler (tc_no, kullanici_adi, sifre_hash, ad)"
                " VALUES ('12345678901', 'mevcut', 'x:y', 'Mevcut Öğrenci')"
            )
            conn.commit()
        finally:
            conn.close()

        database.bootstrap_onbellegini_temizle()
        self.assertTrue(database.bootstrap_database(self.db))

        conn = sqlite3.connect(self.db)
        try:
            ad = conn.execute(
                "SELECT ad FROM ogrenciler WHERE kullanici_adi = 'mevcut'"
            ).fetchone()
            admin_sayisi = conn.execute(
                "SELECT COUNT(*) FROM ogrenciler WHERE kullanici_adi = 'admin'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(ad[0], "Mevcut Öğrenci", "Var olan veri silinmemeli")
        self.assertEqual(admin_sayisi, 1, "Admin kaydı çoğalmamalı")

    def test_10_tum_servisler_ayni_db_yolunu_gosterir(self):
        database.bootstrap_database(self.db)
        beklenen = os.path.abspath(self.db)
        for servis in SERVISLER:
            self.assertEqual(
                os.path.abspath(servis._db_yolu),
                beklenen,
                "%s farklı veritabanına bakıyor" % servis.__name__,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
