"""FAZ 6C - Program görevi <-> kaynak (tekrar / yanlış soru) bağı.

Tasarım ilkeleri:

- **Kaynak ayrı yaşar, görev kaynağı gösterir.** Spaced repetition
  (`tekrar_kayitlari`) ve yanlış soru defteri (`yanlis_sorular`) kendi
  durumlarını yönetir. Program görevi yalnızca "bu görev şu kayıtlar için
  yapıldı" bilgisini taşır; kaynağın durumunu zorla değiştirmez.
- **Tek yönlü yazma.** Görev tamamlanınca kaynak ilerletilir (tekrar sayacı
  artar / görev bağlantısı kapanır). Kaynak öğrenildi/arşivlenince o kaynağa
  bağlı BEKLEYEN görevler `gecersiz = 1` olur (silinmez, geçmiş korunur).
- **Geçmiş programlar değişmez.** Bağlar yalnızca yeni üretilen programlarda
  kurulur; eski görevlerin içeriği geriye dönük değiştirilmez.
- **Mükerrer bağ yok.** `(gorev_id, kaynak_turu, kaynak_id)` UNIQUE.

Bu modül Streamlit'e bağımlı değildir; testler doğrudan çağırabilir.
"""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

TR_TZ = timezone(timedelta(hours=3))

KAYNAK_TEKRAR = "tekrar_kaydi"
KAYNAK_YANLIS = "yanlis_soru"
KAYNAK_TURLERI = (KAYNAK_TEKRAR, KAYNAK_YANLIS)

VARSAYILAN_DB_YOLU = "yks_veritabani.db"

_ZAMAN_KALIBI = "%Y-%m-%d %H:%M:%S"


class KaynakHatasi(ValueError):
    """Geçersiz görev-kaynak işlemi veya doğrulama hatası."""


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
    """Türkiye yerel saatiyle şu an (test enjeksiyonuna duyarlı)."""
    if _saat_fonksiyonu is not None:
        return _saat_fonksiyonu()
    return datetime.now(TR_TZ)


def _zaman_yaz(deger):
    if not deger:
        return None
    return deger.strftime(_ZAMAN_KALIBI)


def _an_zamani(an=None):
    if an is None:
        return simdi()
    if isinstance(an, datetime):
        if an.tzinfo is not None:
            return an.astimezone(TR_TZ)
        return an.replace(tzinfo=TR_TZ)
    if isinstance(an, date):
        return datetime.combine(an, datetime.min.time(), tzinfo=TR_TZ)
    raise KaynakHatasi("Geçersiz işlem zamanı: %s" % (an,))


def _id_dogrula(deger, ad):
    if isinstance(deger, bool):
        raise KaynakHatasi("Geçersiz %s." % ad)
    try:
        sayi = int(deger)
    except (TypeError, ValueError):
        raise KaynakHatasi("Geçersiz %s." % ad) from None
    if sayi <= 0:
        raise KaynakHatasi("Geçersiz %s." % ad)
    return sayi


def _tur_dogrula(kaynak_turu):
    tur = str(kaynak_turu or "").strip()
    if tur not in KAYNAK_TURLERI:
        raise KaynakHatasi("Geçersiz kaynak türü: %s" % (kaynak_turu,))
    return tur


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


_SEMA = """
CREATE TABLE IF NOT EXISTS calisma_gorev_kaynaklari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    program_id INTEGER,
    gorev_id INTEGER NOT NULL,
    kaynak_turu TEXT NOT NULL,
    kaynak_id INTEGER NOT NULL,
    cozuldu INTEGER NOT NULL DEFAULT 0,
    cozulme_zamani TEXT,
    olusturma_zamani TEXT NOT NULL,
    UNIQUE(gorev_id, kaynak_turu, kaynak_id),
    FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE,
    FOREIGN KEY(gorev_id) REFERENCES calisma_programi_gorevler(id)
        ON DELETE CASCADE
)
"""

_INDEKSLER = (
    "CREATE INDEX IF NOT EXISTS idx_gorev_kaynak_gorev"
    " ON calisma_gorev_kaynaklari(gorev_id)",
    "CREATE INDEX IF NOT EXISTS idx_gorev_kaynak_kaynak"
    " ON calisma_gorev_kaynaklari(kaynak_turu, kaynak_id)",
    "CREATE INDEX IF NOT EXISTS idx_gorev_kaynak_ogrenci"
    " ON calisma_gorev_kaynaklari(ogrenci_id, cozuldu)",
)


def _tablo_kolonlari(conn, tablo):
    return [satir[1] for satir in conn.execute("PRAGMA table_info(%s)" % tablo)]


def init_db():
    """Tablo/indeksleri idempotent biçimde kurar (veri silmez)."""
    with _baglanti() as conn:
        with _islem(conn):
            conn.execute(_SEMA)
            # Görev tablosu program servisi tarafından kurulur. Bu modül
            # `gecersiz` kolonuna yazdığı için kolonun varlığını garanti eder
            # (tablo yoksa hiçbir şey yapılmaz).
            gorev_kolonlari = set(
                _tablo_kolonlari(conn, "calisma_programi_gorevler")
            )
            if gorev_kolonlari and "gecersiz" not in gorev_kolonlari:
                conn.execute(
                    "ALTER TABLE calisma_programi_gorevler"
                    " ADD COLUMN gecersiz INTEGER NOT NULL DEFAULT 0"
                )
            for sorgu in _INDEKSLER:
                conn.execute(sorgu)
    return True


# ==============================================================================
# YAZMA
# ==============================================================================
def _kaynak_normallestir(kaynaklar):
    """Kaynak listesini doğrular; `[{'tur': ..., 'id': ...}, ...]` döner."""
    if kaynaklar in (None, ""):
        return []
    if not isinstance(kaynaklar, (list, tuple)):
        raise KaynakHatasi("Kaynak listesi liste olmalıdır.")
    sonuc = []
    gorulen = set()
    for ham in kaynaklar:
        if isinstance(ham, dict):
            tur = _tur_dogrula(ham.get("tur") or ham.get("kaynak_turu"))
            kid = _id_dogrula(
                ham.get("id") if ham.get("id") is not None else ham.get("kaynak_id"),
                "kaynak numarası",
            )
        elif isinstance(ham, (list, tuple)) and len(ham) == 2:
            tur = _tur_dogrula(ham[0])
            kid = _id_dogrula(ham[1], "kaynak numarası")
        else:
            raise KaynakHatasi("Geçersiz kaynak tanımı: %r" % (ham,))
        if (tur, kid) in gorulen:
            continue
        gorulen.add((tur, kid))
        sonuc.append({"tur": tur, "id": kid})
    return sonuc


def kaynaklari_yaz(conn, ogrenci_id, program_id, gorev_id, kaynaklar, an=None):
    """Bağları YAZAR; bağlantı dışarıdan gelir (çağıran commit eder).

    `program_service._gorev_yaz` aynı transaction içinde çağırır. Mükerrer
    bağ `INSERT OR IGNORE` ile atlanır; dönüş: yazılan yeni bağ sayısı.
    """
    oid = _id_dogrula(ogrenci_id, "öğrenci numarası")
    gid = _id_dogrula(gorev_id, "görev numarası")
    pid = None if program_id in (None, "", 0) else _id_dogrula(
        program_id, "program numarası"
    )
    normal = _kaynak_normallestir(kaynaklar)
    if not normal:
        return 0
    zaman = _zaman_yaz(_an_zamani(an))
    yazilan = 0
    for kaynak in normal:
        imlec = conn.execute(
            "INSERT OR IGNORE INTO calisma_gorev_kaynaklari"
            " (ogrenci_id, program_id, gorev_id, kaynak_turu, kaynak_id,"
            "  cozuldu, olusturma_zamani)"
            " VALUES (?, ?, ?, ?, ?, 0, ?)",
            (oid, pid, gid, kaynak["tur"], kaynak["id"], zaman),
        )
        if imlec.rowcount:
            yazilan += 1
    return yazilan


def kaynaklari_kaydet(ogrenci_id, program_id, gorev_id, kaynaklar, an=None):
    """`kaynaklari_yaz`ın kendi transaction'ını açan sürümü (test / UI)."""
    with _baglanti() as conn:
        with _islem(conn):
            return kaynaklari_yaz(
                conn, ogrenci_id, program_id, gorev_id, kaynaklar, an=an
            )


def _gecersiz_kil(conn, gorev_idleri, zaman):
    """Bekleyen (durum = 0) görevleri geçersiz olarak işaretler.

    `calisma_programi_gorevler` şemasında `gecersiz` kolonu program
    servisi tarafından eklenir; `guncelleme_zamani` kolonu ise her sürümde
    bulunmaz. Bu yüzden zaman damgası yalnızca kolon varsa yazılır.
    """
    mevcut = set(_tablo_kolonlari(conn, "calisma_programi_gorevler"))
    zaman_ek = ", guncelleme_zamani = ?" if "guncelleme_zamani" in mevcut else ""
    sayi = 0
    for gid in gorev_idleri:
        degerler = (zaman, gid) if zaman_ek else (gid,)
        imlec = conn.execute(
            "UPDATE calisma_programi_gorevler SET gecersiz = 1%s"
            " WHERE id = ? AND durum = 0" % zaman_ek,
            degerler,
        )
        sayi += max(0, imlec.rowcount or 0)
    return sayi


def kaynak_isi_bitti(kaynak_turu, kaynak_id, gecersiz_kil=False, an=None):
    """Kaynağa bağlı görev bağlarını kapatır.

    `gecersiz_kil=True` ise kaynağa bağlı BEKLEYEN görevler `gecersiz = 1`
    olur (kaynak öğrenildi / arşivlendi ya da soru çözüldü). Dönüş:
    kapatılan bağ sayısı.
    """
    tur = _tur_dogrula(kaynak_turu)
    kid = _id_dogrula(kaynak_id, "kaynak numarası")
    zaman = _zaman_yaz(_an_zamani(an))
    with _baglanti() as conn:
        with _islem(conn):
            gorev_idleri = [
                int(satir["gorev_id"])
                for satir in conn.execute(
                    "SELECT DISTINCT gorev_id FROM calisma_gorev_kaynaklari"
                    " WHERE kaynak_turu = ? AND kaynak_id = ? AND cozuldu = 0",
                    (tur, kid),
                )
            ]
            if not gorev_idleri:
                return 0
            imlec = conn.execute(
                "UPDATE calisma_gorev_kaynaklari SET cozuldu = 1,"
                " cozulme_zamani = ? WHERE kaynak_turu = ? AND kaynak_id = ?"
                " AND cozuldu = 0",
                (zaman, tur, kid),
            )
            if gecersiz_kil:
                _gecersiz_kil(conn, gorev_idleri, zaman)
            return max(0, imlec.rowcount or 0)


# ==============================================================================
# OKUMA
# ==============================================================================
def gorev_kaynaklari(gorev_id):
    """Göreve bağlı kaynaklar (`{'tur', 'id', 'cozuldu'}` listesi)."""
    gid = _id_dogrula(gorev_id, "görev numarası")
    with _baglanti() as conn:
        return [
            {
                "tur": satir["kaynak_turu"],
                "id": int(satir["kaynak_id"]),
                "cozuldu": bool(satir["cozuldu"]),
            }
            for satir in conn.execute(
                "SELECT kaynak_turu, kaynak_id, cozuldu"
                " FROM calisma_gorev_kaynaklari WHERE gorev_id = ?"
                " ORDER BY id ASC",
                (gid,),
            )
        ]


def gorev_kaynak_sayaci(gorev_id):
    """Görevin kaynak sayaçları (arayüz rozetleri için)."""
    gid = _id_dogrula(gorev_id, "görev numarası")
    with _baglanti() as conn:
        satir = conn.execute(
            "SELECT COUNT(*) AS toplam,"
            " SUM(CASE WHEN cozuldu = 1 THEN 1 ELSE 0 END) AS cozuldu"
            " FROM calisma_gorev_kaynaklari WHERE gorev_id = ?",
            (gid,),
        ).fetchone()
    return {
        "toplam": int(satir["toplam"] or 0),
        "cozuldu": int(satir["cozuldu"] or 0),
    }


def bekleyen_kaynak_gorevleri(kaynak_turu, kaynak_id, sadece_gecerli=True):
    """Kaynağa bağlı, henüz kapanmamış görevler."""
    tur = _tur_dogrula(kaynak_turu)
    kid = _id_dogrula(kaynak_id, "kaynak numarası")
    sorgu = (
        "SELECT g.* FROM calisma_gorev_kaynaklari k"
        " JOIN calisma_programi_gorevler g ON g.id = k.gorev_id"
        " WHERE k.kaynak_turu = ? AND k.kaynak_id = ? AND k.cozuldu = 0"
    )
    if sadece_gecerli:
        sorgu += " AND g.durum = 0 AND IFNULL(g.gecersiz, 0) = 0"
    with _baglanti() as conn:
        return [dict(satir) for satir in conn.execute(sorgu, (tur, kid))]


# ==============================================================================
# KÖPRÜ: GÖREV TAMAMLANDI -> KAYNAK İLERLET
# ==============================================================================
def _tekrar_ilerlet(tekrar_id, an=None):
    try:
        from services import spaced_repetition
    except Exception:  # noqa: BLE001
        return False
    try:
        spaced_repetition.tekrar_tamamla(tekrar_id, an=an)
        return True
    except Exception:  # noqa: BLE001 - iptal edilmiş kayıt görevi kilitlemez
        return False


def _yanlis_soru_ilerlet(soru_id, an=None):
    try:
        from services import wrong_questions
    except Exception:  # noqa: BLE001
        return False
    try:
        wrong_questions.tekrar_edildi(soru_id, an=an)
        return True
    except Exception:  # noqa: BLE001
        return False


def gorev_tamamlandi(gorev_id, an=None):
    """Görev tamamlandığında bağlı kaynakları ilerletir.

    Bağlar tek hamlede kapatılır; kaynak durumları (tekrar kaydı / yanlış
    soru) kendi modüllerinde ilerletilir. İşlem idempotenttir: aynı görev
    ikinci kez tamamlanırsa sayaçlar artmaz.
    """
    gid = _id_dogrula(gorev_id, "görev numarası")
    zaman = _zaman_yaz(_an_zamani(an))
    with _baglanti() as conn:
        with _islem(conn):
            satirlar = [
                {"tur": satir["kaynak_turu"], "id": int(satir["kaynak_id"])}
                for satir in conn.execute(
                    "SELECT kaynak_turu, kaynak_id"
                    " FROM calisma_gorev_kaynaklari"
                    " WHERE gorev_id = ? AND cozuldu = 0 ORDER BY id ASC",
                    (gid,),
                )
            ]
            if not satirlar:
                return {"toplam": 0, KAYNAK_TEKRAR: 0, KAYNAK_YANLIS: 0}
            conn.execute(
                "UPDATE calisma_gorev_kaynaklari SET cozuldu = 1,"
                " cozulme_zamani = ? WHERE gorev_id = ? AND cozuldu = 0",
                (zaman, gid),
            )
    ozet = {"toplam": len(satirlar), KAYNAK_TEKRAR: 0, KAYNAK_YANLIS: 0}
    for kaynak in satirlar:
        if kaynak["tur"] == KAYNAK_TEKRAR:
            if _tekrar_ilerlet(kaynak["id"], an=an):
                ozet[KAYNAK_TEKRAR] += 1
        elif kaynak["tur"] == KAYNAK_YANLIS:
            if _yanlis_soru_ilerlet(kaynak["id"], an=an):
                ozet[KAYNAK_YANLIS] += 1
    return ozet
