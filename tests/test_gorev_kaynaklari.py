"""FAZ 6C - Program görevi <-> kaynak köprüsü testleri.

Kapsam:

- Bağ yazma (mükerrer bağ eklenmez), okuma ve rozet sayaçları.
- Doğrulama: geçersiz kaynak türü / numara / görev numarası.
- Kaynak işi bitince bağların kapanması ve BEKLEYEN görevlerin
  `gecersiz = 1` olması (tamamlanmış göreve dokunulmaz, satır silinmez).
- Görev tamamlanınca kaynağın ilerlemesi (tekrar kaydı `Tamamlandı`,
  yanlış soru tekrar sayacı) ve idempotentlik.
- `bekleyen_kaynak_gorevleri` süzgeci.

Testler geçici bir SQLite dosyası ve sabit bir saat kullanır; gerçek
`yks_veritabani.db` dosyasına dokunulmaz.

Çalıştırma:
    python tests/test_gorev_kaynaklari.py
    python -m unittest discover -s tests -v
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(TEST_KOK)
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from services import gorev_kaynaklari as gk  # noqa: E402
from services import programs  # noqa: E402
from services import spaced_repetition as sr  # noqa: E402
from services import task_steps  # noqa: E402
from services import wrong_questions as wq  # noqa: E402

SIMDI = datetime(2026, 11, 9, 10, 0, tzinfo=sr.TR_TZ)
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


class GorevKaynakTestleri(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp(prefix="faz6c_")
        self.db_yolu = os.path.join(self.klasor, "test.db")
        for modul in (programs, task_steps, sr, wq, gk):
            modul.db_yolu_ayarla(self.db_yolu)
        for modul in (sr, wq, gk):
            modul.saat_fonksiyonu_ayarla(lambda: SIMDI)
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
        programs.init_db()
        task_steps.init_db()
        sr.init_db()
        wq.init_db()
        gk.init_db()

    def tearDown(self):
        for modul in (programs, task_steps, sr, wq, gk):
            modul.db_yolu_ayarla(None)
        for modul in (sr, wq, gk):
            modul.saat_fonksiyonu_ayarla(None)
        shutil.rmtree(self.klasor, ignore_errors=True)

    # -- yardımcılar ---------------------------------------------------------
    def _gorev_ekle(self, durum=0, gecersiz=0):
        conn = sqlite3.connect(self.db_yolu)
        imlec = conn.execute(
            "INSERT INTO calisma_programi_gorevler"
            " (ogrenci_id, program_id, gun, ders, makro_konu, mikro_konu,"
            "  gorev_tanimi, hedef_soru, gecersiz, durum, tarih)"
            " VALUES (?, NULL, 'Pazartesi', 'AYT Matematik', 'İleri Cebir',"
            "  'Polinomlar', 'Tekrar', 10, ?, ?, '2026-11-09')",
            (OGRENCI, gecersiz, durum),
        )
        conn.commit()
        gorev_id = imlec.lastrowid
        conn.close()
        return gorev_id

    def _tekrar_ekle(self, durum=sr.DURUM_BEKLIYOR):
        conn = sqlite3.connect(self.db_yolu)
        imlec = conn.execute(
            "INSERT INTO tekrar_kayitlari"
            " (ogrenci_id, ders, makro_konu, mikro_konu, tekrar_turu,"
            "  planlanan_tarih, durum, ogrenme_tarihi, olusturma_zamani)"
            " VALUES (?, 'AYT Matematik', 'İleri Cebir', 'Polinomlar', ?,"
            "  '2026-11-12', ?, '2026-11-09', '2026-11-09 10:00:00')",
            (OGRENCI, sr.TEKRAR_TURU_3_GUN, durum),
        )
        conn.commit()
        tekrar_id = imlec.lastrowid
        conn.close()
        return tekrar_id

    def _yanlis_ekle(self, soru_metni="Kökler toplamı"):
        return wq.yanlis_soru_ekle(
            OGRENCI,
            "AYT Matematik",
            "Polinomlar ve Çarpanlara Ayırma",
            soru_metni=soru_metni,
        )

    def _gorev_durum(self, gorev_id):
        conn = sqlite3.connect(self.db_yolu)
        satir = conn.execute(
            "SELECT durum, gecersiz FROM calisma_programi_gorevler WHERE id = ?",
            (gorev_id,),
        ).fetchone()
        conn.close()
        return {"durum": satir[0], "gecersiz": satir[1]}

    # -- temel yazma / okuma -------------------------------------------------
    def test_baglari_yazar_ve_okur(self):
        gorev_id = self._gorev_ekle()
        tekrar_id = self._tekrar_ekle()
        soru = self._yanlis_ekle()
        yazilan = gk.kaynaklari_kaydet(
            OGRENCI,
            None,
            gorev_id,
            [
                {"tur": gk.KAYNAK_TEKRAR, "id": tekrar_id},
                (gk.KAYNAK_YANLIS, soru["id"]),
            ],
        )
        self.assertEqual(yazilan, 2)
        baglar = gk.gorev_kaynaklari(gorev_id)
        self.assertEqual(len(baglar), 2)
        self.assertEqual(
            {b["tur"] for b in baglar}, {gk.KAYNAK_TEKRAR, gk.KAYNAK_YANLIS}
        )
        self.assertFalse(any(b["cozuldu"] for b in baglar))
        # Mükerrer bağ yazılmaz.
        self.assertEqual(
            gk.kaynaklari_kaydet(
                OGRENCI, None, gorev_id, [(gk.KAYNAK_TEKRAR, tekrar_id)]
            ),
            0,
        )
        self.assertEqual(
            gk.gorev_kaynak_sayaci(gorev_id), {"toplam": 2, "cozuldu": 0}
        )

    def test_dogrulama_hatalari(self):
        gorev_id = self._gorev_ekle()
        tekrar_id = self._tekrar_ekle()
        with self.assertRaises(gk.KaynakHatasi):
            gk.kaynaklari_kaydet(OGRENCI, None, gorev_id, [("uydurma", 1)])
        with self.assertRaises(gk.KaynakHatasi):
            gk.kaynaklari_kaydet(OGRENCI, None, gorev_id, [("tekrar_kaydi", 0)])
        with self.assertRaises(gk.KaynakHatasi):
            gk.kaynaklari_kaydet(OGRENCI, None, gorev_id, "liste-değil")
        with self.assertRaises(gk.KaynakHatasi):
            gk.bekleyen_kaynak_gorevleri("uydurma", tekrar_id)
        with self.assertRaises(gk.KaynakHatasi):
            gk.gorev_kaynaklari(0)
        self.assertEqual(gk.gorev_kaynaklari(gorev_id), [])

    # -- kaynak işi bitti ----------------------------------------------------
    def test_kaynak_isi_bitti_gecersiz_kilar(self):
        tekrar_id = self._tekrar_ekle()
        bekleyen = self._gorev_ekle(durum=0)
        tamamlanmis = self._gorev_ekle(durum=1)
        for gorev_id in (bekleyen, tamamlanmis):
            gk.kaynaklari_kaydet(
                OGRENCI, None, gorev_id, [(gk.KAYNAK_TEKRAR, tekrar_id)]
            )

        kapatilan = gk.kaynak_isi_bitti(
            gk.KAYNAK_TEKRAR, tekrar_id, gecersiz_kil=True
        )
        self.assertEqual(kapatilan, 2)
        # Bekleyen görev geçersiz kılınır, tamamlanmış görev korunur.
        self.assertEqual(self._gorev_durum(bekleyen)["gecersiz"], 1)
        self.assertEqual(self._gorev_durum(tamamlanmis)["gecersiz"], 0)
        # Bağlar kapanır; ikinci çağrı yeni bağ kapatmaz.
        self.assertTrue(all(b["cozuldu"] for b in gk.gorev_kaynaklari(bekleyen)))
        self.assertEqual(gk.gorev_kaynak_sayaci(bekleyen)["cozuldu"], 1)
        self.assertEqual(
            gk.kaynak_isi_bitti(gk.KAYNAK_TEKRAR, tekrar_id, gecersiz_kil=True), 0
        )

    def test_kaynak_isi_bitti_gecersiz_kilmayi_opsiyonel_tutar(self):
        soru = self._yanlis_ekle()
        gorev_id = self._gorev_ekle(durum=0)
        gk.kaynaklari_kaydet(
            OGRENCI, None, gorev_id, [(gk.KAYNAK_YANLIS, soru["id"])]
        )
        self.assertEqual(
            gk.kaynak_isi_bitti(gk.KAYNAK_YANLIS, soru["id"]), 1
        )
        self.assertEqual(self._gorev_durum(gorev_id)["gecersiz"], 0)

    def test_bekleyen_kaynak_gorevleri_suzgeci(self):
        soru = self._yanlis_ekle()
        gecerli = self._gorev_ekle(durum=0)
        gecersiz = self._gorev_ekle(durum=0, gecersiz=1)
        bitmis = self._gorev_ekle(durum=1)
        for gorev_id in (gecerli, gecersiz, bitmis):
            gk.kaynaklari_kaydet(
                OGRENCI, None, gorev_id, [(gk.KAYNAK_YANLIS, soru["id"])]
            )
        sonuc = gk.bekleyen_kaynak_gorevleri(gk.KAYNAK_YANLIS, soru["id"])
        self.assertEqual([satir["id"] for satir in sonuc], [gecerli])
        hepsi = gk.bekleyen_kaynak_gorevleri(
            gk.KAYNAK_YANLIS, soru["id"], sadece_gecerli=False
        )
        self.assertEqual(
            sorted(satir["id"] for satir in hepsi), sorted([gecerli, gecersiz, bitmis])
        )

    # -- görev tamamlandı -> kaynak ilerlet -----------------------------------
    def test_gorev_tamamlandi_kaynagi_ilerletir(self):
        gorev_id = self._gorev_ekle(durum=0)
        tekrar_id = self._tekrar_ekle()
        soru = self._yanlis_ekle()
        gk.kaynaklari_kaydet(
            OGRENCI,
            None,
            gorev_id,
            [(gk.KAYNAK_TEKRAR, tekrar_id), (gk.KAYNAK_YANLIS, soru["id"])],
        )

        ozet = gk.gorev_tamamlandi(gorev_id)
        self.assertEqual(ozet["toplam"], 2)
        self.assertEqual(ozet[gk.KAYNAK_TEKRAR], 1)
        self.assertEqual(ozet[gk.KAYNAK_YANLIS], 1)
        self.assertEqual(sr.tekrar_getir(tekrar_id)["durum"], sr.DURUM_TAMAMLANDI)
        yanlis = wq.yanlis_soru_getir(soru["id"])
        self.assertEqual(yanlis["tekrar_sayisi"], 1)
        self.assertEqual(yanlis["durum"], wq.DURUM_TEKRAR)
        self.assertEqual(gk.gorev_kaynak_sayaci(gorev_id)["cozuldu"], 2)

        # İkinci tamamlama sayaçları artırmaz (idempotent).
        tekrar = gk.gorev_tamamlandi(gorev_id)
        self.assertEqual(tekrar["toplam"], 0)
        self.assertEqual(wq.yanlis_soru_getir(soru["id"])["tekrar_sayisi"], 1)

    def test_gorev_tamamlandi_bagsiz_gorev(self):
        gorev_id = self._gorev_ekle(durum=0)
        self.assertEqual(
            gk.gorev_tamamlandi(gorev_id),
            {"toplam": 0, gk.KAYNAK_TEKRAR: 0, gk.KAYNAK_YANLIS: 0},
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
