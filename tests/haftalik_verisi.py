"""FAZ 7 test altyapısı: geçici SQLite + kaynak tablo yardımcıları.

Testler GERÇEK `yks_veritabani.db` dosyasına dokunmaz. Haftalık rapor bir
"katman" olduğu için testler de gerçek kaynak tabloları (çalışma oturumları,
program görevleri, tekrar, yanlış soru, deneme) doldurup raporu bu veriden
doğrular; rapor tarafında üretilmiş metrik saklanmaz.

Çalıştırma:
    python tests/test_haftalik_rapor.py
    python -m unittest discover -s tests -v
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from services import programs  # noqa: E402
from services import spaced_repetition  # noqa: E402
from services import study_sessions  # noqa: E402
from services import task_steps  # noqa: E402
from services import weekly_report as wr  # noqa: E402
from services import wrong_questions  # noqa: E402

TR_TZ = wr.TR_TZ

# 2026-11-09 Pazartesi .. 2026-11-15 Pazar (sabit referans haftası)
PAZARTESI = "2026-11-09"
SALI = "2026-11-10"
CARSAMBA = "2026-11-11"
PERSEMBE = "2026-11-12"
CUMA = "2026-11-13"
CUMARTESI = "2026-11-14"
PAZAR = "2026-11-15"
ONCEKI_PAZARTESI = "2026-11-02"
ONCEKI_SALI = "2026-11-03"
ONCEKI_CARSAMBA = "2026-11-04"
SONRAKI_PAZARTESI = "2026-11-16"

# Testlerde "şimdi": haftanın Çarşamba günü 12:00 (hafta DEVAM EDİYOR).
SIMDI = datetime(2026, 11, 11, 12, 0, tzinfo=TR_TZ)

MODULLER = (
    programs,
    task_steps,
    study_sessions,
    spaced_repetition,
    wrong_questions,
    wr,
)


# Uygulamanın kurduğu, servislerin kurmadığı tablolar (main.py init_db ile
# aynı kolonlar; yalnızca testte gereken alanlar).
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

CREATE TABLE IF NOT EXISTS konu_durumlari_detay (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER,
    ders TEXT,
    makro_konu TEXT,
    mikro_konu TEXT,
    durum TEXT DEFAULT 'Başlanmadı'
);
"""



class HaftalikTestTabani(unittest.TestCase):
    """Geçici DB kuran ortak taban (öğrenci bazlı izolasyon korunur)."""

    @classmethod
    def setUpClass(cls):
        cls.klasor = tempfile.mkdtemp(prefix="faz7_")
        cls.db_yolu = os.path.join(cls.klasor, "test.db")
        for modul in MODULLER:
            modul.db_yolu_ayarla(cls.db_yolu)
        conn = sqlite3.connect(cls.db_yolu)
        conn.executescript(SEMA)
        conn.commit()
        conn.close()
        for modul in MODULLER:
            modul.init_db()

    @classmethod
    def tearDownClass(cls):
        wr.saat_fonksiyonu_ayarla(None)
        for modul in MODULLER:
            modul.db_yolu_ayarla(None)
        shutil.rmtree(cls.klasor, ignore_errors=True)

    def setUp(self):
        self._temizle()
        wr.saat_fonksiyonu_ayarla(lambda: SIMDI)
        self.ogrenci = self.ogrenci_ekle("Test Öğrenci")

    def tearDown(self):
        wr.saat_fonksiyonu_ayarla(None)

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
        conn.execute("DELETE FROM ogrenciler")  # CASCADE: tüm çocuk kayıtlar
        conn.commit()
        conn.close()

    def _yaz(self, sorgu, parametreler=()):
        conn = self.baglanti()
        imlec = conn.execute(sorgu, parametreler)
        conn.commit()
        son = imlec.lastrowid
        conn.close()
        return son

    def _sayac(self):
        conn = self.baglanti()
        sayi = conn.execute("SELECT COUNT(*) FROM ogrenciler").fetchone()[0]
        conn.close()
        return sayi

    # ------------------------------------------------------------------
    # VERİ ÜRETİM YARDIMCILARI
    # ------------------------------------------------------------------
    def ogrenci_ekle(self, ad, kullanici=None):
        kullanici = kullanici or ("ogr%d" % (len(ad) * 7 + self._sayac()))
        conn = self.baglanti()
        imlec = conn.execute(
            "INSERT INTO ogrenciler (ad, kullanici_adi) VALUES (?, ?)",
            (ad, kullanici),
        )
        conn.commit()
        oid = imlec.lastrowid
        conn.close()
        return oid

    def oturum_ekle(
        self,
        gun,
        dk=60,
        soru=20,
        ders="TYT Matematik",
        makro="Temel Kavramlar",
        mikro="Tek ve Çift Sayılar",
        alt="Tek Sayılar",
        dogru=None,
        yanlis=None,
        bos=None,
        saat="10:00:00",
        durum="Tamamlandı",
        gorev_id=None,
        ogrenci_id=None,
    ):
        oid = ogrenci_id or self.ogrenci
        baslangic = "%s %s" % (gun, saat)
        return self._yaz(
            "INSERT INTO calisma_oturumlari (ogrenci_id, gorev_id, ders,"
            " makro_konu, mikro_konu, alt_konu, durum, baslangic_zamani,"
            " olusturma_zamani, gercek_sure_dk, cozulen_soru, dogru, yanlis,"
            " bos) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                oid,
                gorev_id,
                ders,
                makro,
                mikro,
                alt,
                durum,
                baslangic,
                baslangic,
                dk,
                soru,
                dogru,
                yanlis,
                bos,
            ),
        )

    def gorev_ekle(
        self,
        tarih,
        durum=0,
        ders="TYT Matematik",
        makro="Temel Kavramlar",
        mikro="Tek ve Çift Sayılar",
        alt="Tek Sayılar",
        hedef_soru=30,
        tahmini_sure_dk=60,
        gecersiz=0,
        kaynak_gorev_id=None,
        ogrenci_id=None,
    ):
        oid = ogrenci_id or self.ogrenci
        return self._yaz(
            "INSERT INTO calisma_programi_gorevler (ogrenci_id, gun, ders,"
            " makro_konu, mikro_konu, alt_konu, hedef_soru, mikro_hedef_soru,"
            " tahmini_sure_dk, durum, tarih, kaynak_gorev_id, gecersiz)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)",
            (
                oid,
                tarih,
                ders,
                makro,
                mikro,
                alt,
                hedef_soru,
                tahmini_sure_dk,
                durum,
                tarih,
                kaynak_gorev_id,
                gecersiz,
            ),
        )

    def devir_ekle(self, kaynak_id, hedef_id, soru=10, sure=None, ogrenci_id=None):
        oid = ogrenci_id or self.ogrenci
        return self._yaz(
            "INSERT INTO calisma_gorev_devirleri (ogrenci_id, kaynak_gorev_id,"
            " hedef_gorev_id, devredilen_soru, devredilen_sure_dk,"
            " olusturma_zamani) VALUES (?, ?, ?, ?, ?, ?)",
            (oid, kaynak_id, hedef_id, soru, sure, "%s 09:00:00" % SIMDI.date()),
        )

    def deneme_ekle(
        self,
        tarih,
        dogru=80,
        yanlis=20,
        bos=0,
        tur="TYT",
        ad="Deneme",
        kategori="Genel Deneme",
        ders_sonuclari=None,
        net_bilgisi=None,
        ogrenci_id=None,
    ):
        oid = ogrenci_id or self.ogrenci
        did = self._yaz(
            "INSERT INTO denemeler (ogrenci_id, tarih, deneme_adi,"
            " deneme_kategorisi, deneme_turu, net_bilgisi, dogru_adedi,"
            " yanlis_adedi, bos_adedi, olusturma_zamani)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                oid,
                tarih,
                ad,
                kategori,
                tur,
                net_bilgisi,
                dogru,
                yanlis,
                bos,
                "%s 18:00:00" % tarih,
            ),
        )
        for ders, d, y, b in ders_sonuclari or ():
            self._yaz(
                "INSERT INTO deneme_ders_sonuclari (deneme_id, ders,"
                " soru_sayisi, dogru, yanlis, bos, net)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (did, ders, d + y + b, d, y, b, round(d - y / 4.0, 2)),
            )
        return did

    def tekrar_ekle(
        self,
        planlanan,
        durum="Bekliyor",
        tamamlanma=None,
        ders="TYT Matematik",
        makro="Temel Kavramlar",
        mikro="Tek ve Çift Sayılar",
        alt="Tek Sayılar",
        tur="3 Günlük Tekrar",
        ogrenci_id=None,
    ):
        oid = ogrenci_id or self.ogrenci
        return self._yaz(
            "INSERT INTO tekrar_kayitlari (ogrenci_id, ders, makro_konu,"
            " mikro_konu, alt_konu, tekrar_turu, planlanan_tarih, durum,"
            " ogrenme_tarihi, olusturma_zamani, tamamlanma_zamani)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                oid,
                ders,
                makro,
                mikro,
                alt,
                tur,
                planlanan,
                durum,
                planlanan,
                "%s 09:00:00" % planlanan,
                tamamlanma,
            ),
        )

    def yanlis_soru_ekle(
        self,
        eklenme,
        durum="Yeni",
        ogrenme=None,
        son_tekrar=None,
        mikro="Tek ve Çift Sayılar",
        ders="TYT Matematik",
        tekrar_sayisi=0,
        ogrenci_id=None,
    ):
        oid = ogrenci_id or self.ogrenci
        return self._yaz(
            "INSERT INTO yanlis_sorular (ogrenci_id, ders, makro_konu,"
            " mikro_konu, alt_konu, durum, tekrar_sayisi, ogrenme_tarihi,"
            " son_tekrar_tarihi, olusturma_zamani, guncelleme_zamani)"
            " VALUES (?, ?, 'Temel Kavramlar', ?, 'Alt', ?, ?, ?, ?, ?, ?)",
            (
                oid,
                ders,
                mikro,
                durum,
                tekrar_sayisi,
                ogrenme,
                son_tekrar,
                "%s 11:00:00" % eklenme,
                "%s 11:00:00" % eklenme,
            ),
        )

    def mikro_ekle(
        self,
        ders="TYT Matematik",
        makro="Temel Kavramlar",
        mikro="Tek ve Çift Sayılar",
        alt="Tek Sayılar",
        hedef_soru=50,
        cozulen_soru=0,
        ogrenme_tamam=0,
        tamamlandi=0,
        ogrenci_id=None,
    ):
        oid = ogrenci_id or self.ogrenci
        return self._yaz(
            "INSERT INTO mikro_konu_ilerleme (ogrenci_id, ders, makro_konu,"
            " mikro_konu, alt_konu, ogrenme_tamam, hedef_soru, cozulen_soru,"
            " tamamlandi, olusturma_zamani, guncelleme_zamani)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                oid,
                ders,
                makro,
                mikro,
                alt,
                ogrenme_tamam,
                hedef_soru,
                cozulen_soru,
                tamamlandi,
                "%s 09:00:00" % SIMDI.date(),
                "%s 09:00:00" % SIMDI.date(),
            ),
        )

