"""FAZ 5D - Mikro konu bazlı görev ayrımı testleri.

Kapsam (görev tanımındaki 12 madde):

01 Polinomlar beş ayrı mikro görev üretiyor mu? (+ gerçek çıktı fixture)
02 Her görev tek mikro konu içeriyor mu?
03 Checklist'ler bağımsız mı?
04 İlk görev tamamlandığında diğerleri açık kalıyor mu?
05 Süreler mikro konuya göre hesaplanıyor mu?
06 Soru hedeflerinin toplamı ana konu hedefine eşit mi?
07 Gerçek soru ilerlemesi doğru mikro konuya yazılıyor mu?
08 Kalan sorular/mikro konular sonraki haftaya aktarılıyor mu?
09 Günlük kapasite ve dinlenme günleri korunuyor mu?
10 Fallback motorları aynı yapıyı üretiyor mu?
11 FAZ 6A tekrar motoru doğru mikro göreviyle ilişki kuruyor mu?
12 FAZ 4 / 5 / 6A regresyonları korunuyor mu?

Gerçek müfredat `tests/program_verisi.py` ile main.py'den (Streamlit
çalıştırılmadan) okunur; testler geçici bir SQLite dosyası kullanır, gerçek
`yks_veritabani.db` dosyasına dokunulmaz.

Çalıştırma:
    python tests/test_faz5d_mikro_gorevler.py
    python -m unittest discover -s tests -v
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
if TEST_KOK not in sys.path:
    sys.path.insert(0, TEST_KOK)

import program_verisi as V  # noqa: E402

from services import planner  # noqa: E402
from services import programs  # noqa: E402
from services import spaced_repetition as sr  # noqa: E402
from services import study_sessions  # noqa: E402
from services import task_steps  # noqa: E402

FIXTURE_YOLU = os.path.join(TEST_KOK, "fixtures", "polinomlar_haftalik_program.json")

# Testlerde "şimdi" sabittir: tekrar tarihleri ve zaman damgaları deterministik.
_SIMDI = datetime(2026, 11, 9, 10, 0, tzinfo=sr.TR_TZ)

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


class MikroGorevTestleri(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.klasor = tempfile.mkdtemp(prefix="faz5d_")
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
        cls.uzay = V.sabitler()
        cls.mikro_alt = V.mikro_alt_konular()

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
        imlec = self.conn.execute(
            "INSERT INTO ogrenciler (ad) VALUES (?)", ("Ali Veli",)
        )
        self.conn.commit()
        self.ogrenci = int(imlec.lastrowid)
        sr.saat_fonksiyonu_ayarla(lambda: _SIMDI)
        task_steps.saat_fonksiyonu_ayarla(lambda: _SIMDI)

    def tearDown(self):
        sr.saat_fonksiyonu_ayarla(None)
        task_steps.saat_fonksiyonu_ayarla(None)
        self.conn.close()

    def _plan(self, **kwargs):
        kwargs.setdefault("ogrenci_id", self.ogrenci)
        return planner.plan_uret(V.baglam(**kwargs))

    def _polinom(self, **kwargs):
        gorevler = V.polinom_gorevleri(self._plan(**kwargs))
        return sorted(gorevler, key=lambda g: g["tarih"])

    def _ana_hedef(self, ana=V.POLINOM_ANA_KONU, makro=V.POLINOM_MAKRO):
        mikrolar = V.mufredat("polinom")["AYT Matematik"][makro]
        kredi = self.uzay["SORU_AGIRLIKLARI"][makro]
        return planner.mikro_soru_hedefi(
            kredi, mikrolar, ana, self.uzay["KONU_SURELERI_DK"]
        )

    def _oturum(self, gorev_id, cozulen, ders="AYT Matematik",
                makro=V.POLINOM_MAKRO, mikro=V.POLINOM_ANA_KONU,
                alt=None, sure_dk=30):
        """Tamamlanmış GERÇEK çalışma oturumu (FAZ 4 kaydı)."""
        self.conn.execute(
            "INSERT INTO calisma_oturumlari (ogrenci_id, gorev_id, ders,"
            " makro_konu, mikro_konu, alt_konu, durum, baslangic_zamani,"
            " gercek_sure_dk, cozulen_soru, olusturma_zamani)"
            " VALUES (?, ?, ?, ?, ?, ?, 'Tamamlandı', '2026-11-09 10:00:00',"
            " ?, ?, '2026-11-09 10:30:00')",
            (self.ogrenci, gorev_id, ders, makro, mikro, alt, sure_dk, cozulen),
        )
        self.conn.commit()

    def _programa_yaz(self, gorevler):
        """Planlanan görevleri gerçek program servisiyle yazar."""
        return programs.program_olustur(
            self.ogrenci,
            "2026-11-09",
            "2026-11-15",
            gorevler,
            durum=programs.DURUM_AKTIF,
        )

    def _gorev_id(self, program, alt_konu):
        for gorev in programs.program_gorevleri(program["id"]):
            if gorev["alt_konu"] == alt_konu:
                return int(gorev["id"])
        raise AssertionError("Programda mikro konu bulunamadı: %s" % alt_konu)

    # ------------------------------------------------------------------
    # 01 - BEŞ AYRI MİKRO GÖREV + GERÇEK ÇIKTI FIXTURE
    # ------------------------------------------------------------------
    def test_01_polinomlar_bes_ayri_mikro_gorev(self):
        gorevler = self._polinom()
        beklenen = self.mikro_alt[V.POLINOM_ANA_KONU]

        self.assertEqual(len(beklenen), 5, "Polinomlar beş mikro konu içermeli")
        self.assertEqual(len(gorevler), 5, "Her mikro konu ayrı görev olmalı")
        self.assertEqual([g["alt_konu"] for g in gorevler], beklenen)

        # Aynı mikro konu iki kez planlanmaz.
        self.assertEqual(len({g["alt_konu"] for g in gorevler}), 5)
        self.assertEqual(len({(g["tarih"], g["alt_konu"]) for g in gorevler}), 5)

        # Gerçek program çıktısı fixture olarak saklanır ve karşılaştırılır.
        kayit = {
            "senaryo": {
                "baslangic": V.REFERANS_TARIH.isoformat(),
                "musaitlik": {
                    str(gun): dakika
                    for gun, dakika in (
                        (1, 240), (2, 240), (3, 240), (4, 240), (5, 240),
                        (6, 300), (7, 300),
                    )
                },
                "bilinen_mikro": ["Fonksiyonlar", "Çarpanlara Ayırma"],
            },
            "ana_konu": V.POLINOM_ANA_KONU,
            "soru_hedefi": self._ana_hedef(),
            "gorevler": [V.gorev_ozeti(g) for g in gorevler],
        }
        guncelle = os.environ.get("FAZ5D_FIXTURE_GUNCELLE") == "1"
        if guncelle or not os.path.exists(FIXTURE_YOLU):
            os.makedirs(os.path.dirname(FIXTURE_YOLU), exist_ok=True)
            with open(FIXTURE_YOLU, "w", encoding="utf-8") as dosya:
                json.dump(kayit, dosya, ensure_ascii=False, indent=2)
                dosya.write("\n")
        with open(FIXTURE_YOLU, "r", encoding="utf-8") as dosya:
            beklenen_kayit = json.load(dosya)
        self.assertEqual(kayit, beklenen_kayit, "Gerçek program çıktısı değişti")

    # ------------------------------------------------------------------
    # 02 - HER GÖREV TEK MİKRO KONU
    # ------------------------------------------------------------------
    def test_02_her_gorev_tek_mikro_konu(self):
        # Odaklı senaryo
        for gorev in self._polinom():
            self.assertEqual(gorev["mikro_konu"], V.POLINOM_ANA_KONU)
            self.assertEqual(gorev["makro_konu"], V.POLINOM_MAKRO)
            self.assertNotIn("||", gorev["alt_konu"])
            self.assertIn(gorev["alt_konu"], self.mikro_alt[V.POLINOM_ANA_KONU])
            self.assertIn(gorev["alt_konu"], gorev["gorev_tanimi"])

        # Tam müfredat: hiçbir görevde birleştirilmiş alt başlık olmamalı
        sonuc = self._plan(mode="tam")
        for gorev in sonuc["gorevler"]:
            alt = gorev.get("alt_konu")
            if not alt:
                continue
            self.assertNotIn("||", alt, "Birleştirilmiş mikro konu: %s" % alt)
            alts = self.mikro_alt.get(gorev["mikro_konu"])
            if alts:
                self.assertIn(alt, alts)

        # Alt başlık listesi olmayan konular (9. sınıf Maarif müfredatı) yine
        # de tek görev olarak planlanır; hiçbir konu sessizce düşmez.
        sonuc = self._plan(mode="maarif9", bilinen_mikro=set())
        alt_siz = [
            g for g in sonuc["gorevler"]
            if g["ders"] != "TYT Türkçe"
            and not self.mikro_alt.get(g["mikro_konu"])
        ]
        self.assertTrue(alt_siz, "Alt başlığı olmayan konular planlanmalı")
        for gorev in alt_siz:
            self.assertIsNone(gorev["alt_konu"])
            self.assertGreater(gorev["hedef_soru"], 0)

    # ------------------------------------------------------------------
    # 03 - CHECKLIST'LER BAĞIMSIZ
    # ------------------------------------------------------------------
    def test_03_checklistler_bagimsiz(self):
        gorevler = self._polinom()
        soru_toplamlari = []
        for gorev in gorevler:
            adimlar = gorev["adimlar"]
            self.assertTrue(adimlar, "Her mikro görevin checklist'i olmalı")
            turler = [a["adim_turu"] for a in adimlar]
            self.assertEqual(turler.count(task_steps.ADIM_IZLE), 1)
            self.assertEqual(turler.count(task_steps.ADIM_NOT), 1)

            soru_adimlari = [
                a for a in adimlar if a["adim_turu"] == task_steps.ADIM_SORU
            ]
            hedef = int(gorev["hedef_soru"] or 0)
            self.assertEqual(sum(a["hedef_soru"] for a in soru_adimlari), hedef)
            # Soru blokları 5-10 aralığında (kota 5'in altındaysa tek blok).
            for adim in soru_adimlari:
                self.assertLessEqual(adim["hedef_soru"], task_steps.MAKS_SORU_BLOGU)
                if hedef >= task_steps.MIN_SORU_BLOGU:
                    self.assertGreaterEqual(
                        adim["hedef_soru"], task_steps.MIN_SORU_BLOGU
                    )
            soru_toplamlari.append(hedef)

        # Her görevin checklist'i kendi listesidir; hedefler birbirine geçmez.
        self.assertEqual(len({id(g["adimlar"]) for g in gorevler}), 5)
        self.assertEqual(sum(soru_toplamlari), self._ana_hedef())

    # ------------------------------------------------------------------
    # 04 - İLK GÖREV TAMAMLANINCA DİĞERLERİ AÇIK KALIR
    # ------------------------------------------------------------------
    def test_04_ilk_gorev_tamamlaninca_digerleri_acik(self):
        gorevler = self._polinom()
        program = self._programa_yaz(
            [g for g in self._plan()["gorevler"]
             if g["mikro_konu"] == V.POLINOM_ANA_KONU]
        )
        ilk = self._gorev_id(program, gorevler[0]["alt_konu"])
        # İlk mikro görevin anlatım/not adımları tamamlanır, soruları çözülür.
        for adim in task_steps.gorev_adimlari(ilk):
            if adim["adim_turu"] in task_steps.TURETILEN_ADIMLAR:
                continue
            task_steps.adim_durum_degistir(adim["id"], True)
        self._oturum(ilk, gorevler[0]["hedef_soru"], alt=gorevler[0]["alt_konu"])
        task_steps.gorev_durum_guncelle(ilk)
        self.assertTrue(task_steps.gorev_tamam_mi(ilk))

        for gorev in gorevler[1:]:
            gid = self._gorev_id(program, gorev["alt_konu"])
            self.assertFalse(
                task_steps.gorev_tamam_mi(gid),
                "Diğer mikro görevler açık kalmalı: %s" % gorev["alt_konu"],
            )
            for adim in task_steps.gorev_adimlari(gid):
                self.assertFalse(adim["tamam"])

        # Tamamlanan mikro konu yeniden planlanmaz.
        kalan = self._polinom(
            tamamlanan_altlar={
                ("AYT Matematik", V.POLINOM_ANA_KONU, gorevler[0]["alt_konu"])
            }
        )
        self.assertEqual(
            [g["alt_konu"] for g in kalan], [g["alt_konu"] for g in gorevler[1:]]
        )

    # ------------------------------------------------------------------
    # 05 - SÜRELER MİKRO KONUYA GÖRE
    # ------------------------------------------------------------------
    def test_05_sureler_mikro_konuya_gore(self):
        alts = self.mikro_alt[V.POLINOM_ANA_KONU]
        konu_sureleri = dict(self.uzay["KONU_SURELERI_DK"])
        konu_sureleri[alts[0]] = 60
        konu_sureleri[alts[2]] = 90
        gorevler = self._polinom(konu_sureleri=konu_sureleri)
        anlatim = {g["alt_konu"]: g["sure_plani"]["ogrenme_dk"] for g in gorevler}

        self.assertEqual(anlatim[alts[0]], 60)
        self.assertEqual(anlatim[alts[2]], 90)
        # Tanımlı süresi olmayan mikro konular TEK süre kaynağından
        # (`task_steps`) makul varsayılanı alır: ana konunun süresi ne
        # BÖLÜNÜR (80/5 = 16) ne de her mikro konuya KOPYALANIR (80).
        ana_sure = int(konu_sureleri[V.POLINOM_ANA_KONU])
        for alt in (alts[1], alts[3], alts[4]):
            self.assertEqual(anlatim[alt], task_steps.VARSAYILAN_KONU_SURESI_DK)
            self.assertNotEqual(anlatim[alt], ana_sure // len(alts))
            self.assertNotEqual(anlatim[alt], ana_sure)
        # Görev süreleri mikro konuya göre farklılaşır.
        self.assertGreater(len({g["tahmini_sure_dk"] for g in gorevler}), 1)

        # Gerçek veri varsa mikro konu bazında medyan uygulanır.
        for _ in range(3):
            self._oturum(None, 5, alt=alts[1], sure_dk=25)
        medyan = task_steps.konu_suresi_medyani(
            self.ogrenci, "AYT Matematik", V.POLINOM_ANA_KONU, alts[1]
        )
        self.assertEqual(medyan, 25)
        self.assertIsNone(
            task_steps.konu_suresi_medyani(
                self.ogrenci, "AYT Matematik", V.POLINOM_ANA_KONU, alts[3]
            ),
            "Bir mikro konunun medyanı diğerine uygulanmamalı",
        )

    # ------------------------------------------------------------------
    # 06 - SORU HEDEFLERİNİN TOPLAMI ANA HEDEFE EŞİT
    # ------------------------------------------------------------------
    def test_06_soru_hedefleri_toplami(self):
        alts = self.mikro_alt[V.POLINOM_ANA_KONU]
        ana_hedef = self._ana_hedef()
        gorevler = self._polinom()
        self.assertEqual(sum(g["hedef_soru"] for g in gorevler), ana_hedef)
        # Hiçbir mikro konuya ana hedefin TAMAMI verilmez.
        for gorev in gorevler:
            self.assertLess(gorev["hedef_soru"], ana_hedef)

        paylar = planner.mikro_soru_paylari(ana_hedef, alts)
        self.assertEqual(sum(paylar.values()), ana_hedef)
        self.assertEqual(set(paylar), set(alts))

        # Tüm AYT Matematik ana konuları için toplam korunur.
        for makro, mikrolar in V.mufredat("polinom")["AYT Matematik"].items():
            kredi = self.uzay["SORU_AGIRLIKLARI"].get(makro, 10.0)
            for ana in mikrolar:
                hedef = planner.mikro_soru_hedefi(
                    kredi, mikrolar, ana, self.uzay["KONU_SURELERI_DK"]
                )
                altlar = self.mikro_alt.get(ana) or []
                if not altlar:
                    continue
                pay = planner.mikro_soru_paylari(hedef, altlar)
                self.assertEqual(sum(pay.values()), hedef, ana)

    # ------------------------------------------------------------------
    # 07 - GERÇEK SORU İLERLEMESİ DOĞRU MİKRO KONUYA
    # ------------------------------------------------------------------
    def test_07_gercek_soru_ilerlemesi(self):
        alts = self.mikro_alt[V.POLINOM_ANA_KONU]
        ana_hedef = self._ana_hedef()
        paylar = planner.mikro_soru_paylari(ana_hedef, alts)

        # 1. mikro konunun TAM kotası çözülmüş: yalnızca o mikro konu düşer.
        tam = paylar[alts[0]]
        gorevler = {
            g["alt_konu"]: g
            for g in self._polinom(
                mikro_cozulen={("AYT Matematik", V.POLINOM_ANA_KONU, alts[0]): tam}
            )
        }
        self.assertNotIn(alts[0], gorevler, "Hedefi dolan mikro konu planlanmaz")
        for alt in alts[1:]:
            self.assertEqual(gorevler[alt]["hedef_soru"], paylar[alt])
        self.assertEqual(
            sum(g["hedef_soru"] for g in gorevler.values()), ana_hedef - tam
        )

        # Kısmi ilerleme: kalan soru kadar planlanır.
        gorevler = {
            g["alt_konu"]: g
            for g in self._polinom(
                mikro_cozulen={("AYT Matematik", V.POLINOM_ANA_KONU, alts[1]): 1}
            )
        }
        self.assertEqual(gorevler[alts[1]]["hedef_soru"], paylar[alts[1]] - 1)

        # Ana konu düzeyinde ilerleme de dikkate alınır; hedef dolunca görev yok.
        sonuc = self._plan(gercek_cozulen={("AYT Matematik", V.POLINOM_ANA_KONU): ana_hedef})
        self.assertEqual(V.polinom_gorevleri(sonuc), [])

    # ------------------------------------------------------------------
    # 08 - KALAN MİKRO KONULAR SONRAKİ HAFTAYA
    # ------------------------------------------------------------------
    def test_08_kalan_sorular_sonraki_haftaya(self):
        alts = self.mikro_alt[V.POLINOM_ANA_KONU]
        # 1. hafta: yalnızca pazartesi müsait (diğer günler dinlenme).
        dar = {1: 240, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}
        hafta1 = self._polinom(musaitlik=dar)
        self.assertEqual(len(hafta1), 1, "Tek günde tek ana ders mikro görevi")
        self.assertIn("kapasitesi", " ".join(self._plan(musaitlik=dar)["uyarilar"]))

        # 2. hafta: tamamlanan mikro konu tekrarlanmaz, kalanlar planlanır.
        bitti = ("AYT Matematik", V.POLINOM_ANA_KONU, hafta1[0]["alt_konu"])
        hafta2 = self._polinom(tamamlanan_altlar={bitti},
                               gercek_cozulen={("AYT Matematik", V.POLINOM_ANA_KONU):
                                              hafta1[0]["hedef_soru"]})
        self.assertEqual(
            [g["alt_konu"] for g in hafta2],
            [a for a in alts if a != hafta1[0]["alt_konu"]],
        )
        self.assertEqual(
            sum(g["hedef_soru"] for g in hafta2),
            self._ana_hedef() - hafta1[0]["hedef_soru"],
            "Kalan sorular sonraki haftaya devredilir",
        )

    # ------------------------------------------------------------------
    # 09 - GÜNLÜK KAPASİTE VE DİNLENME GÜNLERİ
    # ------------------------------------------------------------------
    def test_09_gunluk_kapasite_korunuyor(self):
        musaitlik = {1: 120, 2: 120, 3: 0, 4: 150, 5: 150, 6: 0, 7: 180}
        sonuc = self._plan(musaitlik=musaitlik)
        for gun in sonuc["gun_ozeti"]:
            self.assertLessEqual(gun["planlanan_dk"], gun["kapasite_dk"])
            if gun["kapasite_dk"] == 0:
                self.assertTrue(gun["dinlenme"])
                self.assertEqual(gun["gorev_sayisi"], 0, "Dinlenme günü boş kalmalı")
        # Toplam süre gün özetleriyle tutarlı
        self.assertEqual(
            sonuc["toplam_sure_dk"], sum(g["planlanan_dk"] for g in sonuc["gun_ozeti"])
        )

    # ------------------------------------------------------------------
    # 10 - FALLBACK MOTORLARI AYNI YAPIYI ÜRETİYOR
    # ------------------------------------------------------------------
    def test_10_fallback_ayni_yapi(self):
        alts = self.mikro_alt[V.POLINOM_ANA_KONU]
        konu_sureleri = self.uzay["KONU_SURELERI_DK"]
        # Eski motorların ürettiği biçim: ana konu görevi, alt başlık paketli.
        paketli = {
            "gun": "Pazartesi",
            "ders": "AYT Matematik",
            "makro_konu": V.POLINOM_MAKRO,
            "mikro_konu": V.POLINOM_ANA_KONU,
            "gorev_tanimi": "📌 ALT BAŞLIK + SORU: %s — bugünün alt başlıkları"
                            " 1) %s 2) %s" % (V.POLINOM_ANA_KONU, alts[0], alts[1]),
            "hedef_soru": 20,
            "pedagoji_turu": "Pekiştirme",
            "tarih": "2026-11-09",
            "alt_konu": "%s||%s" % (alts[0], alts[1]),
        }
        parcalar = planner.mikro_gorevlere_ayir(paketli, self.mikro_alt, konu_sureleri)
        self.assertEqual([p["alt_konu"] for p in parcalar], [alts[0], alts[1]])
        self.assertEqual(sum(p["hedef_soru"] for p in parcalar), 20)
        for parca in parcalar:
            self.assertNotIn("||", parca["alt_konu"])
            self.assertIn(parca["alt_konu"], parca["gorev_tanimi"])

        # Alt başlığı olmayan (tamamen makro) görev ana konunun tüm
        # mikro konularına ayrılır; soru ve süre toplamı korunur.
        makro_gorev = dict(paketli)
        makro_gorev.pop("alt_konu")
        makro_gorev["hedef_soru"] = 25
        parcalar = planner.mikro_gorevlere_ayir(
            makro_gorev, self.mikro_alt, konu_sureleri
        )
        self.assertEqual([p["alt_konu"] for p in parcalar], alts)
        self.assertEqual(sum(p["hedef_soru"] for p in parcalar), 25)
        # FAZ 5D: süre MİKRO KONU bazındadır; fallback motoru da aynı TEK
        # kaynağı (`task_steps`) kullanır (ana konu süresi bölünmez/kopyalanmaz).
        beklenen_sureler = [
            task_steps.mikro_anlatim_suresi(
                None, "AYT Matematik", V.POLINOM_ANA_KONU, alt, konu_sureleri
            )
            for alt in alts
        ]
        self.assertEqual(
            [p["konu_suresi_dk"] for p in parcalar], beklenen_sureler
        )

        # Idempotent: bölünmüş görevler yeniden bölünmez.
        tekrar = planner.mikro_gorevlere_ayir(parcalar, self.mikro_alt, konu_sureleri)
        self.assertEqual(len(tekrar), len(alts))

        # Tekrar ve deneme görevleri bölünmez.
        for ozel in (
            {**paketli, "pedagoji_turu": "Tekrar", "alt_konu": ""},
            {**paketli, "makro_konu": "Deneme Tekrarı", "alt_konu": ""},
        ):
            self.assertEqual(
                len(planner.mikro_gorevlere_ayir(ozel, self.mikro_alt, konu_sureleri)),
                1,
            )

    # ------------------------------------------------------------------
    # 11 - FAZ 6A: DOĞRU MİKRO GÖREVLE İLİŞKİ
    # ------------------------------------------------------------------
    def test_11_faz6a_dogru_mikro_gorev(self):
        gorevler = self._polinom()
        program = self._programa_yaz(
            [g for g in self._plan()["gorevler"]
             if g["mikro_konu"] == V.POLINOM_ANA_KONU]
        )
        ilk = self._gorev_id(program, gorevler[0]["alt_konu"])
        ikinci = self._gorev_id(program, gorevler[1]["alt_konu"])

        # Yalnızca ilk mikro görev tamamlanır.
        for adim in task_steps.gorev_adimlari(ilk):
            if adim["adim_turu"] in task_steps.TURETILEN_ADIMLAR:
                continue
            task_steps.adim_durum_degistir(adim["id"], True)
        self._oturum(ilk, gorevler[0]["hedef_soru"], alt=gorevler[0]["alt_konu"])
        task_steps.gorev_durum_guncelle(ilk)

        kayitlar = sr.tekrar_listesi(self.ogrenci)
        self.assertEqual(
            len(kayitlar), 1, "Yalnızca tamamlanan mikro görev tekrar üretir"
        )
        kayit = kayitlar[0]
        self.assertEqual(int(kayit["kaynak_gorev_id"]), ilk)
        self.assertEqual(kayit["tekrar_turu"], sr.TEKRAR_TURU_3_GUN)
        self.assertEqual(kayit["planlanan_tarih"], "2026-11-12")
        self.assertNotEqual(int(kayit["kaynak_gorev_id"]), ikinci)

        # Diğer mikro görevler tamamlanmadan tekrar üretilmez.
        for gorev in gorevler[2:]:
            gid = self._gorev_id(program, gorev["alt_konu"])
            self.assertEqual(sr.tekrar_planla(gid), [])

    # ------------------------------------------------------------------
    # 12 - FAZ 4 / 5 / 6A REGRESYONLARI
    # ------------------------------------------------------------------
    def test_12_regresyonlar(self):
        # FAZ 5B: soru blokları hâlâ 5-10 aralığında.
        self.assertEqual(task_steps.soru_bloklara_bol(12), [6, 6])
        self.assertEqual(task_steps.soru_bloklara_bol(7), [7])
        self.assertEqual(sum(task_steps.soru_bloklara_bol(23)), 23)

        # FAZ 5C/5D: her görev checklist + planlanan süre ile üretilir.
        sonuc = self._plan(mode="tam")
        self.assertTrue(sonuc["gorevler"])
        for gorev in sonuc["gorevler"]:
            self.assertTrue(gorev.get("adimlar"))
            self.assertGreaterEqual(int(gorev.get("tahmini_sure_dk") or 0), 5)

        # Paragraf bölünmez ve mikro konuya ayrılmaz.
        paragraf = [
            g for g in sonuc["gorevler"] if g["mikro_konu"] == "Günlük Paragraf"
        ]
        self.assertTrue(paragraf, "Günlük paragraf korunmalı")
        for gorev in paragraf:
            self.assertIsNone(gorev["alt_konu"])
            self.assertEqual(
                [a["adim_turu"] for a in gorev["adimlar"]], [task_steps.ADIM_SORU]
            )

        # FAZ 6A: 3 / 5 gün kuralı ve planlanan tarih hesabı korunur.
        self.assertEqual(sr.TEKRAR_GUN_SAYISI, 3)
        self.assertEqual(sr.NOT_TEKRARI_GUN_SAYISI, 5)
        self.assertEqual(
            sr.planlanan_tarih_hesapla(V.REFERANS_TARIH, 3), "2026-11-12"
        )

        # FAZ 5A: program servisi görevleri mikro konu + alt konu ile yazar.
        program = self._programa_yaz(
            [g for g in self._plan()["gorevler"]
             if g["mikro_konu"] == V.POLINOM_ANA_KONU]
        )
        yazilan = programs.program_gorevleri(program["id"])
        self.assertEqual(len(yazilan), 5)
        self.assertEqual(
            {g["alt_konu"] for g in yazilan},
            set(self.mikro_alt[V.POLINOM_ANA_KONU]),
        )
        for gorev in yazilan:
            self.assertEqual(gorev["mikro_konu"], V.POLINOM_ANA_KONU)
            self.assertIsNotNone(gorev["tahmini_sure_dk"])


    # ------------------------------------------------------------------
    # 13 - GÜNLÜK GÖREV KAPANINCA MİKRO KONU KAPANMAZ
    # ------------------------------------------------------------------
    def test_13_gunluk_gorev_mikro_konuyu_kapatmaz(self):
        alts = self.mikro_alt[V.POLINOM_ANA_KONU]
        hedefler = planner.mikro_soru_paylari(self._ana_hedef(), alts)
        program = self._programa_yaz(
            [g for g in self._plan()["gorevler"]
             if g["mikro_konu"] == V.POLINOM_ANA_KONU]
        )
        yazilan = {
            g["alt_konu"]: g for g in programs.program_gorevleri(program["id"])
        }

        # FAZ 5D: mikro konunun TAM soru hedefi programda saklanır.
        self.assertEqual(set(yazilan), set(alts))
        for alt, gorev in yazilan.items():
            self.assertEqual(int(gorev["mikro_hedef_soru"]), hedefler[alt])
            self.assertGreater(int(gorev["mikro_hedef_soru"]), 0)

        alt = alts[0]
        gorev_id = int(yazilan[alt]["id"])
        hedef = hedefler[alt]
        anahtar = ("AYT Matematik", V.POLINOM_ANA_KONU, alt)

        # Öğrenme adımları bitti + 3 soru çözüldü: mikro konu HÂLÂ AÇIK.
        for adim in task_steps.gorev_adimlari(gorev_id):
            if adim["adim_turu"] in task_steps.TURETILEN_ADIMLAR:
                continue
            task_steps.adim_durum_degistir(adim["id"], True)
        self._oturum(gorev_id, 3, alt=alt)
        ilerleme = task_steps.mikro_ilerleme_guncelle(gorev_id)
        self.assertTrue(ilerleme["ogrenme_tamam"])
        self.assertEqual(ilerleme["hedef_soru"], hedef)
        self.assertEqual(ilerleme["cozulen_soru"], 3)
        self.assertEqual(ilerleme["kalan_soru"], hedef - 3)
        self.assertFalse(ilerleme["tamamlandi"])
        self.assertNotIn(anahtar, task_steps.mikro_tamamlananlar(self.ogrenci))

        # Günlük görev TAMAMLANDI işaretlense bile mikro konu KAPANMAZ:
        # ilerleme yalnızca gerçek adım/oturumlardan türetilir.
        self.conn.execute(
            "UPDATE calisma_programi_gorevler SET durum = 1 WHERE id = ?",
            (gorev_id,),
        )
        self.conn.commit()
        task_steps.mikro_ilerleme_guncelle(gorev_id)
        ilerleme = task_steps.mikro_ilerleme(
            self.ogrenci, "AYT Matematik", V.POLINOM_ANA_KONU, alt
        )
        self.assertFalse(
            ilerleme["tamamlandi"], "Günlük görev durumu mikro konuyu kapatmaz"
        )
        self.assertEqual(ilerleme["cozulen_soru"], 3)
        self.assertEqual(ilerleme["kalan_soru"], hedef - 3)
        self.assertNotIn(anahtar, task_steps.mikro_tamamlananlar(self.ogrenci))

        # Kalan sorular GERÇEKTEN çözülünce mikro konu kapanır.
        self._oturum(gorev_id, hedef - 3, alt=alt)
        ilerleme = task_steps.mikro_ilerleme_guncelle(gorev_id)
        self.assertTrue(ilerleme["tamamlandi"])
        self.assertEqual(ilerleme["kalan_soru"], 0)
        self.assertEqual(
            task_steps.mikro_tamamlananlar(self.ogrenci), {anahtar},
            "Yalnızca hedefi dolan mikro konu kapanır",
        )

    # ------------------------------------------------------------------
    # 14 - DEVİR GÖREVİ YALNIZCA SORU TAŞIR
    # ------------------------------------------------------------------
    def test_14_devir_sadece_soru_tasir(self):
        alts = self.mikro_alt[V.POLINOM_ANA_KONU]
        # Geçen programdan 12 soru kalan mikro konu yeni haftaya devredilir.
        onceki = [{
            "id": 9001,
            "ders": "AYT Matematik",
            "makro_konu": V.POLINOM_MAKRO,
            "mikro_konu": V.POLINOM_ANA_KONU,
            "alt_konu": alts[0],
            "gorev_tanimi": "%s ➔ %s" % (V.POLINOM_ANA_KONU, alts[0]),
            "hedef_soru": 12,
            "mikro_hedef_soru": 12,
            "gercek_soru": 0,
            "devredilen_soru": 0,
            "durum": 0,
            "pedagoji_turu": "Pekiştirme",
            "tarih": "2026-11-09",
        }]
        sonuc = self._plan(onceki_gorevler=onceki)
        devir = [
            g for g in sonuc["gorevler"]
            if g["mikro_konu"] == V.POLINOM_ANA_KONU and g["alt_konu"] == alts[0]
        ]
        self.assertTrue(devir, "Kalan sorular devreden görev olarak planlanmalı")
        self.assertEqual(
            sum(g["hedef_soru"] for g in devir), 12,
            "Devredilen soruların TAMAMI planlanır",
        )
        for gorev in devir:
            # DEVAM görevi videoyu/notu yeniden istemez; yalnızca soru içerir.
            turler = [a["adim_turu"] for a in gorev["adimlar"]]
            self.assertEqual(set(turler), {task_steps.ADIM_SORU})
            self.assertEqual(
                sum(a["hedef_soru"] for a in gorev["adimlar"]),
                int(gorev["hedef_soru"]),
                "Soru blokları devredilen soru sayısına eşit olmalı",
            )
            self.assertEqual(int(gorev["mikro_hedef_soru"]), 12)
            self.assertEqual(int(gorev["kaynak_gorev_id"]), 9001)

        # Diğer mikro konular normal (anlatım + not + soru) planlanır.
        for gorev in sonuc["gorevler"]:
            if gorev["mikro_konu"] != V.POLINOM_ANA_KONU:
                continue
            if gorev["alt_konu"] == alts[0]:
                continue
            turler = [a["adim_turu"] for a in gorev["adimlar"]]
            self.assertIn(task_steps.ADIM_IZLE, turler)
            self.assertIn(task_steps.ADIM_NOT, turler)


    # ------------------------------------------------------------------
    # 15 - FAZ 6A: HER MİKRO KONU KENDİ TEKRARINI ÜRETİR
    # ------------------------------------------------------------------
    def test_15_tekrarlar_mikro_konuya_bagli(self):
        alts = self.mikro_alt[V.POLINOM_ANA_KONU]
        gorevler = {g["alt_konu"]: g for g in self._polinom()}
        program = self._programa_yaz(
            [g for g in self._plan()["gorevler"]
             if g["mikro_konu"] == V.POLINOM_ANA_KONU]
        )

        # Aynı ana konunun iki farklı mikro konusu tamamlanır.
        for alt in alts[:2]:
            gorev_id = self._gorev_id(program, alt)
            for adim in task_steps.gorev_adimlari(gorev_id):
                if adim["adim_turu"] in task_steps.TURETILEN_ADIMLAR:
                    continue
                task_steps.adim_durum_degistir(adim["id"], True)
            self._oturum(gorev_id, gorevler[alt]["hedef_soru"], alt=alt)
            task_steps.gorev_durum_guncelle(gorev_id)

        kayitlar = [
            k for k in sr.tekrar_listesi(self.ogrenci)
            if k["mikro_konu"] == V.POLINOM_ANA_KONU
        ]
        self.assertEqual(
            sorted(k["alt_konu"] for k in kayitlar), sorted(alts[:2]),
            "Her mikro konu KENDİ tekrar kaydını üretir",
        )
        for kayit in kayitlar:
            self.assertEqual(kayit["tekrar_turu"], sr.TEKRAR_TURU_3_GUN)
            self.assertEqual(kayit["planlanan_tarih"], "2026-11-12")
            self.assertIn(kayit["alt_konu"], kayit["aciklama"])

        # Ezber görevi: 3 günlük tekrar + 5 günlük özet notu, ikisi de mikro
        # konuya bağlı ve birbirini engellemez.
        ezber = {
            "ders": "TYT Tarih",
            "makro_konu": "İnkılap Tarihi",
            "mikro_konu": "Atatürk İlkeleri",
            "alt_konu": "İlkelerin Açıklanması",
            "gorev_tanimi": "📌 Atatürk İlkeleri ➔ İlkelerin Açıklanması",
            "hedef_soru": 10,
            "mikro_hedef_soru": 10,
            "pedagoji_turu": sr.EZBER_PEDAGOJISI,
            "tarih": "2026-11-09",
            "adimlar": [
                {"adim_turu": task_steps.ADIM_IZLE,
                 "baslik": "Konu anlatımını izle"},
                {"adim_turu": task_steps.ADIM_NOT,
                 "baslik": "Kısa özet notu çıkar"},
                {"adim_turu": task_steps.ADIM_SORU,
                 "baslik": "10 soru çöz", "hedef_soru": 10},
            ],
        }
        ezber_program = self._programa_yaz([ezber])
        ezber_id = self._gorev_id(ezber_program, ezber["alt_konu"])
        for adim in task_steps.gorev_adimlari(ezber_id):
            if adim["adim_turu"] in task_steps.TURETILEN_ADIMLAR:
                continue
            task_steps.adim_durum_degistir(adim["id"], True)
        self._oturum(
            ezber_id, 10, ders="TYT Tarih", makro="İnkılap Tarihi",
            mikro="Atatürk İlkeleri", alt=ezber["alt_konu"],
        )
        task_steps.gorev_durum_guncelle(ezber_id)

        ezber_kayitlar = [
            k for k in sr.tekrar_listesi(self.ogrenci)
            if k["mikro_konu"] == "Atatürk İlkeleri"
        ]
        self.assertEqual(
            sorted(k["tekrar_turu"] for k in ezber_kayitlar),
            sorted([sr.TEKRAR_TURU_3_GUN, sr.TEKRAR_TURU_5_GUN_NOT]),
            "Ezber görevi hem 3 hem 5 günlük tekrar üretir",
        )
        self.assertEqual(
            {k["planlanan_tarih"] for k in ezber_kayitlar},
            {"2026-11-12", "2026-11-14"},
        )
        for kayit in ezber_kayitlar:
            self.assertEqual(kayit["alt_konu"], ezber["alt_konu"])
            self.assertEqual(kayit["aciklama"].count(ezber["alt_konu"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
