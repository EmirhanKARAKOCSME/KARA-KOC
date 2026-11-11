"""FAZ 4 - Gerçek çalışma oturumu ve zamanlayıcı servisi.

Tasarım ilkesi: **planlanan** ile **gerçekleşen** ayrı veridir.

- `calisma_programi_gorevler.hedef_soru`  -> planlanan soru (plan verisi)
- `calisma_oturumlari.cozulen_soru`       -> öğrencinin beyan ettiği gerçek soru

Soru ilerlemesi artık YALNIZCA tamamlanmış çalışma oturumlarından okunur;
görev checkbox'ları planlanan soru sayısını ilerlemeye eklemez.

Akış:  Devam Ediyor  <->  Molada  ->  Tamamlandı
                    \\_____________->  İptal Edildi
`birikmis_saniye` yalnızca koşan dilimlerin toplamıdır; mola süresi
hiçbir zaman çalışma süresine eklenmez.

Bu modül Streamlit'e bağımlı değildir; testler doğrudan çağırabilir.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

TR_TZ = timezone(timedelta(hours=3))

DURUM_DEVAM = "Devam Ediyor"
DURUM_MOLA = "Molada"
DURUM_TAMAMLANDI = "Tamamlandı"
DURUM_IPTAL = "İptal Edildi"
DURUMLAR = (DURUM_DEVAM, DURUM_MOLA, DURUM_TAMAMLANDI, DURUM_IPTAL)
AKTIF_DURUMLAR = (DURUM_DEVAM, DURUM_MOLA)

GUNLUK_SERI_ESIK_DK = 15
MAKS_GERCEK_SURE_DK = 1440
MAKS_COZULEN_SORU = 2000
MAKS_NOT_UZUNLUK = 500
VARSAYILAN_DB_YOLU = "yks_veritabani.db"

_ZAMAN_KALIBI = "%Y-%m-%d %H:%M:%S"


class CalismaOturumHatasi(ValueError):
    """Geçersiz durum geçişi veya doğrulama hatası."""


class AktifOturumVarHatasi(CalismaOturumHatasi):
    """Öğrencinin zaten aktif (devam eden/molada) bir oturumu var."""


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
    """Testlerde zamanı ileri sarmak için kullanılır (None = gerçek saat)."""
    global _saat_fonksiyonu
    _saat_fonksiyonu = fonksiyon


def simdi():
    """Türkiye yerel saatiyle şu an (test enjeksiyonuna duyarlı)."""
    if _saat_fonksiyonu is not None:
        return _saat_fonksiyonu()
    return datetime.now(TR_TZ)


def _zaman_yaz(deger):
    if not deger:
        return None
    return deger.strftime(_ZAMAN_KALIBI)


def _zaman_oku(metin):
    """'YYYY-MM-DD HH:MM:SS' veya ISO metnini TR saatli datetime'a çevirir."""
    if not metin:
        return None
    if isinstance(metin, datetime):
        deger = metin
    else:
        temiz = str(metin).strip().replace("T", " ")
        deger = None
        for kalip, uzunluk in (
            (_ZAMAN_KALIBI, 19),
            ("%Y-%m-%d %H:%M", 16),
            ("%Y-%m-%d", 10),
        ):
            try:
                deger = datetime.strptime(temiz[:uzunluk], kalip)
                break
            except ValueError:
                continue
        if deger is None:
            try:
                deger = datetime.fromisoformat(temiz)
            except ValueError:
                return None
    if deger.tzinfo is None:
        deger = deger.replace(tzinfo=TR_TZ)
    return deger


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
    """Atomik yazma işlemi (BEGIN IMMEDIATE ile yarış koşulu kapatılır)."""
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
CREATE TABLE IF NOT EXISTS calisma_oturumlari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    gorev_id INTEGER,
    ders TEXT,
    makro_konu TEXT,
    mikro_konu TEXT,
    alt_konu TEXT,
    durum TEXT NOT NULL DEFAULT 'Devam Ediyor',
    baslangic_zamani TEXT NOT NULL,
    son_devam_zamani TEXT,
    birikmis_saniye INTEGER NOT NULL DEFAULT 0,
    olculen_saniye INTEGER NOT NULL DEFAULT 0,
    bitis_zamani TEXT,
    gercek_sure_dk INTEGER,
    cozulen_soru INTEGER,
    dogru INTEGER,
    yanlis INTEGER,
    bos INTEGER,
    sure_duzeltildi INTEGER NOT NULL DEFAULT 0,
    ogrenci_notu TEXT,
    olusturma_zamani TEXT NOT NULL,
    FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE,
    FOREIGN KEY(gorev_id) REFERENCES calisma_programi_gorevler(id) ON DELETE SET NULL
)
"""

_INDEKSLER = (
    "CREATE INDEX IF NOT EXISTS idx_calisma_oturum_ogrenci"
    " ON calisma_oturumlari(ogrenci_id, baslangic_zamani)",
    "CREATE INDEX IF NOT EXISTS idx_calisma_oturum_gorev"
    " ON calisma_oturumlari(gorev_id)",
    "CREATE INDEX IF NOT EXISTS idx_calisma_oturum_durum"
    " ON calisma_oturumlari(durum, ogrenci_id)",
    # Bir öğrencinin aynı anda en fazla BİR aktif zamanlayıcısı olabilir.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_calisma_oturum_tek_aktif"
    " ON calisma_oturumlari(ogrenci_id)"
    " WHERE durum IN ('Devam Ediyor', 'Molada')",
)


def init_db():
    """Tabloyu ve indeksleri idempotent biçimde oluşturur (veri silmez)."""
    with _baglanti() as conn:
        with _islem(conn):
            conn.execute(_SEMA)
            for sorgu in _INDEKSLER:
                conn.execute(sorgu)
    return True


# ==============================================================================
# OKUMA YARDIMCILARI
# ==============================================================================
def _sozluk(satir):
    return dict(satir) if satir is not None else None


def _metin(deger):
    if deger is None:
        return None
    metin = str(deger).strip()
    return metin or None


def _ogrenci_dogrula(ogrenci_id):
    try:
        oid = int(ogrenci_id)
    except (TypeError, ValueError):
        raise CalismaOturumHatasi("Geçersiz öğrenci bilgisi.") from None
    if oid <= 0:
        raise CalismaOturumHatasi("Geçersiz öğrenci bilgisi.")
    return oid


def _gorev_bilgisi(conn, ogrenci_id, gorev_id):
    """Görevi getirir; başka öğrencinin göreviyse hata verir."""
    if gorev_id in (None, "", 0):
        return None
    try:
        gid = int(gorev_id)
    except (TypeError, ValueError):
        raise CalismaOturumHatasi("Geçersiz görev bilgisi.") from None
    satir = conn.execute(
        "SELECT id, ogrenci_id, ders, makro_konu, mikro_konu, alt_konu"
        " FROM calisma_programi_gorevler WHERE id = ?",
        (gid,),
    ).fetchone()
    if satir is None:
        return None
    if satir["ogrenci_id"] not in (None, ogrenci_id):
        raise CalismaOturumHatasi("Bu görev başka bir öğrenciye ait.")
    return dict(satir)


def _oturum_satiri(conn, oturum_id):
    try:
        oid = int(oturum_id)
    except (TypeError, ValueError):
        raise CalismaOturumHatasi("Geçersiz oturum numarası.") from None
    satir = conn.execute(
        "SELECT * FROM calisma_oturumlari WHERE id = ?", (oid,)
    ).fetchone()
    if satir is None:
        raise CalismaOturumHatasi("Çalışma oturumu bulunamadı (#%s)." % oturum_id)
    return dict(satir)


def oturum_getir(oturum_id):
    """Tek oturumun tüm alanlarını sözlük olarak döndürür (yoksa None)."""
    with _baglanti() as conn:
        try:
            return _oturum_satiri(conn, oturum_id)
        except CalismaOturumHatasi:
            return None


def aktif_oturum_getir(ogrenci_id):
    """Öğrencinin devam eden veya moladaki oturumu (yoksa None).

    Zamanlayıcı durumu veritabanında tutulduğu için sayfa yenilense,
    uygulama kapansa veya başka sekmeye geçilse de oturum bulunur.
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    with _baglanti() as conn:
        satir = conn.execute(
            "SELECT * FROM calisma_oturumlari WHERE ogrenci_id = ?"
            " AND durum IN (?, ?) ORDER BY id DESC LIMIT 1",
            (oid, DURUM_DEVAM, DURUM_MOLA),
        ).fetchone()
    return _sozluk(satir)


def gecen_saniye(oturum, an=None):
    """Oturumun GERÇEK çalışma süresi (saniye). Mola süresi sayılmaz."""
    if not oturum:
        return 0
    birikmis = int(oturum.get("birikmis_saniye") or 0)
    durum = oturum.get("durum")
    if durum == DURUM_DEVAM and oturum.get("son_devam_zamani"):
        baslangic = _zaman_oku(oturum["son_devam_zamani"])
        if baslangic is not None:
            ek = int(((an or simdi()) - baslangic).total_seconds())
            birikmis += max(0, ek)
        return max(0, birikmis)
    if durum in (DURUM_TAMAMLANDI, DURUM_IPTAL):
        return max(0, int(oturum.get("olculen_saniye") or birikmis))
    return max(0, birikmis)


# ==============================================================================
# DURUM GEÇİŞLERİ (hepsi transaction içinde; geçersiz geçiş reddedilir)
# ==============================================================================
def oturum_baslat(
    ogrenci_id,
    gorev_id=None,
    ders=None,
    makro_konu=None,
    mikro_konu=None,
    alt_konu=None,
    an=None,
):
    """Yeni çalışma oturumu açar. Aktif oturum varsa reddeder."""
    oid = _ogrenci_dogrula(ogrenci_id)
    zaman = _zaman_yaz(an or simdi())
    with _baglanti() as conn:
        with _islem(conn):
            gorev = _gorev_bilgisi(conn, oid, gorev_id)
            if gorev:
                ders = _metin(ders) or _metin(gorev["ders"])
                makro_konu = _metin(makro_konu) or _metin(gorev["makro_konu"])
                mikro_konu = _metin(mikro_konu) or _metin(gorev["mikro_konu"])
                alt_konu = _metin(alt_konu) or _metin(gorev.get("alt_konu"))
            ders = _metin(ders)
            if not ders:
                raise CalismaOturumHatasi(
                    "Çalışma oturumu için ders bilgisi zorunludur."
                )
            mevcut = conn.execute(
                "SELECT id FROM calisma_oturumlari WHERE ogrenci_id = ?"
                " AND durum IN (?, ?)",
                (oid, DURUM_DEVAM, DURUM_MOLA),
            ).fetchone()
            if mevcut:
                raise AktifOturumVarHatasi(
                    "Zaten aktif bir çalışmanız var (oturum #%d)."
                    " Önce onu bitirmeden yeni çalışma başlatılamaz." % mevcut["id"]
                )
            try:
                imlec = conn.execute(
                    "INSERT INTO calisma_oturumlari"
                    " (ogrenci_id, gorev_id, ders, makro_konu, mikro_konu, alt_konu,"
                    "  durum, baslangic_zamani, son_devam_zamani, birikmis_saniye,"
                    "  olculen_saniye, olusturma_zamani)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)",
                    (
                        oid,
                        gorev["id"] if gorev else None,
                        ders,
                        _metin(makro_konu),
                        _metin(mikro_konu),
                        _metin(alt_konu),
                        DURUM_DEVAM,
                        zaman,
                        zaman,
                        zaman,
                    ),
                )
            except sqlite3.IntegrityError as hata:
                if "UNIQUE" in str(hata).upper():
                    raise AktifOturumVarHatasi(
                        "Zaten aktif bir çalışmanız var; ikinci oturum açılmadı."
                    ) from hata
                raise CalismaOturumHatasi(
                    "Çalışma oturumu açılamadı: %s" % hata
                ) from hata
            return _oturum_satiri(conn, imlec.lastrowid)


def oturum_duraklat(oturum_id, an=None):
    """Çalışmayı durdurur ve süreyi dondurur (mola süresi sayılmaz)."""
    with _baglanti() as conn:
        with _islem(conn):
            oturum = _oturum_satiri(conn, oturum_id)
            if oturum["durum"] in (DURUM_TAMAMLANDI, DURUM_IPTAL):
                raise CalismaOturumHatasi(
                    "Kapanmış oturum molaya alınamaz (%s)." % oturum["durum"]
                )
            if oturum["durum"] == DURUM_MOLA:
                return oturum  # çift tıklama: yeni işlem yapılmaz
            birikmis = gecen_saniye(oturum, an)
            conn.execute(
                "UPDATE calisma_oturumlari SET durum = ?, son_devam_zamani = NULL,"
                " birikmis_saniye = ?, olculen_saniye = ? WHERE id = ?",
                (DURUM_MOLA, birikmis, birikmis, oturum["id"]),
            )
            return _oturum_satiri(conn, oturum["id"])


def oturum_devam_ettir(oturum_id, an=None):
    """Moladaki oturumu yeniden başlatır (mola süresi çalışmaya eklenmez)."""
    zaman = _zaman_yaz(an or simdi())
    with _baglanti() as conn:
        with _islem(conn):
            oturum = _oturum_satiri(conn, oturum_id)
            if oturum["durum"] == DURUM_DEVAM:
                return oturum
            if oturum["durum"] != DURUM_MOLA:
                raise CalismaOturumHatasi(
                    "Yalnızca moladaki oturum devam ettirilebilir (%s)."
                    % oturum["durum"]
                )
            baska = conn.execute(
                "SELECT id FROM calisma_oturumlari WHERE ogrenci_id = ?"
                " AND durum IN (?, ?) AND id != ?",
                (oturum["ogrenci_id"], DURUM_DEVAM, DURUM_MOLA, oturum["id"]),
            ).fetchone()
            if baska:
                raise AktifOturumVarHatasi(
                    "Başka bir çalışma aktifken bu oturum devam ettirilemez."
                )
            conn.execute(
                "UPDATE calisma_oturumlari SET durum = ?, son_devam_zamani = ?"
                " WHERE id = ?",
                (DURUM_DEVAM, zaman, oturum["id"]),
            )
            return _oturum_satiri(conn, oturum["id"])


def oturum_iptal(oturum_id, an=None):
    """Oturumu iptal eder. Kayıt silinmez, istatistiklere katılmaz."""
    zaman = _zaman_yaz(an or simdi())
    with _baglanti() as conn:
        with _islem(conn):
            oturum = _oturum_satiri(conn, oturum_id)
            if oturum["durum"] == DURUM_IPTAL:
                return oturum
            if oturum["durum"] == DURUM_TAMAMLANDI:
                raise CalismaOturumHatasi("Tamamlanmış çalışma iptal edilemez.")
            birikmis = gecen_saniye(oturum, an)
            conn.execute(
                "UPDATE calisma_oturumlari SET durum = ?, son_devam_zamani = NULL,"
                " birikmis_saniye = ?, olculen_saniye = ?, bitis_zamani = ?"
                " WHERE id = ?",
                (DURUM_IPTAL, birikmis, birikmis, zaman, oturum["id"]),
            )
            return _oturum_satiri(conn, oturum["id"])


# ==============================================================================
# TAMAMLAMA (gerçek süre + gerçek soru sayısı)
# ==============================================================================
def _sayi_dogrula(deger, ad, alt, ust):
    """Tam sayı doğrulaması; geçersizse CalismaOturumHatasi fırlatır."""
    if isinstance(deger, bool):
        raise CalismaOturumHatasi("%s sayı olmalıdır." % ad)
    if isinstance(deger, float) and not float(deger).is_integer():
        raise CalismaOturumHatasi("%s tam sayı olmalıdır." % ad)
    try:
        sayi = int(deger)
    except (TypeError, ValueError):
        raise CalismaOturumHatasi("%s sayı olmalıdır." % ad) from None
    if sayi < alt or sayi > ust:
        raise CalismaOturumHatasi(
            "%s %d ile %d arasında olmalıdır (girilen: %s)." % (ad, alt, ust, sayi)
        )
    return sayi


def oturum_tamamla(
    oturum_id,
    cozulen_soru,
    gercek_sure_dk=None,
    dogru=None,
    yanlis=None,
    bos=None,
    ogrenci_notu=None,
    an=None,
):
    """Çalışmayı bitirir; GERÇEK süre ve GERÇEK soru sayısını kaydeder.

    - `cozulen_soru` zorunlu (0 olabilir: sadece konu/teori çalışması).
    - Doğru/yanlış/boş üçlüsü ya tamamen boş (NULL) ya da tamamen dolu
      olmalı ve toplamı `cozulen_soru` ile eşleşmelidir.
    - `gercek_sure_dk` verilmezse ölçülen süre kullanılır; farklıysa
      `sure_duzeltildi = 1` işaretlenir.
    - Tamamlanmış oturum ikinci kez tamamlanamaz.
    """
    cozulen = _sayi_dogrula(
        cozulen_soru, "Çözülen soru sayısı", 0, MAKS_COZULEN_SORU
    )
    uclu = (dogru, yanlis, bos)
    verilen = [d for d in uclu if d is not None and str(d).strip() != ""]
    kirilim = None
    if verilen and len(verilen) != 3:
        raise CalismaOturumHatasi(
            "Doğru / yanlış / boş alanları ya üçü birden doldurulmalı ya da"
            " üçü de boş bırakılmalıdır."
        )
    if verilen:
        kirilim = tuple(
            _sayi_dogrula(d, ad, 0, MAKS_COZULEN_SORU)
            for d, ad in zip(uclu, ("Doğru sayısı", "Yanlış sayısı", "Boş sayısı"))
        )
        if sum(kirilim) != cozulen:
            raise CalismaOturumHatasi(
                "Doğru + yanlış + boş toplamı (%d) çözülen soru sayısıyla"
                " (%d) eşleşmiyor." % (sum(kirilim), cozulen)
            )
    notu = _metin(ogrenci_notu)
    if notu and len(notu) > MAKS_NOT_UZUNLUK:
        notu = notu[:MAKS_NOT_UZUNLUK]
    an = an or simdi()

    with _baglanti() as conn:
        with _islem(conn):
            oturum = _oturum_satiri(conn, oturum_id)
            if oturum["durum"] == DURUM_TAMAMLANDI:
                raise CalismaOturumHatasi(
                    "Bu çalışma oturumu zaten kaydedilmiş; ikinci kez"
                    " tamamlanamaz."
                )
            if oturum["durum"] == DURUM_IPTAL:
                raise CalismaOturumHatasi(
                    "İptal edilmiş oturum çalışma istatistiklerine eklenemez."
                )
            olculen = gecen_saniye(oturum, an)
            olculen_dk = int(round(olculen / 60.0))
            if gercek_sure_dk is None:
                gercek = olculen_dk
                duzeltildi = 0
            else:
                gercek = _sayi_dogrula(
                    gercek_sure_dk,
                    "Gerçek çalışma süresi (dakika)",
                    0,
                    MAKS_GERCEK_SURE_DK,
                )
                duzeltildi = 1 if gercek != olculen_dk else 0
            imlec = conn.execute(
                "UPDATE calisma_oturumlari SET durum = ?, son_devam_zamani = NULL,"
                " birikmis_saniye = ?, olculen_saniye = ?, bitis_zamani = ?,"
                " gercek_sure_dk = ?, cozulen_soru = ?, dogru = ?, yanlis = ?,"
                " bos = ?, sure_duzeltildi = ?, ogrenci_notu = ?"
                " WHERE id = ? AND durum IN (?, ?)",
                (
                    DURUM_TAMAMLANDI,
                    olculen,
                    olculen,
                    _zaman_yaz(an),
                    gercek,
                    cozulen,
                    kirilim[0] if kirilim else None,
                    kirilim[1] if kirilim else None,
                    kirilim[2] if kirilim else None,
                    duzeltildi,
                    notu,
                    oturum["id"],
                    DURUM_DEVAM,
                    DURUM_MOLA,
                ),
            )
            if imlec.rowcount != 1:
                raise CalismaOturumHatasi(
                    "Oturum bu sırada başka bir işlemle kapandı; tekrar deneyin."
                )
            return _oturum_satiri(conn, oturum["id"])


# ==============================================================================
# GERÇEK ÇALIŞMA ÖZETLERİ (yalnızca "Tamamlandı" oturumlar sayılır)
# ==============================================================================
def _tarih(bugun=None):
    return bugun or simdi().date()


def _hafta_basi(gun):
    return gun - timedelta(days=gun.weekday())


def gunluk_haftalik_ozet(ogrenci_id, bugun=None):
    """Bugün ve bu hafta (Pazartesi'den itibaren) gerçek çalışma toplamları.

    Yalnızca `Tamamlandı` oturumlar sayılır; iptal edilen ve hâlâ devam
    eden oturumlar toplama katılmaz.
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    gun = _tarih(bugun)
    hafta_basi = _hafta_basi(gun)
    with _baglanti() as conn:
        satirlar = conn.execute(
            "SELECT substr(baslangic_zamani, 1, 10) AS gun,"
            " COALESCE(SUM(gercek_sure_dk), 0) AS dk,"
            " COALESCE(SUM(cozulen_soru), 0) AS soru,"
            " COUNT(*) AS adet"
            " FROM calisma_oturumlari"
            " WHERE ogrenci_id = ? AND durum = ?"
            "   AND substr(baslangic_zamani, 1, 10) BETWEEN ? AND ?"
            " GROUP BY substr(baslangic_zamani, 1, 10)",
            (oid, DURUM_TAMAMLANDI, hafta_basi.isoformat(), gun.isoformat()),
        ).fetchall()
    bugun_dk = bugun_soru = hafta_dk = hafta_soru = hafta_adet = 0
    gun_str = gun.isoformat()
    for satir in satirlar:
        hafta_dk += int(satir["dk"] or 0)
        hafta_soru += int(satir["soru"] or 0)
        hafta_adet += int(satir["adet"] or 0)
        if satir["gun"] == gun_str:
            bugun_dk = int(satir["dk"] or 0)
            bugun_soru = int(satir["soru"] or 0)
    return {
        "gun": gun_str,
        "hafta_basi": hafta_basi.isoformat(),
        "bugun_dk": bugun_dk,
        "bugun_soru": bugun_soru,
        "hafta_dk": hafta_dk,
        "hafta_soru": hafta_soru,
        "hafta_oturum": hafta_adet,
    }


def ders_bazli_ozet(ogrenci_id, gun_sayisi=7, bugun=None):
    """Son N günün ders bazlı gerçek süre/soru dökümü (süreye göre azalan)."""
    oid = _ogrenci_dogrula(ogrenci_id)
    gun = _tarih(bugun)
    try:
        gun_sayisi = max(1, int(gun_sayisi or 1))
    except (TypeError, ValueError):
        gun_sayisi = 7
    baslangic = (gun - timedelta(days=gun_sayisi - 1)).isoformat()
    with _baglanti() as conn:
        satirlar = conn.execute(
            "SELECT COALESCE(ders, 'Diğer') AS ders,"
            " COALESCE(SUM(gercek_sure_dk), 0) AS dk,"
            " COALESCE(SUM(cozulen_soru), 0) AS soru,"
            " COUNT(*) AS adet"
            " FROM calisma_oturumlari"
            " WHERE ogrenci_id = ? AND durum = ?"
            "   AND substr(baslangic_zamani, 1, 10) BETWEEN ? AND ?"
            " GROUP BY COALESCE(ders, 'Diğer')"
            " ORDER BY dk DESC, ders ASC",
            (oid, DURUM_TAMAMLANDI, baslangic, gun.isoformat()),
        ).fetchall()
    return [
        {
            "ders": satir["ders"],
            "dk": int(satir["dk"] or 0),
            "soru": int(satir["soru"] or 0),
            "oturum": int(satir["adet"] or 0),
        }
        for satir in satirlar
    ]


def gercek_calisma_serisi(ogrenci_id, esik_dk=GUNLUK_SERI_ESIK_DK, bugun=None):
    """Gerçek çalışma serisi (gün).

    Bir gün, o gün TAMAMLANMIŞ oturumların toplamı en az `esik_dk` ise
    "aktif çalışma günü" sayılır (tek oturuma değil günlük toplama bakılır).
    Bugün henüz eşik aşılmadıysa dünün serisi gün içinde korunur.
    İptal edilen ve tamamlanmamış oturumlar sayılmaz.
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    gun = _tarih(bugun)
    try:
        esik = max(1, int(esik_dk or GUNLUK_SERI_ESIK_DK))
    except (TypeError, ValueError):
        esik = GUNLUK_SERI_ESIK_DK
    with _baglanti() as conn:
        satirlar = conn.execute(
            "SELECT substr(baslangic_zamani, 1, 10) AS gun,"
            " COALESCE(SUM(gercek_sure_dk), 0) AS dk"
            " FROM calisma_oturumlari"
            " WHERE ogrenci_id = ? AND durum = ?"
            "   AND substr(baslangic_zamani, 1, 10) <= ?"
            " GROUP BY substr(baslangic_zamani, 1, 10)"
            " HAVING COALESCE(SUM(gercek_sure_dk), 0) >= ?",
            (oid, DURUM_TAMAMLANDI, gun.isoformat(), esik),
        ).fetchall()
    aktif_gunler = set()
    for satir in satirlar:
        try:
            aktif_gunler.add(
                datetime.strptime(str(satir["gun"]), "%Y-%m-%d").date()
            )
        except (TypeError, ValueError):
            continue
    imlec = gun
    if imlec not in aktif_gunler:
        imlec -= timedelta(days=1)
    seri = 0
    while imlec in aktif_gunler:
        seri += 1
        imlec -= timedelta(days=1)
    return seri


def gorev_cozulen_soru(ogrenci_id, gorev_id):
    """Bir görevde GERÇEKTEN çözülen soru (planlanan soru değil)."""
    oid = _ogrenci_dogrula(ogrenci_id)
    if gorev_id in (None, "", 0):
        return {"cozulen": 0, "sure_dk": 0, "oturum": 0}
    with _baglanti() as conn:
        satir = conn.execute(
            "SELECT COALESCE(SUM(cozulen_soru), 0) AS soru,"
            " COALESCE(SUM(gercek_sure_dk), 0) AS dk, COUNT(*) AS adet"
            " FROM calisma_oturumlari WHERE ogrenci_id = ? AND gorev_id = ?"
            " AND durum = ?",
            (oid, int(gorev_id), DURUM_TAMAMLANDI),
        ).fetchone()
    return {
        "cozulen": int(satir["soru"] or 0),
        "sure_dk": int(satir["dk"] or 0),
        "oturum": int(satir["adet"] or 0),
    }


def oturum_gecmisi(ogrenci_id, limit=10):
    """Son tamamlanmış oturumlar (en yeni önce)."""
    oid = _ogrenci_dogrula(ogrenci_id)
    try:
        limit = max(1, min(100, int(limit or 10)))
    except (TypeError, ValueError):
        limit = 10
    with _baglanti() as conn:
        satirlar = conn.execute(
            "SELECT * FROM calisma_oturumlari WHERE ogrenci_id = ?"
            " AND durum = ?"
            " ORDER BY COALESCE(bitis_zamani, baslangic_zamani) DESC, id DESC"
            " LIMIT ?",
            (oid, DURUM_TAMAMLANDI, limit),
        ).fetchall()
    return [dict(satir) for satir in satirlar]
