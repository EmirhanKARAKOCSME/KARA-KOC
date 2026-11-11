"""Alarm motoru testleri: Mor / Siyah kuralları ve "gerçekten çözülen sınav" kapısı.

Alarm hesaplaması artık `services/alarm_service.py`, deneme kohort serileri ise
`services/exam_service.py` içindedir. Bu modül gerçek servisleri import eder
(Streamlit arayüzü çalışmaz); `pandas` dışında ek bağımlılık yoktur.

Kapsam:
01 Tek denemenin çok satırlı yanlışları 3 "farklı deneme" sayılmaz.
02 Aynı gün aynı adla girilmiş AYRI denemeler tek sınav sayılmaz.
03 Mor: 3 farklı denemede yanlış var ve sayı artmıyor (2 ➔ 2 ➔ 1).
04 Siyah: 3 farklı denemede yanlış sayısı ivmeleniyor (1 ➔ 2 ➔ 4).
05 Sıfır yanlışlı deneme seriyi keser (alarm üretilmez).
06 Taslak (net/doğru/yanlış/boş/süre boş) deneme seriye girmez.
07 `deneme_id` bağlantısı olmayan eski detaylar yok sayılır.
08 Sınav türü / kategori / branş kohortları birbirine karışmaz.
09 Pencere yalnızca SON 3 farklı denemeyi değerlendirir.

Çalıştırma:
    python tests/test_alarm_motoru.py
    python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

import pandas as pd

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(TEST_KOK)
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from services import alarm_service, exam_service  # noqa: E402

DERS = "AYT Matematik"
MAKRO = "İleri Cebir ve Fonksiyonlar"
KONU = "Polinomlar ve Çarpanlara Ayırma"

_ISTENEN_ADLAR = (
    "ALARM_SERI_PENCERESI",
    "ALARM_MIN_YANLIS",
    "_DENEME_KANIT_KOLONLARI",
    "_deneme_tamamlanmis_mi",
    "kohort_yanlis_serileri",
    "_alarm_penceresi",
    "_alarm_ivmeleniyor",
    "_alarm_tekrar_ediyor",
)

KOLONLAR = [
    "id",
    "deneme_id",
    "deneme_adi",
    "tarih",
    "ders",
    "makro_konu",
    "konu_adi",
    "yanlis_adedi",
    "yanlis_nedeni",
    "deneme_tarih",
    "deneme_turu",
    "deneme_kategorisi",
    "brans_dersi",
    "deneme_net_bilgisi",
    "deneme_dogru_adedi",
    "deneme_yanlis_adedi",
    "deneme_bos_adedi",
    "deneme_sure_dk",
]

_modul = None


def alarm_modulu():
    """Alarm/deneme fonksiyonlarını gerçek servis modüllerinden toplar."""
    global _modul
    if _modul is not None:
        return _modul
    uzay = {}
    for ad in _ISTENEN_ADLAR:
        kaynak = alarm_service if hasattr(alarm_service, ad) else exam_service
        if not hasattr(kaynak, ad):
            raise AttributeError("Beklenen ad bulunamadı: %s" % ad)
        uzay[ad] = getattr(kaynak, ad)
    _modul = uzay
    return uzay

def deneme(
    deneme_id,
    tarih,
    yanlis,
    *,
    ad=None,
    ders=DERS,
    konu=KONU,
    tur="AYT",
    kategori="Genel Deneme",
    brans=None,
    net=20.0,
    dogru=10,
    deneme_yanlis=5,
    bos=0,
    sure=60,
):
    """Tek bir `deneme_konu_yanlislari` satırı (JOIN'li kolonlarla)."""
    return {
        "deneme_id": deneme_id,
        "deneme_adi": ad or f"Deneme {deneme_id}",
        "tarih": tarih,
        "ders": ders,
        "makro_konu": MAKRO,
        "konu_adi": konu,
        "yanlis_adedi": yanlis,
        "yanlis_nedeni": "Konu Eksikliği",
        "deneme_tarih": tarih,
        "deneme_turu": tur,
        "deneme_kategorisi": kategori,
        "brans_dersi": brans,
        "deneme_net_bilgisi": net,
        "deneme_dogru_adedi": dogru,
        "deneme_yanlis_adedi": deneme_yanlis,
        "deneme_bos_adedi": bos,
        "deneme_sure_dk": sure,
    }


def veri(*satirlar):
    """Satır listesinden, SQL sorgusunun döndürdüğü şemada DataFrame üretir."""
    kayitlar = []
    for i, satir in enumerate(satirlar, start=1):
        kayit = dict(satir)
        kayit["id"] = i
        kayit.setdefault("deneme_adi", f"Deneme {i}")
        kayit.setdefault("tarih", "2026-11-%02d" % i)
        kayit.setdefault("ders", DERS)
        kayit.setdefault("makro_konu", MAKRO)
        kayit.setdefault("konu_adi", KONU)
        kayit.setdefault("yanlis_adedi", 1)
        kayit.setdefault("yanlis_nedeni", "Konu Eksikliği")
        kayit.setdefault("deneme_tarih", kayit["tarih"])
        kayit.setdefault("deneme_turu", "AYT")
        kayit.setdefault("deneme_kategorisi", "Genel Deneme")
        kayit.setdefault("brans_dersi", None)
        kayit.setdefault("deneme_net_bilgisi", 20.0)
        kayit.setdefault("deneme_dogru_adedi", 10)
        kayit.setdefault("deneme_yanlis_adedi", 5)
        kayit.setdefault("deneme_bos_adedi", 0)
        kayit.setdefault("deneme_sure_dk", 60)
        kayitlar.append(kayit)
    return pd.DataFrame(kayitlar, columns=KOLONLAR)


def seri_ve_alarm(df):
    """(seri, alarm_turu, pencere_degerleri) döndürür.

    `hesapla_tum_alarmlar` içindeki if/elif sırası burada birebir uygulanır:
    Siyah ivmelenen seriyi, Mor ise artmayan tekrarı temsil eder.
    """
    modul = alarm_modulu()
    seriler = modul["kohort_yanlis_serileri"](df)
    if not seriler:
        return None, None, []
    seri = next(iter(seriler.values()))
    degerler = [n["yanlis"] for n in modul["_alarm_penceresi"](seri)]
    if modul["_alarm_ivmeleniyor"](degerler):
        return seri, "siyah", degerler
    if modul["_alarm_tekrar_ediyor"](degerler):
        return seri, "mor", degerler
    return seri, None, degerler


class AlarmMotoruTestleri(unittest.TestCase):
    def test_tek_denemenin_cok_satiri_alarm_uretmez(self):
        """Bir denemede aynı konudan 3 yanlış satırı: 3 'farklı deneme' değildir."""
        df = veri(
            deneme(1, "2026-11-01", 1),
            deneme(1, "2026-11-01", 2),
            deneme(1, "2026-11-01", 4),
        )
        seri, alarm, degerler = seri_ve_alarm(df)
        self.assertEqual(len(seri), 1, "Aynı deneme tek nokta olmalı")
        self.assertEqual(degerler, [4], "Satırlar MAX ile tekilleşir")
        self.assertIsNone(alarm)

    def test_ayni_gun_ayni_adli_denemeler_ayri_sinavdir(self):
        """Aynı gün aynı adla girilmiş İKİ AYRI deneme tek sınav sayılmaz.

        Gerçek veri: öğrenci aynı gün birden fazla "345 AYT Matematik" branş
        denemesi çözüp her birini ayrı kayıt olarak girer. Ad + tarih
        benzerliği üzerinden birleştirme yapılırsa 11 ayrı sınav tek sınava
        düşer ve alarm hiç üretilmez.
        """
        df = veri(
            deneme(
                1, "2026-11-01", 1, ad="345", kategori="Branş Denemesi",
                brans="AYT Matematik", net=25.0,
            ),
            deneme(
                2, "2026-11-01", 2, ad="345", kategori="Branş Denemesi",
                brans="AYT Matematik", net=25.0,
            ),
            deneme(
                3, "2026-11-01", 4, ad="345", kategori="Branş Denemesi",
                brans="AYT Matematik", net=25.0,
            ),
        )
        seri, alarm, degerler = seri_ve_alarm(df)
        self.assertEqual(len(seri), 3, "Her deneme kaydı ayrı sınavdır")
        self.assertEqual(degerler, [1, 2, 4])
        self.assertEqual(alarm, "siyah")

    def test_uc_farkli_denemede_artmayan_yanlis_mor_alarm(self):
        """2 ➔ 2 ➔ 1: yanlış sürüyor ama artmıyor ➔ Mor."""
        df = veri(
            deneme(1, "2026-11-01", 2),
            deneme(2, "2026-11-08", 2),
            deneme(3, "2026-11-15", 1),
        )
        _, alarm, degerler = seri_ve_alarm(df)
        self.assertEqual(degerler, [2, 2, 1])
        self.assertEqual(alarm, "mor")

    def test_ivmelenen_yanlis_siyah_alarm(self):
        """1 ➔ 2 ➔ 4: ivmelenen artış ➔ Siyah (Mor ile birlikte ÜRETİLMEZ)."""
        df = veri(
            deneme(1, "2026-11-01", 1),
            deneme(2, "2026-11-08", 2),
            deneme(3, "2026-11-15", 4),
        )
        _, alarm, degerler = seri_ve_alarm(df)
        self.assertEqual(degerler, [1, 2, 4])
        self.assertEqual(alarm, "siyah")

    def test_sifir_yanlis_seriyi_keser(self):
        """Arada yanlışsız deneme varsa 'kesintisiz yanlış' koşulu bozulur."""
        df = veri(
            deneme(1, "2026-11-01", 3),
            deneme(2, "2026-11-08", 0),
            deneme(3, "2026-11-15", 2),
        )
        _, alarm, degerler = seri_ve_alarm(df)
        self.assertEqual(degerler, [3, 0, 2])
        self.assertIsNone(alarm)

    def test_taslak_deneme_seriye_girmez(self):
        """Net ve soru dağılımı boş bir başlık çözülmüş sınav değildir."""
        taslak = dict(
            deneme_net_bilgisi=None,
            deneme_dogru_adedi=None,
            deneme_yanlis_adedi=None,
            deneme_bos_adedi=None,
            deneme_sure_dk=None,
        )
        df = veri(
            deneme(1, "2026-11-01", 2),
            {**deneme(2, "2026-11-08", 3), **taslak},
            deneme(3, "2026-11-15", 4),
        )
        _, alarm, degerler = seri_ve_alarm(df)
        self.assertEqual(degerler, [2, 4], "Taslak deneme pencereye alınmamalı")
        self.assertIsNone(alarm)

    def test_baglantisisiz_detaylar_yok_sayilir(self):
        """deneme_id'si olmayan eski kayıtlar seri üretmez."""
        df = veri(
            deneme(0, "2026-11-01", 1),
            deneme(0, "2026-11-08", 2),
            deneme(0, "2026-11-15", 4),
        )
        self.assertEqual(alarm_modulu()["kohort_yanlis_serileri"](df), {})

    def test_farkli_sinav_kohortlari_karismaz(self):
        """TYT genel / TYT branş / AYT denemeleri aynı seride birleşmez."""
        df = veri(
            deneme(1, "2026-11-01", 2, tur="TYT"),
            deneme(
                2,
                "2026-11-08",
                2,
                tur="TYT",
                kategori="Branş Denemesi",
                brans="TYT Matematik",
            ),
            deneme(3, "2026-11-15", 3, tur="AYT"),
        )
        seriler = alarm_modulu()["kohort_yanlis_serileri"](df)
        self.assertEqual(len(seriler), 3)
        for seri in seriler.values():
            self.assertEqual(len(seri), 1)

    def test_pencere_son_uc_denemeyi_degerlendirir(self):
        """Uzun seride yalnızca son 3 farklı deneme dikkate alınır."""
        df = veri(
            deneme(1, "2026-11-01", 4),
            deneme(2, "2026-11-08", 3),
            deneme(3, "2026-11-15", 2),
            deneme(4, "2026-11-22", 2),
            deneme(5, "2026-11-29", 1),
        )
        seri, alarm, degerler = seri_ve_alarm(df)
        self.assertEqual(len(seri), 5)
        self.assertEqual(degerler, [2, 2, 1])
        self.assertEqual(alarm, "mor")

    def test_pencere_ayni_deneme_id_tekrarini_atlar(self):
        """`_alarm_penceresi` aynı deneme_id'yi iki kez saymaz."""
        modul = alarm_modulu()
        seri = [
            {"deneme_id": 1, "tarih": "2026-11-01", "yanlis": 1, "ids": [1],
             "neden": "", "deneme_sayisi": 1},
            {"deneme_id": 1, "tarih": "2026-11-01", "yanlis": 4, "ids": [2],
             "neden": "", "deneme_sayisi": 1},
            {"deneme_id": 2, "tarih": "2026-11-08", "yanlis": 2, "ids": [3],
             "neden": "", "deneme_sayisi": 1},
        ]
        pencere = modul["_alarm_penceresi"](seri)
        self.assertEqual([n["deneme_id"] for n in pencere], [1, 2])
        self.assertEqual(modul["ALARM_SERI_PENCERESI"], 3)
        self.assertEqual(modul["ALARM_MIN_YANLIS"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

