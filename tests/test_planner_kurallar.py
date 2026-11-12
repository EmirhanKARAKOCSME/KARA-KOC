"""Pedagojik planlama kuralları.

Kapsam:

- **KURAL 1 - Biten (%100) konu:** tamamlanmış konu rutin programa dönmez;
  yalnızca denemede yanlış çıkarsa SINIRLI bir "Eksik Kapatma" (telafi) kartı
  açılır ve hedefi dolunca kart bir daha üretilmez.
- **KURAL 2 - Bilinmeyen konu akışı:** sıfır ilerlemeli konuda kart/checklist
  "Konu Anlatımı (Video/Kaynak)" adımıyla başlar.
- **KURAL 3 - Ezber vs pekiştirme:** ezber derslerinde anlatım süresi uzar,
  pekiştirme derslerinde soru pratiği kolay ➔ orta ➔ zor ilerler.
- **KURAL 4 - Günlük ders bölünme limiti:** 4 saat ve altında en fazla 3,
  her durumda en fazla 5 farklı ders.
- `topic_progress.biten_konulari_yukle` gerçek ilerleme kayıtlarından biten
  konuları tespit eder.

Testler geçici bir SQLite dosyası kullanır; gerçek `yks_veritabani.db`
dosyasına dokunulmaz.

Çalıştırma:
    python tests/test_planner_kurallar.py
    python -m unittest discover -s tests -v
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import date

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(TEST_KOK)
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from data.subtopics import MIKRO_ALT_KONULAR  # noqa: E402
from services import planner  # noqa: E402
from services import task_steps  # noqa: E402
from services import topic_progress  # noqa: E402

BAS = date(2026, 11, 9)  # Pazartesi
DERS = "TYT Matematik"
ANA_KONU = "Sayılar"
ALTLAR = ["Doğal Sayılar", "Tam Sayılar"]
POLINOM = "Polinomlar ve Çarpanlara Ayırma"

_SEMA = """
CREATE TABLE IF NOT EXISTS konu_durumlari_detay (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER,
    ders TEXT,
    makro_konu TEXT,
    mikro_konu TEXT,
    durum TEXT
);
CREATE TABLE IF NOT EXISTS calisma_oturumlari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER,
    ders TEXT,
    mikro_konu TEXT,
    alt_konu TEXT,
    durum TEXT,
    cozulen_soru INTEGER
);
CREATE TABLE IF NOT EXISTS mikro_konu_ilerleme (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER,
    ders TEXT,
    makro_konu TEXT,
    mikro_konu TEXT,
    alt_konu TEXT,
    ogrenme_tamam INTEGER,
    hedef_soru INTEGER,
    cozulen_soru INTEGER,
    tamamlandi INTEGER,
    son_gorev_id INTEGER,
    olusturma_zamani TEXT,
    guncelleme_zamani TEXT
);
"""


class PlannerKurallarTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="plan_kural_")
        self.db_yolu = os.path.join(self.klasor, "test.db")
        conn = sqlite3.connect(self.db_yolu)
        conn.executescript(_SEMA)
        conn.commit()
        conn.close()
        # Tüm süre/ilerleme okumaları geçici veritabanına gider.
        planner.db_yolu_ayarla(self.db_yolu)
        task_steps.db_yolu_ayarla(self.db_yolu)

    def tearDown(self):
        planner.db_yolu_ayarla(None)
        task_steps.db_yolu_ayarla(None)
        shutil.rmtree(self.klasor, ignore_errors=True)

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
            "tekrar_entegrasyonu": False,
            # v2.3: özgün (legacy) planlama davranışını doğrular.
            "legacy_mod": True,
        }
        baglam.update(ek)
        return baglam

    def _konu_gorevleri(self, sonuc, ana=ANA_KONU):
        return [g for g in sonuc["gorevler"] if g.get("mikro_konu") == ana]

    def _telafi_karti(self, **ek):
        kart = {
            "id": 91,
            "ders": DERS,
            "makro_konu": "Temel Kavramlar",
            "mikro_konu": ANA_KONU,
            "alt_konu": None,
            "gorev_tanimi": "🩹 Eksik Kapatma (Özel Ders): Sayılar konusunda ...",
            "hedef_soru": 20,
            "mikro_hedef_soru": 20,
            "pedagoji_turu": "Tekrar",
            "gorev_turu": "soru",
            "durum": 0,
            "tarih": BAS.isoformat(),
        }
        kart.update(ek)
        return kart


    # ------------------------------------------------------------------
    # KURAL 1 - Biten konu
    # ------------------------------------------------------------------
    def test_01_biten_konu_alarm_yoksa_planlanmaz(self):
        sonuc = planner.plan_uret(self._baglam(
            bilinen_mikro={ANA_KONU},
            biten_konular={(DERS, ANA_KONU)},
            gercek_cozulen={(DERS, ANA_KONU): 500},
        ))
        self.assertEqual(self._konu_gorevleri(sonuc), [])

    def test_01b_biten_konunun_yarim_karti_devredilmez(self):
        # Geçen hafta yarım kalan rutin kart, konu %100 bitince devretmez.
        onceki = [{
            "id": 31, "ders": DERS, "makro_konu": "Temel Kavramlar",
            "mikro_konu": ANA_KONU, "alt_konu": ALTLAR[0],
            "gorev_tanimi": "🧩 Sayılar ➔ Doğal Sayılar: 12 soru çöz.",
            "hedef_soru": 12, "mikro_hedef_soru": 12,
            "pedagoji_turu": "Pekiştirme", "gorev_turu": "soru",
            "durum": 0, "tarih": BAS.isoformat(),
        }]
        sonuc = planner.plan_uret(self._baglam(
            bilinen_mikro={ANA_KONU},
            biten_konular={(DERS, ANA_KONU)},
            onceki_gorevler=onceki,
        ))
        self.assertEqual(self._konu_gorevleri(sonuc), [])

    def test_02_biten_konu_deneme_yanlisiyla_telafi_karti(self):
        sonuc = planner.plan_uret(self._baglam(
            bilinen_mikro={ANA_KONU},
            biten_konular={(DERS, ANA_KONU)},
            gercek_cozulen={(DERS, ANA_KONU): 500},
            alarm_konular=[{"ders": DERS, "konu": ANA_KONU, "seviye": "kirmizi"}],
        ))
        kartlar = self._konu_gorevleri(sonuc)
        self.assertEqual(len(kartlar), 1, "Telafi görevi haftada tek kart olmalı")
        kart = kartlar[0]
        self.assertTrue(planner.telafi_gorevi_mi(kart))
        self.assertTrue(kart["gorev_tanimi"].startswith(planner.TELAFI_ETIKETI))
        self.assertEqual(kart["gorev_turu"], "soru", "Bitmiş konu yeniden anlatılmaz")
        self.assertLessEqual(int(kart["hedef_soru"]), planner.TELAFI_HEDEF_SORU)
        self.assertGreaterEqual(int(kart["hedef_soru"]), planner.MIN_ANLAMLI_BLOK)

    def test_03_telafi_tamamlaninca_bir_daha_uretilmez(self):
        sonuc = planner.plan_uret(self._baglam(
            bilinen_mikro={ANA_KONU},
            biten_konular={(DERS, ANA_KONU)},
            gercek_cozulen={(DERS, ANA_KONU): 500},
            alarm_konular=[{"ders": DERS, "konu": ANA_KONU, "seviye": "kirmizi"}],
            onceki_gorevler=[self._telafi_karti(durum=1, gercek_soru=20)],
        ))
        self.assertEqual(
            self._konu_gorevleri(sonuc), [],
            "Hedefi tamamlanan Eksik Kapatma görevi programdan düşmeli",
        )

    def test_04_telafi_yarim_kalirsa_devreder(self):
        sonuc = planner.plan_uret(self._baglam(
            bilinen_mikro={ANA_KONU},
            biten_konular={(DERS, ANA_KONU)},
            gercek_cozulen={(DERS, ANA_KONU): 500},
            alarm_konular=[{"ders": DERS, "konu": ANA_KONU, "seviye": "kirmizi"}],
            onceki_gorevler=[self._telafi_karti(gercek_soru=5)],
        ))
        kartlar = self._konu_gorevleri(sonuc)
        self.assertEqual(len(kartlar), 1)
        self.assertTrue(planner.telafi_gorevi_mi(kartlar[0]))
        self.assertLessEqual(int(kartlar[0]["hedef_soru"]), 15)

    def test_05_biten_konu_suzgeci_rutin_kartlari_ayiklar(self):
        biten = {(DERS, ANA_KONU)}
        gorevler = [
            # Biten konunun rutin pekiştirme kartı -> atılır.
            {"ders": DERS, "mikro_konu": ANA_KONU, "gorev_tanimi": "📌 x"},
            # Biten konunun telafi kartı -> korunur.
            {"ders": DERS, "mikro_konu": ANA_KONU,
             "gorev_tanimi": "🩹 Eksik Kapatma (Özel Ders): x"},
            # Günlük rutin -> korunur.
            {"ders": "TYT Türkçe", "mikro_konu": "Günlük Paragraf",
             "gorev_tanimi": "📖 Günlük paragraf"},
            # Başka konu -> korunur.
            {"ders": DERS, "mikro_konu": "Bölme ve Bölünebilme",
             "gorev_tanimi": "📌 y"},
        ]
        kalan = planner.biten_konu_suzgeci(gorevler, biten)
        self.assertEqual(
            [g["gorev_tanimi"] for g in kalan],
            [
                "🩹 Eksik Kapatma (Özel Ders): x",
                "📖 Günlük paragraf",
                "📌 y",
            ],
        )

    def test_06_telafi_kapsanan_konular(self):
        onceki = [
            self._telafi_karti(durum=1),
            {"ders": DERS, "mikro_konu": "Türev", "gorev_tanimi": "📌 normal"},
        ]
        self.assertEqual(
            planner.telafi_kapsanan_konular(onceki), {(DERS, ANA_KONU)}
        )

    # ------------------------------------------------------------------
    # KURAL 2 - Bilinmeyen konu akışı
    # ------------------------------------------------------------------
    def test_07_ilk_kez_konu_anlatimi_ilk_adim(self):
        sonuc = planner.plan_uret(self._baglam(bilinen_mikro=set()))
        kartlar = self._konu_gorevleri(sonuc)
        self.assertTrue(kartlar)
        kart = kartlar[0]
        self.assertIn(planner.BILINMEYEN_KONU_ADIMI, kart["gorev_tanimi"])
        self.assertTrue(kart.get("ilk_kez_konu"))
        self.assertEqual(kart["adimlar"][0]["adim_turu"], task_steps.ADIM_IZLE)
        self.assertTrue(
            kart["adimlar"][0]["baslik"].startswith(task_steps.ADIM_KONU_ANLATIMI),
            "Konu anlatımı adımı ilk sırada olmalı",
        )

    def test_08_calismis_konuda_ilk_kez_vurgusu_yok(self):
        sonuc = planner.plan_uret(self._baglam(
            bilinen_mikro=set(),
            gercek_cozulen={(DERS, ANA_KONU): 12},
        ))
        kartlar = self._konu_gorevleri(sonuc)
        self.assertTrue(kartlar)
        self.assertFalse(kartlar[0].get("ilk_kez_konu"))
        self.assertNotIn(planner.BILINMEYEN_KONU_ADIMI, kartlar[0]["gorev_tanimi"])

    # ------------------------------------------------------------------
    # KURAL 3 - Ezber vs pekiştirme
    # ------------------------------------------------------------------
    def test_09_ezber_anlatim_suresi_uzar(self):
        ortak = {
            "mikro_konu": ANA_KONU,
            "hedef_soru": 10,
            "konu_sureleri": {ANA_KONU: 40},
            "gorev_turu": "anlatim",
        }
        ezber = task_steps.sure_plani(
            ders="TYT Biyoloji", pedagoji_turu="Ezber", **ortak
        )
        pekistirme = task_steps.sure_plani(
            ders="TYT Matematik", pedagoji_turu="Pekiştirme", **ortak
        )
        self.assertGreater(ezber["ogrenme_dk"], pekistirme["ogrenme_dk"])
        self.assertGreater(ezber["not_dk"], pekistirme["not_dk"])

    def test_10_pekistirme_zorluk_sirasi(self):
        bloklar = [9, 9, 9]
        self.assertEqual(
            task_steps.zorluk_etiketleri(bloklar, "TYT Matematik", "Pekiştirme"),
            [" (kolay)", " (orta)", " (zor)"],
        )
        self.assertEqual(
            task_steps.zorluk_etiketleri(bloklar, "TYT Tarih", "Ezber"),
            ["", "", ""],
            "Ezber derslerinde zorluk etiketi kullanılmaz",
        )
        self.assertEqual(
            task_steps.zorluk_etiketleri([27], "AYT Matematik", "Pekiştirme"),
            [" (kolay ➔ orta ➔ zor)"],
        )

    def test_11_ezber_gorev_soru_tavani_dusuk(self):
        self.assertLess(
            planner.gorev_soru_tavani("TYT Tarih", "Ezber"),
            planner.gorev_soru_tavani("TYT Matematik", "Pekiştirme"),
        )

        self.assertEqual(planner.telafi_kapsanan_konular([]), set())


    # ------------------------------------------------------------------
    # KURAL 4 - Günlük ders bölünme limiti
    # ------------------------------------------------------------------
    def test_12_gunluk_ders_limiti(self):
        self.assertEqual(planner.gunluk_ders_limiti(0), 0)
        self.assertEqual(planner.gunluk_ders_limiti(120), 3)
        self.assertEqual(planner.gunluk_ders_limiti(240), 3)
        self.assertEqual(planner.gunluk_ders_limiti(241), 5)
        self.assertEqual(planner.gunluk_ders_limiti(900), 5)

    def _ders_gorevleri(self, adet=6, dakika=240):
        dersler = ["Ders %d" % (i + 1) for i in range(adet)]
        gorevler = [
            {"tarih": BAS.isoformat(), "ders": ders, "mikro_konu": "Konu"}
            for ders in dersler
        ]
        return gorevler, planner.gunluk_ders_siniri_uygula(gorevler, {1: dakika})

    def test_13_gunluk_ders_siniri_kisa_gun(self):
        _, kalan = self._ders_gorevleri(adet=6, dakika=240)
        self.assertEqual(len({g["ders"] for g in kalan}), 3)

    def test_14_gunluk_ders_siniri_uzun_gun(self):
        _, kalan = self._ders_gorevleri(adet=6, dakika=480)
        self.assertEqual(len({g["ders"] for g in kalan}), 5)

    def test_15_plan_gunluk_ders_limitini_asmaz(self):
        dersler = ["Ders %d" % (i + 1) for i in range(6)]
        mufredat = {ders: {"Konu Grubu": [ANA_KONU]} for ders in dersler}
        gercek = {(ders, ANA_KONU): 0 for ders in dersler}

        kisa = planner.plan_uret(self._baglam(
            musaitlik={1: 240, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0},
            mufredat=mufredat,
            mikro_alt={},
            gercek_cozulen=gercek,
            bilinen_mikro={ANA_KONU},
        ))
        gun1 = [g for g in kisa["gorevler"] if g["tarih"] == BAS.isoformat()]
        self.assertLessEqual(len({g["ders"] for g in gun1}), 3)

        uzun = planner.plan_uret(self._baglam(
            musaitlik={1: 600, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0},
            mufredat=mufredat,
            mikro_alt={},
            gercek_cozulen=gercek,
            bilinen_mikro={ANA_KONU},
        ))
        gun1 = [g for g in uzun["gorevler"] if g["tarih"] == BAS.isoformat()]
        self.assertLessEqual(len({g["ders"] for g in gun1}), 5)

    # ------------------------------------------------------------------
    # Biten konu tespiti (topic_progress)
    # ------------------------------------------------------------------
    def _yaz(self, sorgu, params=()):
        conn = sqlite3.connect(self.db_yolu)
        conn.execute(sorgu, params)
        conn.commit()
        conn.close()

    def test_16_biten_konulari_yukle_alt_basliklar(self):
        alts = MIKRO_ALT_KONULAR[POLINOM]
        for alt in alts:
            self._yaz(
                "INSERT INTO mikro_konu_ilerleme (ogrenci_id, ders, makro_konu,"
                " mikro_konu, alt_konu, ogrenme_tamam, hedef_soru, cozulen_soru,"
                " tamamlandi) VALUES (1, ?, 'İleri Cebir', ?, ?, 1, 30, 30, 1)",
                ("AYT Matematik", POLINOM, alt),
            )
        mufredat = {"AYT Matematik": {"İleri Cebir": [POLINOM]}}
        biten = topic_progress.biten_konulari_yukle(1, mufredat, db_path=self.db_yolu)
        self.assertIn(("AYT Matematik", POLINOM), biten)

        # Son alt başlık kaldırılınca konu artık biten sayılmaz.
        self._yaz("DELETE FROM mikro_konu_ilerleme WHERE alt_konu = ?", (alts[-1],))
        biten = topic_progress.biten_konulari_yukle(1, mufredat, db_path=self.db_yolu)
        self.assertNotIn(("AYT Matematik", POLINOM), biten)

    def test_17_biten_konulari_yukle_soru_borcu(self):
        self._yaz(
            "INSERT INTO konu_durumlari_detay (ogrenci_id, ders, makro_konu,"
            " mikro_konu, durum) VALUES (1, ?, 'Genel', 'Karma Test', 'Biliyorum')",
            (DERS,),
        )
        self._yaz(
            "INSERT INTO calisma_oturumlari (ogrenci_id, ders, mikro_konu,"
            " durum, cozulen_soru) VALUES (1, ?, 'Karma Test', 'Tamamlandı', 60)",
            (DERS,),
        )
        biten = topic_progress.biten_konulari_yukle(1, None, db_path=self.db_yolu)
        self.assertNotIn((DERS, "Karma Test"), biten, "Soru borcu kapanmadı")

        self._yaz(
            "INSERT INTO calisma_oturumlari (ogrenci_id, ders, mikro_konu,"
            " durum, cozulen_soru) VALUES (1, ?, 'Karma Test', 'Tamamlandı', 60)",
            (DERS,),
        )
        biten = topic_progress.biten_konulari_yukle(1, None, db_path=self.db_yolu)
        self.assertIn((DERS, "Karma Test"), biten)


if __name__ == "__main__":
    unittest.main(verbosity=2)
