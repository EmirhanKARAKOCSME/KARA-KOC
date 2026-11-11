"""FAZ 5D test altyapısı: main.py'deki GERÇEK müfredat verisini yükler.

main.py bir Streamlit uygulamasıdır; import edilmesi arayüzü çalıştırır.
Bu modül yalnızca modül düzeyindeki SAF VERİ atamalarını (`SORU_AGIRLIKLARI`,
`KONU_SURELERI_DK`, `mufredat_klasik`, `_ALT_*`, `ON_KOSULLAR` ...) AST
üzerinden değerlendirir. Böylece planlama motoru, kopyalanmış bir test
müfredatıyla değil uygulamanın gerçek verisiyle test edilir.

`MIKRO_ALT_KONULAR` main.py'de `update(_alt_ayristir(...))` çağrılarıyla
kurulduğu için burada aynı dönüşümle yeniden üretilir.
"""
import ast
import os
import sys
from datetime import date

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

MAIN_PY = os.path.join(KOK, "main.py")

POLINOM_ANA_KONU = "Polinomlar ve Çarpanlara Ayırma"
POLINOM_MAKRO = "İleri Cebir ve Fonksiyonlar"
REFERANS_TARIH = date(2026, 11, 9)  # Pazartesi

_uzay = None


def sabitler():
    """main.py'deki saf veri atamalarını döndürür (önbellekli)."""
    global _uzay
    if _uzay is not None:
        return _uzay
    with open(MAIN_PY, "r", encoding="utf-8") as dosya:
        agac = ast.parse(dosya.read(), MAIN_PY)
    uzay = {}
    for dugum in agac.body:
        if not isinstance(dugum, ast.Assign) or len(dugum.targets) != 1:
            continue
        hedef = dugum.targets[0]
        if not isinstance(hedef, ast.Name):
            continue
        try:
            ifade = ast.Expression(dugum.value)
            ast.fix_missing_locations(ifade)
            uzay[hedef.id] = eval(compile(ifade, MAIN_PY, "eval"), dict(uzay))
        except Exception:  # noqa: BLE001 - arayüz çağrıları atlanır
            continue
    _uzay = uzay
    return uzay


def _alt_ayristir(ham_sozluk):
    """main.py'deki `_alt_ayristir` ile aynı kural: 'A|B' -> ['A', 'B']."""
    sonuc = {}
    for anahtar, metin in (ham_sozluk or {}).items():
        sonuc[anahtar] = [p.strip() for p in str(metin).split("|") if p.strip()]
    return sonuc


def mikro_alt_konular():
    """Uygulamanın gerçek MIKRO_ALT_KONULAR haritası."""
    uzay = sabitler()
    sonuc = {}
    for ad in ("_ALT_TYT", "_ALT_AYT_SAYISAL"):
        sonuc.update(_alt_ayristir(uzay.get(ad)))
    return sonuc


def mufredat(mode="polinom"):
    """Planlama bağlamı için müfredat.

    - `polinom`: yalnızca AYT Matematik (odaklı senaryo)
    - `tam`: TYT + AYT Sayısal (tüm dersler)
    - `maarif9`: 9. sınıf Maarif müfredatı (alt başlık listesi olmayan konular)
    """
    uzay = sabitler()
    if mode == "maarif9":
        return {
            ders: gruplar
            for ders, gruplar in uzay["mufredat_maarif_9"].items()
            if isinstance(gruplar, dict)
        }
    klasik = uzay["mufredat_klasik"]
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
    uzay = sabitler()
    return {
        "ogrenci_id": ogrenci_id,
        "baslangic": baslangic or REFERANS_TARIH,
        "gun_sayisi": 7,
        "musaitlik": musaitlik
        or {1: 240, 2: 240, 3: 240, 4: 240, 5: 240, 6: 300, 7: 300},
        "mufredat": mufredat(mode),
        "konu_sureleri": konu_sureleri or uzay["KONU_SURELERI_DK"],
        "soru_agirliklari": uzay["SORU_AGIRLIKLARI"],
        "on_kosullar": {**uzay.get("ON_KOSULLAR_EK", {}), **uzay["ON_KOSULLAR"]},
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
