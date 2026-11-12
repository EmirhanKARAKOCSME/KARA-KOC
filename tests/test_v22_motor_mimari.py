"""v2.2 çekirdek planlama motoru ve çift motor mimarisi testleri.

Kapsam (görev maddeleri):

- **Test 1 (Müfredat sırası):** %0 öğrencide normal dönemde her dersin
  `sira_no = 1` konusu atanır; yüksek kredili son konular atanmaz.
- **Test 2 (TYT ➔ AYT kilidi):** Çekirdek TYT tamamlanmadan AYT konusu
  programa girmez; çekirdek %100 yapılınca AYT 1. konudan açılır.
- **Test 3 (Tek branş = tek konu + rotasyon):** Aynı güne aynı ana branştan
  birden çok konu yazılmaz; yan dersler günler arasında rotasyona girer.
- **Test 4 (%0 konu anlatımı + TYT Türkçe):** %0 konuda `konu_anlatimi` tipi,
  uzatılmış anlatım ve "Konu Anlatımı" ilk adımı; TYT Türkçe işlem dersi.
- **Test 5 (1 Mayıs çift motor):** Mayıs'ta ezber dersleri en yüksek kredili
  makro üniteye gider; pekiştirme dersleri `sira_no` sırasını korur.
- **Test 6 (Sınıf/Alan izolasyonu):** 9. sınıfa AYT verilmez; SAY öğrencisine
  AYT Edebiyat atanmaz.
- **Test 7 (%0 ➔ %30):** Konu anlatımı bitmiş konu sıfır sayılmaz; soru
  çözümü aşamasına geçer.

Testler `tempfile` tabanlı izole SQLite veritabanı kullanır; gerçek
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
from services import planner  # noqa: E402
from services import task_steps  # noqa: E402

BAS = date(2026, 11, 9)  # Pazartesi (normal dönem)
MAYIS = date(2027, 5, 2)  # Kriz / net maksimizasyonu dönemi

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


class _MotorTemel(unittest.TestCase):
    """İzole SQLite DB + bağlam kurucu ortak taban."""

    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="karakoc_v22_")
        self.db_yolu = os.path.join(self.klasor, "test.db")
        conn = sqlite3.connect(self.db_yolu)
        conn.executescript(_SEMA)
        conn.commit()
        conn.close()
        # Tüm planlama/süre servisleri izole DB'ye yönlendirilir (gerçek
        # `yks_veritabani.db` dosyasına erişilmez/okunmaz/yazılmaz).
        planner.db_yolu_ayarla(self.db_yolu)
        task_steps.db_yolu_ayarla(self.db_yolu)

    def tearDown(self):
        planner.db_yolu_ayarla(None)
        task_steps.db_yolu_ayarla(None)
        shutil.rmtree(self.klasor, ignore_errors=True)

    def _baglam(self, mufredat=None, bilinen_mikro=None, biten_konular=None,
                gercek_cozulen=None, mikro_cozulen=None, bas=None,
                gun_sayisi=7, musaitlik_dk=300, sinif_seviyesi="12. Sınıf",
                alan="Sayısal", referans_tarihi=None, ogrenilmis_konular=None,
                on_kosullar=None):
        if musaitlik_dk is None:
            musaitlik = {gun: 0 for gun in range(1, 8)}
        else:
            musaitlik = {gun: musaitlik_dk for gun in range(1, 8)}
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
            "gercek_cozulen": gercek_cozulen or {},
            "mikro_cozulen": mikro_cozulen or {},
            "bilinen_mikro": set(bilinen_mikro or ()),
            "on_kosullar": on_kosullar or {},
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
            "ogrenilmis_konular": set(ogrenilmis_konular or ()),
        }

    def _plan(self, baglam):
        return planner.plan_uret(baglam)

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


class MufredatSirasiTestleri(_MotorTemel):
    """Test 1: normal dönemde mutlak müfredat sırası (sira_no ASC)."""

    def test_01_her_dersin_ilk_konusu_atanir(self):
        mufredat = {
            "TYT Matematik": {
                "Temel Sayılar ve Cebir": [
                    "Temel Kavramlar", "Sayı Basamakları", "Bölme ve Bölünebilme",
                ],
                "Problemler": ["Kesir Problemleri", "Yaş Problemleri"],
            },
            "TYT Biyoloji": {
                "Hücre ve Canlılık": [
                    "Canlıların Ortak Özellikleri", "Hücre Yapısı ve Organeller",
                ],
            },
            "AYT Geometri": {"Katı Cisimler": ["Piramit ve Küre"]},
            "AYT Biyoloji": {"Bitki Biyolojisi ve Ekoloji": ["Bitki Dokuları"]},
            "AYT Matematik": {
                "İleri Cebir ve Fonksiyonlar": ["Polinomlar ve Çarpanlara Ayırma"],
            },
        }
        sonuc = self._plan(self._baglam(
            mufredat=mufredat, referans_tarihi=date(2026, 11, 15),
            gun_sayisi=2, musaitlik_dk=200,
        ))
        ana = self._ana_gorevler(sonuc["gorevler"])
        self.assertTrue(ana, "Normal dönemde ana konu üretilmeli")

        sira = cm.sira_no_haritasi(mufredat)
        # Her dersin SADECE sira_no=1 konusu atanmalı.
        for gorev in ana:
            anahtar = (gorev["ders"], gorev["mikro_konu"])
            self.assertEqual(
                sira.get(anahtar), 1,
                "%s / %s sira_no=1 değil (görülen: %s)"
                % (gorev["ders"], gorev["mikro_konu"], sira.get(anahtar)),
            )
        # Yüksek kredili son konular atanmamalı.
        atanan = {g["mikro_konu"] for g in ana}
        for yasak in ("Kesir Problemleri", "Piramit ve Küre", "Bitki Dokuları"):
            self.assertNotIn(yasak, atanan)
        # Çekirdek TYT bitmeden AYT hiç girmemeli.
        self.assertFalse([g for g in ana if str(g["ders"]).startswith("AYT")])


class CekirdekKilitTestleri(_MotorTemel):
    """Test 2: TYT ➔ AYT çekirdek ön koşul kilidi."""

    _TYT_GEO = [
        "Doğruda Açılar", "Üçgende Açılar", "Dik Üçgen ve Pisagor",
        "Üçgende Eşlik ve Benzerlik", "Üçgende Alan", "Çokgenler",
        "Dörtgenler ve Özel Dörtgenler",
    ]

    def _mufredat(self):
        return {
            "TYT Geometri": {"Üçgenler ve Açılar": list(self._TYT_GEO)},
            "AYT Geometri": {"Katı Cisimler": ["Piramit ve Küre", "Silindir ve Koni"]},
        }

    def test_01_cekirdek_bitmeden_ayt_girmez(self):
        sonuc = self._plan(self._baglam(
            mufredat=self._mufredat(), referans_tarihi=date(2026, 11, 15),
            gun_sayisi=3, musaitlik_dk=300,
        ))
        ana = self._ana_gorevler(sonuc["gorevler"])
        self.assertFalse(
            [g for g in ana if g["ders"] == "AYT Geometri"],
            "Çekirdek TYT Geometri bitmeden AYT Geometri girmemeli",
        )

    def test_02_cekirdek_bitince_ayt_ilk_konudan_acilir(self):
        sonuc = self._plan(self._baglam(
            mufredat=self._mufredat(), bilinen_mikro=self._TYT_GEO,
            referans_tarihi=date(2026, 11, 15), gun_sayisi=3, musaitlik_dk=300,
        ))
        ayt = [g for g in self._ana_gorevler(sonuc["gorevler"])
               if g["ders"] == "AYT Geometri"]
        self.assertTrue(ayt, "Çekirdek TYT %100 olunca AYT Geometri açılmalı")
        self.assertEqual(
            ayt[0]["mikro_konu"], "Piramit ve Küre",
            "AYT 1. konudan (sira_no=1) açılmalı",
        )


class TekBransRotasyonTestleri(_MotorTemel):
    """Test 3: tek branş = tek konu + yan ders rotasyonu."""

    def test_01_ayni_gun_ayni_brans_tek_konu_ve_rotasyon(self):
        # TYT tamamı bitmiş kabul edilir; yalnızca AYT yan dersleri kalır.
        mufredat = {
            "AYT Geometri": {
                "Katı Cisimler": ["Piramit ve Küre", "Silindir ve Koni"],
                "Çember ve Daire": ["Çemberde Açı", "Dairede Alan"],
            },
            "AYT Fizik": {
                "Elektromanyetizma": ["Elektrik Alan", "Manyetizma"],
                "Modern Fizik": ["Fotoelektrik", "Özel Görelilik"],
            },
            "AYT Kimya": {
                "Organik Kimya": ["Alkanlar", "Alkenler"],
                "Modern Atom ve Gazlar": ["Gaz Yasaları", "Atom Modelleri"],
            },
        }
        cekirdek = []
        for ders in ("AYT Geometri", "AYT Fizik", "AYT Kimya"):
            cekirdek.extend(cm.CEKIRDEK_TYT_ONKOSULLAR[ders])
        sonuc = self._plan(self._baglam(
            mufredat=mufredat, bilinen_mikro=cekirdek,
            referans_tarihi=date(2026, 11, 15), gun_sayisi=7, musaitlik_dk=300,
        ))
        ana = self._ana_gorevler(sonuc["gorevler"])
        self.assertTrue(ana, "AYT yan dersleri planlanmalı")

        # 1) Aynı gün + aynı ana branştan en fazla 1 konu.
        gun_brans = {}
        for gorev in ana:
            brans = cm.ana_brans(gorev["ders"])
            anahtar = (gorev["tarih"], brans)
            gun_brans[anahtar] = gun_brans.get(anahtar, 0) + 1
        for (tarih, brans), adet in gun_brans.items():
            self.assertLessEqual(
                adet, 1,
                "%s günü %s branşından %d konu var (en fazla 1 olmalı)"
                % (tarih, brans, adet),
            )

        # 2) Yan dersler günler arasında rotasyona girer (her gün aynı
        #    kombinasyon tekrarlanmaz).
        yan = {"Geometri", "Fizik", "Kimya"}
        gun_yan = {}
        for gorev in ana:
            brans = cm.ana_brans(gorev["ders"])
            if brans in yan:
                gun_yan.setdefault(gorev["tarih"], set()).add(brans)
        kombinasyonlar = {frozenset(v) for v in gun_yan.values()}
        self.assertGreaterEqual(
            len(kombinasyonlar), 2,
            "Yan dersler günler arasında rotasyona girmeli: %s" % (gun_yan,),
        )


class SifirKonuAnlatimiTestleri(_MotorTemel):
    """Test 4: %0 konuda zorunlu konu anlatımı + TYT Türkçe kategori."""

    def test_01_sifir_konu_anlatimi_karti(self):
        mufredat = {
            "TYT Matematik": {"Temel Sayılar ve Cebir": ["Temel Kavramlar"]},
        }
        sonuc = self._plan(self._baglam(
            mufredat=mufredat, referans_tarihi=date(2026, 11, 15),
            gun_sayisi=2, musaitlik_dk=300,
        ))
        kartlar = [
            g for g in sonuc["gorevler"]
            if g.get("mikro_konu") == "Temel Kavramlar"
        ]
        self.assertTrue(kartlar, "%0 konu için kart üretilmeli")
        kart = kartlar[0]
        self.assertEqual(kart["gorev_tipi"], "konu_anlatimi")
        # gorev_turu geriye dönük uyum için "anlatim" kalır.
        self.assertEqual(kart["gorev_turu"], "anlatim")
        konu_dk = int(kart.get("konu_anlatim_dk") or 0)
        toplam_dk = int(kart.get("tahmini_sure_dk") or 0)
        self.assertGreater(konu_dk, 0, "Ayrılmış anlatım dakikası olmalı")
        self.assertGreaterEqual(
            konu_dk, 0.5 * toplam_dk,
            "Anlatım süresi bloğun en az %%50'si olmalı (%d/%d)"
            % (konu_dk, toplam_dk),
        )
        self.assertTrue(kart.get("adimlar"), "Checklist olmalı")
        self.assertIn("Konu Anlatımı", kart["adimlar"][0]["baslik"])
        self.assertLessEqual(int(kart.get("hedef_soru") or 0), 20)

    def test_02_tyt_turkce_islem_dersidir(self):
        self.assertIn("TYT Türkçe", task_steps.ISLEM_PRATIK_DERSLERI)
        self.assertNotIn("TYT Türkçe", task_steps.KAVRAM_SOZEL_DERSLERI)
        self.assertEqual(task_steps.ders_kategorisi("TYT Türkçe"), "islem")
        self.assertTrue(task_steps.islem_pratik_mi("TYT Türkçe"))
        self.assertFalse(task_steps.kavram_sozel_mi("TYT Türkçe"))
        self.assertEqual(
            set(task_steps.KAVRAM_SOZEL_DERSLERI),
            {
                "TYT Biyoloji", "AYT Biyoloji", "TYT Tarih", "AYT Tarih",
                "TYT Coğrafya", "AYT Coğrafya", "AYT Edebiyat",
                "TYT Felsefe", "TYT Din Kültürü",
            },
        )


class CiftMotorTestleri(_MotorTemel):
    """Test 5: 1 Mayıs tarih tetiklemeli çift motor geçişi."""

    def _mufredat(self):
        return {
            "AYT Biyoloji": {
                "Sistemler Fizyolojisi": ["Sindirim Sistemi", "Dolaşım Sistemi"],
                "Genetik ve Enerji": ["DNA Replikasyonu"],
                "Bitki Biyolojisi ve Ekoloji": ["Bitki Dokuları"],
            },
            "AYT Edebiyat": {
                "Metinler ve Şiir": ["Şiir Bilgisi"],
                "Dönem Edebiyatları": ["Divan Edebiyatı", "Cumhuriyet Dönemi"],
            },
            "AYT Matematik": {
                "İleri Cebir ve Fonksiyonlar": ["Polinomlar ve Çarpanlara Ayırma"],
                "Analiz (Limit, Türev, İntegral)": ["Türev Alma Kuralları"],
            },
        }

    def test_01_mayista_ezber_kredi_peksitirme_sira(self):
        sonuc = self._plan(self._baglam(
            mufredat=self._mufredat(), sinif_seviyesi="11. Sınıf", alan=None,
            referans_tarihi=MAYIS, gun_sayisi=7, musaitlik_dk=300,
        ))
        ana = self._ana_gorevler(sonuc["gorevler"])

        bio = [g for g in ana if g["ders"] == "AYT Biyoloji"]
        self.assertTrue(bio, "AYT Biyoloji (Motor 2) planlanmalı")
        self.assertTrue(
            all(g["makro_konu"] == "Sistemler Fizyolojisi" for g in bio),
            "En yüksek kredili makro (Sistemler Fizyolojisi = 10) seçilmeli: %s"
            % {g["makro_konu"] for g in bio},
        )

        edb = [g for g in ana if g["ders"] == "AYT Edebiyat"]
        self.assertTrue(edb, "AYT Edebiyat (Motor 2) planlanmalı")
        self.assertTrue(
            all(g["makro_konu"] == "Dönem Edebiyatları" for g in edb),
            "En yüksek kredili makro (Dönem Edebiyatları = 10) seçilmeli: %s"
            % {g["makro_konu"] for g in edb},
        )

        mat = [g for g in ana if g["ders"] == "AYT Matematik"]
        self.assertTrue(mat, "AYT Matematik (Motor 1) planlanmalı")
        mat_mikro = {g["mikro_konu"] for g in mat}
        self.assertIn("Polinomlar ve Çarpanlara Ayırma", mat_mikro)
        self.assertNotIn(
            "Türev Alma Kuralları", mat_mikro,
            "Pekiştirme dersinde kredi atlanmamalı; sira_no korunmalı",
        )


class SinifAlanIzolasyonTestleri(_MotorTemel):
    """Test 6: sınıf seviyesi ve alan havuz izolasyonu."""

    def test_01_dokuzuncu_sinifa_ayt_verilmez(self):
        mufredat = {
            "Matematik ve Veri": {
                "1. Ünite: Sayılar": ["Sayı Kümeleri ve İşlem Özellikleri"],
            },
            "AYT Fizik": {"Mekanik": ["Newton'un Hareket Yasaları"]},
        }
        sonuc = self._plan(self._baglam(
            mufredat=mufredat, sinif_seviyesi="9. Sınıf", alan="Sayısal",
            referans_tarihi=date(2026, 11, 15), gun_sayisi=3, musaitlik_dk=300,
        ))
        ana = self._ana_gorevler(sonuc["gorevler"])
        self.assertTrue(ana, "9. sınıf TYT başlangıç konusu planlanmalı")
        self.assertFalse(
            [g for g in ana if str(g["ders"]).startswith("AYT")],
            "9. sınıf öğrencisine AYT konusu verilmemeli",
        )

    def test_02_sayisala_ayt_edebiyat_atanmaz(self):
        mufredat = {
            "TYT Matematik": {"Temel Sayılar ve Cebir": ["Temel Kavramlar"]},
            "AYT Edebiyat": {"Dönem Edebiyatları": ["Divan Edebiyatı"]},
            "AYT Matematik": {
                "İleri Cebir ve Fonksiyonlar": ["Polinomlar ve Çarpanlara Ayırma"],
            },
        }
        sonuc = self._plan(self._baglam(
            mufredat=mufredat, sinif_seviyesi="12. Sınıf", alan="Sayısal",
            bilinen_mikro=cm.CEKIRDEK_TYT_ONKOSULLAR["AYT Matematik"],
            referans_tarihi=date(2026, 11, 15), gun_sayisi=4, musaitlik_dk=300,
        ))
        ana = self._ana_gorevler(sonuc["gorevler"])
        self.assertFalse(
            [g for g in ana if g["ders"] == "AYT Edebiyat"],
            "Sayısal öğrencisine AYT Edebiyat atanmamalı",
        )


class YuzdeSifirOtuzGecisTestleri(_MotorTemel):
    """Test 7: %0 ➔ %30 geçişi (konu anlatımı bitince soru çözümü)."""

    def _mufredat(self):
        return {
            "TYT Matematik": {
                "Temel Sayılar ve Cebir": ["Temel Kavramlar", "Sayı Basamakları"],
            },
        }

    def test_01_konu_anlatimi_bitince_soru_cozumune_gecer(self):
        # Hiç öğrenilmemiş: konu anlatımı kartı üretilir.
        sifir = self._plan(self._baglam(
            mufredat=self._mufredat(), referans_tarihi=date(2026, 11, 15),
            gun_sayisi=2, musaitlik_dk=300,
        ))
        tk_sifir = [
            g for g in sifir["gorevler"]
            if g.get("mikro_konu") == "Temel Kavramlar"
        ]
        self.assertTrue(tk_sifir)
        self.assertEqual(tk_sifir[0]["gorev_tipi"], "konu_anlatimi")

        # Konu anlatımı bitmiş (%30): soru çözümü aşamasına geçer.
        ogrenmis = self._plan(self._baglam(
            mufredat=self._mufredat(), referans_tarihi=date(2026, 11, 15),
            gun_sayisi=2, musaitlik_dk=300,
            ogrenilmis_konular={("TYT Matematik", "Temel Kavramlar")},
        ))
        tk = [
            g for g in ogrenmis["gorevler"]
            if g.get("mikro_konu") == "Temel Kavramlar"
        ]
        self.assertTrue(tk)
        self.assertEqual(
            tk[0]["gorev_turu"], "soru",
            "Konu anlatımı bitmiş konu soru çözümüne geçmeli",
        )
        izle = [
            a for a in tk[0].get("adimlar") or []
            if a.get("adim_turu") == task_steps.ADIM_IZLE
        ]
        self.assertFalse(izle, "%30 konuda video/izle adımı tekrar edilmemeli")


if __name__ == "__main__":
    unittest.main(verbosity=2)
