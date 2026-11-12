"""FAZ 5C/5D - Gerçek ilerlemeye dayalı akıllı haftalık program motoru.

İlkeler:

- **Planlama birimi mikro konudur (FAZ 5D).** Ders → ana konu → mikro konu →
  checklist. Bir ana konunun alt başlıkları tek görevde BİRLEŞTİRİLMEZ; her
  mikro konu kendi görev kaydı, kendi tamamlanma durumu, kendi checklist'i,
  kendi soru hedefi ve kendi süresiyle planlanır.
- **Ana konu kotası korunur.** Ana konunun soru hedefi mikro konulara
  paylaştırılır; mikro hedeflerin toplamı ana hedefe eşittir. Aynı hedef her
  mikro konuya tekrar uygulanmaz.
- **Süre bölünmez, mikro konuya göre hesaplanır.** Ana konunun anlatım süresi
  mikro konu sayısına bölünmez; mikro konunun kendi süresi (varsa), yoksa ana
  konunun süresi makul varsayılan olarak kullanılır ve gerçek oturum medyanı
  ile kişiselleştirilir.
- **Gerçek soru kaynağı yalnızca FAZ 4 oturumlarıdır.** `konu_soru_ilerleme`
  (eski planlama sayacı) burada hiç okunmaz.
- **Kota arka planda kalır.** Kredi puanı, ana konu kotası, kalan soru
  matematiği ve öncelik puanları öğrenci arayüzünde gösterilmez.
- **Günlük kapasite aşılmaz.** Her gün için ayrı müsaitlik (dakika) tanımlıdır;
  0 dakika dinlenme günüdür. Görev süreleri `task_steps` ile aynı formülle
  hesaplandığı için planlanan süre gerçek tahminle tutarlıdır.
- **Haftaya sığmayan mikro konular devredilir.** Önceki programdan kalan soru
  miktarı yeni göreve `kaynak_gorev_id` ile bağlanır; tamamlanmış mikro konu
  yeniden üretilmez.
- **Ön koşul ağacı korunur.** Ön koşulu tamamlanmamış konuya geçilmez.
- **Biten konu tekrar etmez (KURAL 1).** %100 tamamlanmış konu rutin programa
  dönmez; yalnızca denemede yanlış çıkarsa sınırlı bir "Eksik Kapatma" görevi
  açılır ve hedefi dolunca kart programdan düşer.
- **Sıfır konu anlatımla başlar (KURAL 2).** Hiç çalışılmamış konunun kartında
  ilk adım her zaman "Konu Anlatımı (Video/Kaynak)"tır.
- **Ezber/pekiştirme ayrımı (KURAL 3).** Ezber derslerinde anlatım/okuma süresi
  uzar, soru yükü azalır; pekiştirme derslerinde anlatım makul kalır ve soru
  pratiği kolay ➔ orta ➔ zor ilerler.
- **Günlük ders bölünmesi sınırlıdır (KURAL 4).** 4 saat ve altı çalışmada en
  fazla 3, müsaitlik ne olursa olsun en fazla 5 farklı ders.

Bu modül Streamlit'e bağımlı değildir.
"""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

from data import curriculum_meta
from services import task_steps

try:  # FAZ 6C köprüsü (modül yoksa planlama aynen çalışır)
    from services import gorev_kaynaklari
except ImportError:  # pragma: no cover
    gorev_kaynaklari = None

KAYNAK_TEKRAR = getattr(gorev_kaynaklari, "KAYNAK_TEKRAR", "tekrar_kaydi")
KAYNAK_YANLIS = getattr(gorev_kaynaklari, "KAYNAK_YANLIS", "yanlis_soru")

TR_TZ = timezone(timedelta(hours=3))

GUN_SAYISI = 7
VARSAYILAN_GUNLUK_DAKIKA = 360
MAKS_GUNLUK_DAKIKA = 1440
MIN_ANLAMLI_BLOK = 5
# v2.3 (FAZ 1.3): yeni/devam eden ANA KONU görevleri için minimum anlamlı
# blok. Daha küçük "5 soru ~11 dk" kırıntıları üretilmez; süre yetmezse
# görev ertesi güne bırakılır.
MIN_KONU_BLOK_DK = 25
MIN_KONU_BLOK_SORU = 15
MAKS_YENI_MIKRO_GUN = 2
# Bir dersten bir güne düşebilecek en fazla görev sayısı (ders dengesi).
MAKS_DERS_GOREV_GUN = 3
# Günlük soru tavanı: gerçekçi üst sınır (100-400 soru/gün hedefi).
MAKS_SORU_GUN = 400
AGIR_DERSLER = ("AYT Matematik", "TYT Matematik", "AYT Geometri", "TYT Geometri")
PARAGRAF_DAKIKA = 30
TEKRAR_DAKIKA = 20
KREDI_MAKS = 100.0
# Toplam soru hedefi = 100 x carpan x normalize kredi. Gerçekçi günlük hacim
# (100-400 soru) için 3 yerine 24 kullanılır: bir mikro konunun toplam soru
# kotası böylece 25-40 bandına oturur (gerçek YKS kitap hacmi). Günlük
# kapasite her zaman üst sınırdır; kota yalnızca talebi belirler.
SORU_CARPANI = 24.0
# Ezber derslerinde soru yükü azaltılır (not/tekrar ağırlığı artar).
EZBER_SORU_ORANI = 0.6
EZBER_GOREV_SORU_TAVANI = 25
VARSAYILAN_DB_YOLU = "yks_veritabani.db"

# --- Biten (%100) konu & "Eksik Kapatma" (KURAL 1) ---------------------------
# Biten konu rutin programa SONSUZA KADAR eklenmez. Konu yalnızca denemede
# yanlış çıkarsa SINIRLI bir "Eksik Kapatma" (özel ders) göreviyle girer; hedef
# soru/tekrar tamamlanınca görev programdan düşer ve bir daha açılmaz.
TELAFI_ETIKETI = "🎯 Telafi / Eksik Kapatma: "
# Eski (v2.0) telafi kartı öneki: geriye dönük tanıma için korunur.
TELAFI_ETIKETI_ESKI = "🩹"
TELAFI_ISARET = "Eksik Kapatma"
TELAFI_HEDEF_SORU = 20
# Deneme yanlışı kaynaklı telafi kotası: yanlış sayısına göre 15-30 soru arası
# TEK ve SINIRLI bir görev kartı (sonsuz çalışma döngüsünü engeller).
TELAFI_MIN_SORU = 15
TELAFI_MAKS_SORU = 30

# --- Bilinmeyen konu akışı (KURAL 2) ----------------------------------------
# Sıfır ilerlemeli konuda kartın İLK adımı konu anlatımıdır.
BILINMEYEN_KONU_ADIMI = "Konu Anlatımı (Video/Kaynak)"
# %0 konunun ilk günü "Konu Anlatımı + İlk Kavrama Testi" tamamlanınca 24-48
# saat sonrasına "Pekiştirme / Hatırlama Kontrolü (20 Soru)" planlanır; bu ikinci
# adım tamamlanmadan konunun ilerlemesi %50 üzerine çıkarılmaz.
PEKISTIRME_SORU = 20
PEKISTIRME_MIN_SAAT = 24
PEKISTIRME_MAX_SAAT = 48
PEKISTIRME_ETIKETI = "🔁 Pekiştirme / Hatırlama Kontrolü"

# --- Günlük farklı ders sayısı (KURAL 4) ------------------------------------
# 4 saat ve altı çalışmada en fazla 3 farklı ders; müsaitlik ne olursa olsun
# en fazla 5 farklı ders (4 saati 6 derse bölüp odak dağıtmamak için).
DERS_LIMIT_ESIK_DK = 240
DERS_LIMIT_KISA_GUN = 3
DERS_LIMIT_MAKS_GUN = 5
# Süre doldurma (KURAL 4): tek bir derse tek günde en fazla 150 dk / 90 soru.
MAKS_DERS_GUN_DAKIKA = 150
MAKS_DERS_GUN_SORU = 90

# Günlük mikro rutinler ana ders kotasında sayılır: Paragraf→Türkçe,
# Problem→Matematik, Geometri 10'lu→Geometri. Anahtar: küçük harf alt metin.
RUTIN_ANA_DERSLERI = {
    "paragraf": "TYT Türkçe",
    "problem": "TYT Matematik",
    "geometri 10": "TYT Geometri",
    "geometri 10'lu": "TYT Geometri",
}


def rutin_ana_dersi(mikro, ders=None):
    """Günlük mikro rutinin ait olduğu ana dersi döndürür (KURAL 4).

    Paragraf → TYT Türkçe, Problem → TYT Matematik, Geometri 10'lu → TYT
    Geometri. Rutin değilse verilen ders aynen döner. Böylece rutin, ana dersi
    zaten varsa AYRI bir ders kotası açmaz.
    """
    if not mikro:
        return ders
    metin = str(mikro).strip().lower()
    for parca, ana_ders in RUTIN_ANA_DERSLERI.items():
        if parca in metin:
            return ana_ders
    return ders

# --- Pekiştirme pratiği (KURAL 3) -------------------------------------------
# Pekiştirme derslerinde sorular kolay ➔ orta ➔ zor sırasıyla ilerler.
ZORLUK_SIRASI = ("kolay", "orta", "zor")

# FAZ 6C: aralıklı tekrar + yanlış soru defteri entegrasyonu.
MAKS_TEKRAR_GOREV_GUN = 2  # günde en fazla 2 tekrar/defter görevi
MAKS_TEKRAR_SORU = 10  # tek görevde en fazla 10 kaynak soru
TEKRAR_DK_PAYI = 0.30  # günün kapasitesinin en fazla %30'u tekrara ayrılır
MIN_TEKRAR_DK = 15  # tekrar için ayrılacak en az süre (kapasite izin verirse)
TEKRAR_HEDEF_SORU = 5  # bir aralıklı tekrar kaydının soru hedefi

# Günlük rutin görevler: aynı rutin bir güne en fazla `max_daily_limit` kez
# yerleştirilir (örn. günde tek "Günlük Paragraf" slotu). Anahtar mikro konu
# adıdır; istenirse `(ders, mikro konu)` biçiminde ders bazlı da tanımlanır.
GUNLUK_RUTINLER = {
    "Günlük Paragraf": {"max_daily_limit": 1},
}

# "Temel Eksik" (ön koşul) etiketlerinin metin biçimleri.
TEMEL_EKSIK_AYRACI = " - Eksikler: "
TEMEL_EKSIK_ESKI_AYRACI = " (Temel Eksik: "

GUN_ADLARI = (
    "Pazartesi",
    "Salı",
    "Çarşamba",
    "Perşembe",
    "Cuma",
    "Cumartesi",
    "Pazar",
)

_ZAMAN_KALIBI = "%Y-%m-%d %H:%M:%S"


class PlanHatasi(ValueError):
    """Geçersiz planlama girdisi."""


# ==============================================================================
# YAPILANDIRMA
# ==============================================================================
_db_yolu = VARSAYILAN_DB_YOLU
_baglanti_fabrikasi = None
_saat_fonksiyonu = None


def db_yolu_ayarla(yol):
    global _db_yolu
    _db_yolu = yol or VARSAYILAN_DB_YOLU


def baglanti_fabrikasi_ayarla(fabrika):
    global _baglanti_fabrikasi
    _baglanti_fabrikasi = fabrika


def saat_fonksiyonu_ayarla(fonksiyon):
    global _saat_fonksiyonu
    _saat_fonksiyonu = fonksiyon


def simdi():
    if _saat_fonksiyonu is not None:
        return _saat_fonksiyonu()
    return datetime.now(TR_TZ)


def _zaman_yaz(deger):
    return deger.strftime(_ZAMAN_KALIBI) if deger else None


@contextmanager
def _baglanti():
    if _baglanti_fabrikasi is not None:
        conn = _baglanti_fabrikasi()
        kendi = False
    else:
        conn = sqlite3.connect(_db_yolu, timeout=20, check_same_thread=False)
        kendi = True
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        if kendi:
            conn.close()


@contextmanager
def _islem(conn):
    if conn.in_transaction:
        yield
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.commit()
    except Exception:
        conn.rollback()
        raise


_SEMA = """
CREATE TABLE IF NOT EXISTS calisma_musaitlik (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    gun INTEGER NOT NULL,
    dakika INTEGER NOT NULL DEFAULT 0,
    guncelleme_zamani TEXT,
    UNIQUE(ogrenci_id, gun),
    FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
)
"""

_INDEKSLER = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_musaitlik_tek"
    " ON calisma_musaitlik(ogrenci_id, gun)",
)

# KURAL 1 (v2.1): "telafisi kapatıldı" damgası. Biten konu yalnızca bu konuda
# KAPATILANDAN DAHA YENİ bir denemede (deneme_id > son_kapatilan_deneme_id)
# yanlış yapılırsa yeniden TEK SEFERLİK telafi kartıyla plana döner.
_SEMA_TELAFI = """
CREATE TABLE IF NOT EXISTS telafi_deneme_takibi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    ders TEXT NOT NULL,
    mikro_konu TEXT NOT NULL,
    son_kapatilan_deneme_id INTEGER NOT NULL DEFAULT 0,
    kapatilma_zamani TEXT,
    UNIQUE(ogrenci_id, ders, mikro_konu)
)
"""

_INDEKSLER_TELAFI = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_telafi_tek"
    " ON telafi_deneme_takibi(ogrenci_id, ders, mikro_konu)",
)


def init_db():
    """Müsaitlik ve telafi takip tablosunu idempotent kurar (veri silmez)."""
    with _baglanti() as conn:
        with _islem(conn):
            conn.execute(_SEMA)
            conn.execute(_SEMA_TELAFI)
            for sorgu in _INDEKSLER:
                conn.execute(sorgu)
            for sorgu in _INDEKSLER_TELAFI:
                conn.execute(sorgu)
    return True


def telafi_kapatilan_denemeler(ogrenci_id):
    """Öğrenci için {(ders, mikro): son_kapatilan_deneme_id} haritası.

    Tablo yoksa (eski/test veritabanı) boş sözlük döner; planlama bozulmaz.
    """
    sonuc = {}
    if ogrenci_id in (None, "", 0):
        return sonuc
    try:
        with _baglanti() as conn:
            satirlar = conn.execute(
                "SELECT ders, mikro_konu, son_kapatilan_deneme_id"
                " FROM telafi_deneme_takibi WHERE ogrenci_id = ?",
                (ogrenci_id,),
            ).fetchall()
    except sqlite3.Error:
        return sonuc
    for satir in satirlar:
        try:
            ders = satir["ders"]
            mikro = satir["mikro_konu"]
            deneme_id = int(satir["son_kapatilan_deneme_id"] or 0)
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if ders and mikro:
            sonuc[(str(ders), str(mikro))] = deneme_id
    return sonuc


def telafi_deneme_kapat(ogrenci_id, ders, mikro_konu, deneme_id):
    """Telafi görevi tamamlandığında deneme_id'yi "kapatıldı" olarak işaretler.

    Aynı (ders, mikro) için yalnızca DAHA BÜYÜK deneme_id saklanır; böylece
    eski bir deneme yeni kapatmayı ezmez. İdempotenttir.
    """
    if ogrenci_id in (None, "", 0) or not (ders and mikro_konu):
        return False
    try:
        did = int(deneme_id or 0)
    except (TypeError, ValueError):
        did = 0
    if did <= 0:
        return False
    zaman = _zaman_yaz(simdi())
    try:
        with _baglanti() as conn:
            with _islem(conn):
                mevcut = conn.execute(
                    "SELECT id, son_kapatilan_deneme_id FROM telafi_deneme_takibi"
                    " WHERE ogrenci_id = ? AND ders = ? AND mikro_konu = ?",
                    (ogrenci_id, str(ders), str(mikro_konu)),
                ).fetchone()
                if mevcut is None:
                    conn.execute(
                        "INSERT INTO telafi_deneme_takibi (ogrenci_id, ders,"
                        " mikro_konu, son_kapatilan_deneme_id, kapatilma_zamani)"
                        " VALUES (?, ?, ?, ?, ?)",
                        (ogrenci_id, str(ders), str(mikro_konu), did, zaman),
                    )
                elif did > int(mevcut["son_kapatilan_deneme_id"] or 0):
                    conn.execute(
                        "UPDATE telafi_deneme_takibi SET son_kapatilan_deneme_id = ?,"
                        " kapatilma_zamani = ? WHERE id = ?",
                        (did, zaman, mevcut["id"]),
                    )
    except sqlite3.Error:
        return False
    return True


def biten_konu_deneme_hedefleri(deneme_yanlislari, biten, kapatilan):
    """Biten konularda YENİ deneme yanlışlarını tespit eder (KURAL 1).

    `deneme_yanlislari`: `[{'ders','konu','deneme_id','yanlis_adedi'}, ...]`.
    `biten`: {(ders, mikro_konu)} — %100 biten konular.
    `kapatilan`: {(ders, mikro_konu): son_kapatilan_deneme_id}.

    Dönen: {(ders, mikro_konu): (en_yeni_deneme_id, toplam_yanlis)}.
    Yalnızca `deneme_id > son_kapatilan_deneme_id` olan yanlışlar alınır;
    böylece kapatılmış bir deneme bir sonraki planda yeniden tetiklenmez.
    """
    sonuc = {}
    if not deneme_yanlislari:
        return sonuc
    for kayit in deneme_yanlislari:
        if not isinstance(kayit, dict):
            continue
        ders = str(kayit.get("ders") or "").strip()
        konu = str(
            kayit.get("konu")
            or kayit.get("konu_adi")
            or kayit.get("mikro_konu")
            or ""
        ).strip()
        if not (ders and konu):
            continue
        if (ders, konu) not in biten:
            continue
        try:
            did = int(kayit.get("deneme_id") or 0)
        except (TypeError, ValueError):
            did = 0
        if did <= 0:
            continue
        esik = int((kapatilan or {}).get((ders, konu), 0) or 0)
        if did <= esik:
            continue
        try:
            yanlis = max(0, int(kayit.get("yanlis_adedi") or kayit.get("yanlis") or 0))
        except (TypeError, ValueError):
            yanlis = 0
        mevcut = sonuc.get((ders, konu))
        if mevcut is None:
            sonuc[(ders, konu)] = (did, yanlis)
        else:
            sonuc[(ders, konu)] = (max(mevcut[0], did), max(mevcut[1], yanlis))
    return sonuc



# ==============================================================================
# GÜNLÜK MÜSAİTLİK
# ==============================================================================
def _gun_dogrula(gun):
    try:
        deger = int(gun)
    except (TypeError, ValueError):
        raise PlanHatasi("Gün 1-7 arasında olmalıdır (Pazartesi=1).") from None
    if deger < 1 or deger > 7:
        raise PlanHatasi("Gün 1-7 arasında olmalıdır (Pazartesi=1).")
    return deger


def _dakika_dogrula(dakika):
    if isinstance(dakika, bool):
        raise PlanHatasi("Müsaitlik süresi sayı olmalıdır.")
    try:
        deger = int(dakika)
    except (TypeError, ValueError):
        raise PlanHatasi("Müsaitlik süresi sayı olmalıdır.") from None
    if deger < 0 or deger > MAKS_GUNLUK_DAKIKA:
        raise PlanHatasi(
            "Müsaitlik 0 ile %d dakika arasında olmalıdır." % MAKS_GUNLUK_DAKIKA
        )
    return deger


def musaitlik_yukle(ogrenci_id):
    """Öğrencinin günlük müsaitliği: {1..7: dakika} (kayıt yoksa varsayılan)."""
    try:
        oid = int(ogrenci_id)
    except (TypeError, ValueError):
        raise PlanHatasi("Geçersiz öğrenci bilgisi.") from None
    sonuc = {gun: VARSAYILAN_GUNLUK_DAKIKA for gun in range(1, 8)}
    try:
        with _baglanti() as conn:
            satirlar = conn.execute(
                "SELECT gun, dakika FROM calisma_musaitlik WHERE ogrenci_id = ?",
                (oid,),
            ).fetchall()
    except sqlite3.Error:
        return sonuc
    for satir in satirlar:
        try:
            sonuc[int(satir["gun"])] = int(satir["dakika"])
        except (TypeError, ValueError):
            continue
    return sonuc


def musaitlik_kaydet(ogrenci_id, musaitlik, an=None):
    """Günlük müsaitliği kaydeder (0 dakika = dinlenme günü)."""
    try:
        oid = int(ogrenci_id)
    except (TypeError, ValueError):
        raise PlanHatasi("Geçersiz öğrenci bilgisi.") from None
    if not isinstance(musaitlik, dict) or not musaitlik:
        raise PlanHatasi("Müsaitlik bilgisi gün->dakika sözlüğü olmalıdır.")
    temiz = {}
    for gun, dakika in musaitlik.items():
        temiz[_gun_dogrula(gun)] = _dakika_dogrula(dakika)
    zaman = _zaman_yaz(an or simdi())
    with _baglanti() as conn:
        with _islem(conn):
            for gun, dakika in temiz.items():
                conn.execute(
                    "INSERT INTO calisma_musaitlik (ogrenci_id, gun, dakika,"
                    " guncelleme_zamani) VALUES (?, ?, ?, ?)"
                    " ON CONFLICT(ogrenci_id, gun) DO UPDATE SET"
                    " dakika = excluded.dakika,"
                    " guncelleme_zamani = excluded.guncelleme_zamani",
                    (oid, gun, dakika, zaman),
                )
    return musaitlik_yukle(oid)


def musaitlik_esitle(ogrenci_id, dakika, an=None):
    """Tek bir günlük süreyi haftanın yedi gününe uygular (varsayılan)."""
    dakika = _dakika_dogrula(dakika)
    return musaitlik_kaydet(ogrenci_id, {gun: dakika for gun in range(1, 8)}, an=an)


def gun_musaitligi(tarih, musaitlik=None):
    """Bir tarihin müsaitlik süresi (dakika)."""
    if isinstance(tarih, str):
        tarih = datetime.strptime(tarih[:10], "%Y-%m-%d").date()
    musaitlik = musaitlik if musaitlik is not None else {}
    return int(musaitlik.get(tarih.weekday() + 1, VARSAYILAN_GUNLUK_DAKIKA))


# ==============================================================================
# KREDİ PUANI -> SORU KOTASI (arka planda; arayüzde gösterilmez)
# ==============================================================================
def kredi_normalize(kredi):
    """SORU_AGIRLIKLARI değerini 0-1 aralığına indirger.

    Kaynaktaki değerler 1.5 - 99.5 aralığında; en yüksek değer (Paragraf 99.5)
    0-100 ölçeğinin üst sınırına denk gelir ve eski motor da `kredi x 10`
    formülüyle bu ölçeği kullanıyordu. Bu nedenle 100'e bölünerek normalize
    edilir. Değer zaten 0-1 aralığındaysa olduğu gibi korunur.
    """
    try:
        deger = float(kredi)
    except (TypeError, ValueError):
        deger = 10.0
    if deger <= 1.0:
        return max(0.0, min(1.0, deger))
    return max(0.0, min(1.0, deger / KREDI_MAKS))


def makro_soru_hedefi(kredi, carpan=None):
    """Makro konu toplam soru hedefi = 100 x carpan x normalize(kredi).

    Eski 40 soruluk yapay minimum kaldırıldı; alt sınır yoktur. `carpan`
    verilmezse modül sabiti (`SORU_CARPANI`) kullanılır.
    """
    if carpan is None:
        carpan = SORU_CARPANI
    normalize = kredi_normalize(kredi)
    hedef = 100.0 * float(carpan) * normalize
    return max(0, int(round(hedef / 5.0) * 5))


def mikro_hedeflere_dagit(makro_hedef, mikrolar, konu_sureleri=None, zorluklar=None):
    """Makro konu hedefini mikro konulara ağırlıklı olarak paylaştırır.

    Ağırlık = konu süresi x zorluk çarpanı. Yuvarlama artıkları en büyük
    kalan yöntemiyle dağıtıldığı için mikro hedeflerin toplamı makro hedefe
    EŞİTTİR.
    """
    konu_sureleri = konu_sureleri or {}
    zorluklar = zorluklar or {}
    liste = [m for m in (mikrolar or []) if m]
    if not liste:
        return {}
    try:
        makro_hedef = max(0, int(makro_hedef or 0))
    except (TypeError, ValueError):
        makro_hedef = 0
    if makro_hedef == 0:
        return {m: 0 for m in liste}
    agirliklar = {}
    for mikro in liste:
        sure = konu_sureleri.get(mikro, task_steps.VARSAYILAN_KONU_SURESI_DK)
        try:
            sure = max(1.0, float(sure))
        except (TypeError, ValueError):
            sure = float(task_steps.VARSAYILAN_KONU_SURESI_DK)
        try:
            zorluk = max(0.5, float(zorluklar.get(mikro, 1.0)))
        except (TypeError, ValueError):
            zorluk = 1.0
        agirliklar[mikro] = sure * zorluk
    toplam_agirlik = sum(agirliklar.values())
    ham = {m: makro_hedef * agirliklar[m] / toplam_agirlik for m in liste}
    sonuc = {m: int(ham[m]) for m in liste}
    kalan = makro_hedef - sum(sonuc.values())
    if kalan:
        sirali = sorted(liste, key=lambda m: (ham[m] - sonuc[m]), reverse=True)
        for i in range(kalan):
            sonuc[sirali[i % len(sirali)]] += 1
    return sonuc


def mikro_soru_hedefi(makro_kredi, mikrolar, mikro, konu_sureleri=None,
                      zorluklar=None):
    """Tek mikro konunun soru hedefi (makro kotanın payı)."""
    dagilim = mikro_hedeflere_dagit(
        makro_soru_hedefi(makro_kredi), mikrolar, konu_sureleri, zorluklar
    )
    return dagilim.get(mikro, 0)

    return int(musaitlik.get(tarih.weekday() + 1, VARSAYILAN_GUNLUK_DAKIKA))



# ==============================================================================
# PLAN MOTORU
# ==============================================================================
MAKS_GOREV_SORU = 40


def _tarih_oku(deger):
    if isinstance(deger, datetime):
        return deger.date()
    if isinstance(deger, date):
        return deger
    return datetime.strptime(str(deger)[:10], "%Y-%m-%d").date()


def gorev_kalan_soru(gorev):
    """Önceki görevin devredilebilir kalan soru miktarı."""
    hedef = int(gorev.get("hedef_soru") or 0)
    gercek = int(gorev.get("gercek_soru") or 0)
    devredilen = int(gorev.get("devredilen_soru") or 0)
    return max(0, hedef - gercek - devredilen)


def _makro_bul(mufredat, ders, mikro):
    for makro, mikrolar in (mufredat.get(ders) or {}).items():
        if mikro in (mikrolar or []):
            return makro
    return "Genel Tekrar"


def _mikro_hedef(ders, makro, mikro, mufredat, soru_agirliklari, konu_sureleri):
    mikrolar = (mufredat.get(ders) or {}).get(makro) or []
    kredi = (soru_agirliklari or {}).get(makro, 10.0)
    if not mikrolar or mikro not in mikrolar:
        return makro_soru_hedefi(kredi)
    return mikro_soru_hedefi(kredi, mikrolar, mikro, konu_sureleri)


# ==============================================================================
# PEKİŞTİRME / EZBER DENGESİ
# ==============================================================================
def ders_soru_orani(ders, pedagoji=None):
    """Dersin soru yükü oranı (ezber 0.6, pekiştirme 1.0).

    Ezber ağırlıklı derslerde (tarih, biyoloji, felsefe ...) soru sayısı
    azaltılır; kazanılan süre not/tekrar adımına gider. Pekiştirme
    derslerinde (matematik, geometri, fizik, dil bilgisi) tam kota korunur.
    """
    if task_steps.ders_ezber_mi(ders, pedagoji):
        return EZBER_SORU_ORANI
    return 1.0


def gorev_soru_tavani(ders, pedagoji=None):
    """Tek görevde istenebilecek en fazla soru (ezberde daha düşük)."""
    if task_steps.ders_ezber_mi(ders, pedagoji):
        return EZBER_GOREV_SORU_TAVANI
    return MAKS_GOREV_SORU


def _on_kosul_hazir(mikro, bilinen, kurallar, derinlik=0):
    """Ön koşulları tamamlanmamış konuya geçilmez."""
    kural = (kurallar or {}).get(mikro)
    if not kural or derinlik > 4:
        return True
    for ok in kural.get("on_kosul") or []:
        if ok not in bilinen:
            return False
    return True


def alt_listesi(mikro, mikro_alt):
    """Ana konunun mikro konuları (alt başlıkları); yoksa boş liste."""
    return [a for a in (mikro_alt or {}).get(mikro, []) or [] if a]


def mikro_soru_paylari(ana_hedef, mikrolar, agirliklar=None):
    """Ana konunun soru hedefini mikro konulara tam sayı olarak paylaştırır.

    FAZ 5D: aynı makro hedef her mikro konuya tekrar UYGULANMAZ; payların
    toplamı ana hedefe eşittir (yuvarlama artığı en büyük kalan yöntemiyle
    dağıtılır). Ağırlık verilmezse eşit bölünür.
    """
    liste = [m for m in (mikrolar or []) if m]
    if not liste:
        return {}
    agirliklar = agirliklar or {}
    return mikro_hedeflere_dagit(
        ana_hedef, liste, {m: agirliklar.get(m, 1.0) for m in liste}
    )


def _tek_alt(deger):
    """'A||B' biçimindeki alt başlık metninden tek mikro konu adı çıkarır."""
    parcalar = [p.strip() for p in str(deger or "").split("||") if p.strip()]
    return parcalar[0] if len(parcalar) == 1 else None


def _gorev_turu_tahmin(gorev):
    """Görev türünü mevcut alandan okur; yoksa tanımdan çıkarır."""
    tur = (gorev.get("gorev_turu") or "").strip()
    if tur:
        return tur
    tanim = str(gorev.get("gorev_tanimi") or "")
    if "🧩" in tanim:
        return "soru"
    if "anlatım" in tanim.lower() or "UYGULAMA" in tanim or "📌" in tanim:
        return "anlatim"
    return "anlatim"


def mikro_gorev_tanimi(ana_konu, mikro, soru, gorev_turu="anlatim"):
    """Tek mikro konuya ait görev metni (ana konu ➔ mikro konu).

    KURAL 2: öğrenme görevinin İLK adımı konu anlatımıdır; kart metni
    "Konu Anlatımı (Video/Kaynak)" ile başlar.
    """
    if gorev_turu == "anlatim":
        kuyruk = ", ardından %d soru çöz" % int(soru) if int(soru or 0) > 0 else ""
        return (
            "📌 %s ➔ %s ➔ %s: izle / oku ve kısa özet çıkar%s."
            % (BILINMEYEN_KONU_ADIMI, ana_konu, mikro, kuyruk)
        )
    if gorev_turu == "tekrar":
        return "🔄 %s ➔ %s: özet notlarını oku." % (ana_konu, mikro)
    return "🧩 %s ➔ %s: %d soru çöz." % (ana_konu, mikro, int(soru or 0))


def mikro_gorevlere_ayir(
    gorevler_or_gorev,
    mikro_alt=None,
    konu_sureleri=None,
    tamamlanan_altlar=None,
    agirliklar=None,
    ogrenci_id=None,
):
    """Ana konu seviyesindeki görevleri MİKRO KONU başına ayrı görevlere böler.

    FAZ 5D: Her mikro konu kendi görev kaydı, kendi süresi ve kendi soru
    hedefiyle üretilir. Ana konunun soru hedefi mikro konulara paylaştırılır;
    toplam korunur. Tek mikro içeren görev olduğu gibi döner (idempotent).

    `gorevler_or_gorev` tek bir görev sözlüğü veya görev listesi olabilir.
    `ogrenci_id` verilirse her mikro konunun anlatım süresi gerçek ölçüm
    medyanıyla kişiselleştirilir (tek süre kaynağı: `task_steps`).
    """
    tek = isinstance(gorevler_or_gorev, dict)
    kaynak = [gorevler_or_gorev] if tek else list(gorevler_or_gorev or [])
    sonuc = []
    for gorev in kaynak:
        sonuc.extend(
            _gorevi_mikrolara_ayir(
                gorev, mikro_alt, konu_sureleri, tamamlanan_altlar, agirliklar,
                ogrenci_id=ogrenci_id,
            )
        )
    return sonuc


def _gorevi_mikrolara_ayir(gorev, mikro_alt, konu_sureleri, tamamlanan_altlar,
                           agirliklar, ogrenci_id=None):
    if not isinstance(gorev, dict):
        return []
    ders = gorev.get("ders")
    ana = (gorev.get("mikro_konu") or "").strip()
    if not ders or not ana:
        return [gorev]
    # Tekrar / deneme tekrarı görevleri ana konu düzeyinde kalır.
    if (gorev.get("pedagoji_turu") or "") == "Tekrar":
        return [gorev]
    if (gorev.get("makro_konu") or "") == "Deneme Tekrarı":
        return [gorev]

    mevcut = [p.strip() for p in str(gorev.get("alt_konu") or "").split("||") if p.strip()]
    if mevcut:
        alts = mevcut
    else:
        alts = [
            a for a in alt_listesi(ana, mikro_alt)
            if (ders, ana, a) not in (tamamlanan_altlar or set())
        ]
    if not alts:
        return [gorev]
    if len(alts) == 1:
        if mevcut:
            return [gorev]  # zaten tek mikro konu
        yeni = dict(gorev)
        yeni["alt_konu"] = alts[0]
        yeni["gorev_turu"] = _gorev_turu_tahmin(gorev)
        yeni["gorev_tanimi"] = mikro_gorev_tanimi(
            ana, alts[0], gorev.get("hedef_soru") or 0, yeni["gorev_turu"]
        )
        # FAZ 5D: ana konunun süresi mikro konuya KOPYALANMAZ.
        if yeni.get("konu_suresi_dk") in (None, "", 0):
            yeni["konu_suresi_dk"] = task_steps.mikro_anlatim_suresi(
                ogrenci_id, ders, ana, alts[0], konu_sureleri
            )
        yeni.setdefault("mikro_hedef_soru", int(gorev.get("hedef_soru") or 0))
        return [yeni]

    hedef = max(0, int(gorev.get("hedef_soru") or 0))
    paylar = mikro_soru_paylari(hedef, alts, agirliklar)

    gorev_turu = _gorev_turu_tahmin(gorev)
    parcalar = []
    for alt in alts:
        yeni = dict(gorev)
        yeni["alt_konu"] = alt
        yeni["hedef_soru"] = int(paylar.get(alt, 0))
        # Mikro konunun TAM hedefi (görev bu hedefin parçası olabilir).
        yeni["mikro_hedef_soru"] = int(paylar.get(alt, 0))
        yeni["gorev_turu"] = gorev_turu
        # FAZ 5D: süre mikro konu bazında; ana konu süresi eşit bölünmez.
        yeni["konu_suresi_dk"] = task_steps.mikro_anlatim_suresi(
            ogrenci_id, ders, ana, alt, konu_sureleri
        )
        yeni["gorev_tanimi"] = mikro_gorev_tanimi(
            ana, alt, yeni["hedef_soru"], gorev_turu
        )
        parcalar.append(yeni)
    return parcalar


def _gorev_uret(
    tur,
    ders,
    makro,
    mikro,
    tarih,
    soru,
    kaynak_gorev_id,
    ogrenci_id,
    konu_sureleri,
    alt_konu=None,
    pedagoji=None,
    alt_sayisi=None,
    sure_dk=None,
    mikro_hedef=None,
    kaynaklar=None,
    eksikler=None,
    ilk_kez=False,
    deneme_id=None,
    konu_anlatimi_aktif=True,
):
    """Görev sözlüğü + alt adımlar + planlanan süre.

    FAZ 5D: `alt_konu` tek bir MİKRO KONUdur; görev metni ana konu ➔ mikro
    konu biçiminde kurulur. `sure_dk` verilirse bu mikro konunun kendi
    anlatım süresi kullanılır (ana konu süresi mikro konulara paylaştırılmıştır).
    `mikro_hedef` mikro konunun TAM soru hedefidir; günlük görev bu hedefin
    yalnızca bir parçasını içerebilir.
    FAZ 6C: `kaynaklar` görevin beslendiği kayıtları taşır
    (`[{'tur': 'yanlis_soru'|'tekrar_kaydi', 'id': N}]`); görev tamamlanınca
    bağlı kayıtlar ilerletilir.
    `eksikler`: eksik ön koşul ("Temel Eksik") listesi. Kart etiketine
    "Polinomlar - Eksikler: Fonksiyonlar, Çarpanlara Ayırma" biçiminde eklenir;
    her ön koşul için AYRI görev kartı üretilmez.
    `ilk_kez`: konuya hiç çalışılmamış (sıfır ilerleme). Bu durumda kartın
    İLK adımı konu anlatımıdır: "Konu Anlatımı (Video/Kaynak)".
    `tur="telafi"`: biten konuda deneme yanlışı için açılan sınırlı
    "Eksik Kapatma" görevi (bkz. `telafi_hedefi`).
    """
    etiket = "%s ➔ %s" % (mikro, alt_konu) if alt_konu else mikro
    if eksikler:
        etiket = "%s%s%s" % (etiket, TEMEL_EKSIK_AYRACI, ", ".join(eksikler))
    # "Eksikler: ..." etiketinden sonra ikinci bir iki nokta olmaması için
    # birleşik etiketlerde ayırıcı olarak "→" kullanılır.
    ayirici = " →" if eksikler else ":"
    if tur == "tekrar":
        tanim = "🔄 %s: özet notlarını oku, hatırlatma sorularını çöz." % etiket
        soru = min(TEKRAR_HEDEF_SORU, max(0, int(soru or TEKRAR_HEDEF_SORU)))
        pedagoji = "Tekrar"
    elif tur == "yanlis":
        tanim = "🎯 %s: yanlış soru defterindeki %d soruyu yeniden çöz." % (
            etiket,
            soru,
        )
        pedagoji = "Tekrar"
    elif tur == "devir":
        tanim = "📌 %s konusundan %d soru çöz." % (etiket, soru)
    elif tur == "alarm":
        tanim = (
            "🔁 %s%s denemede yanlış yaptığın soruları incele ve %d soru çöz."
            % (etiket, ayirici, soru)
        )
    elif tur == "anlatim":
        if ilk_kez:
            # KURAL 2: sıfır ilerlemeli konuda kartın ilk adımı konu anlatımıdır.
            tanim = (
                "📌 %s ➔ %s: izle / oku ve kısa özet çıkar, ardından %d soru çöz."
                % (BILINMEYEN_KONU_ADIMI, etiket, soru)
            )
        else:
            tanim = (
                "📌 %s%s konu anlatımını izle ve kısa özet çıkar, ardından %d soru çöz."
                % (etiket, ayirici, soru)
            )
    elif tur == "telafi":
        # KURAL 1: biten konu yalnızca deneme yanlışıyla, sınırlı bir özel
        # ders/eksik kapatma görevi olarak plana döner.
        tanim = (
            "%s%s konusunda denemede yanlış yaptığın yerleri tekrar et ve"
            " %d soru çöz." % (TELAFI_ETIKETI, etiket, soru)
        )
        pedagoji = "Tekrar"
    elif tur == "pekistirme":
        # KURAL 2: %0 konunun ilk gününü takiben 24-48 saat sonrasına planlanan
        # "Pekiştirme / Hatırlama Kontrolü (20 Soru)" kartı.
        tanim = (
            "%s (%d Soru): %s konusunu hatırla ve %d soru çöz."
            % (PEKISTIRME_ETIKETI, PEKISTIRME_SORU, etiket, soru)
        )
        pedagoji = "Pekiştirme"
    else:
        tanim = "📌 %s konusundan %d soru çöz." % (etiket, soru)
    gorev = {
        "ders": ders,
        "makro_konu": makro,
        "mikro_konu": mikro,
        "alt_konu": alt_konu,
        "gorev_tanimi": tanim,
        "hedef_soru": int(soru or 0),
        "pedagoji_turu": pedagoji or "Pekiştirme",
        "gorev_turu": tur if tur in ("anlatim", "tekrar") else "soru",
        "tarih": tarih.isoformat(),
        "kaynak_gorev_id": kaynak_gorev_id,
    }
    # v2.2 (FAZ 3): %0 konu -> görev TİPİ "konu_anlatimi" (zorunlu anlatım);
    # `gorev_turu` geriye dönük uyum için "anlatim" kalır. Bu semantik
    # yalnızca sınıf/alan bilgili planlarda uygulanır.
    if tur == "anlatim" and ilk_kez and konu_anlatimi_aktif:
        gorev["gorev_tipi"] = "konu_anlatimi"
    elif tur == "karma_tarama":
        gorev["gorev_tipi"] = "karma_tarama"
    else:
        gorev["gorev_tipi"] = "standart"
    if kaynaklar:
        gorev["kaynaklar"] = list(kaynaklar)
    if eksikler:
        # Kart açıklamasında birleştirilen ön koşullar (ayrı kart üretilmez).
        gorev["eksik_konular"] = list(eksikler)
    if tur == "telafi":
        # KURAL 1: telafi kartı; veritabanına yazılmayan ama plan içinde
        # tanınan işaretler (yeniden planlamada metin öneki de kullanılır).
        gorev["eksik_kapatma"] = True
        gorev["deneme_tekrari"] = True
        # Tetikleyen deneme_id görev meta verisine kaydedilir (KURAL 1 v2.1);
        # telafi tamamlanınca bu deneme "kapatıldı" olarak işaretlenir.
        try:
            if deneme_id not in (None, "", 0):
                gorev["deneme_id"] = int(deneme_id)
        except (TypeError, ValueError):
            pass
    if tur == "anlatim" and ilk_kez:
        # KURAL 2: sıfır ilerlemeli konu -> ilk adım konu anlatımı.
        gorev["ilk_kez_konu"] = True
    if tur == "pekistirme":
        gorev["pekistirme"] = True
    gorev["mikro_hedef_soru"] = int(mikro_hedef or gorev["hedef_soru"] or 0)
    if sure_dk not in (None, "", 0):
        gorev["konu_suresi_dk"] = int(sure_dk)
    if alt_sayisi is None:
        alt_sayisi = 1
        if alt_konu:
            alt_sayisi = max(
                1, len([p for p in str(alt_konu).split("||") if p.strip()])
            )
    sonuc = task_steps.gorev_zenginlestir(
        gorev,
        ogrenci_id=ogrenci_id,
        konu_sureleri=konu_sureleri,
        alt_sayisi=alt_sayisi,
    )
    # v2.2 (FAZ 3): ayrıştırılmış konu anlatımı / soru çözümü dakikaları.
    plan = sonuc.get("sure_plani") or {}
    sonuc["konu_anlatim_dk"] = int(plan.get("konu_anlatim_dk") or 0)
    sonuc["soru_cozum_dk"] = int(plan.get("soru_cozum_dk") or 0)
    return sonuc


def _gorev_metnini_tamamla(gorev, etiket):
    """Soru görevlerinin metnini hedef ve tahmini süreyle tamamlar.

    Eski "geçen programdan kalan X soru" ifadesi kaldırıldı; görev metni
    her zaman mikro konu (varsa alt başlık) + soru sayısı + tahmini süre
    biçimindedir: "📌 <alt başlık> konusundan N soru çöz (~M dk)."
    """
    if not gorev or gorev.get("gorev_turu") not in (None, "", "soru"):
        return gorev
    soru = int(gorev.get("hedef_soru") or 0)
    if soru <= 0:
        return gorev
    # Devam kartlarında da "Eksikler: ..." notu korunur (bkz. `eksikler`).
    eksikler = gorev.get("eksik_konular") or []
    if eksikler:
        etiket = "%s%s%s" % (etiket, TEMEL_EKSIK_AYRACI, ", ".join(eksikler))
    dk = int(gorev.get("tahmini_sure_dk") or 0)
    if dk > 0:
        gorev["gorev_tanimi"] = (
            "📌 %s konusundan %d soru çöz (~%d dk)." % (etiket, soru, dk)
        )
    else:
        gorev["gorev_tanimi"] = "📌 %s konusundan %d soru çöz." % (etiket, soru)
    return gorev




def rutin_gunluk_limiti(mikro, ders=None):
    """Günlük rutin görevin bir güne kaç kez yerleşebileceğini döndürür.

    `GUNLUK_RUTINLER` içinde önce `(ders, mikro konu)`, sonra yalnızca
    `mikro konu` anahtarı aranır. Rutin olmayan görevler için `None` döner
    (limit uygulanmaz). Varsayılan limit `max_daily_limit = 1`'dir: günlük
    rutin (örn. "Günlük Paragraf") günde TEK slota oturur.
    """
    if not mikro:
        return None
    kural = None
    if ders is not None:
        kural = GUNLUK_RUTINLER.get((ders, mikro))
    if kural is None:
        kural = GUNLUK_RUTINLER.get(mikro)
    if kural is None and ders is not None:
        for anahtar, aday in GUNLUK_RUTINLER.items():
            if isinstance(anahtar, tuple) and len(anahtar) >= 2 and anahtar[1] == mikro:
                kural = aday
                break
    if kural is None:
        return None
    try:
        return max(0, int(kural.get("max_daily_limit", 1)))
    except (TypeError, ValueError):
        return 1


def gunluk_tekillestir(gorevler, ana_konu_tekillestir=True):
    """Aynı gün içindeki görev tekrarlarını ayıklar (deduplication).

    Kurallar:
      1) Aynı gün + aynı ders + aynı GÖREV (mikro konu / alt konu / tür)
         yalnızca bir kez planlanır. Farklı mikro konular (FAZ 5D) korunur.
      2) Günlük rutin görevler (örn. "Günlük Paragraf") gün başına en fazla
         `max_daily_limit` slot alır (bkz. `GUNLUK_RUTINLER`).
      3) `ana_konu_tekillestir=True` ise aynı gün + aynı ders + aynı ANA KONU
         için ikinci bir kart üretilmez. Yedek motorlar ana konuyu mikro
         konulara bölerek aynı güne birden çok kart yazabildiği için bu kural
         yalnızca akıllı planlayıcıda ve motor çıktısının son süzgecinde
         (`ana_konu_tekillestir=False`) kapalı tutulur.

    Sıra korunur: gün içinde İLK gelen görev tutulur. Fonksiyon idempotenttir;
    ikinci kez uygulanması listeyi değiştirmez.
    """
    sonuc = []
    gorulen = set()
    rutin_sayaci = {}
    gun_konu = {}
    for gorev in gorevler or []:
        if not isinstance(gorev, dict):
            continue
        tarih = gorev.get("tarih") or gorev.get("gun")
        ders = gorev.get("ders")
        ana = gorev.get("mikro_konu")
        alt = gorev.get("alt_konu")
        tur = gorev.get("pedagoji_turu") or gorev.get("gorev_turu") or ""
        mikro_anahtar = (
            tarih,
            ders,
            ana,
            alt,
            tur,
            gorev.get("kaynak_gorev_id"),
        )
        if mikro_anahtar in gorulen:
            continue
        limit = rutin_gunluk_limiti(ana, ders)
        if limit is None:
            anahtar = (tarih, ders, ana)
            if ana_konu_tekillestir and anahtar in gun_konu:
                continue
            gun_konu[anahtar] = True
        else:
            anahtar = (tarih, ders, ana)
            if rutin_sayaci.get(anahtar, 0) >= limit:
                continue
            rutin_sayaci[anahtar] = rutin_sayaci.get(anahtar, 0) + 1
        gorulen.add(mikro_anahtar)
        sonuc.append(gorev)
    return sonuc


def gunluk_ders_limiti(kapasite_dk):
    """Bir güne atanabilecek FARKLI ders sayısı üst sınırı (KURAL 4).

    - 4 saat (240 dk) ve altı günlük çalışmada en fazla 3 farklı ders: 4 saat
      6 derse bölünüp odak dağıtılmaz.
    - Müsaitlik ne olursa olsun en fazla 5 farklı ders.
    - Dinlenme gününde (0 dk) ders planlanmaz.
    """
    try:
        dk = int(kapasite_dk or 0)
    except (TypeError, ValueError):
        dk = 0
    if dk <= 0:
        return 0
    if dk <= DERS_LIMIT_ESIK_DK:
        return DERS_LIMIT_KISA_GUN
    return DERS_LIMIT_MAKS_GUN


def gunluk_ders_siniri_uygula(gorevler, musaitlik=None):
    """Görev listesinde günlük FARKLI ders sayısını sınırlar (KURAL 4).

    Yedek motorlar blok sayısına göre plan ürettiği için aynı güne çok sayıda
    ders düşebilir; bu süzgeç gün içinde İLK gelen görevleri (motorun öncelik
    sırası) korur. Müsaitlik verilmezse varsayılan günlük süre kullanılır.
    Günlük rutinler de bir ders sayılır (TYT Türkçe paragraf dahil).
    """
    musaitlik = musaitlik or {}
    sonuc = []
    gun_ders = {}
    for gorev in gorevler or []:
        if not isinstance(gorev, dict):
            continue
        tarih = gorev.get("tarih") or gorev.get("gun")
        ders = gorev.get("ders")
        if tarih is None or not ders:
            sonuc.append(gorev)
            continue
        anahtar = str(tarih)
        try:
            kapasite = gun_musaitligi(_tarih_oku(tarih), musaitlik)
        except (TypeError, ValueError):
            kapasite = VARSAYILAN_GUNLUK_DAKIKA
        # KURAL 4: rutinler (Paragraf/Problem/Geometri) ana ders kotasında sayılır.
        etkin_ders = rutin_ana_dersi(gorev.get("mikro_konu"), ders)
        dersler = gun_ders.setdefault(anahtar, set())
        if etkin_ders not in dersler and len(dersler) >= gunluk_ders_limiti(kapasite):
            continue
        dersler.add(etkin_ders)
        sonuc.append(gorev)
    return sonuc


def _gun_anahtari(gorev):
    return str(gorev.get("tarih") or gorev.get("gun") or "")


def _ders_oncelik_puani(gorev):
    """Ders/görev öncelik puanı (KURAL 4 süre doldurma sıralaması).

    Düşük puan = daha öncelikli: 1) Kırmızı/Siyah/Mor alarm, 2) Deneme
    telafisi, 3) Ön koşul eksikliği, 4) Müfredat ağırlığı (varsayılan).
    """
    if telafi_gorevi_mi(gorev):
        return 2
    if gorev.get("eksik_konular"):
        return 3
    pedagoji = str(gorev.get("pedagoji_turu") or "")
    tanim = str(gorev.get("gorev_tanimi") or "")
    if "🔁" in tanim or pedagoji == "Tekrar":
        # Tekrar/defter/alarm kartları yüksek öncelikli sayılır.
        return 1
    return 4


def gunluk_ders_doldur(gorevler, musaitlik=None):
    """KURAL 4: günlük farklı ders limitini uygular ve süreyi doldurur.

    - Günlük aday ders havuzu limitten fazlaysa, dersler öncelik puanına göre
      (alarm > deneme telafisi > ön koşul eksiği > müfredat ağırlığı) sıralanır;
      en öncelikli `N` ders tutulur, diğer derslerin görevleri elenir.
    - Boşa çıkan süre, tutulan derslerin görev hacmi artırılarak doldurulur;
      ancak tek bir derse tek günde en fazla `MAKS_DERS_GUN_DAKIKA` (150 dk) ve
      `MAKS_DERS_GUN_SORU` (90 soru) uygulanır.

    Girdi listesi değiştirilmez; yeni liste döner. Rutinler (Paragraf/Problem/
    Geometri) ana ders kotasında sayılır.
    """
    musaitlik = musaitlik or {}
    # 1) Gün bazında grupla.
    gunler = {}
    sira = {}
    for idx, gorev in enumerate(gorevler or []):
        if not isinstance(gorev, dict):
            continue
        anahtar = _gun_anahtari(gorev)
        gunler.setdefault(anahtar, []).append((idx, gorev))
        sira[idx] = gorev

    tutulan_idx = set()
    for anahtar, kayitlar in gunler.items():
        try:
            tarih = _tarih_oku(anahtar)
            kapasite = gun_musaitligi(tarih, musaitlik)
        except (TypeError, ValueError):
            kapasite = VARSAYILAN_GUNLUK_DAKIKA
        limit = gunluk_ders_limiti(kapasite)
        if limit <= 0:
            continue
        # 2) Ders bazında en iyi (en düşük) öncelik puanı.
        ders_puan = {}
        for _idx, gorev in kayitlar:
            ders = rutin_ana_dersi(gorev.get("mikro_konu"), gorev.get("ders"))
            if not ders:
                continue
            puan = _ders_oncelik_puani(gorev)
            if ders not in ders_puan or puan < ders_puan[ders]:
                ders_puan[ders] = puan
        # 3) En öncelikli N dersi seç (eşitlikte ilk görülme sırası korunur).
        secilen_dersler = set(
            d
            for d, _p in sorted(ders_puan.items(), key=lambda c: (c[1],))[:limit]
        )
        # 4) Seçilmeyen derslerin görevlerini ele; tutulanları işaretle.
        for idx, gorev in kayitlar:
            ders = rutin_ana_dersi(gorev.get("mikro_konu"), gorev.get("ders"))
            if not ders or ders in secilen_dersler:
                tutulan_idx.add(idx)

    # 5) Tutulan görevleri sırayla koru.
    sonuc = [sira[idx] for idx in sorted(tutulan_idx) if idx in sira]

    # 6) Tek ders tavanı: aynı gün + ders için 150 dk / 90 soru aşılırsa küçült.
    gun_ders_soru, gun_ders_dk = {}, {}
    for gorev in sonuc:
        ders = rutin_ana_dersi(gorev.get("mikro_konu"), gorev.get("ders"))
        if not ders:
            continue
        anahtar = (_gun_anahtari(gorev), ders)
        hedef = int(gorev.get("hedef_soru") or 0)
        sure = int(gorev.get("tahmini_sure_dk") or 0)
        kalan_soru = MAKS_DERS_GUN_SORU - gun_ders_soru.get(anahtar, 0)
        kalan_dk = MAKS_DERS_GUN_DAKIKA - gun_ders_dk.get(anahtar, 0)
        if hedef > kalan_soru:
            gorev["hedef_soru"] = max(0, kalan_soru)
        if sure > kalan_dk and kalan_dk > 0:
            # Süre tavanı: soru hacmini de orantılı düşür.
            oran = float(kalan_dk) / float(sure)
            gorev["hedef_soru"] = min(
                int(gorev.get("hedef_soru") or 0),
                max(0, int(round(int(gorev.get("hedef_soru") or 0) * oran))),
            )
            gorev["tahmini_sure_dk"] = kalan_dk
        gun_ders_soru[anahtar] = gun_ders_soru.get(anahtar, 0) + int(
            gorev.get("hedef_soru") or 0
        )
        gun_ders_dk[anahtar] = gun_ders_dk.get(anahtar, 0) + int(
            gorev.get("tahmini_sure_dk") or 0
        )
    return sonuc


def temel_eksik_ayir(konu):
    """Alarm konusundan hedef konuyu ve eksik ön koşulları ayırır.

    Desteklenen biçimler:
        "Polinomlar - Eksikler: Fonksiyonlar, Çarpanlara Ayırma"
        "Polinomlar (Temel Eksik: Fonksiyonlar)"
    Dönen değer: `(hedef_konu, [eksik, ...])`. Etiket yoksa eksik listesi boştur.
    """
    metin = " ".join(str(konu or "").split())
    if not metin:
        return "", []
    for ayrac in (TEMEL_EKSIK_AYRACI.strip(), TEMEL_EKSIK_ESKI_AYRACI.strip()):
        if ayrac in metin:
            hedef, kalan = metin.split(ayrac, 1)
            kalan = kalan.strip().rstrip(")")
            eksikler = [
                parca.strip(" *'\"")
                for parca in kalan.split(",")
                if parca.strip(" *'\"")
            ]
            return hedef.strip(), eksikler
    return metin, []


def telafi_gorevi_mi(gorev):
    """Görev bir "Eksik Kapatma" (biten konu telafisi) kartı mı? (KURAL 1)

    Kart metni veritabanına yazılıp geri okunduğunda `eksik_kapatma` alanı
    taşınmaz; bu yüzden hem yeni (`🎯 Telafi / Eksik Kapatma:`), hem eski
    (`🩹`) metin önekleri hem de "Eksik Kapatma" işareti tanınır.
    """
    if not isinstance(gorev, dict):
        return False
    if gorev.get("eksik_kapatma"):
        return True
    metin = str(gorev.get("gorev_tanimi") or "")
    if metin.startswith(TELAFI_ETIKETI) or metin.startswith(TELAFI_ETIKETI_ESKI):
        return True
    return TELAFI_ISARET in metin


def telafi_hedefi(ders, ana, pedagoji=None, yanlis=0):
    """Biten konuda deneme yanlışı için açılan telafi görevinin soru hedefi.

    Hedef bilinçli olarak SINIRLIDIR: konu zaten %100 bitmiştir, amaç yeni
    konu öğrenmek değil denemede kaçan soruları kapatmaktır.

    Deneme yanlışı sayısı verilirse kota 15-30 soru arasında ölçeklenir:
    yanlış arttıkça telafi hacmi artar ama tek kartla sınırlı kalır. Yanlış
    bilgisi yoksa (alarm tabanlı eski akış) üst sınır `TELAFI_HEDEF_SORU`'dur.
    """
    tavan = gorev_soru_tavani(ders, pedagoji)
    try:
        y = max(0, int(yanlis or 0))
    except (TypeError, ValueError):
        y = 0
    hedef = TELAFI_MIN_SORU + min(TELAFI_MAKS_SORU - TELAFI_MIN_SORU, y * 3)
    if y <= 0:
        # Eski davranış: deneme yanlışı sayısı bilinmiyorsa makul varsayılan.
        hedef = min(hedef, TELAFI_HEDEF_SORU)
    return max(MIN_ANLAMLI_BLOK, min(int(tavan), int(hedef)))


def biten_konu_gorevi_mi(gorev):
    """Görev, biten konunun RUTİN (tekrar) kartı mı? (KURAL 1)

    Muhafaza edilenler:
      - deneme yanlışından doğan "Eksik Kapatma" (telafi) kartları,
      - günlük rutinler (örn. "Günlük Paragraf"),
      - tekrar görevleri (aralıklı tekrar takvimi ayrı bir pedagojik akıştır).
    """
    if not isinstance(gorev, dict):
        return False
    if telafi_gorevi_mi(gorev):
        return False
    if rutin_gunluk_limiti(gorev.get("mikro_konu"), gorev.get("ders")) is not None:
        return False
    if str(gorev.get("pedagoji_turu") or "") == "Tekrar":
        return False
    return True


def biten_konu_suzgeci(gorevler, biten_konular):
    """Biten (%100) konuların rutin görevlerini listeden ayıklar (KURAL 1).

    `biten_konular` (ders, mikro konu) çiftlerinden oluşur (bkz.
    `topic_progress.biten_konulari_yukle`). Konu yalnızca denemede yanlış
    çıkarsa telafi kartıyla plana döner; o kart süzgeçten etkilenmez.
    """
    biten = {(str(d), str(m)) for d, m in (biten_konular or ()) if d and m}
    if not biten:
        return list(gorevler or [])
    sonuc = []
    for gorev in gorevler or []:
        if not isinstance(gorev, dict):
            continue
        ders = gorev.get("ders")
        ana = gorev.get("mikro_konu")
        if (
            ders
            and ana
            and (str(ders), str(ana)) in biten
            and biten_konu_gorevi_mi(gorev)
        ):
            continue
        sonuc.append(gorev)
    return sonuc


def telafi_kapsanan_konular(onceki_gorevler):
    """Daha önce "Eksik Kapatma" kartı açılmış (ders, ana konu) çiftleri.

    Tamamlanmış telafi görevi hedefi kapattığı için bir daha açılmaz;
    tamamlanmamış görev DEVİR katmanıyla devam eder (yeni kart üretilmez).
    """
    sonuc = set()
    for gorev in onceki_gorevler or []:
        if not telafi_gorevi_mi(gorev):
            continue
        ders = gorev.get("ders")
        ana = gorev.get("mikro_konu")
        if ders and ana:
            sonuc.add((str(ders), str(ana)))
    return sonuc


def _alarm_gruplari(alarmlar, bilinen):
    """Alarm listesini (ders, hedef konu) bazında tekilleştirir.

    Aynı hedef konu için birden fazla uyarı -- özellikle birden fazla
    "Temel Eksik" -- TEK gruba indirilir; eksik listesi sırası korunarak
    birleştirilir. Böylece her ön koşul için ayrı görev kartı oluşmaz.

    Dönen liste: `[(ders, hedef_konu, [eksik, ...], bilinen_mi), ...]`
    """
    gruplar, sira = {}, []
    for alarm in alarmlar or []:
        if not isinstance(alarm, dict):
            continue
        ders = (alarm.get("ders") or "").strip()
        ham = alarm.get("hedef_konu") or alarm.get("konu") or alarm.get("mikro")
        ana, ayrilan = temel_eksik_ayir(ham)
        if not (ders and ana):
            continue
        eksikler = []
        for kaynak in (alarm.get("eksikler") or [], ayrilan):
            for eksik in kaynak:
                eksik = str(eksik or "").strip()
                if eksik and eksik not in eksikler:
                    eksikler.append(eksik)
        anahtar = (ders, ana)
        grup = gruplar.get(anahtar)
        if grup is None:
            grup = {"ders": ders, "ana": ana, "eksikler": [], "bilinen": ana in (bilinen or set())}
            gruplar[anahtar] = grup
            sira.append(anahtar)
        for eksik in eksikler:
            if eksik not in grup["eksikler"]:
                grup["eksikler"].append(eksik)
    return [
        (gruplar[anahtar]["ders"], gruplar[anahtar]["ana"],
         gruplar[anahtar]["eksikler"], gruplar[anahtar]["bilinen"])
        for anahtar in sira
    ]


def _tekrar_dk_limiti(kapasite):
    """FAZ 6C: bir günde tekrar/defter görevlerine ayrılabilecek dakika."""
    kapasite = int(kapasite or 0)
    if kapasite <= 0:
        return 0
    limiti = int(kapasite * TEKRAR_DK_PAYI)
    if limiti < MIN_TEKRAR_DK and kapasite >= 2 * MIN_TEKRAR_DK:
        limiti = MIN_TEKRAR_DK
    return max(0, min(kapasite, limiti))


def tekrar_havuzu(ogrenci_id, gun=None, bitis=None):
    """FAZ 6C: haftaya beslenecek tekrar kaynaklarını toplar.

    Dönen sözlük:
        `yanlis_sorular`     -> `wrong_questions.bekleyen_yanlis_sorular`
        `bekleyen_tekrarlar` -> `spaced_repetition.tekrar_listesi(Bekliyor)`

    Servisler yoksa veya hata verirse ilgili havuz boş döner; planlama
    bozulmaz. `gun`/`bitis` haftalık pencereyi belirler (gecikenler dahildir).
    """
    havuz = {"yanlis_sorular": [], "bekleyen_tekrarlar": []}
    if ogrenci_id in (None, "", 0):
        return havuz
    try:
        from services import wrong_questions
    except ImportError:  # pragma: no cover - modül yoksa entegrasyon kapalı
        wrong_questions = None
    if wrong_questions is not None:
        try:
            havuz["yanlis_sorular"] = wrong_questions.bekleyen_yanlis_sorular(
                ogrenci_id, gun=gun, bitis=bitis
            )
        except Exception:  # pragma: no cover - defter hatası planı bozmaz
            havuz["yanlis_sorular"] = []
    try:
        from services import spaced_repetition
    except ImportError:  # pragma: no cover
        spaced_repetition = None
    if spaced_repetition is not None:
        try:
            havuz["bekleyen_tekrarlar"] = spaced_repetition.tekrar_listesi(
                ogrenci_id,
                durum=spaced_repetition.DURUM_BEKLIYOR,
                baslangic=gun,
                bitis=bitis,
            )
        except Exception:  # pragma: no cover
            havuz["bekleyen_tekrarlar"] = []
    return havuz


def _tekrar_olusturma_tarihi(kayit):
    """Tekrar kaydının oluşma günü (`YYYY-MM-DD`) veya None."""
    metin = str(kayit.get("olusturma_zamani") or kayit.get("tarih") or "").strip()
    return metin[:10] if len(metin) >= 10 else None


def _pencere_ici_tekrar_mi(kayit, bas):
    """FAZ 6C: tekrar kaydı bu plan penceresinde mi oluştu?

    Öğrenme görevi bu pencerede tamamlandıysa aralıklı tekrarı SONRAKİ plana
    bırakılır; böylece aynı mikro konu aynı haftada hem öğrenme hem tekrar
    görevi olarak iki kez yer almaz (FAZ 5D kuralı korunur). Kayıt beklemede
    kalır, sonraki hafta gecikmiş olarak havuza girer.
    """
    tarih = _tekrar_olusturma_tarihi(kayit)
    if not tarih or bas is None:
        return False
    return tarih >= bas.isoformat()


def _tekrar_havuzunu_suz(havuz, bas):
    """Havuzdaki pencere içi tekrar kayıtlarını çıkarır (yanlış sorular kalır)."""
    if not isinstance(havuz, dict):
        return havuz
    temiz = dict(havuz)
    temiz["bekleyen_tekrarlar"] = [
        kayit
        for kayit in (havuz.get("bekleyen_tekrarlar") or [])
        if not _pencere_ici_tekrar_mi(kayit, bas)
    ]
    return temiz


def _tekrar_en_erken(kayit):
    """Tekrar görevinin yerleşebileceği en erken gün (`YYYY-MM-DD`) veya None."""
    try:
        return _tarih_oku(kayit.get("planlanan_tarih")).isoformat()
    except (TypeError, ValueError):
        return None


def _tekrar_gruplari(havuz, mufredat):
    """FAZ 6C havuzunu (ders, ana konu, mikro konu) bazında gruplar.

    Dönen liste:
        `[(ders, makro, ana, alt, yanlis_idler, tekrar_planlari), ...]`
    `tekrar_planlari` her bekleyen tekrar için `{'id', 'en_erken'}` taşır;
    `en_erken` tekrarın planlanan tarihidir (görev bu tarihten önce yerleşmez).
    Sıralama gecikmiş kayıtları önceleyecek biçimde deterministiktir.
    """
    gruplar = {}
    sira = {}

    def _grup(ders, ana, alt, makro):
        anahtar = (ders, ana, alt)
        if anahtar not in gruplar:
            gruplar[anahtar] = {
                "ders": ders,
                "ana": ana,
                "alt": alt,
                "makro": makro or _makro_bul(mufredat, ders, ana),
                "yanlis": [],
                "tekrar": [],
            }
            sira[anahtar] = len(sira)
        elif makro and not gruplar[anahtar]["makro"]:
            gruplar[anahtar]["makro"] = makro
        return gruplar[anahtar]

    for soru in (havuz or {}).get("yanlis_sorular") or []:
        ders = (soru.get("ders") or "").strip()
        ana = (soru.get("mikro_konu") or "").strip()
        if not (ders and ana):
            continue
        grup = _grup(ders, ana, _tek_alt(soru.get("alt_konu")), soru.get("makro_konu"))
        grup["yanlis"].append(int(soru["id"]))

    for tekrar in (havuz or {}).get("bekleyen_tekrarlar") or []:
        ders = (tekrar.get("ders") or "").strip()
        ana = (tekrar.get("mikro_konu") or "").strip()
        if not (ders and ana):
            continue
        grup = _grup(
            ders, ana, _tek_alt(tekrar.get("alt_konu")), tekrar.get("makro_konu")
        )
        grup["tekrar"].append(
            {
                "id": int(tekrar["id"]),
                "en_erken": _tekrar_en_erken(tekrar),
            }
        )

    siralanmis = sorted(
        gruplar.items(),
        key=lambda cift: (
            0 if cift[1]["yanlis"] else 1,
            -len(cift[1]["yanlis"]) - len(cift[1]["tekrar"]),
            sira[cift[0]],
        ),
    )
    return [
        (
            grup["ders"],
            grup["makro"],
            grup["ana"],
            grup["alt"],
            grup["yanlis"],
            grup["tekrar"],
        )
        for _anahtar, grup in siralanmis
    ]


def plan_uret(baglam, referans_tarihi=None):
    """Haftalık görev planını üretir (yalnızca bellek; veritabanına yazmaz).

    `referans_tarihi` (v2.2): verilirse `1 Mayıs` çift motor geçişi bu tarihe
    göre değerlendirilir; verilmezse `baglam["referans_tarihi"]` ya da plan
    başlangıcı kullanılır (simülatör/test desteği).

    FAZ 5D: Planlama birimi ANA KONU değil MİKRO KONUdur. Ana konunun soru
    hedefi ve işi mikro konularına paylaştırılır; her mikro konu kendi görev
    kaydı, kendi checklist'i, kendi soru hedefi ve kendi süresiyle planlanır.

    Öncelik sırası:
        1) Önceki programdan kalan gerçek eksikler (devir)
        2) Süresi geçmiş / bekleyen tekrar görevleri
        3) Deneme analizinden gelen kritik konular
        4) Ön koşulu tamamlanmış yeni ana konuların mikro konuları
        5) Pekiştirme gerektiren (öğrenilmiş) konuların mikro konuları
        6) Diğer düzenli çalışmalar (günlük paragraf)
    """
    if not isinstance(baglam, dict):
        raise PlanHatasi("Plan bağlamı sözlük olmalıdır.")
    ogrenci_id = baglam.get("ogrenci_id")
    bas = _tarih_oku(baglam.get("baslangic") or simdi().date())
    try:
        gun_sayisi = int(baglam.get("gun_sayisi") or GUN_SAYISI)
    except (TypeError, ValueError):
        gun_sayisi = GUN_SAYISI
    gun_sayisi = max(1, min(14, gun_sayisi))

    musaitlik = baglam.get("musaitlik") or {}
    konu_sureleri = baglam.get("konu_sureleri") or {}
    soru_agirliklari = baglam.get("soru_agirliklari") or {}
    mufredat = baglam.get("mufredat") or {}
    mikro_alt = baglam.get("mikro_alt") or {}
    tamamlanan_alt = set(baglam.get("tamamlanan_altlar") or [])
    gercek = dict(baglam.get("gercek_cozulen") or {})
    mikro_cozulen = {
        (str(anahtar[0]), str(anahtar[1]), str(anahtar[2])): int(deger or 0)
        for anahtar, deger in (baglam.get("mikro_cozulen") or {}).items()
        if isinstance(anahtar, (tuple, list)) and len(anahtar) >= 3
    }
    bilinen = set(baglam.get("bilinen_mikro") or [])
    # v2.2 (FAZ 3/4.5.4): konu anlatımı bitmiş (öğrenilmiş) konular %0 sayılmaz.
    ogrenilmis = set(baglam.get("ogrenilmis_konular") or ())
    kurallar = baglam.get("on_kosullar") or {}
    pedagoji_map = baglam.get("pedagoji") or {}
    try:
        paragraf_soru = max(0, int(baglam.get("paragraf_soru") or 20))
    except (TypeError, ValueError):
        paragraf_soru = 20
    onceki = list(baglam.get("onceki_gorevler") or [])
    # KURAL 1: %100 biten konular rutin programa geri dönmez. Biten konu
    # yalnızca denemede yanlış çıkarsa sınırlı bir "Eksik Kapatma" görevi alır.
    biten = {
        (str(ders), str(ana))
        for ders, ana in (baglam.get("biten_konular") or ())
        if ders and ana
    }

    # ------------------------------------------------------------------
    # v2.2 (FAZ 1-4): havuz kilidi, mutlak sıra, referans tarihi.
    # ------------------------------------------------------------------
    # v2.3 (FAZ 1.1): sınıf/alan boş gelse bile varsayılan atanır; böylece
    # TYT➔AYT çekirdek kilidi ve müfredat sırası asla devre dışı kalmaz.
    sinif_seviyesi = (
        baglam.get("sinif_seviyesi") or baglam.get("sinif") or "Mezun"
    )
    alan = baglam.get("alan") or baglam.get("hedef_alan") or "SAY"
    # v2.3 (FAZ 1.1): tek branş / çekirdek kilit / müfredat sırası VARSAYILAN
    # OLARAK HER ZAMAN aktiftir. Yalnızca eski planlar `legacy_mod=True` ile
    # açıkça kapatabilir.
    _legacy_mod = bool(baglam.get("legacy_mod", False))
    tek_brans_aktif = not _legacy_mod
    # Sınıf seviyesi + alan havuzunu süz (AYT/alan izolasyonu). Legacy planlarda
    # bu filtre uygulanmaz (özgün davranış korunur).
    if not _legacy_mod:
        mufredat = curriculum_meta.havuz_suz(mufredat, sinif_seviyesi, alan)
    # Mutlak müfredat sırası (1'den başlayan) ve makro ünite haritası.
    sira_map = baglam.get("sira_no_map") or curriculum_meta.sira_no_haritasi(mufredat)
    makro_map = baglam.get("makro_unite_map") or curriculum_meta.makro_haritasi(mufredat)
    # `1 Mayıs` tarih tetiklemeli çift motor: Mayıs–Haziran = kriz dönemi.
    _ref = referans_tarihi if referans_tarihi is not None else baglam.get(
        "referans_tarihi"
    )
    if _ref is None:
        aktif_tarih = bas
    elif isinstance(_ref, datetime):
        aktif_tarih = _ref.date()
    elif isinstance(_ref, date):
        aktif_tarih = _ref
    else:
        try:
            aktif_tarih = _tarih_oku(_ref)
        except (TypeError, ValueError):
            aktif_tarih = bas
    motor2_aktif = getattr(aktif_tarih, "month", None) in (5, 6)
    # Çekirdek TYT→AYT kilidi için normalize bilinen/biten kümeleri.
    bilinen_norm = {curriculum_meta.normalize_konu_adi(b) for b in bilinen if b}
    biten_mikro_adlari = {a for (_d, a) in biten if a}
    _sinif_sayi = curriculum_meta.sinif_seviyesi_sayisi(sinif_seviyesi)
    _biten_kumesi = {curriculum_meta.normalize_konu_adi(b) for b in biten_mikro_adlari}
    _bilinen_hepsi = bilinen_norm | _biten_kumesi
    # (_legacy_mod / tek_brans_aktif yukarıda FAZ 1.1 bölümünde tanımlandı.)

    def _cekirdek_acik(ders):
        if not tek_brans_aktif:
            return True
        # 11. sınıf istisnası: AYT konuları 12. sınıf TYT kilidiyle bloke edilmez.
        if _sinif_sayi == 11:
            return True
        if not str(ders).startswith("AYT"):
            return True
        return curriculum_meta.cekirdek_acik_mi(ders, bilinen_norm, _biten_kumesi)

    # Daha önce telafi kartı açılan konular (tamamlanmışsa yeniden açılmaz,
    # tamamlanmamışsa devir katmanıyla devam eder).
    telafi_kapsanan = telafi_kapsanan_konular(onceki)
    telafi_gorulen = set()
    # KURAL 1 (v2.1): deneme_id tabanlı telafi döngüsü. DB'deki kalıcı
    # "kapatıldı" damgaları + aktif programdaki TAMAMLANMIŞ telafi kartları
    # birleştirilir; tamamlanmamış telafi kartları devir katmanında devam eder
    # (yeni kart açılmaz).
    try:
        kapatilan = telafi_kapatilan_denemeler(ogrenci_id)
    except Exception:  # noqa: BLE001 - DB hatası planı bozmaz
        kapatilan = {}
    acik_telafi = set()
    for _gorev in onceki:
        if not telafi_gorevi_mi(_gorev):
            continue
        _ders = _gorev.get("ders")
        _ana = _gorev.get("mikro_konu")
        if not (_ders and _ana):
            continue
        _key = (str(_ders), str(_ana))
        if _gorev.get("durum") in (1, True, "1"):
            try:
                _did = int(_gorev.get("deneme_id") or 0)
            except (TypeError, ValueError):
                _did = 0
            if _did > int(kapatilan.get(_key, 0) or 0):
                kapatilan[_key] = _did
                # Tamamlanan telafi kartı deneme_id'yi KALICI olarak kapatır.
                try:
                    telafi_deneme_kapat(ogrenci_id, _key[0], _key[1], _did)
                except Exception:  # noqa: BLE001
                    pass
        else:
            acik_telafi.add(_key)
    # Yeni deneme yanlışları (biten konularda, kapatılandan daha yeni).
    deneme_hedefleri = biten_konu_deneme_hedefleri(
        baglam.get("deneme_yanlislari"), biten, kapatilan
    )
    uyarilar = []

    gunler = [bas + timedelta(days=i) for i in range(gun_sayisi)]
    kapasite = {gun: gun_musaitligi(gun, musaitlik) for gun in gunler}
    gun_dk = {gun: 0 for gun in gunler}
    gun_gorev = {gun: [] for gun in gunler}
    gun_yeni = {gun: 0 for gun in gunler}
    gun_yeni_ders = {gun: set() for gun in gunler}
    gun_mikro = {gun: set() for gun in gunler}
    # Tekilleştirme: aynı gün aynı ders + ana konu tek kartla planlanır.
    gun_ana = {gun: set() for gun in gunler}
    # Günlük rutin sayaçları: (ders, mikro konu) -> o günkü slot sayısı.
    gun_rutin = {gun: {} for gun in gunler}
    # FAZ 6C: günlük tekrar/defter kotası
    gun_tekrar = {gun: 0 for gun in gunler}
    gun_tekrar_dk = {gun: 0 for gun in gunler}
    gun_konu = {gun: set() for gun in gunler}
    # Ders dengesi ve günlük soru tavanı sayaçları
    gun_soru = {gun: 0 for gun in gunler}
    gun_ders = {gun: {} for gun in gunler}
    # KURAL 4: tek derse günlük 150 dk / 90 soru tavanı sayaçları.
    gun_ders_soru = {gun: {} for gun in gunler}
    gun_ders_dk = {gun: {} for gun in gunler}
    planlanan = set()
    kuyruk = {}

    # v2.3 (FAZ 2): aynı gün aynı ana branştan en fazla 1 ana konu görevi.
    # `tek_brans_aktif` FAZ 1.1 bölümünde bir kez tanımlandı.
    gun_brans_ana = {gun: set() for gun in gunler}
    # Rotasyon: yan derslerin ardışık günlerde sürekli tekrarını cezalandır.
    SIDE_BRANSLAR = {
        "Geometri", "Fizik", "Kimya", "Biyoloji", "Edebiyat",
        "Tarih", "Coğrafya", "Felsefe", "Din Kültürü",
    }
    karma_tarama_aktif = tek_brans_aktif and bool(
        baglam.get("karma_tarama", True)
    )

    def _kuyruga_ekle(oge):
        anahtar = oge.get("anahtar") or (oge["ders"], oge["ana"], oge["mikro"])
        mevcut_oge = kuyruk.get(anahtar)
        if mevcut_oge is None:
            kuyruk[anahtar] = oge
            return
        if oge["oncelik"] < mevcut_oge["oncelik"]:
            kuyruk[anahtar] = oge
            return
        # FAZ 6C: aynı öncelikli kaynaklı görevler (defter) tek görevde birleşir.
        if oge["oncelik"] == mevcut_oge["oncelik"] and oge.get("kaynaklar"):
            kaynaklar = mevcut_oge.setdefault("kaynaklar", [])
            for kaynak in oge["kaynaklar"]:
                if kaynak not in kaynaklar:
                    kaynaklar.append(kaynak)
            mevcut_oge["kalan"] = min(
                MAKS_TEKRAR_SORU, int(mevcut_oge["kalan"]) + int(oge["kalan"])
            )

    def _kalan_hedef(ders, makro, ana):
        hedef = _mikro_hedef(
            ders, makro, ana, mufredat, soru_agirliklari, konu_sureleri
        )
        # Pekiştirme/ezber dengesi: ezber derslerinde soru yükü azaltılır.
        oran = ders_soru_orani(ders, pedagoji_map.get((ders, ana)))
        hedef = int(round(hedef * oran))
        return max(0, hedef - int(gercek.get((ders, ana), 0) or 0))

    def _mikro_sure(ders, ana, alt):
        """Mikro konunun kendi anlatım süresi (TEK kaynak: `task_steps`).

        FAZ 5D: ana konunun süresi mikro konu sayısına BÖLÜNMEZ ve her mikro
        konuya KOPYALANMAZ (80 dk'lık konuyu 5'e bölüp 16 dk vermek gerçekçi
        değildir). Sıra: mikro konuya özel süre → en az 3 gerçek ölçümün
        medyanı → makul varsayılan.
        """
        return float(
            task_steps.mikro_anlatim_suresi(
                ogrenci_id, ders, ana, alt, konu_sureleri
            )
        )

    def _mikro_dilimi(ders, makro, ana):
        """Ana konunun kalan işini MİKRO KONULARA paylaştırır.

        Dönen liste: [(mikro_konu, kalan_soru, anlatim_dk, mikro_hedef), ...]
        - Tamamlanmış mikro konu yeniden üretilmez.
        - Her mikro konu kendi soru hedefini ve kendi anlatım süresini alır;
          soru paylarının toplamı ana konunun hedefini aşmaz.
        - `mikro_hedef`, mikro konunun TAM hedefidir; günlük görev bundan
          yalnızca bir parça alabilir (kalan sorular sonraki plana devreder).
        - Mikro konusu olmayan ana konularda tek parça (mikro=None) döner.
        """
        butce = _kalan_hedef(ders, makro, ana)
        if butce <= 0:
            return []
        tum_alts = alt_listesi(ana, mikro_alt)
        if not tum_alts:
            return [(None, butce, None, butce)]
        alts = [a for a in tum_alts if (ders, ana, a) not in tamamlanan_alt]
        if not alts:
            return []
        sureler = {alt: _mikro_sure(ders, ana, alt) for alt in alts}
        cozulen_mikro = {
            anahtar[2]: int(deger or 0)
            for anahtar, deger in mikro_cozulen.items()
            if anahtar[0] == ders and anahtar[1] == ana
        }
        if cozulen_mikro:
            hedef_tam = _mikro_hedef(
                ders, makro, ana, mufredat, soru_agirliklari, konu_sureleri
            )
            hedef_tam = int(
                round(
                    hedef_tam
                    * ders_soru_orani(ders, pedagoji_map.get((ders, ana)))
                )
            )
            paylar = mikro_soru_paylari(hedef_tam, tum_alts)
        else:
            paylar = mikro_soru_paylari(butce, alts)
        dilimler = []
        kalan_butce = butce
        for alt in alts:
            mikro_hedef = int(paylar.get(alt, 0))
            pay = mikro_hedef - int(cozulen_mikro.get(alt, 0))
            pay = max(0, min(pay, kalan_butce))
            if pay <= 0:
                continue
            kalan_butce -= pay
            dilimler.append((alt, pay, sureler.get(alt), mikro_hedef))
        return dilimler

    # 1) Devir + 2) tekrar (devir kendi mikro konusuna bağlanır)
    for gorev in onceki:
        ders = gorev.get("ders")
        ana = gorev.get("mikro_konu")
        if not (ders and ana) or gorev.get("durum"):
            continue
        # Günlük rutin (örn. "Günlük Paragraf") devredilmez: her gün yeniden
        # üretilir. Aksi hâlde aynı gün ikinci bir rutin kartı doğardı.
        if rutin_gunluk_limiti(ana, ders) is not None:
            continue
        makro = gorev.get("makro_konu") or _makro_bul(mufredat, ders, ana)
        mikro = _tek_alt(gorev.get("alt_konu"))
        kalan = gorev_kalan_soru(gorev)
        if telafi_gorevi_mi(gorev):
            # KURAL 1: Eksik Kapatma görevi kart kimliğini korur; hedef
            # (kalan soru) dolunca kendiliğinden programdan düşer.
            if kalan <= 0:
                continue
            _kuyruga_ekle({
                "oncelik": 1, "tur": "telafi", "ders": ders, "makro": makro,
                "ana": ana, "mikro": None, "kalan": kalan,
                "kaynak": gorev.get("id"), "pay_dk": None,
                "mikro_hedef": int(gorev.get("mikro_hedef_soru") or kalan),
                "eksik_kapatma": True,
            })
            continue
        if (gorev.get("pedagoji_turu") or "") == "Tekrar":
            _kuyruga_ekle({
                "oncelik": 2, "tur": "tekrar", "ders": ders, "makro": makro,
                "ana": ana, "mikro": mikro, "kalan": 5,
                "kaynak": gorev.get("id"), "pay_dk": None,
            })
            continue
        # KURAL 1: konu bu arada %100 bittiyse yarım kalan kart devredilmez;
        # konu ancak yeni bir deneme yanlışıyla telafi kartı olarak döner.
        if (str(ders), str(ana)) in biten:
            continue
        if kalan <= 0:
            continue
        # FAZ 5D: DEVAM görevi yalnızca SORU içerir; video/not tekrar edilmez.
        # (Ana konu "biliniyor" sayılmasa bile izleme adımı yeniden istenmez.)
        mikro_hedef = gorev.get("mikro_hedef_soru") or kalan
        _kuyruga_ekle({
            "oncelik": 1, "tur": "devir", "ders": ders, "makro": makro,
            "ana": ana, "mikro": mikro, "kalan": kalan,
            "kaynak": gorev.get("id"), "pay_dk": None,
            "mikro_hedef": int(mikro_hedef or kalan),
        })

    # 3a) KURAL 1 (v2.1): biten konuda YENİ deneme yanlışı → TEK telafi kartı.
    # Deneme yanlışı DOĞRUDAN (alarm serisinden bağımsız) tespit edilir; böylece
    # biten bir konuda tek denemede yanlış yapılması bile telafi tetikler.
    for (ders, ana), (deneme_id, yanlis) in sorted(
        deneme_hedefleri.items(), key=lambda c: c[1][0]
    ):
        if (ders, ana) in telafi_gorulen or (ders, ana) in acik_telafi:
            continue
        makro = _makro_bul(mufredat, ders, ana)
        hedef = telafi_hedefi(
            ders, ana, pedagoji_map.get((ders, ana), "Pekiştirme"), yanlis=yanlis
        )
        _kuyruga_ekle({
            "oncelik": 3,
            "tur": "telafi",
            "ders": ders,
            "makro": makro,
            "ana": ana,
            "mikro": None,
            "kalan": hedef,
            "kaynak": None,
            "pay_dk": None,
            "mikro_hedef": hedef,
            "eksik_kapatma": True,
            "deneme_id": int(deneme_id),
            "deneme_yanlis": int(yanlis),
        })
        telafi_gorulen.add((str(ders), str(ana)))

    # 3) Alarm konuları
    # Aynı hedef konu için birden fazla uyarı (özellikle birden fazla
    # "Temel Eksik") TEK görev kartında birleştirilir; eksikler kartın
    # açıklamasında listelenir: "Polinomlar - Eksikler: Fonksiyonlar, ...".
    for ders, ana, eksikler, ana_bilinen in _alarm_gruplari(
        baglam.get("alarm_konular") or [], bilinen
    ):
        makro = _makro_bul(mufredat, ders, ana)
        if (str(ders), str(ana)) in biten:
            # KURAL 1: %100 biten konu rutin olarak (anlatım/pekiştirme/yeniden
            # öğrenme) planlanmaz. Yalnızca denemede yanlış çıkarsa, haftada TEK
            # ve SINIRLI bir "Eksik Kapatma" görevi açılır; hedefi dolan görev
            # bir daha üretilmez (telafi_kapsanan + devir mekanizması).
            if eksikler:
                # Biten konu için ön koşul eksiği yok sayılır (konu kapanmış).
                continue
            if (str(ders), str(ana)) in telafi_kapsanan:
                continue
            if (str(ders), str(ana)) in telafi_gorulen:
                continue
            hedef = telafi_hedefi(
                ders, ana, pedagoji_map.get((ders, ana), "Pekiştirme")
            )
            _kuyruga_ekle({
                "oncelik": 3,
                "tur": "telafi",
                "ders": ders,
                "makro": makro,
                "ana": ana,
                "mikro": None,
                "kalan": hedef,
                "kaynak": None,
                "pay_dk": None,
                "mikro_hedef": hedef,
                "eksik_kapatma": True,
            })
            telafi_gorulen.add((str(ders), str(ana)))
            continue
        if eksikler:
            # Ön koşul eksiği mikro konulara BÖLÜNMEZ: tek kart üretilir.
            # Hedef tek görev tavanıyla sınırlanır; böylece aynı eksik kartı
            # günlere yayılıp çoğalmaz (konu kotası sonra normal plana girer).
            hedef = int(_kalan_hedef(ders, makro, ana) or 0)
            tavan_eksik = gorev_soru_tavani(
                ders, pedagoji_map.get((ders, ana), "Pekiştirme")
            )
            if hedef <= 0:
                hedef = max(10, paragraf_soru)
            hedef = max(MIN_ANLAMLI_BLOK, min(hedef, tavan_eksik))
            _kuyruga_ekle({
                "oncelik": 3,
                "tur": "alarm" if ana_bilinen else "anlatim",
                "ders": ders,
                "makro": makro,
                "ana": ana,
                "mikro": None,
                "kalan": hedef,
                "kaynak": None,
                "pay_dk": None,
                "mikro_hedef": hedef,
                "eksikler": eksikler,
            })
            continue
        dilimler = _mikro_dilimi(ders, makro, ana)
        if not dilimler:
            yedek = alt_listesi(ana, mikro_alt)[:1] or [None]
            dilimler = [(yedek[0], max(10, paragraf_soru), None, max(10, paragraf_soru))]
        for alt, pay, sure, mikro_hedef in dilimler:
            _kuyruga_ekle({
                "oncelik": 3,
                "tur": "alarm" if ana_bilinen else "anlatim",
                "ders": ders,
                "makro": makro,
                "ana": ana,
                "mikro": alt,
                "kalan": pay,
                "kaynak": None,
                "pay_dk": sure,
                "mikro_hedef": mikro_hedef,
            })

    # v2.3 (FAZ 1.2): dinamik kuyruk besleyicileri (yalnızca yeni modda).
    # Her ders için sıradaki TEK ana konunun ilk mikro altı kuyruğa girer; o
    # birim kalan<=0 ile düşünce aynı dersin bir sonraki alt/konusu beslenir.
    ders_birimler = {}
    ders_devam = {}
    ders_kuyrukta = {}

    def _birim_olustur(ders, makro, ana):
        """Ana konunun kalan işini sıralı mikro birimlere çevirir."""
        ilk_kez = not (
            int(gercek.get((ders, ana), 0) or 0)
            or any(
                int(deger or 0)
                for anahtar, deger in mikro_cozulen.items()
                if anahtar[0] == ders and anahtar[1] == ana
            )
            or (ders, ana) in ogrenilmis
        )
        _tur_ana = "pes" if (ders, ana) in ogrenilmis else "anlatim"
        _sira = sira_map.get((ders, ana), 10 ** 6)
        mkredi = curriculum_meta.makro_kredi_puani(makro)
        dilimler = [
            (alt, int(pay or 0), sure, mikro_hedef)
            for alt, pay, sure, mikro_hedef in _mikro_dilimi(ders, makro, ana)
            if (ders, ana, alt) not in planlanan
        ]
        if not dilimler:
            return []

        def _birlestir(grup):
            return {
                "ders": ders, "makro": makro, "ana": ana,
                "alt": grup[0][0],
                "kalan": sum(d[1] for d in grup),
                "pay_dk": grup[0][2],
                "mikro_hedef": sum(int(d[3] or 0) for d in grup),
                "ilk_kez": ilk_kez, "tur": _tur_ana,
                "sira_no": _sira, "makro_kredi": mkredi,
            }

        # v2.3 (FAZ 1.3): küçük mikro dilimleri >= MIN_KONU_BLOK_SORU olacak
        # biçimde birleştir ("5 soru ~11 dk" kırıntısı üretilmez).
        birimler = []
        grup = []
        grup_soru = 0
        for d in dilimler:
            grup.append(d)
            grup_soru += d[1]
            if grup_soru >= MIN_KONU_BLOK_SORU:
                birimler.append(_birlestir(grup))
                grup, grup_soru = [], 0
        if grup:
            if birimler:
                son = birimler[-1]
                son["kalan"] += grup_soru
                son["mikro_hedef"] += sum(int(d[3] or 0) for d in grup)
            else:
                birimler.append(_birlestir(grup))
        return birimler

    def _ders_birimleri_kur(ders, makro_dict):
        """Dersin konularını sira_no ASC (Motor 2'de kredi) ile sıralar."""
        adaylar = []
        for makro, mikrolar in makro_dict.items():
            if not isinstance(mikrolar, list):
                continue
            for ana in mikrolar:
                if ana in bilinen or (str(ders), str(ana)) in biten:
                    continue
                if not _on_kosul_hazir(ana, bilinen, kurallar):
                    continue
                adaylar.append((makro, ana))
        motor2_ders = motor2_aktif and not curriculum_meta.motor1_mi(ders)
        if motor2_ders and adaylar:
            # (makro_unite_max_kredi DESC, sira_no ASC)
            adaylar.sort(
                key=lambda c: (
                    -curriculum_meta.makro_kredi_puani(c[0]),
                    sira_map.get((ders, c[1]), 10 ** 6),
                )
            )
            hedef_makro = adaylar[0][0]
            adaylar = [c for c in adaylar if c[0] == hedef_makro]
        else:
            adaylar.sort(key=lambda c: sira_map.get((ders, c[1]), 10 ** 6))
        birimler = []
        for makro, ana in adaylar:
            birimler.extend(_birim_olustur(ders, makro, ana))
        return birimler

    def _ders_besle(ders):
        """Dersin sıradaki birimini kuyruğa ekler (aktif birim varsa bekle)."""
        if ders_kuyrukta.get(ders):
            return
        birimler = ders_birimler.get(ders) or []
        idx = ders_devam.get(ders, 0)
        while idx < len(birimler) and (
            (ders, birimler[idx]["ana"], birimler[idx]["alt"]) in planlanan
        ):
            idx += 1
        if idx >= len(birimler):
            ders_devam[ders] = idx
            return
        b = birimler[idx]
        _kuyruga_ekle({
            "oncelik": 4, "tur": b["tur"], "ders": ders,
            "makro": b["makro"], "ana": b["ana"], "mikro": b["alt"],
            "kalan": b["kalan"], "kaynak": None, "pay_dk": b["pay_dk"],
            "mikro_hedef": b["mikro_hedef"], "ilk_kez": b["ilk_kez"],
            "sira_no": b["sira_no"], "makro_kredi": b["makro_kredi"],
        })
        ders_devam[ders] = idx + 1
        ders_kuyrukta[ders] = True

    if tek_brans_aktif:
        # Yalnızca her dersin sıradaki tek ana konusunun ilk mikro altı.
        for _ders, _makro_dict in (mufredat or {}).items():
            if not isinstance(_makro_dict, dict):
                continue
            if not _cekirdek_acik(_ders):
                continue
            ders_birimler[_ders] = _ders_birimleri_kur(_ders, _makro_dict)
            ders_devam[_ders] = 0
            ders_kuyrukta[_ders] = False
            _ders_besle(_ders)


    # 4) Yeni mikro konular (MUTLAK müfredat sırası / Motor 2 kredi)
    for ders, makro_dict in (mufredat or {}).items():
        if tek_brans_aktif:
            break  # yeni modda kuyruk yukarıda DİNAMİK beslenir
        if not isinstance(makro_dict, dict):
            continue
        # FAZ 1.3: çekirdek TYT→AYT kilidi (11. sınıf istisnası hariç).
        if not _cekirdek_acik(ders):
            continue
        # FAZ 4: Mayıs–Haziran + ezber/kavram dersi -> Motor 2 (kredi motoru).
        motor2_ders = motor2_aktif and not curriculum_meta.motor1_mi(ders)
        hedef_makrolar = None
        if motor2_ders:
            eksik_makrolar = []
            for makro, mikrolar in makro_dict.items():
                if not isinstance(mikrolar, list) or not mikrolar:
                    continue
                tamam = sum(
                    1 for m in mikrolar
                    if m in bilinen or (str(ders), str(m)) in biten
                )
                if tamam < len(mikrolar):
                    ilk_sira = min(
                        (sira_map.get((ders, m), 10 ** 6) for m in mikrolar),
                        default=0,
                    )
                    eksik_makrolar.append((makro, ilk_sira))
            if eksik_makrolar:
                # (makro_unite_max_kredi DESC, sira_no ASC)
                eksik_makrolar.sort(
                    key=lambda c: (
                        -curriculum_meta.makro_kredi_puani(c[0]),
                        c[1],
                    )
                )
                hedef_makrolar = {eksik_makrolar[0][0]}
        for makro, mikrolar in makro_dict.items():
            if not isinstance(mikrolar, list):
                continue
            if hedef_makrolar is not None and makro not in hedef_makrolar:
                continue
            makro_kredi = curriculum_meta.makro_kredi_puani(makro)
            for ana in mikrolar:
                if ana in bilinen or (str(ders), str(ana)) in biten:
                    continue
                if not _on_kosul_hazir(ana, bilinen, kurallar):
                    continue
                # KURAL 2: konuya hiç çalışılmamışsa (sıfır ilerleme) kartın
                # ilk adımı konu anlatımıdır.
                ilk_kez = not (
                    int(gercek.get((ders, ana), 0) or 0)
                    or any(
                        int(deger or 0)
                        for anahtar, deger in mikro_cozulen.items()
                        if anahtar[0] == ders and anahtar[1] == ana
                    )
                    # v2.2: konu anlatımı zaten yapılmışsa %0 değildir.
                    or (ders, ana) in ogrenilmis
                )
                _sira = sira_map.get((ders, ana), 10 ** 6)
                # v2.2 (%0→%30): konu anlatımı bitmiş konu sıfır sayılmaz;
                # sonraki planda SORU ÇÖZÜMÜ aşamasına geçer.
                _tur_ana = (
                    "pes"
                    if (tek_brans_aktif and (ders, ana) in ogrenilmis)
                    else "anlatim"
                )
                for alt, pay, sure, mikro_hedef in _mikro_dilimi(ders, makro, ana):
                    if (ders, ana, alt) in planlanan:
                        continue
                    _kuyruga_ekle({
                        "oncelik": 4, "tur": _tur_ana, "ders": ders,
                        "makro": makro, "ana": ana, "mikro": alt,
                        "kalan": pay, "kaynak": None, "pay_dk": sure,
                        "mikro_hedef": mikro_hedef, "ilk_kez": ilk_kez,
                        "sira_no": _sira, "makro_kredi": makro_kredi,
                    })

    # 5) Pekiştirme (öğrenilmiş ama soru hedefi dolmamış)
    for (ders, ana), cozulen in list(gercek.items()):
        if ders is None or ana is None:
            continue
        # KURAL 1: %100 biten konu pekiştirme/tekrar için geri dönmez.
        if (str(ders), str(ana)) in biten:
            continue
        makro = _makro_bul(mufredat, ders, ana)
        _sira_pes = sira_map.get((ders, ana), 10 ** 6)
        for alt, pay, sure, mikro_hedef in _mikro_dilimi(ders, makro, ana):
            _kuyruga_ekle({
                "oncelik": 5, "tur": "pes", "ders": ders, "makro": makro,
                "ana": ana, "mikro": alt, "kalan": pay, "kaynak": None,
                "pay_dk": None, "mikro_hedef": mikro_hedef,
                "sira_no": _sira_pes,
            })

    # 5b) KURAL 2 (v2.1): ilk günü (Konu Anlatımı + İlk Kavrama Testi)
    # TAMAMLANAN %0 konunun 24-48 saat sonrasına "Pekiştirme / Hatırlama
    # Kontrolü (20 Soru)" görevi planlanır. Bekleyenler dışarıdan (bağlam)
    # bildirilir; aynı planda anlatım kartıyla çakışmaz.
    pek_en_erken = (
        bas + timedelta(days=max(1, PEKISTIRME_MIN_SAAT // 24))
    ).isoformat()
    for kayit in baglam.get("pekistirme_bekleyen") or ():
        if isinstance(kayit, dict):
            ders = kayit.get("ders")
            ana = (
                kayit.get("mikro_konu")
                or kayit.get("konu")
                or kayit.get("ana")
            )
        else:
            try:
                ders, ana = kayit
            except (TypeError, ValueError):
                continue
        if not (ders and ana):
            continue
        # KURAL 1: %100 biten konu pekiştirme için geri dönmez.
        if (str(ders), str(ana)) in biten:
            continue
        makro = _makro_bul(mufredat, ders, ana)
        _kuyruga_ekle({
            "oncelik": 4, "tur": "pekistirme", "ders": ders, "makro": makro,
            "ana": ana, "mikro": None, "kalan": PEKISTIRME_SORU,
            "kaynak": None, "pay_dk": None, "mikro_hedef": PEKISTIRME_SORU,
            "en_erken": pek_en_erken, "pekistirme": True,
        })

    # 2b) FAZ 6C: yanlış soru defteri + zamanı gelmiş aralıklı tekrarlar
    # (devir ve öncelik 2'deki tekrar görevleriyle aynı katman; gecikmiş
    # kayıtlar en önce yerleşir, sığmayanlar kaynakta bekler -> devir).
    havuz = baglam.get("tekrar_havuzu")
    if havuz is None and baglam.get("tekrar_entegrasyonu", True):
        havuz = tekrar_havuzu(ogrenci_id, gun=bas, bitis=gunler[-1])
    havuz = _tekrar_havuzunu_suz(havuz, bas)
    for ders, makro, ana, alt, yanlis_idler, tekrar_planlari in _tekrar_gruplari(
        havuz or {}, mufredat
    ):
        if yanlis_idler:
            secili = yanlis_idler[:MAKS_TEKRAR_SORU]
            _kuyruga_ekle({
                "oncelik": 2, "tur": "yanlis", "ders": ders, "makro": makro,
                "ana": ana, "mikro": alt, "kalan": len(secili), "kaynak": None,
                "pay_dk": None,
                "anahtar": ("defter", ders, ana, alt),
                "kaynaklar": [
                    {"tur": KAYNAK_YANLIS, "id": soru_id}
                    for soru_id in secili
                ],
            })
        for tekrar in tekrar_planlari:
            tekrar_id = tekrar["id"]
            _kuyruga_ekle({
                "oncelik": 2, "tur": "tekrar", "ders": ders, "makro": makro,
                "ana": ana, "mikro": alt, "kalan": TEKRAR_HEDEF_SORU,
                "kaynak": None, "pay_dk": None,
                "anahtar": ("tekrar", tekrar_id),
                # FAZ 6C: tekrar, planlanan tarihinden önce yerleştirilmez.
                "en_erken": tekrar.get("en_erken"),
                "kaynaklar": [{"tur": KAYNAK_TEKRAR, "id": tekrar_id}],
            })

    # ------------------------------------------------------------------
    # YERLEŞTİRME (günlük kapasite asla aşılmaz)
    # ------------------------------------------------------------------
    for tarih in gunler:
        kap = kapasite[tarih]
        if kap <= 0:
            continue  # dinlenme günü

        # 6) Günlük paragraf (tek oturuşluk, bölünmez)
        if paragraf_soru > 0:
            paragraf = task_steps.gorev_zenginlestir(
                {
                    "ders": "TYT Türkçe",
                    "makro_konu": "Paragraf",
                    "mikro_konu": "Günlük Paragraf",
                    "alt_konu": None,
                    "gorev_tanimi": "📖 Günlük paragraf: %d soru çöz." % paragraf_soru,
                    "hedef_soru": paragraf_soru,
                    "pedagoji_turu": "Ezber",
                    "gorev_turu": "soru",
                    "tarih": tarih.isoformat(),
                },
                ogrenci_id=ogrenci_id,
                konu_sureleri=konu_sureleri,
            )
            sure = int(paragraf.get("tahmini_sure_dk") or 0)
            if 0 < sure <= kap:
                gun_gorev[tarih].append(paragraf)
                gun_dk[tarih] += sure
                gun_soru[tarih] += int(paragraf.get("hedef_soru") or 0)
                gun_ders[tarih]["TYT Türkçe"] = (
                    gun_ders[tarih].get("TYT Türkçe", 0) + 1
                )
                # Günlük rutin slotu dolu: günde TEK paragraf kartı.
                rutin_anahtar = ("TYT Türkçe", "Günlük Paragraf")
                gun_rutin[tarih][rutin_anahtar] = (
                    gun_rutin[tarih].get(rutin_anahtar, 0) + 1
                )

        for _ in range(60):  # gün içi yerleştirme turu
            kalan_dk = kap - gun_dk[tarih]
            # v2.3 (FAZ 1.3): yeni modda gün içi kırıntı bloğu yok (min 25 dk).
            _gun_min = MIN_KONU_BLOK_DK if tek_brans_aktif else MIN_ANLAMLI_BLOK
            if kalan_dk < _gun_min:
                break
            if tek_brans_aktif:
                # v2.2: mutlak müfredat sırası (sira_no) + rotasyon cezası.
                try:
                    _gun_idx = gunler.index(tarih)
                except ValueError:
                    _gun_idx = 0
                _onceki_branslar = (
                    gun_brans_ana[gunler[_gun_idx - 1]] if _gun_idx > 0 else set()
                )

                def _siralama_v22(cift):
                    _o = cift[1]
                    _brans = curriculum_meta.ana_brans(_o["ders"])
                    _rotasyon = 0
                    if (
                        _brans in SIDE_BRANSLAR
                        and _brans in _onceki_branslar
                        and not _o.get("eksikler")
                        and _o["tur"] != "alarm"
                    ):
                        _rotasyon = 1
                    return (
                        _o["oncelik"],
                        gun_ders[tarih].get(_o["ders"], 0),
                        _rotasyon,
                        _o.get("sira_no", 0),
                        -_o["kalan"],
                    )

                adaylar = sorted(kuyruk.items(), key=_siralama_v22)
            else:
                adaylar = sorted(
                    kuyruk.items(),
                    key=lambda cift: (
                        cift[1]["oncelik"],
                        # Ders dengesi: bugün en az görev alan ders öne geçer.
                        gun_ders[tarih].get(cift[1]["ders"], 0),
                        -cift[1]["kalan"],
                    ),
                )
            yerlesti = False
            for oge_anahtar, oge in adaylar:
                tekrar_mi = oge["tur"] in ("tekrar", "yanlis")
                # FAZ 6C: tekrar görevi planlanan tarihinden önce yerleşmez.
                if oge.get("en_erken") and tarih.isoformat() < oge["en_erken"]:
                    continue
                # KURAL 4: günlük FARKLI ders sayısı müsaitliğe göre sınırlıdır
                # (4 saat ve altında en fazla 3, her durumda en fazla 5).
                if (
                    oge["ders"] not in gun_ders[tarih]
                    and len(gun_ders[tarih]) >= gunluk_ders_limiti(kap)
                ):
                    continue
                if tekrar_mi:
                    # Günlük tekrar kotası: görev sayısı + dakika payı
                    if gun_tekrar[tarih] >= MAKS_TEKRAR_GOREV_GUN:
                        continue
                    if (oge["ders"], oge["ana"], oge["mikro"]) in gun_konu[tarih]:
                        continue
                    if gun_tekrar_dk[tarih] >= _tekrar_dk_limiti(kap):
                        continue
                else:
                    # Ders dengesi ve günlük soru tavanı
                    if (
                        gun_ders[tarih].get(oge["ders"], 0)
                        >= MAKS_DERS_GOREV_GUN
                    ):
                        continue
                    if gun_soru[tarih] >= MAKS_SORU_GUN:
                        continue
                if oge_anahtar in gun_mikro[tarih]:
                    continue  # aynı mikro konu aynı gün iki görev olmaz
                # TEKİLLEŞTİRME: aynı gün + aynı ders + aynı ana konu tek kart.
                # Günlük rutinler (örn. Günlük Paragraf) kendi slot limitine
                # tabidir (max_daily_limit, varsayılan 1).
                rutin_limiti = rutin_gunluk_limiti(oge["ana"], oge["ders"])
                if rutin_limiti is None:
                    if (oge["ders"], oge["ana"]) in gun_ana[tarih]:
                        continue
                elif (
                    gun_rutin[tarih].get((oge["ders"], oge["ana"]), 0)
                    >= rutin_limiti
                ):
                    continue
                # v2.2 (FAZ 2): aynı gün aynı ana branştan en fazla 1 ana konu
                # (mikro rutin kovası ve tekrar/defter görevleri hariç).
                if (
                    tek_brans_aktif
                    and not tekrar_mi
                    and rutin_limiti is None
                    and curriculum_meta.ana_brans(oge["ders"]) in gun_brans_ana[tarih]
                ):
                    continue
                if oge["tur"] == "anlatim":
                    if gun_yeni[tarih] >= MAKS_YENI_MIKRO_GUN:
                        continue
                    # Aynı dersten günde tek YENİ konu: dersler arasında denge
                    # kurulur (matematik de tarih de sırayla ilerler).
                    if oge["ders"] in gun_yeni_ders[tarih]:
                        continue
                pedagoji = pedagoji_map.get(
                    (oge["ders"], oge["ana"]), "Pekiştirme"
                )
                tavan = gorev_soru_tavani(oge["ders"], pedagoji)
                hedef_soru = min(tavan, oge["kalan"]) if oge["kalan"] else 0
                kalan_dk_gorev = kalan_dk
                if tekrar_mi:
                    kalan_dk_gorev = min(
                        kalan_dk, _tekrar_dk_limiti(kap) - gun_tekrar_dk[tarih]
                    )
                # KURAL 4: tek derse günlük 150 dk / 90 soru tavanı.
                ders_kalan_soru = MAKS_DERS_GUN_SORU - gun_ders_soru[tarih].get(
                    oge["ders"], 0
                )
                ders_kalan_dk = MAKS_DERS_GUN_DAKIKA - gun_ders_dk[tarih].get(
                    oge["ders"], 0
                )
                if ders_kalan_soru <= 0 or ders_kalan_dk < MIN_ANLAMLI_BLOK:
                    continue
                hedef_soru = min(hedef_soru, ders_kalan_soru)
                kalan_dk_gorev = min(kalan_dk_gorev, ders_kalan_dk)
                # v2.2 (FAZ 3): %0 konu anlatımı semantiği (uzun anlatım +
                # 15-20 soru kotası) yalnızca sınıf/alan bilgili planlarda
                # uygulanır; eski planlar özgün davranışını korur.
                if oge["tur"] == "anlatim" and oge.get("ilk_kez") and tek_brans_aktif:
                    # %0 ilk kavrama 15-20 soru; ancak 20'ye kırpınca konunun
                    # toplamı içinde <15 soruluk kırıntı kalacaksa tek blokta
                    # bitir (kırıntı yasağı, FAZ 1.3).
                    _kota = int(oge["kalan"] or 0)
                    _ver = min(20, _kota)
                    _artik = _kota - _ver
                    if 0 < _artik < MIN_KONU_BLOK_SORU and _kota <= tavan:
                        _ver = _kota
                    hedef_soru = min(hedef_soru, _ver)
                gorev = _soru_sayisi_sigdir(
                    oge["tur"],
                    oge["ders"],
                    oge["makro"],
                    oge["ana"],
                    tarih,
                    int(hedef_soru or 0),
                    kalan_dk_gorev,
                    oge["kaynak"],
                    ogrenci_id,
                    konu_sureleri,
                    oge["mikro"],
                    pedagoji,
                    alt_sayisi=1,
                    sure_dk=oge.get("pay_dk"),
                    mikro_hedef=oge.get("mikro_hedef"),
                    kaynaklar=oge.get("kaynaklar"),
                    tavan=tavan,
                    eksikler=oge.get("eksikler"),
                    ilk_kez=bool(oge.get("ilk_kez")),
                    konu_anlatimi_aktif=tek_brans_aktif,
                    min_soru=(
                        MIN_KONU_BLOK_SORU
                        if (tek_brans_aktif and oge["tur"] in ("anlatim", "pes"))
                        else None
                    ),
                    deneme_id=oge.get("deneme_id"),
                )
                if gorev is None:
                    continue
                # v2.3 (FAZ 1.3): ana konu kırıntısı yasak — blok HEM 25 dk
                # altı HEM 15 soru altı ise güne sıkıştırılmaz (ertesi gün).
                if (
                    tek_brans_aktif
                    and oge["tur"] in ("anlatim", "pes")
                    and int(gorev.get("tahmini_sure_dk") or 0) < MIN_KONU_BLOK_DK
                    and int(gorev.get("hedef_soru") or 0) < MIN_KONU_BLOK_SORU
                ):
                    continue
                gun_gorev[tarih].append(gorev)
                gun_dk[tarih] += int(gorev.get("tahmini_sure_dk") or 0)
                # KURAL 4: tek ders tavanı sayaçları (150 dk / 90 soru).
                gun_ders_soru[tarih][oge["ders"]] = (
                    gun_ders_soru[tarih].get(oge["ders"], 0)
                    + int(gorev.get("hedef_soru") or 0)
                )
                gun_ders_dk[tarih][oge["ders"]] = (
                    gun_ders_dk[tarih].get(oge["ders"], 0)
                    + int(gorev.get("tahmini_sure_dk") or 0)
                )
                gun_mikro[tarih].add(oge_anahtar)
                if tek_brans_aktif and not tekrar_mi and rutin_limiti is None:
                    # Ana branş kotası: o gün bu branş artık dolu.
                    gun_brans_ana[tarih].add(
                        curriculum_meta.ana_brans(oge["ders"])
                    )
                if rutin_limiti is None:
                    gun_ana[tarih].add((oge["ders"], oge["ana"]))
                else:
                    gun_rutin[tarih][(oge["ders"], oge["ana"])] = (
                        gun_rutin[tarih].get((oge["ders"], oge["ana"]), 0) + 1
                    )
                planlanan.add(oge_anahtar)
                if tekrar_mi:
                    gun_tekrar[tarih] += 1
                    gun_tekrar_dk[tarih] += int(gorev.get("tahmini_sure_dk") or 0)
                    gun_konu[tarih].add((oge["ders"], oge["ana"], oge["mikro"]))
                    kuyruk.pop(oge_anahtar, None)
                    yerlesti = True
                    break
                gun_soru[tarih] += int(gorev.get("hedef_soru") or 0)
                gun_ders[tarih][oge["ders"]] = (
                    gun_ders[tarih].get(oge["ders"], 0) + 1
                )
                oge["kalan"] = max(0, oge["kalan"] - int(gorev["hedef_soru"]))
                if oge["tur"] == "anlatim":
                    gun_yeni[tarih] += 1
                    gun_yeni_ders[tarih].add(oge["ders"])
                    # Devam görevi yalnızca soru içerir; anlatım tekrar edilmez.
                    oge["tur"] = "pes"
                    oge["pay_dk"] = None
                if oge["tur"] == "tekrar" or oge["kalan"] <= 0:
                    kuyruk.pop(oge_anahtar, None)
                    # v2.3 (FAZ 1.2): ana konu birimi tamamlandı -> aynı dersin
                    # bir sonraki alt/konusunu DİNAMİK besle (yeni mod).
                    if tek_brans_aktif and not tekrar_mi:
                        ders_kuyrukta[oge["ders"]] = False
                        _ders_besle(oge["ders"])
                yerlesti = True
                break
            if not yerlesti:
                break

    if kuyruk:
        uyarilar.append(
            "Bu haftanın kapasitesi tüm görevlere yetmedi; kalan işler bir"
            " sonraki programda devam edecek."
        )

    # ------------------------------------------------------------------
    # v2.2 (FAZ 2.1 / 4.5.4): anti-starvation — süre artıyorsa aynı dersin
    # 2./3. konusunu eklemek YERİNE "Genel Branş Denemesi / Karma Tarama" ekle.
    # ------------------------------------------------------------------
    if karma_tarama_aktif:
        for tarih in gunler:
            kalan_dk = kapasite[tarih] - gun_dk[tarih]
            # v2.3 (FAZ 1.3): karma tarama yalnızca gün zaten SEYREK ise
            # (görev < 3) ve en az 60 dk boşsa eklenir; dolu günlerde fazladan
            # kart üretilmez (haftalık kart bütçesi 28-42 korunur).
            if (
                len(gun_gorev[tarih]) >= 3
                or kalan_dk < 60
                or not gun_brans_ana[tarih]
            ):
                continue
            dk = min(60, int(kalan_dk))
            soru = max(10, min(40, int(dk / 1.5)))
            _tarama = {
                "ders": "Genel Deneme",
                "makro_konu": "Karma Tarama",
                "mikro_konu": "Genel Branş Denemesi / Karma Tarama",
                "alt_konu": None,
                "gorev_tanimi": (
                    "🎯 Genel Branş Denemesi / Karma Tarama: %d soru çöz"
                    " (~%d dk)." % (soru, dk)
                ),
                "hedef_soru": soru,
                "pedagoji_turu": "Pekiştirme",
                "gorev_turu": "soru",
                "gorev_tipi": "karma_tarama",
                "tarih": tarih.isoformat(),
                "kaynak_gorev_id": None,
                "is_mikro_rutin": True,
                "mikro_hedef_soru": soru,
            }
            try:
                zengin = task_steps.gorev_zenginlestir(
                    _tarama, ogrenci_id=ogrenci_id, konu_sureleri=konu_sureleri
                )
            except Exception:  # noqa: BLE001 - tarama eklenemezse plan bozulmaz
                continue
            if int(zengin.get("tahmini_sure_dk") or 0) > kalan_dk:
                continue
            gun_gorev[tarih].append(zengin)
            gun_dk[tarih] += int(zengin.get("tahmini_sure_dk") or 0)

    tum_gorevler = [g for tarih in gunler for g in gun_gorev[tarih]]
    # KURAL 4 son süzgeci: günlük ders limiti + tek ders 150 dk / 90 soru tavanı.
    # Akıllı planlama sırasında zaten uygulandığı için çoğunlukla idempotenttir.
    try:
        tum_gorevler = gunluk_ders_doldur(tum_gorevler, musaitlik)
    except Exception:  # noqa: BLE001 - süzgeç hatası planı bozmaz
        pass
    gun_ozeti = [
        {
            "tarih": tarih.isoformat(),
            "gun": GUN_ADLARI[tarih.weekday()],
            "kapasite_dk": kapasite[tarih],
            "planlanan_dk": gun_dk[tarih],
            "gorev_sayisi": len(gun_gorev[tarih]),
            "dinlenme": kapasite[tarih] == 0,
        }
        for tarih in gunler
    ]
    return {
        "gorevler": tum_gorevler,
        "gun_ozeti": gun_ozeti,
        "uyarilar": uyarilar,
        "toplam_sure_dk": sum(gun_dk.values()),
        "toplam_soru": sum(int(g["hedef_soru"] or 0) for g in tum_gorevler),
    }



def _soru_sayisi_sigdir(
    tur, ders, makro, mikro, tarih, kalan_soru, kalan_dk,
    kaynak, ogrenci_id, konu_sureleri, alt_konu, pedagoji, alt_sayisi=1,
    sure_dk=None, mikro_hedef=None, kaynaklar=None, tavan=None, eksikler=None,
    ilk_kez=False, deneme_id=None, konu_anlatimi_aktif=True, min_soru=None,
):
    """Kalan süreye sığan en büyük soru sayısıyla görevi üretir (yoksa None).

    FAZ 5D: mikro konunun hedefi 5'in altındaysa (ana konu kotası mikro
    konulara paylaştırıldığında oluşabilir) hedef küçültülmez; tek küçük blok
    olarak planlanır. Aksi hâlde bloklar 5-10 aralığında kalır.

    FAZ 6C: `kaynaklar` verilirse göreve YALNIZCA gerçekten planlanan soru
    kadar kaynak bağlanır (kalan kaynaklar defterde bekler, sonraki hafta
    yeniden havuza girer -> devir otomatiktir).

    `tavan`: ders bazlı görev soru tavanı (ezber derslerinde daha düşük).
    Adaylar kabadan inceye sıralanır; günün kalan dakikasına sığan EN BÜYÜK
    aday seçilir, böylece kapasite boşa harcanmaz.
    """
    # v2.3 (FAZ 1.3): ana konu için minimum soru tabanı. Taban, konunun
    # TOPLAM kalanından büyük olamaz (küçük kalanın bitirilmesine izin verir)
    # ama büyük bir konudan 15'in altında dilim alınmasını engeller.
    _taban = MIN_ANLAMLI_BLOK
    if min_soru not in (None, ""):
        try:
            _taban = max(MIN_ANLAMLI_BLOK, min(int(min_soru), int(kalan_soru)))
        except (TypeError, ValueError):
            _taban = MIN_ANLAMLI_BLOK
    if tavan in (None, "", 0):
        tavan = gorev_soru_tavani(ders, pedagoji)
    tavan = max(_taban, int(tavan))
    adaylar = []
    for soru in (
        min(tavan, kalan_soru),
        tavan,
        35,
        30,
        25,
        20,
        15,
        10,
        MIN_ANLAMLI_BLOK,
    ):
        if soru < _taban or soru > kalan_soru or soru > tavan:
            continue
        if soru not in adaylar:
            adaylar.append(soru)
    if not adaylar and 0 < kalan_soru < _taban:
        adaylar.append(int(kalan_soru))
    for soru in adaylar:
        secili = None
        if kaynaklar:
            secili = list(kaynaklar)[: int(soru)]
            if not secili:
                secili = None
        gorev = _gorev_uret(
            tur, ders, makro, mikro, tarih, soru, kaynak, ogrenci_id,
            konu_sureleri, alt_konu=alt_konu, pedagoji=pedagoji,
            alt_sayisi=alt_sayisi, sure_dk=sure_dk, mikro_hedef=mikro_hedef,
            kaynaklar=secili, eksikler=eksikler, ilk_kez=ilk_kez,
            deneme_id=deneme_id, konu_anlatimi_aktif=konu_anlatimi_aktif,
        )
        if int(gorev.get("tahmini_sure_dk") or 0) <= kalan_dk:
            if tur in ("devir", "pes"):
                etiket = (
                    "%s ➔ %s" % (mikro, alt_konu) if alt_konu else mikro
                )
                _gorev_metnini_tamamla(gorev, etiket)
            return gorev
    return None


def tum_gorevleri(baglam_sonuc):
    """Yardımcı: plan sonucundaki görev listesi."""
    return (baglam_sonuc or {}).get("gorevler") or []
