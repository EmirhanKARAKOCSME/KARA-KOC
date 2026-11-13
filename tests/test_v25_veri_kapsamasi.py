"""v2.5 — Müfredat/mikro konu kapsamı, ön koşul ağı ve 11. sınıf testleri.

Doğrulananlar:
- Maarif 9/10, Maarif 11, klasik TYT, AYT Sayısal/EA/Sözel ve YDT
  konularının TAMAMI için mikro konu karşılığı var.
- Mikro konu listeleri boş veya mükerrer değil.
- Her mikro konu için çalışma süresi tanımlı.
- Ön koşul ağında kopuk bağlantı ve döngü yok.
- Eski/alternatif adlar kanonik konulara çözülüyor.
- 11. sınıf Maarif havuzu klasik AYT'den ayrı seçiliyor.

Çalıştırma:
    python tests/test_v25_veri_kapsamasi.py
    python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(TEST_KOK)
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from data.curriculum import mufredat_klasik, mufredat_maarif_9  # noqa: E402
from data.curriculum_aliases import KONU_ALIASLARI, kanonik_konular  # noqa: E402
from data.curriculum_maarif_11 import mufredat_maarif_11  # noqa: E402
from data.prerequisites import ON_KOSULLAR  # noqa: E402
from data.subtopics import MIKRO_ALT_KONULAR  # noqa: E402
from data.weights_and_times import KONU_SURELERI_DK  # noqa: E402


def _mikrolar(mufredat):
    """Her derinlikteki `... -> [mikro konu]` listelerini toplar.

    Klasik AYT `alan -> ders -> ünite -> liste` biçiminde birkaç kat
    iç içe olduğu için sabit derinlik yerine genel özyineleme kullanılır.
    Dönen üçlü: (ilk anahtar, son anahtar, mikro konu).
    """
    sonuc = []

    def gez(dugum, yol):
        if isinstance(dugum, list):
            for m in dugum:
                if isinstance(m, str):
                    sonuc.append(
                        (yol[0] if yol else "", yol[-1] if yol else "", m)
                    )
            return
        if isinstance(dugum, dict):
            for anahtar, deger in dugum.items():
                gez(deger, yol + [anahtar])

    gez(mufredat or {}, [])
    return sonuc


def _tum_gercek_mikrolar():
    gercek = set()
    for mufredat in (mufredat_maarif_9, mufredat_maarif_11):
        gercek |= {m for _, _, m in _mikrolar(mufredat)}
    for dersler in mufredat_klasik.values():
        gercek |= {m for _, _, m in _mikrolar(dersler)}
    return gercek


class MikroKapsamaTestleri(unittest.TestCase):
    def _kapsam(self, ad, mufredat):
        eksik = [m for _, _, m in _mikrolar(mufredat) if m not in MIKRO_ALT_KONULAR]
        self.assertEqual(eksik, [], "%s için eksik mikro konu: %s" % (ad, eksik))

    def test_maarif_9_tam(self):
        self._kapsam("Maarif 9/10", mufredat_maarif_9)

    def test_maarif_11_tam(self):
        self._kapsam("Maarif 11", mufredat_maarif_11)

    def test_klasik_tam(self):
        for alan, dersler in mufredat_klasik.items():
            self._kapsam("klasik:%s" % alan, dersler)

    def test_mikro_listeleri_bos_degil_ve_mukerrer_degil(self):
        for mikro, altlar in MIKRO_ALT_KONULAR.items():
            self.assertTrue(altlar, "%s için alt başlık yok" % mikro)
            self.assertEqual(
                len(altlar), len(set(altlar)),
                "%s içinde mükerrer alt başlık var" % mikro,
            )

    def test_her_mikro_konunun_suresi_var(self):
        eksik = [m for m in MIKRO_ALT_KONULAR if m not in KONU_SURELERI_DK]
        self.assertEqual(eksik, [], "Süresi tanımsız mikro konu: %s" % eksik)

    def test_hucre_alias_suresi(self):
        self.assertEqual(
            KONU_SURELERI_DK.get("Hücre Yapısı ve Organeller"),
            KONU_SURELERI_DK.get("Hücre Yapısı, Organeller ve Çekirdek"),
        )


class OnKosulTestleri(unittest.TestCase):
    def _cozum(self, ad, gercek):
        return [c for c in kanonik_konular(ad) if c in gercek]

    def test_kopuk_baglanti_yok(self):
        gercek = _tum_gercek_mikrolar()
        kopuk = []
        for anahtar, kural in ON_KOSULLAR.items():
            if not self._cozum(anahtar, gercek):
                kopuk.append(("ANAHTAR", anahtar))
            for ok in kural.get("on_kosul", []):
                if not self._cozum(ok, gercek):
                    kopuk.append(("ONKOSUL", anahtar, ok))
        self.assertEqual(kopuk, [], "Kopuk ön koşul: %s" % kopuk)

    def test_dongu_yok(self):
        gercek = _tum_gercek_mikrolar()
        grafik = {}
        for anahtar, kural in ON_KOSULLAR.items():
            hedef = []
            for ok in kural.get("on_kosul", []):
                hedef.extend(self._cozum(ok, gercek) or [ok])
            grafik[anahtar] = hedef
        WHITE, GRAY, BLACK = 0, 1, 2
        renk = {}

        def ziyaret(dugum, yol):
            renk[dugum] = GRAY
            for komsu in grafik.get(dugum, []):
                if renk.get(komsu, WHITE) == GRAY:
                    return yol + [dugum, komsu]
                if renk.get(komsu, WHITE) == WHITE:
                    sonuc = ziyaret(komsu, yol + [dugum])
                    if sonuc:
                        return sonuc
            renk[dugum] = BLACK
            return None

        for dugum in grafik:
            if renk.get(dugum, WHITE) == WHITE:
                self.assertIsNone(ziyaret(dugum, []), "Ön koşul döngüsü var")

    def test_alias_cozum_kanonik(self):
        gercek = _tum_gercek_mikrolar()
        for eski, kanonikler in KONU_ALIASLARI.items():
            for k in kanonikler:
                self.assertIn(k, gercek, "%s -> %s müfredatta yok" % (eski, k))


class OnBirinciSinifTestleri(unittest.TestCase):
    def test_11_havuzu_ayri(self):
        from services.topic_progress import build_student_curriculum

        self.assertEqual(
            build_student_curriculum("11. Sınıf", "Sayısal"), mufredat_maarif_11
        )

    def test_11_havuz_suz_korunuyor(self):
        from data import curriculum_meta as cm

        havuz = cm.havuz_suz(mufredat_maarif_11, "11. Sınıf", "Sayısal")
        self.assertEqual(set(havuz), set(mufredat_maarif_11))


if __name__ == "__main__":
    unittest.main(verbosity=2)

