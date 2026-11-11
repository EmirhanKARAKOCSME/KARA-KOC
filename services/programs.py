"""FAZ 5A - Haftalık çalışma programı sürümleme servisi.

Tasarım ilkesi: **program yenilemek geçmişi silmez.**

- Her program `calisma_programlari` tablosunda ayrı bir kayıttır ve kendi
  ID'sini alır (Taslak / Aktif / Arşivlendi / Tamamlandı / İptal Edildi).
- Görevler `calisma_programi_gorevler.program_id` ile programına bağlanır.
  Bu alan NULL olan eski (migrasyon öncesi) görevler **korunur**; tarih veya
  ilişki tahmin edilerek yanlış bir programa bağlanmaz, "eski kayıt" olarak
  gösterilir.
- Aynı öğrencinin aynı anda **tek** aktif programı olabilir. Bu kural hem
  kısmi UNIQUE indeksle (veritabanı seviyesi) hem de `program_olustur`
  içindeki sıralı arşivleme ile güvence altındadır.
- Program üretimi tek transaction'dır: doğrulama veya yazma hatasında yeni
  program tamamen geri alınır, eski aktif program ve tüm görevleri yerinde
  kalır. Hiçbir yerde `DELETE` kullanılmaz.

Yarım kalan görevlerin devri `calisma_gorev_devirleri` tablosuyla izlenir;
bir kaynağın aynı kalan miktarı ikinci kez devredilemez.

Bu modül Streamlit'e bağımlı değildir; testler doğrudan çağırabilir.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

TR_TZ = timezone(timedelta(hours=3))

DURUM_TASLAK = "Taslak"
DURUM_AKTIF = "Aktif"
DURUM_ARSIV = "Arşivlendi"
DURUM_TAMAMLANDI = "Tamamlandı"
DURUM_IPTAL = "İptal Edildi"
DURUMLAR = (DURUM_TASLAK, DURUM_AKTIF, DURUM_ARSIV, DURUM_TAMAMLANDI, DURUM_IPTAL)
# Aktif olmayan (geçmişte kalmış) program durumları
GECMIS_DURUMLAR = (DURUM_ARSIV, DURUM_TAMAMLANDI, DURUM_IPTAL)
LEGACY_DURUM = "Eski Kayıtlar"

GUN_ADLARI = (
    "Pazartesi",
    "Salı",
    "Çarşamba",
    "Perşembe",
    "Cuma",
    "Cumartesi",
    "Pazar",
)

MAKS_GOREV_SAYISI = 500
MAKS_GUNLUK_DAKIKA = 1440
VARSAYILAN_DB_YOLU = "yks_veritabani.db"

_ZAMAN_KALIBI = "%Y-%m-%d %H:%M:%S"
_TARIH_KALIBI = "%Y-%m-%d"


class ProgramHatasi(ValueError):
    """Geçersiz program/görev verisi veya işlem hatası."""


class TekAktifProgramHatasi(ProgramHatasi):
    """Öğrencinin zaten aktif bir programı var (kural ihlali)."""


# ==============================================================================
# YAPILANDIRMA (testler için enjekte edilebilir)
# ==============================================================================
_db_yolu = VARSAYILAN_DB_YOLU
_baglanti_fabrikasi = None
_saat_fonksiyonu = None


def db_yolu_ayarla(yol):
    """Testlerin geçici kopya DB kullanabilmesi için yol değiştirir."""
    global _db_yolu
    _db_yolu = yol or VARSAYILAN_DB_YOLU


def baglanti_fabrikasi_ayarla(fabrika):
    """Testlerin hazır bir bağlantı vermesini sağlar (None = varsayılan)."""
    global _baglanti_fabrikasi
    _baglanti_fabrikasi = fabrika


def saat_fonksiyonu_ayarla(fonksiyon):
    """Testlerde zamanı sabitlemek için kullanılır (None = gerçek saat)."""
    global _saat_fonksiyonu
    _saat_fonksiyonu = fonksiyon


def simdi():
    if _saat_fonksiyonu is not None:
        return _saat_fonksiyonu()
    return datetime.now(TR_TZ)


def bugun():
    return simdi().date()


def _zaman_yaz(deger):
    if not deger:
        return None
    return deger.strftime(_ZAMAN_KALIBI)


def _metin(deger):
    if deger is None:
        return None
    metin = str(deger).strip()
    return metin or None


def _ogrenci_dogrula(ogrenci_id):
    if isinstance(ogrenci_id, bool):
        raise ProgramHatasi("Geçersiz öğrenci bilgisi.")
    try:
        oid = int(ogrenci_id)
    except (TypeError, ValueError):
        raise ProgramHatasi("Geçersiz öğrenci bilgisi.") from None
    if oid <= 0:
        raise ProgramHatasi("Geçersiz öğrenci bilgisi.")
    return oid


def _tarih_dogrula(deger, ad="Tarih"):
    """'YYYY-MM-DD' metnini doğrular ve normalleştirir."""
    if isinstance(deger, datetime):
        return deger.date().isoformat()
    if hasattr(deger, "isoformat") and not isinstance(deger, str):
        try:
            return deger.isoformat()[:10]
        except Exception:  # pragma: no cover - savunma
            raise ProgramHatasi("%s geçersiz." % ad) from None
    metin = _metin(deger)
    if not metin:
        raise ProgramHatasi("%s boş olamaz." % ad)
    try:
        return datetime.strptime(metin[:10], _TARIH_KALIBI).date().isoformat()
    except ValueError:
        raise ProgramHatasi("%s geçersiz (YYYY-AA-GG beklenir): %s" % (ad, deger)) from None


def gun_adi(tarih):
    """ISO tarihten Türkçe gün adı ('2024-05-06' -> 'Pazartesi')."""
    return GUN_ADLARI[datetime.strptime(tarih[:10], _TARIH_KALIBI).date().weekday()]


@contextmanager
def _baglanti():
    """Kendi açtığı bağlantıyı kapatır; enjekte edilen bağlantıya dokunmaz."""
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
    """Atomik yazma işlemi (yarış koşulunu kapatmak için BEGIN IMMEDIATE)."""
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


# ==============================================================================
# ŞEMA
# ==============================================================================
_SEMA_PROGRAM = """
CREATE TABLE IF NOT EXISTS calisma_programlari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    baslangic_tarihi TEXT NOT NULL,
    bitis_tarihi TEXT NOT NULL,
    durum TEXT NOT NULL DEFAULT 'Taslak',
    olusturma_zamani TEXT NOT NULL,
    guncelleme_zamani TEXT,
    gunluk_hedef_dakika INTEGER,
    program_notu TEXT,
    FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
)
"""

# Görev tablosu uygulamada da kurulur; burada kendi kendine yeten bir kopya
# tutulur (yalnızca yoksa oluşturulur, mevcut veriye dokunulmaz).
_SEMA_GOREV = """
CREATE TABLE IF NOT EXISTS calisma_programi_gorevler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER,
    gun TEXT,
    ders TEXT,
    makro_konu TEXT,
    mikro_konu TEXT,
    gorev_tanimi TEXT,
    hedef_soru INTEGER,
    mikro_hedef_soru INTEGER,
    pedagoji_turu TEXT DEFAULT 'Pekiştirme',
    durum INTEGER DEFAULT 0,
    tarih TEXT,
    alt_konu TEXT,
    program_id INTEGER,
    tahmini_sure_dk INTEGER,
    kaynak_gorev_id INTEGER,
    FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
)
"""

_GOREV_EK_KOLONLAR = (
    ("alt_konu", "TEXT"),
    ("mikro_hedef_soru", "INTEGER"),
    ("program_id", "INTEGER"),
    ("tahmini_sure_dk", "INTEGER"),
    ("kaynak_gorev_id", "INTEGER"),
)

_SEMA_DEVIR = """
CREATE TABLE IF NOT EXISTS calisma_gorev_devirleri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    kaynak_gorev_id INTEGER NOT NULL,
    hedef_gorev_id INTEGER NOT NULL,
    devredilen_soru INTEGER NOT NULL DEFAULT 0,
    devredilen_sure_dk INTEGER,
    olusturma_zamani TEXT NOT NULL,
    UNIQUE(kaynak_gorev_id, hedef_gorev_id),
    FOREIGN KEY(kaynak_gorev_id) REFERENCES calisma_programi_gorevler(id)
        ON DELETE CASCADE,
    FOREIGN KEY(hedef_gorev_id) REFERENCES calisma_programi_gorevler(id)
        ON DELETE CASCADE
)
"""

_INDEKSLER = (
    # Bir öğrencinin aynı anda yalnızca BİR aktif programı olabilir.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_program_tek_aktif"
    " ON calisma_programlari(ogrenci_id) WHERE durum = 'Aktif'",
    "CREATE INDEX IF NOT EXISTS idx_program_ogrenci"
    " ON calisma_programlari(ogrenci_id, baslangic_tarihi)",
    "CREATE INDEX IF NOT EXISTS idx_program_durum"
    " ON calisma_programlari(ogrenci_id, durum)",
    "CREATE INDEX IF NOT EXISTS idx_gorev_program"
    " ON calisma_programi_gorevler(program_id, tarih)",
    "CREATE INDEX IF NOT EXISTS idx_gorev_ogrenci_tarih"
    " ON calisma_programi_gorevler(ogrenci_id, tarih)",
    "CREATE INDEX IF NOT EXISTS idx_gorev_kaynak"
    " ON calisma_programi_gorevler(kaynak_gorev_id)",
    "CREATE INDEX IF NOT EXISTS idx_devir_kaynak"
    " ON calisma_gorev_devirleri(kaynak_gorev_id)",
    "CREATE INDEX IF NOT EXISTS idx_devir_ogrenci"
    " ON calisma_gorev_devirleri(ogrenci_id)",
)


def _tablo_kolonlari(conn, tablo):
    return [satir[1] for satir in conn.execute("PRAGMA table_info(%s)" % tablo)]


def _tek_aktif_onar(conn):
    """Veri bozulmuşsa (birden fazla aktif) en yenisini bırakır, diğerlerini arşivler."""
    fazlalar = conn.execute(
        "SELECT ogrenci_id FROM calisma_programlari WHERE durum = ?"
        " GROUP BY ogrenci_id HAVING COUNT(*) > 1",
        (DURUM_AKTIF,),
    ).fetchall()
    for satir in fazlalar:
        oid = satir[0]
        korunacak = conn.execute(
            "SELECT MAX(id) FROM calisma_programlari WHERE ogrenci_id = ?"
            " AND durum = ?",
            (oid, DURUM_AKTIF),
        ).fetchone()[0]
        conn.execute(
            "UPDATE calisma_programlari SET durum = ?, guncelleme_zamani = ?"
            " WHERE ogrenci_id = ? AND durum = ? AND id <> ?",
            (DURUM_ARSIV, _zaman_yaz(simdi()), oid, DURUM_AKTIF, korunacak),
        )
    return len(fazlalar)


def init_db():
    """Şemayı idempotent biçimde kurar; hiçbir kaydı silmez.

    Birden fazla kez çağrılabilir (migrasyon testlerinin dayanağı budur).
    """
    with _baglanti() as conn:
        with _islem(conn):
            conn.execute(_SEMA_PROGRAM)
            conn.execute(_SEMA_GOREV)
            conn.execute(_SEMA_DEVIR)
            mevcut = set(_tablo_kolonlari(conn, "calisma_programi_gorevler"))
            for kolon, tip in _GOREV_EK_KOLONLAR:
                if kolon not in mevcut:
                    conn.execute(
                        "ALTER TABLE calisma_programi_gorevler ADD COLUMN %s %s"
                        % (kolon, tip)
                    )
            _tek_aktif_onar(conn)
            for sorgu in _INDEKSLER:
                conn.execute(sorgu)
    return True


# ==============================================================================
# DOĞRULAMA
# ==============================================================================
def _sayi_dogrula(deger, ad, alt, ust):
    if isinstance(deger, bool):
        raise ProgramHatasi("%s sayı olmalıdır." % ad)
    try:
        sayi = int(deger)
    except (TypeError, ValueError):
        raise ProgramHatasi("%s sayı olmalıdır." % ad) from None
    if sayi < alt or sayi > ust:
        raise ProgramHatasi(
            "%s %d ile %d arasında olmalıdır (girilen: %s)." % (ad, alt, ust, sayi)
        )
    return sayi


def _gorev_normallestir(gorev, sira=1):
    """Görev sözlüğünü doğrular ve eksik alanları güvenli varsayılanla doldurur."""
    if not isinstance(gorev, dict):
        raise ProgramHatasi("%d. görev sözlük olmalıdır." % sira)
    tarih = _tarih_dogrula(gorev.get("tarih"), "%d. görevin tarihi" % sira)
    ders = _metin(gorev.get("ders"))
    mikro = _metin(gorev.get("mikro_konu"))
    if not ders:
        raise ProgramHatasi("%d. görevin dersi boş olamaz." % sira)
    if not mikro:
        raise ProgramHatasi("%d. görevin mikro konusu boş olamaz." % sira)
    hedef = _sayi_dogrula(gorev.get("hedef_soru") or 0, "Hedef soru sayısı", 0, 2000)
    # FAZ 5D: mikro konunun TAM soru hedefi (görev bu hedefin bir parçası olabilir).
    mikro_hedef = gorev.get("mikro_hedef_soru")
    mikro_hedef = 0 if mikro_hedef in (None, "") else _sayi_dogrula(
        mikro_hedef, "Mikro konu soru hedefi", 0, 2000
    )
    sure = gorev.get("tahmini_sure_dk")
    sure = None if sure in (None, "") else _sayi_dogrula(
        sure, "Tahmini süre (dk)", 1, MAKS_GUNLUK_DAKIKA
    )
    kaynak = gorev.get("kaynak_gorev_id")
    kaynak = None if kaynak in (None, "", 0) else _sayi_dogrula(
        kaynak, "Kaynak görev numarası", 1, 10 ** 9
    )
    adimlar = gorev.get("adimlar") or []
    if not isinstance(adimlar, (list, tuple)):
        raise ProgramHatasi("%d. görevin alt adımları liste olmalıdır." % sira)
    return {
        "gun": _metin(gorev.get("gun")) or gun_adi(tarih),
        "ders": ders,
        "makro_konu": _metin(gorev.get("makro_konu")),
        "mikro_konu": mikro,
        "alt_konu": _metin(gorev.get("alt_konu")),
        "gorev_tanimi": _metin(gorev.get("gorev_tanimi"))
        or ("%s — %s" % (ders, mikro)),
        "hedef_soru": hedef,
        "mikro_hedef_soru": mikro_hedef,
        "tahmini_sure_dk": sure,
        "pedagoji_turu": _metin(gorev.get("pedagoji_turu")) or "Pekiştirme",
        "tarih": tarih,
        "kaynak_gorev_id": kaynak,
        "adimlar": list(adimlar),
    }


def _butunluk_dogrula(conn, program_id, ogrenci_id, adet):
    """Yazılan görevlerin programa gerçekten bağlandığını doğrular."""
    satir = conn.execute(
        "SELECT COUNT(*) AS adet FROM calisma_programi_gorevler"
        " WHERE program_id = ? AND ogrenci_id = ?",
        (program_id, ogrenci_id),
    ).fetchone()
    if int(satir["adet"] or 0) != int(adet):
        raise ProgramHatasi(
            "Program bütünlük hatası: %d görev yazılması gerekirken %d bulundu."
            % (adet, int(satir["adet"] or 0))
        )
    bozuk = conn.execute(
        "SELECT COUNT(*) AS adet FROM calisma_programi_gorevler"
        " WHERE program_id = ? AND (tarih IS NULL OR substr(tarih, 1, 10) = ''"
        " OR mikro_konu IS NULL OR ders IS NULL OR hedef_soru IS NULL"
        " OR hedef_soru < 0)",
        (program_id,),
    ).fetchone()
    if int(bozuk["adet"] or 0):
        raise ProgramHatasi(
            "Program bütünlük hatası: %d görevde tarih/konu/soru alanı geçersiz."
            % int(bozuk["adet"] or 0)
        )
    aralik = conn.execute(
        "SELECT baslangic_tarihi, bitis_tarihi FROM calisma_programlari"
        " WHERE id = ?",
        (program_id,),
    ).fetchone()
    disarida = conn.execute(
        "SELECT COUNT(*) AS adet FROM calisma_programi_gorevler"
        " WHERE program_id = ? AND (tarih < ? OR tarih > ?)",
        (program_id, aralik["baslangic_tarihi"], aralik["bitis_tarihi"]),
    ).fetchone()
    if int(disarida["adet"] or 0):
        raise ProgramHatasi(
            "Program bütünlük hatası: %d görev program tarih aralığının dışında."
            % int(disarida["adet"] or 0)
        )
    return True


def _satir_sozluk(satir):
    return dict(satir) if satir is not None else None



# ==============================================================================
# PROGRAM OLUŞTURMA (tek transaction)
# ==============================================================================
def program_olustur(
    ogrenci_id,
    baslangic_tarihi,
    bitis_tarihi,
    gorevler,
    gunluk_hedef_dakika=None,
    program_notu=None,
    durum=DURUM_AKTIF,
    an=None,
):
    """Yeni programı güvenli biçimde oluşturur ve (istenirse) aktifleştirir.

    Sıra:
        1) Tüm görevler doğrulanır (tarih, ders, konu, soru, süre).
        2) Taslak program + görevleri yazılır.
        3) Bütünlük kontrolü yapılır.
        4) Önceki aktif program(lar) arşivlenir (silinmez).
        5) Yeni program aktif yapılır.

    Herhangi bir adım hata verirse transaction geri alınır: yarım program,
    yarım görev veya kaybolmuş eski program kalmaz.
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    if durum not in DURUMLAR:
        raise ProgramHatasi("Geçersiz program durumu: %s" % durum)
    bas = _tarih_dogrula(baslangic_tarihi, "Başlangıç tarihi")
    bit = _tarih_dogrula(bitis_tarihi, "Bitiş tarihi")
    if not gorevler:
        raise ProgramHatasi("Program için en az bir görev gerekir.")
    gorevler = list(gorevler)
    if len(gorevler) > MAKS_GOREV_SAYISI:
        raise ProgramHatasi(
            "Bir programa en fazla %d görev eklenebilir (girilen: %d)."
            % (MAKS_GOREV_SAYISI, len(gorevler))
        )
    hedef = gunluk_hedef_dakika
    hedef = None if hedef in (None, "") else _sayi_dogrula(
        hedef, "Günlük hedef (dk)", 0, MAKS_GUNLUK_DAKIKA
    )
    normaller = [
        _gorev_normallestir(gorev, sira) for sira, gorev in enumerate(gorevler, 1)
    ]
    # Program penceresi görevlerin gerçek tarihlerini kapsayacak şekilde
    # genişletilir (3 günlük aralıklı tekrar görevleri hafta sonunu aşabilir).
    tarihler = [g["tarih"] for g in normaller]
    bas = min([bas] + tarihler)
    bit = max([bit] + tarihler)
    an = an or simdi()
    zaman = _zaman_yaz(an)
    notu = _metin(program_notu)

    with _baglanti() as conn:
        with _islem(conn):
            imlec = conn.execute(
                "INSERT INTO calisma_programlari"
                " (ogrenci_id, baslangic_tarihi, bitis_tarihi, durum,"
                "  olusturma_zamani, guncelleme_zamani, gunluk_hedef_dakika,"
                "  program_notu) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (oid, bas, bit, DURUM_TASLAK, zaman, zaman, hedef, notu),
            )
            program_id = imlec.lastrowid
            for gorev in normaller:
                yeni_id = _gorev_yaz(conn, oid, program_id, gorev, zaman, an)
                if gorev["kaynak_gorev_id"]:
                    devredilen = gorev["hedef_soru"] or _devredilebilir_kalan(
                        conn, gorev["kaynak_gorev_id"]
                    )["kalan"]
                    _devir_kaydet(
                        conn,
                        oid,
                        gorev["kaynak_gorev_id"],
                        yeni_id,
                        devredilen,
                        gorev["tahmini_sure_dk"],
                        zaman,
                    )
            _butunluk_dogrula(conn, program_id, oid, len(normaller))
            if durum == DURUM_AKTIF:
                conn.execute(
                    "UPDATE calisma_programlari SET durum = ?, guncelleme_zamani = ?"
                    " WHERE ogrenci_id = ? AND durum = ? AND id <> ?",
                    (DURUM_ARSIV, zaman, oid, DURUM_AKTIF, program_id),
                )
            conn.execute(
                "UPDATE calisma_programlari SET durum = ?, guncelleme_zamani = ?"
                " WHERE id = ?",
                (durum, zaman, program_id),
            )
            return _program_getir_conn(conn, program_id)


def _gorev_yaz(conn, ogrenci_id, program_id, gorev, zaman, an):
    """Tek görevi (varsa alt adımlarıyla) yazar; yeni görev ID'sini döndürür."""
    imlec = conn.execute(
        "INSERT INTO calisma_programi_gorevler"
        " (ogrenci_id, program_id, gun, ders, makro_konu, mikro_konu,"
        "  gorev_tanimi, hedef_soru, mikro_hedef_soru, pedagoji_turu, durum, tarih,"
        "  alt_konu, tahmini_sure_dk, kaynak_gorev_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)",
        (
            ogrenci_id,
            program_id,
            gorev["gun"],
            gorev["ders"],
            gorev["makro_konu"],
            gorev["mikro_konu"],
            gorev["gorev_tanimi"],
            gorev["hedef_soru"],
            gorev.get("mikro_hedef_soru") or 0,
            gorev["pedagoji_turu"],
            gorev["tarih"],
            gorev["alt_konu"],
            gorev["tahmini_sure_dk"],
            gorev["kaynak_gorev_id"],
        ),
    )
    yeni_id = imlec.lastrowid
    if gorev["adimlar"]:
        adimlar = gorev["adimlar"]
        try:
            from services import task_steps
        except ImportError:  # FAZ 5B modülü henüz yok
            task_steps = None
        if task_steps is not None:
            task_steps.adimlari_kaydet(yeni_id, adimlar, conn=conn, an=an)
    return yeni_id


# ==============================================================================
# OKUMA
# ==============================================================================
def _program_getir_conn(conn, program_id):
    satir = conn.execute(
        "SELECT * FROM calisma_programlari WHERE id = ?", (program_id,)
    ).fetchone()
    return _satir_sozluk(satir)


def program_getir(program_id):
    """Program kaydını sözlük olarak döndürür (yoksa None)."""
    with _baglanti() as conn:
        return _program_getir_conn(conn, program_id)


def aktif_program(ogrenci_id):
    """Öğrencinin aktif programı (yoksa None)."""
    oid = _ogrenci_dogrula(ogrenci_id)
    with _baglanti() as conn:
        satir = conn.execute(
            "SELECT * FROM calisma_programlari WHERE ogrenci_id = ? AND durum = ?"
            " ORDER BY id DESC LIMIT 1",
            (oid, DURUM_AKTIF),
        ).fetchone()
    return _satir_sozluk(satir)


def program_listesi(ogrenci_id, durumlar=None):
    """Öğrencinin programları (en yeni önce)."""
    oid = _ogrenci_dogrula(ogrenci_id)
    sorgu = "SELECT * FROM calisma_programlari WHERE ogrenci_id = ?"
    params = [oid]
    if durumlar:
        durumlar = list(durumlar)
        sorgu += " AND durum IN (%s)" % ", ".join("?" * len(durumlar))
        params.extend(durumlar)
    sorgu += " ORDER BY baslangic_tarihi DESC, id DESC"
    with _baglanti() as conn:
        satirlar = conn.execute(sorgu, tuple(params)).fetchall()
    return [dict(s) for s in satirlar]


def program_gorevleri(program_id, sadece_tarih=None):
    """Bir programa bağlı görevler (tarih, id sırasıyla)."""
    sorgu = "SELECT * FROM calisma_programi_gorevler WHERE program_id = ?"
    params = [program_id]
    if sadece_tarih:
        sorgu += " AND tarih = ?"
        params.append(_tarih_dogrula(sadece_tarih))
    sorgu += " ORDER BY tarih ASC, id ASC"
    with _baglanti() as conn:
        satirlar = conn.execute(sorgu, tuple(params)).fetchall()
    return [dict(s) for s in satirlar]


def _legacy_gorevler(conn, ogrenci_id, tarih=None):
    sorgu = (
        "SELECT * FROM calisma_programi_gorevler"
        " WHERE ogrenci_id = ? AND program_id IS NULL"
    )
    params = [ogrenci_id]
    if tarih:
        sorgu += " AND tarih = ?"
        params.append(tarih)
    sorgu += " ORDER BY tarih ASC, id ASC"
    return [dict(s) for s in conn.execute(sorgu, tuple(params)).fetchall()]


def gun_gorevleri(ogrenci_id, tarih=None):
    """Belirli bir günün görevleri (TAM tarih + aktif program + öğrenci).

    Eski haftaların aynı gün adına ait görevleri asla bugüne karışmaz:
    gün adı (`gun`) yerine yalnızca tam tarih kullanılır. Aktif program varsa
    yalnızca onun görevleri döner; yoksa program bağlantısı olmayan eski
    kayıtlar (yalnızca o güne ait olanlar) döner.
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    gun = _tarih_dogrula(tarih, "Gün") if tarih else bugun().isoformat()
    with _baglanti() as conn:
        aktif = conn.execute(
            "SELECT id FROM calisma_programlari WHERE ogrenci_id = ? AND durum = ?"
            " ORDER BY id DESC LIMIT 1",
            (oid, DURUM_AKTIF),
        ).fetchone()
        if aktif is None:
            return _legacy_gorevler(conn, oid, gun)
        satirlar = conn.execute(
            "SELECT * FROM calisma_programi_gorevler"
            " WHERE ogrenci_id = ? AND tarih = ? AND program_id = ?"
            " ORDER BY id ASC",
            (oid, gun, aktif["id"]),
        ).fetchall()
    return [dict(s) for s in satirlar]


def gorunur_gorevler(ogrenci_id):
    """Haftalık çizelgede gösterilecek görevler (aktif program veya eski kayıtlar)."""
    oid = _ogrenci_dogrula(ogrenci_id)
    with _baglanti() as conn:
        aktif = conn.execute(
            "SELECT id FROM calisma_programlari WHERE ogrenci_id = ? AND durum = ?"
            " ORDER BY id DESC LIMIT 1",
            (oid, DURUM_AKTIF),
        ).fetchone()
        if aktif is None:
            return _legacy_gorevler(conn, oid)
        satirlar = conn.execute(
            "SELECT * FROM calisma_programi_gorevler WHERE program_id = ?"
            " ORDER BY tarih ASC, id ASC",
            (aktif["id"],),
        ).fetchall()
    return [dict(s) for s in satirlar]


def _gercek_toplam(conn, program_id):
    """Programın görevlerine bağlı TAMAMLANMIŞ oturumların gerçek toplamları."""
    try:
        satir = conn.execute(
            "SELECT COALESCE(SUM(o.gercek_sure_dk), 0) AS dk,"
            " COALESCE(SUM(o.cozulen_soru), 0) AS soru, COUNT(*) AS adet"
            " FROM calisma_oturumlari o"
            " JOIN calisma_programi_gorevler g ON g.id = o.gorev_id"
            " WHERE g.program_id = ? AND o.durum = ?",
            (program_id, "Tamamlandı"),
        ).fetchone()
    except sqlite3.Error:
        return {"sure_dk": 0, "soru": 0, "oturum": 0}
    return {
        "sure_dk": int(satir["dk"] or 0),
        "soru": int(satir["soru"] or 0),
        "oturum": int(satir["adet"] or 0),
    }


def _gorev_toplam(conn, program_id=None, ogrenci_id=None):
    """Görev sayıları: toplam / tamamlanan / yarım kalan / planlanan soru."""
    if program_id is not None:
        kosul, params = "program_id = ?", (program_id,)
    else:
        kosul, params = "ogrenci_id = ? AND program_id IS NULL", (ogrenci_id,)
    satir = conn.execute(
        "SELECT COUNT(*) AS gorev,"
        " COALESCE(SUM(CASE WHEN durum = 1 THEN 1 ELSE 0 END), 0) AS biten,"
        " COALESCE(SUM(CASE WHEN durum = 1 THEN 0 ELSE 1 END), 0) AS yarim,"
        " COALESCE(SUM(hedef_soru), 0) AS plan_soru"
        " FROM calisma_programi_gorevler WHERE " + kosul,
        params,
    ).fetchone()
    return {
        "gorev": int(satir["gorev"] or 0),
        "tamamlanan": int(satir["biten"] or 0),
        "yarim": int(satir["yarim"] or 0),
        "planlanan_soru": int(satir["plan_soru"] or 0),
    }


# ==============================================================================
# GEÇMİŞ
# ==============================================================================
def _program_ozeti_conn(conn, satir):
    program = dict(satir)
    toplam = _gorev_toplam(conn, program_id=program["id"])
    gercek = _gercek_toplam(conn, program["id"])
    gorev = toplam["gorev"]
    program.update(toplam)
    program["gercek_sure_dk"] = gercek["sure_dk"]
    program["gercek_soru"] = gercek["soru"]
    program["gercek_oturum"] = gercek["oturum"]
    program["oran"] = int(round(100.0 * toplam["tamamlanan"] / gorev)) if gorev else 0
    return program


def program_ozeti(program_id):
    """Tek programın tamamlanma/gerçek çalışma özeti."""
    with _baglanti() as conn:
        satir = conn.execute(
            "SELECT * FROM calisma_programlari WHERE id = ?", (program_id,)
        ).fetchone()
        if satir is None:
            return None
        return _program_ozeti_conn(conn, satir)


def program_gecmisi(ogrenci_id, limit=10, durumlar=None):
    """Geçmiş (aktif olmayan) programların özet listesi (en yeni önce)."""
    oid = _ogrenci_dogrula(ogrenci_id)
    try:
        limit = max(1, min(50, int(limit or 10)))
    except (TypeError, ValueError):
        limit = 10
    durumlar = list(durumlar or GECMIS_DURUMLAR)
    with _baglanti() as conn:
        satirlar = conn.execute(
            "SELECT * FROM calisma_programlari WHERE ogrenci_id = ?"
            " AND durum IN (%s) ORDER BY baslangic_tarihi DESC, id DESC LIMIT ?"
            % ", ".join("?" * len(durumlar)),
            tuple([oid] + durumlar + [limit]),
        ).fetchall()
        return [_program_ozeti_conn(conn, s) for s in satirlar]


def eski_kayitlar_ozeti(ogrenci_id):
    """Program bağlantısı olmayan eski görevler (migrasyon öncesi kayıtlar).

    Bu kayıtlar hiçbir programa bağlanmaz; yalnızca korunur ve raporlanır.
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    with _baglanti() as conn:
        toplam = _gorev_toplam(conn, ogrenci_id=oid)
        if not toplam["gorev"]:
            return None
        aralik = conn.execute(
            "SELECT MIN(tarih) AS bas, MAX(tarih) AS bit"
            " FROM calisma_programi_gorevler"
            " WHERE ogrenci_id = ? AND program_id IS NULL",
            (oid,),
        ).fetchone()
        try:
            gercek = conn.execute(
                "SELECT COALESCE(SUM(o.gercek_sure_dk), 0) AS dk,"
                " COALESCE(SUM(o.cozulen_soru), 0) AS soru"
                " FROM calisma_oturumlari o"
                " JOIN calisma_programi_gorevler g ON g.id = o.gorev_id"
                " WHERE g.ogrenci_id = ? AND g.program_id IS NULL"
                "   AND o.durum = ?",
                (oid, "Tamamlandı"),
            ).fetchone()
        except sqlite3.Error:
            gercek = {"dk": 0, "soru": 0}
    gorev = toplam["gorev"]
    return {
        "id": None,
        "durum": LEGACY_DURUM,
        "baslangic_tarihi": aralik["bas"],
        "bitis_tarihi": aralik["bit"],
        "gorev": gorev,
        "tamamlanan": toplam["tamamlanan"],
        "yarim": toplam["yarim"],
        "planlanan_soru": toplam["planlanan_soru"],
        "gercek_sure_dk": int(gercek["dk"] or 0),
        "gercek_soru": int(gercek["soru"] or 0),
        "oran": int(round(100.0 * toplam["tamamlanan"] / gorev)) if gorev else 0,
        "program_notu": "Program bilgisi olmayan eski kayıtlar (korunuyor).",
    }


def gecmis_ozeti(ogrenci_id, limit=10):
    """Geçmiş programlar + eski kayıt özeti (arayüz için tek çağrı)."""
    return {
        "programlar": program_gecmisi(ogrenci_id, limit=limit),
        "eski_kayitlar": eski_kayitlar_ozeti(ogrenci_id),
    }


def program_durum_degistir(program_id, yeni_durum, an=None):
    """Program durumunu değiştirir (Aktif yaparken diğerleri arşivlenir)."""
    if yeni_durum not in DURUMLAR:
        raise ProgramHatasi("Geçersiz program durumu: %s" % yeni_durum)
    zaman = _zaman_yaz(an or simdi())
    with _baglanti() as conn:
        with _islem(conn):
            satir = conn.execute(
                "SELECT * FROM calisma_programlari WHERE id = ?", (program_id,)
            ).fetchone()
            if satir is None:
                raise ProgramHatasi("Program bulunamadı (#%s)." % program_id)
            if yeni_durum == DURUM_AKTIF:
                conn.execute(
                    "UPDATE calisma_programlari SET durum = ?, guncelleme_zamani = ?"
                    " WHERE ogrenci_id = ? AND durum = ? AND id <> ?",
                    (DURUM_ARSIV, zaman, satir["ogrenci_id"], DURUM_AKTIF, program_id),
                )
            conn.execute(
                "UPDATE calisma_programlari SET durum = ?, guncelleme_zamani = ?"
                " WHERE id = ?",
                (yeni_durum, zaman, program_id),
            )
            return _program_getir_conn(conn, program_id)


# ==============================================================================
# YARIM KALAN GÖREVLERİN DEVRİ
# ==============================================================================
def _gercek_cozulen(conn, gorev_id):
    try:
        satir = conn.execute(
            "SELECT COALESCE(SUM(cozulen_soru), 0) AS soru FROM calisma_oturumlari"
            " WHERE gorev_id = ? AND durum = ?",
            (gorev_id, "Tamamlandı"),
        ).fetchone()
    except sqlite3.Error:
        return 0
    return int(satir["soru"] or 0)


def _devredilen_toplam(conn, kaynak_gorev_id):
    satir = conn.execute(
        "SELECT COALESCE(SUM(devredilen_soru), 0) AS soru"
        " FROM calisma_gorev_devirleri WHERE kaynak_gorev_id = ?",
        (kaynak_gorev_id,),
    ).fetchone()
    return int(satir["soru"] or 0)


def _devredilebilir_kalan(conn, kaynak_gorev_id):
    satir = conn.execute(
        "SELECT id, ogrenci_id, hedef_soru, durum FROM calisma_programi_gorevler"
        " WHERE id = ?",
        (kaynak_gorev_id,),
    ).fetchone()
    if satir is None:
        raise ProgramHatasi("Kaynak görev bulunamadı (#%s)." % kaynak_gorev_id)
    hedef = int(satir["hedef_soru"] or 0)
    gercek = _gercek_cozulen(conn, satir["id"])
    devredilen = _devredilen_toplam(conn, satir["id"])
    return {
        "gorev_id": int(satir["id"]),
        "ogrenci_id": satir["ogrenci_id"],
        "hedef_soru": hedef,
        "gercek_soru": gercek,
        "devredilen_soru": devredilen,
        "kalan": max(0, hedef - gercek - devredilen),
        "tamamlandi": bool(satir["durum"]),
    }


def devredilebilir_kalan(kaynak_gorev_id):
    """Bir görevden başka programa devredilebilecek gerçek kalan soru."""
    with _baglanti() as conn:
        return _devredilebilir_kalan(conn, kaynak_gorev_id)


def _devir_kaydet(conn, ogrenci_id, kaynak_id, hedef_id, soru, sure_dk, zaman):
    """Devir ilişkisini yazar; kalan miktarın iki kez devrini engeller."""
    if int(kaynak_id) == int(hedef_id):
        raise ProgramHatasi("Bir görev kendisine devredilemez.")
    kaynak = conn.execute(
        "SELECT id, ogrenci_id FROM calisma_programi_gorevler WHERE id = ?",
        (kaynak_id,),
    ).fetchone()
    if kaynak is None:
        raise ProgramHatasi("Kaynak görev bulunamadı (#%s)." % kaynak_id)
    hedef = conn.execute(
        "SELECT id, ogrenci_id FROM calisma_programi_gorevler WHERE id = ?",
        (hedef_id,),
    ).fetchone()
    if hedef is None:
        raise ProgramHatasi("Devredilen (yeni) görev bulunamadı (#%s)." % hedef_id)
    if kaynak["ogrenci_id"] != hedef["ogrenci_id"]:
        raise ProgramHatasi("Devir yalnızca aynı öğrencinin görevleri arasında olur.")
    kalan = _devredilebilir_kalan(conn, kaynak_id)["kalan"]
    miktar = int(soru or 0)
    if miktar <= 0:
        raise ProgramHatasi(
            "Devredilecek kalan soru yok (kaynak görev #%s)." % kaynak_id
        )
    if miktar > kalan:
        raise ProgramHatasi(
            "Devredilen soru (%d) kalan miktarı (%d) aşıyor; aynı kalan miktar"
            " iki kez devredilemez." % (miktar, kalan)
        )
    try:
        conn.execute(
            "INSERT INTO calisma_gorev_devirleri"
            " (ogrenci_id, kaynak_gorev_id, hedef_gorev_id, devredilen_soru,"
            "  devredilen_sure_dk, olusturma_zamani) VALUES (?, ?, ?, ?, ?, ?)",
            (
                ogrenci_id or kaynak["ogrenci_id"],
                kaynak_id,
                hedef_id,
                miktar,
                sure_dk,
                zaman,
            ),
        )
    except sqlite3.IntegrityError as hata:
        raise ProgramHatasi(
            "Bu devir ilişkisi zaten kayıtlı (kaynak #%s -> hedef #%s)."
            % (kaynak_id, hedef_id)
        ) from hata
    conn.execute(
        "UPDATE calisma_programi_gorevler SET kaynak_gorev_id = ? WHERE id = ?",
        (kaynak_id, hedef_id),
    )
    return miktar


def gorev_devret(kaynak_gorev_id, hedef_gorev_id, soru=None, sure_dk=None, an=None):
    """Var olan iki görev arasında kalan miktarı devreder (çift devri engeller)."""
    with _baglanti() as conn:
        with _islem(conn):
            kalan = _devredilebilir_kalan(conn, kaynak_gorev_id)
            miktar = kalan["kalan"] if soru in (None, "") else int(soru)
            return _devir_kaydet(
                conn,
                kalan["ogrenci_id"],
                kaynak_gorev_id,
                hedef_gorev_id,
                miktar,
                sure_dk,
                _zaman_yaz(an or simdi()),
            )


def devir_ozeti(kaynak_gorev_id):
    """Bir kaynak görevin devir geçmişi."""
    with _baglanti() as conn:
        satirlar = conn.execute(
            "SELECT * FROM calisma_gorev_devirleri WHERE kaynak_gorev_id = ?"
            " ORDER BY id ASC",
            (kaynak_gorev_id,),
        ).fetchall()
    return [dict(s) for s in satirlar]
