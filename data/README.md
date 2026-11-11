# ÖSYM puan–sıra referans verisi

KARA KOÇ'un YKS simülatörü **puan** ile **sıralama** işini bilinçli olarak ayırır:

- **Puan**: `services/ranking_engine.py` içindeki doğrusal model hesaplar
  (taban 100 + test başına katsayı × net + OBP katkısı). Bu bir **tahmindir**;
  ÖSYM'nin resmî standart puanı değildir.
- **Sıralama**: yalnızca bu dosyada **doğrulanmış** puan–sıra noktaları varsa
  üretilir. Veri yoksa simülatör sıralama tahmini **göstermez** ve eksik veriyi
  açıkça bildirir.

> Bu sürümde dosya **boştur**. Kasten boştur: resmî kaynağı doğrulanmamış hiçbir
> puan–sıra sayısı ürüne gömülmez.

## Neden boş?

ÖSYM'nin resmî puanı, ilgili yılın test ortalama ve standart sapmalarıyla yapılan
standart puan dönüşümüne dayanır. Bu değerler yayımlanmadan üretilen puanlar
tahmindir. Aynı şekilde, internette dolaşan "puan–sıra tabloları"nın büyük kısmı
özel kurumların derlemesidir. Bunları resmî veri gibi sunmak öğrenciyi yanıltır.

## Nasıl doldurulur?

1. Resmî kaynağı belirle (ÖSYM kılavuzu, ÖSYM sayısal bilgiler bülteni vb.).
2. Aynı yıl + puan türü için en az **3** nokta gir (arada tahmin yapılabilmesi için).
3. Noktalar **puan azalan**, **sıra artan** sırada olmalı.
4. Kaynak kurum ve kaynak belge zorunludur; kaynaksız kayıt reddedilir.

### Dosya biçimi

```json
{
  "surum": 1,
  "guncelleme": "2026-11-11",
  "kayitlar": [
    {
      "yil": "2024",
      "puan_turu": "Sayısal",
      "kaynak": {
        "kurum": "ÖSYM",
        "belge": "2024-YKS ... (belge adı / tablo adı)",
        "url": "https://...",
        "erisim_tarihi": "2026-11-11"
      },
      "not": "Kapsam ve varsa sınırlılık notu",
      "noktalar": [
        {"puan": 500.0, "sira": 1},
        {"puan": 450.0, "sira": 9000},
        {"puan": 400.0, "sira": 45000},
        {"puan": 350.0, "sira": 120000}
      ]
    }
  ]
}
```

`puan_turu` değerleri: `TYT`, `Sayısal`, `Eşit Ağırlık`, `Sözel`, `Dil`.

### Arayüzden giriş

Yönetici (admin) hesabıyla **🎯 YKS Simülatörü** sekmesindeki
"Puan–sıra referans verisi" bölümünden aynı bilgiler girilebilir; dosya
`services/osym_verisi.py` tarafından doğrulanarak atomik yazılır.

## Sıralama aralığı nasıl yorumlanır?

- Tek yıl verisi varsa **aralık üretilmez**; tek tahmin gösterilir.
- İki veya daha fazla yıl varsa, her yıl için ayrı tahmin hesaplanır ve
  en iyi/en kötü değer **"geçmiş yıllara göre senaryo aralığı"** olarak
  gösterilir. Bu bir istatistiksel güven aralığı **değildir**.
- Puan, girilen noktaların puan aralığının dışındaysa tahmin üretilmez
  (dışa doğru ekstrapolasyon yapılmaz).
