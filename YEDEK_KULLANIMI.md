# KARAKOÇ — Pilot Dönem Yedekleme Talimatı

> **Bu geçici bir yöntemdir; kalıcı veritabanı çözümü DEĞİLDİR.**
> Streamlit Community Cloud'un yerel dosya alanı kalıcı değildir. Öğrenci
> verilerinin kesinlikle kaybolmayacağı garantisi verilemez. Kalıcı depolama
> ayrı bir kurulum/geçiş çalışmasıdır (`YAYIN_KURULUMU.md`).

## Günlük pilot kuralları

1. **Her günün sonunda** güncel yedeği indir.
2. **Yeni öğrenci hesabı** oluşturulduğunda yedek al.
3. **Kod güncellemesi veya yeniden dağıtımdan hemen önce** yedek al.
4. Yedeği yalnızca Streamlit sunucusunda bırakma. **Yerel bilgisayarda** ve
   **erişimi kısıtlı ikinci bir depolama alanında** sakla.
5. Yedekleri **GitHub deposuna ekleme**.
6. Yedek dosyaları öğrenci bilgileri içerir; erişimlerini sınırla ve güvenli
   sakla. Paylaşılan/ortak klasörlere koyma.

> Streamlit içindeki zamanlayıcıların veya arka plan botlarının sürekli açık
> kalacağını varsayma. Otomatik yedekleme daha sonra harici ve kalıcı bir
> altyapı üzerinden planlanmalıdır.

## Admin panelinden yedek alma (adım adım)

1. Yönetici hesabıyla giriş yap → **💾 Veritabanı Yedekleme** sekmesi.
2. **🗄️ Tutarlı yedek oluştur (Backup API)** düğmesine bas.
   - SQLite Backup API kullanılır; WAL'deki son commit'ler de yedeğe girer.
   - Dosya adına tarih-saat eklenir.
   - `PRAGMA integrity_check` otomatik yapılır.
   - Tablo kümesi ve öğrenci sayısı kaynakla karşılaştırılır.
3. **⬇️ Yedeği İndir (.db)** ile dosyayı indir.
4. İndirdiğin dosyayı yerel bilgisayarda ve erişimi kısıtlı ikinci bir alanda
   sakla.
5. İstersen **🔎 Yedeği doğrula** ile bütünlüğü yeniden kontrol et.

## Geri yükleme (yalnızca yetkili yönetici)

- **♻️ Yedeği Geri Yükle ve Yenile** yalnızca admin tarafından çalıştırılır.
- Geri yüklemeden önce mevcut veritabanı `.bak` güvenlik kopyasına alınır.
- Geri yükleme sonrası bütünlük, tablo sayısı ve öğrenci sayısı gösterilir.

> Mümkünse geri yüklemeyi doğrudan üretim veritabanına değil, önce **geçici bir
> test kopyasına** uygulayıp doğrulayın. Otomatik test:
> `tests/test_v25_veritabani_yedek.py`.

## Doğrulama komutları

```powershell
# Testler (geçici DB'ler; gerçek veriye dokunmaz)
python -m unittest tests.test_v25_veritabani_yedek tests.test_v25_admin_guvenlik -v
```

Gerçek veritabanını salt okuma ile kontrol:

```python
import sqlite3
c = sqlite3.connect("file:yks_veritabani.db?mode=ro", uri=True)
print(c.execute("PRAGMA integrity_check").fetchone()[0])
print(c.execute("SELECT COUNT(*) FROM ogrenciler").fetchone()[0])
```
