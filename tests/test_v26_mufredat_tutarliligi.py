"""v2.6 — Müfredat / mikro konu / ön koşul bütünlüğü testleri.

Veri DEĞİŞTİRMEZ; yalnızca mevcut müfredatın yapısal tutarlılığını doğrular.
"""
import os
import sys
import unittest

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(TEST_KOK)
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from data.curriculum_meta import mufredat_denetimi  # noqa: E402
from services.topic_progress import build_student_curriculum  # noqa: E402


class MufredatTutarliligiTestleri(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rapor = mufredat_denetimi()

    def test_yapisal_sorun_yok(self):
        self.assertEqual(self.rapor["sorun_sayisi"], 0, self.rapor)
        self.assertEqual(self.rapor["eksik_alt_konu"], [])
        self.assertEqual(self.rapor["mukerrer_mikro"], [])
        self.assertEqual(self.rapor["onkosul_hedefi_yok"], [])
        self.assertEqual(self.rapor["onkosul_ders_yok"], [])
        self.assertEqual(self.rapor["cekirdek_eslesmeyen"], [])

    def test_havuz_boyutlari_korunur(self):
        havuzlar = self.rapor["havuzlar"]
        self.assertEqual(havuzlar["maarif9"]["ders_sayisi"], 8)
        self.assertEqual(havuzlar["maarif11"]["ders_sayisi"], 9)
        self.assertEqual(havuzlar["klasik"]["ders_sayisi"], 22)
        self.assertEqual(havuzlar["maarif9"]["mikro_sayisi"], 88)
        self.assertEqual(havuzlar["maarif11"]["mikro_sayisi"], 125)
        self.assertEqual(havuzlar["klasik"]["mikro_sayisi"], 221)

    def test_ayt_matematik_ve_geometri_tam_kapsama(self):
        kapsama = self.rapor["ayt_kapsama"]
        self.assertEqual(kapsama["AYT Matematik"]["oran"], 1.0)
        self.assertEqual(kapsama["AYT Geometri"]["oran"], 1.0)

    def test_sinif_havuzlari_bos_degil_ve_mikrolari_tutarli(self):
        for sinif, alan in (
            ("9. Sınıf", "Sayısal"),
            ("10. Sınıf", "Sayısal"),
            ("11. Sınıf", "Sayısal"),
            ("12. Sınıf", "Sayısal"),
            ("Mezun", "Eşit Ağırlık"),
            ("12. Sınıf", "Dil"),
        ):
            havuz = build_student_curriculum(sinif, alan)
            self.assertTrue(havuz, "%s/%s boş" % (sinif, alan))
            for ders, makro in havuz.items():
                self.assertIsInstance(makro, dict)
                for mikro_listesi in makro.values():
                    self.assertIsInstance(mikro_listesi, list)
                    self.assertTrue(all(mikro_listesi))


if __name__ == "__main__":
    unittest.main(verbosity=2)
