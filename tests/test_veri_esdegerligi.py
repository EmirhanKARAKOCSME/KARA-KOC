"""Refactoring veri eşdeğerliği testleri (FAZ A kabul kriterleri).

Veriler `main.py` içindeyken hesaplanan parmak izleri (md5) ile `data/`
paketindeki değerlerin **birebir aynı** olduğunu doğrular. Parmak izleri
refactoring öncesi dosyadan alınmıştır: kazara yapılan bir veri değişikliği
(konu kaybı, süre/ağırlık değişimi, sıra bozulması) bu testi kırar.

Veri bilinçli olarak güncellenirse parmak izi sabitleri de güncellenir.

Çalıştırma:
    python tests/test_veri_esdegerligi.py
    python -m unittest discover -s tests -v
"""
import hashlib
import os
import sys
import unittest

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(TEST_KOK)
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from data import prerequisites  # noqa: E402
from data.curriculum import mufredat_klasik, mufredat_maarif_9  # noqa: E402
from data.pedagogy import get_konu_pedagoji_turu  # noqa: E402
from data.prerequisites import ON_KOSULLAR  # noqa: E402
from data.subtopics import (  # noqa: E402
    MIKRO_ALT_KONULAR,
    _ALT_AYT_SAYISAL,
    _ALT_TYT,
)
from data.weights_and_times import (  # noqa: E402
    KONU_SURELERI_DK,
    SINIF_SEVIYE_SKORU,
    SORU_AGIRLIKLARI,
)

# Refactoring ÖNCESİ (main.py içindeki) verilerden alınan parmak izleri.
PARMAK_IZLERI = {
    "mufredat_klasik": "ccddd37d",
    "mufredat_maarif_9": "4b37301e",
    "MIKRO_ALT_KONULAR": "0a7b101f",
    "_ALT_TYT": "e0e14465",
    "_ALT_AYT_SAYISAL": "530f0b8c",
    "ON_KOSULLAR": "77d20001",
    "KONU_SURELERI_DK": "59eeb572",
    "SORU_AGIRLIKLARI": "9044afb4",
    "SINIF_SEVIYE_SKORU": "0dbb7bf1",
}


def parmak_izi(deger):
    return hashlib.md5(repr(deger).encode("utf-8")).hexdigest()[:8]


class VeriEsdegerligiTestleri(unittest.TestCase):
    def test_mufredat_parmak_izleri_ayni(self):
        """Müfredat hiyerarşileri eski dosyayla birebir aynı."""
        self.assertEqual(parmak_izi(mufredat_klasik), PARMAK_IZLERI["mufredat_klasik"])
        self.assertEqual(
            parmak_izi(mufredat_maarif_9), PARMAK_IZLERI["mufredat_maarif_9"]
        )

    def test_alt_konu_ve_mikro_konu_parmak_izleri_ayni(self):
        """Alt konu/mikro konu kaydı kaybolmadı, sırası bozulmadı."""
        self.assertEqual(parmak_izi(_ALT_TYT), PARMAK_IZLERI["_ALT_TYT"])
        self.assertEqual(
            parmak_izi(_ALT_AYT_SAYISAL), PARMAK_IZLERI["_ALT_AYT_SAYISAL"]
        )
        self.assertEqual(
            parmak_izi(MIKRO_ALT_KONULAR), PARMAK_IZLERI["MIKRO_ALT_KONULAR"]
        )

    def test_mikro_alt_konu_yapisi_korunuyor(self):
        """MIKRO_ALT_KONULAR: anahtar=mikro konu, değer=alt başlık listesi."""
        self.assertTrue(MIKRO_ALT_KONULAR)
        for mikro, altlar in MIKRO_ALT_KONULAR.items():
            self.assertIsInstance(mikro, str)
            self.assertIsInstance(altlar, list)
            self.assertTrue(altlar, "%s için alt başlık yok" % mikro)

    def test_sure_ve_agirlik_parmak_izleri_ayni(self):
        """Konu süreleri, soru ağırlıkları ve sınıf seviye skorları değişmedi."""
        self.assertEqual(
            parmak_izi(KONU_SURELERI_DK), PARMAK_IZLERI["KONU_SURELERI_DK"]
        )
        self.assertEqual(
            parmak_izi(SORU_AGIRLIKLARI), PARMAK_IZLERI["SORU_AGIRLIKLARI"]
        )
        self.assertEqual(
            parmak_izi(SINIF_SEVIYE_SKORU), PARMAK_IZLERI["SINIF_SEVIYE_SKORU"]
        )

    def test_on_kosul_birlesimi_ayni(self):
        """{**EK, **TEMEL} sonucu tek veri yapısında birebir korundu."""
        self.assertEqual(parmak_izi(ON_KOSULLAR), PARMAK_IZLERI["ON_KOSULLAR"])
        self.assertEqual(len(ON_KOSULLAR), 70)

    def test_on_kosul_ek_artik_yok(self):
        """Birleşik veri tek yapıya taşındı; `ON_KOSULLAR_EK` kaldırıldı."""
        self.assertFalse(hasattr(prerequisites, "ON_KOSULLAR_EK"))

    def test_on_kosul_oncelik_kurali(self):
        """Çakışan kayıtlarda TEMEL sözlük kazanır (ders alanı dolu olan)."""
        dersli = [ad for ad, kayit in ON_KOSULLAR.items() if kayit.get("ders")]
        self.assertTrue(dersli, "Ön koşul kayıtlarında ders alanı bulunmalı")
        for ad in dersli:
            self.assertIn("on_kosul", ON_KOSULLAR[ad], ad)
            self.assertIn("min_sinif", ON_KOSULLAR[ad], ad)

    def test_pedagoji_turu_calisiyor(self):
        """Pedagoji yardımcısı veri modülünden aynı sözleşmeyle çalışıyor."""
        for ders in ("TYT Türkçe", "AYT Matematik", "Bilinmeyen Ders"):
            self.assertIsInstance(get_konu_pedagoji_turu(ders), str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
