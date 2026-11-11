"""FAZ 6B - Yanlış soru defteri servis testleri.

Kapsam:

- Kayıt oluşturma, zorunlu alan / hata türü doğrulaması, mükerrer koruması.
- Öğrenci izolasyonu (başka öğrencinin kaydı okunamaz / güncellenemez).
- Durum yaşam döngüsü: Yeni -> Tekrar Bekliyor -> Öğrenildi, arşivleme ve
  yeniden açma; tekrar sayacı kuralları (idempotent "çözdüm").
- Programa beslenen havuz (`bekleyen_yanlis_sorular`) ve pencere filtresi.
- Defter sayaçları (`yanlis_soru_ozeti`) ve liste filtreleri.

Testler geçici bir SQLite dosyası ve sabit bir saat kullanır; gerçek
`yks_veritabani.db` dosyasına dokunulmaz.

Çalıştırma:
    python tests/test_wrong_questions.py
    python -m unittest discover -s tests -v
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(TEST_KOK)
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from services import wrong_questions as wq  # noqa: E402

# Testlerde "şimdi" sabittir: tekrar tarihleri deterministik olur.
SIMDI = datetime(2026, 11, 9, 10, 0, tzinfo=wq.TR_TZ)
OGRENCI = 1
DIGER_OGRENCI = 2

_OGRENCI_SEMASI = """
CREATE TABLE IF NOT EXISTS ogrenciler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tc_no TEXT UNIQUE,
    kullanici_adi TEXT UNIQUE,
    sifre_hash TEXT,
    ad TEXT
)
"""


class YanlisSoruTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="faz6b_")
        self.db_yolu = os.path.join(self.klasor, "test.db")
        wq.db_yolu_ayarla(self.db_yolu)
        wq.saat_fonksiyonu_ayarla(lambda: SIMDI)
        conn = sqlite3.connect(self.db_yolu)
        conn.executescript(_OGRENCI_SEMASI)
        conn.execute(
            "INSERT INTO ogrenciler (id, tc_no, kullanici_adi) VALUES (1, '1', 'ogr1')"
        )
        conn.execute(
            "INSERT INTO ogrenciler (id, tc_no, kullanici_adi) VALUES (2, '2', 'ogr2')"
        )
        conn.commit()
        conn.close()
        wq.init_db()

    def tearDown(self):
        wq.db_yolu_ayarla(None)
        wq.saat_fonksiyonu_ayarla(None)
        shutil.rmtree(self.klasor, ignore_errors=True)

    def _ekle(self, **alanlar):
        ogrenci_id = alanlar.pop("ogrenci_id", OGRENCI)
        veri = {
            "ders": "AYT Matematik",
            "mikro_konu": "Polinomlar ve Çarpanlara Ayırma",
            "makro_konu": "İleri Cebir ve Fonksiyonlar",
        }
        veri.update(alanlar)
        return wq.yanlis_soru_ekle(ogrenci_id, **veri)

    def test_ekle_varsayilanlar(self):
        kayit = self._ekle(soru_metni="x^2 - 5x + 6 köklerini bul")
        self.assertEqual(kayit["durum"], wq.DURUM_YENI)
        self.assertEqual(kayit["tekrar_sayisi"], 0)
        self.assertTrue(kayit["aktif"])
        self.assertTrue(kayit["bekliyor"])
        self.assertEqual(kayit["sonraki_tekrar_tarihi"], SIMDI.date().isoformat())
        self.assertTrue(kayit["bugun"])
        self.assertFalse(kayit["gecikmis"])
        self.assertIsNone(kayit["alt_konu"])
        self.assertEqual(kayit["hata_turu"], wq.VARSAYILAN_HATA_TURU)
        self.assertEqual(kayit["olusturma_zamani"], "2026-11-09 10:00:00")

    def test_zorunlu_alan_ve_hata_turu_dogrulama(self):
        with self.assertRaises(wq.YanlisSoruHatasi):
            self._ekle(ders="   ")
        with self.assertRaises(wq.YanlisSoruHatasi):
            self._ekle(mikro_konu="")
        with self.assertRaises(wq.YanlisSoruHatasi):
            self._ekle(hata_turu="Uydurma Hata")
        with self.assertRaises(wq.YanlisSoruHatasi):
            wq.yanlis_soru_ekle(0, "AYT Matematik", "Polinomlar")

    def test_mukerrer_kayit_engellenir(self):
        ilk = self._ekle(soru_metni="Aynı soru metni")
        with self.assertRaises(wq.YanlisSoruHatasi):
            self._ekle(soru_metni="Aynı soru metni")
        # Öğrenildi işaretlenen kayıt mükerrer sayılmaz: yeniden eklenebilir.
        wq.ogrenildi_isaretle(ilk["id"], ogrenci_id=OGRENCI)
        ikinci = self._ekle(soru_metni="Aynı soru metni")
        self.assertNotEqual(ilk["id"], ikinci["id"])

    def test_ogrenci_izolasyonu(self):
        kayit = self._ekle(soru_metni="İzolasyon testi")
        with self.assertRaises(wq.YanlisSoruHatasi):
            wq.yanlis_soru_getir(kayit["id"], ogrenci_id=DIGER_OGRENCI)
        with self.assertRaises(wq.YanlisSoruHatasi):
            wq.ogrenildi_isaretle(kayit["id"], ogrenci_id=DIGER_OGRENCI)
        self.assertEqual(wq.yanlis_sorulari_getir(DIGER_OGRENCI), [])
        self.assertEqual(
            len(wq.yanlis_sorulari_getir(OGRENCI)), 1
        )

    def test_tekrar_yapilamadi_havuza_doner(self):
        kayit = self._ekle(soru_metni="Tekrar testi")
        sonuc = wq.tekrar_sonucu_kaydet(kayit["id"], False, ogrenci_id=OGRENCI)
        self.assertEqual(sonuc["durum"], wq.DURUM_TEKRAR)
        self.assertEqual(sonuc["tekrar_sayisi"], 1)
        self.assertEqual(sonuc["son_tekrar_tarihi"], SIMDI.date().isoformat())
        self.assertEqual(
            sonuc["sonraki_tekrar_tarihi"],
            (SIMDI.date() + timedelta(days=wq.TEKRAR_ARALIGI_GUN)).isoformat(),
        )
        self.assertTrue(sonuc["bekliyor"])
        self.assertIsNone(sonuc["ogrenme_tarihi"])

    def test_cozuldu_ogrenildi_ve_idempotent(self):
        kayit = self._ekle(soru_metni="Çözüldü testi")
        sonuc = wq.tekrar_sonucu_kaydet(kayit["id"], True, ogrenci_id=OGRENCI)
        self.assertEqual(sonuc["durum"], wq.DURUM_OGRENILDI)
        self.assertEqual(sonuc["ogrenme_tarihi"], SIMDI.date().isoformat())
        self.assertIsNone(sonuc["sonraki_tekrar_tarihi"])
        self.assertFalse(sonuc["bekliyor"])
        # Aynı işlem ikinci kez çalışırsa sayaç artmaz.
        tekrar = wq.tekrar_sonucu_kaydet(kayit["id"], True, ogrenci_id=OGRENCI)
        self.assertEqual(tekrar["tekrar_sayisi"], 1)
        self.assertEqual(tekrar["durum"], wq.DURUM_OGRENILDI)

    def test_ogrenildi_kayda_yapamadim_denemez_ve_yeniden_ac(self):
        kayit = self._ekle(soru_metni="Yeniden açma testi")
        wq.ogrenildi_isaretle(kayit["id"], ogrenci_id=OGRENCI)
        with self.assertRaises(wq.YanlisSoruHatasi):
            wq.tekrar_sonucu_kaydet(kayit["id"], False, ogrenci_id=OGRENCI)
        acilan = wq.yeniden_ac(kayit["id"], ogrenci_id=OGRENCI)
        self.assertEqual(acilan["durum"], wq.DURUM_TEKRAR)
        self.assertIsNone(acilan["ogrenme_tarihi"])
        self.assertEqual(acilan["sonraki_tekrar_tarihi"], SIMDI.date().isoformat())
        self.assertTrue(acilan["bekliyor"])

    def test_arsiv_yasam_dongusu(self):
        kayit = self._ekle(soru_metni="Arşiv testi")
        arsiv = wq.arsivle(kayit["id"], ogrenci_id=OGRENCI)
        self.assertEqual(arsiv["durum"], wq.DURUM_ARSIV)
        self.assertEqual(arsiv["aktif"], 0)
        self.assertIsNone(arsiv["sonraki_tekrar_tarihi"])
        # Arşivdeki kayıt düzenlenemez ve tekrar sonucu alamaz.
        with self.assertRaises(wq.YanlisSoruHatasi):
            wq.yanlis_soru_guncelle(
                kayit["id"], ogrenci_id=OGRENCI, notlar="olmaz"
            )
        with self.assertRaises(wq.YanlisSoruHatasi):
            wq.tekrar_sonucu_kaydet(kayit["id"], True, ogrenci_id=OGRENCI)
        geri = wq.arsivden_cikar(kayit["id"], ogrenci_id=OGRENCI)
        self.assertEqual(geri["durum"], wq.DURUM_TEKRAR)
        self.assertEqual(geri["aktif"], 1)
        self.assertTrue(geri["bekliyor"])

    def test_bekleyen_havuzu_pencere_filtresi(self):
        bugun_kayit = self._ekle(soru_metni="Bugün tekrar")
        yapamadi = self._ekle(soru_metni="İki gün sonra tekrar")
        wq.tekrar_sonucu_kaydet(yapamadi["id"], False, ogrenci_id=OGRENCI)
        ogrenilen = self._ekle(soru_metni="Öğrenildi olan")
        wq.ogrenildi_isaretle(ogrenilen["id"], ogrenci_id=OGRENCI)

        hafta_basi = wq.bekleyen_yanlis_sorular(
            OGRENCI, gun=SIMDI.date(), bitis=SIMDI.date()
        )
        self.assertEqual([k["id"] for k in hafta_basi], [bugun_kayit["id"]])

        pencere_sonu = SIMDI.date() + timedelta(days=wq.TEKRAR_ARALIGI_GUN)
        pencere = wq.bekleyen_yanlis_sorular(
            OGRENCI, gun=SIMDI.date(), bitis=pencere_sonu
        )
        self.assertEqual(
            sorted(k["id"] for k in pencere),
            sorted([bugun_kayit["id"], yapamadi["id"]]),
        )
        self.assertNotIn(ogrenilen["id"], [k["id"] for k in pencere])

    def test_ozet_sayaclari(self):
        self._ekle(soru_metni="Yeni kayıt")
        gecikmis = self._ekle(
            soru_metni="Gecikmiş kayıt", an=SIMDI - timedelta(days=5)
        )
        yapamadi = self._ekle(soru_metni="Tekrar bekleyen")
        wq.tekrar_sonucu_kaydet(yapamadi["id"], False, ogrenci_id=OGRENCI)
        ogrenilen = self._ekle(soru_metni="Öğrenilmiş")
        wq.ogrenildi_isaretle(ogrenilen["id"], ogrenci_id=OGRENCI)
        arsiv = self._ekle(soru_metni="Arşivlenmiş")
        wq.arsivle(arsiv["id"], ogrenci_id=OGRENCI)

        ozet = wq.yanlis_soru_ozeti(OGRENCI)
        self.assertEqual(ozet["toplam"], 5)
        self.assertEqual(ozet["yeni"], 2)
        self.assertEqual(ozet["tekrar"], 1)
        self.assertEqual(ozet["ogrenildi"], 1)
        self.assertEqual(ozet["arsiv"], 1)
        self.assertEqual(ozet["bekleyen"], 3)
        self.assertEqual(ozet["gecikmis"], 1)
        self.assertEqual(ozet["bugun"], 1)
        self.assertEqual(ozet["dersler"]["AYT Matematik"]["toplam"], 5)
        self.assertEqual(ozet["dersler"]["AYT Matematik"]["bekleyen"], 3)
        self.assertEqual(ozet["dersler"]["AYT Matematik"]["ogrenildi"], 1)
        self.assertIsNotNone(gecikmis["id"])

    def test_liste_filtreleri_ve_arama(self):
        polinom = self._ekle(soru_metni="Kökler toplamı", notlar="işaret hatası")
        turev = self._ekle(
            ders="AYT Matematik", mikro_konu="Türev", soru_metni="Zincir kuralı"
        )
        wq.ogrenildi_isaretle(turev["id"], ogrenci_id=OGRENCI)

        aktifler = wq.yanlis_sorulari_getir(OGRENCI, sadece_aktif=True)
        self.assertEqual([k["id"] for k in aktifler], [polinom["id"]])
        tumu = wq.yanlis_sorulari_getir(OGRENCI)
        self.assertEqual(len(tumu), 2)
        # Yeni kayıtlar önce gelir (id DESC).
        self.assertEqual(tumu[0]["id"], turev["id"])

        arama = wq.yanlis_sorulari_getir(OGRENCI, arama="zincir")
        self.assertEqual([k["id"] for k in arama], [turev["id"]])
        nota_gore = wq.yanlis_sorulari_getir(OGRENCI, arama="işaret")
        self.assertEqual([k["id"] for k in nota_gore], [polinom["id"]])
        konuya_gore = wq.yanlis_sorulari_getir(OGRENCI, durum=wq.DURUM_OGRENILDI)
        self.assertEqual([k["id"] for k in konuya_gore], [turev["id"]])
        with self.assertRaises(wq.YanlisSoruHatasi):
            wq.yanlis_sorulari_getir(OGRENCI, durum="Bilinmeyen")

    def test_tekrar_edildi_ogrenilmis_kaydi_degistirmez(self):
        kayit = self._ekle(soru_metni="Sayaç testi")
        birinci = wq.tekrar_edildi(kayit["id"], ogrenci_id=OGRENCI)
        self.assertEqual(birinci["tekrar_sayisi"], 1)
        self.assertEqual(birinci["durum"], wq.DURUM_TEKRAR)
        wq.ogrenildi_isaretle(kayit["id"], ogrenci_id=OGRENCI)
        sonra = wq.tekrar_edildi(kayit["id"], ogrenci_id=OGRENCI)
        self.assertEqual(sonra["durum"], wq.DURUM_OGRENILDI)
        self.assertEqual(sonra["tekrar_sayisi"], 2)

    def test_guncelle_alanlari_ve_not_yazimi(self):
        kayit = self._ekle(soru_metni="Güncelleme testi")
        guncel = wq.yanlis_soru_guncelle(
            kayit["id"],
            ogrenci_id=OGRENCI,
            alt_konu="Kökler",
            notlar="Katsayıları yanlış okudum",
            hata_turu="Soruyu Yanlış Okudum",
        )
        self.assertEqual(guncel["alt_konu"], "Kökler")
        self.assertEqual(guncel["notlar"], "Katsayıları yanlış okudum")
        self.assertEqual(guncel["hata_turu"], "Soruyu Yanlış Okudum")
        self.assertIsNotNone(guncel["guncelleme_zamani"])
        with self.assertRaises(wq.YanlisSoruHatasi):
            wq.yanlis_soru_guncelle(kayit["id"], ogrenci_id=OGRENCI, durum="X")


if __name__ == "__main__":
    unittest.main(verbosity=2)

