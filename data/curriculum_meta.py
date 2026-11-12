"""v2.2 müfredat/kredi metadata katmanı.

Bu modül **saf veri ve saf yardımcı** barındırır; servis/arayüz/DB import etmez.

Sağladıkları:

- `normalize_konu_adi`: Türkçe karakter, tire ve bağlaç farklarını temizleyen
  tek eşleştirme fonksiyonu (ön koşul/çekirdek kilit testleri bunu kullanır).
- `ana_brans`: dersin "ana branş ailesi" (Matematik, Geometri, Fizik ...).
  Faz 2 "tek branş = tek konu" ve TYT➔AYT kilit senkronizasyonu bunu kullanır.
- `sira_no_haritasi`: bir müfredat sözlüğünden her ders için 1'den başlayan
  deterministik `sira_no` üretir (mutlak müfredat sırası).
- `kredi_puani`: YKS çıkmış soru ağırlığını temsil eden 1–10 arası tam sayı.
- `makro_unite`: mikro konunun bağlı olduğu makro ünite adı.
- `CEKIRDEK_TYT_ONKOSULLAR`: AYT branşlarının çekirdek TYT ön koşulları.
- `motor1_mi`: Mayıs–Haziran çift motor mimarisinde pekiştirme/işlem dersi mi?

Tüm fonksiyonlar deterministiktir ve yan etki üretmez.
"""
import re
import unicodedata

from data.curriculum import mufredat_klasik, mufredat_maarif_9
from data.weights_and_times import SORU_AGIRLIKLARI


# ---------------------------------------------------------------------------
# 1) İSİM NORMALİZASYONU
# ---------------------------------------------------------------------------
_TR_CEVIR = {
    "ı": "i", "ş": "s", "ğ": "g", "ç": "c", "ö": "o", "ü": "u",
    "â": "a", "î": "i", "û": "u",
}


def normalize_konu_adi(ad):
    """Konu adını eşleştirme için sadeleştirir (Türkçe karakter/tire/bağlaç)."""
    if ad is None:
        return ""
    metin = str(ad).strip().lower()
    # Birleşik nokta (İ.lower() -> i + combining dot) ve aksanları temizle.
    metin = unicodedata.normalize("NFKD", metin)
    metin = "".join(c for c in metin if not unicodedata.combining(c))
    metin = "".join(_TR_CEVIR.get(c, c) for c in metin)
    # Tire ve bağlaçları boşluğa çevir (Dörtgenler ve Özel Dörtgenler vb.).
    metin = re.sub(r"[&\-/–—]", " ", metin)
    metin = re.sub(r"\b(ve|ile|veya)\b", " ", metin)
    metin = re.sub(r"[^\w\s]", " ", metin)
    metin = re.sub(r"\s+", " ", metin).strip()
    return metin


def konu_esit_mi(a, b):
    """İki konu adı normalize edildikten sonra eşit mi?"""
    return normalize_konu_adi(a) == normalize_konu_adi(b)


def konu_iceriyor_mu(metin, parca):
    """`metin` normalize edilmiş parçayı içeriyor mu? (fuzzy kilit eşleşmesi)."""
    n_metin = normalize_konu_adi(metin)
    n_parca = normalize_konu_adi(parca)
    return bool(n_parca) and n_parca in n_metin


# ---------------------------------------------------------------------------
# 2) ANA BRANŞ AİLESİ
# ---------------------------------------------------------------------------
# Sıra önemlidir: felsefe, din'den önce eşleşmeli (TYT Felsefe & Din -> Felsefe).
_BRANS_KURALLARI = (
    ("matematik", "Matematik"),
    ("geometri", "Geometri"),
    ("fizik", "Fizik"),
    ("kimya", "Kimya"),
    ("biyoloji", "Biyoloji"),
    ("edebiyat", "Edebiyat"),
    ("cografya", "Coğrafya"),
    ("felsefe", "Felsefe"),
    ("din", "Din Kültürü"),
    ("turkce", "Türkçe"),
    ("gramer", "İngilizce"),
    ("soru tipleri", "İngilizce"),
    ("ydt", "İngilizce"),
    ("ingilizce", "İngilizce"),
)


def ana_brans(ders):
    """Dersin ana branş ailesi (TYT/AYT aynı aileye düşer)."""
    norm = normalize_konu_adi(ders)
    for anahtar, aile in _BRANS_KURALLARI:
        if normalize_konu_adi(anahtar) in norm:
            return aile
    temiz = str(ders or "").strip()
    return temiz or "Diğer"


# Mayıs–Haziran çift motor: pekiştirme/işlem dersleri Motor 1'de kalır.
MOTOR1_BRANSLAR = frozenset({"Matematik", "Geometri", "Fizik", "Kimya"})


def motor1_mi(ders):
    """Ders Mayıs–Haziran döneminde Motor 1 (sıra korunur) ile mi çalışır?"""
    if str(ders or "").strip() == "TYT Türkçe":
        return True
    return ana_brans(ders) in MOTOR1_BRANSLAR


# ---------------------------------------------------------------------------
# 3) KREDİ PUANI (1–10)
# ---------------------------------------------------------------------------
# YKS çıkmış soru ağırlığını temsil eder. Değerler anahtar (makro ünite) adına
# normalized olarak eşlenir. Nadir çıkan yan konular 2–4, lokomotif makro
# üniteler 9–10 aralığındadır.
_MAKRO_KREDI = {
    # --- AYT Biyoloji (yüksek getiri) ---
    "sistemler fizyolojisi": 10,
    "genetik ve enerji": 9,
    "bitki biyolojisi ve ekoloji": 9,
    # --- AYT Edebiyat ---
    "donem edebiyatlari": 10,
    "metinler ve siir": 9,
    "siir ve metinler": 9,
    # --- Tarih (İnkılap lokomotif) ---
    "inkilap tarihi": 9,
    "tarih ve osmanli": 8,
    "ilk cag ve cagdas tarih": 7,
    # --- AYT Matematik / Geometri ---
    "ileri cebir ve fonksiyonlar": 8,
    "ileri cebir": 8,
    "trigonometri logaritma ve diziler": 8,
    "trigonometri": 8,
    "analiz limit turev integral": 9,
    "analiz": 9,
    "permutasyon kombinasyon olasilik binom": 8,
    "polinomlar": 6,
    "cember ve daire": 7,
    "analitik geometri": 7,
    "kati cisimler": 7,
    "cember ve analitik": 7,
    "donusum geometrisi": 3,
    "karmasik sayilar": 3,
    "parabol": 4,
    # --- AYT Fizik / Kimya ---
    "mekanik": 8,
    "elektromanyetizma": 8,
    "modern fizik": 7,
    "modern atom ve gazlar": 7,
    "termodinamik ve denge": 8,
    "elektrokimya ve organik": 7,
    "organik kimya": 7,
    # --- AYT Coğrafya / Felsefe / Din ---
    "ekosistem ve turkiye": 7,
    "mekansal sentez": 6,
    "felsefe ve mantik": 6,
    "psikoloji ve sosyoloji": 6,
    "inanc ve ibadet": 5,
    # --- TYT Matematik / Geometri ---
    "temel sayilar ve cebir": 8,
    "denklem ve esitsizlikler": 8,
    "problemler": 9,
    "kumeler mantik ve olasilik": 7,
    "ucgenler ve acilar": 7,
    "cokgenler ve dortgenler": 6,
    # --- TYT Türkçe ---
    "sozcukte anlam": 6,
    "cumlede anlam": 7,
    "paragraf": 9,
    "dil bilgisi ve yapi": 7,
    "sozcuk turleri": 6,
    "fiiller ve cumle": 7,
    # --- TYT Fen ---
    "fizik bilimi ve madde": 6,
    "kuvvet basinc ve isi": 8,
    "elektrik optik ve dalgalar": 8,
    "kimya bilimi ve atom": 7,
    "hesaplamalar ve karisimlar": 8,
    "hucre ve canlilik": 8,
    "ureme ve ekoloji": 7,
    "tarih bilimi ve ilk uygarliklar": 6,
    "islam ve osmanli tarihi": 8,
    "dogal sistemler": 6,
    "beseri sistemler ve afetler": 6,
    "felsefe": 5,
    "din kulturu": 5,
    # --- YDT ---
    "gramer ve kelime": 6,
    "soru tipleri": 8,
}


def _sayisal_kredi_deneme(ad, varsayilan=5):
    """Bilinmeyen makro için SORU_AGIRLIKLARI'ndan kaba 1–10 kredi türetir."""
    for anahtar, deger in SORU_AGIRLIKLARI.items():
        if normalize_konu_adi(anahtar) == normalize_konu_adi(ad):
            try:
                return max(1, min(10, int(round(float(deger) / 8.0))))
            except (TypeError, ValueError):
                return varsayilan
    return varsayilan


def kredi_puani(ad, varsayilan=5):
    """Bir makro/konu adının 1–10 arası YKS kredi puanı."""
    norm = normalize_konu_adi(ad)
    if norm in _MAKRO_KREDI:
        return _MAKRO_KREDI[norm]
    # Parçalı eşleşme (ör. "Analiz (Limit, Türev, İntegral)").
    for anahtar, deger in _MAKRO_KREDI.items():
        if anahtar in norm:
            return deger
    return _sayisal_kredi_deneme(ad, varsayilan)


def makro_kredi_puani(makro, varsayilan=5):
    """Makro ünite kredi puanı (Motor 2 sıralamasının birincil anahtarı)."""
    return kredi_puani(makro, varsayilan)


# ---------------------------------------------------------------------------
# 4) MÜFREDAT DÜZLEŞTİRME + SIRA_NO / MAKRO HARİTASI
# ---------------------------------------------------------------------------
def mufredati_duzlestir(mufredat):
    """{ders: {makro: [mikro]}} sözlüğünü (ders, makro, mikro) üçlüsüne açar."""
    for ders, makro_dict in (mufredat or {}).items():
        if not isinstance(makro_dict, dict):
            continue
        for makro, mikrolar in makro_dict.items():
            if not isinstance(mikrolar, list):
                continue
            for mikro in mikrolar:
                if mikro:
                    yield ders, makro, mikro


def sira_no_haritasi(mufredat):
    """Her ders için 1'den başlayan deterministik `sira_no` üretir.

    Dönen: `{(ders, mikro): sira_no}`. Aynı mikro tekrar ederse İLK sırası
    korunur (idempotent).
    """
    sira = {}
    sayac = {}
    for ders, _makro, mikro in mufredati_duzlestir(mufredat):
        anahtar = (ders, mikro)
        if anahtar in sira:
            continue
        sayac[ders] = sayac.get(ders, 0) + 1
        sira[anahtar] = sayac[ders]
    return sira


def makro_haritasi(mufredat):
    """`{(ders, mikro): makro_unite}` haritası (ilk gördüğü makro)."""
    harita = {}
    for ders, makro, mikro in mufredati_duzlestir(mufredat):
        harita.setdefault((ders, mikro), makro)
    return harita


def sinif_seviyesi_haritasi(mufredat):
    """`{(ders, mikro): sinif_seviyesi}` — Maarif dersleri 9, kalanı 12."""
    maarif = set(mufredati_duzlestir(mufredat_maarif_9))
    harita = {}
    for ders, makro, mikro in mufredati_duzlestir(mufredat):
        harita[(ders, mikro)] = 9 if (ders, makro, mikro) in maarif else 12
    return harita


# ---------------------------------------------------------------------------
# 5) SINIF / ALAN HAVUZ KİLİDİ
# ---------------------------------------------------------------------------
_ALAN_AYT_DERSLERI = {
    "sayisal": {"AYT Matematik", "AYT Geometri", "AYT Fizik", "AYT Kimya", "AYT Biyoloji"},
    "esit agirlik": {"AYT Matematik", "AYT Geometri", "AYT Edebiyat", "AYT Tarih-1", "AYT Coğrafya-1"},
    "sozel": {"AYT Edebiyat", "AYT Tarih-2", "AYT Coğrafya-2", "AYT Felsefe Grubu", "AYT Din Kültürü"},
    "dil": {"YDT İngilizce"},
}
_ALAN_ESLEME = {
    "say": "sayisal", "sayisal": "sayisal",
    "ea": "esit agirlik", "esit agirlik": "esit agirlik",
    "soz": "sozel", "sozel": "sozel",
    "dil": "dil",
}


def alan_normalize(alan):
    """Alan adını kanonik anahtara çevirir ('SAY'/'Eşit Ağırlık'/'Sözel'/'Dil')."""
    return _ALAN_ESLEME.get(normalize_konu_adi(alan), None)


def ders_alana_uygun_mu(ders, alan):
    """AYT dersi öğrencinin alanına uygun mu? (TYT dersleri her zaman uygun.)"""
    if not str(ders or "").startswith("AYT"):
        return True
    anahtar = alan_normalize(alan)
    if anahtar is None:
        return True  # alan bilinmiyorsa kısıtlama uygulanmaz
    return str(ders).strip() in _ALAN_AYT_DERSLERI.get(anahtar, set())


def sinif_seviyesi_sayisi(sinif_seviyesi):
    """'9. Sınıf' → 9, 'Mezun' → 12 (en üst). Bilinmiyorsa 12."""
    metin = str(sinif_seviyesi or "").strip()
    eslesme = re.match(r"\s*(\d+)", metin)
    if eslesme:
        return int(eslesme.group(1))
    if normalize_konu_adi(metin) == "mezun":
        return 12
    return 12


def havuz_suz(mufredat, sinif_seviyesi=None, alan=None):
    """Sınıf seviyesi + alanına göre müfredat havuzunu süzer.

    - 9. Sınıf: yalnızca Maarif (9. sınıf) dersleri; AYT kilitli.
    - 10. Sınıf: yalnızca TYT dersleri; AYT kilitli.
    - 11/12/Mezun: TYT + öğrencinin alanına ait AYT dersleri.
    """
    sinif = sinif_seviyesi_sayisi(sinif_seviyesi)
    sonuc = {}
    for ders, makro_dict in (mufredat or {}).items():
        if not isinstance(makro_dict, dict):
            continue
        is_ayt = str(ders).startswith("AYT")
        if sinif <= 9:
            if ders not in mufredat_maarif_9:
                continue
        elif sinif == 10:
            if is_ayt:
                continue
        elif is_ayt and not ders_alana_uygun_mu(ders, alan):
            continue
        sonuc[ders] = makro_dict
    return sonuc


# ---------------------------------------------------------------------------
# 6) ÇEKİRDEK TYT ➔ AYT KİLİDİ
# ---------------------------------------------------------------------------
CEKIRDEK_TYT_ONKOSULLAR = {
    "AYT Matematik": [
        "Temel Kavramlar", "Sayı Basamakları", "Bölme ve Bölünebilme",
        "Rasyonel Sayılar", "Basit Eşitsizlikler", "Mutlak Değer",
        "Üslü Sayılar", "Köklü Sayılar", "Çarpanlara Ayırma",
        "Denklem Çözme", "Fonksiyonlar",
    ],
    "AYT Geometri": [
        "Doğruda Açılar", "Üçgende Açılar", "Dik Üçgen ve Pisagor",
        "Üçgende Eşlik ve Benzerlik", "Üçgende Alan", "Çokgenler",
        "Dörtgenler ve Özel Dörtgenler",
    ],
    "AYT Fizik": [
        "Fizik Bilimine Giriş", "Madde ve Özellikleri",
        "Hareket ve Kuvvet", "Newton'un Hareket Yasaları",
    ],
    "AYT Kimya": [
        "Atom Yapısı ve Periyodik Sistem", "Kimyasal Türler Arası Etkileşimler",
        "Mol Kavramı ve Kimyasal Hesaplamalar",
    ],
    "AYT Biyoloji": [
        "Canlıların Ortak Özellikleri", "Canlıların Temel Bileşenleri",
        "Hücre Yapısı ve Organeller",
    ],
}

CEKIRDEK_ESIK_ORANI = 0.80


def _bilinen_kumesi(bilinen):
    """Ham konu adı kümesini normalize edilmiş kümeye çevirir."""
    return {normalize_konu_adi(k) for k in (bilinen or ()) if k}


def cekirdek_tamam_orani(ders, bilinen, biten_mikro=None):
    """AYT dersinin çekirdek TYT ön koşullarının tamamlanma oranı (0–1)."""
    liste = CEKIRDEK_TYT_ONKOSULLAR.get(ders)
    if not liste:
        return 1.0
    bilinen_norm = _bilinen_kumesi(bilinen) | _bilinen_kumesi(biten_mikro)
    tamam = 0
    for konu in liste:
        n = normalize_konu_adi(konu)
        if n in bilinen_norm or any(n in b for b in bilinen_norm):
            tamam += 1
    return tamam / float(len(liste))


def cekirdek_acik_mi(ders, bilinen, biten_mikro=None):
    """AYT dersinin çekirdek TYT kilidi açık mı? (>= %80 tamamlanmış)"""
    return cekirdek_tamam_orani(ders, bilinen, biten_mikro) >= CEKIRDEK_ESIK_ORANI
