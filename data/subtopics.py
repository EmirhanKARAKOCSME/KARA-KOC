"""Mikro konuların alt başlıkları (alt konu kataloğu).

`_ALT_TYT` / `_ALT_AYT_SAYISAL` sözlükleri "Alt Başlık 1|Alt Başlık 2|..."
biçiminde ham metin tutar; `_alt_ayristir` bunları listeye çevirir ve
`MIKRO_ALT_KONULAR` uygulamanın kullandığı nihai haritayı üretir.

Veri `main.py`'den birebir taşındı; başlık sıraları ve yazımları korunmuştur.
"""


def _alt_ayristir(ham_sozluk):
    sonuc = {}
    for anahtar, metin in ham_sozluk.items():
        sonuc[anahtar] = [p.strip() for p in metin.split("|") if p.strip()]
    return sonuc


_ALT_TYT = {
    # TYT MATEMATİK
    "Temel Kavramlar": "Rakam, sayı ve sayı kümeleri|Tek-çift sayılar ve işlem kuralları|Pozitif ve negatif sayılar|Asal sayılar ve asal çarpanlara ayırma|Ardışık sayılar ve toplam formülleri|Faktöriyel kavramı",
    "Sayı Basamakları": "Basamak değeri ve çözümleme|Basamak sayısı ve rakam değişimi problemleri|Taban aritmetiği ve taban dönüştürme",
    "Bölme ve Bölünebilme": "Bölme algoritması|Bölünebilme kuralları (2, 3, 4, 5, 8, 9, 10, 11)|Aralarında asal çarpanlara bölünme|Kalan aritmetiği",
    "EBOB – EKOK": "Asal çarpanlarla EBOB-EKOK hesabı|EBOB-EKOK bağıntıları|Periyodik problemler (zil, nöbet, tur)|Boyut eşitleme problemleri",
    "Rasyonel Sayılar": "Kesir türleri|Dört işlem ve işlem önceliği|Sonsuz merdivenli kesirler|Ondalık ve devirli ondalık sayılar|Rasyonel sayılarda sıralama",
    "Basit Eşitsizlikler": "Eşitsizlik özellikleri ve yön değiştirme|Taraf tarafa toplama ve çarpma|Üslü ifadeli eşitsizlikler|İfade aralığı belirleme",
    "Mutlak Değer": "Mutlak değerin uzaklık tanımı|Mutlak değerli denklemler|Mutlak değerli eşitsizlikler|Üçgen eşitsizliği|En küçük ve en büyük değer problemleri",
    "Üslü Sayılar": "Özellikler ve negatif üs|Toplama, çıkarma, çarpma, bölme|Üssün üssü ve parantez önceliği|Üslü denklemler (taban/üs analizi)|Üslü ifadelerde sıralama",
    "Köklü Sayılar": "Kök derecesi ve tanımlılık şartları|Kök dışına çıkarma, içeri alma, derece sadeleştirme|Köklü ifadelerde dört işlem|Eşlenik ile paydayı kökten kurtarma|Köklü denklemler ve yalancı kök",
    "Çarpanlara Ayırma": "Ortak çarpan parantezine alma|Gruplandırarak çarpanlara ayırma|Özdeşliklerle çarpanlara ayırma|ax²+bx+c üç terimlileri|Terim ekleyip çıkarma|Rasyonel ifadelerin sadeleştirilmesi",
    "Oran Orantı": "Oran ve orantı sabiti|Doğru, ters ve bileşik orantı|Aritmetik, geometrik, harmonik ortalama|Orantı problemleri",
    "Denklem Çözme": "Bir ve iki bilinmeyenli denklemler|Denklem sistemleri|Sonsuz çözüm / boş küme şartları|Parametrik denklemler ve değişken eleme",
    "Sayı Problemleri": "Denklem kurma|Sıra ve kuyruk problemleri|Merdiven problemleri|Bilet dağıtım problemleri",
    "Kesir Problemleri": "Tel kesme ve orta nokta kayması|Parça alma problemleri|Depo ve havuz doluluk oranları",
    "Yaş Problemleri": "Yaş farkının sabitliği|Doğum yılı bağıntıları|Yaş ortalamaları",
    "Hareket Hız Problemleri": "x=v·t ve ortalama hız|Karşılıklı ve aynı yönde hareket|Dairesel pist|Akıntı ve rüzgâr|Tren-tünel problemleri",
    "İşçi Emek Problemleri": "Birim zamanda yapılan iş|Birlikte çalışma denklemleri|İş gücü ve süre değişimi",
    "Yüzde-Kâr-Zarar Problemleri": "Yüzde hesapları|Maliyet, etiket fiyatı, kâr ve zarar|Zam ve indirim|Enflasyon ve alım gücü",
    "Karışım Problemleri": "Karışım oranı|Saf madde/su ekleme ve buharlaştırma|Karışımları birleştirme",
    "Grafik Problemleri": "Daire grafiği|Sütun ve çizgi grafiği okuma|Zamana bağlı değişim grafikleri",
    "Kümeler – Kartezyen Çarpım": "Küme tanımı ve gösterimler|Alt küme sayısı formülleri|Küme işlemleri|Küme problemleri|Kartezyen çarpım",
    "Mantık": "Önerme ve denk önermeler|Bağlaçlar (ve, veya, ya da)|Koşullu ve iki yönlü koşullu önerme|De Morgan ve sadeleştirme|Niceleyiciler|Açık önermeler ve doğruluk kümesi|Teorem ve ispat yöntemleri",
    "Fonksiyonlar": "Fonksiyon kavramı, tanım ve değer kümesi|Fonksiyon olma şartı|Fonksiyon türleri|Bileşke fonksiyon|Ters fonksiyon|Grafik okuma ve eksen kesim noktaları",
    "Permütasyon ve Kombinasyon": "Toplama ve çarpma yoluyla sayma|Permütasyon|Tekrarlı permütasyon|Dairesel permütasyon|Kombinasyon|Seçim ve geometri problemleri|Binom açılımı",
    "Olasılık": "Örnek uzay ve olay kavramları|Teorik ve deneysel olasılık|Ayrık ve ayrık olmayan olaylar|Bağımsız olaylar ve bileşik olasılık|Koşullu olasılık ve Bayes|Geometrik olasılık",
    "Veri – İstatistik": "Aritmetik ortalama, medyan, mod|Açıklık, çeyrekler açıklığı, standart sapma|Veri toplama ve örneklem|Grafik yorumlama (kutu, serpme, çizgi, sütun)",
    # TYT TÜRKÇE
    "Sözcükte Anlam": "Gerçek, yan, mecaz ve terim anlam|Somut-soyut ve genel-özel anlam|Eş anlamlı, zıt anlamlı, eş sesli|Anlam aktarmaları ve ad aktarması|Somutlaştırma ve soyutlaştırma",
    "Söz Yorumu": "Mecaz ve yan anlamlı söz yorumu|Duyular arası ve insandan doğaya aktarımlı sözler|Soyut-somut kavram yorumu",
    "Deyim ve Atasözü": "Deyimlerin kalıplaşmış yapısı|Deyimlerin cümleye kattığı anlamlar|Atasözlerinin mecaz/gerçek anlamı|Deyim ve atasözü eşleştirme",
    "Cümlede Anlam İlişkileri": "Neden-sonuç cümleleri|Amaç-sonuç cümleleri|Koşul-sonuç cümleleri|Öznel ve nesnel yargılar|Doğrudan ve dolaylı anlatım",
    "Cümle Yorumu ve Kavramlar": "Örtülü anlam|Cümleye hâkim duygular (pişmanlık, sitem, öz eleştiri...)|Cümle tamamlama ve birleştirme|Cümleden kesin yargı çıkarma",
    "Paragrafta Anlatım Teknikleri": "Anlatım biçimleri (açıklayıcı, tartışmacı, öyküleyici, betimleyici)|Anlatıcı türleri ve bakış açıları",
    "Paragrafta Düşünceyi Geliştirme Yolları": "Tanımlama ve örneklendirme|Tanık gösterme|Karşılaştırma ve benzetme|Sayısal verilerden yararlanma|Somutlama",
    "Paragrafta Yapı": "Giriş-gelişme-sonuç bölümleri|Paragrafı ikiye bölme|Düşüncenin akışını bozan cümle|Cümle yerleştirme ve yer değiştirme|Karma (çoklu) paragraf soruları",
    "Paragrafta Konu-Ana Düşünce": "Paragrafın konusu|Ana düşünce|Başlık bulma",
    "Paragrafta Yardımcı Düşünce": "Yardımcı düşünceler|Çıkarılamayacak yargılar|Paragraftan kesin yargı",
    "Ses Bilgisi": "Büyük ve küçük ünlü uyumu|Ünlü düşmesi, türemesi, daralması, değişimi|Ünsüz yumuşaması ve sertleşmesi|Ünsüz düşmesi ve türemesi|Dudak ünsüzlerinin benzeşmesi (n-b)|Kaynaştırma harfleri|Ulama",
    "Yazım Kuralları": "Büyük harflerin kullanımı|de/da yazımı|ki yazımı|mi yazımı|Sayıların yazımı|Kısaltmalar|Birleşik sözcüklerin yazımı|İkileme ve pekiştirmeler|Düzeltme işareti",
    "Noktalama İşaretleri": "Nokta, virgül, noktalı virgül, iki nokta|Üç nokta, soru ve ünlem işareti|Kısa çizgi, uzun çizgi, eğik çizgi|Tırnak ve tek tırnak|Parantez, köşeli ayraç, kesme işareti|İşlevler ve yanlış kullanımlar",
    "Sözcükte Yapı ve Ekler": "Kök türleri|Yapım ekleri|İsim çekim ekleri|Fiil çekim ekleri|Basit, türemiş, birleşik sözcük",
    "İsimler": "Özel-cins, tekil-çoğul-topluluk, somut-soyut isimler|İsim tamlamaları",
    "Zamirler": "Kişi zamirleri|İşaret zamirleri|Belgisiz ve soru zamirleri|Dönüşlülük zamiri|İyelik ve ilgi zamiri (ki)",
    "Sıfatlar": "Niteleme sıfatları|Belirtme sıfatları (işaret, sayı, belgisiz, soru)|Sıfat tamlaması ve adlaşmış sıfat|Pekiştirme ve küçültme",
    "Zarflar": "Durum zarfı|Zaman zarfı|Miktar zarfı|Yer-yön zarfı|Soru zarfı",
    "Edat – Bağlaç – Ünlem": "Edat (ilgeç)|Bağlaç|Ünlem",
    "Fiilde Anlam": "İş, durum, oluş fiilleri|Haber ve dilek kipleri|Kişi, olumsuzluk ve soru biçimleri|Zaman/kip kayması",
    "Ek Fiil": "İsim soylu sözcükleri yüklem yapma|Birleşik zamanlı fiiller (idi, imiş, ise)|Ek fiilin görevleri",
    "Fiilimsi": "İsim-fiil (mastar)|Sıfat-fiil (ortaç)|Zarf-fiil (ulaç)",
    "Fiilde Çatı": "Etken ve edilgen|Dönüşlü ve işteş|Geçişli ve geçişsiz|Oldurgan ve ettirgen",
    "Cümlenin Ögeleri": "Yüklem|Özne türleri|Nesne (belirtili/belirtisiz)|Dolaylı tümleç|Zarf tümleci ve edat tümleci|Ara söz, ara cümle ve vurgu",
    "Anlatım Bozukluğu": "Gereksiz ve çelişen sözcükler|Yanlış anlam ve yer kullanımı|Mantık ve sıralama hatası|Deyim ve atasözü yanlışları|Özne-yüklem uyumsuzluğu|Öge eksikliği|Ek ve tamlama yanlışları|Çatı uyumsuzluğu",
    # TYT GEOMETRİ
    "Temel Kavramlar ve Doğruda Açılar": "Nokta, doğru, düzlem, ışın|Komşu, tümler, bütünler, ters açılar|Paralel doğrular ve kesen (Z, U, M, kalem ucu)",
    "Üçgende Açılar": "İç ve dış açı toplamı|Dış açı eşitliği|Üçgen eşitsizliği|Açı-kenar bağıntıları|Dar, dik, geniş açılı üçgenlerde kenar sınırları",
    "Dik Üçgen ve Pisagor": "Pisagor teoremi|Öklid bağıntıları|Özel açılı dik üçgenler|Özel kenarlı dik üçgenler (3-4-5 vb.)",
    "İkizkenar ve Eşkenar Üçgen": "İkizkenar üçgende taban dikmesi (YAĞİ)|Taban üzerindeki noktadan dikmeler|Eşkenar üçgen alan ve yükseklik|Eşkenar üçgende iç nokta dikmeleri",
    "Açıortay ve Kenarortay": "İç açıortay teoremi|Dış açıortay teoremi|Teğet çember merkezleri|Kenarortay ve ağırlık merkezi|Muhteşem üçlü|Kenarortay formülü ve orta taban",
    "Üçgende Eşlik ve Benzerlik": "Eşlik kuralları (KAK, AKA, KKK)|Benzerlik kuralları (AA, KAK, KKK)|Thales ve temel orantı teoremi|Kelebek benzerliği|Benzerlik oranı: çevre ve alan",
    "Üçgende Alan": "Taban × yükseklik / 2|Sinüslü alan formülü|Heron formülü|İç teğet çember (A=u·r)|Çevrel çember (A=abc/4R)|Alan oranlama ve kaydırma",
    "Çokgenler": "İç ve dış açı toplamları|Köşegen sayısı|Düzgün çokgenler",
    "Dörtgenler ve Özel Dörtgenler": "Genel dörtgen özellikleri|Köşegenleri dik kesişen dörtgenler|Alan formülleri",
    "Deltoid": "Deltoid özellikleri|Köşegen dikliği ve açıortaylık|Deltoid alanı",
    "Paralelkenar ve Eşkenar Dörtgen": "Paralelkenar özellikleri|Paralelkenar alanı|Eşkenar dörtgen köşegenleri|Eşkenar dörtgen alanı",
    "Dikdörtgen ve Kare": "Köşegen özellikleri|İç nokta kuralları|Alan ve çevre",
    "Yamuk": "İkizkenar ve dik yamuk|Orta taban|Yamuk alanı",
    # TYT FİZİK
    "Fizik Bilimine Giriş": "Fiziğin tanımı ve alt dalları|Diğer bilimlerle ilişkisi|Bilim insanları ve tarihsel gelişim|Kariyer alanları ve araştırma merkezleri",
    "Madde ve Özellikleri": "Kütle, hacim, özkütle|Özkütle grafikleri|Karışımların özkütlesi",
    "Dayanıklılık ve Akışkanlar": "Katılarda dayanıklılık|Adezyon ve kohezyon|Yüzey gerilimi|Kılcallık",
    "Hareket ve Kuvvet": "4 temel kuvvet ve hareket türleri|Konum, yer değiştirme, yol, hız, sürat|Düzgün doğrusal hareket|x-t, v-t, a-t grafikleri",
    "Newton'un Hareket Yasaları": "Eylemsizlik ilkesi|Temel yasa (F=m·a)|Etki-tepki|Sürtünme kuvveti|Eğik düzlem|Bloklar ve makaralı sistemler",
    "Basınç": "Katı basıncı|Sıvı basıncı ve basınç kuvveti|U boruları|Pascal ilkesi ve hidrolik sistemler",
    "Sıvıların Kaldırma Kuvveti": "Açık hava basıncı ve barometre|Gaz basıncı ve manometre|Arşimet ilkesi|Yüzme, askıda kalma, batma|Taşırma kapları",
    "Isı, Sıcaklık ve Genleşme": "Sıcaklık, ısı, iç enerji|Termometreler ve sıcaklık dönüşümleri|Öz ısı ve Q=m·c·ΔT|Hâl değişimi ve gizli ısı|Isıl denge|Isı iletim yolları|Genleşme ve suyun anomalisi",
    "Elektrostatik": "Yük ve yükün korunumu|Elektriklenme türleri|Elektroskop|Coulomb yasası|Elektrik alan",
    "Elektrik Akımı ve Devreler": "Akım, potansiyel fark, direnç|Ohm yasası ve direnç formülü|Seri ve paralel bağlama|Kirchhoff yasaları|Üreteçler ve iç direnç|Elektriksel güç ve enerji",
    "Mıknatıslar ve Manyetik Alan": "Mıknatıs türleri ve kutuplar|Manyetik alan çizgileri|Akım geçen tel, halka, selenoid alanı",
    "Aydınlanma ve Aynalar": "Işık şiddeti, akısı, aydınlanma|Gölge ve tutulmalar|Düzlem ayna|Küresel aynalar",
    "Kırılma ve Mercekler": "Kırılma indisi ve Snell yasası|Tam yansıma ve sınır açısı|Görünür derinlik|Mercekler|Göz kusurları",
    "Dalga Harekatı": "Dalga parametreleri|Yay dalgaları|Su dalgaları|Kırınım ve girişim|Elektromanyetik spektrum",
    # TYT KİMYA
    "Kimya Bilimi": "Simyadan kimyaya|Kimyanın alt disiplinleri|Kimya meslekleri|Maddelerin sağlık ve çevre etkisi|Laboratuvar güvenliği ve piktogramlar|Laboratuvar cam malzemeleri",
    "Atom Yapısı ve Periyodik Sistem": "Atom modelleri|Temel tanecikler (Z, A, iyon yükü)|İzotop, izobar, izoton, izoelektronik|Elektron dizilimi kuralları|Periyodik sistemin yapısı|Periyodik özellikler (yarıçap, iyonlaşma enerjisi, EN)",
    "Kimyasal Türler Arası Etkileşimler": "Kimyasal türler|İyonik bağ|Kovalent bağ|Metalik bağ|Lewis yapısı|Molekül polarlığı|Van der Waals kuvvetleri|Hidrojen bağı",
    "Maddenin Halleri": "Plazma hali|Katı türleri|Viskozite|Buharlaşma ve buhar basıncı|Kaynama|Bağıl nem|Hâl değişim grafikleri",
    "Kimyanın Temel Kanunları": "Kütlenin korunumu (Lavoisier)|Sabit oranlar (Proust)|Katlı oranlar (Dalton)",
    "Mol Kavramı ve Kimyasal Hesaplamalar": "Mol, Avogadro, molar kütle|Denklem denkleştirme ve tepkime türleri|Tepkime hesaplamaları|Sınırlayıcı bileşen|Yüzde verim ve saflık|Formül bulma",
    "Karışımlar ve Ayırma Yöntemleri": "Homojen ve heterojen karışımlar|Çözünme ve benzer benzeri çözer|Derişim birimleri|Seyreltme ve deriştirme|Koligatif özellikler|Ayırma teknikleri|Çözünürlük eğrileri",
    "Asitler, Bazlar ve Tuzlar": "Asit-baz özellikleri ve pH|Arrhenius ve Brønsted-Lowry|Kuvvetli ve zayıf asit/bazlar|Nötralleşme ve metallerle tepkime|Tuzlar",
    # TYT BİYOLOJİ
    "Canlıların Ortak Özellikleri": "Hücresel yapı|Beslenme|Solunum|Boşaltım|Hareket|Uyarılara tepki ve uyum|Organizasyon basamakları|Üreme, büyüme, gelişme|Homeostazi ve metabolizma",
    "Canlıların Temel Bileşenleri": "Su ve mineraller|Asit, baz, pH|Karbonhidratlar|Lipitler|Proteinler|Enzimler|Vitaminler|Nükleik asitler|ATP",
    "Hücre Yapısı ve Organeller": "Prokaryot ve ökaryot hücre|Hücre zarı yapısı|Zarsız organeller|Tek zarlı organeller|Çift zarlı organeller|Çekirdek|Hücreden organizmaya organizasyon",
    "Hücre Zarından Madde Geçişleri": "Difüzyon ve kolaylaştırılmış difüzyon|Ozmoz|Aktif taşıma|Endositoz ve ekzositoz",
    "Canlıların Sınıflandırılması": "Yapay ve doğal sınıflandırma|İkili adlandırma|Sınıflandırma kategorileri|3 domain sistemi|Bakteriler ve arkeler|Protistler ve mantarlar|Bitkiler|Hayvanlar|Virüsler",
    "Mitoz ve Eşeysiz Üreme": "Hücre döngüsü|Mitoz evreleri|Sitokinez|Kontrol noktaları ve kanser|Eşeysiz üreme türleri",
    "Mayoz ve Eşeyli Üreme": "Mayoz I|Mayoz II|Mitoz-mayoz farkları|Gamet oluşumu ve döllenme",
    "Mendelyan Kalıtım": "Mendel ilkeleri ve terimler|Monohibrit ve dihibrit çaprazlama|Test çaprazlaması|Eksik ve eş baskınlık|Çok alellilik (kan grupları)|Eşey belirlenmesi ve eşeye bağlı kalıtım|Soyağacı analizi",
    "Ekosistem Ekolojisi": "Abiyotik ve biyotik bileşenler|Besin zinciri, ağı ve ekolojik piramitler|Madde döngüleri (C, N, su)|Biyobirikim",
    # TYT TARİH
    "Tarih ve Zaman": "Tarihin konusu ve yöntemi|Tarihsel araştırmanın 5 T aşaması|Birincil ve ikincil kaynaklar|Tarihe yardımcı bilimler|Takvim sistemleri",
    "İnsanlığın İlk Dönemleri": "Taş ve maden çağları|Neolitik devrim ve ilk yerleşmeler|Mezopotamya uygarlıkları|Mısır uygarlığı|Anadolu uygarlıkları|Doğu Akdeniz, Hint ve Çin uygarlıkları|İlk çağda hukuk",
    "İlk ve Orta Çağlarda Türk Dünyası": "Türk adı, ana yurt ve konargöçer yaşam|Asya Hun Devleti|Kavimler Göçü ve Avrupa Hun Devleti|Kök Türk devletleri|Uygur Devleti|Diğer Türk boyları|Kültür ve medeniyet",
    "İslam Medeniyetinin Doğuşu": "Cahiliye dönemi|Hz. Muhammed dönemi|Dört Halife dönemi|Emeviler|Abbasiler",
    "Türk-İslam Devletleri": "Karahanlılar|Gazneliler|Büyük Selçuklu Devleti|Mısır'da kurulan Türk devletleri",
    "Beylikten Devlete Osmanlı Siyareti": "Kuruluş ve ilk beyler|Ankara Savaşı ve Fetret|İskan ve istimalet politikası|Fatih dönemi|II. Bayezid ve Yavuz|Kanuni dönemi|Merkez ve taşra teşkilatı|Tımar sistemi",
    "Milli Mücadele ve Atatürkçülük": "XX. yüzyıl başı savaşlar|I. Dünya Savaşı|Mondros ve işgaller|Kongreler dönemi|TBMM ve ayaklanmalar|Cepheler|Lozan|Atatürk ilkeleri|İnkılaplar",
    # TYT COĞRAFYA
    "Doğa ve İnsan": "Coğrafyanın tanımı ve bölümleri|Fiziki ve beşeri alt dallar|Temel ilkeler|Doğa-insan etkileşimi",
    "Dünya’nın Şekli ve Hareketleri": "Geoit şekil ve sonuçları|Küresel şeklin sonuçları|Günlük hareket|Yıllık hareket ve eksen eğikliği|Özel tarihler",
    "Coğrafi Konum": "Mutlak konum (paralel, meridyen)|Yerel ve ulusal saat|Türkiye'nin mutlak konumu|Özel konum",
    "Harita Bilgisi": "Harita elemanları|Ölçek|Projeksiyonlar|Yer şekillerini gösterme yöntemleri|İzohips okuma|CBS, uzaktan algılama, GPS",
    "İklim Bilgisi": "Atmosfer katmanları|Sıcaklık|Basınç ve rüzgârlar|Nem ve yağış|Büyük iklim tipleri|Türkiye iklimi",
    "Nüfus ve Yerleşme": "Nüfusun tarihsel değişimi|Dağılışı etkileyen faktörler|Demografik göstergeler|Nüfus piramitleri|Göç türleri|Kırsal yerleşme|Şehirsel yerleşme",
    "Türkiye’nin Yer Şekilleri": "Dağlar (kıvrım, kırık, volkanik)|Platolar|Ovalar|Akarsu ve göller",
    "Ekonomik Faaliyetler": "Birincil faaliyetler|İkincil faaliyetler|Üçüncül faaliyetler|Dördüncül ve beşincil faaliyetler|Türkiye ekonomisi|Bölge kavramı ve türleri",
    "Doğal Afetler ve Çevre": "İklim değişikliği ve sera etkisi|Jeolojik afetler|Meteorolojik ve hidrolojik afetler|Beşeri/teknolojik afetler|Afet yönetimi safhaları|Küresel ve bölgesel örgütler",
    # TYT FELSEFE & DİN
    "Felsefenin Konusu": "Felsefenin anlamı|Felsefi düşüncenin özellikleri|Felsefe-bilim-din-sanat|Soru sorma ve argümantasyon",
    "Bilgi Felsefesi": "Temel kavramlar|Bilgi türleri|Şüphecilik|Rasyonalizm|Empirizm|Kritisizm|Pozitivizm ve diğer akımlar",
    "Varlık Felsefesi": "Ontolojinin soruları|Monizm, düalizm, plüralizm|Oluş ve madde (materyalizm)|İdealizm|Fenomen ve varoluşçuluk",
    "Ahlak Felsefesi": "Etiğin temel kavramları|Özgürlük ve determinizm|Ahlak yasasını reddedenler|Utilitarizm ve sezgicilik|Erdem ve ödev etiği",
    "Bilgi ve İnanç": "İslam'da bilginin kaynakları|İman kavramı ve iman-amel ilişkisi|Allah'ın sıfatları|Peygamberlerin sıfatları|Hz. Muhammed'in örnekliği",
    "İslam ve İbadet": "İbadet kavramı ve çeşitleri|İslam'ın şartları ve imanın esasları|Mükellefiyet dereceleri|Dua, tövbe, istiğfar, tevekkül",
    "Ahlak ve Değerler": "Ahlakın kaynakları|Övülen ahlaki erdemler|Yerilen davranışlar",
}


_ALT_AYT_SAYISAL = {
    # AYT MATEMATİK
    "Polinomlar ve Çarpanlara Ayırma": "Polinom tanımı, derece, katsayılar toplamı|Polinomlarda dört işlem|Bölme algoritması ve kalan teoremi|Kök-katsayı ilişkileri|Çarpanlara ayırma yöntemleri",
    "İkinci Dereceden Denklemler": "Diskriminant analizi|Kök bulma formülleri|Vieta formülleri|Kökleri verilen denklemi kurma",
    "Karmaşık Sayılar": "Sanal birim ve i'nin kuvvetleri|Standart form, reel ve sanal kısım|Karmaşık eşlenik|Dört işlem",
    "Parabol": "İkinci dereceden fonksiyon grafiği|Tepe noktası|Eksenleri kestiği noktalar|Parabol denklemi yazma|Parabol-doğru ilişkisi|Optimizasyon problemleri",
    "İkinci Dereceden Eşitsizlik Sistemleri": "İşaret tablosu|Tek ve çift katlı kökler|Payda ve rasyonel eşitsizlik|Mutlak değerli eşitsizlikler|Kesişim kümesi bulma",
    "Yönlü Açılar ve Trigonometrik Oranlar": "Yönlü açılar, derece-radyan|Birim çember ve trigonometrik oranlar|Trigonometrik özdeşlikler|Bölgelere göre işaret ve açı dönüştürme|Sinüs ve kosinüs teoremi|Periyot ve grafikler|Ters trigonometrik fonksiyonlar|Toplam-fark formülleri|İki kat açı formülleri",
    "Trigonometrik Denklemler": "sinx = sina|cosx = cosa|tanx = tana|Genel çözüm kümeleri",
    "Üstel ve Logaritmik Fonksiyonlar": "Üstel fonksiyon ve grafiği|Logaritma fonksiyonu ve tanım kümesi|Onluk ve doğal logaritma|Logaritma özellikleri|Logaritmik denklem ve eşitsizlikler|Gerçek hayat problemleri",
    "Aritmetik ve Geometrik Diziler": "Dizi kavramı ve genel terim|Aritmetik dizi|Aritmetik dizide toplam|Geometrik dizi|Geometrik dizide toplam|Sonsuz toplam ve yakınsaklık",
    "Limit ve Süreklilik": "Yaklaşım, sağdan ve soldan limit|Limit özellikleri ve kuralları|0/0 belirsizliği|Bir noktada süreklilik|Süreksizlik türleri|Parçalı fonksiyonlarda limit ve süreklilik",
    "Türev Alma Kuralları": "Türevin limit tanımı|Polinom, rasyonel, köklü ifadelerin türevi|Çarpım ve bölüm türevi|Zincir kuralı|Parçalı ve mutlak değerli fonksiyonların türevi",
    "Türevin Geometrik Yorumu ve Maks-Min": "Teğet ve normal doğruları|Artan-azalan aralıklar|Ekstremum noktalar|Maksimum-minimum problemleri",
    "Belirsiz İntegral": "Ters türev ve belirsiz integral|İntegral alma kuralları|Değişken değiştirme yöntemi",
    "Belirli İntegral ve Alan Hesabı": "Belirli integral ve Riemann toplamı|Newton-Leibniz ve özellikleri|Parçalı ve simetrik fonksiyonlar|Eğri altında kalan alan|İki eğri arasında kalan alan|Eksenlere göre alan",
    # AYT GEOMETRİ
    "Çemberde Açı": "Merkez, çevre, teğet-kiriş açılar|İç ve dış açılar|Aynı yayı gören açılar|Kirişler dörtgeni",
    "Çemberde Uzunluk": "Teğet özellikleri|Teğetler dörtgeni|Çemberde kuvvet|Kirişe inilen dikme",
    "Dairede Çevre ve Alan": "Çevre ve yay uzunluğu|Daire alanı|Daire dilimi alanı",
    "Noktanın Analitik İncelemesi": "Dik koordinat sistemi|İki nokta arası uzaklık|Orta nokta ve bölen nokta",
    "Doğrunun Analitik İncelemesi": "Eğim|Doğru denklemi yazma|Eksenleri kestiği noktalar|Paralellik ve diklik|Kesim noktası|Noktanın doğruya uzaklığı",
    "Dönüşüm Geometrisi": "Öteleme|Yansıma (simetri)|Dönme|Bileşke dönüşümler",
    "Çemberin Analitik İncelemesi": "Standart denklem|Merkezil çember|Genel denklem|Doğru ile çemberin durumu|Teğet denklemi",
    "Prizmalar ve Küp": "Dik prizma: yanal alan, toplam alan, hacim|Küp: alan, hacim, cisim köşegeni",
    "Silindir ve Koni": "Dik dairesel silindir|Dik dairesel koni ve açınımı",
    "Piramit ve Küre": "Dik piramit ve düzgün dörtyüzlü|Küre: yüzey alanı, hacim, kesit",
    # AYT FİZİK
    "Vektörler ve Bağıl Hareket": "Vektör özellikleri|Toplama-çıkarma yöntemleri|Bileşke vektör ve özel durumlar|Bağıl hız|Nehirde hareket",
    "Newton'ın Hareket Yasaları": "Birinci ve üçüncü yasa|Temel yasa ve sürtünme|Eğik düzlem|Bloklar ve makaralı sistemler",
    "Atışlar": "Serbest düşme|Limit hız ve hava direnci|Düşey atış|Yatay atış|Eğik atış",
    "İş-Enerji Korunumu": "İş ve güç|Kinetik ve potansiyel enerji|Esneklik potansiyel enerjisi ve Hooke yasası|İş-enerji teoremi|Mekanik enerjinin korunumu",
    "İtme ve Çizgisel Momentum": "İtme ve momentum|İtme-momentum değişimi ve F-t grafiği|Momentumun korunumu|Esnek çarpışmalar|Esnek olmayan çarpışmalar|Patlamalar ve roket hareketi",
    "Tork ve Dönme Dengesi": "Tork ve yönü|Dönme dengesi ve kuvvet dengesi|Lami teoremi|Kütle ve ağırlık merkezi",
    "Elektriksel Kuvvet ve Elektrik Alan": "Elektrik yükleri ve elektriklenme|Elektroskop|Coulomb yasası|Elektrik alan ve alan çizgileri|Yüklü iletken küre",
    "Elektriksel Potansiyel": "Elektriksel potansiyel enerji|Elektriksel potansiyel|Elektriksel iş (W=q·ΔV)",
    "Düzgün Elektrik Alan ve Sığaçlar": "Düzgün elektrik alan ve sapma hareketi|Sığa ve kondansatörler|Depolanan enerji",
    "Manyetik Alan ve Manyetik Kuvvet": "Akım geçen tel, halka, selenoid alanı|Akım taşıyan tele etkiyen kuvvet|Yüklü parçacığa etkiyen kuvvet|Manyetik akı",
    "İndüksiyon ve Alternatif Akım": "Faraday ve Lenz yasaları|Öz-indüksiyon|Alternatif akım (R, XL, XC, rezonans)|Transformatörler",
    "Düzgün Çembersel Hareket": "Çizgisel hız, açısal hız, periyot, frekans|Merkezcil ivme ve kuvvet|Yatay, düşey ve virajlı çembersel hareket",
    "Açısal Momentum ve Kepler": "Eylemsizlik momenti ve dönme kinetik enerjisi|Açısal momentum ve korunumu|Kepler yasaları|Kütle çekim kuvveti ve çekim ivmesi",
    "Basit Harmonik Hareket": "BHH tanımı ve büyüklükler|Konum-hız-ivme denklemleri|Yaylı sarkaç|Basit sarkaç",
    "Dalga Mekaniği ve Doppler": "Dalga parametreleri ve yay dalgaları|Su dalgaları: kırınım ve girişim|Işıkta girişim ve kırınım (Young)|Elektromanyetik dalgalar|Doppler olayı",
    "Atom Fiziği ve Radyoaktivite": "Atom modellerinin gelişimi|Bohr modeli|Atomun uyarılması|Işıma serileri|Radyoaktivite (α, β, γ)|Yarılanma ömrü, fisyon ve füzyon",
    "Fotoelektrik Olay": "Foton ve fotoelektrik denklemi|Bağlanma enerjisi ve kesme potansiyeli|Compton saçılması ve de Broglie dalga boyu",
    # AYT KİMYA
    "Modern Atom Teorisi": "Kuantum sayıları|Orbitaller ve orbital şemaları|Elektron dizilimi kuralları (Aufbau, Pauli, Hund)|Küresel simetri, uyarılmış atom, iyon dizilimleri",
    "Gazlar ve Ideal Gaz Yasası": "Gazların genel özellikleri|Gaz yasaları (Boyle, Charles, Gay-Lussac)|İdeal gaz denklemi|Gaz karışımları ve kısmi basınç|Difüzyon ve gerçek gazlar",
    "Sıvı Çözeltiler ve Çözünürlük": "Çözünme ve çözücü-çözünen etkileşimi|Derişim birimleri (molarite, molalite, mol kesri)|Koligatif özellikler|Çözünürlük eğrileri ve etkileyen faktörler",
    "Kimyasal Tepkimelerde Enerji": "Entalpi, endotermik-ekzotermik|Potansiyel enerji grafikleri|Oluşum entalpisi|Bağ enerjileri|Hess yasası",
    "Tepkime Hızları": "Hız tanımı|Çarpışma teorisi ve aktifleşme enerjisi|Hız bağıntısı ve mertebe|Mekanizmalı tepkimeler|Hızı etkileyen faktörler",
    "Kimyasal Denge": "Dinamik denge|Denge sabiti Kc|Kp ve Kp-Kc ilişkisi|Qc ile denge kontrolü|Le Chatelier ilkesi",
    "Asit-Baz Dengesi": "Su oto-iyonizasyonu|Ka, Kb ve iyonlaşma yüzdesi|Tampon çözeltiler|Tuz hidrolizi|Titrasyon",
    "Çözünürlük Dengesi (KÇÇ)": "Çözünürlük çarpımı (Kçç)|Çökelme şartları (Qc-Kçç)|Ortak iyon etkisi",
    "Redoks ve Elektrokimya": "Yükseltgenme basamağı|Redoks denkleştirme|Galvanik hücre|Standart elektrot potansiyeli|Nernst denklemi|Derişim pilleri|Elektroliz|Faraday kanunları|Korozyon",
    "Karbon Kimyasına Giriş": "Hibritleşme|Sigma ve pi bağları|VSEPR ve molekül geometrisi|Karbon allotropları|Organik-anorganik farkları",
    "Organik Bileşikler": "Fonksiyonel gruplar ve adlandırma|Alkanlar|Alkenler|Alkinler|Aromatik bileşikler|Alkoller ve eterler|Aldehitler ve ketonlar|Karboksilik asitler ve esterler",
    # AYT BİYOLOJİ
    "Sinir Sistemi ve Duyu Organları": "Nöron yapısı ve çeşitleri|İmpuls oluşumu ve iletimi|Sinapslar|Merkezi sinir sistemi|Çevresel sinir sistemi|Duyu organları",
    "Endokrin Sistem": "Endokrin bezler ve hormonlar|Hormonal geri bildirim",
    "Destek ve Hareket Sistemi": "İskelet sistemi|Kas doku türleri|Kayan iplikler ve kasılma",
    "Sindirim Sistemi": "Sindirim organları|Yardımcı organlar|Mekanik ve kimyasal sindirim|Emilim",
    "Dolaşım ve Bağışıklık Sistemi": "Kalp ve kardiyak döngü|Kan damarları|Kanın yapısı|Lenf dolaşımı|Doğal bağışıklık|Kazanılmış bağışıklık|Aşı ve serum",
    "Solunum Sistemi": "Solunum organları|Soluk alıp verme|Gazların taşınması",
    "Üriner Sistem": "Böbrek ve nefron yapısı|Süzülme|Geri emilim|Salgılama",
    "Genden Proteine (Protein Sentezi)": "Genetik şifre, kodon, antikodon|DNA replikasyonu|Santral dogma|Transkripsiyon ve translasyon",
    "Fotosentez ve Kemosentez": "Kloroplast yapısı|Işığa bağımlı reaksiyonlar|Calvin döngüsü|Fotosentez hızını etkileyen faktörler|Kemosentez",
    "Hücresel Solunum": "Glikoliz|Oksijenli solunum (pirüvat oksidasyonu, Krebs, ETS)|Oksijensiz solunum|Fermentasyon",
    "Bitkisel Dokular ve Organlar": "Meristem doku|Temel doku|İletim doku|Örtü doku|Kök, gövde, yaprak kesitleri|Stoma hareketleri|Bitkide madde taşınması",
    "Bitkilerde Büyüme ve Hareket": "Bitkisel hormonlar|Tropizma ve nasti hareketleri|Fotoperiyodizm",
    "Komünite ve Popülasyon Ekolojisi": "Rekabet ve av-avcı ilişkisi|Simbiyotik ilişkiler|Süksesyon|Popülasyon yoğunluğu ve yaş piramitleri|J ve S tipi büyüme eğrileri",
}


MIKRO_ALT_KONULAR = {}
MIKRO_ALT_KONULAR.update(_alt_ayristir(_ALT_TYT))
MIKRO_ALT_KONULAR.update(_alt_ayristir(_ALT_AYT_SAYISAL))


# Yeni bir sınav alanı (ör. 9. sınıf Maarif, EA, Sözel, YDT) eklendiğinde
# aynı desen izlenir:
#   _ALT_DIGER = {...}
#   MIKRO_ALT_KONULAR.update(_alt_ayristir(_ALT_DIGER))
