"""Türkiye Yüzyılı Maarif Modeli — 11. sınıf müfredatı.

9/10. sınıf (`mufredat_maarif_9`) ve klasik YKS (`mufredat_klasik`)
verilerinden **ayrı** tutulur. 2026–2027'de Maarif Modeli 11. sınıflarda
uygulanacağı için sınıf seviyesine göre seçilebilen bağımsız bir havuz gerekir.

Yapı: `ders -> ünite/tema -> [mikro konular]`

- Ünite/tema adları MEB çerçeve planlarındaki başlıklara dayanır.
- Mikro konular MEB'in resmî alt başlık listesi DEĞİL, uygulama içi öğrenme
  kırılımlarıdır.
- Bu havuz klasik AYT müfredatıyla aynı değildir; ayrı değerlendirilir.
"""


mufredat_maarif_11 = {
    "Matematik ve Veri": {
        "İstatistiksel Araştırma Süreci": [
            "İki Nicel Değişkenli Veri Analizi",
            "Saçılım Diyagramı ve Korelasyon",
            "Korelasyon ve Nedensellik Ayrımı",
            "İstatistiksel Araştırma Sorusu ve Veri Toplama",
        ],
        "Geometrik Şekiller": [
            "Dörtgenler ve Özellikleri",
            "Özel Dörtgenler",
            "Çokgenler",
            "Çokgenlerde Açı ve Kenar İlişkileri",
        ],
        "Nicelikler ve Değişimler (1)": [
            "Trigonometrik Fonksiyonlar",
            "Trigonometrik Fonksiyon Grafikleri",
            "Ters Trigonometrik Fonksiyonlar",
            "Trigonometrik Özdeşlik ve Denklemler",
        ],
        "Nicelikler ve Değişimler (2)": [
            "Üstel Fonksiyonlar",
            "Logaritmik Fonksiyonlar",
            "Üstel ve Logaritmik Denklemler",
            "Logaritma Uygulamaları",
        ],
        "Nicelikler ve Değişimler (3)": [
            "Bileşke Fonksiyonlar",
            "Ters Fonksiyonlar",
            "Fonksiyon Dönüşümleri",
            "Fonksiyonlarda Öteleme ve Yansıma",
        ],
    },
    "Fizik": {
        "Kuvvet ve Hareket": [
            "Vektörler ve Denge",
            "Newton'un Hareket Yasaları",
            "Bir Boyutta Sabit İvmeli Hareket",
            "İki Boyutta Hareket ve Atışlar",
            "İş, Enerji ve Güç",
            "İtme ve Momentum",
        ],
        "Elektrik ve Manyetizma": [
            "Elektrik Yükü ve Elektriksel Kuvvet",
            "Elektrik Alan ve Elektriksel Potansiyel",
            "Sığaçlar",
            "Akım, Direnç ve Elektrik Devreleri",
            "Manyetik Alan ve Manyetik Kuvvet",
            "Elektromanyetik İndüksiyon",
        ],
        "Optik": [
            "Işığın Yansıması ve Aynalar",
            "Işığın Kırılması ve Mercekler",
            "Prizmalar ve Renk",
            "Optik Araçlar ve Göz",
        ],
    },
    "Kimya": {
        "Etkileşim": [
            "Fiziksel ve Kimyasal Olaylarda Enerji Değişimleri",
            "Tepkime Entalpisi",
            "Bağ Enerjisi ve Hess Yasası",
        ],
        "Çeşitlilik": [
            "Kimyasal Tepkime Hızı",
            "Kimyasal Denge",
            "Dengeye Etki Eden Faktörler",
            "Asit-Baz Dengesi",
            "Çözünürlük Dengesi",
        ],
        "Sürdürülebilirlik": [
            "Yeşil Hidrojen",
            "Nanoteknoloji",
            "Mikroplastik ve Nanoplastikler",
        ],
    },
    "Biyoloji": {
        "Tepki": [
            "Canlıların Uyaranlara Tepkileri",
            "Bitkisel Hormonlar",
            "Tropizma ve Nasti",
            "Reseptörler ve Uyaran Çeşitleri",
            "Nöron Yapısı",
            "Sinirsel İletim ve Sinaps",
            "Duyu Organları",
            "Hayvanlarda Sinir Sistemi Farklılıkları",
            "İnsan Sinir Sistemi",
            "Refleks",
            "İskelet, Kas ve Eklemler",
            "Kasların Kasılma Mekanizması",
        ],
        "Homeostazi": [
            "Doğal ve Kazanılmış Bağışıklık",
            "Alerji",
            "Homeostazi",
            "Pozitif ve Negatif Geri Bildirim",
            "Sinir ve Endokrin Sistemin Homeostazideki Rolü",
            "Dolaşım, Solunum ve Boşaltım Sistemlerinin Eş Güdümü",
            "Homeostatik Dengenin Bozulması",
            "Diyabetes Mellitus ve Diyabetes İnsipidus",
            "Kan Basıncı Anormallikleri ve Obezite",
        ],
    },
    "Coğrafya": {
        "Coğrafyanın Doğası": [
            "Coğrafyanın Konusu ve Bölümleri",
            "Coğrafyada Araştırma Yöntemleri",
        ],
        "Mekânsal Bilgi Teknolojileri": [
            "Coğrafi Bilgi Sistemleri",
            "Uzaktan Algılama ve GPS",
        ],
        "Doğal Sistemler ve Süreçler": [
            "Atmosfer ve İklim Süreçleri",
            "Yer Şekilleri ve Oluşum Süreçleri",
            "Su ve Toprak Sistemleri",
        ],
        "Beşerî Sistemler ve Süreçler": [
            "Nüfus Dinamikleri",
            "Yerleşme ve Şehirleşme",
            "Kültürel ve Siyasi Süreçler",
        ],
        "Ekonomik Faaliyetler ve Etkileri": [
            "Ekonomik Faaliyet Türleri",
            "Kaynak Kullanımı ve Ekonomi",
        ],
        "Afetler ve Sürdürülebilir Çevre": [
            "Afet Risk Yönetimi",
            "Sürdürülebilir Çevre ve Kalkınma",
        ],
        "Bölgeler, Ülkeler ve Küresel Bağlantılar": [
            "Bölge Türleri ve Sınıflandırma",
            "Küresel Bağlantılar ve Ticaret",
        ],
    },
    "Türk Dili ve Edebiyatı": {
        "Bir Diyeceğim Var!": [
            "Metin Türleri ve Anlatım",
            "Yazma Becerileri",
            "Konuşma ve Dinleme",
        ],
        "Kültür Yolculuğu": [
            "Türk Edebiyatında Dönemler",
            "Kültürel Değerler ve Edebiyat",
            "Metin Çözümleme",
        ],
        "Yaşamın İzinde": [
            "Hikâye ve Roman İncelemesi",
            "Şiir Çözümlemesi",
            "Tema ve Yapı",
        ],
        "Hayatın Aynası": [
            "Tiyatro ve Dramatik Metinler",
            "Eleştiri ve Deneme",
            "Dil Bilgisi Uygulamaları",
        ],
    },
    "Tarih": {
        "Değişen Dünyada Osmanlı Devleti (1683–1789)": [
            "Osmanlı'da Gerileme ve Değişim",
            "Avrupa'daki Gelişmeler ve Osmanlı",
            "Islahat Hareketleri",
        ],
        "Dönüşüm Sürecinde Osmanlı (1789–1908)": [
            "Yenileşme Hareketleri",
            "Tanzimat ve Meşrutiyet",
            "Osmanlı'da Modernleşme",
        ],
    },
    "Felsefe": {
        "Çevre Sorunları ve Felsefe": [
            "Çevre Etiği",
            "İnsan-Doğa İlişkisi",
        ],
        "Teknoloji ve Hayat": [
            "Teknoloji Felsefesi",
            "Teknolojinin Etik Boyutu",
        ],
        "Akıl ve İnanç": [
            "Akıl-İnanç İlişkisi",
            "Bilgi ve İnanç",
        ],
        "Edebiyat ve Felsefe": [
            "Edebiyat-Felsefe İlişkisi",
            "Metinlerde Felsefi Temalar",
        ],
        "Hayatın Anlamı": [
            "Anlam Arayışı",
            "Varoluş ve Değerler",
        ],
        "Hukuk ve Felsefe": [
            "Hukuk Felsefesi",
            "Adalet ve Hak",
        ],
    },
    "Din Kültürü": {
        "Kader, İrade ve Sorumluluk": [
            "Kader ve Kaza",
            "İrade ve Sorumluluk",
        ],
        "Din, Felsefe, Bilim ve Sanat": [
            "Din-Felsefe İlişkisi",
            "Din-Bilim İlişkisi",
            "Din-Sanat İlişkisi",
        ],
        "İslam Medeniyeti ve Gönül Coğrafyamız": [
            "İslam Medeniyeti",
            "Gönül Coğrafyası",
        ],
        "İnançla İlgili Meseleler": [
            "İnanç Konuları ve Yorumlar",
            "Güncel İnanç Meseleleri",
        ],
        "Yahudilik ve Hristiyanlık": [
            "Yahudilik",
            "Hristiyanlık",
        ],
    },
}
