"""v2.6 — Kamp kokpiti gerçek render testi (Streamlit AppTest).

Gerçek veritabanı kullanılmaz; geçici DB + test öğrencisi oluşturulur ve kamp
ekranı açılır. Amaç:
- İki ilerleme çubuğunun (MAKRO KONU + GÖREV İLERLEMESİ) çizilmesi,
- Mikro konu başlığının kartta görünmesi,
- `st.exception` oluşmaması.
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
from services.auth_service import hash_password  # noqa: E402

MAIN_PY = os.path.join(KOK, "main.py")


class KampKokpitiRenderTestleri(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from streamlit.testing.v1 import AppTest

        cls.AppTest = AppTest
        cls.dizin = tempfile.mkdtemp(prefix="karakoc_kamp_ui_")
        cls.db = os.path.join(cls.dizin, "kamp_ui.db")
        database.bootstrap_database(cls.db)
        conn = sqlite3.connect(cls.db)
        try:
            conn.execute(
                "INSERT INTO ogrenciler (tc_no, kullanici_adi, sifre_hash, ad,"
                " hedef_alan, sinif_seviyesi, rol, hesap_durumu, diploma_notu)"
                " VALUES ('33333333333', 'kamp_ogrenci', ?, 'Kamp Öğrenci',"
                " 'Sayısal', '12. Sınıf', 'ogrenci', 'Aktif', 88.0)",
                (hash_password("test123"),),
            )
            conn.commit()
            satir = conn.execute(
                "SELECT id, tc_no, kullanici_adi, ad, hedef_alan,"
                " sinif_seviyesi, rol, diploma_notu FROM ogrenciler"
                " WHERE kullanici_adi = 'kamp_ogrenci'"
            ).fetchone()
        finally:
            conn.close()
        cls.ogrenci = {
            "id": satir[0], "tc_no": satir[1], "kullanici_adi": satir[2],
            "ad": satir[3], "hedef_alan": satir[4], "sinif_seviyesi": satir[5],
            "alan_kilitli": 0, "rol": satir[6], "streak_count": 1,
            "diploma_notu": satir[7],
        }
        cls.onceki_env = os.environ.get("KARAKOC_DB_PATH")
        os.environ["KARAKOC_DB_PATH"] = cls.db

    @classmethod
    def tearDownClass(cls):
        database.bootstrap_onbellegini_temizle()
        if cls.onceki_env is None:
            os.environ.pop("KARAKOC_DB_PATH", None)
        else:
            os.environ["KARAKOC_DB_PATH"] = cls.onceki_env
        shutil.rmtree(cls.dizin, ignore_errors=True)

    def test_kamp_ekrani_iki_cubukla_render_edilir(self):
        database.bootstrap_onbellegini_temizle()
        at = self.AppTest.from_file(MAIN_PY, default_timeout=300)
        at.session_state["active_user"] = dict(self.ogrenci)
        at.session_state["kamp_aktif"] = True
        at.session_state["kamp_protokol_onay"] = True
        at.session_state["kamp_telafi_tamam"] = True
        at.run()

        self.assertFalse(at.exception, at.exception)
        metin = "\n".join(m.value for m in at.markdown)
        self.assertIn("MAKRO KONU", metin)
        self.assertIn("GÖREV İLERLEMESİ", metin)
        self.assertIn("kamp-makro-bar", metin)
        self.assertIn("kamp-gorev-bar", metin)
        self.assertIn("kamp-mikro-baslik", metin)


if __name__ == "__main__":
    unittest.main(verbosity=2)
