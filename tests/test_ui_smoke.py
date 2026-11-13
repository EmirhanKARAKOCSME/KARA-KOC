"""Arayüz smoke testleri (Streamlit AppTest) - FAZ E kabul kriterleri.

Gerçek veritabanı kullanılmaz: geçici bir DB oluşturulur, test öğrencisi ve
test koçu bu DB'ye yazılır, `KARAKOC_DB_PATH` geçici dosyaya yönlendirilir.

Doğrulananlar:
01 Oturum yokken giriş ekranı açılır (hata yok).
02 Öğrenci girişinde 9 sekmenin tamamı ve başlıkları render edilir.
03 Yönetici girişinde yönetim paneli açılır, öğrenci kokpiti çalışmaz.
04 Hiçbir senaryoda `st.exception` oluşmaz.

Çalıştırma:
    python tests/test_ui_smoke.py
    python -m unittest discover -s tests -v
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
from services import (  # noqa: E402
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
from services.auth_service import hash_password  # noqa: E402

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

SEKME_BASLIKLARI = (
    "Bugünün Görevleri",
    "Konu Takip",
    "Deneme Analizi",
    "Yanlış Soru Defteri",
    "Konu Uyarıları",
    "Haftalık Çalışma Programı",
    "Özel Ders",
    "Haftalık Performans",
    "YKS Puan ve Sıralama Simülatörü",
)

MAIN_PY = os.path.join(KOK, "main.py")


class UiSmokeTestleri(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from streamlit.testing.v1 import AppTest

        cls.AppTest = AppTest
        cls.dizin = tempfile.mkdtemp(prefix="karakoc_ui_")
        cls.db = os.path.join(cls.dizin, "ui.db")
        database.bootstrap_database(cls.db)
        cls._kullanicilari_ekle()
        cls.onceki_env = os.environ.get("KARAKOC_DB_PATH")
        os.environ["KARAKOC_DB_PATH"] = cls.db

    @classmethod
    def _kullanicilari_ekle(cls):
        conn = sqlite3.connect(cls.db)
        try:
            for tc, kadi, ad, alan, sinif, rol in (
                ("11111111111", "test_ogrenci", "Test Öğrenci", "Sayısal",
                 "12. Sınıf", "ogrenci"),
                ("22222222222", "test_koc", "Test Koç", "Yönetim", "Koç", "admin"),
            ):
                conn.execute(
                    "INSERT INTO ogrenciler (tc_no, kullanici_adi, sifre_hash,"
                    " ad, hedef_alan, sinif_seviyesi, rol, hesap_durumu,"
                    " diploma_notu) VALUES (?, ?, ?, ?, ?, ?, ?, 'Aktif', 88.0)",
                    (tc, kadi, hash_password("test123"), ad, alan, sinif, rol),
                )
            conn.commit()
            cls.ogrenci = cls._kullanici(conn, "test_ogrenci", "ogrenci")
            cls.koc = cls._kullanici(conn, "test_koc", "admin")
        finally:
            conn.close()

    @staticmethod
    def _kullanici(conn, kadi, rol):
        satir = conn.execute(
            "SELECT id, tc_no, kullanici_adi, ad, hedef_alan, sinif_seviyesi,"
            " rol, diploma_notu FROM ogrenciler WHERE kullanici_adi = ?",
            (kadi,),
        ).fetchone()
        return {
            "id": satir[0],
            "tc_no": satir[1],
            "kullanici_adi": satir[2],
            "ad": satir[3],
            "hedef_alan": satir[4],
            "sinif_seviyesi": satir[5],
            "alan_kilitli": 1 if rol == "admin" else 0,
            "rol": satir[6],
            "streak_count": 1,
            "diploma_notu": satir[7],
        }

    @classmethod
    def tearDownClass(cls):
        database.bootstrap_onbellegini_temizle()
        for servis in SERVISLER:
            servis.db_yolu_ayarla(None)
        if cls.onceki_env is None:
            os.environ.pop("KARAKOC_DB_PATH", None)
        else:
            os.environ["KARAKOC_DB_PATH"] = cls.onceki_env
        shutil.rmtree(cls.dizin, ignore_errors=True)

    def setUp(self):
        database.bootstrap_onbellegini_temizle()

    def calistir(self, kullanici=None):
        at = self.AppTest.from_file(MAIN_PY, default_timeout=300)
        if kullanici is not None:
            at.session_state["active_user"] = kullanici
        at.run()
        return at

    def test_01_giris_ekrani_hatasiz(self):
        at = self.calistir()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertGreaterEqual(len(at.button), 1)
        self.assertEqual(len(at.tabs), 0)

    def test_02_ogrenci_dokuz_sekme(self):
        at = self.calistir(self.ogrenci)
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        basliklar = [h.value for h in at.header]
        self.assertGreaterEqual(len(basliklar), 9, basliklar)
        for beklenen in SEKME_BASLIKLARI:
            self.assertTrue(
                any(beklenen in baslik for baslik in basliklar),
                "Sekme başlığı bulunamadı: %s" % beklenen,
            )

    def test_03_yonetici_paneli(self):
        at = self.calistir(self.koc)
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertGreaterEqual(len(at.tabs), 4)
        self.assertGreaterEqual(len(at.selectbox), 1)

    def test_04_gercek_db_degismedi(self):
        gercek = os.path.join(KOK, "yks_veritabani.db")
        once = os.path.getsize(gercek) if os.path.exists(gercek) else None
        self.calistir(self.ogrenci)
        sonra = os.path.getsize(gercek) if os.path.exists(gercek) else None
        self.assertEqual(once, sonra, "Testler gerçek veritabanını değiştirmemeli")

    def _admin_paneli_gorunuyor_mu(self, at):
        basliklar = [t.value for t in at.title]
        return any("YÖNETİCİ PANELİ" in str(b) for b in basliklar)

    def test_05_ogrenci_admin_panelini_goremez(self):
        at = self.calistir(self.ogrenci)
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertFalse(self._admin_paneli_gorunuyor_mu(at))

    def test_06_yonetici_panelini_gorur(self):
        at = self.calistir(self.koc)
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertTrue(self._admin_paneli_gorunuyor_mu(at))

    def test_07_sahte_admin_rolu_reddedilir(self):
        # Oturum rolü arayüzden 'admin' yapılsa bile DB rolü 'ogrenci' ise
        # yönetici paneli AÇILMAMALI (sunucu taraflı doğrulama).
        sahte = dict(self.ogrenci)
        sahte["rol"] = "admin"
        at = self.calistir(sahte)
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertFalse(self._admin_paneli_gorunuyor_mu(at))


if __name__ == "__main__":
    unittest.main(verbosity=2)
