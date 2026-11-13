"""v2.5 — Kamp motoru pedagojik görev ve sonuç testleri.

Kapsam:
- İlk kez öğrenilen konu / ezber / pekiştirme / yalnızca tekrar planları.
- Soru hedefi olan ve olmayan görevler.
- %75 ve üzeri / altı başarı; yanlış+boş hedefi aşamaz.
- Mükerrer tamamlama (sayfa yenilemesi / çift tıklama) kayıt şişirmez.
- Atomik 10–15 dilim korunur.

Tüm testler `tempfile` tabanlı izole SQLite üzerinde çalışır; gerçek
`yks_veritabani.db` dosyasına dokunulmaz.
"""
import os
import shutil
import sys
import tempfile
import unittest

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(TEST_KOK)
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from services import kamp_motoru  # noqa: E402


class _KampTemel(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="karakoc_v25_")
        self.db_yolu = os.path.join(self.klasor, "test.db")
        kamp_motoru.db_yolu_ayarla(self.db_yolu)
        kamp_motoru.init_db()
        self.oturum = kamp_motoru.oturum_baslat(1, tema="Kozmik Lacivert")
        self.oturum_id = self.oturum["id"]

    def tearDown(self):
        kamp_motoru.db_yolu_ayarla(None)
        shutil.rmtree(self.klasor, ignore_errors=True)

    def _baslat(self, hedef=15, **kw):
        return kamp_motoru.mikro_gorev_baslat(
            self.oturum_id, 1, kw.get("ders", "TYT Matematik"), "Ünite",
            "Mikro", "Mikro", hedef,
            pedagoji_turu=kw.get("pedagoji_turu"),
            gorev_turu=kw.get("gorev_turu"),
            adimlar=kw.get("adimlar"),
            soru_gerekli=kw.get("soru_gerekli", 1),
        )


class GorevPlaniTestleri(_KampTemel):
    def test_pekistirme_plani(self):
        plan = kamp_motoru.gorev_plani_uret("TYT Matematik", "Ünite", "Mikro", 15)
        self.assertEqual(plan["pedagoji_turu"], "Pekiştirme")
        self.assertEqual(plan["soru_gerekli"], 1)
        turler = [a["adim_turu"] for a in plan["adimlar"]]
        self.assertIn("izle", turler)
        self.assertIn("not", turler)
        self.assertIn("soru", turler)

    def test_ezber_plani(self):
        plan = kamp_motoru.gorev_plani_uret("TYT Biyoloji", "Ünite", "Mikro", 15)
        self.assertEqual(plan["pedagoji_turu"], "Ezber")
        turler = [a["adim_turu"] for a in plan["adimlar"]]
        self.assertIn("izle", turler)
        self.assertIn("not", turler)

    def test_tekrar_plani_soru_yok(self):
        plan = kamp_motoru.tekrar_gorev_plani("TYT Matematik", "Ünite", "Mikro")
        self.assertEqual(plan["soru_gerekli"], 0)
        self.assertEqual(plan["hedef_soru"], 0)
        self.assertEqual(plan["gorev_turu"], "tekrar")

    def test_dilim_10_15(self):
        dilimler = kamp_motoru.mikro_dilimle(30)
        for d in dilimler:
            self.assertGreaterEqual(d["hedef_soru"], 10)
            self.assertLessEqual(d["hedef_soru"], 15)

    def test_basari_formulu(self):
        self.assertEqual(kamp_motoru.basari_orani(15, 3, 0), 80.0)
        self.assertEqual(kamp_motoru.basari_orani(15, 0, 0), 100.0)


class SonucTestleri(_KampTemel):
    def test_75_ve_uzeri(self):
        k = self._baslat(hedef=15)
        sonuc = kamp_motoru.mikro_gorev_tamamla(k["id"], 3, 0)  # %80
        self.assertFalse(sonuc["analiz_gerekli"])
        self.assertEqual(sonuc["sonraki"], "mikro")
        self.assertEqual(sonuc["basari_orani"], 80.0)

    def test_75_alti(self):
        k = self._baslat(hedef=15)
        sonuc = kamp_motoru.mikro_gorev_tamamla(k["id"], 4, 0)  # %73.3
        self.assertTrue(sonuc["analiz_gerekli"])
        self.assertEqual(sonuc["sonraki"], "analiz")

    def test_yanlis_bos_hedefi_asmaz(self):
        k = self._baslat(hedef=15)
        sonuc = kamp_motoru.mikro_gorev_tamamla(k["id"], 20, 20)
        self.assertLessEqual(
            int(sonuc["yanlis_sayisi"]) + int(sonuc["bos_sayisi"]), 15
        )

    def test_mukerrer_tamamlama(self):
        k = self._baslat(hedef=15)
        kamp_motoru.mikro_gorev_tamamla(k["id"], 0, 0)
        onceki = kamp_motoru.oturum_getir(self.oturum_id)
        tekrar = kamp_motoru.mikro_gorev_tamamla(k["id"], 0, 0)
        sonraki = kamp_motoru.oturum_getir(self.oturum_id)
        self.assertTrue(tekrar.get("mukerrer"))
        self.assertEqual(
            onceki["toplam_soru"] + onceki["toplam_sure_sn"],
            sonraki["toplam_soru"] + sonraki["toplam_sure_sn"],
        )

    def test_soru_gerekmeyen_gorev(self):
        k = self._baslat(hedef=1, soru_gerekli=0)
        sonuc = kamp_motoru.mikro_gorev_tamamla(k["id"])
        self.assertEqual(sonuc["basari_orani"], 100.0)
        ozet = kamp_motoru.oturum_getir(self.oturum_id)
        self.assertEqual(int(ozet.get("toplam_soru") or 0), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
