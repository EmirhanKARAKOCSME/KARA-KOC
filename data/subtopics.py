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


_ALT_MAARIF_11_TARIH = {
    "Osmanlı'da Gerileme ve Değişim": "Gerileme nedenleri|Toprak ve maliye|Toplumsal değişim",
    "Avrupa'daki Gelişmeler ve Osmanlı": "Coğrafi keşifler|Sanayi ve aydınlanma|Osmanlı'ya etkileri",
    "Islahat Hareketleri": "Lale Devri|III. Selim ve II. Mahmud|Islahatların sonuçları",
    "Yenileşme Hareketleri": "Sened-i İttifak|Tanzimat Fermanı|Islahat Fermanı",
    "Tanzimat ve Meşrutiyet": "Tanzimat dönemi|I. Meşrutiyet|II. Meşrutiyet",
    "Osmanlı'da Modernleşme": "Eğitim ve hukuk|Ordu ve ekonomi|Modernleşmenin sonuçları",
}

_ALT_MAARIF_11_FELSEFE = {
    "Çevre Etiği": "Çevre sorunları|İnsan merkezli yaklaşım|Çevre etiği yaklaşımları",
    "İnsan-Doğa İlişkisi": "Doğa kavrayışı|İnsanın doğadaki yeri|Felsefi görüşler",
    "Teknoloji Felsefesi": "Teknoloji kavramı|Teknoloji ve insan|Felsefi yaklaşımlar",
    "Teknolojinin Etik Boyutu": "Etik sorunlar|Mahremiyet|Yapay zekâ ve etik",
    "Akıl-İnanç İlişkisi": "Akıl ve inanç|Uyum ve çatışma|Felsefi görüşler",
    "Bilgi ve İnanç": "Bilgi türleri|İnanç ve gerekçelendirme|Tartışmalar",
    "Edebiyat-Felsefe İlişkisi": "Ortak alanlar|Edebiyatta felsefe|Felsefede edebiyat",
    "Metinlerde Felsefi Temalar": "Tema tespiti|Felsefi kavramlar|Yorumlama",
    "Anlam Arayışı": "Hayatın anlamı|Anlam ve değer|Felsefi yaklaşımlar",
    "Varoluş ve Değerler": "Varoluşçuluk|Değerler|Özgürlük ve sorumluluk",
    "Hukuk Felsefesi": "Hukukun temeli|Doğal hukuk ve pozitif hukuk|Felsefi tartışmalar",
    "Adalet ve Hak": "Adalet türleri|Hak kavramı|Adalet teorileri",
}

_ALT_MAARIF_11_DIN = {
    "Kader ve Kaza": "Kader|Kaza|İnsan iradesi",
    "İrade ve Sorumluluk": "İrade|Sorumluluk|Özgürlük",
    "Din-Felsefe İlişkisi": "Ortak konular|Tarihsel ilişki|Yaklaşımlar",
    "Din-Bilim İlişkisi": "Bilim ve din|Uyum tartışmaları|Örnekler",
    "Din-Sanat İlişkisi": "Sanat ve din|İslam sanatları|Estetik",
    "İslam Medeniyeti": "Medeniyet unsurları|Bilim ve kültür|Katkılar",
    "Gönül Coğrafyası": "Kavram|Kültürel bağlar|Ortak değerler",
    "İnanç Konuları ve Yorumlar": "İnanç esasları|Yorum farklılıkları|Mezhepler",
    "Güncel İnanç Meseleleri": "Güncel sorular|İnanç ve çağ|Değerlendirme",
    "Yahudilik": "Tarih|İnanç esasları|Kutsal metinler",
    "Hristiyanlık": "Tarih|İnanç esasları|Kutsal metinler",
}


_ALT_MAARIF_11_COGRAFYA = {
    "Coğrafyanın Konusu ve Bölümleri": "Coğrafyanın tanımı|Fiziki ve beşerî coğrafya|Alt dallar",
    "Coğrafyada Araştırma Yöntemleri": "Gözlem|Veri toplama|Harita ve analiz",
    "Coğrafi Bilgi Sistemleri": "CBS bileşenleri|Katman mantığı|Uygulamalar",
    "Uzaktan Algılama ve GPS": "Uzaktan algılama|GPS|Uydu görüntüleri",
    "Atmosfer ve İklim Süreçleri": "Atmosfer|İklim elemanları|İklim tipleri",
    "Yer Şekilleri ve Oluşum Süreçleri": "İç kuvvetler|Dış kuvvetler|Yer şekilleri",
    "Su ve Toprak Sistemleri": "Su döngüsü|Toprak oluşumu|Doğal kaynaklar",
    "Nüfus Dinamikleri": "Nüfus artışı|Göç|Nüfus yapısı",
    "Yerleşme ve Şehirleşme": "Yerleşme türleri|Şehirleşme|Kentsel sorunlar",
    "Kültürel ve Siyasi Süreçler": "Kültür bölgeleri|Siyasi coğrafya|Küresel etkileşim",
    "Ekonomik Faaliyet Türleri": "Tarım|Sanayi|Hizmet",
    "Kaynak Kullanımı ve Ekonomi": "Doğal kaynaklar|Sürdürülebilir kullanım|Ekonomik etkiler",
    "Afet Risk Yönetimi": "Afet türleri|Risk analizi|Yönetim aşamaları",
    "Sürdürülebilir Çevre ve Kalkınma": "Çevre sorunları|Sürdürülebilirlik|Kalkınma politikaları",
    "Bölge Türleri ve Sınıflandırma": "Bölge kavramı|Doğal ve beşerî bölgeler|İşlevsel bölgeler",
    "Küresel Bağlantılar ve Ticaret": "Küresel ticaret|Ulaşım ağları|Ekonomik bağlantılar",
}

_ALT_MAARIF_11_TDE = {
    "Metin Türleri ve Anlatım": "Anlatım biçimleri|Metin türleri|Anlatıcı ve bakış açısı",
    "Yazma Becerileri": "Planlama|Yazma süreci|Düzeltme",
    "Konuşma ve Dinleme": "Etkili konuşma|Dinleme becerisi|Topluluk önünde konuşma",
    "Türk Edebiyatında Dönemler": "Dönemler|Temsilciler|Dönem özellikleri",
    "Kültürel Değerler ve Edebiyat": "Kültür-edebiyat ilişkisi|Değerler|Metinlerden örnekler",
    "Metin Çözümleme": "Yapı|Tema|Dil ve anlatım",
    "Hikâye ve Roman İncelemesi": "Yapı unsurları|Karakter ve olay|Anlatım teknikleri",
    "Şiir Çözümlemesi": "Nazım biçimi|Ölçü ve uyak|Söz sanatları",
    "Tema ve Yapı": "Tema belirleme|Yapı çözümleme|Metinler arası karşılaştırma",
    "Tiyatro ve Dramatik Metinler": "Tiyatro türleri|Dramatik yapı|Sahneleme",
    "Eleştiri ve Deneme": "Eleştiri türü|Deneme türü|Düşünce yazıları",
    "Dil Bilgisi Uygulamaları": "Sözcük türleri|Cümle bilgisi|Yazım ve noktalama",
}


_ALT_MAARIF_11_KIMYA = {
    "Fiziksel ve Kimyasal Olaylarda Enerji Değişimleri": "Isı alan-veren olaylar|İç enerji|Enerji dönüşümleri",
    "Tepkime Entalpisi": "Entalpi kavramı|Ekzotermik-endotermik|Oluşum entalpisi",
    "Bağ Enerjisi ve Hess Yasası": "Bağ enerjisi|Hess yasası|Entalpi hesaplamaları",
    "Kimyasal Tepkime Hızı": "Hız tanımı|Hızı etkileyen faktörler|Çarpışma teorisi",
    "Kimyasal Denge": "Dinamik denge|Denge sabiti|Denge hesaplamaları",
    "Dengeye Etki Eden Faktörler": "Le Chatelier ilkesi|Derişim, basınç, sıcaklık|Denge kaymaları",
    "Asit-Baz Dengesi": "Asit-baz tanımları|pH ve pOH|Tampon çözeltiler",
    "Çözünürlük Dengesi": "Çözünürlük çarpımı|Çökelme koşulları|Ortak iyon etkisi",
    "Yeşil Hidrojen": "Yeşil hidrojen üretimi|Enerji depolama|Sürdürülebilirlik",
    "Nanoteknoloji": "Nano ölçek|Nanomalzemeler|Uygulama alanları",
    "Mikroplastik ve Nanoplastikler": "Plastik kirliliği|Mikroplastik|Çevresel etkiler",
}

_ALT_MAARIF_11_BIYO = {
    "Canlıların Uyaranlara Tepkileri": "Uyaran kavramı|Tepki türleri|Canlıda uyum",
    "Bitkisel Hormonlar": "Oksin|Giberellin ve sitokinin|Absisik asit ve etilen",
    "Tropizma ve Nasti": "Tropizma türleri|Nasti hareketleri|Fotoperiyodizm",
    "Reseptörler ve Uyaran Çeşitleri": "Reseptör türleri|Duyu hücreleri|Uyaran dönüşümü",
    "Nöron Yapısı": "Nöron bölümleri|Nöron çeşitleri|Miyelin kılıf",
    "Sinirsel İletim ve Sinaps": "Aksiyon potansiyeli|İmpuls iletimi|Sinaps ve nörotransmitter",
    "Duyu Organları": "Görme|İşitme|Koku, tat ve dokunma",
    "Hayvanlarda Sinir Sistemi Farklılıkları": "Sinir ağları|Gangliyonlu sistem|Merkezî sinir sistemi",
    "İnsan Sinir Sistemi": "Merkezî sinir sistemi|Çevresel sinir sistemi|Beyin bölümleri",
    "Refleks": "Refleks yayı|Doğuştan ve kazanılmış refleks|Refleksin önemi",
    "İskelet, Kas ve Eklemler": "İskelet sistemi|Kas çeşitleri|Eklem türleri",
    "Kasların Kasılma Mekanizması": "Kayan iplikler modeli|Kas kasılması|Enerji kullanımı",
    "Doğal ve Kazanılmış Bağışıklık": "Doğal bağışıklık|Kazanılmış bağışıklık|Aşı ve serum",
    "Alerji": "Alerji mekanizması|Alerjenler|Alerjik tepkiler",
    "Homeostazi": "Homeostazi kavramı|İç denge|Dengeyi sağlayan sistemler",
    "Pozitif ve Negatif Geri Bildirim": "Negatif geri bildirim|Pozitif geri bildirim|Örnekler",
    "Sinir ve Endokrin Sistemin Homeostazideki Rolü": "Sinir sistemi denetimi|Hormonal denetim|İş birliği",
    "Dolaşım, Solunum ve Boşaltım Sistemlerinin Eş Güdümü": "Dolaşım-solunum ilişkisi|Boşaltım ve denge|Sistemler arası koordinasyon",
    "Homeostatik Dengenin Bozulması": "Denge bozuklukları|Hastalık örnekleri|Korunma yolları",
    "Diyabetes Mellitus ve Diyabetes İnsipidus": "Kan şekeri düzenlenmesi|Diyabet türleri|Belirti ve sonuçlar",
    "Kan Basıncı Anormallikleri ve Obezite": "Hipertansiyon|Hipotansiyon|Obezite ve metabolizma",
}


# ==============================================================================
# MAARİF MODELİ 11. SINIF — uygulama içi çalışma kırılımları
# Anahtarlar `data/curriculum_maarif_11.py` mikro konu adlarıyla eşleşir.
# ==============================================================================
_ALT_MAARIF_11_MAT = {
    "İki Nicel Değişkenli Veri Analizi": "İki değişkenli veri tablosu|Dağılımın incelenmesi|İki değişkenin birlikte yorumlanması",
    "Saçılım Diyagramı ve Korelasyon": "Saçılım diyagramı çizimi|Pozitif ve negatif ilişki|Korelasyon katsayısının yorumu",
    "Korelasyon ve Nedensellik Ayrımı": "Korelasyonun anlamı|Nedensellik yanılgısı|Örneklerle ayrım",
    "İstatistiksel Araştırma Sorusu ve Veri Toplama": "Araştırma sorusu oluşturma|Veri toplama yöntemleri|Örneklem ve yanlılık",
    "Dörtgenler ve Özellikleri": "Dörtgen tanımı ve türleri|Açı ve kenar özellikleri|Köşegen özellikleri",
    "Özel Dörtgenler": "Paralelkenar|Dikdörtgen ve kare|Eşkenar dörtgen ve yamuk",
    "Çokgenler": "Çokgen tanımı|İç ve dış açı toplamları|Düzgün çokgenler",
    "Çokgenlerde Açı ve Kenar İlişkileri": "Açı hesaplamaları|Kenar ve köşegen sayısı|Problem çözümü",
    "Trigonometrik Fonksiyonlar": "Birim çember|Sinüs ve kosinüs|Tanjant ve kotanjant",
    "Trigonometrik Fonksiyon Grafikleri": "Periyot ve grafik|Genlik ve öteleme|Grafik yorumlama",
    "Ters Trigonometrik Fonksiyonlar": "Ters fonksiyon kavramı|arcsin, arccos, arctan|Tanım kümeleri",
    "Trigonometrik Özdeşlik ve Denklemler": "Temel özdeşlikler|Toplam-fark formülleri|Trigonometrik denklemler",
    "Üstel Fonksiyonlar": "Üstel fonksiyon tanımı|Grafik ve özellikler|Üstel büyüme ve azalma",
    "Logaritmik Fonksiyonlar": "Logaritma tanımı|Logaritma kuralları|Grafik ve özellikler",
    "Üstel ve Logaritmik Denklemler": "Üstel denklemler|Logaritmik denklemler|Dönüşümler",
    "Logaritma Uygulamaları": "Gerçek yaşam modelleri|Büyüme-azalma problemleri|Logaritmik ölçekler",
    "Bileşke Fonksiyonlar": "Bileşke tanımı|Bileşke hesaplama|Bileşkenin özellikleri",
    "Ters Fonksiyonlar": "Ters fonksiyon tanımı|Ters fonksiyon bulma|Grafik ilişkisi",
    "Fonksiyon Dönüşümleri": "Öteleme|Yansıma|Ölçekleme (genişletme-daraltma)",
    "Fonksiyonlarda Öteleme ve Yansıma": "Yatay ve düşey öteleme|Eksenlere göre yansıma|Dönüşümlerin grafiğe etkisi",
}

_ALT_MAARIF_11_FIZIK = {
    "Vektörler ve Denge": "Vektör bileşenleri|Bileşke vektör|Denge koşulları",
    "Newton'un Hareket Yasaları": "Eylemsizlik|F=ma|Etki-tepki",
    "Bir Boyutta Sabit İvmeli Hareket": "Konum-hız-ivme|Hareket denklemleri|Grafikler",
    "İki Boyutta Hareket ve Atışlar": "Yatay atış|Eğik atış|Bileşenlere ayırma",
    "İş, Enerji ve Güç": "İş kavramı|Kinetik ve potansiyel enerji|Enerji korunumu ve güç",
    "İtme ve Momentum": "İtme|Momentum korunumu|Çarpışmalar",
    "Elektrik Yükü ve Elektriksel Kuvvet": "Yük çeşitleri|Coulomb yasası|Elektriklenme",
    "Elektrik Alan ve Elektriksel Potansiyel": "Elektrik alan|Potansiyel fark|Eş potansiyel yüzeyler",
    "Sığaçlar": "Sığa kavramı|Paralel levhalı sığaç|Enerji depolama",
    "Akım, Direnç ve Elektrik Devreleri": "Ohm yasası|Seri-paralel devreler|Elektriksel güç",
    "Manyetik Alan ve Manyetik Kuvvet": "Manyetik alan|Akımın manyetik etkisi|Manyetik kuvvet",
    "Elektromanyetik İndüksiyon": "İndüksiyon|Lenz yasası|Alternatif akım",
    "Işığın Yansıması ve Aynalar": "Yansıma yasaları|Düzlem ayna|Küresel aynalar",
    "Işığın Kırılması ve Mercekler": "Kırılma|İnce mercekler|Görüntü oluşumu",
    "Prizmalar ve Renk": "Prizmada kırılma|Renk ayrışması|Işık renkleri",
    "Optik Araçlar ve Göz": "Gözün yapısı|Optik araçlar|Görme kusurları",
}


# ==============================================================================
# KLASİK YKS — YDT (Dil) İngilizce mikro konuları
# Anahtarlar `mufredat_klasik["YDT (Dil)"]` konu adlarıyla birebir eşleşir.
# ==============================================================================
_ALT_YDT = {
    "Vocabulary & Collocations": "Word families|Synonyms and antonyms|Phrasal verbs|Collocations|Contextual vocabulary",
    "Tenses & Modals": "Present and past tenses|Perfect tenses|Future forms|Modal verbs|Tense consistency",
    "Clauses & Conjunctions": "Noun clauses|Relative clauses|Adverbial clauses|Conjunctions and transitions|Sentence structure",
    "Cloze Test & Cümle Tamamlama": "Contextual grammar|Vocabulary in context|Connectors|Paragraph coherence|Sentence completion strategies",
    "İngilizce-Türkçe Çeviri": "Subject-verb consistency|Tense and aspect transfer|Clause structure|Idiomatic expressions|Meaning-preserving translation",
    "Paragraf Okuma ve Anlama": "Main idea|Supporting details|Inference|Reference words|Paragraph organization",
    "Diyalog & Anlamı Bozan Cümle": "Dialogue completion|Appropriate response|Context and tone|Irrelevant sentence detection|Paragraph coherence",
}


# ==============================================================================
# KLASİK YKS — AYT SÖZEL mikro konuları
# Anahtarlar `mufredat_klasik["AYT"]["Sözel"]` konu adlarıyla eşleşir.
# ==============================================================================
_ALT_SOZEL = {
    "Edebi Sanatlar": "Teşbih ve istiare|Mecazımürsel ve kinaye|Tezat ve mübalağa|Hüsnütalil ve tecahülüarif|Metin üzerinden sanat tespiti",
    "Divan Edebiyatı": "Divan şiirinin özellikleri|Nazım biçimleri|Nazım türleri|Aruz ölçüsü|Önemli sanatçılar ve eserler",
    "Halk Edebiyatı": "Anonim halk edebiyatı|Âşık edebiyatı|Tekke ve tasavvuf edebiyatı|Nazım biçimleri ve türleri|Halk edebiyatı sanatçıları",
    "Cumhuriyet Dönemi": "Cumhuriyet dönemi şiir anlayışları|Roman ve hikâye|Tiyatro|Edebî topluluklar|Sanatçı ve eser ilişkileri",
    "İlk Uygarlıklar": "Mezopotamya uygarlıkları|Mısır uygarlığı|Anadolu uygarlıkları|Doğu Akdeniz uygarlıkları|İlk Çağ siyasi ve kültürel yapıları",
    "Osmanlı Merkez Teşkilatı": "Padişah ve saray|Divan-ı Hümayun|Yönetim görevlileri|Merkezî bürokrasi|Osmanlı yönetim sisteminin işleyişi",
    "İki Savaş Arası Dönem": "I. Dünya Savaşı sonrası düzen|Barış antlaşmaları|Dünya ekonomik krizi|Otoriter rejimlerin yükselişi|II. Dünya Savaşı'na giden gelişmeler",
    "Soğuk Savaş ve XXI. Yüzyıl": "İki kutuplu dünya|NATO ve Varşova Paktı|Soğuk Savaş krizleri|Soğuk Savaş'ın sona ermesi|XXI. yüzyılın siyasi gelişmeleri",
    "Türkiye'nin İklimi ve Yeryüzü Şekilleri": "Türkiye'nin iklim tipleri|İklim elemanlarının dağılışı|Dağ ve ova sistemleri|Akarsu ve göller|Yer şekillerinin ekonomik etkileri",
    "Küresel Örgütler ve Afetler": "Uluslararası kuruluşlar|Birleşmiş Milletler ve bağlı kuruluşlar|Küresel çevre anlaşmaları|Afet riskleri|Uluslararası afet iş birliği",
    "Felsefi Düşünce": "Felsefenin doğuşu|Felsefi soru ve problemler|Felsefi akıl yürütme|Felsefi görüşlerin karşılaştırılması|Bilgi, varlık ve değer ilişkisi",
    "Klasik Mantık ve Mantık-Dil": "Kavram ve terimler|Tanım ve sınıflandırma|Önerme ve yargı|Akıl yürütme biçimleri|Dil ve mantık ilişkisi",
    "Sembolik Mantık": "Önermeler mantığı|Mantıksal bağlaçlar|Sembolleştirme|Doğruluk tabloları|Geçerlilik ve çıkarım",
    "Psikolojinin Temel Süreçleri": "Psikolojinin konusu ve yöntemleri|Duyum ve algı|Dikkat ve bellek|Öğrenme|Duygu ve motivasyon",
    "Öğrenme ve Bellek": "Öğrenme türleri|Koşullanma|Bilişsel öğrenme|Bellek süreçleri|Unutma ve hatırlama",
    "Sosyolojiye Giriş ve Toplumsal Yapı": "Sosyolojinin konusu|Toplum ve kültür|Sosyalleşme|Toplumsal kurumlar|Toplumsal değişme",
    "Allah İnsan İlişkisi": "Allah inancı|İnsan ve yaratılış|İrade ve sorumluluk|Dua ve ibadet|İnsan ve Allah ilişkisi",
    "Kur'an Kavramları": "Kur'an'ın temel kavramları|Ayet ve sure|Kur'an'ın ana konuları|Kur'an'dan mesajlar|Kavramları bağlam içinde yorumlama",
    "İslam Düşüncesinde Tasavvufi Yorumlar": "Tasavvufun ortaya çıkışı|Tasavvufi düşüncenin temel kavramları|Tasavvufi yorum gelenekleri|Önemli düşünürler|Tasavvufi yorumların kültüre etkisi",
}


# ==============================================================================
# KLASİK YKS — AYT EŞİT AĞIRLIK mikro konuları
# Anahtarlar `mufredat_klasik["AYT"]["Eşit Ağırlık"]` konu adlarıyla birebir
# eşleşir. Mevcut TYT / AYT Sayısal eşleşmeleri korunur (additive merge).
# ==============================================================================
_ALT_EA = {
    "Polinomlar ve Parabol": "Polinom kavramı|Polinomlarda derece ve katsayı|Polinomlarda işlemler|Parabolün denklemi ve grafiği|Parabolün tepe noktası ve kesişimler",
    "İkinci Dereceden Eşitsizlikler": "İkinci dereceden eşitsizlikler|Köklerin işaret incelemesi|Parabol yardımıyla çözüm|İşaret tablosu|Eşitsizlik sistemleri",
    "Trigonometri": "Yönlü açılar|Birim çember|Trigonometrik oranlar|Trigonometrik özdeşlikler|Trigonometrik denklemler",
    "Logaritma ve Diziler": "Logaritma tanımı ve özellikleri|Üstel-logaritmik dönüşümler|Aritmetik diziler|Geometrik diziler|Dizi problemleri",
    "Limit, Türev ve İntegral": "Limit kavramı|Süreklilik|Türev ve türev alma|Türevin grafiksel yorumu|Belirli integral ve alan",
    "Çemberde Açı ve Uzunluk": "Merkez ve çevre açı|Teğet-kiriş ilişkileri|Çemberde yay uzunluğu|Kiriş uzunluğu|Daire alanı ve çevresi",
    "Analitik Geometri": "Noktanın koordinat düzleminde gösterimi|İki nokta arası uzaklık|Doğru denklemi|Doğruların konumları|Çemberin analitik denklemi",
    "Katı Cisimler": "Prizma ve küp|Silindir|Koni|Piramit|Küre ve hacim-alan problemleri",
    "Şiir Bilgisi ve Edebi Sanatlar": "Nazım biçimleri|Nazım türleri|Ölçü ve uyak|Söz sanatları|Şiir çözümleme",
    "İslamiyet Öncesi ve Geçiş Dönemi Türk Edebiyatı": "Sözlü edebiyat ürünleri|Yazılı edebiyat ürünleri|Orhun Yazıtları|Geçiş dönemi eserleri|Dönemlerin dil ve kültür özellikleri",
    "Halk Edebiyatı": "Anonim halk edebiyatı|Âşık edebiyatı|Tekke ve tasavvuf edebiyatı|Nazım biçimleri ve türleri|Halk edebiyatı sanatçıları",
    "Divan Edebiyatı": "Divan şiirinin özellikleri|Nazım biçimleri|Nazım türleri|Aruz ölçüsü|Önemli sanatçılar ve eserler",
    "Tanzimat ve Servet-i Fünun Edebiyatı": "Tanzimat birinci dönem|Tanzimat ikinci dönem|Servet-i Fünun sanatçıları|Edebî türlerde yenilikler|Dönemlerin karşılaştırılması",
    "Milli Edebiyat Dönemi": "Milli edebiyatın ortaya çıkışı|Dil ve sadeleşme|Şiir ve roman anlayışı|Önemli sanatçılar|Eser ve sanatçı eşleştirmeleri",
    "Cumhuriyet Dönemi Edebiyatı": "Cumhuriyet şiiri|Cumhuriyet romanı ve hikâyesi|Tiyatro ve öğretici metinler|Edebî topluluklar ve anlayışlar|Sanatçı ve eser eşleştirmeleri",
    "İlk Türk Devletleri ve İslam Medeniyeti": "İlk Türk devletlerinin yönetimi|Türklerde sosyal ve ekonomik hayat|İslamiyet'in doğuşu|İslam medeniyetinin gelişimi|Türklerin İslamiyet'i kabulü",
    "Beylikten Devlete Osmanlı": "Osmanlı Beyliği'nin kuruluşu|Beylikten devlete geçiş|Osmanlı'nın Balkanlara yayılması|Kurumsallaşma|Erken Osmanlı devlet yapısı",
    "Dünya Gücü Osmanlı": "İstanbul'un fethi|Osmanlı'nın siyasi genişlemesi|Merkezî yönetim|Askerî teşkilat|Osmanlı'nın dünya siyasetindeki konumu",
    "XX. Yüzyıl Başlarında Osmanlı": "Trablusgarp Savaşı|Balkan Savaşları|I. Dünya Savaşı|Cepheler ve sonuçlar|Mondros Ateşkes Antlaşması",
    "Milli Mücadele Dönemi": "Mondros sonrası işgaller|Kongreler ve genelgeler|TBMM'nin açılması|Kurtuluş Savaşı cepheleri|Lozan Antlaşması",
    "Atatürk İlkeleri ve İnkılapları": "Cumhuriyetçilik|Milliyetçilik ve halkçılık|Devletçilik|Laiklik ve inkılapçılık|Siyasi, hukuki ve toplumsal inkılaplar",
    "Ekosistem ve Biyoçeşitlilik": "Ekosistem bileşenleri|Besin zinciri ve enerji akışı|Biyoçeşitliliğin dağılışı|Ekosistem dengesi|Biyolojik çeşitliliğin korunması",
    "Türkiye Ekonomisi ve Bölgeler": "Türkiye'de tarım|Sanayi faaliyetleri|Enerji ve madencilik|Hizmet sektörü|Ekonomik bölgeler",
    "Küresel Ticaret ve Çevre": "Uluslararası ticaret|Ticaret yolları ve limanlar|Küresel ekonomik ağlar|Çevre sorunları|Sürdürülebilir kalkınma",
}


_ALT_MAARIF_COGRAFYA = {
    "Coğrafya Biliminin Konusu ve Gelişimi": "Coğrafyanın tanımı|Fiziki coğrafya|Beşerî ve ekonomik coğrafya|Coğrafyanın araştırma yöntemleri|Coğrafyanın günlük yaşamdaki önemi",
    "Haritalar ve Türkiye'nin Konumu": "Harita unsurları|Ölçek ve uzaklık|Coğrafi koordinatlar|Türkiye'nin matematik konumu|Türkiye'nin özel konumu",
    "Mekânsal Bilgi Teknolojileri Bileşenleri": "Coğrafi bilgi sistemleri|Uzaktan algılama|GPS ve konum teknolojileri|Uydu görüntüleri|Mekânsal verilerin yorumlanması",
    "Hava Olayları ve İklim Sistemleri": "Hava durumu ve iklim|Atmosfer ve katmanları|Sıcaklık ve basınç|Rüzgâr ve yağış|İklim elemanları",
    "İklim Değişiklikleri": "Küresel iklim değişikliği|Sera etkisi|İklim değişikliğinin nedenleri|Ekosistem ve insan üzerindeki sonuçlar|Azaltım ve uyum stratejileri",
    "Nüfusun Tarihsel Değişimi ve Dağılışı": "Nüfusun tarihsel gelişimi|Nüfus dağılışını etkileyen faktörler|Nüfus yoğunluğu|Kentsel ve kırsal nüfus|Nüfus politikaları",
    "Demografik Dönüşüm ve Piramitler": "Doğum ve ölüm oranları|Doğal nüfus artışı|Demografik geçiş|Nüfus piramitleri|Yaş ve cinsiyet yapısı",
    "Ekonomik Faaliyetleri Etkileyen Coğrafi Faktörler": "Doğal kaynaklar|İklim ve yer şekilleri|Beşerî sermaye|Ulaşım ve pazar koşulları|Ekonomik faaliyetlerin mekânsal dağılışı",
    "Afet Türleri ve Bütüncül Afet Yönetimi": "Doğal ve beşerî afetler|Deprem, sel ve heyelan|Risk ve zarar azaltma|Afet öncesi hazırlık|Afet sonrası müdahale ve iyileştirme",
    "Bölge ve Bölge Sınırı Kavramı": "Bölge kavramı|Doğal ve beşerî bölgeler|Bölge sınırlarının belirlenmesi|İşlevsel bölgeler|Bölgesel sınıflandırmalar",
}

_ALT_MAARIF_DIN = {
    "İnsanın Yaratılışı, İbadet ve Dua": "Yaratılış kavramı|İnsan ve sorumluluk|İbadetin anlamı|Dua ve niyaz|İbadetin bireysel ve toplumsal etkileri",
    "İman Esasları ve Toplumsal Boyutu": "Allah'a iman|Meleklere, kitaplara ve peygamberlere iman|Ahiret inancı|Kader ve kaza|İman ve toplumsal sorumluluk",
    "Temel İbadetler ve İnsan": "İbadet kavramı|Namaz, oruç ve zekât|Hac ve kurban|İbadetin ahlaki boyutu|İbadet ve toplumsal dayanışma",
    "Ahlakın Temel Unsurları ve Tutumlar": "Ahlak kavramı|Doğruluk ve adalet|Sorumluluk ve saygı|Yardımlaşma|Ahlaki davranışın toplumsal etkileri",
    "Hz. Muhammed'in Örnekliği ve Peygamberliği": "Peygamberlik kavramı|Hz. Muhammed'in örnek ahlakı|Güvenilirlik ve doğruluk|Tebliğ ve rehberlik|Günlük yaşamda örnekliği",
}


_ALT_MAARIF_TDE = {
    "Edebiyatın Sanat ve Bilimle İlişkisi": "Edebiyatın tanımı ve işlevi|Edebiyatın güzel sanatlarla ilişkisi|Edebiyat ve bilim|Edebiyat ve toplum|Edebî metinlerin özellikleri",
    "İletişim Öğeleri ve Göstergeler": "Gönderici ve alıcı|İleti, kanal ve bağlam|Dönüt ve iletişim engelleri|Gösterge ve gösteren-gösterilen|Günlük iletişim örnekleri",
    "Dilin İşlevleri ve Kullanım Türleri": "Dilin göndergesel işlevi|Heyecana bağlı ve alıcıyı harekete geçiren işlevler|Şiirsel, kanalı kontrol ve dil ötesi işlevler|Dil türleri ve kullanım alanları|Dilin bağlama göre değişimi",
    "Hikaye Türleri ve Gelişimi": "Hikâyenin yapı unsurları|Olay ve durum hikâyesi|Anlatıcı ve bakış açısı|Hikâyenin tarihsel gelişimi|Hikâye türlerini metin üzerinden inceleme",
    "Yazım ve Noktalama": "Büyük harflerin kullanımı|Birleşik ve ayrı yazılan kelimeler|Sayıların yazımı|Noktalama işaretleri|Yazım yanlışlarının tespiti",
    "Şiir Bilgisi ve Türleri": "Şiirin yapı unsurları|Nazım birimi ve nazım biçimi|Ölçü ve uyak|Kafiye ve redif|Lirik, epik, didaktik ve diğer şiir türleri",
    "Masal ve Fabl Özellikleri": "Masalın yapı ve anlatım özellikleri|Olağanüstü unsurlar|Fablın özellikleri|Kişileştirme ve konuşturma|Masal ve fablın karşılaştırılması",
    "Edat, Bağlaç, Ünlem": "Edatların görevleri|Bağlaçların görevleri|Ünlemlerin kullanım alanları|Sözcük türlerini ayırt etme|Cümlede anlam ve görev ilişkisi",
    "Roman Türleri ve Yapı Unsurları": "Romanın yapı unsurları|Olay örgüsü ve tema|Anlatıcı ve bakış açısı|Roman türleri|Türk ve dünya romanının gelişimi",
    "Tiyatro Terimleri ve Geleneksel Türk Tiyatrosu": "Tiyatro metninin temel unsurları|Perde ve sahne|Geleneksel Türk tiyatrosu|Karagöz ve Hacivat|Orta oyunu ve meddah",
    "Biyografi ve Otobiyografi": "Biyografinin özellikleri|Otobiyografinin özellikleri|Anlatım ve zaman kullanımı|Belge ve bilgi doğrulama|Biyografi ve otobiyografi karşılaştırması",
    "CV, Dilekçe ve Tutanak": "CV hazırlama|Dilekçe yazım kuralları|Tutanak oluşturma|Resmî yazışma dili|Biçim ve içerik kontrolü",
    "Fiiller": "Fiil kavramı|Fiilde anlam ve zaman|Kip ve kişi ekleri|Haber ve dilek kipleri|Fiil çekimleri",
    "Mektup Türleri ve E-Posta": "Özel ve resmî mektup|Mektup bölümleri|E-posta yazım kuralları|Hitap ve iletişim dili|Dijital iletişim etiği",
    "Günlük ve Blog": "Günlük türünün özellikleri|Blog türünün özellikleri|Kişisel anlatım|Dijital içerik oluşturma|Günlük, blog ve anı türlerini karşılaştırma",
}

_ALT_MAARIF_TARIH = {
    "Tarih Öğrenmenin Faydaları ve Doğası": "Tarihin konusu|Geçmiş ve tarihsel bilgi|Tarih biliminin yöntemleri|Tarih bilmenin birey ve toplum için faydaları|Tarihsel bakış açısı",
    "Tarihsel Bilgi Üretimi ve Dijitalleşme": "Tarihsel kaynakların sınıflandırılması|Birincil ve ikincil kaynaklar|Tarih araştırmasının aşamaları|Dijital arşivler|Dijital tarih ve doğrulama",
    "Tarım Devriminin Yerleşmeye Etkisi": "Avcı-toplayıcı yaşam|Tarıma geçiş|Yerleşik yaşama geçiş|İlk köyler ve üretim|Nüfus ve toplumsal yapı değişimi",
    "Eski Çağda Yönetim, Hukuk ve İnançlar": "İlk devletlerde yönetim|Krallık ve imparatorluk yapıları|Hukuk sistemleri|Çok tanrılı ve tek tanrılı inançlar|Din ve devlet ilişkisi",
    "Türklerde Konargöçer Yaşam": "Orta Asya coğrafyası|Konargöçer yaşam biçimi|Hayvancılık ve ekonomi|Boy ve devlet teşkilatı|Türk kültürünün temel özellikleri",
    "Orta Çağ Göçleri ve Devlet Yapıları": "Kavimler Göçü|Göçlerin siyasi sonuçları|Feodalite|Orta Çağ devlet yapıları|Toplumsal değişimler",
    "Orta Çağ Ticaret Yolları ve Bilim Havzaları": "İpek Yolu|Baharat Yolu|Ticaretin siyasi ve ekonomik etkileri|İslam dünyasında bilim|Orta Çağ bilim havzaları",
}


_ALT_MAARIF_FIZIK = {
    "Fizik Bilimi ve Alt Dalları": "Mekanik ve hareket|Elektromanyetizma|Optik|Termodinamik|Modern fizik ve uygulama alanları",
    "Fizik Bilimine Yön Verenler ve Kariyer Keşfi": "Fizik tarihindeki önemli bilim insanları|Bilimsel keşiflerin gelişimi|Fizik ve teknoloji ilişkisi|Fizik alanındaki meslekler|Güncel bilimsel çalışmalar",
    "Temel ve Türetilmiş Nicelikler": "Temel fiziksel nicelikler|SI birim sistemi|Türetilmiş nicelikler|Birim dönüşümleri|Boyut analizi",
    "Skaler ve Vektörel Nicelikler": "Skaler nicelikler|Vektörel nicelikler|Vektörlerin yön ve büyüklüğü|Vektörlerde toplama ve çıkarma|Vektörlerin bileşenlerine ayırılması",
    "Doğadaki Temel Kuvvetler ve Hareket Türleri": "Kütle çekim kuvveti|Elektromanyetik kuvvet|Güçlü ve zayıf nükleer kuvvet|Öteleme, dönme ve titreşim hareketleri|Doğadaki hareket örnekleri",
    "Basınç ve Sıvılarda Basınç": "Katılarda basınç|Sıvı basıncı|Derinlik ve yoğunluk ilişkisi|Pascal ilkesi|Basıncın günlük yaşam uygulamaları",
    "Açık Hava Basıncı ve Kaldırma Kuvveti": "Atmosfer basıncı|Barometre ve basınç ölçümü|Sıvılarda kaldırma kuvveti|Arşimet ilkesi|Yüzme, batma ve askıda kalma",
    "Bernoulli İlkesi": "Akışkanlarda basınç ve hız|Bernoulli ilkesi|Kesit alanı ve akış hızı|Venturi etkisi|Uçuş ve akışkan uygulamaları",
    "Enerji, Isı, Öz Isı ve Sıcaklık İlişkisi": "İç enerji ve ısı|Sıcaklık kavramı|Öz ısı|Isı alışverişi|Isı ve sıcaklık hesaplamaları",
    "Hâl Değişimi ve Isıl Denge": "Erime ve donma|Buharlaşma ve yoğuşma|Süblimleşme|Hâl değişim ısısı|Isıl denge ve enerji aktarımı",
    "Isı Aktarım Yolları ve İletim Hızı": "İletim|Taşınım|Işıma|Isı yalıtımı|Isı iletim hızını etkileyen faktörler",
}

_ALT_MAARIF_BIYO = {
    "Biyolojinin Önemi ve Bilim Etiği": "Biyolojinin çalışma alanları|Bilimsel yöntem ve gözlem|Hipotez ve deney|Bilim etiği|Biyolojinin toplumsal ve teknolojik etkileri",
    "Sınıflandırma ve Biyoçeşitlilik (3 Domain)": "Sınıflandırmanın amacı|Taksonomik basamaklar|Canlıların akrabalık ilişkileri|Bakteri, Arke ve Ökarya domainleri|Biyoçeşitlilik ve korunması",
    "İnorganik Moleküller (Su ve Mineraller)": "Suyun canlılar için önemi|Suyun çözücü özellikleri|Mineraller ve görevleri|Elektrolit dengesi|Su ve mineral eksikliğinin sonuçları",
    "Organik Moleküller (Karbonhidrat, Yağ, Protein, Nükleik Asit, Vitamin)": "Karbonhidratlar ve görevleri|Yağlar ve görevleri|Proteinlerin yapısı ve işlevleri|Nükleik asitler|Vitaminler ve enzimlerle ilişkili temel kavramlar",
    "Hücre Yapısı, Organeller ve Çekirdek": "Prokaryot ve ökaryot hücreler|Hücre zarı ve sitoplazma|Organellerin görevleri|Çekirdek ve genetik materyal|Bitki ve hayvan hücrelerinin karşılaştırılması",
    "Hücreden Organ ve Sistem Organizasyonuna": "Hücre ve doku|Doku çeşitleri|Organ oluşumu|Sistemlerin temel organizasyonu|Organizma düzeyinde bütünlük",
}


# ==============================================================================
# MAARİF MODELİ 9/10 SINIF — uygulama içi çalışma kırılımları
# Anahtarlar `data/curriculum.py::mufredat_maarif_9` konu adlarıyla birebir
# eşleşir. Bunlar MEB'in resmî alt başlık listesi değil, öğrenme çıktılarından
# hareketle üretilmiş çalışma kırılımlarıdır.
# ==============================================================================
_ALT_MAARIF_MAT = {
    "Gerçek Sayıların Üslü ve Köklü Gösterimleri": "Tam sayı ve rasyonel sayı üsleri|Üslü ifadelerin temel işlem kuralları|Kök içi ve kök dışı ifadeler|Köklü ifadelerde sadeleştirme ve işlemler|Üslü ve köklü ifadeler arasında dönüşüm",
    "Gerçek Sayı Aralıkları ile İşlemler": "Açık, kapalı ve yarı açık aralıklar|Aralıkların sayı doğrusunda gösterimi|Aralıkların birleşimi ve kesişimi|Aralıklarla eşitsizlik gösterimi|Aralıklarla işlem ve karşılaştırma",
    "Sayı Kümeleri ve İşlem Özellikleri": "Doğal, tam, rasyonel ve irrasyonel sayılar|Gerçek sayı kümesi ve alt kümeleri|Toplama ve çarpmanın temel özellikleri|Birim, ters eleman ve işlem önceliği|Sayı kümelerinde sıralama ve işlemler",
    "İki Kare Farkı ve Tamkare Özdeşlikleri": "İki kare farkı özdeşliği|Tam kare açılımı|İki kare farkı ile çarpanlara ayırma|Özdeşliklerin sadeleştirme işlemlerinde kullanılması|Özdeşliklerle denklem çözümüne hazırlık",
    "Gerçek Sayılarda Tanımlı Doğrusal Fonksiyonlar ve Mutlak Değer": "Doğrusal fonksiyonun tanımı|Eğimin ve eksenleri kesme noktalarının bulunması|Doğrusal fonksiyon grafikleri|Mutlak değer fonksiyonu ve grafiği|Fonksiyonlarda öteleme ve yansıma",
    "Fonksiyonların Nitel Özellikleri": "Tanım ve görüntü kümesi|Fonksiyonun sıfırları|Artan ve azalan fonksiyonlar|Maksimum ve minimum değerler|Grafik üzerinden fonksiyon yorumlama",
    "Doğrusal Fonksiyonlarla İfade Edilen Denklem ve Eşitsizlikler": "Doğrusal denklem kurma|Birinci dereceden denklem çözümü|Birinci dereceden eşitsizlikler|Eşitsizlik çözüm kümelerinin gösterimi|Doğrusal modellerle gerçek yaşam problemleri",
    "Algoritma Temelli Problemler": "Problem çözme adımlarını belirleme|Sözde kod oluşturma|Akış şemaları|Koşullu ifadeler ve döngüler|Girdi, işlem ve çıktı ilişkisi",
    "Mantık Bağlaçları ve Niceleyiciler": "Önermeler ve doğruluk değerleri|Ve, veya, ya da bağlaçları|Koşullu ve çift koşullu önermeler|Doğruluk tabloları|Evrensel ve varlıksal niceleyiciler",
    "Üçgende Açı ve Kenar Özellikleri": "Üçgenin temel elemanları|İç ve dış açılar|Üçgende açıların toplamı|Kenar uzunluğu ve karşı açı ilişkisi|Üçgen eşitsizliği",
    "Üçgende Açı İlişkileri": "İç açılar ve dış açılar|Dış açı teoremi|Paralel doğrular ve üçgen açıları|İkizkenar üçgende açı ilişkileri|Eşkenar üçgende açı özellikleri",
    "Üçgende Kenar İlişkileri": "Üçgen eşitsizliği|Kenar uzunluklarının karşılaştırılması|Büyük açı ve büyük kenar ilişkisi|Üçgende yardımcı çizimler|Kenar uzunluğu bulma problemleri",
    "Geometrik Şekillerin Dönüşümleri (Yansıma, Öteleme, Dönme)": "Nokta ve şekillerin yansıması|Öteleme vektörü|Dönme merkezi ve dönme açısı|Dönüşümde uzunluk ve açı korunumu|Birleşik geometrik dönüşümler",
    "Üçgenlerde Eşlik ve Benzerlik Koşulları": "Üçgenlerde eşlik koşulları|Açı-kenar ilişkileri|Benzerlik koşulları|Benzerlik oranı|Benzer üçgenlerle uzunluk ve alan problemleri",
    "Tek Nicel Değişken İçeren İstatistiksel Problem Oluşturma": "Anakütle ve örneklem|Nicel değişken belirleme|Araştırma sorusu oluşturma|Veri toplama yöntemleri|Örneklem yanlılığı ve araştırma tasarımı",
    "Verileri Toplama ve Analize Hazırlama": "Veri türleri|Veri toplama ve sınıflandırma|Frekans tabloları|Aritmetik ortalama, ortanca ve tepe değer|Verilerin grafiklerle gösterimi",
    "Bulgulara Ulaşma ve Yorumlama": "Veri dağılımlarını inceleme|Merkezi eğilim ölçüleri|Dağılım ve değişkenlik|İki veri grubunu karşılaştırma|İstatistiksel sonuçlardan çıkarım yapma",
    "İstatistiksel Görsel ve Çıkarımları Değerlendirme": "Grafik türünü amaca göre seçme|Grafiklerde eksen ve ölçek okuma|Yanıltıcı grafiklerin tespiti|Görsel verilerden çıkarım|Korelasyon ve nedensellik farkı",
}

_ALT_MAARIF_KIMYA = {
    "Günlük Hayatta Kimya ve Güvenlik": "Kimyasalların günlük yaşamda kullanımı|Kimyasal tehlike sembolleri|Laboratuvar güvenliği ve koruyucu ekipman|Kimyasal atıkların yönetimi|Kimyasal maddelerin güvenli saklanması",
    "Kimyanın Alt Disiplinleri ve Kariyer": "Analitik kimya|Organik ve anorganik kimya|Fizikokimya ve biyokimya|Kimyanın endüstride kullanımı|Kimya alanındaki meslekler",
    "Atom Teorileri ve Elektron Dizilimi": "Dalton, Thomson ve Rutherford atom modelleri|Bohr atom modeli|Modern atom teorisi|Orbitaller ve kuantum sayıları|Elektron dizilimi ve orbital yerleşimi",
    "Periyodik Tablo ve Periyodik Özellikler": "Grup ve periyot kavramları|Atom yarıçapı|İyonlaşma enerjisi|Elektronegatiflik|Metalik ve ametalik özellikler",
    "Kimyasal Bağlar (Metalik, İyonik, Kovalent)": "İyonik bağ oluşumu|Kovalent bağ oluşumu|Metalik bağ|Bağ yapısı ve kararlılık|Bağ türlerinin özelliklerle ilişkisi",
    "Lewis Nokta Yapısı ve Polarlık": "Değerlik elektronları|Lewis elektron nokta yapıları|Oktet ve dublet kuralı|Molekül geometrisi|Molekül polarlığı ve bağ polarlığı",
    "Moleküller Arası Etkileşimler": "London kuvvetleri|Dipol-dipol etkileşimleri|Hidrojen bağı|Moleküller arası etkileşimlerin karşılaştırılması|Etkileşimlerin fiziksel özelliklere etkisi",
    "Katılar, Sıvılar ve Özellikleri": "Kristal ve amorf katılar|Katılarda yapı ve düzen|Sıvılarda viskozite|Yüzey gerilimi|Buhar basıncı ve sıvıların özellikleri",
    "Nanoparçacıklar ve Ekolojik Sürdürülebilirlik": "Nanoteknoloji ve nano ölçek|Nanoparçacıkların özellikleri|Nanoteknolojik uygulamalar|Nanoparçacıkların çevresel etkileri|Sürdürülebilir üretim ve kullanım",
    "Yeşil Kimyanın Atık Önleme İlkesi": "Atık oluşumunu önleme|Atom ekonomisi|Güvenli çözücü kullanımı|Enerji tasarruflu kimyasal süreçler|Çevreye duyarlı üretim",
}


MIKRO_ALT_KONULAR = {}
MIKRO_ALT_KONULAR.update(_alt_ayristir(_ALT_TYT))
MIKRO_ALT_KONULAR.update(_alt_ayristir(_ALT_AYT_SAYISAL))


def _ek_konulari_birlestir(hedef, ham):
    """Mevcut anahtarları KORUYARAK yeni mikro konuları ekler.

    Var olan bir mikro konu tekrar tanımlanırsa **ilk (mevcut) tanım korunur**;
    böylece klasik TYT / AYT Sayısal eşleşmeleri değişmez. Yalnızca yeni
    anahtarlar eklenir (Maarif 9/10/11, EA, Sözel, YDT).
    """
    for anahtar, deger in _alt_ayristir(ham).items():
        if anahtar not in hedef:
            hedef[anahtar] = deger


_EK_KATALOGLAR = (
    _ALT_MAARIF_MAT,
    _ALT_MAARIF_KIMYA,
    _ALT_MAARIF_FIZIK,
    _ALT_MAARIF_BIYO,
    _ALT_MAARIF_TDE,
    _ALT_MAARIF_TARIH,
    _ALT_MAARIF_COGRAFYA,
    _ALT_MAARIF_DIN,
    _ALT_EA,
    _ALT_SOZEL,
    _ALT_YDT,
    _ALT_MAARIF_11_MAT,
    _ALT_MAARIF_11_FIZIK,
    _ALT_MAARIF_11_KIMYA,
    _ALT_MAARIF_11_BIYO,
    _ALT_MAARIF_11_COGRAFYA,
    _ALT_MAARIF_11_TDE,
    _ALT_MAARIF_11_TARIH,
    _ALT_MAARIF_11_FELSEFE,
    _ALT_MAARIF_11_DIN,
)
for _katalog in _EK_KATALOGLAR:
    _ek_konulari_birlestir(MIKRO_ALT_KONULAR, _katalog)


# Yeni bir sınav alanı (ör. 9. sınıf Maarif, EA, Sözel, YDT) eklendiğinde
# aynı desen izlenir:

