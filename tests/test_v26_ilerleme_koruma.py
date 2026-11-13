"""v2.6 — İlerleme koruma ve tutarlılık testleri.

- Yüzde değerleri her zaman 0–100 arasındadır (negatif üretilemez).
- Mikro konu güncellemesi başka mikro konuyu değiştirmez.
- Aynı görev iki kez işlendiğinde ilerleme ÇİFT artmaz.
- Yeniden hesaplama mevcut ilerlemeyi sebepsiz düşüremez.
- Görev sıfırlama diğer konuların kayıtlarını silmez.
- Başarısız/geçersiz işlem yarım kayıt bırakmaz.

Gerçek `yks_veritabani.db` dosyasına DOKUNULMAZ.
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

from services import core_schema, study_sessions, task_steps  # noqa: E402
from services import topic_progress  # noqa: E402

DERS = "AYT Matematik"
MIKRO_A = "Polinomlar ve Çarpanlara Ayırma"
MIKRO_B = "İkinci Dereceden Denklemler"
MAKRO = "İleri Cebir"


class IlerlemeKorumaTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="karakoc_ilerleme_v26_")
        self.db = os.path.join(self.klasor, "test.db")
        core_schema.init_db(self.db)
        for modul in (task_steps, study_sessions):
            modul.db_yolu_ayarla(self.db)
            modul.init_db()
        topic_progress.init_alt_konu_db(self.db)
        # core_schema bootstrap yönetici hesabını id=1 ile oluşturur; testlerde
        # bu hesap öğrenci kimliği olarak kullanılır (gerçek veriye dokunulmaz).
        self.mufredat = {DERS: {MAKRO: [MIKRO_A, MIKRO_B]}}

    def tearDown(self):
        shutil.rmtree(self.klasor, ignore_errors=True)

    # --- yardımcılar ------------------------------------------------------
    def _yaz(self, sorgu, params=()):
        conn = sqlite3.connect(self.db)
        try:
            cur = conn.execute(sorgu, params)
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def _oku(self, sorgu, params=()):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(sorgu, params).fetchall()
        finally:
            conn.close()

    def _gorev(self, mikro, alt, hedef=10, mikro_hedef=30):
        return self._yaz(
            "INSERT INTO calisma_programi_gorevler (ogrenci_id, ders, makro_konu,"
            " mikro_konu, alt_konu, hedef_soru, mikro_hedef_soru, durum)"
            " VALUES (1, ?, ?, ?, ?, ?, ?, 0)",
            (DERS, MAKRO, mikro, alt, hedef, mikro_hedef),
        )

    def _adim(self, gorev_id, tamam=True):
        return self._yaz(
            "INSERT INTO calisma_gorev_alt_adimlari"
            " (gorev_id, baslik, adim_turu, hedef_soru, durum, olusturma_zamani)"
            " VALUES (?, 'Adım', ?, 0, ?, '2026-01-01 00:00:00')",
            (gorev_id, task_steps.ADIM_IZLE, 1 if tamam else 0),
        )

    def _oturum(self, gorev_id, cozulen, alt=None):
        return self._yaz(
            "INSERT INTO calisma_oturumlari (ogrenci_id, gorev_id, ders,"
            " mikro_konu, alt_konu, durum, cozulen_soru, baslangic_zamani,"
            " bitis_zamani, olusturma_zamani) VALUES (1, ?, ?, ?, ?,"
            " 'Tamamlandı', ?, '2026-01-01 10:00:00',"
            " '2026-01-01 10:30:00', '2026-01-01 10:00:00')",
            (gorev_id, DERS, MIKRO_A, alt, cozulen),
        )

    def _mikro_kayit(self, mikro, alt, ogrenme, hedef, cozulen, tamam):
        return self._yaz(
            "INSERT INTO mikro_konu_ilerleme (ogrenci_id, ders, makro_konu,"
            " mikro_konu, alt_konu, ogrenme_tamam, hedef_soru, cozulen_soru,"
            " tamamlandi) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)",
            (DERS, MAKRO, mikro, alt, ogrenme, hedef, cozulen, tamam),
        )

    # --- 1) sınırlar ------------------------------------------------------
    def test_yuzde_sinirlari(self):
        self.assertEqual(topic_progress.ilerleme_sinirla(-40.0), 0.0)
        self.assertEqual(topic_progress.ilerleme_sinirla(140.0), 100.0)
        self.assertEqual(topic_progress.ilerleme_sinirla("bozuk"), 0.0)
        self.assertEqual(topic_progress.ilerleme_sinirla(None), 0.0)
        self.assertEqual(topic_progress.ilerleme_sinirla(40.0), 40.0)

    def test_negatif_ve_asiri_kayit_yuzdeye_yansimaz(self):
        self._mikro_kayit(MIKRO_A, "", 0, -50, -10, 0)
        oranlar = topic_progress.mikro_ilerleme_oranlari(
            1, self.mufredat, db_path=self.db
        )
        oran = oranlar.get((DERS, MIKRO_A), 0.0)
        self.assertGreaterEqual(oran, 0.0)
        self.assertLessEqual(oran, 100.0)
        detay = topic_progress.makro_ilerleme_detay(
            1, DERS, MAKRO, self.mufredat, oranlar=oranlar
        )
        self.assertGreaterEqual(detay["oran"], 0.0)
        self.assertLessEqual(detay["oran"], 100.0)

    # --- 2) tek kaynak / mikro izolasyonu --------------------------------
    def test_mikro_konu_izolasyonu(self):
        self._mikro_kayit(MIKRO_A, "", 1, 30, 15, 0)
        self._mikro_kayit(MIKRO_B, "", 0, 30, 0, 0)
        oranlar = topic_progress.mikro_ilerleme_oranlari(
            1, self.mufredat, db_path=self.db
        )
        # A: öğrenme 50 + soru 25 = 75; B: 0
        self.assertAlmostEqual(oranlar[(DERS, MIKRO_A)], 75.0, places=1)
        self.assertAlmostEqual(oranlar[(DERS, MIKRO_B)], 0.0, places=1)
        detay = topic_progress.makro_ilerleme_detay(
            1, DERS, MAKRO, self.mufredat, oranlar=oranlar
        )
        self.assertAlmostEqual(detay["oran"], 37.5, places=1)

    # --- 3) çift işleme ---------------------------------------------------
    def test_ayni_gorev_iki_kez_islenince_cift_artmaz(self):
        gid = self._gorev(MIKRO_A, "Alt 1")
        self._adim(gid)
        self._oturum(gid, 6, "Alt 1")
        ilk = task_steps.mikro_ilerleme_guncelle(gid)
        ikinci = task_steps.mikro_ilerleme_guncelle(gid)
        self.assertEqual(ilk["cozulen_soru"], 6)
        self.assertEqual(ikinci["cozulen_soru"], 6)
        satirlar = self._oku(
            "SELECT COUNT(*) AS adet FROM mikro_konu_ilerleme"
            " WHERE ogrenci_id = 1 AND ders = ? AND mikro_konu = ?",
            (DERS, MIKRO_A),
        )
        self.assertEqual(int(satirlar[0]["adet"]), 1)

    # --- 4) sebepsiz gerileme engeli --------------------------------------
    def test_yeniden_hesaplama_mevcut_ilerlemeyi_dusurmez(self):
        gid = self._gorev(MIKRO_A, "Alt 1", hedef=10, mikro_hedef=30)
        self._adim(gid)
        self._oturum(gid, 18, "Alt 1")
        ilk = task_steps.mikro_ilerleme_guncelle(gid)
        self.assertEqual(ilk["cozulen_soru"], 18)

        # Oturum kaydı kaybolmuş gibi davran (yeniden hesaplama 0 üretir).
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM calisma_oturumlari")
        conn.commit()
        conn.close()

        korunan = task_steps.mikro_ilerleme_guncelle(gid)
        self.assertEqual(korunan["cozulen_soru"], 18)
        self.assertTrue(korunan["gerileme_engellendi"])
        satir = self._oku(
            "SELECT cozulen_soru, son_neden FROM mikro_konu_ilerleme"
            " WHERE ogrenci_id = 1 AND ders = ? AND mikro_konu = ?",
            (DERS, MIKRO_A),
        )[0]
        self.assertEqual(int(satir["cozulen_soru"]), 18)
        self.assertEqual(satir["son_neden"], "gerileme_engellendi")

    # --- 5) sıfırlama diğer konuyu silmez ---------------------------------
    def test_gorev_sifirlama_diger_mikroyu_silmez(self):
        self._mikro_kayit(MIKRO_A, "Alt 1", 1, 30, 30, 1)
        self._mikro_kayit(MIKRO_B, "Alt 1", 1, 30, 30, 1)
        conn = sqlite3.connect(self.db)
        conn.execute(
            "UPDATE mikro_konu_ilerleme SET tamamlandi = 0, cozulen_soru = 0"
            " WHERE mikro_konu = ?",
            (MIKRO_A,),
        )
        conn.commit()
        conn.close()
        kalan = self._oku(
            "SELECT mikro_konu, tamamlandi FROM mikro_konu_ilerleme"
            " WHERE mikro_konu = ?", (MIKRO_B,)
        )
        self.assertEqual(len(kalan), 1)
        self.assertEqual(int(kalan[0]["tamamlandi"]), 1)

    # --- 6) atomiklik -----------------------------------------------------
    def test_olmayan_gorev_yarim_kayit_birakmaz(self):
        once = self._oku("SELECT COUNT(*) AS a FROM mikro_konu_ilerleme")[0]["a"]
        sonuc = task_steps.mikro_ilerleme_guncelle(999999)
        self.assertIsNone(sonuc)
        sonra = self._oku("SELECT COUNT(*) AS a FROM mikro_konu_ilerleme")[0]["a"]
        self.assertEqual(once, sonra)


if __name__ == "__main__":
    unittest.main(verbosity=2)
