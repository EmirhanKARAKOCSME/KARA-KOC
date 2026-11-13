"""Konu ön koşulları (tek ve nihai harita).

`main.py`'de iki ayrı sözlük vardı ve şu sırayla birleştiriliyordu:

    {**ON_KOSULLAR_EK, **ON_KOSULLAR}

Yani **aynı anahtar iki sözlükte de varsa `ON_KOSULLAR` kazanıyordu**. Bu
davranış `ON_KOSULLAR` içinde birebir korunmuştur: birleştirme yazılı olarak,
tek yerde yapılır ve `ON_KOSULLAR_EK` adı kaldırılmıştır.

- `_ON_KOSULLAR_TEMEL`: alarm motorunun da kullandığı ana ön koşul haritası.
- `_ON_KOSULLAR_PLANLAYICI_EK`: planlayıcı için sonradan eklenen ek koşullar.
- `ON_KOSULLAR`: uygulamanın kullandığı nihai harita (öncelik: TEMEL).
"""


_ON_KOSULLAR_TEMEL = {
    # --------------------------------------------------------------------------
    # 1. AYT MATEMATİK & GEOMETRİ (ZORUNLU KİLİT: TYT 'Fonksiyonlar')
    # --------------------------------------------------------------------------
    "Polinomlar ve Çarpanlara Ayırma": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Çarpanlara Ayırma"],
        "min_sinif": 3,
    },
    "İkinci Dereceden Denklemler": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Denklem Çözme"],
        "min_sinif": 3,
    },
    "Karmaşık Sayılar": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "İkinci Dereceden Denklemler"],
        "min_sinif": 3,
    },
    "Parabol": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "İkinci Dereceden Denklemler"],
        "min_sinif": 3,
    },
    "İkinci Dereceden Eşitsizlik Sistemleri": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "İkinci Dereceden Denklemler", "Parabol"],
        "min_sinif": 3,
    },
    "Yönlü Açılar ve Trigonometrik Oranlar": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Dik Üçgen ve Pisagor", "Üçgende Açılar"],
        "min_sinif": 3,
    },
    "Trigonometrik Denklemler": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Yönlü Açılar ve Trigonometrik Oranlar"],
        "min_sinif": 3,
    },
    "Üstel ve Logaritmik Fonksiyonlar": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Üslü Sayılar", "Polinomlar ve Çarpanlara Ayırma"],
        "min_sinif": 3,
    },
    "Aritmetik ve Geometrik Diziler": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Üstel ve Logaritmik Fonksiyonlar"],
        "min_sinif": 3,
    },
    "Limit ve Süreklilik": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Polinomlar ve Çarpanlara Ayırma"],
        "min_sinif": 4,
    },
    "Türev Alma Kuralları": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Limit ve Süreklilik"],
        "min_sinif": 4,
    },
    "Türevin Geometrik Yorumu ve Maks-Min": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Türev Alma Kuralları"],
        "min_sinif": 4,
    },
    "Belirsiz İntegral": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Türev Alma Kuralları"],
        "min_sinif": 4,
    },
    "Belirli İntegral ve Alan Hesabı": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Belirsiz İntegral"],
        "min_sinif": 4,
    },
    "Dönüşüm Geometrisi": {
        "ders": "AYT Geometri",
        "on_kosul": ["Noktanın Analitik İncelemesi", "Doğrunun Analitik İncelemesi"],
        "min_sinif": 3,
    },
    "Çemberin Analitik İncelemesi": {
        "ders": "AYT Geometri",
        "on_kosul": ["Doğrunun Analitik İncelemesi", "Çemberde Uzunluk"],
        "min_sinif": 4,
    },

    # --------------------------------------------------------------------------
    # 2. TYT MATEMATİK
    # --------------------------------------------------------------------------
    "Sayı Problemleri": {
        "ders": "TYT Matematik",
        "on_kosul": ["Denklem Çözme", "Basit Eşitsizlikler"],
        "min_sinif": 1,
    },
    "Yaş Problemleri": {
        "ders": "TYT Matematik",
        "on_kosul": ["Denklem Çözme"],
        "min_sinif": 1,
    },
    "Hareket Hız Problemleri": {
        "ders": "TYT Matematik",
        "on_kosul": ["Oran Orantı", "Denklem Çözme"],
        "min_sinif": 1,
    },
    "Karışım Problemleri": {
        "ders": "TYT Matematik",
        "on_kosul": ["Oran Orantı"],
        "min_sinif": 1,
    },
    "Fonksiyonlar": {
        "ders": "TYT Matematik",
        "on_kosul": ["Kümeler – Kartezyen Çarpım", "Denklem Çözme"],
        "min_sinif": 2,
    },

    # --------------------------------------------------------------------------
    # 3. TYT & AYT FİZİK
    # --------------------------------------------------------------------------
    "Newton'ın Hareket Yasaları": {
        "ders": "AYT Fizik",
        "on_kosul": ["Vektörler ve Bağıl Hareket"],
        "min_sinif": 3,
    },
    "Atışlar": {
        "ders": "AYT Fizik",
        "on_kosul": ["Vektörler ve Bağıl Hareket"],
        "min_sinif": 3,
    },
    "Tork ve Dönme Dengesi": {
        "ders": "AYT Fizik",
        "on_kosul": ["Newton'ın Hareket Yasaları"],
        "min_sinif": 3,
    },
    "İtme ve Çizgisel Momentum": {
        "ders": "AYT Fizik",
        "on_kosul": ["İş-Enerji Korunumu"],
        "min_sinif": 3,
    },
    "Elektriksel Potansiyel": {
        "ders": "AYT Fizik",
        "on_kosul": ["Elektriksel Kuvvet ve Elektrik Alan"],
        "min_sinif": 3,
    },
    "Düzgün Elektrik Alan ve Sığaçlar": {
        "ders": "AYT Fizik",
        "on_kosul": ["Elektriksel Potansiyel"],
        "min_sinif": 3,
    },
    "Manyetik Alan ve Manyetik Kuvvet": {
        "ders": "AYT Fizik",
        "on_kosul": ["Elektrik Akımı ve Devreler"],
        "min_sinif": 3,
    },
    "İndüksiyon ve Alternatif Akım": {
        "ders": "AYT Fizik",
        "on_kosul": ["Manyetik Alan ve Manyetik Kuvvet"],
        "min_sinif": 3,
    },

    # --------------------------------------------------------------------------
    # 4. TYT & AYT KİMYA
    # --------------------------------------------------------------------------
    "Mol Kavramı ve Kimyasal Hesaplamalar": {
        "ders": "TYT Kimya",
        "on_kosul": ["Kimyanın Temel Kanunları"],
        "min_sinif": 1,
    },
    "Kimyasal Denge": {
        "ders": "AYT Kimya",
        "on_kosul": ["Tepkime Hızları"],
        "min_sinif": 3,
    },
    "Asit-Baz Dengesi": {
        "ders": "AYT Kimya",
        "on_kosul": ["Kimyasal Denge"],
        "min_sinif": 3,
    },
    "Çözünürlük Dengesi (KÇÇ)": {
        "ders": "AYT Kimya",
        "on_kosul": ["Kimyasal Denge"],
        "min_sinif": 3,
    },
    "Organik Bileşikler": {
        "ders": "AYT Kimya",
        "on_kosul": ["Karbon Kimyasına Giriş"],
        "min_sinif": 4,
    },

    # --------------------------------------------------------------------------
    # 5. TYT & AYT BİYOLOJİ
    # --------------------------------------------------------------------------
    "Hücre Zarından Madde Geçişleri": {
        "ders": "TYT Biyoloji",
        "on_kosul": ["Canlıların Temel Bileşenleri", "Hücre Yapısı ve Organeller"],
        "min_sinif": 1,
    },
    "Mayoz ve Eşeyli Üreme": {
        "ders": "TYT Biyoloji",
        "on_kosul": ["Mitoz ve Eşeysiz Üreme"],
        "min_sinif": 2,
    },
    "Mendelyan Kalıtım": {
        "ders": "TYT Biyoloji",
        "on_kosul": ["Mayoz ve Eşeyli Üreme"],
        "min_sinif": 2,
    },
    # v2.5: "İnsan Fizyolojisi - ..." eski/alternatif adları gerçek müfredat
    # mikro konularına ayrıştırıldı (tek string yerine kanonik başlıklar).
    "Sinir Sistemi ve Duyu Organları": {
        "ders": "AYT Biyoloji",
        "on_kosul": ["Hücre Yapısı ve Organeller", "Hücre Zarından Madde Geçişleri"],
        "min_sinif": 3,
    },
    "Endokrin Sistem": {
        "ders": "AYT Biyoloji",
        "on_kosul": ["Hücre Yapısı ve Organeller", "Hücre Zarından Madde Geçişleri"],
        "min_sinif": 3,
    },
    "Dolaşım ve Bağışıklık Sistemi": {
        "ders": "AYT Biyoloji",
        "on_kosul": ["Sinir Sistemi ve Duyu Organları", "Endokrin Sistem"],
        "min_sinif": 3,
    },
    "Solunum Sistemi": {
        "ders": "AYT Biyoloji",
        "on_kosul": ["Dolaşım ve Bağışıklık Sistemi"],
        "min_sinif": 3,
    },
    "Üriner Sistem": {
        "ders": "AYT Biyoloji",
        "on_kosul": ["Dolaşım ve Bağışıklık Sistemi"],
        "min_sinif": 3,
    },
    "Genden Proteine (Protein Sentezi)": {
        "ders": "AYT Biyoloji",
        "on_kosul": ["Canlıların Temel Bileşenleri", "Hücre Yapısı ve Organeller"],
        "min_sinif": 4,
    },
    "Fotosentez ve Kemosentez": {
        "ders": "AYT Biyoloji",
        "on_kosul": ["Canlıların Temel Bileşenleri", "Genden Proteine (Protein Sentezi)"],
        "min_sinif": 4,
    },
    "Hücresel Solunum": {
        "ders": "AYT Biyoloji",
        "on_kosul": ["Canlıların Temel Bileşenleri", "Genden Proteine (Protein Sentezi)"],
        "min_sinif": 4,
    },
    "Bitkisel Dokular ve Organlar": {
        "ders": "AYT Biyoloji",
        "on_kosul": [
            "Hücre Zarından Madde Geçişleri",
            "Hücresel Solunum",
            "Fotosentez ve Kemosentez",
        ],
        "min_sinif": 4,
    },

    # --------------------------------------------------------------------------
    # 6. AYT EDEBİYAT & SOSYAL-1 / SOSYAL-2
    # --------------------------------------------------------------------------
    "Divan Edebiyatı": {
        "ders": "AYT Edebiyat",
        "on_kosul": ["Şiir Bilgisi ve Edebi Sanatlar", "İslamiyet Öncesi ve Geçiş Dönemi Türk Edebiyatı"],
        "min_sinif": 2,
    },
    "Tanzimat ve Servet-i Fünun Edebiyatı": {
        "ders": "AYT Edebiyat",
        "on_kosul": ["Şiir Bilgisi ve Edebi Sanatlar", "Divan Edebiyatı"],
        "min_sinif": 3,
    },
    "Cumhuriyet Dönemi Edebiyatı": {
        "ders": "AYT Edebiyat",
        "on_kosul": ["Tanzimat ve Servet-i Fünun Edebiyatı", "Milli Edebiyat Dönemi"],
        "min_sinif": 4,
    },
    "Türk-İslam Devletleri": {
        "ders": "AYT Tarih-1",
        "on_kosul": ["İlk ve Orta Çağlarda Türk Dünyası", "İslam Medeniyetinin Doğuşu"],
        "min_sinif": 1,
    },
    "Beylikten Devlete Osmanlı": {
        "ders": "AYT Tarih-1",
        "on_kosul": ["Türk-İslam Devletleri"],
        "min_sinif": 2,
    },
    "Milli Mücadele Dönemi": {
        "ders": "AYT Tarih-1",
        "on_kosul": ["XX. Yüzyıl Başlarında Osmanlı"],
        "min_sinif": 4,
    },
    "Atatürk İlkeleri ve İnkılapları": {
        "ders": "AYT Tarih-1",
        "on_kosul": ["Milli Mücadele Dönemi"],
        "min_sinif": 4,
    },
    "Soğuk Savaş ve XXI. Yüzyıl": {
        "ders": "AYT Tarih-2",
        "on_kosul": ["İki Savaş Arası Dönem"],
        "min_sinif": 4,
    },
    "Türkiye Ekonomisi ve Bölgeler": {
        "ders": "AYT Coğrafya-1",
        "on_kosul": ["İklim Bilgisi", "Türkiye’nin Yer Şekilleri"],
        "min_sinif": 3,
    },
    "Klasik Mantık ve Mantık-Dil": {
        "ders": "AYT Felsefe Grubu",
        "on_kosul": ["Felsefi Düşünce"],
        "min_sinif": 3,
    },
    "Sembolik Mantık": {
        "ders": "AYT Felsefe Grubu",
        "on_kosul": ["Klasik Mantık ve Mantık-Dil"],
        "min_sinif": 4,
    },

    # --------------------------------------------------------------------------
    # 7. YDT (İNGİLİZCE)
    # --------------------------------------------------------------------------
    "Clauses & Conjunctions": {
        "ders": "YDT İngilizce",
        "on_kosul": ["Tenses & Modals", "Vocabulary & Collocations"],
        "min_sinif": 2,
    },
    "Cloze Test & Cümle Tamamlama": {
        "ders": "YDT İngilizce",
        "on_kosul": ["Clauses & Conjunctions"],
        "min_sinif": 3,
    },
    "Paragraf Okuma ve Anlama": {
        "ders": "YDT İngilizce",
        "on_kosul": ["Cloze Test & Cümle Tamamlama"],
        "min_sinif": 3,
    },
    "İngilizce-Türkçe Çeviri": {
        "ders": "YDT İngilizce",
        "on_kosul": ["Paragraf Okuma ve Anlama"],
        "min_sinif": 4,
    },

    # --------------------------------------------------------------------------
    # 8. MAARİF MODELİ (9. SINIF MATEMATİK VE VERİ)
    # --------------------------------------------------------------------------
    "Gerçek Sayıların Üslü ve Köklü Gösterimleri": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Sayı Kümeleri ve İşlem Özellikleri"],
        "min_sinif": 1,
    },
    "Gerçek Sayı Aralıkları ile İşlemler": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Gerçek Sayıların Üslü ve Köklü Gösterimleri"],
        "min_sinif": 1,
    },
    "İki Kare Farkı ve Tamkare Özdeşlikleri": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Gerçek Sayı Aralıkları ile İşlemler"],
        "min_sinif": 1,
    },
    "Gerçek Sayılarda Tanımlı Doğrusal Fonksiyonlar ve Mutlak Değer": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["İki Kare Farkı ve Tamkare Özdeşlikleri"],
        "min_sinif": 1,
    },
    "Fonksiyonların Nitel Özellikleri": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Gerçek Sayılarda Tanımlı Doğrusal Fonksiyonlar ve Mutlak Değer"],
        "min_sinif": 1,
    },
    "Doğrusal Fonksiyonlarla İfade Edilen Denklem ve Eşitsizlikler": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Fonksiyonların Nitel Özellikleri"],
        "min_sinif": 1,
    },
    "Üçgende Açı İlişkileri": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Üçgende Açı ve Kenar Özellikleri"],
        "min_sinif": 1,
    },
    "Üçgende Kenar İlişkileri": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Üçgende Açı İlişkileri"],
        "min_sinif": 1,
    },
    "Üçgenlerde Eşlik ve Benzerlik Koşulları": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Üçgende Kenar İlişkileri", "Geometrik Şekillerin Dönüşümleri (Yansıma, Öteleme, Dönme)"],
        "min_sinif": 1,
    },
    "Verileri Toplama ve Analize Hazırlama": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Tek Nicel Değişken İçeren İstatistiksel Problem Oluşturma"],
        "min_sinif": 1,
    },
    "Bulgulara Ulaşma ve Yorumlama": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Verileri Toplama ve Analize Hazırlama"],
        "min_sinif": 1,
    },
    "İstatistiksel Görsel ve Çıkarımları Değerlendirme": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Bulgulara Ulaşma ve Yorumlama"],
        "min_sinif": 1,
    },
}


_ON_KOSULLAR_PLANLAYICI_EK = {
    "Üstel ve Logaritmik Fonksiyonlar": {"on_kosul": ["Polinomlar ve Çarpanlara Ayırma", "İkinci Dereceden Denklemler"], "min_sinif": 1},
    "Parabol": {"on_kosul": ["İkinci Dereceden Denklemler"], "min_sinif": 1},
    "Karmaşık Sayılar": {"on_kosul": ["İkinci Dereceden Denklemler"], "min_sinif": 1},
    "İkinci Dereceden Eşitsizlik Sistemleri": {"on_kosul": ["İkinci Dereceden Denklemler", "Parabol"], "min_sinif": 1},
    "Limit ve Süreklilik": {"on_kosul": ["Fonksiyonlar"], "min_sinif": 1},
    "Yönlü Açılar ve Trigonometrik Oranlar": {"on_kosul": ["Dik Üçgen ve Pisagor"], "min_sinif": 1},
    "Newton'ın Hareket Yasaları": {"on_kosul": ["Vektörler ve Bağıl Hareket"], "min_sinif": 1},
    "Atışlar": {"on_kosul": ["Vektörler ve Bağıl Hareket"], "min_sinif": 1},
    "Tork ve Dönme Dengesi": {"on_kosul": ["Newton'ın Hareket Yasaları"], "min_sinif": 1},
    "İtme ve Çizgisel Momentum": {"on_kosul": ["İş-Enerji Korunumu"], "min_sinif": 1},
    "Elektriksel Potansiyel": {"on_kosul": ["Elektriksel Kuvvet ve Elektrik Alan"], "min_sinif": 1},
    "Düzgün Elektrik Alan ve Sığaçlar": {"on_kosul": ["Elektriksel Potansiyel"], "min_sinif": 1},
    "İndüksiyon ve Alternatif Akım": {"on_kosul": ["Manyetik Alan ve Manyetik Kuvvet"], "min_sinif": 1},
    "Kimyasal Denge": {"on_kosul": ["Tepkime Hızları"], "min_sinif": 1},
    "Asit-Baz Dengesi": {"on_kosul": ["Kimyasal Denge"], "min_sinif": 1},
    "Çözünürlük Dengesi (KÇÇ)": {"on_kosul": ["Kimyasal Denge"], "min_sinif": 1},
    "Organik Bileşikler": {"on_kosul": ["Karbon Kimyasına Giriş"], "min_sinif": 1},
    "Mol Kavramı ve Kimyasal Hesaplamalar": {"on_kosul": ["Kimyanın Temel Kanunları"], "min_sinif": 1},
    "Hareket Hız Problemleri": {"on_kosul": ["Oran Orantı"], "min_sinif": 1},
    "Yaş Problemleri": {"on_kosul": ["Denklem Çözme"], "min_sinif": 1},
    "Karışım Problemleri": {"on_kosul": ["Oran Orantı"], "min_sinif": 1},
}


# v2.6 — EKSİK ÖN KOŞUL TAMAMLAMASI (AYT Geometri).
# Çakışma analizi: bu anahtarlardan hiçbiri `_ON_KOSULLAR_TEMEL` veya
# `_ON_KOSULLAR_PLANLAYICI_EK` içinde YOKTUR; mevcut kurallar ezilmez.
# Ön koşulların tamamı TYT Geometri müfredatında birebir bulunur.
_ON_KOSULLAR_V26_EK = {
    "Çemberde Açı": {
        "ders": "AYT Geometri",
        "on_kosul": ["Üçgende Açılar", "Dörtgenler ve Özel Dörtgenler"],
        "min_sinif": 3,
    },
    "Çemberde Uzunluk": {
        "ders": "AYT Geometri",
        "on_kosul": ["Çemberde Açı", "Dik Üçgen ve Pisagor"],
        "min_sinif": 3,
    },
    "Dairede Çevre ve Alan": {
        "ders": "AYT Geometri",
        "on_kosul": ["Çemberde Uzunluk"],
        "min_sinif": 3,
    },
    "Noktanın Analitik İncelemesi": {
        "ders": "AYT Geometri",
        "on_kosul": ["Temel Kavramlar ve Doğruda Açılar", "Dik Üçgen ve Pisagor"],
        "min_sinif": 3,
    },
    "Doğrunun Analitik İncelemesi": {
        "ders": "AYT Geometri",
        "on_kosul": ["Noktanın Analitik İncelemesi"],
        "min_sinif": 3,
    },
    "Prizmalar ve Küp": {
        "ders": "AYT Geometri",
        "on_kosul": ["Çokgenler", "Dörtgenler ve Özel Dörtgenler"],
        "min_sinif": 3,
    },
    "Silindir ve Koni": {
        "ders": "AYT Geometri",
        "on_kosul": ["Prizmalar ve Küp", "Dairede Çevre ve Alan"],
        "min_sinif": 3,
    },
    "Piramit ve Küre": {
        "ders": "AYT Geometri",
        "on_kosul": ["Silindir ve Koni"],
        "min_sinif": 3,
    },
}


ON_KOSULLAR = {
    **_ON_KOSULLAR_PLANLAYICI_EK,
    **_ON_KOSULLAR_V26_EK,
    **_ON_KOSULLAR_TEMEL,
}
