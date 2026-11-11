"""FAZ 6A - Aralıklı tekrar motoru testleri.

Testler geçici bir SQLite dosyası kullanır; gerçek `yks_veritabani.db`
dosyasına dokunulmaz. Her test kendi öğrencisini oluşturur ve önceki test
verilerini temizler (FK CASCADE), böylece testler birbirinden bağımsızdır.

Çalıştırma:
    python tests/test_spaced_repetition.py
    python -m unittest discover -s tests -v
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from services import programs  # noqa: E402
from services import spaced_repetition as sr  # noqa: E402
from services import study_sessions  # noqa: E402
from services import task_steps  # noqa: E402

TR_TZ = sr.TR_TZ

_PAZARTESI = datetime(2026, 5, 4, 10, 0, tzinfo=TR_TZ)  # 2026-05-04 Pazartesi
_CARSAMBA = datetime(2026, 5, 6, 9, 30, tzinfo=TR_TZ)  # 2026-05-06 Çarşamba

_OGRENCI_SEMASI = """
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
)
"""


class TekrarMotoruTestleri(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.klasor = tempfile.mkdtemp(prefix="faz6a_")
        cls.db_yolu = os.path.join(cls.klasor, "test.db")
        for modul in (programs, task_steps, study_sessions, sr):
            modul.db_yolu_ayarla(cls.db_yolu)
        conn = sqlite3.connect(cls.db_yolu)
        conn.execute(_OGRENCI_SEMASI)
        conn.commit()
        conn.close()
        programs.init_db()
        task_steps.init_db()
        study_sessions.init_db()
        sr.init_db()

    @classmethod
    def tearDownClass(cls):
        for modul in (programs, task_steps, study_sessions, sr):
            modul.db_yolu_ayarla(None)
        shutil.rmtree(cls.klasor, ignore_errors=True)

    # ------------------------------------------------------------------
    # YARDIMCILAR
    # ------------------------------------------------------------------
    def setUp(self):
        self.conn = sqlite3.connect(self.db_yolu)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("DELETE FROM ogrenciler")  # CASCADE: tüm test verisi
        self.conn.commit()
        # `bugun()` deterministik olsun (gecikmişlik hesabı testlere bağlı kalmasın).
        sr.saat_fonksiyonu_ayarla(lambda: _PAZARTESI)
        self.ogrenci = self._ogrenci("Ali Veli")

    def tearDown(self):
        sr.saat_fonksiyonu_ayarla(None)
        self.conn.close()

    def _ogrenci(self, ad):
        imlec = self.conn.execute("INSERT INTO ogrenciler (ad) VALUES (?)", (ad,))
        self.conn.commit()
        return int(imlec.lastrowid)

    def _gorev(
        self,
        mikro="Türev Alma Kuralları",
        makro="Türev",
        ders="AYT Matematik",
        pedagoji="Pekiştirme",
        hedef=0,
        tarih="2026-05-04",
        gorev_turu="anlatim",
        adimlar=None,
        ogrenci=None,
    ):
        """Gerçek görev satırı + checklist üretir (FAZ 5B akışıyla aynı)."""
        oid = self.ogrenci if ogrenci is None else ogrenci
        imlec = self.conn.execute(
            "INSERT INTO calisma_programi_gorevler"
            " (ogrenci_id, gun, ders, makro_konu, mikro_konu, gorev_tanimi,"
            "  hedef_soru, pedagoji_turu, durum, tarih)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
            (
                oid,
                "Pazartesi",
                ders,
                makro,
                mikro,
                "%s — %s" % (ders, mikro),
                hedef,
                pedagoji,
                tarih,
            ),
        )
        gid = int(imlec.lastrowid)
        self.conn.commit()
        if adimlar is None:
            adimlar = task_steps.adimlari_uret(
                {
                    "ders": ders,
                    "makro_konu": makro,
                    "mikro_konu": mikro,
                    "pedagoji_turu": pedagoji,
                    "hedef_soru": hedef,
                    "gorev_turu": gorev_turu,
                }
            )
        task_steps.adimlari_kaydet(gid, adimlar)
        return gid

    def _bitir(self, gorev_id, an):
        """Manuel adımları tamamlar; her adımda görev durumu türetilir."""
        for adim in task_steps.gorev_adimlari(gorev_id):
            if adim["tamam"] or adim["adim_turu"] in task_steps.TURETILEN_ADIMLAR:
                continue
            task_steps.adim_durum_degistir(adim["id"], True, an=an)

    def _tekrarlar(self, ogrenci=None, sorgu_ek=""):
        oid = self.ogrenci if ogrenci is None else ogrenci
        return self.conn.execute(
            "SELECT * FROM tekrar_kayitlari WHERE ogrenci_id = ?" + sorgu_ek
            + " ORDER BY id",
            (oid,),
        ).fetchall()

    def _adim_id(self, gorev_id, tur):
        for adim in task_steps.gorev_adimlari(gorev_id):
            if adim["adim_turu"] == tur:
                return int(adim["id"])
        return None

    # ------------------------------------------------------------------
    # 1) Öğrenme görevi -> 3 gün sonra tekrar
    # ------------------------------------------------------------------
    def test_01_ogrenme_gorevi_3_gun_sonra_tekrar_uretir(self):
        gid = self._gorev()
        # Yalnızca ilk adım bitince görev tamamlanmadığı için tekrar yok.
        adimlar = task_steps.gorev_adimlari(gid)
        task_steps.adim_durum_degistir(adimlar[0]["id"], True, an=_PAZARTESI)
        self.assertEqual(self._tekrarlar(), [])

        self._bitir(gid, _PAZARTESI)
        kayitlar = self._tekrarlar()
        self.assertEqual(len(kayitlar), 1)
        kayit = kayitlar[0]
        self.assertEqual(kayit["tekrar_turu"], sr.TEKRAR_TURU_3_GUN)
        self.assertEqual(kayit["planlanan_tarih"], "2026-05-07")
        self.assertEqual(kayit["ogrenme_tarihi"], "2026-05-04")
        self.assertEqual(kayit["durum"], sr.DURUM_BEKLIYOR)
        self.assertEqual(kayit["ders"], "AYT Matematik")
        self.assertEqual(kayit["makro_konu"], "Türev")
        self.assertEqual(kayit["mikro_konu"], "Türev Alma Kuralları")
        self.assertEqual(int(kayit["kaynak_gorev_id"]), gid)
        self.assertEqual(
            int(kayit["kaynak_adim_id"]), self._adim_id(gid, task_steps.ADIM_IZLE)
        )
        self.assertEqual(int(kayit["hedef_soru"]), 0)
        self.assertTrue(kayit["aciklama"])

    # ------------------------------------------------------------------
    # 2) Ezber dersi -> ek olarak 5 gün sonra özet notu tekrarı
    # ------------------------------------------------------------------
    def test_02_ezber_dersinde_5_gunluk_ozet_notu_tekrari(self):
        gid = self._gorev(
            ders="AYT Biyoloji",
            makro="Sinir Sistemi",
            mikro="Nöronlar",
            pedagoji="Ezber",
        )
        self._bitir(gid, _PAZARTESI)
        kayitlar = self._tekrarlar()
        self.assertEqual(len(kayitlar), 2)
        turler = [k["tekrar_turu"] for k in kayitlar]
        self.assertEqual(turler, [sr.TEKRAR_TURU_3_GUN, sr.TEKRAR_TURU_5_GUN_NOT])
        uc_gun, bes_gun = kayitlar
        self.assertEqual(uc_gun["planlanan_tarih"], "2026-05-07")
        self.assertEqual(bes_gun["planlanan_tarih"], "2026-05-09")
        self.assertEqual(int(bes_gun["kaynak_adim_id"]),
                         self._adim_id(gid, task_steps.ADIM_NOT))
        # Özet notu tekrarı ek soru zorunluluğu getirmez.
        self.assertEqual(int(bes_gun["hedef_soru"]), 0)
        self.assertEqual(bes_gun["pedagoji_turu"], "Ezber")

    # ------------------------------------------------------------------
    # 3) Pekiştirme dersinde 5 günlük not tekrarı YOK
    # ------------------------------------------------------------------
    def test_03_pekistirme_dersinde_5_gunluk_not_tekrari_yok(self):
        gid = self._gorev(pedagoji="Pekiştirme")
        self._bitir(gid, _PAZARTESI)
        kayitlar = self._tekrarlar()
        self.assertEqual(len(kayitlar), 1)
        self.assertEqual(kayitlar[0]["tekrar_turu"], sr.TEKRAR_TURU_3_GUN)
        self.assertEqual(
            [k for k in self._tekrarlar() if k["tekrar_turu"] == sr.TEKRAR_TURU_5_GUN_NOT],
            [],
        )

    # ------------------------------------------------------------------
    # 4) Hafta sonuna / tatile tarih kaydırma yok
    # ------------------------------------------------------------------
    def test_04_hafta_sonuna_tasima_yok(self):
        gid = self._gorev(mikro="İntegral", makro="İntegral")
        self._bitir(gid, _CARSAMBA)  # 2026-05-06 Çarşamba
        kayit = self._tekrarlar()[0]
        # +3 takvim günü = 2026-05-09 Cumartesi (pazartesiye taşınmaz).
        self.assertEqual(kayit["planlanan_tarih"], "2026-05-09")
        self.assertEqual(kayit["ogrenme_tarihi"], "2026-05-06")
        self.assertEqual(
            sr.planlanan_tarih_hesapla("2026-05-06", 3), "2026-05-09"
        )
        self.assertEqual(sr.planlanan_tarih_hesapla("2026-12-31", 3), "2027-01-03")

    # ------------------------------------------------------------------
    # 5) Yalnızca soru bloğu olan görev öğrenme olayı değildir
    # ------------------------------------------------------------------
    def test_05_soru_gorevi_tekrar_uretmez(self):
        gid = self._gorev(
            hedef=5,
            gorev_turu="soru",
            adimlar=[{"baslik": "5 soru çöz.", "adim_turu": "soru", "hedef_soru": 5}],
        )
        oturum = study_sessions.oturum_baslat(self.ogrenci, gorev_id=gid, an=_PAZARTESI)
        study_sessions.oturum_tamamla(
            oturum["id"], 5, gercek_sure_dk=10, an=_PAZARTESI
        )
        task_steps.gorev_durum_guncelle(gid, an=_PAZARTESI)
        self.assertTrue(task_steps.gorev_tamam_mi(gid))
        self.assertEqual(self._tekrarlar(), [])

        # Tekrar görevi de kendi tekrarını üretmez.
        tekrar_gid = self._gorev(
            ders="TYT Türkçe",
            makro="Paragraf",
            mikro="Anlatım Biçimleri",
            pedagoji="Tekrar",
            adimlar=[
                {"baslik": "Özet notlarını oku ve gözden geçir.",
                 "adim_turu": "tekrar"}
            ],
        )
        self._bitir(tekrar_gid, _PAZARTESI)
        self.assertTrue(task_steps.gorev_tamam_mi(tekrar_gid))
        self.assertEqual(self._tekrarlar(), [])

        # Günlük alıştırma (bölünmez) ve deneme tekrarı da hariçtir.
        paragraf = self._gorev(
            ders="TYT Türkçe",
            makro="Paragraf",
            mikro="Günlük Paragraf",
            gorev_turu="soru",
            hedef=0,
        )
        self._bitir(paragraf, _PAZARTESI)
        deneme = self._gorev(
            makro="Deneme Tekrarı",
            mikro="Deneme Hataları",
            gorev_turu="soru",
        )
        self._bitir(deneme, _PAZARTESI)
        self.assertEqual(self._tekrarlar(), [])

    # ------------------------------------------------------------------
    # 6) Aynı öğrenme olayı için mükerrer kayıt yok (idempotent)
    # ------------------------------------------------------------------
    def test_06_mukerrer_kayit_uretilmez(self):
        gid = self._gorev()
        self._bitir(gid, _PAZARTESI)
        self.assertEqual(len(self._tekrarlar()), 1)

        ikinci = sr.tekrar_planla(gid, an=_PAZARTESI)
        self.assertEqual(ikinci, [])
        ucuncu = sr.tekrar_planla(gid, an=_PAZARTESI)
        self.assertEqual(ucuncu, [])
        task_steps.gorev_durum_guncelle(gid, an=_PAZARTESI)
        self.assertEqual(len(self._tekrarlar()), 1)

        # Tekrar kaydı elle de eklenemez: kısmi UNIQUE indeks engeller.
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO tekrar_kayitlari"
                " (ogrenci_id, ders, makro_konu, mikro_konu, tekrar_turu,"
                "  kaynak_gorev_id, planlanan_tarih, durum, ogrenme_tarihi,"
                "  olusturma_zamani) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.ogrenci,
                    "AYT Matematik",
                    "Türev",
                    "Türev Alma Kuralları",
                    sr.TEKRAR_TURU_3_GUN,
                    gid,
                    "2026-05-07",
                    sr.DURUM_BEKLIYOR,
                    "2026-05-04",
                    "2026-05-04 10:00:00",
                ),
            )

    # ------------------------------------------------------------------
    # 7) Sayfa yenilemesi / yeniden kaydetme çoğaltmaz
    # ------------------------------------------------------------------
    def test_07_sayfa_yenilemesi_cogaltmaz(self):
        gid = self._gorev()
        self._bitir(gid, _PAZARTESI)
        self.assertEqual(len(self._tekrarlar()), 1)

        for _ in range(5):
            kayitli = self.conn.execute(
                "SELECT durum FROM calisma_programi_gorevler WHERE id = ?", (gid,)
            ).fetchone()["durum"]
            turetilen = task_steps.gorev_tamam_mi(gid)
            if bool(kayitli) != bool(turetilen):
                task_steps.gorev_durum_guncelle(gid, an=_PAZARTESI)
            sr.tekrar_planla(gid, an=_PAZARTESI)  # yeniden kaydetme simülasyonu
        self.assertEqual(len(self._tekrarlar()), 1)

    # ------------------------------------------------------------------
    # 8) Geciken tekrar silinmez, tarihi değişmez
    # ------------------------------------------------------------------
    def test_08_geciken_tekrar_korunur(self):
        gid = self._gorev()
        self._bitir(gid, _PAZARTESI)
        kayit = self._tekrarlar()[0]
        self.assertEqual(kayit["planlanan_tarih"], "2026-05-07")

        referans = date(2026, 5, 20)
        bekleyen = sr.bekleyen_tekrarlar(self.ogrenci, gun=referans)
        self.assertEqual(len(bekleyen), 1)
        self.assertTrue(bekleyen[0]["gecikmis"])
        gecikmis = sr.gecikmis_tekrarlar(self.ogrenci, gun=referans)
        self.assertEqual([k["id"] for k in gecikmis], [int(kayit["id"])])

        # Tarih ileri taşınmaz, silinmez; durum Bekliyor kalır.
        satir = self.conn.execute(
            "SELECT planlanan_tarih, durum FROM tekrar_kayitlari WHERE id = ?",
            (kayit["id"],),
        ).fetchone()
        self.assertEqual(satir["planlanan_tarih"], "2026-05-07")
        self.assertEqual(satir["durum"], sr.DURUM_BEKLIYOR)

        ozet = sr.tekrar_ozeti(self.ogrenci, gun=referans)
        self.assertEqual(ozet["bekleyen"], 1)
        self.assertEqual(ozet["gecikmis"], 1)
        self.assertEqual(ozet["bugun"], 0)
        # Tekrar "bugün" sorgusunda görünmez ama bekleyenlerde durur.
        self.assertEqual(sr.bekleyen_tekrarlar(self.ogrenci, gun=referans,
                                              sadece_bugun=True), [])

    # ------------------------------------------------------------------
    # 9) İptal: bekleyenden çıkar, geçmiş korunur, yeni öğrenme yeni kayıt
    # ------------------------------------------------------------------
    def test_09_iptal_edilen_tekrar_bekleyenden_cikar(self):
        gid = self._gorev()
        self._bitir(gid, _PAZARTESI)
        kayit = self._tekrarlar()[0]

        iptal = sr.tekrar_iptal(kayit["id"], an=_PAZARTESI)
        self.assertEqual(iptal["durum"], sr.DURUM_IPTAL)
        self.assertIsNone(iptal["tamamlanma_zamani"])
        self.assertEqual(
            sr.bekleyen_tekrarlar(self.ogrenci, gun=date(2026, 5, 7)), []
        )
        ozet = sr.tekrar_ozeti(self.ogrenci, gun=date(2026, 5, 7))
        self.assertEqual(ozet["iptal"], 1)
        self.assertEqual(ozet["bekleyen"], 0)

        # İptal edilen kayıt silinmez; ikinci iptal idempotenttir.
        self.assertEqual(sr.tekrar_iptal(kayit["id"])["durum"], sr.DURUM_IPTAL)
        self.assertEqual(len(self._tekrarlar()), 1)

        # Aynı konu yeniden öğrenilirse yeni BEKLEYEN kayıt açılabilir.
        yeni = self._gorev(tarih="2026-05-07")
        self._bitir(yeni, datetime(2026, 5, 7, 10, 0, tzinfo=TR_TZ))
        kayitlar = self._tekrarlar()
        self.assertEqual(len(kayitlar), 2)
        self.assertEqual(
            sum(1 for k in kayitlar if k["durum"] == sr.DURUM_BEKLIYOR), 1
        )
        self.assertEqual(
            sr.tekrar_ozeti(self.ogrenci, gun=date(2026, 5, 10))["bekleyen"], 1
        )
        with self.assertRaises(sr.TekrarHatasi):
            sr.tekrar_tamamla(kayit["id"], an=_PAZARTESI)

    # ------------------------------------------------------------------
    # 10) Tamamlama gerçek zamanı yazar, planlanan tarihi değiştirmez
    # ------------------------------------------------------------------
    def test_10_tamamlanma_gercek_zamani_kaydeder(self):
        gid = self._gorev()
        self._bitir(gid, _PAZARTESI)
        kayit = self._tekrarlar()[0]

        an = datetime(2026, 5, 10, 14, 30, tzinfo=TR_TZ)  # 3 gün gecikmeli
        tamam = sr.tekrar_tamamla(kayit["id"], an=an)
        self.assertEqual(tamam["durum"], sr.DURUM_TAMAMLANDI)
        self.assertEqual(tamam["tamamlanma_zamani"], "2026-05-10 14:30:00")
        self.assertEqual(tamam["guncelleme_zamani"], "2026-05-10 14:30:00")
        # Planlanan tarih geriye dönük değiştirilmez.
        self.assertEqual(tamam["planlanan_tarih"], "2026-05-07")
        self.assertFalse(tamam["gecikmis"])

        # İkinci tamamlama idempotenttir; saat ilk kayıtla aynı kalır.
        tekrar = sr.tekrar_tamamla(
            kayit["id"], an=datetime(2026, 5, 11, 9, 0, tzinfo=TR_TZ)
        )
        self.assertEqual(tekrar["tamamlanma_zamani"], "2026-05-10 14:30:00")

        with self.assertRaises(sr.TekrarHatasi):
            sr.tekrar_iptal(kayit["id"])
        self.assertEqual(sr.bekleyen_tekrarlar(self.ogrenci, gun=date(2026, 6, 1)), [])
        ozet = sr.tekrar_ozeti(self.ogrenci, gun=date(2026, 6, 1))
        self.assertEqual(ozet["tamamlanan"], 1)
        self.assertEqual(ozet["bekleyen"], 0)

        liste = sr.tekrar_listesi(
            self.ogrenci,
            durum=sr.DURUM_TAMAMLANDI,
            baslangic="2026-05-07",
            bitis="2026-05-07",
        )
        self.assertEqual([k["id"] for k in liste], [int(kayit["id"])])
        self.assertEqual(
            sr.tekrar_listesi(self.ogrenci, baslangic="2026-05-08"), []
        )

    # ------------------------------------------------------------------
    # 11) Öğrenciler izole: aynı konu, ayrı kayıtlar
    # ------------------------------------------------------------------
    def test_11_ogrenciler_izole(self):
        diger = self._ogrenci("Ayşe Yılmaz")
        g1 = self._gorev()
        g2 = self._gorev(ogrenci=diger)
        self._bitir(g1, _PAZARTESI)
        self._bitir(g2, _PAZARTESI)

        kayit1 = self._tekrarlar(self.ogrenci)
        kayit2 = self._tekrarlar(diger)
        self.assertEqual(len(kayit1), 1)
        self.assertEqual(len(kayit2), 1)
        self.assertNotEqual(int(kayit1[0]["id"]), int(kayit2[0]["id"]))

        sr.tekrar_tamamla(kayit1[0]["id"], an=date(2026, 5, 7))
        self.assertEqual(sr.tekrar_ozeti(diger)["bekleyen"], 1)
        self.assertEqual(sr.tekrar_ozeti(self.ogrenci)["tamamlanan"], 1)
        self.assertEqual(len(sr.bekleyen_tekrarlar(diger, gun=date(2026, 5, 7))), 1)
        self.assertEqual(sr.bekleyen_tekrarlar(self.ogrenci, gun=date(2026, 5, 7)), [])

        with self.assertRaises(sr.TekrarHatasi):
            sr.bekleyen_tekrarlar(0)
        with self.assertRaises(sr.TekrarHatasi):
            sr.tekrar_listesi(self.ogrenci, durum="Uydurma")
        self.assertIsNone(sr.tekrar_getir(999999))

    # ------------------------------------------------------------------
    # 12) Veritabanı bütünlüğü + FAZ 1-5 akışları korunur
    # ------------------------------------------------------------------
    def test_12_butunluk_ve_faz1_5_akislari_korunur(self):
        def sayilar():
            return {
                tablo: self.conn.execute(
                    "SELECT COUNT(*) FROM %s" % tablo
                ).fetchone()[0]
                for tablo in (
                    "ogrenciler",
                    "calisma_programlari",
                    "calisma_programi_gorevler",
                    "calisma_gorev_alt_adimlari",
                    "calisma_oturumlari",
                    "tekrar_kayitlari",
                )
            }

        anlatim_gorev = {
            "tarih": "2026-05-04",
            "ders": "AYT Fizik",
            "makro_konu": "Kuvvet",
            "mikro_konu": "Newton Yasaları",
            "hedef_soru": 0,
            "pedagoji_turu": "Pekiştirme",
            "adimlar": task_steps.adimlari_uret(
                {
                    "ders": "AYT Fizik",
                    "makro_konu": "Kuvvet",
                    "mikro_konu": "Newton Yasaları",
                    "pedagoji_turu": "Pekiştirme",
                    "gorev_turu": "anlatim",
                }
            ),
        }
        tekrar_gorev = {
            "tarih": "2026-05-05",
            "ders": "AYT Fizik",
            "makro_konu": "Kuvvet",
            "mikro_konu": "Newton Yasaları",
            "hedef_soru": 0,
            "pedagoji_turu": "Tekrar",
            "adimlar": [
                {"baslik": "Özet notlarını oku.", "adim_turu": "tekrar"}
            ],
        }
        program = programs.program_olustur(
            self.ogrenci, "2026-05-04", "2026-05-10", [anlatim_gorev, tekrar_gorev]
        )
        self.assertEqual(program["durum"], "Aktif")
        gorevler = programs.program_gorevleri(program["id"])
        self.assertEqual(len(gorevler), 2)
        anlatim_id = [g["id"] for g in gorevler if g["pedagoji_turu"] == "Pekiştirme"][0]
        tekrar_id = [g["id"] for g in gorevler if g["pedagoji_turu"] == "Tekrar"][0]
        self.assertEqual(task_steps.gorev_ilerleme(anlatim_id)["adim_sayisi"], 2)
        self.assertEqual(
            [a["adim_turu"] for a in task_steps.gorev_adimlari(anlatim_id)],
            [task_steps.ADIM_IZLE, task_steps.ADIM_NOT],
        )

        # Migrasyon idempotent: tekrar tekrar init_db hiçbir satırı değiştirmez.
        once = sayilar()
        for modul in (programs, task_steps, study_sessions, sr):
            modul.init_db()
            modul.init_db()
        self.assertEqual(sayilar(), once)

        # Öğrenme görevi 1 tekrar üretir; tamamlanan Tekrar görevi üretmez.
        self._bitir(anlatim_id, _PAZARTESI)
        self.assertEqual(len(self._tekrarlar()), 1)
        self._bitir(tekrar_id, datetime(2026, 5, 5, 10, 0, tzinfo=TR_TZ))
        self.assertTrue(task_steps.gorev_tamam_mi(tekrar_id))
        self.assertEqual(len(self._tekrarlar()), 1)

        # FAZ 4 oturum + FAZ 5B gerçek soru türetimi bozulmadı.
        gid = self._gorev(
            ders="TYT Matematik",
            makro="Temel Kavramlar",
            mikro="Sayılar",
            hedef=10,
        )
        oturum = study_sessions.oturum_baslat(
            self.ogrenci, gorev_id=gid, an=_PAZARTESI
        )
        study_sessions.oturum_tamamla(
            oturum["id"],
            10,
            dogru=7,
            yanlis=2,
            bos=1,
            gercek_sure_dk=25,
            an=_PAZARTESI,
        )
        self._bitir(gid, _PAZARTESI)
        ilerleme = task_steps.gorev_ilerleme(gid)
        self.assertEqual(ilerleme["gercek_soru"], 10)
        self.assertEqual(ilerleme["hedef_soru"], 10)
        self.assertTrue(ilerleme["tamam"])
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM calisma_oturumlari WHERE gorev_id = ?", (gid,)
            ).fetchone()[0],
            1,
        )
        # Öğrenme görevi olduğu için burada da tek tekrar (Pekiştirme) oluştu.
        kayitlar = self._tekrarlar()
        self.assertEqual(len(kayitlar), 2)
        self.assertEqual(
            kayitlar[1]["mikro_konu"], "Sayılar"
        )
        self.assertEqual(kayitlar[1]["planlanan_tarih"], "2026-05-07")

        # Bütünlük: SQLite integrity + foreign key kontrolü temiz.
        self.assertEqual(
            self.conn.execute("PRAGMA integrity_check").fetchone()[0], "ok"
        )
        self.assertEqual(
            self.conn.execute("PRAGMA foreign_key_check").fetchall(), []
        )
        indeksler = {
            satir["name"]
            for satir in self.conn.execute("PRAGMA index_list('tekrar_kayitlari')")
        }
        for ad in (
            "idx_tekrar_ogrenci_tarih",
            "idx_tekrar_durum",
            "idx_tekrar_kaynak_gorev",
            "idx_tekrar_ogrenme_olayi",
            "idx_tekrar_tek_bekleyen",
        ):
            self.assertIn(ad, indeksler)


if __name__ == "__main__":
    unittest.main(verbosity=2)
