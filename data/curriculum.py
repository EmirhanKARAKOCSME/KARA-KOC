"""Müfredat hiyerarşileri (Maarif 9-10 ve klasik YKS).

Veri `main.py`'den **birebir** taşındı; ders, ünite ve konu adları, sıraları ve
iç içe sözlük yapısı korunmuştur. Burada yalnızca veri vardır; hesaplama
yapılmaz.

- `mufredat_maarif_9`: Türkiye Yüzyılı Maarif Modeli (9/10. sınıf) dersleri.
- `mufredat_klasik`: TYT / AYT (Sayısal, Eşit Ağırlık, Sözel, Dil) dersleri.
"""


mufredat_maarif_9 = {
    "Matematik ve Veri": {
        "1. Ünite: Sayılar": [
            "Gerçek Sayıların Üslü ve Köklü Gösterimleri",
            "Gerçek Sayı Aralıkları ile İşlemler",
            "Sayı Kümeleri ve İşlem Özellikleri",
            "İki Kare Farkı ve Tamkare Özdeşlikleri",
        ],
        "2. Ünite: Nicelikler ve Değişimler": [
            "Gerçek Sayılarda Tanımlı Doğrusal Fonksiyonlar ve Mutlak Değer",
            "Fonksiyonların Nitel Özellikleri",
            "Doğrusal Fonksiyonlarla İfade Edilen Denklem ve Eşitsizlikler",
        ],
        "3. Ünite: Algoritma ve Bilişim": [
            "Algoritma Temelli Problemler",
            "Mantık Bağlaçları ve Niceleyiciler",
        ],
        "4. Ünite: Geometrik Şekiller": [
            "Üçgende Açı ve Kenar Özellikleri",
            "Üçgende Açı İlişkileri",
            "Üçgende Kenar İlişkileri",
        ],
        "5. Ünite: Eşlik ve Benzerlik": [
            "Geometrik Şekillerin Dönüşümleri (Yansıma, Öteleme, Dönme)",
            "Üçgenlerde Eşlik ve Benzerlik Koşulları",
        ],
        "6. Ünite: İstatistiksel Araştırma": [
            "Tek Nicel Değişken İçeren İstatistiksel Problem Oluşturma"
        ],
        "7. Ünite: Veriden Olasılığa": [
            "Verileri Toplama ve Analize Hazırlama",
            "Bulgulara Ulaşma ve Yorumlama",
            "İstatistiksel Görsel ve Çıkarımları Değerlendirme",
        ],
    },
    "TYT Kimya": {
        "1. Ünite: ETKİLEŞİM": [
            "Günlük Hayatta Kimya ve Güvenlik",
            "Kimyanın Alt Disiplinleri ve Kariyer",
            "Atom Teorileri ve Elektron Dizilimi",
            "Periyodik Tablo ve Periyodik Özellikler",
        ],
        "2. Ünite: ÇEŞİTLİLİK": [
            "Kimyasal Bağlar (Metalik, İyonik, Kovalent)",
            "Lewis Nokta Yapısı ve Polarlık",
            "Moleküller Arası Etkileşimler",
            "Katılar, Sıvılar ve Özellikleri",
        ],
        "3. Ünite: SÜRDÜRÜLEBİLİRLİK": [
            "Nanoparçacıklar ve Ekolojik Sürdürülebilirlik",
            "Yeşil Kimyanın Atık Önleme İlkesi",
        ],
    },
    "TYT Fizik": {
        "1. Ünite: FİZİK BİLİMİ VE KARİYER": [
            "Fizik Bilimi ve Alt Dalları",
            "Fizik Bilimine Yön Verenler ve Kariyer Keşfi",
        ],
        "2. Ünite: KUVVET VE HAREKET": [
            "Temel ve Türetilmiş Nicelikler",
            "Skaler ve Vektörel Nicelikler",
            "Doğadaki Temel Kuvvetler ve Hareket Türleri",
        ],
        "3. Ünite: AKIŞKANLAR": [
            "Basınç ve Sıvılarda Basınç",
            "Açık Hava Basıncı ve Kaldırma Kuvveti",
            "Bernoulli İlkesi",
        ],
        "4. Ünite: ENERJİ": [
            "Enerji, Isı, Öz Isı ve Sıcaklık İlişkisi",
            "Hâl Değişimi ve Isıl Denge",
            "Isı Aktarım Yolları ve İletim Hızı",
        ],
    },
    "TYT Biyoloji": {
        "1. Ünite: YAŞAM": [
            "Biyolojinin Önemi ve Bilim Etiği",
            "Canlıların Ortak Özellikleri",
            "Sınıflandırma ve Biyoçeşitlilik (3 Domain)",
        ],
        "2. Ünite: ORGANİZASYON": [
            "İnorganik Moleküller (Su ve Mineraller)",
            "Organik Moleküller (Karbonhidrat, Yağ, Protein, Nükleik Asit, Vitamin)",
            "Hücre Yapısı, Organeller ve Çekirdek",
            "Hücre Zarından Madde Geçişleri",
            "Hücreden Organ ve Sistem Organizasyonuna",
        ],
    },
    "TYT Türkçe": {
        "1. Ünite: GİRİŞ": [
            "Edebiyatın Sanat ve Bilimle İlişkisi",
            "İletişim Öğeleri ve Göstergeler",
            "Dilin İşlevleri ve Kullanım Türleri",
        ],
        "2. Ünite: HİKAYE (ÖYKÜ)": [
            "Hikaye Türleri ve Gelişimi",
            "Yazım ve Noktalama",
            "İsimler",
        ],
        "3. Ünite: ŞİİR": ["Şiir Bilgisi ve Türleri", "Sıfatlar"],
        "4. Ünite: MASAL / FABL": [
            "Masal ve Fabl Özellikleri",
            "Edat, Bağlaç, Ünlem",
        ],
        "5. Ünite: ROMAN": ["Roman Türleri ve Yapı Unsurları", "Zamirler"],
        "6. Ünite: TİYATRO": [
            "Tiyatro Terimleri ve Geleneksel Türk Tiyatrosu",
            "Zarflar",
        ],
        "7. Ünite: BİYOGRAFİ / OTOBİYOGRAFİ": [
            "Biyografi ve Otobiyografi",
            "CV, Dilekçe ve Tutanak",
            "Fiiller",
        ],
        "8. Ünite: MEKTUP / E-POSTA": ["Mektup Türleri ve E-Posta"],
        "9. Ünite: GÜNLÜK / BLOG": ["Günlük ve Blog"],
    },
    "TYT Tarih": {
        "1. Ünite: GEÇMİŞİN İNŞA SÜRECİNDE TARİH": [
            "Tarih Öğrenmenin Faydaları ve Doğası",
            "Tarihsel Bilgi Üretimi ve Dijitalleşme",
        ],
        "2. Ünite: ESKİ ÇAĞ MEDENİYETLERİ": [
            "Tarım Devriminin Yerleşmeye Etkisi",
            "Eski Çağda Yönetim, Hukuk ve İnançlar",
            "Türklerde Konargöçer Yaşam",
        ],
        "3. Ünite: ORTA ÇAĞ MEDENİYETLERİ": [
            "Orta Çağ Göçleri ve Devlet Yapıları",
            "Orta Çağ Ticaret Yolları ve Bilim Havzaları",
        ],
    },
    "TYT Coğrafya": {
        "1. Ünite: COĞRAFYANIN DOĞASI": [
            "Coğrafya Biliminin Konusu ve Gelişimi"
        ],
        "2. Ünite: MEKANSAL BİLGİ TEKNOLOJİLERİ": [
            "Haritalar ve Türkiye'nin Konumu",
            "Mekânsal Bilgi Teknolojileri Bileşenleri",
        ],
        "3. Ünite: DOĞAL SİSTEMLER VE SÜREÇLER": [
            "Hava Olayları ve İklim Sistemleri",
            "İklim Değişiklikleri",
        ],
        "4. Ünite: BEŞERİ SİSTEMLER VE SÜREÇLER": [
            "Nüfusun Tarihsel Değişimi ve Dağılışı",
            "Demografik Dönüşüm ve Piramitler",
        ],
        "5. Ünite: EKONOMİK FAALİYETLER": [
            "Ekonomik Faaliyetleri Etkileyen Coğrafi Faktörler"
        ],
        "6. Ünite: AFETLER VE SÜRDÜRÜLEBİLİR ÇEVRE": [
            "Afet Türleri ve Bütüncül Afet Yönetimi"
        ],
        "7. Ünite: BÖLGELER VE ÜLKELER": ["Bölge ve Bölge Sınırı Kavramı"],
    },
    "TYT Felsefe & Din": {
        "1. Ünite: ALLAH-İNSAN İLİŞKİSİ": ["İnsanın Yaratılışı, İbadet ve Dua"],
        "2. Ünite: İSLAM'DA İNANÇ ESASLARI": [
            "İman Esasları ve Toplumsal Boyutu"
        ],
        "3. Ünite: İSLAM'DA İBADETLER": ["Temel İbadetler ve İnsan"],
        "4. Ünite: İSLAM'DA AHLAK İLKELERİ": [
            "Ahlakın Temel Unsurları ve Tutumlar"
        ],
        "5. Ünite: HZ. MUHAMMED (S.A.V)": [
            "Hz. Muhammed'in Örnekliği ve Peygamberliği"
        ],
    },
}


mufredat_klasik = {
    "TYT": {
        "TYT Türkçe": {
            "Sözcükte Anlam": [
                "Sözcükte Anlam",
                "Söz Yorumu",
                "Deyim ve Atasözü",
            ],
            "Cümlede Anlam": [
                "Cümlede Anlam İlişkileri",
                "Cümle Yorumu ve Kavramlar",
            ],
            "Paragraf": [
                "Paragrafta Anlatım Teknikleri",
                "Paragrafta Düşünceyi Geliştirme Yolları",
                "Paragrafta Yapı",
                "Paragrafta Konu-Ana Düşünce",
                "Paragrafta Yardımcı Düşünce",
            ],
            "Dil Bilgisi ve Yapı": [
                "Ses Bilgisi",
                "Yazım Kuralları",
                "Noktalama İşaretleri",
                "Sözcükte Yapı ve Ekler",
            ],
            "Sözcük Türleri": [
                "İsimler",
                "Zamirler",
                "Sıfatlar",
                "Zarflar",
                "Edat – Bağlaç – Ünlem",
            ],
            "Fiiller ve Cümle": [
                "Fiilde Anlam",
                "Ek Fiil",
                "Fiilimsi",
                "Fiilde Çatı",
                "Cümlenin Ögeleri",
                "Anlatım Bozukluğu",
            ],
        },
        "TYT Matematik": {
            "Temel Sayılar ve Cebir": [
                "Temel Kavramlar",
                "Sayı Basamakları",
                "Bölme ve Bölünebilme",
                "EBOB – EKOK",
                "Rasyonel Sayılar",
            ],
            "Denklem ve Eşitsizlikler": [
                "Basit Eşitsizlikler",
                "Mutlak Değer",
                "Üslü Sayılar",
                "Köklü Sayılar",
                "Çarpanlara Ayırma",
                "Oran Orantı",
                "Denklem Çözme",
            ],
            "Problemler": [
                "Sayı Problemleri",
                "Kesir Problemleri",
                "Yaş Problemleri",
                "Hareket Hız Problemleri",
                "İşçi Emek Problemleri",
                "Yüzde-Kâr-Zarar Problemleri",
                "Karışım Problemleri",
                "Grafik Problemleri",
            ],
            "Kümeler, Mantık ve Olasılık": [
                "Kümeler – Kartezyen Çarpım",
                "Mantık",
                "Fonksiyonlar",
                "Permütasyon ve Kombinasyon",
                "Olasılık",
                "Veri – İstatistik",
            ],
        },
        "TYT Geometri": {
            "Üçgenler ve Açılar": [
                "Temel Kavramlar ve Doğruda Açılar",
                "Üçgende Açılar",
                "Dik Üçgen ve Pisagor",
                "İkizkenar ve Eşkenar Üçgen",
                "Açıortay ve Kenarortay",
                "Üçgende Eşlik ve Benzerlik",
                "Üçgende Alan",
            ],
            "Çokgenler ve Dörtgenler": [
                "Çokgenler",
                "Dörtgenler ve Özel Dörtgenler",
                "Deltoid",
                "Paralelkenar ve Eşkenar Dörtgen",
                "Dikdörtgen ve Kare",
                "Yamuk",
            ],
        },
        "TYT Fizik": {
            "Fizik Bilimi ve Madde": [
                "Fizik Bilimine Giriş",
                "Madde ve Özellikleri",
                "Dayanıklılık ve Akışkanlar",
            ],
            "Kuvvet, Basınç ve Isı": [
                "Hareket ve Kuvvet",
                "Newton'un Hareket Yasaları",
                "Basınç",
                "Sıvıların Kaldırma Kuvveti",
                "Isı, Sıcaklık ve Genleşme",
            ],
            "Elektrik, Optik ve Dalgalar": [
                "Elektrostatik",
                "Elektrik Akımı ve Devreler",
                "Mıknatıslar ve Manyetik Alan",
                "Aydınlanma ve Aynalar",
                "Kırılma ve Mercekler",
                "Dalga Harekatı",
            ],
        },
        "TYT Kimya": {
            "Kimya Bilimi ve Atom": [
                "Kimya Bilimi",
                "Atom Yapısı ve Periyodik Sistem",
                "Kimyasal Türler Arası Etkileşimler",
                "Maddenin Halleri",
            ],
            "Hesaplamalar ve Karışımlar": [
                "Kimyanın Temel Kanunları",
                "Mol Kavramı ve Kimyasal Hesaplamalar",
                "Karışımlar ve Ayırma Yöntemleri",
                "Asitler, Bazlar ve Tuzlar",
            ],
        },
        "TYT Biyoloji": {
            "Hücre ve Canlılık": [
                "Canlıların Ortak Özellikleri",
                "Canlıların Temel Bileşenleri",
                "Hücre Yapısı ve Organeller",
                "Hücre Zarından Madde Geçişleri",
                "Canlıların Sınıflandırılması",
            ],
            "Üreme ve Ekoloji": [
                "Mitoz ve Eşeysiz Üreme",
                "Mayoz ve Eşeyli Üreme",
                "Mendelyan Kalıtım",
                "Ekosistem Ekolojisi",
            ],
        },
        "TYT Tarih": {
            "Tarih Bilimi ve İlk Uygarlıklar": [
                "Tarih ve Zaman",
                "İnsanlığın İlk Dönemleri",
                "İlk ve Orta Çağlarda Türk Dünyası",
            ],
            "İslam ve Osmanlı Tarihi": [
                "İslam Medeniyetinin Doğuşu",
                "Türk-İslam Devletleri",
                "Beylikten Devlete Osmanlı Siyareti",
                "Milli Mücadele ve Atatürkçülük",
            ],
        },
        "TYT Coğrafya": {
            "Doğal Sistemler": [
                "Doğa ve İnsan",
                "Dünya’nın Şekli ve Hareketleri",
                "Coğrafi Konum",
                "Harita Bilgisi",
                "İklim Bilgisi",
            ],
            "Beşeri Sistemler ve Afetler": [
                "Nüfus ve Yerleşme",
                "Türkiye’nin Yer Şekilleri",
                "Ekonomik Faaliyetler",
                "Doğal Afetler ve Çevre",
            ],
        },
        "TYT Felsefe & Din": {
            "Felsefe": [
                "Felsefenin Konusu",
                "Bilgi Felsefesi",
                "Varlık Felsefesi",
                "Ahlak Felsefesi",
            ],
            "Din Kültürü": [
                "Bilgi ve İnanç",
                "İslam ve İbadet",
                "Ahlak ve Değerler",
            ],
        },
    },
    "AYT": {
        "Sayısal": {
            "AYT Matematik": {
                "İleri Cebir ve Fonksiyonlar": [
                    "Polinomlar ve Çarpanlara Ayırma",
                    "İkinci Dereceden Denklemler",
                    "Karmaşık Sayılar",
                    "Parabol",
                    "İkinci Dereceden Eşitsizlik Sistemleri",
                ],
                "Trigonometri, Logaritma ve Diziler": [
                    "Yönlü Açılar ve Trigonometrik Oranlar",
                    "Trigonometrik Denklemler",
                    "Üstel ve Logaritmik Fonksiyonlar",
                    "Aritmetik ve Geometrik Diziler",
                ],
                "Analiz (Limit, Türev, İntegral)": [
                    "Limit ve Süreklilik",
                    "Türev Alma Kuralları",
                    "Türevin Geometrik Yorumu ve Maks-Min",
                    "Belirsiz İntegral",
                    "Belirli İntegral ve Alan Hesabı",
                ],
            },
            "AYT Geometri": {
                "Çember ve Daire": [
                    "Çemberde Açı",
                    "Çemberde Uzunluk",
                    "Dairede Çevre ve Alan",
                ],
                "Analitik Geometri": [
                    "Noktanın Analitik İncelemesi",
                    "Doğrunun Analitik İncelemesi",
                    "Dönüşüm Geometrisi",
                    "Çemberin Analitik İncelemesi",
                ],
                "Katı Cisimler": [
                    "Prizmalar ve Küp",
                    "Silindir ve Koni",
                    "Piramit ve Küre",
                ],
            },
            "AYT Fizik": {
                "Mekanik": [
                    "Vektörler ve Bağıl Hareket",
                    "Newton'ın Hareket Yasaları",
                    "Atışlar",
                    "İş-Enerji Korunumu",
                    "İtme ve Çizgisel Momentum",
                    "Tork ve Dönme Dengesi",
                ],
                "Elektromanyetizma": [
                    "Elektriksel Kuvvet ve Elektrik Alan",
                    "Elektriksel Potansiyel",
                    "Düzgün Elektrik Alan ve Sığaçlar",
                    "Manyetik Alan ve Manyetik Kuvvet",
                    "İndüksiyon ve Alternatif Akım",
                ],
                "Modern Fizik": [
                    "Düzgün Çembersel Hareket",
                    "Açısal Momentum ve Kepler",
                    "Basit Harmonik Hareket",
                    "Dalga Mekaniği ve Doppler",
                    "Atom Fiziği ve Radyoaktivite",
                    "Fotoelektrik Olay",
                ],
            },
            "AYT Kimya": {
                "Modern Atom ve Gazlar": [
                    "Modern Atom Teorisi",
                    "Gazlar ve Ideal Gaz Yasası",
                    "Sıvı Çözeltiler ve Çözünürlük",
                ],
                "Termodinamik ve Denge": [
                    "Kimyasal Tepkimelerde Enerji",
                    "Tepkime Hızları",
                    "Kimyasal Denge",
                    "Asit-Baz Dengesi",
                    "Çözünürlük Dengesi (KÇÇ)",
                ],
                "Elektrokimya ve Organik": [
                    "Redoks ve Elektrokimya",
                    "Karbon Kimyasına Giriş",
                    "Organik Bileşikler",
                ],
            },
            "AYT Biyoloji": {
                "Sistemler Fizyolojisi": [
                    "Sinir Sistemi ve Duyu Organları",
                    "Endokrin Sistem",
                    "Destek ve Hareket Sistemi",
                    "Sindirim Sistemi",
                    "Dolaşım ve Bağışıklık Sistemi",
                    "Solunum Sistemi",
                    "Üriner Sistem",
                ],
                "Genetik ve Enerji": [
                    "Genden Proteine (Protein Sentezi)",
                    "Fotosentez ve Kemosentez",
                    "Hücresel Solunum",
                ],
                "Bitki Biyolojisi ve Ekoloji": [
                    "Bitkisel Dokular ve Organlar",
                    "Bitkilerde Büyüme ve Hareket",
                    "Komünite ve Popülasyon Ekolojisi",
                ],
            },
        },
        "Eşit Ağırlık": {
            "AYT Matematik": {
                "İleri Cebir": [
                    "Polinomlar ve Parabol",
                    "İkinci Dereceden Eşitsizlikler",
                    "Trigonometri",
                    "Logaritma ve Diziler",
                    "Limit, Türev ve İntegral",
                ],
            },
            "AYT Geometri": {
                "Çember ve Analitik": [
                    "Çemberde Açı ve Uzunluk",
                    "Analitik Geometri",
                    "Katı Cisimler",
                ],
            },
            "AYT Edebiyat": {
                "Metinler ve Şiir": [
                    "Şiir Bilgisi ve Edebi Sanatlar",
                    "İslamiyet Öncesi ve Geçiş Dönemi Türk Edebiyatı",
                    "Halk Edebiyatı",
                    "Divan Edebiyatı",
                ],
                "Dönem Edebiyatları": [
                    "Tanzimat ve Servet-i Fünun Edebiyatı",
                    "Milli Edebiyat Dönemi",
                    "Cumhuriyet Dönemi Edebiyatı",
                ],
            },
            "AYT Tarih-1": {
                "Tarih ve Osmanlı": [
                    "İlk Türk Devletleri ve İslam Medeniyeti",
                    "Beylikten Devlete Osmanlı",
                    "Dünya Gücü Osmanlı",
                ],
                "İnkılap Tarihi": [
                    "XX. Yüzyıl Başlarında Osmanlı",
                    "Milli Mücadele Dönemi",
                    "Atatürk İlkeleri ve İnkılapları",
                ],
            },
            "AYT Coğrafya-1": {
                "Ekosistem ve Türkiye": [
                    "Ekosistem ve Biyoçeşitlilik",
                    "Türkiye Ekonomisi ve Bölgeler",
                    "Küresel Ticaret ve Çevre",
                ],
            },
        },
        "Sözel": {
            "AYT Edebiyat": {
                "Şiir ve Metinler": [
                    "Edebi Sanatlar",
                    "Divan Edebiyatı",
                    "Halk Edebiyatı",
                    "Cumhuriyet Dönemi",
                ],
            },
            "AYT Tarih-2": {
                "İlk Çağ ve Çağdaş Tarih": [
                    "İlk Uygarlıklar",
                    "Osmanlı Merkez Teşkilatı",
                    "İki Savaş Arası Dönem",
                    "Soğuk Savaş ve XXI. Yüzyıl",
                ],
            },
            "AYT Coğrafya-2": {
                "Mekansal Sentez": [
                    "Türkiye'nin İklimi ve Yeryüzü Şekilleri",
                    "Küresel Örgütler ve Afetler",
                ],
            },
            "AYT Felsefe Grubu": {
                "Felsefe ve Mantık": [
                    "Felsefi Düşünce",
                    "Klasik Mantık ve Mantık-Dil",
                    "Sembolik Mantık",
                ],
                "Psikoloji ve Sosyoloji": [
                    "Psikolojinin Temel Süreçleri",
                    "Öğrenme ve Bellek",
                    "Sosyolojiye Giriş ve Toplumsal Yapı",
                ],
            },
            "AYT Din Kültürü": {
                "İnanç ve İbadet": [
                    "Allah İnsan İlişkisi",
                    "Kur'an Kavramları",
                    "İslam Düşüncesinde Tasavvufi Yorumlar",
                ],
            },
        },
    },
    "YDT (Dil)": {
        "YDT İngilizce": {
            "Gramer ve Kelime": [
                "Vocabulary & Collocations",
                "Tenses & Modals",
                "Clauses & Conjunctions",
            ],
            "Soru Tipleri": [
                "Cloze Test & Cümle Tamamlama",
                "İngilizce-Türkçe Çeviri",
                "Paragraf Okuma ve Anlama",
                "Diyalog & Anlamı Bozan Cümle",
            ],
        }
    },
}
