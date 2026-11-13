"""Soru hedefleri ve atomik görev dilimleri (v2.6).

Kurallar:
- NORMAL mikro konu görevi: 8 kolay + 8 orta + 8 zor = **24 soru**.
- PEKİŞTİRME kategorisi (Matematik, Geometri, Fizik): her seviye iki katı,
  16 + 16 + 16 = **48 soru**.
- Görevler tek parça gösterilmez; her dilim **8 soru**dur. Pekiştirmede
  aynı seviyeden iki dilim üst üste gelir (8 kolay, 8 kolay, ...).

Bu modül saf veri + saf fonksiyondur; DB/Streamlit/servis import etmez.
Mevcut program motorunun soru kotası (`planner.SORU_CARPANI`,
`topic_progress.konu_soru_kotasi`) DEĞİŞTİRİLMEZ; bu hedefler kamp
görevlerinin atomik dilimleri için tek kaynaktır.
"""
from data.curriculum_meta import ana_brans

SEVIYELER = ("kolay", "orta", "zor")
SEVIYE_BASINA_NORMAL = 8
SEVIYE_BASINA_PEKISTIRME = 16
DILIM_SORU = 8

# Kullanıcının onayladığı pekiştirme kategorisi: Matematik, Geometri, Fizik.
# `data.pedagogy.PEKISTIRME_DERSLERI` daha geniş pedagojik sınıflamadır; burada
# yalnızca soru hedefini ikiye katlayan branş ailesi tanımlıdır.
PEKISTIRME_BRANSLARI = frozenset({"Matematik", "Geometri", "Fizik"})


def pekistirme_mi(ders):
    """Ders, soru hedefi iki katına çıkan pekiştirme kategorisinde mi?"""
    return ana_brans(ders) in PEKISTIRME_BRANSLARI


def soru_hedefi(ders):
    """Ders için seviye başına ve toplam soru hedefi.

    Dönen: `{"kolay", "orta", "zor", "toplam", "pekistirme"}`.
    """
    pekistirme = pekistirme_mi(ders)
    basina = SEVIYE_BASINA_PEKISTIRME if pekistirme else SEVIYE_BASINA_NORMAL
    hedef = {seviye: basina for seviye in SEVIYELER}
    hedef["toplam"] = basina * len(SEVIYELER)
    hedef["pekistirme"] = pekistirme
    return hedef


def toplam_soru(ders):
    """Dersin bir mikro konu için TOPLAM soru hedefi (24 veya 48)."""
    return soru_hedefi(ders)["toplam"]


def dilimler(ders):
    """Görev dilimleri: her biri 8 soru, seviye etiketiyle.

    Normal: kolay, orta, zor (3 dilim).
    Pekiştirme: kolay x2, orta x2, zor x2 (6 dilim).
    Toplam soru sayısı `toplam_soru(ders)` ile birebir eşleşir.
    """
    hedef = soru_hedefi(ders)
    adet = hedef["kolay"] // DILIM_SORU
    sonuc = []
    sira = 1
    for seviye in SEVIYELER:
        for _ in range(max(1, adet)):
            sonuc.append({
                "dilim_no": sira,
                "toplam_dilim": 3 * max(1, adet),
                "seviye": seviye,
                "hedef_soru": DILIM_SORU,
            })
            sira += 1
    return sonuc


def seviye_etiketi(seviye):
    """'kolay' -> 'Kolay' (arayüz gösterimi)."""
    return str(seviye or "").strip().capitalize() or "-"
