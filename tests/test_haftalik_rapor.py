"""FAZ 7 - Haftalık performans raporu testleri (services/weekly_report.py).

Kapsam: hafta matematiği, kaynak veriden metrik üretimi, öğrenci izolasyonu,
tarih sınırları, eşit uzunlukta karşılaştırma, tekrar/deneme/defter özetleri,
yorum motorunun deterministik kuralları ve çok haftalık seri/trend yardımcıları.

Çalıştırma:
    python tests/test_haftalik_rapor.py
"""
import os
import sys
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from haftalik_verisi import (  # noqa: E402
    CARSAMBA,
    CUMA,
    ONCEKI_CARSAMBA,
    ONCEKI_PAZARTESI,
    ONCEKI_SALI,
    PAZAR,
    PAZARTESI,
    PERSEMBE,
    SALI,
    SIMDI,
    SONRAKI_PAZARTESI,
    TR_TZ,
    HaftalikTestTabani,
)
from services import weekly_report as wr  # noqa: E402

# Hafta tamamlandıktan sonraki Pazartesi: karşılaştırma "tam hafta" olur.
SONRAKI_AN = datetime(2026, 11, 16, 9, 0, tzinfo=TR_TZ)


class HaftaMatematigiTest(unittest.TestCase):
    """Hafta = Pazartesi..Pazar; TR saat dilimi; tarih sınırları."""

    def test_hafta_basi_her_gun_pazartesiye_duser(self):
        for gun in (
            date(2026, 11, 9),
            date(2026, 11, 11),
            date(2026, 11, 15),
        ):
            self.assertEqual(wr.hafta_basi(gun), date(2026, 11, 9))
        self.assertEqual(wr.hafta_basi(date(2026, 11, 16)), date(2026, 11, 16))

    def test_metin_ve_datetime_girdileri_kabul_edilir(self):
        self.assertEqual(wr.hafta_basi("2026-11-13"), date(2026, 11, 9))
        self.assertEqual(
            wr.hafta_basi(datetime(2026, 11, 13, 23, 30, tzinfo=TR_TZ)),
            date(2026, 11, 9),
        )

    def test_gecersiz_tarih_hata_verir(self):
        with self.assertRaises(wr.HaftalikRaporHatasi):
            wr.hafta_basi("13/11/2026")
        with self.assertRaises(wr.HaftalikRaporHatasi):
            wr.hafta_basi("2026-13-45")

    def test_aralik_iso_ve_etiket(self):
        bas, bit = wr.hafta_araligi(date(2026, 11, 11))
        self.assertEqual(bas, date(2026, 11, 9))
        self.assertEqual(bit, date(2026, 11, 15))
        self.assertEqual(wr.hafta_iso("2026-11-11"), "2026-11-09")
        self.assertEqual(
            wr.hafta_etiketi("2026-11-11"), "9 Kasım Pazartesi – 15 Kasım Pazar"
        )

    def test_onceki_ve_sonraki_hafta(self):
        self.assertEqual(wr.onceki_hafta("2026-11-09"), date(2026, 11, 2))
        self.assertEqual(wr.sonraki_hafta("2026-11-09"), date(2026, 11, 16))
        # Hafta sınırı geçişi (yılbaşı) doğru hesaplanır.
        self.assertEqual(wr.hafta_basi("2027-01-01"), date(2026, 12, 28))
        self.assertEqual(wr.onceki_hafta("2027-01-01"), date(2026, 12, 21))

    def test_hafta_secenekleri_ve_devam_bilgisi(self):
        secenekler = wr.hafta_secenekleri(4, an=SIMDI)
        self.assertEqual(len(secenekler), 4)
        self.assertEqual(secenekler[0]["baslangic"], "2026-11-09")
        self.assertTrue(secenekler[0]["devam_ediyor"])
        self.assertEqual(secenekler[-1]["baslangic"], "2026-10-19")
        self.assertFalse(secenekler[-1]["devam_ediyor"])

    def test_saat_metni_bicimi(self):
        self.assertEqual(wr._saat_metni(0), "0 dk")
        self.assertEqual(wr._saat_metni(45), "45 dk")
        self.assertEqual(wr._saat_metni(60), "1 sa")
        self.assertEqual(wr._saat_metni(255), "4 sa 15 dk")



class MetrikTest(HaftalikTestTabani):
    """Kaynak tablolardan üretilen metrikler (canlı hesap, snapshot yok)."""

    def test_bos_hafta_sifir_ve_veri_yok(self):
        rapor = wr.rapor_uret(self.ogrenci, "2026-01-05")
        self.assertFalse(rapor["veri_var"])
        self.assertEqual(rapor["ozet"]["dk"], 0)
        self.assertEqual(rapor["ozet"]["soru"], 0)
        self.assertEqual(rapor["yorumlar"][0]["kod"], "veri_yok")
        self.assertFalse(rapor["karsilastirma"]["kullanilabilir"])
        self.assertFalse(rapor["snapshot"])

    def test_oturumlar_sure_soru_ve_aktif_gun(self):
        # Pazartesi 90 dk, Salı 15 dk (eşik), Çarşamba 10 dk (eşik altı)
        self.oturum_ekle(PAZARTESI, dk=90, soru=30)
        self.oturum_ekle(SALI, dk=15, soru=5, saat="09:00:00")
        self.oturum_ekle(CARSAMBA, dk=10, soru=4, saat="08:00:00")
        rapor = wr.rapor_uret(self.ogrenci, CARSAMBA)
        self.assertEqual(rapor["ozet"]["dk"], 115)
        self.assertEqual(rapor["ozet"]["soru"], 39)
        # Aktif gün: süre/soru > 0 olan gün (eşiğe bakmaz) -> 3 gün
        self.assertEqual(rapor["ozet"]["aktif_gun"], 3)
        # Seri günü eşiği 15 dk -> 2 gün
        self.assertEqual(rapor["calisma"]["seri_gun"], 2)
        self.assertEqual(rapor["calisma"]["aktif_gun_esik_dk"], 15)

    def test_devam_eden_hafta_olculen_gun(self):
        rapor = wr.rapor_uret(self.ogrenci, CARSAMBA)
        self.assertEqual(rapor["hafta"]["durum"], "devam")
        self.assertEqual(rapor["hafta"]["olculen_gun"], 3)
        self.assertEqual(rapor["hafta"]["bitis_etkin"], CARSAMBA)
        self.assertEqual(rapor["hafta"]["bitis"], PAZAR)
        self.assertTrue(rapor["hafta"]["devam_ediyor"])

    def test_tamamlanan_hafta_tum_gunleri_olcer(self):
        rapor = wr.rapor_uret(
            self.ogrenci, PAZARTESI, an=datetime(2026, 11, 16, 9, 0, tzinfo=TR_TZ)
        )
        self.assertEqual(rapor["hafta"]["durum"], "tamamlandi")
        self.assertEqual(rapor["hafta"]["olculen_gun"], 7)
        self.assertEqual(rapor["hafta"]["bitis_etkin"], PAZAR)

    def test_gelecek_hafta_veri_okumaz(self):
        self.oturum_ekle(PAZARTESI, dk=60, soru=20)
        rapor = wr.rapor_uret(self.ogrenci, SONRAKI_PAZARTESI)
        self.assertEqual(rapor["hafta"]["durum"], "gelecek")
        self.assertEqual(rapor["ozet"]["dk"], 0)
        self.assertEqual(rapor["ozet"]["aktif_gun"], 0)
        self.assertFalse(rapor["karsilastirma"]["kullanilabilir"])

    def test_pencere_disi_kayitlar_sayilmaz(self):
        self.oturum_ekle(PAZAR, dk=60, soru=20)  # haftanın son günü: dahil
        self.oturum_ekle("2026-11-16", dk=50, soru=10)  # sonraki Pazartesi
        self.oturum_ekle("2026-11-08", dk=40, soru=8)  # önceki Pazar
        rapor = wr.rapor_uret(
            self.ogrenci, PAZAR, an=datetime(2026, 11, 16, 9, 0, tzinfo=TR_TZ)
        )
        self.assertEqual(rapor["ozet"]["dk"], 60)
        self.assertEqual(rapor["ozet"]["soru"], 20)

    def test_saat_siniri_pazar_aksami_dahil(self):
        # 23:59'da başlayan oturum o haftaya aittir (gün bazlı filtre).
        self.oturum_ekle(PAZAR, dk=30, soru=10, saat="23:59:00")
        rapor = wr.rapor_uret(
            self.ogrenci, PAZAR, an=datetime(2026, 11, 16, 9, 0, tzinfo=TR_TZ)
        )
        self.assertEqual(rapor["ozet"]["dk"], 30)

    def test_iptal_edilen_oturum_sayilmaz(self):
        self.oturum_ekle(PAZARTESI, dk=60, soru=20)
        self.oturum_ekle(SALI, dk=90, soru=30, durum="İptal Edildi")
        rapor = wr.rapor_uret(self.ogrenci, SALI)
        self.assertEqual(rapor["ozet"]["dk"], 60)

    def test_ogrenci_izolasyonu(self):
        diger = self.ogrenci_ekle("Diğer Öğrenci")
        self.oturum_ekle(PAZARTESI, dk=60, soru=20)
        self.oturum_ekle(PAZARTESI, dk=300, soru=120, ogrenci_id=diger)
        self.gorev_ekle(PAZARTESI, durum=1)
        self.gorev_ekle(PAZARTESI, durum=1, ogrenci_id=diger)
        rapor = wr.rapor_uret(self.ogrenci, PAZARTESI)
        self.assertEqual(rapor["ozet"]["dk"], 60)
        self.assertEqual(rapor["gorevler"]["planlanan"], 1)
        self.assertEqual(rapor["gorevler"]["tamamlanan"], 1)

    def test_gecersiz_ogrenci_hata_verir(self):
        with self.assertRaises(wr.HaftalikRaporHatasi):
            wr.rapor_uret(999999, PAZARTESI)
        with self.assertRaises(wr.HaftalikRaporHatasi):
            wr.rapor_uret("abc", PAZARTESI)

    def test_ders_dagilimi_sure_ve_soru(self):
        self.oturum_ekle(PAZARTESI, dk=120, soru=40, ders="TYT Matematik")
        self.oturum_ekle(SALI, dk=60, soru=30, ders="TYT Türkçe")
        rapor = wr.rapor_uret(self.ogrenci, SALI)
        dersler = rapor["dersler"]
        self.assertEqual(dersler[0]["ders"], "TYT Matematik")
        self.assertEqual(dersler[0]["dk"], 120)
        self.assertEqual(dersler[1]["ders"], "TYT Türkçe")
        self.assertEqual(rapor["_metrik"]["ders_dk"]["TYT Türkçe"], 60)

    def test_sorulari_isaretlenmemis_oturumda_basari_orani_yok(self):
        self.oturum_ekle(PAZARTESI, dk=60, soru=20)
        rapor = wr.rapor_uret(self.ogrenci, PAZARTESI)
        self.assertIsNone(rapor["calisma"]["basari_orani"])
        self.oturum_ekle(PAZARTESI, dk=30, soru=10, dogru=8, yanlis=2, bos=0)
        rapor = wr.rapor_uret(self.ogrenci, PAZARTESI)
        self.assertEqual(rapor["calisma"]["dogru"], 8)
        self.assertEqual(rapor["calisma"]["basari_orani"], 80.0)


class GorevVeDenemeTest(HaftalikTestTabani):
    """Program görevleri, devirler ve denemeler (tekrar sayılmama)."""

    def _calisma_oturumu_ile_gorev(self, tarih, tamam=True):
        gid = self.gorev_ekle(tarih, durum=1 if tamam else 0)
        self.oturum_ekle(tarih, dk=60, soru=20, gorev_id=gid)
        self.oturum_ekle(tarih, dk=30, soru=10, gorev_id=gid, saat="18:00:00")
        return gid

    def test_ayni_gorev_iki_oturumda_bir_gorev_sayilir(self):
        self._calisma_oturumu_ile_gorev(PAZARTESI)
        rapor = wr.rapor_uret(self.ogrenci, PAZARTESI)
        gorevler = rapor["gorevler"]
        self.assertEqual(gorevler["planlanan"], 1)
        self.assertEqual(gorevler["tamamlanan"], 1)
        self.assertEqual(gorevler["uyum"], 100.0)
        # Süre/soru oturum bazında toplanır: aynı görevin iki oturumu var.
        self.assertEqual(gorevler["gercek_dk"], 90)
        self.assertEqual(rapor["ozet"]["dk"], 90)
        self.assertEqual(rapor["ozet"]["soru"], 30)

    def test_uyum_orani_ve_gecersiz_gorev_paydadan_cikar(self):
        g1 = self.gorev_ekle(PAZARTESI, durum=1, tahmini_sure_dk=90)
        self.gorev_ekle(SALI, durum=0, tahmini_sure_dk=60)
        self.gorev_ekle(CARSAMBA, durum=0, gecersiz=1, tahmini_sure_dk=45)
        self.oturum_ekle(PAZARTESI, dk=90, soru=30, gorev_id=g1)
        rapor = wr.rapor_uret(self.ogrenci, CARSAMBA)
        gorevler = rapor["gorevler"]
        self.assertEqual(gorevler["planlanan"], 2)
        self.assertEqual(gorevler["gecersiz"], 1)
        self.assertEqual(gorevler["uyum"], 50.0)
        self.assertEqual(gorevler["planlanan_dk"], 150)
        self.assertEqual(gorevler["gercek_dk"], 90)
        self.assertEqual(gorevler["program_disi_dk"], 0)

    def test_program_disi_oturum_ve_bekleyen_kart(self):
        self.oturum_ekle(PAZARTESI, dk=45, soru=15)  # gorev_id yok
        self.gorev_ekle(SALI, durum=0)
        rapor = wr.rapor_uret(self.ogrenci, PERSEMBE)
        self.assertEqual(rapor["gorevler"]["program_disi_dk"], 45)
        self.assertEqual(rapor["gorevler"]["tamamlanmayan_sayisi"], 1)
        kart = rapor["gorevler"]["bekleyen_kartlar"][0]
        self.assertTrue(kart["gecikmis"])

    def test_devir_gelen_ve_giden(self):
        onceki = self.gorev_ekle(ONCEKI_PAZARTESI, durum=0)
        yeni = self.gorev_ekle(PAZARTESI, durum=0, kaynak_gorev_id=onceki)
        sonraki = self.gorev_ekle(SONRAKI_PAZARTESI, durum=0)
        self.devir_ekle(yeni, sonraki, soru=12, sure=40)
        rapor = wr.rapor_uret(self.ogrenci, PAZARTESI)
        gorevler = rapor["gorevler"]
        self.assertEqual(gorevler["devir_gelen"], 1)
        self.assertEqual(gorevler["devir_giden"], 1)
        self.assertEqual(gorevler["devredilen_soru"], 12)

    def test_deneme_neti_dogru_yanlistan_hesaplanir(self):
        self.deneme_ekle(CUMA, dogru=80, yanlis=20, bos=0)
        rapor = wr.rapor_uret(self.ogrenci, CUMA, an=SONRAKI_AN)
        self.assertEqual(rapor["ozet"]["deneme_adet"], 1)
        self.assertEqual(rapor["ozet"]["deneme_net"], 75.0)
        self.assertEqual(rapor["denemeler"]["netler"][0]["net"], 75.0)

    def test_deneme_neti_ve_ders_kirilimi(self):
        self.deneme_ekle(
            CUMA,
            dogru=60,
            yanlis=20,
            ders_sonuclari=[
                ("TYT Matematik", 30, 5, 5),
                ("TYT Türkçe", 30, 15, 5),
            ],
        )
        self.deneme_ekle(SALI, dogru=40, yanlis=0, tur="AYT")
        rapor = wr.rapor_uret(self.ogrenci, CUMA, an=SONRAKI_AN)
        denemeler = rapor["denemeler"]
        self.assertEqual(denemeler["adet"], 2)
        # (55.0 + 40.0) / 2
        self.assertEqual(denemeler["net_ort"], 47.5)
        dersler = {d["ders"]: d for d in denemeler["dersler"]}
        self.assertEqual(dersler["TYT Matematik"]["net_ort"], 28.75)
        self.assertEqual(dersler["TYT Türkçe"]["net_ort"], 26.25)

    def test_baska_ogrencinin_denemesi_sayilmaz(self):
        diger = self.ogrenci_ekle("Deneme Öğrencisi")
        self.deneme_ekle(CUMA, dogru=80, yanlis=20)
        self.deneme_ekle(CUMA, dogru=10, yanlis=10, ogrenci_id=diger)
        rapor = wr.rapor_uret(self.ogrenci, CUMA, an=SONRAKI_AN)
        self.assertEqual(rapor["ozet"]["deneme_adet"], 1)


class TekrarVeDefterTest(HaftalikTestTabani):
    """Aralıklı tekrar akışı ve yanlış soru defteri sayaçları."""

    def test_tekrar_planlanan_tamamlanan_ve_gecikmis(self):
        self.tekrar_ekle(PAZARTESI, durum="Tamamlandı", tamamlanma="%s 20:00:00" % PAZARTESI)
        self.tekrar_ekle(PAZARTESI, mikro="Asal Sayılar")
        self.tekrar_ekle(CARSAMBA, mikro="Bölünebilme")
        # Önceki hafta planlanmış, bu hafta tamamlanmış -> gecikmiş tamamlanan
        self.tekrar_ekle(
            ONCEKI_SALI,
            durum="Tamamlandı",
            tamamlanma="%s 21:00:00" % SALI,
            mikro="Faktöriyel",
        )
        rapor = wr.rapor_uret(self.ogrenci, CARSAMBA)
        tekrar = rapor["tekrar"]
        self.assertEqual(tekrar["planlanan"], 3)
        self.assertEqual(tekrar["tamamlanan"], 1)
        self.assertEqual(tekrar["bekleyen"], 2)
        self.assertEqual(tekrar["gecikmis_tamamlanan"], 1)
        self.assertEqual(tekrar["tamamlama_orani"], 33.3)
        self.assertEqual(rapor["ozet"]["tekrar_planlanan"], 3)
        self.assertEqual(rapor["ozet"]["tamamlanan_tekrar"], 1)

    def test_gecikmis_bekleyen_bugune_gore_hesaplanir(self):
        self.tekrar_ekle(SALI, durum="Bekliyor")
        self.tekrar_ekle(CARSAMBA, durum="Bekliyor", mikro="Asal Sayılar")
        rapor = wr.rapor_uret(self.ogrenci, CARSAMBA)
        # Salı planlanan bekliyor (bugün Çarşamba) -> gecikmiş
        self.assertEqual(rapor["tekrar"]["gecikmis_bekleyen"], 1)
        self.assertEqual(rapor["tekrar"]["stok_bekleyen"], 2)

    def test_defter_eklenen_ogrenilen_ve_bekleyen(self):
        self.yanlis_soru_ekle(PAZARTESI)
        self.yanlis_soru_ekle(SALI, mikro="Asal Sayılar")
        # Önceki hafta eklenmiş, bu hafta öğrenilmiş
        self.yanlis_soru_ekle(
            ONCEKI_PAZARTESI,
            durum="Öğrenildi",
            ogrenme="%s" % CARSAMBA,
            mikro="Faktöriyel",
        )
        # Önceki hafta eklenmiş, hâlâ bekleyen
        self.yanlis_soru_ekle(ONCEKI_SALI, mikro="Bölünebilme")
        rapor = wr.rapor_uret(self.ogrenci, CARSAMBA)
        defter = rapor["defter"]
        self.assertEqual(defter["eklenen"], 2)
        self.assertEqual(defter["ogrenilen"], 1)
        # Hafta başında önceki haftadan devreden 2 soru bekliyordu; biri hafta
        # içinde öğrenildi. Hafta içinde eklenenler hafta başında yoktu.
        self.assertEqual(defter["baslangic_bekleyen"], 2)
        self.assertEqual(defter["bitis_bekleyen"], 3)
        self.assertEqual(defter["degisim"], 1)
        self.assertEqual(rapor["ozet"]["yanlis_eklenen"], 2)
        self.assertEqual(rapor["ozet"]["bekleyen_yanlis"], 3)

    def test_ayni_yanlis_soru_bir_kez_sayilir(self):
        # Aynı soru hafta içinde iki kez çözülse de tekrar sayısı 1'dir.
        self.yanlis_soru_ekle(
            ONCEKI_PAZARTESI,
            durum="Tekrar Bekliyor",
            son_tekrar="%s" % SALI,
            tekrar_sayisi=2,
        )
        rapor = wr.rapor_uret(self.ogrenci, CARSAMBA)
        self.assertEqual(rapor["defter"]["yeniden_cozulen"], 1)
        self.assertEqual(rapor["defter"]["eklenen"], 0)

    def test_arsivlenen_soru_stokta_sayilmaz(self):
        self.yanlis_soru_ekle(ONCEKI_PAZARTESI, durum="Arşivlendi")
        rapor = wr.rapor_uret(self.ogrenci, CARSAMBA)
        self.assertEqual(rapor["defter"]["bitis_bekleyen"], 0)
        self.assertEqual(rapor["defter"]["toplam_kayit"], 1)


class KarsilastirmaTest(HaftalikTestTabani):
    """Devam eden hafta, önceki haftanın EŞİT uzunluktaki dönemiyle kıyaslanır."""

    def test_devam_eden_hafta_esit_uzunlukta_karsilastirilir(self):
        # Önceki hafta: Pzt+Sal+Çar = 180 dk, Perşembe 120 dk (dönem dışı)
        self.oturum_ekle(ONCEKI_PAZARTESI, dk=60, soru=20)
        self.oturum_ekle(ONCEKI_SALI, dk=60, soru=20)
        self.oturum_ekle("2026-11-04", dk=60, soru=20)
        self.oturum_ekle("2026-11-05", dk=120, soru=40)
        # Bu hafta: Pzt+Sal+Çar = 240 dk
        self.oturum_ekle(PAZARTESI, dk=80, soru=30)
        self.oturum_ekle(SALI, dk=80, soru=30)
        self.oturum_ekle(CARSAMBA, dk=80, soru=30)
        rapor = wr.rapor_uret(self.ogrenci, CARSAMBA)
        karsilastirma = rapor["karsilastirma"]
        self.assertEqual(karsilastirma["donem"], "esit_uzunluk")
        self.assertTrue(karsilastirma["kullanilabilir"])
        sure = [a for a in karsilastirma["alanlar"] if a["alan"] == "dk"][0]
        self.assertEqual(sure["gercek"], 240)
        self.assertEqual(sure["onceki"], 180)  # Perşembe dahil edilmedi
        self.assertEqual(sure["fark"], 60)
        self.assertEqual(sure["yuzde"], 33.3)

    def test_tamamlanan_hafta_tam_hafta_ile_karsilastirilir(self):
        self.oturum_ekle(ONCEKI_PAZARTESI, dk=60, soru=20)
        self.oturum_ekle("2026-11-05", dk=120, soru=40)
        self.oturum_ekle(PAZARTESI, dk=90, soru=30)
        rapor = wr.rapor_uret(self.ogrenci, PAZARTESI, an=SONRAKI_AN)
        karsilastirma = rapor["karsilastirma"]
        self.assertEqual(karsilastirma["donem"], "tam_hafta")
        sure = [a for a in karsilastirma["alanlar"] if a["alan"] == "dk"][0]
        self.assertEqual(sure["gercek"], 90)
        self.assertEqual(sure["onceki"], 180)
        self.assertEqual(sure["fark"], -90)
        self.assertEqual(sure["yuzde"], -50.0)

    def test_onceki_hafta_veri_yoksa_alan_uretilmez(self):
        self.oturum_ekle(PAZARTESI, dk=90, soru=30)
        rapor = wr.rapor_uret(self.ogrenci, PAZARTESI)
        self.assertFalse(rapor["karsilastirma"]["onceki_veri_var"])
        alanlar = {a["alan"]: a for a in rapor["karsilastirma"]["alanlar"]}
        # Önceki hafta çalışma yok: süre karşılaştırması üretilmez.
        self.assertNotIn("dk", alanlar)


class YorumTest(HaftalikTestTabani):
    """Yorum motoru: deterministik kurallar, veri yoksa uydurma yok."""

    def _kodlar(self, rapor):
        return [y["kod"] for y in rapor["yorumlar"]]

    def test_veri_yoksa_tek_bilgi_yorumu_uretilir(self):
        rapor = wr.rapor_uret(self.ogrenci, PAZARTESI)
        self.assertFalse(rapor["veri_var"])
        self.assertEqual(self._kodlar(rapor), ["veri_yok"])
        yorum = rapor["yorumlar"][0]
        self.assertEqual(yorum["tur"], "bilgi")
        self.assertTrue(yorum["oneri"])

    def test_program_uyumu_dusuk_yorumu(self):
        # Devam eden hafta Çarşamba'ya kadar ölçülür; görevler o pencerede.
        for sira, gun in enumerate((PAZARTESI, PAZARTESI, SALI, CARSAMBA)):
            self.gorev_ekle(
                gun, durum=1 if sira == 0 else 0, makro="Konu %d" % sira
            )
        rapor = wr.rapor_uret(self.ogrenci, CARSAMBA)
        self.assertEqual(rapor["gorevler"]["planlanan"], 4)
        self.assertEqual(rapor["gorevler"]["uyum"], 25.0)
        self.assertIn("program_uyumu_dusuk", self._kodlar(rapor))
        yorum = [y for y in rapor["yorumlar"] if y["kod"] == "program_uyumu_dusuk"][0]
        self.assertEqual(yorum["tur"], "dikkat")

    def test_program_uyumu_yuksek_yorumu(self):
        for sira, gun in enumerate((PAZARTESI, PAZARTESI, SALI, CARSAMBA)):
            self.gorev_ekle(gun, durum=1, makro="Konu %d" % sira)
        rapor = wr.rapor_uret(self.ogrenci, CARSAMBA)
        self.assertEqual(rapor["gorevler"]["uyum"], 100.0)
        self.assertIn("program_uyumu_iyi", self._kodlar(rapor))

    def test_gecikmis_tekrar_yorumu(self):
        self.tekrar_ekle(SALI, durum="Bekliyor")
        rapor = wr.rapor_uret(self.ogrenci, CARSAMBA)
        self.assertEqual(rapor["tekrar"]["gecikmis_bekleyen"], 1)
        self.assertIn("tekrar_gecikme", self._kodlar(rapor))

    def test_hedef_yok_bilgisi_veri_varken_uretilir(self):
        self.oturum_ekle(PAZARTESI, dk=60, soru=20)
        rapor = wr.rapor_uret(self.ogrenci, PAZARTESI)
        yorumlar = [y for y in rapor["yorumlar"] if y["kod"] == "hedef_yok"]
        self.assertEqual(len(yorumlar), 1)
        self.assertEqual(yorumlar[0]["tur"], "bilgi")
        self.assertEqual(rapor["hedefler"]["ozet"]["adet"], 0)

    def test_hedef_varsa_hedef_yok_yorumu_uretilmez(self):
        self.oturum_ekle(PAZARTESI, dk=60, soru=20)
        wr.hedef_kaydet(self.ogrenci, PAZARTESI, "calisma_suresi", 300)
        rapor = wr.rapor_uret(self.ogrenci, PAZARTESI)
        self.assertNotIn("hedef_yok", self._kodlar(rapor))

    def test_gecen_hafta_tekrarlanan_yorum_isaretlenir_ve_sona_duser(self):
        # Önceki dönem eşit uzunlukta (Pzt–Çar) kesildiği için görevler o
        # pencerede olmalı; aksi halde kural (>=4 görev) hiç çalışmaz.
        for sira, gun in enumerate(
            (ONCEKI_PAZARTESI, ONCEKI_PAZARTESI, ONCEKI_SALI, ONCEKI_CARSAMBA)
        ):
            self.gorev_ekle(
                gun, durum=1 if sira == 0 else 0, makro="Konu %d" % sira
            )
        for sira, gun in enumerate((PAZARTESI, PAZARTESI, SALI, CARSAMBA)):
            self.gorev_ekle(
                gun, durum=1 if sira == 0 else 0, makro="Konu %d" % sira
            )
        rapor = wr.rapor_uret(self.ogrenci, CARSAMBA)
        tekrar_kodlari = {y["kod"] for y in rapor["yorumlar"] if y["tekrar"]}
        self.assertIn("program_uyumu_dusuk", tekrar_kodlari)
        bayraklar = [bool(y["tekrar"]) for y in rapor["yorumlar"]]
        self.assertEqual(bayraklar, sorted(bayraklar))

    def test_gelecek_hafta_veri_ve_karsilastirma_uretmez(self):
        self.oturum_ekle(PAZARTESI, dk=90, soru=30)
        rapor = wr.rapor_uret(self.ogrenci, SONRAKI_PAZARTESI)
        self.assertTrue(rapor["hafta"]["gelecek"])
        self.assertFalse(rapor["veri_var"])
        self.assertFalse(rapor["karsilastirma"]["kullanilabilir"])
        self.assertEqual(rapor["karsilastirma"]["alanlar"], [])
        self.assertEqual(self._kodlar(rapor), ["veri_yok"])

    def test_devam_eden_hafta_esit_uzunlukta_karsilastirir(self):
        self.oturum_ekle(ONCEKI_PAZARTESI, dk=120, soru=40)
        self.oturum_ekle("2026-11-05", dk=120, soru=40)
        self.oturum_ekle(PAZARTESI, dk=120, soru=40)
        rapor = wr.rapor_uret(self.ogrenci, CARSAMBA)
        sure = [a for a in rapor["karsilastirma"]["alanlar"] if a["alan"] == "dk"][0]
        self.assertEqual(sure["onceki"], 120)
        self.assertEqual(sure["fark"], 0)


class SeriTest(HaftalikTestTabani):
    """Çok haftalık seri, ortalama ve trend yeterliliği yardımcıları."""

    def test_seri_en_eski_ilk_en_yeni_son(self):
        self.oturum_ekle(ONCEKI_PAZARTESI, dk=60, soru=20)
        seri = wr.haftalik_seri(self.ogrenci, 2)
        self.assertEqual(len(seri), 2)
        self.assertEqual(seri[0]["baslangic"], ONCEKI_PAZARTESI)
        self.assertEqual(seri[0]["durum"], "tamamlandi")
        self.assertEqual(seri[0]["dk"], 60)
        self.assertEqual(seri[0]["soru"], 20)
        self.assertEqual(seri[-1]["baslangic"], PAZARTESI)
        self.assertEqual(seri[-1]["durum"], "devam")
        self.assertEqual(seri[-1]["dk"], 0)
        self.assertFalse(seri[-1]["veri_var"])

    def test_seri_hafta_sayisi_sinirlanir(self):
        self.assertEqual(len(wr.haftalik_seri(self.ogrenci, 1)), 1)
        self.assertEqual(
            len(wr.haftalik_seri(self.ogrenci, 100)), wr.MAKS_SERI_HAFTA
        )
        self.assertEqual(
            len(wr.haftalik_seri(self.ogrenci, "abc")), wr.VARSAYILAN_SERI_HAFTA
        )

    def test_seri_calisma_ve_gorev_verisini_tasir(self):
        self.oturum_ekle(ONCEKI_PAZARTESI, dk=90, soru=30)
        self.gorev_ekle(ONCEKI_PAZARTESI, durum=1)
        self.gorev_ekle(ONCEKI_PAZARTESI, durum=0, makro="Üslü Sayılar")
        seri = wr.haftalik_seri(self.ogrenci, 2)
        onceki = seri[0]
        self.assertEqual(onceki["dk"], 90)
        self.assertEqual(onceki["aktif_gun"], 1)
        self.assertEqual(onceki["tamamlanan_gorev"], 1)
        self.assertEqual(onceki["uyum"], 50.0)
        self.assertTrue(onceki["veri_var"])

    def test_seri_ders_surelerini_haftalik_tasir(self):
        self.oturum_ekle(PAZARTESI, dk=120, ders="TYT Matematik")
        self.oturum_ekle(SALI, dk=60, ders="TYT Türkçe")
        self.oturum_ekle(ONCEKI_PAZARTESI, dk=30, ders="TYT Türkçe")
        seri = wr.haftalik_seri(self.ogrenci, 2)
        self.assertEqual(seri[0]["ders_dk"], {"TYT Türkçe": 30})
        self.assertEqual(seri[-1]["ders_dk"]["TYT Matematik"], 120)
        self.assertEqual(seri[-1]["ders_dk"]["TYT Türkçe"], 60)

    def test_seri_ogrenci_izolasyonu(self):
        diger = self.ogrenci_ekle("Diğer Öğrenci")
        self.oturum_ekle(PAZARTESI, dk=60, soru=20)
        self.oturum_ekle(PAZARTESI, dk=300, soru=120, ogrenci_id=diger)
        seri = wr.haftalik_seri(self.ogrenci, 1)
        self.assertEqual(seri[-1]["dk"], 60)
        self.assertEqual(seri[-1]["soru"], 20)

    def test_seri_ortalamasi_veri_olmayan_haftayi_atlar(self):
        seri = [
            {"dk": 60, "veri_var": True},
            {"dk": 0, "veri_var": False},
            {"dk": 120, "veri_var": True},
        ]
        self.assertEqual(wr.seri_ortalamasi(seri, "dk", 3), 90.0)
        self.assertEqual(wr.seri_ortalamasi(seri, "dk", 1), 120.0)
        self.assertIsNone(wr.seri_ortalamasi(seri, "uyum"))
        self.assertIsNone(wr.seri_ortalamasi([], "dk"))

    def test_trend_yeterli_mi_veri_haftasini_sayar(self):
        az = [{"veri_var": False}] * 3
        self.assertFalse(wr.trend_yeterli_mi(az))
        yeterli = [{"veri_var": True}] * wr.GRAFIK_MIN_HAFTA
        self.assertTrue(wr.trend_yeterli_mi(yeterli))
        self.assertFalse(wr.trend_yeterli_mi(yeterli, en_az=wr.GRAFIK_MIN_HAFTA + 1))
        self.assertFalse(wr.trend_yeterli_mi([]))

    def test_seri_ortalama_serisi_kumulatif_ortalama(self):
        seri = [
            {"dk": 60, "veri_var": True},
            {"dk": 120, "veri_var": True},
            {"dk": 0, "veri_var": False},
        ]
        # Son hafta veri taşımadığı için ortalama son verili haftada kalır.
        self.assertEqual(
            wr.seri_ortalama_serisi(seri, "dk", 2), [60.0, 90.0, 120.0]
        )
        self.assertEqual(wr.seri_ortalama_serisi([], "dk"), [])


class HedefTest(HaftalikTestTabani):
    """Haftalık hedef CRUD, doğrulama, kopyalama ve ilerleme kartları."""

    def test_hedef_olusturulur_ve_haftaya_baglanir(self):
        kart = wr.hedef_kaydet(self.ogrenci, PAZARTESI, "calisma_suresi", 600)
        self.assertTrue(kart["yeni"])
        self.assertEqual(kart["hedef_deger"], 600.0)
        self.assertEqual(kart["hafta_baslangici"], PAZARTESI)
        self.assertEqual(kart["birim"], "dk")
        self.assertEqual(kart["ders"], "")
        # Haftanın herhangi bir günü aynı haftaya düşer.
        self.assertEqual(len(wr.hedefleri_getir(self.ogrenci, CARSAMBA)), 1)
        self.assertEqual(wr.hedefleri_getir(self.ogrenci, SONRAKI_PAZARTESI), [])

    def test_ayni_deger_tekrar_yazilmaz(self):
        wr.hedef_kaydet(self.ogrenci, PAZARTESI, "soru", 500)
        ikinci = wr.hedef_kaydet(self.ogrenci, PAZARTESI, "soru", 500)
        self.assertNotIn("yeni", ikinci)
        self.assertEqual(ikinci["guncelleme_sayisi"], 0)
        self.assertIsNone(ikinci["onceki_deger"])
        self.assertEqual(len(wr.hedefleri_getir(self.ogrenci, PAZARTESI)), 1)

    def test_hedef_guncellemesi_onceki_degeri_saklar(self):
        wr.hedef_kaydet(self.ogrenci, PAZARTESI, "soru", 500)
        guncel = wr.hedef_kaydet(self.ogrenci, PAZARTESI, "soru", 750)
        self.assertFalse(guncel["yeni"])
        self.assertEqual(guncel["hedef_deger"], 750.0)
        self.assertEqual(guncel["onceki_deger"], 500.0)
        self.assertEqual(guncel["guncelleme_sayisi"], 1)
        self.assertEqual(len(wr.hedefleri_getir(self.ogrenci, PAZARTESI)), 1)

    def test_ders_hedefinde_ders_zorunlu(self):
        with self.assertRaises(wr.HaftalikRaporHatasi):
            wr.hedef_kaydet(self.ogrenci, PAZARTESI, "ders_suresi", 120)
        kart = wr.hedef_kaydet(
            self.ogrenci, PAZARTESI, "ders_suresi", 120, ders="TYT Matematik"
        )
        self.assertEqual(kart["ders"], "TYT Matematik")
        self.assertIn("TYT Matematik", kart["etiket"])

    def test_gecersiz_tur_ve_deger_reddedilir(self):
        with self.assertRaises(wr.HaftalikRaporHatasi):
            wr.hedef_kaydet(self.ogrenci, PAZARTESI, "yok_boyle_hedef", 10)
        for deger in (0, -5, "abc", None, True):
            with self.assertRaises(wr.HaftalikRaporHatasi):
                wr.hedef_kaydet(self.ogrenci, PAZARTESI, "soru", deger)
        with self.assertRaises(wr.HaftalikRaporHatasi):
            wr.hedef_kaydet(self.ogrenci, PAZARTESI, "aktif_gun", 8)
        self.assertEqual(wr.hedefleri_getir(self.ogrenci, PAZARTESI), [])

    def test_hedef_sil_sahiplik_kontrolu(self):
        kart = wr.hedef_kaydet(self.ogrenci, PAZARTESI, "soru", 400)
        diger = self.ogrenci_ekle("Diğer Öğrenci")
        self.assertFalse(wr.hedef_sil(kart["id"], diger))
        self.assertEqual(len(wr.hedefleri_getir(self.ogrenci, PAZARTESI)), 1)
        self.assertTrue(wr.hedef_sil(kart["id"], self.ogrenci))
        self.assertEqual(wr.hedefleri_getir(self.ogrenci, PAZARTESI), [])
        with self.assertRaises(wr.HaftalikRaporHatasi):
            wr.hedef_sil("abc")

    def test_hedefleri_kopyala_mevcut_hedefi_ezmez(self):
        wr.hedef_kaydet(self.ogrenci, ONCEKI_PAZARTESI, "calisma_suresi", 600)
        wr.hedef_kaydet(self.ogrenci, ONCEKI_PAZARTESI, "soru", 400)
        wr.hedef_kaydet(self.ogrenci, PAZARTESI, "soru", 100)
        sonuc = wr.hedefleri_kopyala(self.ogrenci, ONCEKI_PAZARTESI)
        self.assertEqual(sonuc["kaynak_hafta"], ONCEKI_PAZARTESI)
        self.assertEqual(sonuc["hedef_hafta"], PAZARTESI)
        self.assertEqual(sonuc["kaynak_adet"], 2)
        self.assertEqual(sonuc["kopyalanan"], 1)
        hedefler = {
            h["hedef_turu"]: h for h in wr.hedefleri_getir(self.ogrenci, PAZARTESI)
        }
        self.assertEqual(hedefler["soru"]["hedef_deger"], 100.0)
        self.assertEqual(hedefler["calisma_suresi"]["hedef_deger"], 600.0)
        tekrar = wr.hedefleri_kopyala(self.ogrenci, ONCEKI_PAZARTESI)
        self.assertEqual(tekrar["kopyalanan"], 0)
        with self.assertRaises(wr.HaftalikRaporHatasi):
            wr.hedefleri_kopyala(self.ogrenci, PAZARTESI, PAZARTESI)

    def test_hedef_ilerlemesi_devam_ve_tamamlanma(self):
        wr.hedef_kaydet(self.ogrenci, PAZARTESI, "calisma_suresi", 600)
        self.oturum_ekle(PAZARTESI, dk=300, soru=100)
        rapor = wr.rapor_uret(self.ogrenci, PAZARTESI)
        kart = rapor["hedefler"]["ilerleme"][0]
        self.assertEqual(kart["gercek"], 300)
        self.assertEqual(kart["kalan"], 300.0)
        self.assertEqual(kart["oran"], 50.0)
        self.assertEqual(kart["durum"], wr.HEDEF_DURUM_DEVAM)
        self.assertEqual(kart["gercek_metin"], "5 sa")
        self.assertEqual(rapor["hedefler"]["ozet"]["devam"], 1)

        self.oturum_ekle(SALI, dk=400, soru=50)
        kart = wr.rapor_uret(self.ogrenci, PAZARTESI)["hedefler"]["ilerleme"][0]
        self.assertEqual(kart["oran"], 100.0)
        self.assertTrue(kart["asildi"])
        self.assertEqual(kart["kalan"], 0.0)
        self.assertEqual(kart["durum"], wr.HEDEF_DURUM_TAMAM)

    def test_hedef_program_uyumu_verisi_yoksa_bekliyor(self):
        wr.hedef_kaydet(self.ogrenci, PAZARTESI, "program_uyumu", 80)
        kart = wr.rapor_uret(self.ogrenci, PAZARTESI)["hedefler"]["ilerleme"][0]
        self.assertIsNone(kart["oran"])
        self.assertIsNone(kart["kalan"])
        self.assertEqual(kart["durum"], wr.HEDEF_DURUM_VERI)
        self.assertEqual(kart["gercek_metin"], "—")

    def test_ders_hedefi_yalnizca_ilgili_ders_suresini_olcer(self):
        wr.hedef_kaydet(
            self.ogrenci, PAZARTESI, "ders_suresi", 120, ders="TYT Matematik"
        )
        self.oturum_ekle(PAZARTESI, dk=60, ders="TYT Matematik")
        self.oturum_ekle(PAZARTESI, dk=200, ders="TYT Türkçe")
        kart = wr.rapor_uret(self.ogrenci, PAZARTESI)["hedefler"]["ilerleme"][0]
        self.assertEqual(kart["gercek"], 60)
        self.assertEqual(kart["oran"], 50.0)
        self.assertEqual(kart["durum"], wr.HEDEF_DURUM_DEVAM)

    def test_hedefler_dahil_edilmeden_rapor_uretilir(self):
        wr.hedef_kaydet(self.ogrenci, PAZARTESI, "soru", 400)
        wr.degerlendirme_kaydet(self.ogrenci, PAZARTESI, en_iyi="Not")
        rapor = wr.rapor_uret(self.ogrenci, PAZARTESI, hedefler_dahil=False)
        # İlerleme kartları ve değerlendirme istenmez; haftanın kayıtları
        # yine de görünür (arayüz "hedef ekle" formunu doldurabilsin).
        self.assertEqual(rapor["hedefler"]["ilerleme"], [])
        self.assertEqual(rapor["hedefler"]["ozet"]["adet"], 0)
        self.assertIsNone(rapor["degerlendirme"])
        self.assertEqual(len(rapor["hedefler"]["kayitli"]), 1)


class DegerlendirmeTest(HaftalikTestTabani):
    """Haftalık öğrenci değerlendirmesi (isteğe bağlı notlar)."""

    def test_bos_not_yazilmaz(self):
        self.assertIsNone(wr.degerlendirme_kaydet(self.ogrenci, PAZARTESI))
        self.assertIsNone(wr.degerlendirme_getir(self.ogrenci, PAZARTESI))
        self.assertEqual(wr.degerlendirmeleri_getir(self.ogrenci), [])

    def test_not_kaydedilir_ve_guncellenir(self):
        ilk = wr.degerlendirme_kaydet(
            self.ogrenci,
            PAZARTESI,
            en_iyi="Türev sorularında hız arttı",
            degistirilecek="Deneme saatini öne al",
        )
        self.assertTrue(ilk["dolu"])
        self.assertIsNone(ilk["guncelleme_zamani"])
        self.assertEqual(ilk["hafta_baslangici"], PAZARTESI)

        ayni = wr.degerlendirme_kaydet(
            self.ogrenci,
            PAZARTESI,
            en_iyi="Türev sorularında hız arttı",
            degistirilecek="Deneme saatini öne al",
        )
        self.assertEqual(ayni["id"], ilk["id"])
        self.assertIsNone(ayni["guncelleme_zamani"])

        guncel = wr.degerlendirme_kaydet(
            self.ogrenci,
            PAZARTESI,
            en_iyi="Türev sorularında hız arttı",
            zorlanilan="Paragraf süresi",
            degistirilecek="Deneme saatini öne al",
        )
        self.assertEqual(guncel["id"], ilk["id"])
        self.assertEqual(guncel["zorlanilan"], "Paragraf süresi")
        self.assertIsNotNone(guncel["guncelleme_zamani"])

    def test_gecmis_notlar_yeniden_eskiye_siralanir(self):
        wr.degerlendirme_kaydet(self.ogrenci, ONCEKI_PAZARTESI, en_iyi="Eski not")
        wr.degerlendirme_kaydet(self.ogrenci, PAZARTESI, en_iyi="Yeni not")
        kayitlar = wr.degerlendirmeleri_getir(self.ogrenci)
        self.assertEqual(len(kayitlar), 2)
        self.assertEqual(kayitlar[0]["hafta_baslangici"], PAZARTESI)
        self.assertEqual(kayitlar[1]["hafta_baslangici"], ONCEKI_PAZARTESI)
        self.assertTrue(kayitlar[0]["etiket"])

    def test_rapor_degerlendirmeyi_tasir(self):
        wr.degerlendirme_kaydet(self.ogrenci, PAZARTESI, ise_yarayan="Sabah bloğu")
        rapor = wr.rapor_uret(self.ogrenci, PAZARTESI)
        self.assertEqual(rapor["degerlendirme"]["ise_yarayan"], "Sabah bloğu")
        self.assertTrue(rapor["degerlendirme"]["dolu"])

    def test_ogrenci_izolasyonu(self):
        diger = self.ogrenci_ekle("Diğer Öğrenci")
        wr.degerlendirme_kaydet(self.ogrenci, PAZARTESI, en_iyi="Birinci öğrenci")
        wr.degerlendirme_kaydet(diger, PAZARTESI, en_iyi="İkinci öğrenci")
        kendi = wr.degerlendirme_getir(self.ogrenci, PAZARTESI)
        self.assertEqual(kendi["en_iyi"], "Birinci öğrenci")
        self.assertEqual(len(wr.degerlendirmeleri_getir(self.ogrenci)), 1)

    def test_gecersiz_ogrenci_hata_verir(self):
        with self.assertRaises(wr.HaftalikRaporHatasi):
            wr.degerlendirme_kaydet(999999, PAZARTESI, en_iyi="x")


if __name__ == "__main__":
    unittest.main(verbosity=2)
