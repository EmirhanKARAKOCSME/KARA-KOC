"""FAZ 6C - Haftalık plana aralıklı tekrar / yanlış soru entegrasyonu.

Kapsam:

- Havuzdaki tekrar kaydı `planlanan_tarih`inden ÖNCE planlanmaz (`en_erken`).
- Gecikmiş tekrar ilk uygun günde (plan penceresinin başında) yerleşir.
- Plan penceresinde OLUŞAN tekrar kaydı aynı hafta plana girmez
  (`_tekrar_havuzunu_suz`); beklemede kalır.
- Yanlış soru defteri kayıtları aynı konuda tek görevde birleşir ve görev
  `kaynaklar` alanında gerçek kaynak ID'lerini taşır.
- `tekrar_entegrasyonu=False` ile entegrasyon kapatılabilir.

Testler geçici bir SQLite dosyası ve sabit bir "bugün" kullanır; gerçek
`yks_veritabani.db` dosyasına dokunulmaz.

Çalıştırma:
    python tests/test_planner_tekrar.py
    python -m unittest discover -s tests -v
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(TEST_KOK)
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from services import planner  # noqa: E402
from services import spaced_repetition as sr  # noqa: E402
from services import wrong_questions as wq  # noqa: E402

SIMDI = datetime(2026, 11, 9, 10, 0, tzinfo=sr.TR_TZ)
BAS = date(2026, 11, 9)  # Pazartesi
OGRENCI = 1

_OGRENCI_SEMASI = """
CREATE TABLE IF NOT EXISTS ogrenciler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tc_no TEXT UNIQUE,
    kullanici_adi TEXT UNIQUE,
    sifre_hash TEXT,
    ad TEXT
)
"""


class PlannerTekrarTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="faz6c_plan_")
        self.db_yolu = os.path.join(self.klasor, "test.db")
        for modul in (sr, wq):
            modul.db_yolu_ayarla(self.db_yolu)
            modul.saat_fonksiyonu_ayarla(lambda: SIMDI)
        conn = sqlite3.connect(self.db_yolu)
        conn.executescript(_OGRENCI_SEMASI)
        conn.execute(
            "INSERT INTO ogrenciler (id, tc_no, kullanici_adi) VALUES (1, '1', 'ogr1')"
        )
        conn.commit()
        conn.close()
        sr.init_db()
        wq.init_db()

    def tearDown(self):
        for modul in (sr, wq):
            modul.db_yolu_ayarla(None)
            modul.saat_fonksiyonu_ayarla(None)
        shutil.rmtree(self.klasor, ignore_errors=True)

    # -- yardımcılar ---------------------------------------------------------
    def _baglam(self, **ek):
        baglam = {
            "ogrenci_id": OGRENCI,
            "baslangic": BAS,
            "gun_sayisi": 7,
            "musaitlik": {gun: 120 for gun in range(1, 8)},
            "mufredat": {"TYT Matematik": {"Temel Kavramlar": ["Sayılar"]}},
            "mikro_alt": {"Sayılar": ["Doğal Sayılar"]},
            "konu_sureleri": {"Sayılar": 40},
            "soru_agirliklari": {},
            "on_kosullar": {},
            "mikro_cozulen": {},
            "onceki_gorevler": [],
            "paragraf_soru": 0,
            "pedagoji": {},
            "tamamlanan_altlar": set(),
            "alarm_konular": [],
            # v2.3: özgün (legacy) planlama davranışını doğrular.
            "legacy_mod": True,
        }
        baglam.update(ek)
        return baglam

    def _tekrar_kaydi(self, planlanan, olusturma="2026-11-01 09:00:00"):
        return {
            "id": 41,
            "ogrenci_id": OGRENCI,
            "ders": "TYT Matematik",
            "makro_konu": "Temel Kavramlar",
            "mikro_konu": "Sayılar",
            "alt_konu": "Doğal Sayılar",
            "tekrar_turu": sr.TEKRAR_TURU_3_GUN,
            "planlanan_tarih": planlanan,
            "durum": sr.DURUM_BEKLIYOR,
            "olusturma_zamani": olusturma,
        }

    def _kaynakli(self, sonuc, tur):
        return [
            gorev
            for gorev in sonuc["gorevler"]
            if any(k.get("tur") == tur for k in (gorev.get("kaynaklar") or []))
        ]

    def _kaynak_idleri(self, gorev, tur):
        return [
            k["id"] for k in (gorev.get("kaynaklar") or []) if k.get("tur") == tur
        ]

    def _db_tekrar_ekle(self, planlanan, olusturma, mikro="Sayılar",
                        alt="Doğal Sayılar"):
        conn = sqlite3.connect(self.db_yolu)
        imlec = conn.execute(
            "INSERT INTO tekrar_kayitlari"
            " (ogrenci_id, ders, makro_konu, mikro_konu, alt_konu, tekrar_turu,"
            "  planlanan_tarih, durum, ogrenme_tarihi, olusturma_zamani)"
            " VALUES (?, 'TYT Matematik', 'Temel Kavramlar', ?,"
            "  ?, ?, ?, ?, '2026-10-30', ?)",
            (
                OGRENCI,
                mikro,
                alt,
                sr.TEKRAR_TURU_3_GUN,
                planlanan,
                sr.DURUM_BEKLIYOR,
                olusturma,
            ),
        )
        conn.commit()
        tekrar_id = imlec.lastrowid
        conn.close()
        return tekrar_id

    def test_tekrar_planlanan_tarihinden_once_yerlesmez(self):
        hedef = (BAS + timedelta(days=4)).isoformat()
        havuz = {
            "yanlis_sorular": [],
            "bekleyen_tekrarlar": [self._tekrar_kaydi(hedef)],
        }
        sonuc = planner.plan_uret(self._baglam(tekrar_havuzu=havuz))
        gorevler = self._kaynakli(sonuc, planner.KAYNAK_TEKRAR)
        self.assertEqual(len(gorevler), 1)
        self.assertGreaterEqual(gorevler[0]["tarih"], hedef)

    def test_gecikmis_tekrar_ilk_gunde_yerlesir(self):
        gecmis = (BAS - timedelta(days=2)).isoformat()
        havuz = {
            "yanlis_sorular": [],
            "bekleyen_tekrarlar": [self._tekrar_kaydi(gecmis)],
        }
        sonuc = planner.plan_uret(self._baglam(tekrar_havuzu=havuz))
        gorevler = self._kaynakli(sonuc, planner.KAYNAK_TEKRAR)
        self.assertEqual(len(gorevler), 1)
        self.assertEqual(gorevler[0]["tarih"], BAS.isoformat())

    def test_pencere_ici_tekrar_plana_girmez(self):
        hazir = self._db_tekrar_ekle(
            (BAS + timedelta(days=1)).isoformat(), "2026-11-05 09:00:00"
        )
        yeni = self._db_tekrar_ekle(
            (BAS + timedelta(days=2)).isoformat(),
            "2026-11-09 12:00:00",
            mikro="Bölme ve Bölünebilme",
            alt="Bölünebilme Kuralları",
        )
        sonuc = planner.plan_uret(self._baglam())
        gorevler = self._kaynakli(sonuc, planner.KAYNAK_TEKRAR)
        planlanan = [
            kid for gorev in gorevler for kid in self._kaynak_idleri(
                gorev, planner.KAYNAK_TEKRAR
            )
        ]
        self.assertEqual(planlanan, [hazir])
        self.assertNotIn(yeni, planlanan)
        self.assertGreaterEqual(
            gorevler[0]["tarih"], (BAS + timedelta(days=1)).isoformat()
        )

    def test_yanlis_sorular_tek_gorevde_birlesir(self):
        ilk = wq.yanlis_soru_ekle(
            OGRENCI, "TYT Matematik", "Sayılar", soru_metni="Asal sayılar"
        )
        ikinci = wq.yanlis_soru_ekle(
            OGRENCI, "TYT Matematik", "Sayılar", soru_metni="EBOB-EKOK"
        )
        sonuc = planner.plan_uret(self._baglam())
        gorevler = self._kaynakli(sonuc, planner.KAYNAK_YANLIS)
        self.assertEqual(len(gorevler), 1)
        self.assertEqual(
            sorted(self._kaynak_idleri(gorevler[0], planner.KAYNAK_YANLIS)),
            sorted([ilk["id"], ikinci["id"]]),
        )
        # Defter görevi bugünden önceye yerleşmez.
        self.assertGreaterEqual(gorevler[0]["tarih"], BAS.isoformat())
        self.assertGreaterEqual(int(gorevler[0]["hedef_soru"] or 0), 2)

    def test_entegrasyon_kapatilabilir(self):
        wq.yanlis_soru_ekle(
            OGRENCI, "TYT Matematik", "Sayılar", soru_metni="Kapalı test"
        )
        self._db_tekrar_ekle(BAS.isoformat(), "2026-11-05 09:00:00")
        sonuc = planner.plan_uret(self._baglam(tekrar_entegrasyonu=False))
        self.assertEqual(self._kaynakli(sonuc, planner.KAYNAK_YANLIS), [])
        self.assertEqual(self._kaynakli(sonuc, planner.KAYNAK_TEKRAR), [])

    def test_plan_gorevleri_kaynak_ve_tarih_tasir(self):
        wq.yanlis_soru_ekle(
            OGRENCI, "TYT Matematik", "Sayılar", soru_metni="Alan testi"
        )
        sonuc = planner.plan_uret(self._baglam())
        self.assertTrue(sonuc["gorevler"])
        for gorev in sonuc["gorevler"]:
            self.assertIn("tarih", gorev)
            self.assertIn("hedef_soru", gorev)
            self.assertIn("ders", gorev)
        defter = self._kaynakli(sonuc, planner.KAYNAK_YANLIS)[0]
        self.assertEqual(defter["ders"], "TYT Matematik")
        self.assertEqual(defter["mikro_konu"], "Sayılar")


if __name__ == "__main__":
    unittest.main(verbosity=2)
