"""FAZ 5D test altyapısı: uygulamanın GERÇEK müfredat verisini yükler.

Veriler artık `main.py` içinde değil, saf veri paketi `data/` altındadır
(bkz. FAZ A refactoring). Bu modül testlere eski API'yi (`sabitler`,
`mufredat`, `mikro_alt_konular`, `baglam`) aynen sunar; böylece planlama
motoru testleri kopyalanmış bir müfredatla değil, ürünün gerçek verisiyle
çalışmaya devam eder.

`data/` modülleri yan etkisizdir: import edilmeleri Streamlit'i veya
veritabanını çalıştırmaz.
"""
import os
import sys
from datetime import date

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

from data.curriculum import mufredat_klasik as _MUFREDAT_KLASIK  # noqa: E402
from data.curriculum import mufredat_maarif_9 as _MUFREDAT_MAARIF  # noqa: E402
from data.prerequisites import ON_KOSULLAR  # noqa: E402
from data.subtopics import (  # noqa: E402
    _ALT_AYT_SAYISAL,
    _ALT_TYT,
    MIKRO_ALT_KONULAR,
)
from data.weights_and_times import (  # noqa: E402
    KONU_SURELERI_DK,
    SORU_AGIRLIKLARI,
)

POLINOM_ANA_KONU = "Polinomlar ve Çarpanlara Ayırma"
POLINOM_MAKRO = "İleri Cebir ve Fonksiyonlar"
REFERANS_TARIH = date(2026, 11, 9)  # Pazartesi


def sabitler():
    """Testlerin kullandığı gerçek veri sabitleri."""
    return {
        "SORU_AGIRLIKLARI": SORU_AGIRLIKLARI,
        "KONU_SURELERI_DK": KONU_SURELERI_DK,
        "mufredat_klasik": _MUFREDAT_KLASIK,
        "mufredat_maarif_9": _MUFREDAT_MAARIF,
        "ON_KOSULLAR": ON_KOSULLAR,
        "_ALT_TYT": _ALT_TYT,
        "_ALT_AYT_SAYISAL": _ALT_AYT_SAYISAL,
    }


def _alt_ayristir(ham_sozluk):
    """`data.subtopics._alt_ayristir` ile aynı kural: 'A|B' -> ['A', 'B']."""
    sonuc = {}
    for anahtar, metin in (ham_sozluk or {}).items():
        sonuc[anahtar] = [p.strip() for p in str(metin).split("|") if p.strip()]
    return sonuc


def mikro_alt_konular():
    """Uygulamanın gerçek MIKRO_ALT_KONULAR haritası (kopya)."""
    return {anahtar: list(altlar) for anahtar, altlar in MIKRO_ALT_KONULAR.items()}


def mufredat(mode="polinom"):
    """Planlama bağlamı için müfredat.

    - `polinom`: yalnızca AYT Matematik (odaklı senaryo)
    - `tam`: TYT + AYT Sayısal (tüm dersler)
    - `maarif9`: 9. sınıf Maarif müfredatı (alt başlık listesi olmayan konular)
    """
    if mode == "maarif9":
        return {
            ders: gruplar
            for ders, gruplar in _MUFREDAT_MAARIF.items()
            if isinstance(gruplar, dict)
        }
    klasik = _MUFREDAT_KLASIK
    if mode == "polinom":
        return {"AYT Matematik": klasik["AYT"]["Sayısal"]["AYT Matematik"]}
    sonuc = {}
    for ders, gruplar in (klasik.get("TYT") or {}).items():
        sonuc[ders] = gruplar
    for ders, gruplar in ((klasik.get("AYT") or {}).get("Sayısal") or {}).items():
        sonuc[ders] = gruplar
    return sonuc


def baglam(
    mode="polinom",
    musaitlik=None,
    bilinen_mikro=None,
    gercek_cozulen=None,
    mikro_cozulen=None,
    onceki_gorevler=None,
    tamamlanan_altlar=None,
    konu_sureleri=None,
    baslangic=None,
    paragraf_soru=20,
    ogrenci_id=1,
):
    """`planner.plan_uret` için gerçek verilerle bağlam kurar."""
    return {
        "ogrenci_id": ogrenci_id,
        # v2.3: bu test verisi ESKİ motor davranışını doğrular; yeni (her zaman
        # aktif) sınıf/alan kilidini kapatmak için açık opt-out gerekir.
        "legacy_mod": True,
        "baslangic": baslangic or REFERANS_TARIH,
        "gun_sayisi": 7,
        "musaitlik": musaitlik
        or {1: 240, 2: 240, 3: 240, 4: 240, 5: 240, 6: 300, 7: 300},
        "mufredat": mufredat(mode),
        "konu_sureleri": konu_sureleri or KONU_SURELERI_DK,
        "soru_agirliklari": SORU_AGIRLIKLARI,
        "on_kosullar": ON_KOSULLAR,
        "mikro_alt": mikro_alt_konular(),
        # Polinomlar'ın ön koşulu olan TYT konuları biliniyor varsayılır.
        "bilinen_mikro": set(bilinen_mikro if bilinen_mikro is not None
                             else ("Fonksiyonlar", "Çarpanlara Ayırma")),
        "gercek_cozulen": dict(gercek_cozulen or {}),
        "mikro_cozulen": dict(mikro_cozulen or {}),
        "onceki_gorevler": list(onceki_gorevler or []),
        "paragraf_soru": paragraf_soru,
        "pedagoji": {},
        "tamamlanan_altlar": set(tamamlanan_altlar or ()),
        "alarm_konular": [],
    }


def gorev_ozeti(gorev):
    """Görev sözlüğünü karşılaştırılabilir sade bir sözlüğe çevirir."""
    return {
        "tarih": gorev.get("tarih"),
        "ders": gorev.get("ders"),
        "makro_konu": gorev.get("makro_konu"),
        "mikro_konu": gorev.get("mikro_konu"),
        "alt_konu": gorev.get("alt_konu"),
        "hedef_soru": int(gorev.get("hedef_soru") or 0),
        "mikro_hedef_soru": int(gorev.get("mikro_hedef_soru") or 0),
        "tahmini_sure_dk": int(gorev.get("tahmini_sure_dk") or 0),
        "pedagoji_turu": gorev.get("pedagoji_turu"),
        "gorev_turu": gorev.get("gorev_turu"),
        "gorev_tanimi": gorev.get("gorev_tanimi"),
        "adimlar": [
            {
                "baslik": adim.get("baslik"),
                "adim_turu": adim.get("adim_turu"),
                "hedef_soru": int(adim.get("hedef_soru") or 0),
            }
            for adim in gorev.get("adimlar") or []
        ],
    }


def polinom_gorevleri(sonuc):
    """Plan sonucundan Polinomlar ana konusunun görevlerini süz."""
    return [
        gorev
        for gorev in (sonuc.get("gorevler") or [])
        if gorev.get("mikro_konu") == POLINOM_ANA_KONU
    ]
