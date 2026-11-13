# KARA KOÇ v2.6 — Stabilizasyon ve Veri Güvenliği Raporu

> Tarih: 2026-11-13 · Pilot dönem (gerçek öğrenci verisi korunumu öncelikli)

## 1. Başlangıç durumu (kanıt)

- Aktif giriş noktası: `main.py` (Streamlit). `main_2.py` yok; tek giriş.
- Veritabanı: **SQLite**, yerel dosya `yks_veritabani.db`, **WAL** modu.
- Canlı DB: 25 tablo, **1 hesap** (admin), konu/ilerleme tabloları boş.
  `PRAGMA integrity_check = ok`.
- Değişiklik öncesi yedek (Backup API):
  `KARA_KOC_YEDEK/yks_veritabani_phase1_once_20261113_190921.db`
  (737.280 bayt, sha256 `cf306977...`, integrity `ok`).
- Başlangıç test referansı: **326 test OK** (`baseline_err.txt`).
- Canlı DB hiçbir testte kullanılmadı; tüm testler `tempfile` DB'leri ile.

## 2. Aşama 1 — Yedekleme ve veri güvenliği

Eklenenler (`config/database.py`, `views/admin_panel.py`):

- `zaman_damgali_yedek`: Backup API + tarih-saat adı + `integrity_check` +
  tablo/öğrenci karşılaştırması + **son 10 yedek** saklama (yalnızca kendi
  ürettiği `karakoc_yks_yedek_*` dosyalarını temizler).
- `yedek_listesi` / `son_yedek_bilgisi`: admin panelinde son yedek ve arşiv.
- `yedekten_gecici_dogrula`: yedeği **geçici kopyaya** açıp geri
  yüklenebilirliğini kanıtlar; canlı DB'ye yazmaz.
- `geri_yukle` sertleştirildi: yedek canlı DB'ye dokunmadan önce geçici
  dosyada `integrity_check` + tablo kontrolünden geçer; mevcut DB Backup API
  ile `.bak` kopyasına alınır; WAL checkpoint + atomik `os.replace`; son
  doğrulama başarısızsa `.bak`'tan otomatik geri dönüş.
- Windows'ta dosyayı açık tutan bağlantı sızıntısı (replace hatası) giderildi.
- Yedek oluşturma `DB_BACKUP`, geri yükleme `DB_RESTORE` olarak loglanır.

Yedek testleri: `tests/test_v26_yedek_guvenligi.py` (7 test) +
mevcut `test_v25_veritabani_yedek.py` (4 test) — hepsi OK.

## 3. Aşama 2 — Negatif ilerleme / -40.0 kök nedeni

**Kök neden 1 (görünen -40):** Veritabanında negatif ilerleme üreten bir kod
yolu yok. `-%40` ifadesi **aylık hedefe göre FARKTIR**:
`delta_yuzde = gercek_tamamlanma_orani - hedef_yuzde` (ör. %5 - %45 = -40).
Dashboard bunu delta olarak, alarm servisi "**-%40** gerisindesiniz" diye
yazıyordu; öğrenci bunu "konu ilerlemesi -40" sanıyordu.
**Düzeltme:** değer artık "Hedefin 40.0 puan gerisinde" olarak, hedef ve gerçek
oran ayrı gösteriliyor; eksi işaretli "ilerleme" görünümü kaldırıldı.

**Kök neden 2 (gerçek veri riski):** `task_steps.mikro_ilerleme_guncelle`
yeniden hesaplamada `cozulen_soru` / `tamamlandi` değerlerini düşürebiliyordu
(görev/oturum bağlantısı değişince). Ayrıca kamp tamamlamaları
`mikro_konu_ilerleme` tablosuna hiç yazmıyordu; bu yüzden ilerleme hiç artmıyor,
kamp aynı mikro konuda dönüyordu.

**Düzeltmeler:**
- `mikro_ilerleme_guncelle`: cozulen/hedef/öğrenme/tamamlandı değerleri
  **monoton** korunur; engellenen gerileme `son_neden='gerileme_engellendi'` ve
  `son_gerileme_zamani` ile kayıt altına alınır. Bilinçli yeniden değerlendirme
  için `yeniden_degerlendir=True` parametresi var.
- Tüm yüzdeler `topic_progress.ilerleme_sinirla` ile **0–100** aralığına
  sabitlenir; NaN/güvenilmeyen girişler 0 kabul edilir.
- Tek ilerleme modeli: Konu Takip ve Kamp aynı `mikro_ilerleme_oranlari` /
  `makro_ilerleme_detay` fonksiyonlarını kullanır (öğrenme %50 + soru hedefi
  %50; makro = mikro konuların eşit ağırlıklı ortalaması).
- Canlı DB negatif/bayat kayıt taraması: **0 bulgu**.

Kontrollü bakım aracı: `services/maintenance.py`
(`python -m services.maintenance --db ...` = salt okunur rapor;
`--uygula` = önce yedek alır, yalnızca bariz bozulmaları düzeltir).

## 4. Aşama 3 — Makro / mikro müfredat yapısı

- Havuzlar: Maarif 9 (8 ders / 88 mikro), Maarif 11 (9 / 125), Klasik TYT+AYT+YDT
  (22 / 221). Toplam **434 mikro konu**; **hepsinin alt başlığı var**.
- Aynı ders içinde mükerrer mikro konu yok. 12 mikro adı farklı derslerde
  geçiyor; bu yüzden kamp artık düz ad yerine **(ders, mikro)** çifti kullanır.
- Ön koşul haritası 73 → **81** kurala çıkarıldı (yalnızca AYT Geometri için
  8 eksik kural; mevcut kurallar ezilmedi). AYT Matematik ve AYT Geometri
  kapsaması **%100**.
- `Doğruda Açılar` → `Temel Kavramlar ve Doğruda Açılar` alias'ı eklendi.
- Yapısal denetim: `data.curriculum_meta.mufredat_denetimi()` (saf, yazmaz) ve
  `tests/test_v26_mufredat_tutarliligi.py` (4 test) — sorun sayısı **0**.
- Bilinen eksik (rapor): AYT Fizik %47, Kimya %36, Biyoloji %69, Edebiyat %43,
  Tarih/Coğrafya/Felsefe/Din kısmi. Bunlar için uydurma kural eklenmedi; ürün
  kararı bekliyor.

## 5. Aşama 4 — Kamp görev kuyruğu ve geçiş

`kamp_motoru.kamp_kuyrugu_hesapla` artık 4 durumu **ayırır**:

| Durum | Anlam | Arayüz |
|---|---|---|
| `hazir` | Sıradaki makro + çalışılacak mikrolar | Görev kartı |
| `onkosul_kilitli` | AYT çekirdek TYT eksiği | Uyarı + eksik TYT konu listesi |
| `tamamlandi` | Gerçekten tüm mikro konular bitti | Başarı mesajı |
| `tanim_eksik` | Ders/mikro tanımı yok | Teknik hata uyarısı |

- AYT kilidi %80 çekirdek eşiğine göre; 11. sınıf Maarif istisnası korunur.
- Kamp tamamlaması `mikro_konu_ilerleme` (`alt_konu=''`) tablosuna atomik
  yazılır; `biten_konulari_yukle` bu kaydı %100 biten kabul eder. Böylece
  tamamlanan mikro konu kuyruktan düşer ve **sıradaki konuya geçilir**.
- Başarısız dilim (<%75) atlanmaz; analiz sonrası **aynı dilim tekrar** edilir.
- Çift tıklama/yenileme `mukerrer` koruması ve `sayildi` bayrağı ile çift
  saymaz.

## 6. Aşama 5 — Soru hedefleri

`data/question_targets.py` (tek kaynak):

- Normal: 8 kolay + 8 orta + 8 zor = **24**.
- Pekiştirme (Matematik, Geometri, Fizik): 16 + 16 + 16 = **48**.
- Dilimler her zaman **8 soru**: normal 3 dilim; pekiştirme 6 dilim
  (kolay, kolay, orta, orta, zor, zor).
- Tek dilim bitirmek mikro konunun %100 öğrenildiği anlamına gelmez; mikro
  tamamlanması için öğrenme + TÜM dilimler + toplam soru hedefi gerekir.
- Mevcut `planner.SORU_CARPANI` / `konu_soru_kotasi` (program motoru) ellenmedi.

## 7. Aşama 6–7 — İki ilerleme çubuğu ve mikro konu görünürlüğü

- Üstte **MAKRO KONU** çubuğu: altın/amber, kalın, `%oran` + makro adı +
  "x / y mikro konu tamamlandı"; mikro konu verisinden türetilir ve Konu Takip
  ile aynı fonksiyonu kullanır.
- Altta **GÖREV İLERLEMESİ** çubuğu: ince, camgöbeği/mavi, `3/5` biçiminde,
  yalnızca o mikro konunun başarıyla geçilen dilimlerini sayar.
- Görev kartında sıra: **mikro konu başlığı (en büyük)** → makro adı → görev
  x/y + seviye → "8 soru".
- Mobil yatay (max-height 520px) için küçültme ve taşma kuralları eklendi;
  dikey mobil tam optimizasyon bilinçli olarak sonraki sürüme bırakıldı.

## 8. Aşama 8–9 — Enter, oturum ve admin güvenliği

- Kamp sonuç alanları `st.form` içine alındı; Enter sayfayı yenilemez, form
  tek sefer gönderilir. Çalışma kaydı formu zaten `st.form` idi.
- Kronometre ve aktif görev DB'de (`baslangic_ts`, kayıt durumu) tutulduğu için
  rerun/telefon uykusunda kaybolmaz.
- Admin güvenliği mevcut mimaride doğrulandı: her istekte rol DB'den okunur,
  admin işlemleri `auth_service.yetki_dogrula` ile sunucu tarafında kontrol
  edilir, parola secret/env'de tutulur, istemci kodunda değildir.
  Cihaz ID'sinin tek başına kimlik doğrulama olmadığı `GUVENLIK.md`'ye yazıldı.
  Ayrı admin uygulaması ihtiyacı ayrı aşama olarak bırakıldı.


## 9. Aşama 10 — Mimari ve veritabanı başlatma

- Mevcut katmanlar korundu: `config/` → `data/` → `services/` → `views/`.
  Yeni veri modülü `data/question_targets.py`, yeni bakım servisi
  `services/maintenance.py`; başka yeniden yazım yapılmadı.
- `@st.cache_resource` yalnızca **bootstrap** için kullanılıyor; SQLite
  bağlantısı cache'lenmiyor (her kullanımda aç/kapat). Cache anahtarı
  (mutlak DB yolu, şema sürümü). Şema sürümü **5 → 6**.
- Migration'lar idempotent; canlı DB kopyasında denendi:
  25 → 27 tablo, 1 hesap korundu, `integrity_check=ok`.

## 10. Veritabanı değişiklikleri ve migration

Eklemeli (veri silmeyen) değişiklikler:

| Tablo | Değişiklik |
|---|---|
| `mikro_konu_ilerleme` | `son_neden TEXT`, `son_gerileme_zamani TEXT` |
| `kamp_mikro_kayitlari` | `sayildi INTEGER DEFAULT 0`, `seviye TEXT` |
| `kamp_oturumlari`, `kamp_mikro_kayitlari` | Yoksa oluşturulur (v2.3 şeması) |

- Mevcut satırlar silinmedi, yeniden adlandırılmadı, sıfırlanmadı.
- `yks_veritabani.db` Git'e eklenmedi (`.gitignore`: `*.db`, `*-wal`, `*-shm`).
- Migration öncesi/sonrası öğrenci sayısı ve tablo sayısı karşılaştırıldı.
- Canlı DB'ye bu çalışma sırasında **yazılmadı**; uygulama ilk açılışta
  bootstrap ile eklemeleri yapacak.

## 11. Testler

| Test dosyası | Kapsam | Sonuç |
|---|---|---|
| `test_v26_yedek_guvenligi.py` | WAL/boş/retention/geçici restore/bozuk yedek | 7 OK |
| `test_v26_ilerleme_koruma.py` | 0–100 sınırı, izolasyon, çift işleme, gerileme, atomiklik | 7 OK |
| `test_v26_mufredat_tutarliligi.py` | 434 mikro, alt başlık, ön koşul, havuzlar | 4 OK |
| `test_v26_kamp_motoru.py` | kuyruk durumları, TYT kilidi, 24/48, geçiş, mükerrer | 13 OK |
| `test_v26_kamp_ui.py` | AppTest: iki çubuk + mikro başlık + exception yok | 1 OK |
| Tüm mevcut testler | FAZ 5/6/7/8/9 + UI smoke + admin | OK |

- Başlangıç: **326 test OK**. Son: **358 test OK** (0 hata, 0 başarısız).
- Canlı DB regresyon testi: `integrity_check=ok`, 25 tablo, 1 hesap.
- Yedek/geri yükleme kanıtı: geçici kopyada geri yükleme + tablo/öğrenci
  eşleşmesi testleri.

## 12. Bilinen sorunlar / sınırlar

1. **Kalıcı disk zorunluluğu:** Streamlit Community Cloud'un yerel alanı
   kalıcı değildir. `KARAKOC_DB_PATH` kalıcı diske yönlendirilmezse veri
   kaybı riski sürer (`YAYIN_KURULUMU.md`, yayın engeli).
2. **Admin paneli aynı uygulamada:** Yetki sunucu tarafında doğrulanıyor ancak
   ayrı admin uygulaması yok; ihtiyaç ayrı aşama.
3. **Ön koşul kapsaması:** AYT Fizik/Kimya/Biyoloji ve sözel derslerde kural
   kapsaması kısmi; veri kararı bekliyor.
4. **Program motoru kotası:** FAZ 5 planlayıcısının 25–40 soru kotası
   değiştirilmedi; yeni 24/48 hedefi kamp dilimleri için geçerlidir. Bu bilinçli
   uyumluluk kararıdır.
5. **Dikey mobil:** Tam tek elle kullanım optimizasyonu sonraki sürümde.
6. **Yedek saklama:** Son 10 zaman damgalı yedek tutulur; harici/ikinci kopya
   yine operatör sorumluluğundadır.

## 13. Canlıya geçiş adımları

1. Yeni bir **zaman damgalı yedek** al ve indir; `integrity_check=ok` doğrula.
2. `python -m unittest discover -s tests -p "test_*.py"` → tüm testler OK.
3. `python -m services.maintenance --db yks_veritabani.db` → 0 bulgu.
4. Uygulamayı yayına al; ilk açılışta bootstrap şema sürümü 6'yı uygular.
5. Admin panelinden bir yedek oluştur, "Geçici kopyada geri yükleme testi"ni
   çalıştır.
6. Bir test öğrencisiyle kampı başlat: iki çubuk, 8 soruluk dilim, mikro
   geçişi ve ön koşul kilidi mesajını doğrula.
7. Gerçek öğrenci hesaplarıyla giriş/çıkış, görev, kamp ve rapor akışlarını
   kontrol et. Sorun varsa yedeği geri yükle (önce `.bak` alınır).

