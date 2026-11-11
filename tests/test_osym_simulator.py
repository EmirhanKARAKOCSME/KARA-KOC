"""FAZ 8 - YKS puan ve sıralama simülatörü testleri.

Kapsam (görev tanımındaki 16 senaryo):
- TYT / AYT net hesabı, farklı puan türleri, OBP dahil-hariç
- Yıla özgü kural setleri ve desteklenmeyen yıl hatası
- Puan-sıra referans verisi: var / yok / yetersiz / aralık dışı
- Eksik veya hatalı giriş, sıfır net, yüksek net
- Deneme verisinden otomatik net alma (son N genel deneme, öğrenci izolasyonu)
- Hedef net ile mevcut netin ayrı tutulması
- Farklı yılların karşılaştırılması, veri kaynağının doğru gösterilmesi

Testler geçici SQLite dosyası ve geçici referans JSON'u kullanır; gerçek
`yks_veritabani.db` ve `data/osym_puan_sira.json` dosyalarına dokunulmaz.

Çalıştırma:
    python tests/test_osym_simulator.py
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
PROJE_KOK = os.path.dirname(TEST_KOK)
for _yol in (TEST_KOK, PROJE_KOK):
    if _yol not in sys.path:
        sys.path.insert(0, _yol)

from services import osym_verisi as ov  # noqa: E402
from services import ranking_engine as re  # noqa: E402

_SIMDI = datetime(2026, 11, 11, 12, 0, tzinfo=re.TR_TZ)

SEMA = """
CREATE TABLE IF NOT EXISTS ogrenciler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tc_no TEXT UNIQUE,
    kullanici_adi TEXT UNIQUE,
    sifre_hash TEXT,
    ad TEXT,
    hedef_alan TEXT DEFAULT 'Sayısal',
    sinif_seviyesi TEXT DEFAULT '12. Sınıf',
    alan_kilitli INTEGER DEFAULT 0,
    son_sinif_atlatma_yili INTEGER DEFAULT 0,
    rol TEXT DEFAULT 'ogrenci',
    hesap_durumu TEXT DEFAULT 'Aktif',
    lisans_bitis TEXT,
    streak_count INTEGER DEFAULT 1,
    son_aktif_tarih TEXT,
    diploma_notu REAL DEFAULT 100.0
);

CREATE TABLE IF NOT EXISTS denemeler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER,
    tarih TEXT,
    deneme_adi TEXT,
    deneme_kategorisi TEXT DEFAULT 'Genel Deneme',
    deneme_turu TEXT,
    brans_dersi TEXT,
    net_bilgisi REAL,
    dogru_adedi INTEGER,
    yanlis_adedi INTEGER,
    bos_adedi INTEGER,
    sure_dk INTEGER,
    kayit_kaynagi TEXT DEFAULT 'wizard',
    legacy_signature TEXT,
    olusturma_zamani TEXT
);

CREATE TABLE IF NOT EXISTS deneme_ders_sonuclari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deneme_id INTEGER NOT NULL,
    ders TEXT NOT NULL,
    soru_sayisi INTEGER,
    dogru INTEGER DEFAULT 0,
    yanlis INTEGER DEFAULT 0,
    bos INTEGER DEFAULT 0,
    net REAL DEFAULT 0,
    sure_dk INTEGER
);
"""

TYT_NETLER = {
    "TYT Türkçe": 30.0,
    "TYT Matematik": 25.0,
    "TYT Sosyal Bilimler": 15.0,
    "TYT Fen Bilimleri": 10.0,
}

SAY_NETLER = dict(
    TYT_NETLER,
    **{
        "AYT Matematik": 20.0,
        "AYT Fizik": 7.0,
        "AYT Kimya": 6.0,
        "AYT Biyoloji": 6.0,
    }
)

EA_NETLER = dict(
    TYT_NETLER,
    **{
        "AYT Matematik": 20.0,
        "AYT Edebiyat": 15.0,
        "AYT Tarih-1": 6.0,
        "AYT Coğrafya-1": 4.0,
    }
)

SOZ_NETLER = dict(
    TYT_NETLER,
    **{
        "AYT Edebiyat": 15.0,
        "AYT Tarih-1": 6.0,
        "AYT Coğrafya-1": 4.0,
        "AYT Tarih-2": 7.0,
        "AYT Coğrafya-2": 6.0,
        "AYT Felsefe Grubu": 7.0,
        "AYT Din Kültürü": 4.0,
    }
)

DIL_NETLER = dict(TYT_NETLER, **{"YDT İngilizce": 60.0})

TAM_NETLER = {
    "TYT Türkçe": 40.0,
    "TYT Matematik": 40.0,
    "TYT Sosyal Bilimler": 20.0,
    "TYT Fen Bilimleri": 20.0,
    "AYT Matematik": 40.0,
    "AYT Fizik": 14.0,
    "AYT Kimya": 13.0,
    "AYT Biyoloji": 13.0,
    "AYT Edebiyat": 24.0,
    "AYT Tarih-1": 10.0,
    "AYT Coğrafya-1": 6.0,
    "AYT Tarih-2": 11.0,
    "AYT Coğrafya-2": 11.0,
    "AYT Felsefe Grubu": 12.0,
    "AYT Din Kültürü": 6.0,
    "YDT İngilizce": 80.0,
}

SIFIR_NETLER = {test: 0.0 for test in ov.TEST_SORU_SAYILARI}

ORNEK_KAYNAK = {
    "kurum": "ÖSYM",
    "belge": "Test amaçlı örnek tablo (resmî değil)",
    "url": "https://example.invalid/ornek",
    "erisim_tarihi": "2026-11-11",
}

ORNEK_NOKTALAR = [
    {"puan": 560.0, "sira": 1},
    {"puan": 500.0, "sira": 500},
    {"puan": 450.0, "sira": 6000},
    {"puan": 400.0, "sira": 30000},
    {"puan": 350.0, "sira": 90000},
    {"puan": 300.0, "sira": 200000},
]


class SimulatorTestTabani(unittest.TestCase):
    """Geçici DB + geçici referans dosyası kuran ortak taban."""

    @classmethod
    def setUpClass(cls):
        cls.klasor = tempfile.mkdtemp(prefix="faz8_")
        cls.db_yolu = os.path.join(cls.klasor, "test.db")
        cls.veri_yolu = os.path.join(cls.klasor, "puan_sira.json")
        re.db_yolu_ayarla(cls.db_yolu)
        ov.veri_dosyasi_ayarla(cls.veri_yolu)
        conn = sqlite3.connect(cls.db_yolu)
        conn.executescript(SEMA)
        conn.commit()
        conn.close()
        re.init_db()

    @classmethod
    def tearDownClass(cls):
        re.saat_fonksiyonu_ayarla(None)
        re.db_yolu_ayarla(None)
        ov.veri_dosyasi_ayarla(None)
        shutil.rmtree(cls.klasor, ignore_errors=True)

    def setUp(self):
        self._temizle()
        re.saat_fonksiyonu_ayarla(lambda: _SIMDI)
        ov.veri_dosyasi_ayarla(self.veri_yolu)
        if os.path.exists(self.veri_yolu):
            os.remove(self.veri_yolu)
        self.ogrenci = self.ogrenci_ekle("Test Öğrenci")

    def tearDown(self):
        re.saat_fonksiyonu_ayarla(None)

    # ------------------------------------------------------------------
    # ALTYAPI
    # ------------------------------------------------------------------
    def baglanti(self):
        conn = sqlite3.connect(self.db_yolu)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _temizle(self):
        conn = self.baglanti()
        try:
            for tablo in (
                "deneme_ders_sonuclari",
                "denemeler",
                "ogrenci_hedef_netleri",
                "ogrenciler",
            ):
                conn.execute("DELETE FROM %s" % tablo)
            conn.commit()
        finally:
            conn.close()

    def ogrenci_ekle(self, ad="Test Öğrenci", diploma_notu=85.0,
                     hedef_alan="Sayısal"):
        conn = self.baglanti()
        try:
            imlec = conn.execute(
                "INSERT INTO ogrenciler (ad, kullanici_adi, hedef_alan,"
                " diploma_notu) VALUES (?, ?, ?, ?)",
                (ad, "kullanici_%d" % abs(hash(ad)), hedef_alan, diploma_notu),
            )
            conn.commit()
            return int(imlec.lastrowid)
        finally:
            conn.close()

    def deneme_ekle(self, tur="TYT", tarih="2026-11-01", netler=None,
                    kategori="Genel Deneme", ogrenci_id=None,
                    ders_sonucu_var=True, deneme_adi="Deneme"):
        oid = self.ogrenci if ogrenci_id is None else ogrenci_id
        conn = self.baglanti()
        try:
            imlec = conn.execute(
                "INSERT INTO denemeler (ogrenci_id, tarih, deneme_adi,"
                " deneme_kategorisi, deneme_turu, net_bilgisi, olusturma_zamani)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    oid,
                    tarih,
                    deneme_adi,
                    kategori,
                    tur,
                    sum((netler or {}).values()),
                    "%s 12:00:00" % tarih,
                ),
            )
            deneme_id = int(imlec.lastrowid)
            if ders_sonucu_var and netler:
                for ders, net in netler.items():
                    conn.execute(
                        "INSERT INTO deneme_ders_sonuclari (deneme_id, ders,"
                        " soru_sayisi, net) VALUES (?, ?, ?, ?)",
                        (deneme_id, ders, ov.test_soru_sayisi(ders) or 40, net),
                    )
            conn.commit()
            return deneme_id
        finally:
            conn.close()

    def nokta_ekle(self, yil="2026", puan_turu="Sayısal", noktalar=None,
                   kaynak=None):
        return ov.kayit_ekle(
            yil,
            puan_turu,
            ORNEK_NOKTALAR if noktalar is None else noktalar,
            ORNEK_KAYNAK if kaynak is None else kaynak,
        )


class NetHesabiTest(unittest.TestCase):
    """Net = Doğru - Yanlış/4 kuralı ve giriş doğrulaması."""

    def test_tyt_net_hesabi(self):
        self.assertEqual(re.net_hesapla(30, 8, 2, 40), 28.0)
        self.assertEqual(re.net_hesapla(40, 0, 0, 40), 40.0)

    def test_ayt_net_hesabi_ondalik(self):
        self.assertEqual(re.net_hesapla(7, 3, 4, 14), 6.25)

    def test_sifir_net(self):
        self.assertEqual(re.net_hesapla(0, 0, 40, 40), 0.0)

    def test_negatif_giris_reddedilir(self):
        with self.assertRaises(re.SimulatorHatasi):
            re.net_hesapla(-1, 0)
        with self.assertRaises(re.SimulatorHatasi):
            re.net_hesapla(10, -2)

    def test_soru_sayisi_asilamaz(self):
        with self.assertRaises(re.SimulatorHatasi):
            re.net_hesapla(30, 10, 5, 40)

    def test_sayisal_olmayan_giris_reddedilir(self):
        with self.assertRaises(re.SimulatorHatasi):
            re.net_hesapla("abc", 0)

    def test_soru_sayisi_pozitif_olmali(self):
        with self.assertRaises(re.SimulatorHatasi):
            re.net_hesapla(1, 0, 0, 0)

    def test_app_kuraliyla_ayni(self):
        """Ders net kuralı uygulamanın genel kuralıyla aynı olmalı."""
        for dogru, yanlis in ((17, 5), (40, 0), (0, 12), (23, 7)):
            self.assertAlmostEqual(
                re.net_hesapla(dogru, yanlis), round(dogru - yanlis / 4.0, 2)
            )


class PuanHesabiTest(SimulatorTestTabani):
    """Puan türleri, OBP, sıfır/tam net ve yıl kuralları."""

    def test_tyt_puani_obp_haric(self):
        sonuc = re.puan_hesapla(
            TYT_NETLER, "TYT", "2026", diploma_notu=85.0, obp_dahil=False
        )
        beklenen = 100.0 + 30 * 3.30 + 25 * 3.30 + 15 * 3.40 + 10 * 3.40
        self.assertEqual(sonuc["durum"], re.DURUM_OK)
        self.assertAlmostEqual(sonuc["puan"], round(beklenen, 2))
        self.assertEqual(sonuc["obp_katkisi"], 51.0)

    def test_obp_dahil_ve_haric_ayri(self):
        haric = re.puan_hesapla(SAY_NETLER, "Sayısal", "2026", 85.0, False)
        dahil = re.puan_hesapla(SAY_NETLER, "Sayısal", "2026", 85.0, True)
        self.assertAlmostEqual(dahil["puan"] - haric["puan"], 51.0, places=2)
        self.assertEqual(dahil["puan_obp_haric"], haric["puan_obp_haric"])

    def test_obp_yoksa_katki_sifir(self):
        sonuc = re.puan_hesapla(SAY_NETLER, "Sayısal", "2026", None, True)
        self.assertIsNone(sonuc["obp_puani"])
        self.assertEqual(sonuc["obp_katkisi"], 0.0)
        self.assertEqual(sonuc["puan"], sonuc["ham_puan"])

    def test_obp_diploma_sinirlari(self):
        self.assertEqual(ov.obp_puani(120.0), 500.0)
        self.assertEqual(ov.obp_puani(10.0), 250.0)
        self.assertEqual(ov.obp_katkisi(100.0), 60.0)
        with self.assertRaises(ov.VeriHatasi):
            ov.obp_puani("abc")

    def test_farkli_puan_turleri(self):
        for tur, netler in (
            ("TYT", TYT_NETLER),
            ("Sayısal", SAY_NETLER),
            ("Eşit Ağırlık", EA_NETLER),
            ("Sözel", SOZ_NETLER),
            ("Dil", DIL_NETLER),
        ):
            sonuc = re.puan_hesapla(netler, tur, "2026", 85.0)
            self.assertEqual(sonuc["durum"], re.DURUM_OK, tur)
            self.assertGreater(sonuc["puan"], 100.0, tur)
            self.assertLessEqual(sonuc["puan"], 560.0, tur)
            testler = [k["test"] for k in sonuc["test_katkilari"]]
            self.assertEqual(len(testler), len(re.gereken_testler(tur)))

    def test_puan_turu_esleme(self):
        self.assertEqual(ov.puan_turu_kontrol("say"), "Sayısal")
        self.assertEqual(ov.puan_turu_kontrol("EA"), "Eşit Ağırlık")
        self.assertEqual(ov.puan_turu_kontrol("sözel"), "Sözel")
        self.assertEqual(ov.puan_turu_kontrol("ydt"), "Dil")
        with self.assertRaises(ov.VeriHatasi):
            ov.puan_turu_kontrol("Uzay")

    def test_tam_net_ust_sinir(self):
        """Tam nette ham puan 500'e, yerleştirme 560'a yaklaşır (katsayı yuvarlaması)."""
        for tur in ("TYT", "Sayısal", "Eşit Ağırlık", "Sözel", "Dil"):
            sonuc = re.puan_hesapla(TAM_NETLER, tur, "2026", 100.0)
            self.assertAlmostEqual(sonuc["ham_puan"], 500.0, delta=0.5)
            self.assertAlmostEqual(sonuc["puan"], 560.0, delta=0.5)


    def test_sifir_net_taban_puan(self):
        sonuc = re.puan_hesapla(SIFIR_NETLER, "Sayısal", "2026", 85.0)
        self.assertEqual(sonuc["ham_puan"], 100.0)
        self.assertEqual(sonuc["puan"], 151.0)

    def test_eksik_net_hesap_yapmaz(self):
        eksik = dict(TYT_NETLER)
        eksik.pop("TYT Matematik")
        sonuc = re.puan_hesapla(eksik, "TYT", "2026", 85.0)
        self.assertEqual(sonuc["durum"], re.DURUM_EKSIK_NET)
        self.assertIsNone(sonuc["puan"])
        self.assertIn("TYT Matematik", sonuc["eksik_testler"])

    def test_net_soru_sayisini_asamaz(self):
        fazla = dict(TYT_NETLER, **{"TYT Türkçe": 41.0})
        with self.assertRaises(re.SimulatorHatasi):
            re.puan_hesapla(fazla, "TYT", "2026", 85.0)

    def test_sayisal_olmayan_net_reddedilir(self):
        bozuk = dict(TYT_NETLER, **{"TYT Türkçe": "x"})
        with self.assertRaises(re.SimulatorHatasi):
            re.puan_hesapla(bozuk, "TYT", "2026", 85.0)

    def test_desteklenmeyen_yil_hata(self):
        with self.assertRaises(ov.VeriHatasi):
            re.puan_hesapla(SAY_NETLER, "Sayısal", "1999", 85.0)

    def test_yil_bazli_kural_seti(self):
        eski = re.puan_hesapla(SAY_NETLER, "Sayısal", "2020", 85.0)
        yeni = re.puan_hesapla(SAY_NETLER, "Sayısal", "2026", 85.0)
        self.assertEqual(eski["kural"]["yil"], "2020")
        self.assertEqual(yeni["kural"]["yil"], "2026")
        self.assertIn("kaynak", yeni["kural"])
        self.assertIsNot(
            yeni["kural"]["ayt_katsayilari"], eski["kural"]["ayt_katsayilari"]
        )

    def test_resmi_olmadigi_bildirilir(self):
        sonuc = re.puan_hesapla(SAY_NETLER, "Sayısal", "2026", 85.0)
        self.assertFalse(sonuc["resmi_mi"])
        self.assertEqual(sonuc["kural"]["dogrulama_durumu"], "dogrulanmadi")
        self.assertTrue(any("model tahminidir" in u for u in sonuc["uyarilar"]))


class ReferansVeriTest(SimulatorTestTabani):
    """Puan-sıra referans katmanı: doğrulama, yazma, kaynak zorunluluğu."""

    def test_varsayilan_dosya_bos(self):
        """Ürünle gelen referans dosyası boş olmalı (uydurma veri yok)."""
        ov.veri_dosyasi_ayarla(None)
        try:
            ozet = ov.veri_ozeti()
        finally:
            ov.veri_dosyasi_ayarla(self.veri_yolu)
        self.assertEqual(ozet["kayit_sayisi"], 0)
        self.assertEqual(ozet["yillar"], [])
        self.assertEqual(len(ozet["eksik_puan_turleri"]), len(ov.PUAN_TURLERI))

    def test_kayit_ekle_ve_oku(self):
        self.nokta_ekle()
        kayit = ov.kayit_getir("2026", "Sayısal")
        self.assertIsNotNone(kayit)
        self.assertEqual(len(kayit["noktalar"]), len(ORNEK_NOKTALAR))
        self.assertEqual(kayit["kaynak"]["kurum"], ORNEK_KAYNAK["kurum"])

    def test_kaynaksiz_veri_reddedilir(self):
        with self.assertRaises(ov.VeriHatasi):
            ov.kayit_ekle(
                "2026",
                "Sayısal",
                ORNEK_NOKTALAR,
                {"kurum": "", "belge": "", "url": "", "erisim_tarihi": None},
            )
        self.assertEqual(ov.veri_ozeti()["kayit_sayisi"], 0)

    def test_min_nokta_zorunlu(self):
        with self.assertRaises(ov.VeriHatasi):
            self.nokta_ekle(noktalar=ORNEK_NOKTALAR[:2])

    def test_puan_azalan_sirali_olmali(self):
        bozuk = list(reversed(ORNEK_NOKTALAR))
        with self.assertRaises(ov.VeriHatasi):
            self.nokta_ekle(noktalar=bozuk)

    def test_sira_artan_olmali(self):
        bozuk = [
            {"puan": 560.0, "sira": 5},
            {"puan": 500.0, "sira": 4},
            {"puan": 450.0, "sira": 3},
        ]
        with self.assertRaises(ov.VeriHatasi):
            self.nokta_ekle(noktalar=bozuk)

    def test_puan_araligi_dogrulanir(self):
        with self.assertRaises(ov.VeriHatasi):
            self.nokta_ekle(
                noktalar=[
                    {"puan": 900.0, "sira": 1},
                    {"puan": 450.0, "sira": 6000},
                    {"puan": 400.0, "sira": 30000},
                ]
            )

    def test_ayni_yil_tur_tek_kayit(self):
        self.nokta_ekle()
        yeni = [n for n in ORNEK_NOKTALAR]
        yeni[1] = {"puan": 500.0, "sira": 400}
        self.nokta_ekle(noktalar=yeni)
        ozet = ov.veri_ozeti()
        self.assertEqual(ozet["kayit_sayisi"], 1)
        self.assertEqual(ov.noktalari_getir("2026", "Sayısal")[1]["sira"], 400)

    def test_kayit_sil(self):
        self.nokta_ekle()
        self.assertEqual(ov.kayit_sil("2026", "Sayısal"), 1)
        self.assertEqual(ov.veri_ozeti()["kayit_sayisi"], 0)
        self.assertEqual(ov.kayit_sil("2026", "Sayısal"), 0)

    def test_kapsanan_yillar(self):
        self.nokta_ekle("2025")
        self.nokta_ekle("2026")
        self.nokta_ekle("2026", "Eşit Ağırlık")
        self.assertEqual(ov.kapsanan_yillar("Sayısal"), ["2025", "2026"])
        self.assertEqual(ov.kapsanan_yillar("Eşit Ağırlık"), ["2026"])
        self.assertEqual(ov.kapsanan_yillar("Dil"), [])

    def test_bozuk_dosya_hata_verir(self):
        with open(self.veri_yolu, "w", encoding="utf-8") as dosya:
            dosya.write("{bozuk json")
        with self.assertRaises(ov.VeriHatasi):
            ov.veri_yukle()

    def test_gecersiz_yil_reddedilir(self):
        with self.assertRaises(ov.VeriHatasi):
            self.nokta_ekle("1999")

    def test_kaynak_ozet_bilgisi(self):
        self.nokta_ekle()
        ozet = ov.veri_ozeti()
        self.assertEqual(ozet["kaynaklar"][0]["kurum"], ORNEK_KAYNAK["kurum"])
        self.assertEqual(ozet["kaynaklar"][0]["belge"], ORNEK_KAYNAK["belge"])
        self.assertEqual(ozet["kaynaklar"][0]["nokta_sayisi"], len(ORNEK_NOKTALAR))
        self.assertEqual(ozet["eksik_puan_turleri"], [
            tur for tur in ov.PUAN_TURLERI if tur != "Sayısal"
        ])

    def test_metinden_noktalar(self):
        noktalar = ov.metinden_noktalar(
            "500;500\n450;6000\n\n400,5;30.000\n"
        )
        self.assertEqual(
            noktalar,
            [
                {"puan": 500.0, "sira": 500},
                {"puan": 450.0, "sira": 6000},
                {"puan": 400.5, "sira": 30000},
            ],
        )

    def test_metinden_noktalar_hatalari(self):
        for metin in ("", "500", "abc;100", "500;100\n450;200", "500;abc"):
            with self.assertRaises(ov.VeriHatasi, msg=metin):
                ov.metinden_noktalar(metin)



class SiralamaTahminiTest(SimulatorTestTabani):
    """Sıralama tahmini yalnızca doğrulanmış veriyle üretilir."""

    def test_veri_yoksa_tahmin_yok(self):
        sonuc = re.siralama_tahmini(420.0, "Sayısal", "2026")
        self.assertEqual(sonuc["durum"], re.DURUM_VERI_YOK)
        self.assertIsNone(sonuc["sira"])
        self.assertIsNone(sonuc["aralik"])
        self.assertEqual(sonuc["kapsanan_yillar"], [])
        self.assertTrue(sonuc["eksik_veri"])
        self.assertTrue(sonuc["notlar"])

    def test_aralik_ici_interpolasyon(self):
        self.nokta_ekle()
        sonuc = re.siralama_tahmini(425.0, "Sayısal", "2026")
        self.assertEqual(sonuc["durum"], re.DURUM_OK)
        self.assertEqual(sonuc["sira"], 18000)

    def test_nokta_uzerinde_tam_deger(self):
        self.nokta_ekle()
        self.assertEqual(re.siralama_tahmini(450.0, "Sayısal", "2026")["sira"], 6000)

    def test_aralik_disi_ekstrapolasyon_yok(self):
        self.nokta_ekle()
        sonuc = re.siralama_tahmini(590.0, "Sayısal", "2026")
        self.assertEqual(sonuc["durum"], re.DURUM_ARALIK_DISI)
        self.assertIsNone(sonuc["sira"])
        self.assertTrue(any("aralığı dışında" in n for n in sonuc["notlar"]))

    def test_tek_yil_aralik_uretmez(self):
        self.nokta_ekle("2026")
        sonuc = re.siralama_tahmini(425.0, "Sayısal", "2026")
        self.assertEqual(sonuc["durum"], re.DURUM_OK)
        self.assertIsNone(sonuc["aralik"])
        self.assertEqual(sonuc["aralik_turu"], None)

    def test_iki_yil_senaryo_araligi(self):
        self.nokta_ekle("2026")
        self.nokta_ekle(
            "2025",
            noktalar=[
                {"puan": 560.0, "sira": 1},
                {"puan": 500.0, "sira": 450},
                {"puan": 450.0, "sira": 5400},
                {"puan": 400.0, "sira": 27000},
                {"puan": 350.0, "sira": 81000},
                {"puan": 300.0, "sira": 180000},
            ],
        )
        sonuc = re.siralama_tahmini(425.0, "Sayısal", "2026")
        self.assertEqual(sonuc["durum"], re.DURUM_OK)
        self.assertEqual(sonuc["sira"], 18000)
        self.assertEqual(sonuc["aralik"], (16200, 18000))
        self.assertEqual(sonuc["aralik_turu"], "senaryo_araligi")
        self.assertTrue(any("güven" in n for n in sonuc["notlar"]))
        self.assertEqual(sonuc["kapsanan_yillar"], ["2025", "2026"])

    def test_veri_yetersiz_kayit_yok_sayilir(self):
        """Doğrulanmamış (2 noktalı) kayıt tahminde kullanılmaz."""
        import json

        with open(self.veri_yolu, "w", encoding="utf-8") as dosya:
            json.dump(
                {
                    "surum": 1,
                    "guncelleme": "2026-11-11",
                    "kayitlar": [
                        {
                            "yil": "2026",
                            "puan_turu": "Sayısal",
                            "kaynak": ORNEK_KAYNAK,
                            "not": "",
                            "noktalar": ORNEK_NOKTALAR[:2],
                        }
                    ],
                },
                dosya,
            )
        sonuc = re.siralama_tahmini(450.0, "Sayısal", "2026")
        self.assertEqual(sonuc["durum"], re.DURUM_VERI_YOK)
        self.assertIsNone(sonuc["sira"])

    def test_kaynak_sonuca_yansir(self):
        self.nokta_ekle()
        sonuc = re.siralama_tahmini(425.0, "Sayısal", "2026")
        self.assertEqual(sonuc["kaynak"]["kurum"], ORNEK_KAYNAK["kurum"])
        self.assertEqual(sonuc["kaynak"]["belge"], ORNEK_KAYNAK["belge"])

    def test_baska_puan_turu_verisi_kullanilmaz(self):
        self.nokta_ekle("2026", "Sayısal")
        sonuc = re.siralama_tahmini(425.0, "Eşit Ağırlık", "2026")
        self.assertEqual(sonuc["durum"], re.DURUM_VERI_YOK)

    def test_puan_yoksa_tahmin_yok(self):
        self.nokta_ekle()
        sonuc = re.siralama_tahmini(None, "Sayısal", "2026")
        self.assertIsNone(sonuc["sira"])
        self.assertEqual(sonuc["durum"], re.DURUM_VERI_YOK)


class SimulasyonTest(SimulatorTestTabani):
    """Birleşik çıktı, yıl karşılaştırması ve veri durumu."""

    def test_simulasyon_paketi(self):
        self.nokta_ekle()
        paket = re.simulasyon(SAY_NETLER, "Sayısal", "2026", 85.0)
        self.assertEqual(paket["puan"]["durum"], re.DURUM_OK)
        self.assertEqual(paket["siralama"]["durum"], re.DURUM_OK)
        self.assertIsNotNone(paket["siralama"]["sira"])

    def test_simulasyon_eksik_nette_tahmin_yok(self):
        paket = re.simulasyon(TYT_NETLER, "Sayısal", "2026", 85.0)
        self.assertEqual(paket["puan"]["durum"], re.DURUM_EKSIK_NET)
        self.assertIsNone(paket["siralama"]["sira"])

    def test_yil_karsilastirmasi(self):
        self.nokta_ekle("2026")
        satirlar = re.yil_karsilastirmasi(
            SAY_NETLER, "Sayısal", 85.0, yillar=["2025", "2026"]
        )
        self.assertEqual([s["yil"] for s in satirlar], ["2025", "2026"])
        self.assertEqual(satirlar[1]["durum"], re.DURUM_OK)
        self.assertEqual(satirlar[0]["durum"], re.DURUM_VERI_YOK)
        self.assertIsNotNone(satirlar[1]["sira"])
        self.assertEqual(satirlar[0]["puan"], satirlar[1]["puan"])

    def test_veri_durumu_model_resmi_degil(self):
        durum = re.veri_durumu()
        self.assertFalse(durum["model"]["resmi_mi"])
        self.assertEqual(durum["model"]["dogrulama_durumu"], "dogrulanmadi")
        self.assertIn("2026", durum["model"]["yillar"])
        self.assertEqual(durum["siralama"]["kayit_sayisi"], 0)
        self.assertIn("sinirlilik", durum["model"]["kaynak"])


class DenemeVerisiTest(SimulatorTestTabani):
    """Deneme verisinden otomatik net alma davranışı."""

    def test_deneme_yoksa_bos_doner(self):
        sonuc = re.mevcut_netler(self.ogrenci)
        self.assertFalse(sonuc["kayit_var"])
        self.assertEqual(sonuc["tyt"], {})
        self.assertIsNone(sonuc["yontem"])

    def test_tek_denemenin_netleri(self):
        self.deneme_ekle("TYT", "2026-11-01", TYT_NETLER)
        sonuc = re.mevcut_netler(self.ogrenci)
        self.assertTrue(sonuc["kayit_var"])
        self.assertEqual(sonuc["tyt"]["TYT Türkçe"], 30.0)
        self.assertEqual(sonuc["deneme_sayisi"]["TYT"], 1)
        self.assertIn("Son genel denemenin", sonuc["yontem"])

    def test_son_n_denemenin_ortalamasi(self):
        self.deneme_ekle("TYT", "2026-10-01", dict(TYT_NETLER, **{"TYT Türkçe": 10.0}))
        self.deneme_ekle("TYT", "2026-10-15", dict(TYT_NETLER, **{"TYT Türkçe": 20.0}))
        self.deneme_ekle("TYT", "2026-11-01", dict(TYT_NETLER, **{"TYT Türkçe": 40.0}))
        sonuc = re.mevcut_netler(self.ogrenci, son_deneme=2)
        self.assertEqual(sonuc["tyt"]["TYT Türkçe"], 30.0)
        self.assertEqual(sonuc["deneme_sayisi"]["TYT"], 2)
        self.assertIn("Son 2 genel denemenin", sonuc["yontem"])

    def test_ayt_netleri_ayri_toplanir(self):
        self.deneme_ekle("TYT", "2026-11-01", TYT_NETLER)
        self.deneme_ekle("AYT", "2026-11-02", SAY_NETLER)
        sonuc = re.mevcut_netler(self.ogrenci)
        self.assertEqual(sonuc["tyt"]["TYT Türkçe"], 30.0)
        self.assertEqual(sonuc["ayt"]["AYT Matematik"], 20.0)
        self.assertEqual(sonuc["deneme_sayisi"]["TYT"], 1)
        self.assertEqual(sonuc["deneme_sayisi"]["AYT"], 1)

    def test_brans_denemesi_hesaba_katilmaz(self):
        self.deneme_ekle("TYT", "2026-11-01", TYT_NETLER)
        self.deneme_ekle(
            "AYT",
            "2026-11-02",
            {"AYT Matematik": 40.0},
            kategori="Branş Denemesi",
        )
        sonuc = re.mevcut_netler(self.ogrenci)
        self.assertEqual(sonuc["ayt"], {})
        self.assertEqual(sonuc["kullanilan_denemeler"]["AYT"], [])

    def test_ogrenci_izolasyonu(self):
        diger = self.ogrenci_ekle("Başka Öğrenci")
        self.deneme_ekle("TYT", "2026-11-01", TYT_NETLER, ogrenci_id=diger)
        sonuc = re.mevcut_netler(self.ogrenci)
        self.assertFalse(sonuc["kayit_var"])

    def test_ders_sonucu_yoksa_uyari(self):
        self.deneme_ekle("TYT", "2026-11-01", TYT_NETLER, ders_sonucu_var=False)
        sonuc = re.mevcut_netler(self.ogrenci)
        self.assertFalse(sonuc["kayit_var"])
        self.assertTrue(any("ders bazlı net" in u for u in sonuc["uyarilar"]))

    def test_son_deneme_sinirlanir(self):
        for gun in range(1, 13):
            self.deneme_ekle(
                "TYT", "2026-10-%02d" % gun, dict(TYT_NETLER, **{"TYT Türkçe": 10.0})
            )
        sonuc = re.mevcut_netler(self.ogrenci, son_deneme=99)
        self.assertEqual(sonuc["deneme_sayisi"]["TYT"], re.MAKS_SON_DENEME)

    def test_gecersiz_ogrenci(self):
        with self.assertRaises(re.SimulatorHatasi):
            re.mevcut_netler(0)


class HedefNetTest(SimulatorTestTabani):
    """Hedef netler ayrı kaynakta tutulur; mevcut netlerin üzerine yazılmaz."""

    def test_kaydet_ve_getir(self):
        hedefler = re.hedef_netleri_kaydet(
            self.ogrenci,
            "Sayısal",
            {"TYT Türkçe": 35.0, "AYT Matematik": 30.0},
        )
        self.assertEqual(hedefler["TYT Türkçe"], 35.0)
        self.assertEqual(
            re.hedef_netleri_getir(self.ogrenci, "Sayısal"),
            {"TYT Türkçe": 35.0, "AYT Matematik": 30.0},
        )

    def test_guncelleme_tek_kayit(self):
        re.hedef_netleri_kaydet(self.ogrenci, "Sayısal", {"TYT Türkçe": 30.0})
        re.hedef_netleri_kaydet(self.ogrenci, "Sayısal", {"TYT Türkçe": 38.0})
        conn = self.baglanti()
        try:
            adet = conn.execute(
                "SELECT COUNT(*) AS adet FROM ogrenci_hedef_netleri WHERE"
                " ogrenci_id = ? AND test = ?",
                (self.ogrenci, "TYT Türkçe"),
            ).fetchone()["adet"]
        finally:
            conn.close()
        self.assertEqual(adet, 1)
        self.assertEqual(
            re.hedef_netleri_getir(self.ogrenci, "Sayısal")["TYT Türkçe"], 38.0
        )

    def test_mevcut_netler_degismez(self):
        self.deneme_ekle("TYT", "2026-11-01", TYT_NETLER)
        once = re.mevcut_netler(self.ogrenci)
        re.hedef_netleri_kaydet(
            self.ogrenci, "Sayısal", {"TYT Türkçe": 39.0, "AYT Matematik": 35.0}
        )
        sonra = re.mevcut_netler(self.ogrenci)
        self.assertEqual(once["tyt"], sonra["tyt"])
        self.assertEqual(sonra["ayt"], {})

    def test_karsilastirma_farki(self):
        self.deneme_ekle("TYT", "2026-11-01", TYT_NETLER)
        self.deneme_ekle("AYT", "2026-11-02", SAY_NETLER)
        re.hedef_netleri_kaydet(
            self.ogrenci,
            "Sayısal",
            {"TYT Türkçe": 35.0, "AYT Matematik": 30.0},
        )
        satirlar = re.hedef_karsilastirma(self.ogrenci, "Sayısal")
        sozluk = {s["test"]: s for s in satirlar}
        self.assertEqual(sozluk["TYT Türkçe"]["mevcut"], 30.0)
        self.assertEqual(sozluk["TYT Türkçe"]["hedef"], 35.0)
        self.assertEqual(sozluk["TYT Türkçe"]["fark"], -5.0)
        self.assertEqual(sozluk["TYT Türkçe"]["durum"], "hedefin_altinda")
        self.assertIsNone(sozluk["AYT Fizik"]["hedef"])
        self.assertEqual(sozluk["AYT Fizik"]["durum"], "hedef_yok")

    def test_hedefte_durumu(self):
        self.deneme_ekle("TYT", "2026-11-01", TYT_NETLER)
        re.hedef_netleri_kaydet(self.ogrenci, "TYT", {"TYT Türkçe": 25.0})
        satirlar = {
            s["test"]: s for s in re.hedef_karsilastirma(self.ogrenci, "TYT")
        }
        self.assertEqual(satirlar["TYT Türkçe"]["durum"], "hedefte")

    def test_dogrulama_hatalari(self):
        with self.assertRaises(re.SimulatorHatasi):
            re.hedef_netleri_kaydet(self.ogrenci, "TYT", {"AYT Fizik": 5.0})
        with self.assertRaises(re.SimulatorHatasi):
            re.hedef_netleri_kaydet(self.ogrenci, "TYT", {"TYT Türkçe": 41.0})
        with self.assertRaises(re.SimulatorHatasi):
            re.hedef_netleri_kaydet(self.ogrenci, "TYT", {"TYT Türkçe": -1.0})
        with self.assertRaises(re.SimulatorHatasi):
            re.hedef_netleri_kaydet(self.ogrenci, "TYT", {})

    def test_silme(self):
        re.hedef_netleri_kaydet(self.ogrenci, "TYT", {"TYT Türkçe": 30.0})
        self.assertEqual(re.hedef_netleri_sil(self.ogrenci, "TYT"), 1)
        self.assertEqual(re.hedef_netleri_getir(self.ogrenci, "TYT"), {})

    def test_ogrenci_izolasyonu(self):
        diger = self.ogrenci_ekle("Başka Öğrenci")
        re.hedef_netleri_kaydet(diger, "TYT", {"TYT Türkçe": 35.0})
        self.assertEqual(re.hedef_netleri_getir(self.ogrenci, "TYT"), {})

    def test_hedef_net_puana_donusur(self):
        hedefler = dict(SAY_NETLER)
        hedefler["AYT Matematik"] = 32.0
        re.hedef_netleri_kaydet(self.ogrenci, "Sayısal", {"AYT Matematik": 32.0})
        mevcut = re.puan_hesapla(SAY_NETLER, "Sayısal", "2026", 85.0)
        hedef = re.puan_hesapla(hedefler, "Sayısal", "2026", 85.0)
        self.assertGreater(hedef["puan"], mevcut["puan"])
        self.assertEqual(
            hedef["ham_puan"] - mevcut["ham_puan"], round(12 * 3.0, 2)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)








