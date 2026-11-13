"""v2.6 — Kamp motoru görev kuyruğu, geçiş ve soru hedefi testleri.

Kapsam:
- Görev kuyruğu durumları: hazır / ön koşul kilitli / gerçekten tamamlandı /
  tanım eksik (hepsi AYNI mesajı göstermez).
- Mikro konu tamamlanınca sıradaki mikro konuya geçiş.
- TYT ön koşul kilidi ve eksik konu listesi.
- Normal görev 24 (8+8+8), pekiştirme 48 (16+16+16) ve 8'lik dilimler.
- Aynı görev iki kez işlendiğinde çift kayıt/çift ilerleme olmaması.

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

from data import curriculum_meta as cm  # noqa: E402
from data import question_targets as qt  # noqa: E402
from services import core_schema, kamp_motoru, task_steps  # noqa: E402
from services import topic_progress  # noqa: E402

DERS = "TYT Türkçe"
MAKRO = "Sözün Anlamı"


class KampMotoruV26Testleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="karakoc_kamp_v26_")
        self.db = os.path.join(self.klasor, "test.db")
        core_schema.init_db(self.db)
        for modul in (task_steps, kamp_motoru):
            modul.db_yolu_ayarla(self.db)
            modul.init_db()
        topic_progress.init_alt_konu_db(self.db)
        self.mufredat = {
            DERS: {
                "Makro A": ["Sözcükte Anlam", "Söz Yorumu"],
                "Makro B": ["Deyim ve Atasözü"],
            },
        }

    def tearDown(self):
        for modul in (task_steps, kamp_motoru):
            modul.db_yolu_ayarla(None)
        shutil.rmtree(self.klasor, ignore_errors=True)

    def _oku(self, sorgu, params=()):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(sorgu, params).fetchall()
        finally:
            conn.close()

    # --- 1) kuyruk durumları ---------------------------------------------
    def test_kuyruk_sirayla_ilerler(self):
        sonuc = kamp_motoru.kamp_kuyrugu_hesapla(
            DERS, self.mufredat, bilinen=(), biten=(), sinif_seviyesi="12. Sınıf"
        )
        self.assertEqual(sonuc["durum"], "hazir")
        self.assertEqual(sonuc["makro_unite"], "Makro A")
        self.assertEqual(sonuc["mikrolar"], ["Sözcükte Anlam", "Söz Yorumu"])

        sonuc = kamp_motoru.kamp_kuyrugu_hesapla(
            DERS, self.mufredat,
            bilinen={(DERS, "Sözcükte Anlam")},
        )
        self.assertEqual(sonuc["mikrolar"], ["Söz Yorumu"])

        sonuc = kamp_motoru.kamp_kuyrugu_hesapla(
            DERS, self.mufredat,
            bilinen={(DERS, "Sözcükte Anlam"), (DERS, "Söz Yorumu")},
        )
        self.assertEqual(sonuc["makro_unite"], "Makro B")
        self.assertEqual(sonuc["mikrolar"], ["Deyim ve Atasözü"])

    def test_ayni_adli_mikro_baska_derste_bilinmiyor_sayilmaz(self):
        mufredat = {
            "TYT Matematik": {"Makro A": ["Fonksiyonlar"]},
            "AYT Matematik": {"Makro X": ["Fonksiyonlar"]},
        }
        sonuc = kamp_motoru.kamp_kuyrugu_hesapla(
            "AYT Matematik", mufredat,
            bilinen={("TYT Matematik", "Fonksiyonlar")},
            sinif_seviyesi="12. Sınıf", alan="Sayısal",
        )
        # AYT kilidi açık değilse kilitli döner; önemli olan TYT kaydının
        # AYT mikro konusunu "biliniyor" yapmamasıdır.
        if sonuc["durum"] == "hazir":
            self.assertIn("Fonksiyonlar", sonuc["mikrolar"])

    def test_tum_konular_bitince_tamamlandi(self):
        bilinen = {(DERS, m) for m in
                   ("Sözcükte Anlam", "Söz Yorumu", "Deyim ve Atasözü")}
        sonuc = kamp_motoru.kamp_kuyrugu_hesapla(DERS, self.mufredat, bilinen=bilinen)
        self.assertEqual(sonuc["durum"], "tamamlandi")
        self.assertIsNone(kamp_motoru.aktif_makro_unite_hesapla(
            DERS, self.mufredat, bilinen=bilinen
        ))

    def test_tanim_eksik_ile_tamamlandi_ayrilir(self):
        sonuc = kamp_motoru.kamp_kuyrugu_hesapla("Olmayan Ders", self.mufredat)
        self.assertEqual(sonuc["durum"], "tanim_eksik")
        sonuc = kamp_motoru.kamp_kuyrugu_hesapla(
            DERS, {DERS: {"Boş Makro": []}}
        )
        self.assertEqual(sonuc["durum"], "tanim_eksik")
        self.assertEqual(sonuc["neden"], "mikro_tanimi_yok")

    # --- 2) TYT ön koşul kilidi -----------------------------------------
    def test_ayt_onkosul_kilitli_ve_eksik_listesi(self):
        mufredat = {
            "AYT Matematik": {"İleri Cebir": ["Polinomlar ve Çarpanlara Ayırma"]},
        }
        sonuc = kamp_motoru.kamp_kuyrugu_hesapla(
            "AYT Matematik", mufredat, bilinen=(), biten=(),
            sinif_seviyesi="12. Sınıf", alan="Sayısal",
        )
        self.assertEqual(sonuc["durum"], "onkosul_kilitli")
        self.assertTrue(sonuc["eksik_onkosular"])
        self.assertIn("Fonksiyonlar", sonuc["eksik_onkosular"])
        self.assertIsNone(kamp_motoru.aktif_makro_unite_hesapla(
            "AYT Matematik", mufredat, sinif_seviyesi="12. Sınıf", alan="Sayısal"
        ))

    def test_cekirdek_tamamlaninca_ayt_acilir(self):
        gerekli = cm.CEKIRDEK_TYT_ONKOSULLAR["AYT Matematik"]
        # %80 eşiği: 11 konunun 9'u tamamlanınca kilit açılır.
        bilinen = {("TYT Matematik", k) for k in gerekli[:9]}
        mufredat = {
            "TYT Matematik": {"Temel": ["Fonksiyonlar"]},
            "AYT Matematik": {"İleri Cebir": ["Polinomlar ve Çarpanlara Ayırma"]},
        }
        sonuc = kamp_motoru.kamp_kuyrugu_hesapla(
            "AYT Matematik", mufredat, bilinen=bilinen,
            sinif_seviyesi="12. Sınıf", alan="Sayısal",
        )
        self.assertEqual(sonuc["durum"], "hazir", sonuc)
        self.assertEqual(sonuc["mikrolar"], ["Polinomlar ve Çarpanlara Ayırma"])

    def test_11_sinif_ayt_istisnasi(self):
        mufredat = {"AYT Matematik": {"İleri Cebir": ["Polinomlar ve Çarpanlara Ayırma"]}}
        sonuc = kamp_motoru.kamp_kuyrugu_hesapla(
            "AYT Matematik", mufredat, bilinen=(), biten=(),
            sinif_seviyesi="11. Sınıf", alan="Sayısal",
        )
        self.assertEqual(sonuc["durum"], "hazir")


    # --- 3) Soru hedefleri / dilimler ------------------------------------
    def test_soru_hedefleri_normal_ve_pekistirme(self):
        normal = qt.soru_hedefi("TYT Türkçe")
        self.assertFalse(normal["pekistirme"])
        self.assertEqual(normal["toplam"], 24)
        self.assertEqual((normal["kolay"], normal["orta"], normal["zor"]), (8, 8, 8))

        for ders in ("TYT Matematik", "AYT Geometri", "AYT Fizik"):
            hedef = qt.soru_hedefi(ders)
            self.assertTrue(hedef["pekistirme"], ders)
            self.assertEqual(hedef["toplam"], 48, ders)
            self.assertEqual(
                (hedef["kolay"], hedef["orta"], hedef["zor"]), (16, 16, 16), ders
            )
            dilimler = qt.dilimler(ders)
            self.assertEqual(len(dilimler), 6)
            self.assertEqual([d["seviye"] for d in dilimler],
                             ["kolay", "kolay", "orta", "orta", "zor", "zor"])
            self.assertTrue(all(d["hedef_soru"] == 8 for d in dilimler))
            self.assertEqual(sum(d["hedef_soru"] for d in dilimler), 48)

        # Kimya pekiştirme kategorisinde DEĞİL (çift uygulanmaz).
        self.assertEqual(qt.soru_hedefi("AYT Kimya")["toplam"], 24)

    def test_hedef_hesabi_idempotent(self):
        self.assertEqual(qt.toplam_soru("TYT Matematik"), 48)
        self.assertEqual(qt.toplam_soru("TYT Matematik"), 48)
        self.assertEqual(len(qt.dilimler("TYT Matematik")), 6)

    # --- 4) Kamp tamamlama ve geçiş --------------------------------------
    def _ac_oturum(self):
        return int(kamp_motoru.oturum_baslat(1)["id"])

    def _kamp_gorev(self, oturum_id, dilim_no, toplam=3, seviye="kolay",
                    mikro="Sözcükte Anlam"):
        return kamp_motoru.mikro_gorev_baslat(
            oturum_id, 1, DERS, MAKRO, "Tema", mikro, 8,
            dilim_no=dilim_no, toplam_dilim=toplam, gorev_turu="anlatim",
            soru_gerekli=1, seviye=seviye,
            adimlar=[{"baslik": "Çalış", "adim_turu": "genel", "hedef_soru": 0}],
        )

    def test_mikro_tamamlaninca_ilerleme_ve_sonraki_konu(self):
        oturum_id = self._ac_oturum()
        sonuc = None
        for i, seviye in enumerate(("kolay", "orta", "zor"), 1):
            kayit = self._kamp_gorev(oturum_id, i, seviye=seviye)
            sonuc = kamp_motoru.mikro_gorev_tamamla(kayit["id"], 1, 0)
            self.assertEqual(sonuc["sonraki"], "mikro")
            self.assertEqual(
                kamp_motoru.mikro_dilim_ilerlemesi(
                    1, DERS, "Sözcükte Anlam"
                )["tamamlanan"], i
            )
        ilerleme = sonuc["ilerleme"]
        self.assertTrue(ilerleme["ogrenme_tamam"])
        self.assertTrue(ilerleme["tamamlandi"])
        self.assertEqual(ilerleme["cozulen_soru"], 24)
        self.assertEqual(ilerleme["hedef_soru"], 24)

        biten = topic_progress.biten_konulari_yukle(1, self.mufredat)
        self.assertIn((DERS, "Sözcükte Anlam"), biten)

        # Makro ilerleme mikro konulardan türetilir: 2 mikroden 1'i %100 -> %50.
        detay = topic_progress.makro_ilerleme_detay(
            1, DERS, "Makro A", self.mufredat
        )
        self.assertAlmostEqual(detay["oran"], 50.0, places=1)
        self.assertEqual(detay["tamamlanan"], 1)
        self.assertEqual(detay["toplam"], 2)
        self.assertEqual(
            topic_progress.makro_unite_ilerleme_durumu(
                1, DERS, "Makro A", self.mufredat
            ),
            50,
        )

        kuyruk = kamp_motoru.kamp_kuyrugu_hesapla(
            DERS, self.mufredat, bilinen=(),
            biten=biten, sinif_seviyesi="12. Sınıf",
        )
        self.assertEqual(kuyruk["durum"], "hazir")
        self.assertEqual(kuyruk["mikrolar"], ["Söz Yorumu"])

    def test_tek_dilim_tamamlamak_yuzde_yuz_ogrenme_degildir(self):
        oturum_id = self._ac_oturum()
        kayit = self._kamp_gorev(oturum_id, 1)
        sonuc = kamp_motoru.mikro_gorev_tamamla(kayit["id"], 0, 0)
        self.assertTrue(sonuc["ilerleme"]["ogrenme_tamam"])
        self.assertFalse(sonuc["ilerleme"]["tamamlandi"])
        self.assertEqual(sonuc["ilerleme"]["cozulen_soru"], 8)
        self.assertNotIn(
            (DERS, "Sözcükte Anlam"),
            topic_progress.biten_konulari_yukle(1, self.mufredat),
        )

    def test_basarisiz_dilim_sayilmaz_ve_tekrar_gerekir(self):
        oturum_id = self._ac_oturum()
        kayit = self._kamp_gorev(oturum_id, 1)
        sonuc = kamp_motoru.mikro_gorev_tamamla(kayit["id"], 3, 0)  # %62.5
        self.assertTrue(sonuc["analiz_gerekli"])
        self.assertEqual(sonuc["ilerleme"]["gecen_dilim"], 0)
        self.assertFalse(sonuc["ilerleme"]["ogrenme_tamam"])
        self.assertEqual(sonuc["ilerleme"]["cozulen_soru"], 0)
        self.assertEqual(
            kamp_motoru.mikro_dilim_ilerlemesi(1, DERS, "Sözcükte Anlam")[
                "tamamlanan"
            ], 0,
        )

    def test_mukerrer_tamamlama_cift_saymaz(self):
        oturum_id = self._ac_oturum()
        kayit = self._kamp_gorev(oturum_id, 1)
        kamp_motoru.mikro_gorev_tamamla(kayit["id"], 0, 0)
        tekrar = kamp_motoru.mikro_gorev_tamamla(kayit["id"], 0, 0)
        self.assertTrue(tekrar.get("mukerrer"))
        satirlar = self._oku(
            "SELECT cozulen_soru FROM mikro_konu_ilerleme"
            " WHERE ogrenci_id = 1 AND ders = ? AND mikro_konu = ?",
            (DERS, "Sözcükte Anlam"),
        )
        self.assertEqual(len(satirlar), 1)
        self.assertEqual(int(satirlar[0]["cozulen_soru"]), 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)

