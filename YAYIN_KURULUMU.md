# KARAKOÇ — Yayın ve Veri Kalıcılığı Kurulumu

Bu belge, uygulamanın **gerçek öğrenci verisini kaybetmeden** yayınlanması
için gereken adımları açıklar. Uygulama SQLite kullanır; veritabanı yolunun
kalıcı bir diske işaret etmesi **yayın için zorunludur**.

## 1. Neden önemli?

Streamlit Community Cloud (ör. `*.streamlit.app`) konteynerinin yerel dosya
alanı **kalıcı değildir**. Konteyner uykuya geçtiğinde veya yeniden
başladığında `yks_veritabani.db` gibi yerel dosyalar kaybolabilir. Bu nedenle:

- Yalnızca admin panelinden yedek indirmek sorunu **çözmez** (yedek de aynı
  geçici alanda tutulabilir).
- Veritabanı yolu kalıcı bir diske veya yönetilen bir veritabanına
  yönlendirilmeden uygulama **üretim açısından güvenli kabul edilmez**.

Resmî açıklama:
https://docs.streamlit.io/develop/concepts/connections/connecting-to-data

## 2. Seçenek A — Kalıcı disk üzerinde SQLite (önerilen, en az değişiklik)

Uygulama veritabanı yolunu şu öncelikle belirler (`config/settings.py`):

1. `KARAKOC_DB_PATH` **ortam değişkeni**
2. Streamlit `secrets.toml` içindeki `KARAKOC_DB_PATH`
3. Varsayılan: proje kökündeki `yks_veritabani.db` (yalnızca yerel geliştirme)

### Yerel geliştirme

```powershell
$env:KARAKOC_DB_PATH = "C:\veri\karakoc\yks_veritabani.db"
streamlit run main.py
```

### Streamlit Community Cloud / kalıcı volume

`secrets.toml` (Streamlit Cloud → Settings → Secrets):

```toml
KARAKOC_DB_PATH = "/mnt/kalici/karakoc/yks_veritabani.db"
```

`/mnt/kalici` **kalıcı bir volume** olmalıdır. Community Cloud varsayılan
olarak kalıcı volume sunmaz; bu nedenle kalıcı disk gerektiren bir ortam
(VPS, Docker volume, Railway/Render persistent disk vb.) gerekir.

### VPS / Docker

- SQLite dosyasını kalıcı bir volume'a bağlayın (ör.
  `docker run -v /srv/karakoc:/data -e KARAKOC_DB_PATH=/data/yks_veritabani.db ...`).
- Dosya izinlerini yalnızca uygulama kullanıcısına verin.

## 3. Seçenek B — Yönetilen uzak veritabanı (PostgreSQL/Supabase)

Bütün servisler SQLite'e özgü bazı davranışlar kullanır (`sqlite3.Row`,
`lastrowid`, `ON CONFLICT`, tarih metinleri, `PRAGMA`). Uzak veritabanına
geçiş, yalnızca bağlantı dizesi değiştirmekle olmaz; her servis tek tek
uyarlanmalıdır. Bu nedenle:

- Bağlantı bilgisi **yoksa** gerçek bağlantı kurulmuş gibi davranılmaz.
- Yapılandırma env/secrets üzerinden hazırlanır, yerel SQLite desteği korunur.
- Geçiş tamamlanmadan üretimde uzak DB **aktif sayılmaz**.

## 4. Yayın öncesi kontrol listesi

- [ ] `KARAKOC_DB_PATH` kalıcı bir diske işaret ediyor.
- [ ] Uygulama, DB dosyasının bulunduğu dizine yazma yetkisine sahip.
- [ ] `yks_veritabani.db` **Git'e eklenmemiş** (`.gitignore` içinde `*.db`).
- [ ] Admin panelinden bir kez **tutarlı yedek** alındı ve indirildi.
- [ ] Yedek `PRAGMA integrity_check` = `ok`.
- [ ] Giriş, profil, görev, kamp ve rapor akışları duman testinden geçti.

## 5. Yedekleme ve geri yükleme

Admin paneli → **💾 Veritabanı Yedekleme**:

- **Tutarlı yedek oluştur (Backup API):** SQLite `Connection.backup` ile
  kilitlenmeden tutarlı kopya üretir, tarih-saat ekler, `integrity_check`
  ile doğrular ve indirilebilir.
- **Yedekten geri yükle:** Yalnızca admin başlatabilir. Önce mevcut DB `.bak`
  güvenlik kopyasına alınır; ardından bütünlük, tablo ve öğrenci sayısı
  kontrol edilir.
- Bu yedekler **ikinci güvenlik katmanıdır**; kalıcı depolamanın yerine
  geçmez.

## 6. Önemli uyarı

Kalıcı disk veya yönetilen uzak veritabanı **aktif değilse**, uygulama
teknik olarak çalışsa bile öğrenci verileri kaybolabilir. Bu durum bir
**yayın engelidir**; "çözüldü" olarak raporlanmamalıdır.
