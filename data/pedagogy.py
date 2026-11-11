"""Ders bazlı pedagoji sınıflandırması.

Pekiştirme dersleri soru ağırlıklı, ezber dersleri not ağırlıklı planlanır.
`get_konu_pedagoji_turu` konu adı verilmeden ders adına göre tür döndürür;
planlayıcı ve görev motorları bu türü kullanır.

Listeler `main.py`'den birebir taşındı.
"""


PEKISTIRME_DERSLERI = [
    "Matematik ve Veri",
    "TYT Matematik",
    "AYT Matematik",
    "TYT Geometri",
    "AYT Geometri",
    "TYT Fizik",
    "AYT Fizik",
    "Gramer ve Kelime",
    "Soru Tipleri",
]


EZBER_DERSLERI = [
    "TYT Biyoloji",
    "AYT Biyoloji",
    "TYT Türkçe",
    "TYT Tarih",
    "AYT Tarih-1",
    "AYT Tarih-2",
    "TYT Coğrafya",
    "AYT Coğrafya-1",
    "AYT Coğrafya-2",
    "TYT Felsefe & Din",
    "AYT Felsefe Grubu",
    "AYT Din Kültürü",
    "AYT Edebiyat",
    "TYT Kimya",
    "AYT Kimya",
    "YDT İngilizce",
]


def get_konu_pedagoji_turu(ders_adi, mikro_konu=""):
    if ders_adi in PEKISTIRME_DERSLERI:
        return "Pekiştirme"
    elif ders_adi in EZBER_DERSLERI:
        return "Ezber"
    else:
        return "Pekiştirme"
