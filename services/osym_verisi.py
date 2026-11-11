"""FAZ 8 - ÖSYM sınav kuralları ve puan-sıra referans verisi (VERİ KATMANI).

Bu modül **hesap yapmaz**. Yalnızca şunları taşır ve doğrular:

1. Hangi sınav yılının hangi kural setiyle hesaplanacağı (`KURAL_SETLERI`).
2. Puan türü başına test katsayıları ve soru sayıları.
3. OBP (ortaöğretim başarı puanı) katsayısı.
4. Doğrulanmış puan-sıra referans noktaları (JSON dosyası).

Neden ayrı katman?
- Puan hesaplama (model) ile sıralama tahmini farklı işlemlerdir. İkisi ayrı
  tutulur; sıralama yalnızca gerçek referans verisi varsa üretilir.
- Katsayılar ve yıllara özgü kurallar kodun içine dağınık sabitler olarak
  gömülmez; tek bir yerde, kaynak bilgisiyle birlikte durur.
- Resmî olmayan hiçbir sayı "resmî veri" gibi etiketlenmez. Bu sürümde
  puan-sıra referans dosyası **boştur** (bkz. `data/osym_puan_sira.json`).

DÜRÜSTLÜK KURALLARI (bilinçli sınırlar)
---------------------------------------
- `KURAL_SETLERI` içindeki katsayılar, ÖSYM'nin test ağırlık yapısıyla
  tutarlı (maksimum ham puan 500 olacak şekilde) **doğrusal model**
  katsayılarıdır. `dogrulama_durumu` alanı bu sürümde `"dogrulanmadi"`
  değerindedir: katsayıların ilgili yılın resmî kılavuzuyla karşılaştırılması
  gerekir.
- ÖSYM'nin resmî puanı, testlerin yıl bazlı ortalama ve standart sapmalarıyla
  yapılan bir standart puan dönüşümü içerir. Bu veriler olmadan **resmî puan
  üretilemez**; bu modül de üretmez.
- Bu modül hiçbir puan-sıra tablosunu "tahminen" doldurmaz. Boş veri,
  boş kalır ve çağıran katman bunu kullanıcıya açıkça bildirir.

Bu modül Streamlit'e bağımlı değildir; testler doğrudan çağırabilir.
"""
import json
import os
import tempfile
from datetime import date, datetime

# ==============================================================================
# SABİTLER
# ==============================================================================
VARSAYILAN_VERI_DOSYASI = os.path.join("data", "osym_puan_sira.json")
VERI_SURUMU = 1

PUAN_TURLERI = (
    "TYT",
    "Sayısal",
    "Eşit Ağırlık",
    "Sözel",
    "Dil",
)

# Kanonik puan türü -> kısa kod (dosya/etiket uyumu için).
PUAN_TURU_KODLARI = {
    "TYT": "TYT",
    "Sayısal": "SAY",
    "Eşit Ağırlık": "EA",
    "Sözel": "SOZ",
    "Dil": "DIL",
}

# YKS'de test başına soru sayıları (sınav yapısı).
TEST_SORU_SAYILARI = {
    "TYT Türkçe": 40,
    "TYT Matematik": 40,
    "TYT Sosyal Bilimler": 20,
    "TYT Fen Bilimleri": 20,
    "AYT Matematik": 40,
    "AYT Fizik": 14,
    "AYT Kimya": 13,
    "AYT Biyoloji": 13,
    "AYT Edebiyat": 24,
    "AYT Tarih-1": 10,
    "AYT Coğrafya-1": 6,
    "AYT Tarih-2": 11,
    "AYT Coğrafya-2": 11,
    "AYT Felsefe Grubu": 12,
    "AYT Din Kültürü": 6,
    "YDT İngilizce": 80,
}

# TYT puanı: test başına toplam katkı (40x3.3 + 40x3.3 + 20x3.4 + 20x3.4 = 400).
TYT_KATSAYILARI = {
    "TYT Türkçe": 3.30,
    "TYT Matematik": 3.30,
    "TYT Sosyal Bilimler": 3.40,
    "TYT Fen Bilimleri": 3.40,
}

# AYT/YDT puan türlerinde TYT'nin payı (toplam 160 puan).
TYT_AYT_PAYI_KATSAYILARI = {
    "TYT Türkçe": 1.32,
    "TYT Matematik": 1.32,
    "TYT Sosyal Bilimler": 1.36,
    "TYT Fen Bilimleri": 1.36,
}

# AYT/YDT puan türleri: alan testlerinin katkısı (toplam 240 puan).
AYT_KATSAYILARI = {
    "Sayısal": {
        "AYT Matematik": 3.00,
        "AYT Fizik": 2.85,
        "AYT Kimya": 3.07,
        "AYT Biyoloji": 3.07,
    },
    "Eşit Ağırlık": {
        "AYT Matematik": 3.00,
        "AYT Edebiyat": 3.00,
        "AYT Tarih-1": 2.80,
        "AYT Coğrafya-1": 3.33,
    },
    "Sözel": {
        "AYT Edebiyat": 3.00,
        "AYT Tarih-1": 2.80,
        "AYT Coğrafya-1": 3.33,
        "AYT Tarih-2": 2.91,
        "AYT Coğrafya-2": 2.91,
        "AYT Felsefe Grubu": 3.00,
        "AYT Din Kültürü": 3.33,
    },
    "Dil": {
        "YDT İngilizce": 3.00,
    },
}

TABAN_PUAN = 100.0
MAKS_HAM_PUAN = 500.0
MAKS_YERLESTIRME_PUANI = 560.0
OBP_KATSAYISI = 0.12
OBP_DIPLOMA_ALT = 50.0
OBP_DIPLOMA_UST = 100.0
OBP_PUAN_CARPANI = 5.0

# Sıralama tahmini için gereken en az referans noktası sayısı.
MIN_NOKTA = 3

# ==============================================================================
# KURAL SETLERİ (yıl bazlı)
# ==============================================================================
DESTEKLENEN_YILLAR = (
    "2018",
    "2019",
    "2020",
    "2021",
    "2022",
    "2023",
    "2024",
    "2025",
    "2026",
)

# Her kural seti bir kaynağa bağlıdır. Kaynak bilgisi olmadan kural tanımlanmaz.
KAYNAKLAR = {
    "MODEL_YKS_DOGRUSAL": {
        "kurum": "ÖSYM (YKS kılavuzlarındaki test ağırlık yapısı)",
        "belge": (
            "YKS puan türlerinde testlerin ağırlıkları; taban puan 100, "
            "ham puan üst sınırı 500, OBP katkı katsayısı 0.12"
        ),
        "url": "https://www.osym.gov.tr/",
        "kayit_tarihi": "2026-11-11",
        "erisim_tarihi": None,
        "kapsam": (
            "Doğrusal ham puan modeli katsayıları (test başına katkı). "
            "Yıllık test ortalama/standart sapma değerleri KULLANILMAZ."
        ),
        "guvenilirlik": "model",
        "dogrulama_durumu": "dogrulanmadi",
        "sinirlilik": (
            "Resmî ÖSYM puanı değildir. ÖSYM'nin standart puan (T/S) "
            "dönüşümü yıl bazlı ortalama ve standart sapma gerektirir; bu "
            "katsayılar yalnızca tahmin modeli içindir. Yayımlanan kılavuzla "
            "karşılaştırılıp doğrulanmalıdır."
        ),
    },
}

DYOGRULAMA_DOGRULANMADI = "dogrulanmadi"
DOGRULAMA_DOGRULANDI = "dogrulandi"


def _kural_olustur(yil):
    """Bir yıl için kural seti sözlüğü üretir (kopyalar; paylaşılan referans yok)."""
    return {
        "yil": yil,
        "model": "yks_dogrusal",
        "kaynak_kodu": "MODEL_YKS_DOGRUSAL",
        "taban_puan": TABAN_PUAN,
        "maks_ham_puan": MAKS_HAM_PUAN,
        "maks_yerlestirme_puani": MAKS_YERLESTIRME_PUANI,
        "obp_katsayisi": OBP_KATSAYISI,
        "tyt_katsayilari": dict(TYT_KATSAYILARI),
        "tyt_ayt_payi_katsayilari": dict(TYT_AYT_PAYI_KATSAYILARI),
        "ayt_katsayilari": {
            tur: dict(degerler) for tur, degerler in AYT_KATSAYILARI.items()
        },
        "dogrulama_durumu": DYOGRULAMA_DOGRULANMADI,
    }


KURAL_SETLERI = {yil: _kural_olustur(yil) for yil in DESTEKLENEN_YILLAR}


class VeriHatasi(ValueError):
    """Geçersiz yıl, puan türü veya bozuk referans verisi."""


def desteklenen_yillar():
    """Desteklenen sınav yılları (eskiden yeniye)."""
    return list(DESTEKLENEN_YILLAR)


def varsayilan_yil():
    """En güncel desteklenen sınav yılı."""
    return DESTEKLENEN_YILLAR[-1]


def yil_normalize(yil):
    """Yılı 'YYYY' metnine çevirir; desteklenmiyorsa VeriHatasi."""
    if yil is None or (isinstance(yil, str) and not yil.strip()):
        return varsayilan_yil()
    metin = str(yil).strip()
    if len(metin) == 2 and metin.isdigit():
        metin = "20" + metin
    if metin not in KURAL_SETLERI:
        raise VeriHatasi(
            "Bu sınav yılı için kural tanımlı değil: %s (desteklenen: %s – %s)."
            % (metin, DESTEKLENEN_YILLAR[0], DESTEKLENEN_YILLAR[-1])
        )
    return metin


def kural_seti(yil=None):
    """İlgili yılın kural setini döndürür (kopya)."""
    kod = yil_normalize(yil)
    kural = _kural_olustur(kod)
    kural["kaynak"] = dict(KAYNAKLAR[kural["kaynak_kodu"]])
    return kural


def puan_turu_kontrol(puan_turu):
    """Kanonik puan türünü döndürür; geçersizse VeriHatasi."""
    metin = str(puan_turu or "").strip().upper()
    esleme = {
        "TYT": "TYT",
        "TEMEL YETERLILIK": "TYT",
        "SAY": "Sayısal",
        "SAYISAL": "Sayısal",
        "MF": "Sayısal",
        "EA": "Eşit Ağırlık",
        "EŞİT AĞIRLIK": "Eşit Ağırlık",
        "ESIT AGIRLIK": "Eşit Ağırlık",
        "TM": "Eşit Ağırlık",
        "SOZ": "Sözel",
        "SÖZEL": "Sözel",
        "SOZEL": "Sözel",
        "TS": "Sözel",
        "DIL": "Dil",
        "DİL": "Dil",
        "YDT": "Dil",
        "YABANCI DIL": "Dil",
    }
    for anahtar in (metin, metin.replace("İ", "I")):
        if anahtar in esleme:
            return esleme[anahtar]
    # Türkçe küçük/büyük harf farklılıklarını tolere et.
    sade = metin.replace("İ", "I").replace("Ş", "S").replace("Ğ", "G")
    sade = sade.replace("Ü", "U").replace("Ö", "O").replace("Ç", "C")
    esleme_sade = {
        "ESIT AGIRLIK": "Eşit Ağırlık",
        "SOZEL": "Sözel",
        "SAYISAL": "Sayısal",
        "DIL": "Dil",
    }
    if sade in esleme_sade:
        return esleme_sade[sade]
    raise VeriHatasi(
        "Geçersiz puan türü: %s (desteklenen: %s)."
        % (puan_turu, ", ".join(PUAN_TURLERI))
    )


def testleri_getir(puan_turu):
    """Puan türü için [(test, katsayı)] listesi (TYT testleri + alan testleri)."""
    tur = puan_turu_kontrol(puan_turu)
    if tur == "TYT":
        return list(TYT_KATSAYILARI.items())
    testler = list(TYT_AYT_PAYI_KATSAYILARI.items())
    testler.extend(AYT_KATSAYILARI[tur].items())
    return testler


def test_soru_sayisi(test):
    """Testin soru sayısı; tanımsızsa None."""
    return TEST_SORU_SAYILARI.get(str(test or "").strip())


# ==============================================================================
# OBP (ORTAÖĞRETİM BAŞARI PUANI)
# ==============================================================================
def obp_puani(diploma_notu):
    """Diploma notundan OBP üretir: OBP = diploma notu x 5 (50–100 aralığı)."""
    try:
        notu = float(diploma_notu)
    except (TypeError, ValueError):
        raise VeriHatasi("Diploma notu sayısal olmalıdır.") from None
    if notu != notu:  # NaN
        raise VeriHatasi("Diploma notu sayısal olmalıdır.")
    sinirli = min(OBP_DIPLOMA_UST, max(OBP_DIPLOMA_ALT, notu))
    return round(sinirli * OBP_PUAN_CARPANI, 2)


def obp_katkisi(diploma_notu, yil=None):
    """OBP'nin yerleştirme puanına katkısı (en fazla 60 puan)."""
    kural = kural_seti(yil)
    return round(obp_puani(diploma_notu) * kural["obp_katsayisi"], 2)


# ==============================================================================
# PUAN-SIRA REFERANS VERİSİ (JSON)
# ==============================================================================
# Şema:
# {
#   "surum": 1,
#   "guncelleme": "YYYY-AA-GG",
#   "kayitlar": [
#     {
#       "yil": "2024",
#       "puan_turu": "Sayısal",
#       "kaynak": {"kurum": "...", "belge": "...", "url": "...",
#                  "erisim_tarihi": "YYYY-AA-GG"},
#       "not": "serbest açıklama",
#       "noktalar": [{"puan": 450.0, "sira": 12000}, ...]
#     }
#   ]
# }
#
# Kurallar:
# - Noktalar puan olarak AZALAN, sıra olarak ARTAN olmalıdır.
# - En az MIN_NOKTA nokta gerekir (arada tahmin için).
# - Puan [taban, maks yerleştirme] aralığında, sıra >= 1 olmalıdır.
# - Kaynak kurum + belge zorunludur; kaynaksız veri reddedilir.

_veri_yolu = VARSAYILAN_VERI_DOSYASI


def veri_dosyasi_ayarla(yol):
    """Testlerin geçici referans dosyası kullanmasını sağlar (None = varsayılan)."""
    global _veri_yolu
    _veri_yolu = yol or VARSAYILAN_VERI_DOSYASI


def veri_dosyasi():
    return _veri_yolu


def bos_veri():
    """Boş (kaynaksız veri içermeyen) referans yapısı."""
    return {"surum": VERI_SURUMU, "guncelleme": None, "kayitlar": []}


def _sayi(deger, ad):
    try:
        return float(deger)
    except (TypeError, ValueError):
        raise VeriHatasi("%s sayısal olmalıdır: %r" % (ad, deger)) from None


def _tarih_metni(deger, ad, zorunlu=False):
    """'YYYY-AA-GG' doğrulaması; zorunlu değilse boş bırakılabilir."""
    metin = "" if deger is None else str(deger).strip()
    if not metin:
        if zorunlu:
            raise VeriHatasi("%s boş olamaz." % ad)
        return None
    if len(metin) < 10:
        raise VeriHatasi("%s YYYY-AA-GG biçiminde olmalıdır: %s" % (ad, metin))
    try:
        datetime.strptime(metin[:10], "%Y-%m-%d")
    except ValueError:
        raise VeriHatasi(
            "%s YYYY-AA-GG biçiminde olmalıdır: %s" % (ad, metin)
        ) from None
    return metin[:10]


def kayit_dogrula(kayit):
    """Tek bir veri kaydını doğrular; hata mesajları listesi döndürür."""
    hatalar = []
    if not isinstance(kayit, dict):
        return ["Kayıt bir sözlük olmalıdır."]

    yil = str(kayit.get("yil") or "").strip()
    if yil not in KURAL_SETLERI:
        hatalar.append(
            "Geçersiz sınav yılı: %r (desteklenen: %s)."
            % (kayit.get("yil"), ", ".join(DESTEKLENEN_YILLAR))
        )

    try:
        puan_turu_kontrol(kayit.get("puan_turu"))
    except VeriHatasi as hata:
        hatalar.append(str(hata))

    kaynak = kayit.get("kaynak")
    if not isinstance(kaynak, dict):
        hatalar.append("Kaynak bilgisi zorunludur (kurum ve belge).")
    else:
        for alan, etiket in (("kurum", "Kaynak kurum"), ("belge", "Kaynak belge")):
            if not str(kaynak.get(alan) or "").strip():
                hatalar.append("%s boş olamaz." % etiket)
        try:
            _tarih_metni(kaynak.get("erisim_tarihi"), "Kaynağa erişim tarihi")
        except VeriHatasi as hata:
            hatalar.append(str(hata))

    noktalar = kayit.get("noktalar")
    if not isinstance(noktalar, list):
        hatalar.append("Noktalar bir liste olmalıdır.")
        return hatalar
    if len(noktalar) < MIN_NOKTA:
        hatalar.append(
            "En az %d referans noktası gerekir (veri: %d)."
            % (MIN_NOKTA, len(noktalar))
        )

    temiz = []
    for sira_no, nokta in enumerate(noktalar, start=1):
        if not isinstance(nokta, dict):
            hatalar.append("%d. nokta bir sözlük olmalıdır." % sira_no)
            continue
        try:
            puan = _sayi(nokta.get("puan"), "%d. nokta puanı" % sira_no)
            siralama = _sayi(nokta.get("sira"), "%d. nokta sırası" % sira_no)
        except VeriHatasi as hata:
            hatalar.append(str(hata))
            continue
        if puan < TABAN_PUAN or puan > MAKS_YERLESTIRME_PUANI:
            hatalar.append(
                "%d. nokta puanı %.2f, [%d, %d] aralığında olmalıdır."
                % (sira_no, puan, TABAN_PUAN, MAKS_YERLESTIRME_PUANI)
            )
        if siralama < 1 or siralama != int(siralama):
            hatalar.append(
                "%d. nokta sırası pozitif tam sayı olmalıdır: %s"
                % (sira_no, nokta.get("sira"))
            )
        temiz.append((puan, siralama))

    onceki = None
    for indeks, (puan, siralama) in enumerate(temiz):
        if onceki is not None:
            onceki_puan, onceki_sira = onceki
            if puan >= onceki_puan:
                hatalar.append(
                    "Noktalar puan olarak azalan sırada olmalıdır (%d. nokta)."
                    % (indeks + 1)
                )
            if siralama <= onceki_sira:
                hatalar.append(
                    "Noktalar sıra olarak artan sırada olmalıdır (%d. nokta)."
                    % (indeks + 1)
                )
        onceki = (puan, siralama)
    return hatalar


def kayit_normalize(kayit):
    """Doğrulanmış kaydı yazılabilir, sade bir sözlüğe çevirir."""
    temiz_noktalar = []
    for nokta in kayit.get("noktalar") or []:
        temiz_noktalar.append(
            {"puan": round(float(nokta["puan"]), 2), "sira": int(nokta["sira"])}
        )
    kaynak = kayit.get("kaynak") or {}
    return {
        "yil": str(kayit["yil"]).strip(),
        "puan_turu": puan_turu_kontrol(kayit["puan_turu"]),
        "kaynak": {
            "kurum": str(kaynak.get("kurum") or "").strip(),
            "belge": str(kaynak.get("belge") or "").strip(),
            "url": str(kaynak.get("url") or "").strip(),
            "erisim_tarihi": _tarih_metni(
                kaynak.get("erisim_tarihi"), "Kaynağa erişim tarihi"
            ),
        },
        "not": str(kayit.get("not") or "").strip(),
        "noktalar": temiz_noktalar,
    }


def veri_yukle(yol=None):
    """Referans dosyasını okur. Dosya yoksa boş yapı döner (hata üretmez)."""
    hedef = yol or _veri_yolu
    if not os.path.exists(hedef):
        return bos_veri()
    try:
        with open(hedef, "r", encoding="utf-8") as dosya:
            veri = json.load(dosya)
    except (OSError, ValueError) as hata:
        raise VeriHatasi(
            "Puan-sıra referans dosyası okunamadı (%s): %s" % (hedef, hata)
        ) from None
    if not isinstance(veri, dict) or not isinstance(veri.get("kayitlar"), list):
        raise VeriHatasi(
            "Puan-sıra referans dosyası geçersiz yapıda (%s)." % hedef
        )
    return {
        "surum": veri.get("surum", VERI_SURUMU),
        "guncelleme": veri.get("guncelleme"),
        "kayitlar": [k for k in veri["kayitlar"] if isinstance(k, dict)],
    }


def veri_kaydet(veri, yol=None):
    """Referans verisini doğrulayıp atomik olarak yazar."""
    hedef = yol or _veri_yolu
    if not isinstance(veri, dict) or not isinstance(veri.get("kayitlar"), list):
        raise VeriHatasi("Yazılacak veri geçersiz yapıda.")
    for kayit in veri["kayitlar"]:
        hatalar = kayit_dogrula(kayit)
        if hatalar:
            raise VeriHatasi("; ".join(hatalar))
    paket = {
        "surum": VERI_SURUMU,
        "guncelleme": date.today().isoformat(),
        "kayitlar": [kayit_normalize(k) for k in veri["kayitlar"]],
    }
    klasor = os.path.dirname(os.path.abspath(hedef))
    os.makedirs(klasor, exist_ok=True)
    gecici = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=klasor, delete=False, suffix=".tmp"
        ) as dosya:
            json.dump(paket, dosya, ensure_ascii=False, indent=2)
            gecici = dosya.name
        os.replace(gecici, hedef)
    except OSError as hata:
        if gecici and os.path.exists(gecici):
            os.remove(gecici)
        raise VeriHatasi("Referans verisi yazılamadı: %s" % hata) from None
    return paket


def kayit_ekle(yil, puan_turu, noktalar, kaynak, not_metni="", yol=None):
    """Bir yıl + puan türü için referans noktalarını ekler (varsa değiştirir)."""
    kayit = {
        "yil": str(yil).strip(),
        "puan_turu": puan_turu,
        "kaynak": kaynak or {},
        "not": not_metni,
        "noktalar": noktalar or [],
    }
    hatalar = kayit_dogrula(kayit)
    if hatalar:
        raise VeriHatasi("; ".join(hatalar))
    veri = veri_yukle(yol)
    temiz = kayit_normalize(kayit)
    kalanlar = []
    for mevcut in veri["kayitlar"]:
        ayni = str(mevcut.get("yil")).strip() == temiz["yil"]
        try:
            ayni = ayni and puan_turu_kontrol(mevcut.get("puan_turu")) == temiz[
                "puan_turu"
            ]
        except VeriHatasi:
            ayni = False
        if not ayni:
            kalanlar.append(mevcut)
    kalanlar.append(temiz)
    return veri_kaydet({"kayitlar": kalanlar}, yol)


def kayit_sil(yil, puan_turu, yol=None):
    """Bir yıl + puan türü kaydını siler; silinen kayıt sayısını döndürür."""
    hedef_yil = str(yil).strip()
    hedef_tur = puan_turu_kontrol(puan_turu)
    veri = veri_yukle(yol)
    kalanlar = []
    silinen = 0
    for kayit in veri["kayitlar"]:
        ayni = str(kayit.get("yil")).strip() == hedef_yil
        try:
            ayni = ayni and puan_turu_kontrol(kayit.get("puan_turu")) == hedef_tur
        except VeriHatasi:
            ayni = False
        if ayni:
            silinen += 1
        else:
            kalanlar.append(kayit)
    if silinen:
        veri_kaydet({"kayitlar": kalanlar}, yol)
    return silinen


def kayit_getir(yil, puan_turu, veri=None):
    """Belirli yıl + puan türü kaydını (normalize) döndürür; yoksa None."""
    hedef_yil = str(yil).strip()
    try:
        hedef_tur = puan_turu_kontrol(puan_turu)
    except VeriHatasi:
        return None
    kaynak_veri = veri if veri is not None else veri_yukle()
    for kayit in kaynak_veri.get("kayitlar") or []:
        if str(kayit.get("yil")).strip() != hedef_yil:
            continue
        try:
            if puan_turu_kontrol(kayit.get("puan_turu")) != hedef_tur:
                continue
        except VeriHatasi:
            continue
        if not kayit_dogrula(kayit):
            return kayit_normalize(kayit)
        return None
    return None


def noktalari_getir(yil, puan_turu, veri=None):
    """Puan-sıra noktaları (puan azalan). Veri yoksa boş liste."""
    kayit = kayit_getir(yil, puan_turu, veri=veri)
    return list(kayit["noktalar"]) if kayit else []


def kapsanan_yillar(puan_turu=None, veri=None):
    """Geçerli referans verisi bulunan yıllar (eskiden yeniye)."""
    kaynak_veri = veri if veri is not None else veri_yukle()
    hedef_tur = None
    if puan_turu is not None:
        try:
            hedef_tur = puan_turu_kontrol(puan_turu)
        except VeriHatasi:
            return []
    yillar = set()
    for kayit in kaynak_veri.get("kayitlar") or []:
        if kayit_dogrula(kayit):
            continue
        try:
            tur = puan_turu_kontrol(kayit.get("puan_turu"))
        except VeriHatasi:
            continue
        if hedef_tur is not None and tur != hedef_tur:
            continue
        yillar.add(str(kayit.get("yil")).strip())
    return sorted(yillar)


def veri_ozeti(veri=None):
    """Arayüz için referans verisinin durumu (hangi yıl/puan türü var?)."""
    kaynak_veri = veri if veri is not None else veri_yukle()
    gecerli = []
    hatali = []
    for kayit in kaynak_veri.get("kayitlar") or []:
        hatalar = kayit_dogrula(kayit)
        if hatalar:
            hatali.append({"kayit": kayit, "hatalar": hatalar})
        else:
            gecerli.append(kayit_normalize(kayit))
    return {
        "dosya": _veri_yolu,
        "dosya_var": os.path.exists(_veri_yolu),
        "kayit_sayisi": len(gecerli),
        "hatali_kayit_sayisi": len(hatali),
        "hatali_kayitlar": hatali,
        "yillar": sorted({k["yil"] for k in gecerli}),
        "kapsanan": {
            tur: sorted({k["yil"] for k in gecerli if k["puan_turu"] == tur})
            for tur in PUAN_TURLERI
        },
        "eksik_puan_turleri": [
            tur
            for tur in PUAN_TURLERI
            if not any(k["puan_turu"] == tur for k in gecerli)
        ],
        "kaynaklar": [
            {
                "yil": k["yil"],
                "puan_turu": k["puan_turu"],
                "kurum": k["kaynak"]["kurum"],
                "belge": k["kaynak"]["belge"],
                "url": k["kaynak"]["url"],
                "erisim_tarihi": k["kaynak"]["erisim_tarihi"],
                "nokta_sayisi": len(k["noktalar"]),
            }
            for k in sorted(gecerli, key=lambda x: (x["puan_turu"], x["yil"]))
        ],
        "guncelleme": kaynak_veri.get("guncelleme"),
    }






