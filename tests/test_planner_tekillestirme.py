"""Görev üretiminde tekilleştirme (deduplication) ve "Temel Eksik" birleştirme.

Kapsam:

- **Günlük tekilleştirme:** aynı gün içinde aynı ders + aynı ANA KONU için
  ikinci bir görev kartı üretilmez (`plan_uret`).
- **Temel Eksik birleştirme:** bir konunun birden çok eksik ön koşulu AYRI
  kartlara bölünmez; tek kartın açıklamasında listelenir
  ("Polinomlar - Eksikler: Fonksiyonlar, Çarpanlara Ayırma").
- **Günlük rutin slotu:** "Günlük Paragraf" gibi rutinler gün başına
  `max_daily_limit = 1` slotla sınırlıdır; önceki programdan devretmez.
- `gunluk_tekillestir()` / `temel_eksik_ayir()` yardımcılarının birim
  davranışı.

Testler yalnızca bellekte çalışır (SQLite/tekrar entegrasyonu kapalı); gerçek
`yks_veritabani.db` dosyasına dokunulmaz.

Çalıştırma:
    python tests/test_planner_tekillestirme.py
    python -m unittest discover -s tests -v
"""
import os
import sys
import unittest
from datetime import date

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(TEST_KOK)
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from services import planner  # noqa: E402

BAS = date(2026, 11, 9)  # Pazartesi
ANA_KONU = "Sayılar"
DERS = "TYT Matematik"
ALTLAR = ["Doğal Sayılar", "Tam Sayılar"]


class PlannerTekillestirmeTestleri(unittest.TestCase):
    # -- yardımcılar ---------------------------------------------------------
    def _baglam(self, **ek):
        baglam = {
            "ogrenci_id": 1,
            "baslangic": BAS,
            "gun_sayisi": 7,
            "musaitlik": {gun: 240 for gun in range(1, 8)},
            "mufredat": {DERS: {"Temel Kavramlar": [ANA_KONU]}},
            "mikro_alt": {ANA_KONU: list(ALTLAR)},
            "konu_sureleri": {ANA_KONU: 40},
            "soru_agirliklari": {},
            "on_kosullar": {},
            "mikro_cozulen": {},
            "onceki_gorevler": [],
            "paragraf_soru": 0,
            "pedagoji": {},
            "tamamlanan_altlar": set(),
            "alarm_konular": [],
            # Tekrar havuzu bu testlerin kapsamı dışında: veritabanı okumasın.
            "tekrar_entegrasyonu": False,
            # v2.3: özgün (legacy) planlama davranışını doğrular.
            "legacy_mod": True,
        }
        baglam.update(ek)
        return baglam

    def _konu_gorevleri(self, sonuc, ana=ANA_KONU):
        return [g for g in sonuc["gorevler"] if g.get("mikro_konu") == ana]

    # ------------------------------------------------------------------
    # 01/02 - Aynı gün + aynı ders + aynı ana konu tek kart
    # ------------------------------------------------------------------
    def test_01_ayni_gun_ayni_ana_konu_tek_kart(self):
        # Yalnızca pazartesi açık ve kapasite çok geniş: birden çok mikro konu
        # AYNI güne sığabilirdi. Tekilleştirme bunu engellemeli.
        musaitlik = {1: 600, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}
        sonuc = planner.plan_uret(self._baglam(musaitlik=musaitlik))
        kartlar = self._konu_gorevleri(sonuc)
        self.assertEqual(len(kartlar), 1, "Aynı gün aynı ana konu tek kart olmalı")
        self.assertEqual(kartlar[0]["tarih"], BAS.isoformat())
        # Sığmayan mikro konular sonraki plana devreder (kaybolmaz).
        self.assertIn("kapasitesi", " ".join(sonuc["uyarilar"]))

    def test_02_hafta_boyunca_ana_konu_gunde_tek(self):
        sonuc = planner.plan_uret(self._baglam())
        gorulen = {}
        for gorev in sonuc["gorevler"]:
            anahtar = (gorev["tarih"], gorev["ders"], gorev["mikro_konu"])
            gorulen[anahtar] = gorulen.get(anahtar, 0) + 1
        tekrarlanan = [a for a, adet in gorulen.items() if adet > 1]
        self.assertEqual(tekrarlanan, [], "Aynı gün/konu tekrarı olmamalı")

    # ------------------------------------------------------------------
    # 03/04 - Temel Eksik: tek kart + birleşik açıklama
    # ------------------------------------------------------------------
    def test_03_temel_eksik_tek_kartta_birlesir(self):
        alarmlar = [
            {
                "ders": DERS,
                "konu": "%s - Eksikler: Doğal Sayılar" % ANA_KONU,
                "hedef_konu": ANA_KONU,
                "eksikler": ["Doğal Sayılar"],
            },
            {
                "ders": DERS,
                "konu": "%s - Eksikler: Tam Sayılar" % ANA_KONU,
                "hedef_konu": ANA_KONU,
                "eksikler": ["Tam Sayılar"],
            },
        ]
        sonuc = planner.plan_uret(self._baglam(alarm_konular=alarmlar))
        kartlar = [g for g in self._konu_gorevleri(sonuc) if g.get("eksik_konular")]
        self.assertTrue(kartlar, "Eksik kartı üretilmeli")
        gunler = [k["tarih"] for k in kartlar]
        self.assertEqual(len(gunler), len(set(gunler)), "Günde tek eksik kartı")
        for kart in kartlar:
            # Tek kart, birleşik liste: ön koşul başına ayrı kart YOK.
            self.assertEqual(
                kart.get("eksik_konular"), ["Doğal Sayılar", "Tam Sayılar"]
            )
            self.assertIn(
                "%s - Eksikler: Doğal Sayılar, Tam Sayılar" % ANA_KONU,
                kart["gorev_tanimi"],
            )
            self.assertIsNone(
                kart.get("alt_konu"), "Eksik kartı mikro konuya bölünmez"
            )

    def test_04_eski_temel_eksik_bicimide_birlesir(self):
        # Eski biçim: "Konu (Temel Eksik: X)" -> yine tek kart, birleşik liste.
        alarmlar = [
            {"ders": DERS, "konu": "%s (Temel Eksik: Doğal Sayılar)" % ANA_KONU},
            {"ders": DERS, "konu": "%s (Temel Eksik: Tam Sayılar)" % ANA_KONU},
        ]
        sonuc = planner.plan_uret(self._baglam(alarm_konular=alarmlar))
        kartlar = [g for g in self._konu_gorevleri(sonuc) if g.get("eksik_konular")]
        self.assertTrue(kartlar, "Eski biçim de birleşik karta dönüşmeli")
        for kart in kartlar:
            self.assertEqual(
                kart.get("eksik_konular"), ["Doğal Sayılar", "Tam Sayılar"]
            )
            self.assertIn("Eksikler: Doğal Sayılar, Tam Sayılar", kart["gorev_tanimi"])

    # ------------------------------------------------------------------
    # 05/06 - Günlük rutin: gün başına tek slot
    # ------------------------------------------------------------------
    def test_05_gunluk_paragraf_gunde_tek_slot(self):
        sonuc = planner.plan_uret(self._baglam(paragraf_soru=20))
        paragraflar = [
            g for g in sonuc["gorevler"] if g["mikro_konu"] == "Günlük Paragraf"
        ]
        self.assertEqual(len(paragraflar), 7, "Her gün tek paragraf slotu")
        tarihler = [g["tarih"] for g in paragraflar]
        self.assertEqual(len(tarihler), len(set(tarihler)), "Gün başına tek paragraf")

    def test_06_devreden_paragraf_ikinci_kart_uretmez(self):
        devir = [
            {
                "id": 7,
                "ders": "TYT Türkçe",
                "makro_konu": "Paragraf",
                "mikro_konu": "Günlük Paragraf",
                "alt_konu": None,
                "gorev_tanimi": "📖 Günlük paragraf: 20 soru çöz.",
                "hedef_soru": 20,
                "mikro_hedef_soru": 20,
                "pedagoji_turu": "Ezber",
                "durum": 0,
                "tarih": BAS.isoformat(),
            }
        ]
        sonuc = planner.plan_uret(
            self._baglam(paragraf_soru=20, onceki_gorevler=devir)
        )
        paragraflar = [
            g for g in sonuc["gorevler"] if g["mikro_konu"] == "Günlük Paragraf"
        ]
        self.assertEqual(len(paragraflar), 7, "Devir paragraf kartı ÜRETİLMEMELİ")



    # ------------------------------------------------------------------
    # 07-10 - Yardımcı fonksiyonlar
    # ------------------------------------------------------------------
    def test_07_rutin_gunluk_limiti(self):
        self.assertEqual(planner.rutin_gunluk_limiti("Günlük Paragraf"), 1)
        self.assertEqual(
            planner.rutin_gunluk_limiti("Günlük Paragraf", "TYT Türkçe"), 1
        )
        self.assertIsNone(planner.rutin_gunluk_limiti(ANA_KONU, DERS))

    def test_08_gunluk_tekillestir_tekrarlari_ayiklar(self):
        gorevler = [
            {"tarih": "2026-11-09", "ders": DERS, "mikro_konu": ANA_KONU,
             "alt_konu": "Doğal Sayılar", "pedagoji_turu": "Pekiştirme"},
            # Birebir tekrar -> atılır.
            {"tarih": "2026-11-09", "ders": DERS, "mikro_konu": ANA_KONU,
             "alt_konu": "Doğal Sayılar", "pedagoji_turu": "Pekiştirme"},
            # Aynı gün aynı ana konu -> atılır.
            {"tarih": "2026-11-09", "ders": DERS, "mikro_konu": ANA_KONU,
             "alt_konu": "Tam Sayılar", "pedagoji_turu": "Pekiştirme"},
            # Farklı gün -> korunur.
            {"tarih": "2026-11-10", "ders": DERS, "mikro_konu": ANA_KONU,
             "alt_konu": "Tam Sayılar", "pedagoji_turu": "Pekiştirme"},
        ]
        sonuc = planner.gunluk_tekillestir(gorevler)
        self.assertEqual(len(sonuc), 2)
        self.assertEqual([g["tarih"] for g in sonuc], ["2026-11-09", "2026-11-10"])
        # Mikro konu bazlı bölünmüş kartlar (fallback motoru) korunur.
        korunan = planner.gunluk_tekillestir(gorevler, ana_konu_tekillestir=False)
        self.assertEqual(len(korunan), 3)

    def test_09_rutin_gunluk_tekillestir_slotu(self):
        paragraf = {
            "tarih": "2026-11-09",
            "ders": "TYT Türkçe",
            "mikro_konu": "Günlük Paragraf",
            "alt_konu": None,
            "pedagoji_turu": "Ezber",
        }
        sonuc = planner.gunluk_tekillestir([dict(paragraf), dict(paragraf)])
        self.assertEqual(len(sonuc), 1, "Günlük rutin günde tek slota oturur")

    def test_10_temel_eksik_ayir(self):
        self.assertEqual(
            planner.temel_eksik_ayir(
                "Polinomlar - Eksikler: Fonksiyonlar, Çarpanlara Ayırma"
            ),
            ("Polinomlar", ["Fonksiyonlar", "Çarpanlara Ayırma"]),
        )
        self.assertEqual(
            planner.temel_eksik_ayir("Polinomlar (Temel Eksik: Fonksiyonlar)"),
            ("Polinomlar", ["Fonksiyonlar"]),
        )
        self.assertEqual(planner.temel_eksik_ayir("Türev"), ("Türev", []))


if __name__ == "__main__":
    unittest.main(verbosity=2)

