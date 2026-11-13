"""Eski/alternatif konu adları -> kanonik müfredat adları eşlemesi.

Ön koşul haritasında ve eski kayıtlarda geçen bazı adlar güncel müfredattaki
karşılıklarıyla birebir eşleşmeyebilir. Bu modül yalnızca **okuma/doğrulama**
amaçlı bir çeviri katmanıdır:

- Veritabanındaki öğrenci kayıtlarını DEĞİŞTİRMEZ (migrasyon yazmaz).
- Aynı konuyu iki ayrı konu gibi göstermez.
- Bir eski ad birden çok kanonik konuya karşılık gelebilir.
- Konu tamamlanma ve alarm hesapları bu modüle bağlanmaz; yalnızca ön koşul
  doğrulaması ve testler kullanır.

Bu modül saf veri + saf yardımcıdır; servis/arayüz/DB import etmez.
"""


# Eski/alternatif ad -> kanonik müfredat ad(ları)
KONU_ALIASLARI = {
    "Doğruda Açılar": ["Temel Kavramlar ve Doğruda Açılar"],
    "Divan Edebiyaı": ["Divan Edebiyatı"],
    "Beylikten Devlete Osmanlı Siyaseti": ["Beylikten Devlete Osmanlı"],
    "Klasik Mantık": ["Klasik Mantık ve Mantık-Dil"],
    "Nükleik Asitler ve Protein Sentezi": ["Genden Proteine (Protein Sentezi)"],
    "Hücresel Solunum ve Fotosentez": [
        "Hücresel Solunum",
        "Fotosentez ve Kemosentez",
    ],
    "İnsan Fizyolojisi - Sinir ve Endokrin Sistem": [
        "Sinir Sistemi ve Duyu Organları",
        "Endokrin Sistem",
    ],
    "İnsan Fizyolojisi - Dolaşım ve Bağışıklık": ["Dolaşım ve Bağışıklık Sistemi"],
    "İnsan Fizyolojisi - Solunum ve Boşaltım": [
        "Solunum Sistemi",
        "Üriner Sistem",
    ],
    "Bitki Biyolojisi - Madde Taşınması ve Beslenme": [
        "Bitkisel Dokular ve Organlar",
    ],
    "XX. Yüzyıl Başlarında Osmanlı Devleti": ["XX. Yüzyıl Başlarında Osmanlı"],
}


def kanonik_konular(ad):
    """Bir konu adını kanonik liste(lere) çevirir; alias yoksa [ad] döner."""
    if not ad:
        return []
    return list(KONU_ALIASLARI.get(str(ad), [str(ad)]))


def alias_mi(ad):
    """Verilen ad bir eski/alternatif ad mı?"""
    return str(ad) in KONU_ALIASLARI
