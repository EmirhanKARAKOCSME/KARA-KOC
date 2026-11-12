"""v2.3 haftalık program kesin düzeltmesi + "KARAKOÇ YKS KAMP" testleri.

Kapsam:
- Test 1 (Sıfır konu ve kilit): sınıf bilgisi verilmese bile AYT kilitli; her
  ders sıra_no=1 ile başlar; hiçbir ana konu görevi 25 dk/15 soru altı kırıntı
  değildir.
- Test 2 (Tek branş = tek görev + kart bütçesi): aynı gün aynı ana branştan tek
  kart; toplam görev ≤ 42.
- Test 3 (Dinamik takvim Gün 1): Perşembe (2026-11-12) başlayan programın 1.
  günü Perşembe'dir (Pazartesi'ye çekilmez).
- Test 4 (Kamp makro kilidi + atomik dilimleme): makro %100 olmadan sonrakine
  geçilmez; dilimler 10-15 soru.
- Test 5 (%75 eşiği + yorgunluk): < %75 -> analiz kartı; sayısal derste
  "Yoruldum" -> sözel derse geçiş önerisi.

Tüm testler `tempfile` tabanlı izole SQLite üzerinde çalışır; gerçek
`yks_veritabani.db` dosyasına dokunulmaz.
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

BAS = date(2026, 11, 9)          # Pazartesi
PERSEMBE = date(2026, 11, 12)    # Perşembe

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


class _KampTemel(unittest.TestCase):
    """İzole SQLite DB + bağlam kurucu ortak taban."""

    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="karakoc_v23_")
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

    def _baglam(self, mufredat=None, bas=None, gun_sayisi=7, musaitlik_dk=240,
                sinif_seviyesi=None, alan=None, bilinen_mikro=None,
                biten_konular=None, referans_tarihi=None):
        musaitlik = {g: musaitlik_dk for g in range(1, 8)}
        return {
            "ogrenci_id": 1,
            "baslangic": bas or BAS,
            "gun_sayisi": gun_sayisi,
            "musaitlik": musaitlik,
            "konu_sureleri": {},
            "soru_agirliklari": {},
            "mufredat": mufredat or {},
            "mikro_alt": MIKRO_ALT_KONULAR,
            "tamamlanan_altlar": set(),
            "gercek_cozulen": {},
            "mikro_cozulen": {},
            "bilinen_mikro": set(bilinen_mikro or ()),
            "on_kosullar": {},
            "pedagoji": {},
            "paragraf_soru": 0,
            "onceki_gorevler": [],
            "biten_konular": set(biten_konular or ()),
            "deneme_yanlislari": [],
            "pekistirme_bekleyen": [],
            "tekrar_entegrasyonu": False,
            "sinif_seviyesi": sinif_seviyesi,
            "alan": alan,
            "referans_tarihi": referans_tarihi,
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


class MotorKesinlikTestleri(_KampTemel):
    """Test 1: sıfır konu + kilit kesinliği (kırıntı yok)."""

    def _mufredat(self):
        return {
            "TYT Matematik": {
                "Temel Sayılar ve Cebir": ["Temel Kavramlar", "Sayı Basamakları"],
            },
            "TYT Geometri": {"Üçgenler ve Açılar": ["Doğruda Açılar"]},
            "TYT Fizik": {"Fizik Bilimine Giriş": ["Fizik Bilimine Giriş"]},
            "TYT Kimya": {"Kimya Bilimi": ["Kimya Bilimi"]},
            "AYT Matematik": {
                "İleri Cebir ve Fonksiyonlar": ["Polinomlar ve Çarpanlara Ayırma"],
            },
        }

    def test_01_sifir_konu_kilit_ve_kirinti(self):
        mufredat = self._mufredat()
        # sinif_seviyesi/alan DIŞARIDAN verilmez (None) — varsayılan yine kilitler.
        sonuc = planner.plan_uret(self._baglam(
            mufredat=mufredat, gun_sayisi=7, musaitlik_dk=240,
        ))
        ana = self._ana_gorevler(sonuc["gorevler"])
        self.assertTrue(ana, "TYT konuları planlanmalı")

        # 1) Çekirdek TYT bitmeden AYT hiç girmemeli.
        self.assertFalse(
            [g for g in ana if str(g["ders"]).startswith("AYT")],
            "sınıf bilgisi verilmese bile AYT kilitli kalmalı",
        )

        # 2) Her ders sıra_no=1 ile BAŞLAR (sıra atlaması yok).
        sira = cm.sira_no_haritasi(mufredat)
        per_ders = {}
        for g in ana:
            per_ders.setdefault(g["ders"], set()).add(
                sira.get((g["ders"], g["mikro_konu"]))
            )
        self.assertGreaterEqual(len(per_ders), 4, "en az 4 TYT dersi başlamalı")
        for ders, siras in per_ders.items():
            self.assertIn(1, siras, "%s sira_no=1 ile başlamalı: %s" % (ders, siras))

        # 3) Hiçbir ana konu görevi 25 dk / 15 soru altı KIRINTI olmamalı.
        for g in ana:
            sure = int(g.get("tahmini_sure_dk") or 0)
            soru = int(g.get("hedef_soru") or 0)
            self.assertFalse(
                sure < planner.MIN_KONU_BLOK_DK
                and soru < planner.MIN_KONU_BLOK_SORU,
                "kırıntı görev: %s / %s = %d dk, %d soru"
                % (g["ders"], g["mikro_konu"], sure, soru),
            )


class TekBransButceTestleri(_KampTemel):
    """Test 2: tek branş = tek görev + haftalık kart bütçesi."""

    def test_01_tek_brans_ve_kart_butcesi(self):
        mufredat = {
            "TYT Matematik": {"Temel Sayılar": ["Temel Kavramlar"]},
            "TYT Geometri": {"Açılar": ["Doğruda Açılar"]},
            "TYT Fizik": {"Fizik Bilimi": ["Fizik Bilimine Giriş"]},
            "TYT Kimya": {"Kimya Bilimi": ["Kimya Bilimi"]},
            "TYT Biyoloji": {"Hücre": ["Canlıların Ortak Özellikleri"]},
        }
        sonuc = planner.plan_uret(self._baglam(
            mufredat=mufredat, gun_sayisi=7, musaitlik_dk=240,
        ))
        ana = self._ana_gorevler(sonuc["gorevler"])
        self.assertTrue(ana)

        gun_brans = {}
        for g in ana:
            anahtar = (g["tarih"], cm.ana_brans(g["ders"]))
            gun_brans[anahtar] = gun_brans.get(anahtar, 0) + 1
        for (tarih, brans), adet in gun_brans.items():
            self.assertLessEqual(
                adet, 1,
                "%s günü %s branşından %d kart var (en fazla 1)"
                % (tarih, brans, adet),
            )
        self.assertLessEqual(
            len(sonuc["gorevler"]), 42,
            "haftalık kart sayısı 42'yi aşmamalı: %d" % len(sonuc["gorevler"]),
        )


class DinamikTakvimTestleri(_KampTemel):
    """Test 3: dinamik takvim (Bugün = Gün 1)."""

    def test_01_gun1_persembe(self):
        mufredat = {"TYT Matematik": {"Temel Sayılar": ["Temel Kavramlar"]}}
        sonuc = planner.plan_uret(self._baglam(
            mufredat=mufredat, bas=PERSEMBE, gun_sayisi=7, musaitlik_dk=240,
            referans_tarihi=PERSEMBE,
        ))
        self.assertTrue(sonuc["gun_ozeti"])
        ilk = sonuc["gun_ozeti"][0]
        self.assertEqual(ilk["tarih"], PERSEMBE.isoformat())
        self.assertEqual(ilk["gun"], "Perşembe", "1. gün Perşembe olmalı")
        # 1. güne ait en az bir görev olmalı (Pazartesi'ye çekilmemeli).
        self.assertTrue(
            [g for g in sonuc["gorevler"]
             if str(g.get("tarih"))[:10] == PERSEMBE.isoformat()],
            "1. gün (Perşembe) görev içermeli",
        )


class KampMakroDilimTestleri(_KampTemel):
    """Test 4: kamp makro ünite kilidi + atomik mikro dilimleme."""

    def test_01_makro_unite_kilidi(self):
        mufredat = {"TYT Matematik": {"Ünite1": ["A", "B"], "Ünite2": ["C"]}}
        k1 = kamp_motoru.aktif_makro_unite_hesapla(
            "TYT Matematik", mufredat, sinif_seviyesi="Mezun", alan="SAY"
        )
        self.assertEqual(k1["makro_unite"], "Ünite1")
        # Ünite1 %100 bitmeden Ünite2'ye geçilmez.
        k2 = kamp_motoru.aktif_makro_unite_hesapla(
            "TYT Matematik", mufredat,
            biten={("TYT Matematik", "A")},
            sinif_seviyesi="Mezun", alan="SAY",
        )
        self.assertEqual(k2["makro_unite"], "Ünite1")
        # Ünite1 tamamen bitince Ünite2 açılır.
        k3 = kamp_motoru.aktif_makro_unite_hesapla(
            "TYT Matematik", mufredat,
            biten={("TYT Matematik", "A"), ("TYT Matematik", "B")},
            sinif_seviyesi="Mezun", alan="SAY",
        )
        self.assertEqual(k3["makro_unite"], "Ünite2")

    def test_02_atomik_dilimleme(self):
        for hedef in (20, 30, 45):
            dilimler = kamp_motoru.mikro_dilimle(hedef)
            self.assertEqual(
                sum(d["hedef_soru"] for d in dilimler), hedef,
                "dilim toplamı hedefe eşit olmalı",
            )
            for d in dilimler:
                self.assertGreaterEqual(d["hedef_soru"], 10)
                self.assertLessEqual(d["hedef_soru"], 15)
            self.assertEqual(
                [d["dilim_no"] for d in dilimler],
                list(range(1, len(dilimler) + 1)),
            )

    def test_03_kronometre_baslangic_ts(self):
        oturum = kamp_motoru.oturum_baslat(1)
        kayit = kamp_motoru.mikro_gorev_baslat(
            oturum["id"], 1, "TYT Matematik", "Ünite1", "A", "A", 15,
        )
        self.assertIsNotNone(kayit["baslangic_ts"])
        self.assertGreater(float(kayit["baslangic_ts"]), 0)
        self.assertEqual(kayit["durum"], kamp_motoru.DURUM_AKTIF)


class BasariVeYorgunlukTestleri(_KampTemel):
    """Test 5: %75 doğruluk eşiği + yorgunluk merdiveni."""

    def test_01_esik_hesabi(self):
        # 20 soruda 6 yanlış = %70 -> analiz; 4 yanlış = %80 -> devam.
        self.assertEqual(
            kamp_motoru.sonraki_adim(kamp_motoru.basari_orani(20, 6, 0)),
            "analiz",
        )
        self.assertEqual(
            kamp_motoru.sonraki_adim(kamp_motoru.basari_orani(20, 4, 0)),
            "mikro",
        )
        self.assertAlmostEqual(kamp_motoru.basari_orani(20, 2, 3), 75.0)

    def test_02_analiz_karti_db(self):
        oturum = kamp_motoru.oturum_baslat(1)
        k1 = kamp_motoru.mikro_gorev_baslat(
            oturum["id"], 1, "AYT Matematik", "U", "A", "A", 15,
        )
        r1 = kamp_motoru.mikro_gorev_tamamla(k1["id"], 8, 0)  # %46.7 < 75
        self.assertTrue(r1["analiz_gerekli"])
        self.assertEqual(r1["sonraki"], "analiz")
        k2 = kamp_motoru.mikro_gorev_baslat(
            oturum["id"], 1, "AYT Matematik", "U", "B", "B", 15,
        )
        r2 = kamp_motoru.mikro_gorev_tamamla(k2["id"], 0, 0)  # %100 >= 75
        self.assertFalse(r2["analiz_gerekli"])
        self.assertEqual(r2["sonraki"], "mikro")

    def test_03_yorgunluk_merdiveni(self):
        sayisal = kamp_motoru.yorgunluk_onerisi("AYT Matematik")
        self.assertEqual(sayisal["tur"], "sozel")
        self.assertEqual(sayisal["oneri"], "TYT Türkçe")
        sozel = kamp_motoru.yorgunluk_onerisi("TYT Biyoloji")
        self.assertEqual(sozel["tur"], "mola")
        kademeler = kamp_motoru.yorgunluk_kademeleri()
        self.assertEqual([k["tur"] for k in kademeler], ["sozel", "mola", "bitir"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
