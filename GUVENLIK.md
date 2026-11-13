# KARAKOÇ — Yönetici Güvenliği

Bu belge, yönetici (koç) hesabının güvenli yapılandırılmasını ve sunucu
taraflı yetkilendirmeyi açıklar. **Parola veya gizli anahtar hiçbir Python,
HTML, CSS, JavaScript veya APK dosyasında açık metin olarak tutulmaz.**

## 1. Yönetici parolası nerede tanımlanır?

Öncelik sırası:

1. Ortam değişkeni: `KARAKOC_ADMIN_USERNAME`, `KARAKOC_ADMIN_PASSWORD`
2. Streamlit Secrets (üretim): Streamlit Cloud → Settings → Secrets
3. Yerel geliştirme: `.streamlit/secrets.toml` (Git'e EKLENMEZ)

Örnek dosya: `.streamlit/secrets.toml.example`

```toml
KARAKOC_ADMIN_USERNAME = "admin"
KARAKOC_ADMIN_PASSWORD = "GUCLU-VE-TAHMIN-EDILEMEZ-BIR-PAROLA"
```

> `.streamlit/secrets.toml` ve `.env` dosyaları `.gitignore` içindedir.
> Gerçek değerleri asla commit etmeyin.

## 2. Parola hash'i

- Yeni kayıtlar **scrypt** (bellek-zorlu KDF; Argon2id'ye denk güvenli) ile
  `scrypt$tuz$hash` biçiminde saklanır.
- Eski PBKDF2-HMAC-SHA256 kayıtları geriye dönük doğrulanır; mevcut öğrenci
  hesapları bozulmaz.
- Düz metin parola saklanmaz ve loglanmaz.

## 3. İlk admin oluşturma / rotasyon

- `KARAKOC_ADMIN_PASSWORD` tanımlıysa bootstrap, admin hesabını bu parolayla
  **idempotent** biçimde eşitler. Parola yalnızca secret ile uyuşmuyorsa
  güncellenir; her başlangıçta kontrolsüz sıfırlanmaz.
- Secret **tanımlı değilse** bilinen bir varsayılan parola oluşturulmaz;
  admin hesabı `Pasif` bırakılır veya mevcut güvenli (scrypt) parola korunur.
- Eski PBKDF2 biçimli admin parolası secret yoksa pasifleştirilir.

**Parola değiştirme:** `KARAKOC_ADMIN_PASSWORD` değerini güncelleyip uygulamayı
yeniden başlatın. Bootstrap yeni hash'i yazar.

> Eski varsayılan yönetici parolası **geçersizdir**. Bu bilgi kodda veya Git
> geçmişinde yer aldıysa güvenli kabul edilmez; yeni bir secret ile değiştirin.

## 4. Sunucu taraflı yetkilendirme

- `main.py`, her istekte kullanıcının rolünü **veritabanından** okur.
  `st.session_state["rol"]` tek başına yetki kanıtı değildir.
- `views/admin_panel.py::render`, `yks_referans_verisi_yonetimi` ve
  `veritabani_yedek_geri_yukle` her çağrıda `auth_service.yetki_dogrula`
  ile admin rolünü doğrular.
- Öğrenci; kullanıcı yönetimi, yedekleme, geri yükleme, rol değiştirme ve
  veri düzenleme işlemlerini **yapamaz**.
- Yetkisiz girişimler `sistem_loglari` tablosuna `YETKISIZ_ERISIM` olarak
  yazılır; loglarda parola bulunmaz.
- Hesap pasif/silinmişse oturum kapatılır.

## 5. Doğrulama (kabul testi)

1. `.streamlit/secrets.toml` içinde güçlü bir `KARAKOC_ADMIN_PASSWORD` tanımlayın.
2. Uygulamayı başlatın; mevcut giriş ekranından `admin` + secret parolasıyla
   giriş yapın → yönetici paneli açılır.
3. Öğrenci hesabıyla giriş yapın → yönetici paneli **görünmez**.
4. Öğrenci oturumunda `rol` 'admin' yapılsa bile panel açılmaz (DB doğrulaması).

Otomatik testler: `tests/test_v25_admin_guvenlik.py`,
`tests/test_ui_smoke.py` (05–07).
