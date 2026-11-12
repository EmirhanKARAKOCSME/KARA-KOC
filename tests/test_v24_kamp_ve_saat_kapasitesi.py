"""v2.4 testleri: Kamp uzay kokpiti CSS düzeltmesi + dinamik günlük saat ölçekleme.

Kapsam:
- Test 1 (Kamp CSS `ValueError` koruması): `kamp_kokpiti._css(tema)` 5 soğuk
  uzay temasının TAMAMINDA `ValueError` fırlatmadan geçerli CSS döndürür;
  `%` biçimlendirme çökmesi yok; yıldız (`twinkle`) ve gradyan (`background-size`)
  animasyon kurallarını içerir.
- Test 2 (6 saat = 360 dk): sıfır ilerlemeli öğrencide günlük toplam planlanan
  süre 240 dk'da takılmaz, 315-375 dk bandına ulaşır; `sira_no=1`, TYT➔AYT
  çekirdek kilidi ve tek branş kuralı BOZULMAZ.
- Test 3 (8 saat = 480 dk): günlük planlanan süre 430-495 dk bandına ölçeklenir.
- Test 4 (2 saat = 120 dk): program 4 saate taşmaz, ~95-130 dk bandında kalır.

Tüm testler `tempfile` tabanlı izole SQLite üzerinde çalışır; gerçek
`yks_veritabani.db` dosyasına DOKUNULMAZ.
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

from data import curriculum_meta as cm  # noqa: E402
from data.subtopics import MIKRO_ALT_KONULAR  # noqa: E402
from services import kamp_motoru  # noqa: E402
from services import planner  # noqa: E402
from services import task_steps  # noqa: E402
from views import kamp_kokpiti  # noqa: E402

BAS = date(2026, 11, 9)  # Pazartesi (Gün 1)

_SEMA = """
CREATE TABLE IF NOT EXISTS telafi_deneme_takibi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    ders TEXT NOT NULL,
    mikro_konu TEXT NOT NULL,
    son_kapatilan_deneme_id INTEGER NOT NULL DEFAULT 0,
    kapatilma_zamani TEXT,
    UNIQUE(ogrenci_id, ders, mikro_konu)
);
CREATE TABLE IF NOT EXISTS calisma_oturumlari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER, ders TEXT, mikro_konu TEXT, alt_konu TEXT,
    durum TEXT, gercek_sure_dk INTEGER, cozulen_soru INTEGER
);
CREATE TABLE IF NOT EXISTS mikro_konu_ilerleme (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER, ders TEXT, makro_konu TEXT, mikro_konu TEXT,
    alt_konu TEXT, ogrenme_tamam INTEGER, hedef_soru INTEGER,
    cozulen_soru INTEGER, tamamlandi INTEGER, son_gorev_id INTEGER,
    olusturma_zamani TEXT, guncelleme_zamani TEXT
);
"""


class _Temel(unittest.TestCase):
    """İzole SQLite DB + bağlam kurucu ortak taban."""

    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="karakoc_v24_")
        self.db_yolu = os.path.join(self.klasor, "test.db")
        conn = sqlite3.connect(self.db_yolu)
        conn.executescript(_SEMA)
        conn.commit()
        conn.close()
        planner.db_yolu_ayarla(self.db_yolu)
        task_steps.db_yolu_ayarla(self.db_yolu)
        kamp_motoru.db_yolu_ayarla(self.db_yolu)
        kamp_motoru.init_db()

    def tearDown(self):
        planner.db_yolu_ayarla(None)
        task_steps.db_yolu_ayarla(None)
        kamp_motoru.db_yolu_ayarla(None)
        shutil.rmtree(self.klasor, ignore_errors=True)

    def _mufredat(self):
        """5 TYT dersi + 1 AYT (TYT➔AYT kilidini sınamak için)."""
        return {
            "TYT Matematik": {
                "Temel Sayılar ve Cebir": ["Temel Kavramlar", "Sayı Basamakları"],
            },
            "TYT Geometri": {"Üçgenler ve Açılar": ["Doğruda Açılar"]},
            "TYT Fizik": {"Fizik Bilimine Giriş": ["Fizik Bilimine Giriş"]},
            "TYT Kimya": {"Kimya Bilimi": ["Kimya Bilimi"]},
            "TYT Biyoloji": {"Hücre": ["Canlıların Ortak Özellikleri"]},
            "AYT Matematik": {
                "İleri Cebir ve Fonksiyonlar": ["Polinomlar ve Çarpanlara Ayırma"],
            },
        }

    def _baglam(self, mufredat=None, musaitlik_dk=240,
                sinif_seviyesi=None, alan=None):
        # NOT: `legacy_mod` verilmez -> yeni (v2.4) kapasite ölçekleme AKTİF.
        return {
            "ogrenci_id": 1,
            "baslangic": BAS,
            "gun_sayisi": 7,
            "musaitlik": {g: musaitlik_dk for g in range(1, 8)},
            "konu_sureleri": {},
            "soru_agirliklari": {},
            "mufredat": mufredat or self._mufredat(),
            "mikro_alt": MIKRO_ALT_KONULAR,
            "tamamlanan_altlar": set(),
            "gercek_cozulen": {},
            "mikro_cozulen": {},
            "bilinen_mikro": set(),
            "on_kosullar": {},
            "pedagoji": {},
            "paragraf_soru": 0,
            "onceki_gorevler": [],
            "biten_konular": set(),
            "deneme_yanlislari": [],
            "pekistirme_bekleyen": [],
            "tekrar_entegrasyonu": False,
            "sinif_seviyesi": sinif_seviyesi,
            "alan": alan,
            "referans_tarihi": None,
        }

    @staticmethod
    def _ana_gorevler(gorevler):
        """Mikro rutin / tekrar / karma tarama dışındaki ana konu görevleri."""
        return [
            g for g in gorevler
            if g.get("gorev_tipi") != "karma_tarama"
            and g.get("pedagoji_turu") != "Tekrar"
            and planner.rutin_gunluk_limiti(
                g.get("mikro_konu"), g.get("ders")
            ) is None
        ]


class KampCssTestleri(_Temel):
    """Test 1: `_css` 5 temada da `ValueError` vermez; yıldız/gradyan içerir."""

    def test_01_css_valueerror_yok(self):
        temalar = list(kamp_motoru.TEMA_PALETLERI.keys())
        self.assertEqual(len(temalar), 5, "5'li soğuk uzay tema seçici korunmalı")
        for tema in temalar:
            # Eski `% renk` çökmesi burada ValueError fırlatırdı.
            css = kamp_kokpiti._css(tema)
            self.assertIsInstance(css, str, "%s: CSS metin dönmeli" % tema)
            self.assertIn("<style>", css)
            self.assertIn("@keyframes", css, "%s: animasyon keyframe'i yok" % tema)
            self.assertIn("twinkle", css, "%s: yıldız twinkle animasyonu yok" % tema)
            self.assertIn("background-size", css,
                          "%s: gradyan kayma animasyonu yok" % tema)
            self.assertNotIn("__MERKEZ_RENK__", css)
            self.assertNotIn("__ORTA_RENK__", css)
            self.assertNotIn("__KENAR_RENK__", css)
        # Varsayılan tema derin kozmik lacivert / uzay siyahı 3 duraklı gradyan.
        varsayilan = kamp_kokpiti._css(kamp_motoru.VARSAYILAN_TEMA)
        self.assertIn("#0A182E", varsayilan)
        self.assertIn("#050B18", varsayilan)
        self.assertIn("#020306", varsayilan)


class SaatKapasitesiTestleri(_Temel):
    """Test 2-4: günlük müsaitlik saatlerinin programa birebir ölçeklenmesi."""

    def _plan(self, musaitlik_dk):
        return planner.plan_uret(self._baglam(musaitlik_dk=musaitlik_dk))

    def test_02_alti_saat_360dk(self):
        sonuc = self._plan(360)
        gun1 = sonuc["gun_ozeti"][0]
        toplam1 = int(gun1["planlanan_dk"])
        # 240 dk (4 saat) tavanına sıkışmamalı; 315-375 bandına ulaşmalı.
        self.assertGreaterEqual(toplam1, 315, "6 saatte günlük süre ~%d dk" % toplam1)
        self.assertLessEqual(toplam1, 375, "6 saatte günlük süre ~%d dk" % toplam1)
        self.assertLessEqual(toplam1, int(gun1["kapasite_dk"]),
                             "günlük süre kapasiteyi aşmamalı")
        self.assertEqual(
            int(sonuc["toplam_sure_dk"]),
            sum(int(g["planlanan_dk"]) for g in sonuc["gun_ozeti"]),
            "toplam süre gün özetleriyle tutarlı olmalı",
        )
        ana = self._ana_gorevler(sonuc["gorevler"])
        self.assertTrue(ana, "TYT konuları planlanmalı")
        # 1) TYT➔AYT çekirdek kilidi bozulmadı.
        self.assertFalse(
            [g for g in ana if str(g["ders"]).startswith("AYT")],
            "çekirdek TYT bitmeden AYT planlanmamalı",
        )
        # 2) Mutlak müfredat sırası: her ders sira_no=1 ile başlar.
        sira = cm.sira_no_haritasi(self._mufredat())
        per_ders = {}
        for g in ana:
            per_ders.setdefault(g["ders"], set()).add(
                sira.get((g["ders"], g["mikro_konu"]))
            )
        for ders, siras in per_ders.items():
            self.assertIn(1, siras, "%s sira_no=1 ile başlamalı: %s" % (ders, siras))
        # 3) Tek branş = tek görev (gün + ana branş en fazla 1).
        gun_brans = {}
        for g in ana:
            anahtar = (g["tarih"], cm.ana_brans(g["ders"]))
            gun_brans[anahtar] = gun_brans.get(anahtar, 0) + 1
        for (tarih, brans), adet in gun_brans.items():
            self.assertLessEqual(
                adet, 1,
                "%s günü %s branşından %d kart (en fazla 1)" % (tarih, brans, adet),
            )

    def test_03_sekiz_saat_480dk(self):
        sonuc = self._plan(480)
        gun1 = sonuc["gun_ozeti"][0]
        toplam1 = int(gun1["planlanan_dk"])
        # Yoğun 8 saatlik program 430-495 dk bandına gerçekçi ölçeklenmeli.
        self.assertGreaterEqual(toplam1, 430, "8 saatte günlük süre ~%d dk" % toplam1)
        self.assertLessEqual(toplam1, 495, "8 saatte günlük süre ~%d dk" % toplam1)
        self.assertLessEqual(toplam1, int(gun1["kapasite_dk"]))
        self.assertEqual(
            int(sonuc["toplam_sure_dk"]),
            sum(int(g["planlanan_dk"]) for g in sonuc["gun_ozeti"]),
        )

    def test_04_iki_saat_120dk(self):
        sonuc = self._plan(120)
        gun1 = sonuc["gun_ozeti"][0]
        toplam1 = int(gun1["planlanan_dk"])
        # 4 saate (240 dk) taşmamalı; ~95-130 dk bandında kalmalı.
        self.assertGreaterEqual(toplam1, 95, "2 saatte günlük süre ~%d dk" % toplam1)
        self.assertLessEqual(toplam1, 130, "2 saatte günlük süre ~%d dk" % toplam1)
        self.assertLess(toplam1, 240, "2 saatlik gün 4 saate taşmamalı")


if __name__ == "__main__":
    unittest.main(verbosity=2)

