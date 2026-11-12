"""v2.1 mimari/kural güncellemeleri - kilit testleri.

Kapsam (görev maddeleri):

- **Modül 1:** Biten (%100) konu rutin programa girmez; deneme yanlışı varsa
  `deneme_id` tabanlı TEK telafi kartı açılır, tamamlanınca düşer (aynı
  denemeden tekrar tetiklenmez) ve yalnızca YENİ denemede yeniden tetiklenir.
- **Modül 2:** %0 konunun ilk adımı Konu Anlatımı'dır; ilk gün tamamlanınca
  24-48 saat sonrasına Pekiştirme / Hatırlama Kontrolü planlanır; kavram/işlem
  ders katsayı oranları farklılaşır.
- **Modül 3:** Günlük 3-5 farklı ders limiti; Paragraf/Problem/Geometri rutinleri
  ana ders kotasından sayılır; tek derse günlük 150 dk / 90 soru tavanı.

Testler geçici SQLite dosyası kullanır; gerçek `yks_veritabani.db` dosyasına
dokunulmaz.

Çalıştırma:
    python -m unittest tests.test_v21_kilitler -v
    python -m unittest discover -s tests -p "test_*.py"
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
    guncelleme_zamani TEXT,
    UNIQUE(ogrenci_id, ders, mikro_konu, alt_konu)
);
CREATE TABLE IF NOT EXISTS calisma_programi_gorevler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER,
    gun TEXT,
    ders TEXT,
    makro_konu TEXT,
    mikro_konu TEXT,
    gorev_tanimi TEXT,
    hedef_soru INTEGER,
    mikro_hedef_soru INTEGER,
    pedagoji_turu TEXT,
    durum INTEGER DEFAULT 0,
    tarih TEXT,
    alt_konu TEXT,
    deneme_id INTEGER
);
CREATE TABLE IF NOT EXISTS deneme_konu_yanlislari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER,
    deneme_id INTEGER,
    ders TEXT,
    makro_konu TEXT,
    konu_adi TEXT,
    yanlis_adedi INTEGER,
    durum TEXT DEFAULT 'Aktif',
    tarih TEXT
);
CREATE TABLE IF NOT EXISTS telafi_deneme_takibi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    ders TEXT NOT NULL,
    mikro_konu TEXT NOT NULL,
    son_kapatilan_deneme_id INTEGER NOT NULL DEFAULT 0,
    kapatilma_zamani TEXT,
    UNIQUE(ogrenci_id, ders, mikro_konu)
);
"""


class V21KilitTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="v21_kilit_")
        self.db_yolu = os.path.join(self.klasor, "test.db")
        conn = sqlite3.connect(self.db_yolu)
        conn.executescript(_SEMA)
        conn.commit()
        conn.close()
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
            "biten_konular": set(),
            "deneme_yanlislari": [],
            "pekistirme_bekleyen": [],
        }
        baglam.update(ek)
        return baglam

    def _yaz(self, sorgu, params=()):
        conn = sqlite3.connect(self.db_yolu)
        conn.execute(sorgu, params)
        conn.commit()
        conn.close()

    def _konu_gorevleri(self, sonuc, ana=ANA_KONU):
        return [g for g in sonuc["gorevler"] if g.get("mikro_konu") == ana]

    # ------------------------------------------------------------------
    # MODÜL 1 - Biten (%100) konu izolasyonu ve deneme telafi döngüsü
    # ------------------------------------------------------------------
    def test_01_biten_konu_rutin_programa_girmez(self):
        sonuc = planner.plan_uret(self._baglam(
            bilinen_mikro={ANA_KONU},
            biten_konular={(DERS, ANA_KONU)},
            gercek_cozulen={(DERS, ANA_KONU): 500},
        ))
        # Biten konunun hiçbir rutin kartı (anlatım/pekiştirme/tekrar) yoktur.
        self.assertEqual(self._konu_gorevleri(sonuc), [])
        self.assertEqual(
            [g for g in sonuc["gorevler"] if g.get("mikro_konu") == ANA_KONU], []
        )

    def test_02_biten_konu_deneme_yanlisi_telafi_karti(self):
        sonuc = planner.plan_uret(self._baglam(
            bilinen_mikro={ANA_KONU},
            biten_konular={(DERS, ANA_KONU)},
            gercek_cozulen={(DERS, ANA_KONU): 500},
            deneme_yanlislari=[{
                "ders": DERS, "konu": ANA_KONU,
                "deneme_id": 5, "yanlis_adedi": 3,
            }],
        ))
        telafiler = [g for g in sonuc["gorevler"] if planner.telafi_gorevi_mi(g)]
        self.assertEqual(len(telafiler), 1)
        kart = telafiler[0]
        self.assertEqual(kart.get("deneme_id"), 5)
        self.assertEqual(kart["gorev_turu"], "soru")
        self.assertGreaterEqual(int(kart["hedef_soru"]), planner.TELAFI_MIN_SORU)
        self.assertLessEqual(int(kart["hedef_soru"]), planner.TELAFI_MAKS_SORU)

    def test_03_telafi_ayni_denemeden_tekrar_tetiklenmez(self):
        # 1) deneme 5 yanlışı -> telafi kartı
        sonuc = planner.plan_uret(self._baglam(
            bilinen_mikro={ANA_KONU},
            biten_konular={(DERS, ANA_KONU)},
            gercek_cozulen={(DERS, ANA_KONU): 500},
            deneme_yanlislari=[{
                "ders": DERS, "konu": ANA_KONU,
                "deneme_id": 5, "yanlis_adedi": 3,
            }],
        ))
        kart = [g for g in sonuc["gorevler"] if planner.telafi_gorevi_mi(g)][0]
        tamam = dict(kart)
        tamam["id"] = 401
        tamam["durum"] = 1  # öğrenci telafiyi tamamladı

        # 2) AYNI deneme (5) hâlâ yanlış görünse de telafi yeniden AÇILMAZ.
        sonuc2 = planner.plan_uret(self._baglam(
            bilinen_mikro={ANA_KONU},
            biten_konular={(DERS, ANA_KONU)},
            gercek_cozulen={(DERS, ANA_KONU): 500},
            deneme_yanlislari=[{
                "ders": DERS, "konu": ANA_KONU,
                "deneme_id": 5, "yanlis_adedi": 3,
            }],
            onceki_gorevler=[tamam],
        ))
        self.assertEqual(
            [g for g in sonuc2["gorevler"] if planner.telafi_gorevi_mi(g)], []
        )

        # 3) YENİ tarihli deneme (6) -> telafi yeniden TEK kez tetiklenir.
        sonuc3 = planner.plan_uret(self._baglam(
            bilinen_mikro={ANA_KONU},
            biten_konular={(DERS, ANA_KONU)},
            gercek_cozulen={(DERS, ANA_KONU): 500},
            deneme_yanlislari=[{
                "ders": DERS, "konu": ANA_KONU,
                "deneme_id": 6, "yanlis_adedi": 2,
            }],
            onceki_gorevler=[tamam],
        ))
        yeniler = [g for g in sonuc3["gorevler"] if planner.telafi_gorevi_mi(g)]
        self.assertEqual(len(yeniler), 1)
        self.assertEqual(yeniler[0].get("deneme_id"), 6)

    def test_04_bekleyen_pekistirme_konuyu_biten_saymaz(self):
        # POLINOM'un tüm alt başlıkları kapanmış (normalde biten sayılır).
        for alt in MIKRO_ALT_KONULAR[POLINOM]:
            self._yaz(
                "INSERT INTO mikro_konu_ilerleme (ogrenci_id, ders, makro_konu,"
                " mikro_konu, alt_konu, ogrenme_tamam, hedef_soru, cozulen_soru,"
                " tamamlandi) VALUES (1, 'AYT Matematik', 'İleri Cebir', ?, ?,"
                " 1, 30, 30, 1)",
                (POLINOM, alt),
            )
        mufredat = {"AYT Matematik": {"İleri Cebir": [POLINOM]}}
        biten = topic_progress.biten_konulari_yukle(
            1, mufredat, db_path=self.db_yolu
        )
        self.assertIn(("AYT Matematik", POLINOM), biten)

        # Bekleyen bir pekiştirme görevi varsa konu %100 biten SAYILMAZ.
        self._yaz(
            "INSERT INTO calisma_programi_gorevler (ogrenci_id, ders,"
            " mikro_konu, gorev_tanimi, hedef_soru, durum, tarih) VALUES"
            " (1, 'AYT Matematik', ?, '🔁 Pekiştirme / Hatırlama Kontrolü"
            " (20 Soru): Polinomlar', 20, 0, '2026-11-10')",
            (POLINOM,),
        )
        biten = topic_progress.biten_konulari_yukle(
            1, mufredat, db_path=self.db_yolu
        )
        self.assertNotIn(("AYT Matematik", POLINOM), biten)

        # Pekiştirme tamamlanınca kilit açılır.
        self._yaz(
            "UPDATE calisma_programi_gorevler SET durum = 1"
            " WHERE gorev_tanimi LIKE '%Pekiştirme%'"
        )
        biten = topic_progress.biten_konulari_yukle(
            1, mufredat, db_path=self.db_yolu
        )
        self.assertIn(("AYT Matematik", POLINOM), biten)

    # ------------------------------------------------------------------
    # MODÜL 2 - %0 konu akışı + 24-48 saat pekiştirme + katsayı dengesi
    # ------------------------------------------------------------------
    def test_05_sifir_konu_ilk_adim_konu_anlatimi(self):
        sonuc = planner.plan_uret(self._baglam(bilinen_mikro=set()))
        anlatimlar = [
            g for g in sonuc["gorevler"]
            if g.get("mikro_konu") == ANA_KONU and g.get("gorev_turu") == "anlatim"
        ]
        self.assertTrue(anlatimlar)
        ilk = anlatimlar[0]
        self.assertEqual(ilk["adimlar"][0]["adim_turu"], task_steps.ADIM_IZLE)
        self.assertTrue(
            ilk["adimlar"][0]["baslik"].startswith(task_steps.ADIM_KONU_ANLATIMI)
        )
        # Aynı planda pekiştirme YOK (ilk gün henüz tamamlanmadı).
        self.assertEqual(
            [g for g in sonuc["gorevler"] if task_steps.pekistirme_gorevi_mi(g)], []
        )

    def test_06_ilk_gun_tamamlaninca_24_48_saat_pekistirme(self):
        # İlk gün tamamlandı -> bekleyen pekiştirme ile yeni plan.
        sonuc = planner.plan_uret(self._baglam(
            bilinen_mikro={ANA_KONU},
            gercek_cozulen={(DERS, ANA_KONU): 10},
            pekistirme_bekleyen=[(DERS, ANA_KONU)],
        ))
        pek = [g for g in sonuc["gorevler"] if task_steps.pekistirme_gorevi_mi(g)]
        self.assertEqual(
            len(pek), 1, "Tamamlanan %0 konu için pekiştirme planlanmalı"
        )
        fark = (date.fromisoformat(pek[0]["tarih"]) - BAS).days
        self.assertGreaterEqual(fark, planner.PEKISTIRME_MIN_SAAT // 24)
        self.assertLessEqual(fark, planner.PEKISTIRME_MAX_SAAT // 24 + 1)
        # %50 kilidi saf mantığı
        self.assertEqual(task_steps.konu_ilerleme_ust_siniri(True), 50)
        self.assertEqual(task_steps.konu_ilerleme_ust_siniri(False), 100)

    def test_07_kavram_vs_islem_sure_orani_farklilasir(self):
        ortak = {
            "mikro_konu": ANA_KONU,
            "hedef_soru": 10,
            "gorev_turu": "anlatim",
        }
        biyoloji = task_steps.sure_plani(
            ders="TYT Biyoloji", pedagoji_turu="Ezber", **ortak
        )
        matematik = task_steps.sure_plani(
            ders="TYT Matematik", pedagoji_turu="Pekiştirme", **ortak
        )
        self.assertEqual(task_steps.ders_kategorisi("TYT Biyoloji"), "kavram")
        self.assertEqual(task_steps.ders_kategorisi("TYT Matematik"), "islem")
        # Kavram dersinde okuma payı daha yüksek, işlem dersinde pratik payı.
        self.assertGreater(biyoloji["okuma_orani"], matematik["okuma_orani"])
        self.assertGreater(matematik["pratik_orani"], biyoloji["pratik_orani"])
        # Hedef bantları (spec: kavram %55-65 okuma, işlem %80-90 pratik).
        self.assertGreaterEqual(
            task_steps.ders_sure_dengesi("TYT Biyoloji")["okuma_orani"], 0.55
        )
        self.assertLessEqual(
            task_steps.ders_sure_dengesi("TYT Biyoloji")["okuma_orani"], 0.65
        )
        self.assertGreaterEqual(
            task_steps.ders_sure_dengesi("TYT Matematik")["pratik_orani"], 0.80
        )
        self.assertLessEqual(
            task_steps.ders_sure_dengesi("TYT Matematik")["pratik_orani"], 0.90
        )

    # ------------------------------------------------------------------
    # MODÜL 3 - Günlük 3-5 ders limiti + rutin kovası + tek ders tavanı
    # ------------------------------------------------------------------
    def test_08_gunluk_ders_limiti_3_ve_5(self):
        dersler = ["Ders %d" % (i + 1) for i in range(6)]
        mufredat = {ders: {"Konu Grubu": [ANA_KONU]} for ders in dersler}
        gercek = {(ders, ANA_KONU): 0 for ders in dersler}

        kisa = planner.plan_uret(self._baglam(
            musaitlik={1: 240, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0},
            mufredat=mufredat, mikro_alt={}, gercek_cozulen=gercek,
            bilinen_mikro={ANA_KONU},
        ))
        gun1 = [g for g in kisa["gorevler"] if g["tarih"] == BAS.isoformat()]
        self.assertLessEqual(len({g["ders"] for g in gun1}), 3)

        uzun = planner.plan_uret(self._baglam(
            musaitlik={1: 540, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0},
            mufredat=mufredat, mikro_alt={}, gercek_cozulen=gercek,
            bilinen_mikro={ANA_KONU},
        ))
        gun1 = [g for g in uzun["gorevler"] if g["tarih"] == BAS.isoformat()]
        self.assertLessEqual(len({g["ders"] for g in gun1}), 5)
        # Tek ders tavanı: günlük toplam soru/süre limitleri aşılmaz.
        for ders in {g["ders"] for g in gun1}:
            ders_gorevleri = [g for g in gun1 if g["ders"] == ders]
            self.assertLessEqual(
                sum(int(g["hedef_soru"] or 0) for g in ders_gorevleri),
                planner.MAKS_DERS_GUN_SORU,
            )
            self.assertLessEqual(
                sum(int(g.get("tahmini_sure_dk") or 0) for g in ders_gorevleri),
                planner.MAKS_DERS_GUN_DAKIKA,
            )

    def test_09_rutin_kovasi_ana_ders_kotasinda(self):
        # Günlük rutinler ana ders kotasından sayılır (ayrı ders açmaz).
        self.assertEqual(
            planner.rutin_ana_dersi("Günlük Paragraf", "TYT Türkçe"), "TYT Türkçe"
        )
        self.assertEqual(
            planner.rutin_ana_dersi("Günlük Problem", "TYT Matematik"),
            "TYT Matematik",
        )
        self.assertEqual(
            planner.rutin_ana_dersi("Geometri 10'lu", "TYT Geometri"),
            "TYT Geometri",
        )
        self.assertEqual(
            planner.rutin_ana_dersi("Polinomlar", "AYT Matematik"),
            "AYT Matematik",
        )

    def test_10_gunluk_ders_doldur_eleme_ve_tavan(self):
        gorevler = [
            {
                "tarih": BAS.isoformat(),
                "ders": "Ders %d" % (i + 1),
                "mikro_konu": "Konu",
                "gorev_tanimi": "📌 test",
                "hedef_soru": 40,
                "tahmini_sure_dk": 60,
            }
            for i in range(6)
        ]
        sonuc = planner.gunluk_ders_doldur(
            gorevler, {1: 240, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}
        )
        # 4 saatlik günde en fazla 3 farklı ders kalır.
        self.assertLessEqual(len({g["ders"] for g in sonuc}), 3)
        # Tek derse günlük 90 soru tavanı.
        for ders in {g["ders"] for g in sonuc}:
            self.assertLessEqual(
                sum(g["hedef_soru"] for g in sonuc if g["ders"] == ders),
                planner.MAKS_DERS_GUN_SORU,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)

