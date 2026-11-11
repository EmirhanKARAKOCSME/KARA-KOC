"""FAZ 6B - Bireysel yanlış soru defteri.

Tasarım ilkeleri:

- **Soru bazlı kayıt.** Deneme sihirbazı konu bazlı yanlış sayısı üretir
  (`deneme_konu_yanlislari` = toplu veri, DEĞİŞTİRİLMEZ). Bu modül onun
  yerine geçmez; öğrencinin tek tek hatırladığı / işaretlediği soruları
  AYRICA saklar. Geçmiş toplu veriden geriye dönük soru kaydı üretilmez.
- **Öğrenci izolasyonu.** Her sorgu `ogrenci_id` ile süzülür; başka
  öğrencinin kaydı ne okunabilir ne güncellenebilir.
- **Konu hiyerarşisi korunur.** `mikro_konu` müfredattaki mikro konu
  (planner'daki `ana`), `alt_konu` ise o mikro konunun alt başlığıdır.
  Alt başlık bilinmiyorsa NULL kalır (uydurulmaz); bu durumda görev mikro
  konu seviyesinde planlanır.
- **Durum yaşam döngüsü.** `Yeni` -> `Tekrar Bekliyor` -> `Öğrenildi`;
  `Arşivlendi` her aktif durumdan ulaşılabilen ayrı bir uçtür. Öğrenilmiş
  kayıt kendiliğinden yeniden açılmaz (`yeniden_ac` açık çağrı gerektirir).
- **Defter notu öğrenme kanıtı değildir.** Alt konu ustalığı
  (`alt_konu_durumlari`) bu modülden ASLA yazılmaz.

Bu modül Streamlit'e bağımlı değildir; testler doğrudan çağırabilir.
"""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

TR_TZ = timezone(timedelta(hours=3))

DURUM_YENI = "Yeni"
DURUM_TEKRAR = "Tekrar Bekliyor"
DURUM_OGRENILDI = "Öğrenildi"
DURUM_ARSIV = "Arşivlendi"
DURUMLAR = (DURUM_YENI, DURUM_TEKRAR, DURUM_OGRENILDI, DURUM_ARSIV)
# Defterde "işi bitmemiş" sayılan durumlar (programa beslenen havuz).
AKTIF_DURUMLAR = (DURUM_YENI, DURUM_TEKRAR)

# Deneme sihirbazındaki hata nedeni listesiyle aynı sözlüktür.
HATA_TURLERI = (
    "Konu Eksikliği",
    "İşlem / Dikkat Hatası",
    "Süre Yetişmedi",
    "İki Şık Arasında Kaldım",
    "Soruyu Yanlış Okudum",
)
VARSAYILAN_HATA_TURU = HATA_TURLERI[0]

# Yanlış çözülen sorunun yeniden denenme aralığı (TAKVİM günü).
TEKRAR_ARALIGI_GUN = 2

MAKS_METIN_UZUNLUGU = 4000

KAYNAK_TURU = "yanlis_soru"

VARSAYILAN_DB_YOLU = "yks_veritabani.db"

_ZAMAN_KALIBI = "%Y-%m-%d %H:%M:%S"
_TARIH_KALIBI = "%Y-%m-%d"


class YanlisSoruHatasi(ValueError):
    """Geçersiz yanlış soru işlemi veya doğrulama hatası."""


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


def bugun():
    return simdi().date()


def _zaman_yaz(deger):
    if not deger:
        return None
    return deger.strftime(_ZAMAN_KALIBI)


def _metin(deger, ad=None, zorunlu=False, ust_sinir=MAKS_METIN_UZUNLUGU):
    metin = None if deger is None else str(deger).strip()
    if not metin:
        if zorunlu:
            raise YanlisSoruHatasi("%s boş olamaz." % (ad or "Değer"))
        return None
    if ust_sinir and len(metin) > ust_sinir:
        raise YanlisSoruHatasi(
            "%s çok uzun (en fazla %d karakter)." % (ad or "Değer", ust_sinir)
        )
    return metin


def _tarih_oku(deger, ad="Tarih"):
    """date / datetime / 'YYYY-AA-GG' değerini TR takvim gününe çevirir."""
    if isinstance(deger, datetime):
        return deger.date()
    if isinstance(deger, date):
        return deger
    metin = _metin(deger)
    if not metin:
        raise YanlisSoruHatasi("%s boş olamaz." % ad)
    try:
        return datetime.strptime(metin[:10], _TARIH_KALIBI).date()
    except ValueError:
        raise YanlisSoruHatasi(
            "%s geçersiz (YYYY-AA-GG beklenir): %s" % (ad, deger)
        ) from None


def _an_tarihi(an=None):
    """İşlem anının TR takvim günü."""
    if an is None:
        return simdi().date()
    if isinstance(an, datetime):
        if an.tzinfo is None:
            an = an.replace(tzinfo=TR_TZ)
        return an.astimezone(TR_TZ).date()
    if isinstance(an, date):
        return an
    return _tarih_oku(an, "İşlem tarihi")


def _an_zamani(an=None):
    """Kayıt zaman damgası (TR saati, saniye hassasiyetinde)."""
    if an is None:
        return simdi()
    if isinstance(an, datetime):
        if an.tzinfo is not None:
            return an.astimezone(TR_TZ)
        return an.replace(tzinfo=TR_TZ)
    return datetime.combine(
        _tarih_oku(an, "İşlem tarihi"), datetime.min.time(), tzinfo=TR_TZ
    )


def _ogrenci_dogrula(ogrenci_id):
    if isinstance(ogrenci_id, bool):
        raise YanlisSoruHatasi("Geçersiz öğrenci bilgisi.")
    try:
        oid = int(ogrenci_id)
    except (TypeError, ValueError):
        raise YanlisSoruHatasi("Geçersiz öğrenci bilgisi.") from None
    if oid <= 0:
        raise YanlisSoruHatasi("Geçersiz öğrenci bilgisi.")
    return oid


def _soru_id_dogrula(soru_id):
    if isinstance(soru_id, bool):
        raise YanlisSoruHatasi("Geçersiz soru numarası.")
    try:
        sid = int(soru_id)
    except (TypeError, ValueError):
        raise YanlisSoruHatasi("Geçersiz soru numarası.") from None
    if sid <= 0:
        raise YanlisSoruHatasi("Geçersiz soru numarası.")
    return sid


def _deneme_id_dogrula(deneme_id):
    if deneme_id in (None, "", 0, "0"):
        return None
    if isinstance(deneme_id, bool):
        raise YanlisSoruHatasi("Geçersiz deneme numarası.")
    try:
        did = int(deneme_id)
    except (TypeError, ValueError):
        raise YanlisSoruHatasi("Geçersiz deneme numarası.") from None
    if did <= 0:
        raise YanlisSoruHatasi("Geçersiz deneme numarası.")
    return did


def _hata_turu_dogrula(deger):
    metin = _metin(deger, "Hata türü") or VARSAYILAN_HATA_TURU
    if metin not in HATA_TURLERI:
        raise YanlisSoruHatasi(
            "Geçersiz hata türü: %s (geçerli: %s)"
            % (metin, ", ".join(HATA_TURLERI))
        )
    return metin


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
# ŞEMA (idempotent migrasyon - veri silmez, geçmiş kayıtlara dokunmaz)
# ==============================================================================
_SEMA = """
CREATE TABLE IF NOT EXISTS yanlis_sorular (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    ders TEXT NOT NULL,
    makro_konu TEXT,
    mikro_konu TEXT NOT NULL,
    alt_konu TEXT,
    hata_turu TEXT NOT NULL DEFAULT 'Konu Eksikliği',
    soru_metni TEXT,
    kaynak TEXT,
    soru_no TEXT,
    deneme_id INTEGER,
    deneme_tarihi TEXT,
    durum TEXT NOT NULL DEFAULT 'Yeni',
    aktif INTEGER NOT NULL DEFAULT 1,
    tekrar_sayisi INTEGER NOT NULL DEFAULT 0,
    son_tekrar_tarihi TEXT,
    sonraki_tekrar_tarihi TEXT,
    ogrenme_tarihi TEXT,
    notlar TEXT,
    olusturma_zamani TEXT NOT NULL,
    guncelleme_zamani TEXT,
    FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
)
"""

_INDEKSLER = (
    "CREATE INDEX IF NOT EXISTS idx_yanlis_ogrenci"
    " ON yanlis_sorular(ogrenci_id, durum)",
    "CREATE INDEX IF NOT EXISTS idx_yanlis_tekrar"
    " ON yanlis_sorular(ogrenci_id, sonraki_tekrar_tarihi)",
    "CREATE INDEX IF NOT EXISTS idx_yanlis_konu"
    " ON yanlis_sorular(ogrenci_id, ders, mikro_konu)",
    "CREATE INDEX IF NOT EXISTS idx_yanlis_deneme"
    " ON yanlis_sorular(deneme_id)",
)


def init_db():
    """Tablo/indeksleri idempotent biçimde kurar (veri silmez).

    Birden fazla kez çağrılabilir; mevcut deneme, program ve tekrar
    kayıtlarına dokunmaz.
    """
    with _baglanti() as conn:
        with _islem(conn):
            conn.execute(_SEMA)
            for sorgu in _INDEKSLER:
                conn.execute(sorgu)
    return True


# ==============================================================================
# YARDIMCILAR
# ==============================================================================
def _satir_sozluk(satir, gun=None):
    """Satırı sözlüğe çevirir; türetilmiş alanları ekler."""
    if satir is None:
        return None
    kayit = dict(satir)
    kayit["tekrar_sayisi"] = int(kayit.get("tekrar_sayisi") or 0)
    kayit["aktif"] = bool(kayit.get("aktif", 1))
    kayit["deneme_id"] = (
        int(kayit["deneme_id"]) if kayit.get("deneme_id") not in (None, "") else None
    )
    gun = gun or bugun()
    sonraki = kayit.get("sonraki_tekrar_tarihi")
    kayit["bekliyor"] = kayit.get("durum") in AKTIF_DURUMLAR
    kayit["gecikmis"] = bool(
        kayit["bekliyor"] and sonraki and _tarih_oku(sonraki) < gun
    )
    kayit["bugun"] = bool(kayit["bekliyor"] and sonraki and _tarih_oku(sonraki) == gun)
    return kayit


def _soru_satiri(conn, soru_id, ogrenci_id=None):
    sid = _soru_id_dogrula(soru_id)
    if ogrenci_id is None:
        satir = conn.execute(
            "SELECT * FROM yanlis_sorular WHERE id = ?", (sid,)
        ).fetchone()
    else:
        oid = _ogrenci_dogrula(ogrenci_id)
        satir = conn.execute(
            "SELECT * FROM yanlis_sorular WHERE id = ? AND ogrenci_id = ?",
            (sid, oid),
        ).fetchone()
    if satir is None:
        raise YanlisSoruHatasi("Yanlış soru kaydı bulunamadı (#%s)." % sid)
    return _satir_sozluk(satir)


def _mukerrer_soru(conn, veri, ogrenci_id):
    """Aynı öğrenci + ders + konu + soru metni için aktif kayıt var mı?"""
    metin = veri.get("soru_metni")
    if not metin:
        return None
    satir = conn.execute(
        "SELECT id FROM yanlis_sorular WHERE ogrenci_id = ?"
        " AND ders = ? AND mikro_konu = ? AND IFNULL(alt_konu, '') = ?"
        " AND IFNULL(soru_metni, '') = ? AND durum IN (?, ?)"
        " LIMIT 1",
        (
            ogrenci_id,
            veri["ders"],
            veri["mikro_konu"],
            veri.get("alt_konu") or "",
            metin,
            AKTIF_DURUMLAR[0],
            AKTIF_DURUMLAR[1],
        ),
    ).fetchone()
    return None if satir is None else int(satir["id"])


def _kaynak_isi_bitti(soru_id, gecersiz_kil=False, an=None):
    """Görev bağlantısını kapatır (FAZ 6C köprüsü, isteğe bağlı)."""
    try:
        from services import gorev_kaynaklari
    except Exception:  # noqa: BLE001 - FAZ 6C modülü yoksa defter yine çalışır
        return 0
    try:
        return gorev_kaynaklari.kaynak_isi_bitti(
            KAYNAK_TURU, soru_id, gecersiz_kil=gecersiz_kil, an=an
        )
    except Exception:  # noqa: BLE001 - köprü hatası defteri kilitlemez
        return 0


# ==============================================================================
# YAZMA
# ==============================================================================
def yanlis_soru_ekle(
    ogrenci_id,
    ders,
    mikro_konu,
    makro_konu=None,
    alt_konu=None,
    hata_turu=None,
    soru_metni=None,
    kaynak=None,
    soru_no=None,
    deneme_id=None,
    deneme_tarihi=None,
    notlar=None,
    an=None,
):
    """Deftere yeni yanlış soru ekler ve kaydı döndürür.

    `mikro_konu` müfredattaki mikro konudur (zorunlu); `alt_konu` verilirse
    yalnızca o mikro konunun alt başlığı olarak saklanır. Aynı soru metni
    ikinci kez aktif olarak eklenemez (mükerrer kayıt koruması).
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    veri = {
        "ders": _metin(ders, "Ders", zorunlu=True, ust_sinir=120),
        "mikro_konu": _metin(mikro_konu, "Mikro konu", zorunlu=True, ust_sinir=200),
        "makro_konu": _metin(makro_konu, "Makro konu", ust_sinir=200),
        "alt_konu": _metin(alt_konu, "Alt konu", ust_sinir=200),
        "hata_turu": _hata_turu_dogrula(hata_turu),
        "soru_metni": _metin(soru_metni, "Soru metni"),
        "kaynak": _metin(kaynak, "Kaynak", ust_sinir=200),
        "soru_no": _metin(soru_no, "Soru numarası", ust_sinir=60),
        "deneme_id": _deneme_id_dogrula(deneme_id),
        "deneme_tarihi": None,
        "notlar": _metin(notlar, "Notlar"),
    }
    if _metin(deneme_tarihi):
        veri["deneme_tarihi"] = _tarih_oku(
            deneme_tarihi, "Deneme tarihi"
        ).isoformat()
    gun = _an_tarihi(an)
    zaman = _zaman_yaz(_an_zamani(an))
    with _baglanti() as conn:
        with _islem(conn):
            mukerrer = _mukerrer_soru(conn, veri, oid)
            if mukerrer:
                raise YanlisSoruHatasi("Bu soru defterde zaten var (#%d)." % mukerrer)
            imlec = conn.execute(
                "INSERT INTO yanlis_sorular"
                " (ogrenci_id, ders, makro_konu, mikro_konu, alt_konu, hata_turu,"
                "  soru_metni, kaynak, soru_no, deneme_id, deneme_tarihi, durum,"
                "  aktif, tekrar_sayisi, sonraki_tekrar_tarihi, olusturma_zamani,"
                "  notlar)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?)",
                (
                    oid,
                    veri["ders"],
                    veri["makro_konu"],
                    veri["mikro_konu"],
                    veri["alt_konu"],
                    veri["hata_turu"],
                    veri["soru_metni"],
                    veri["kaynak"],
                    veri["soru_no"],
                    veri["deneme_id"],
                    veri["deneme_tarihi"],
                    DURUM_YENI,
                    gun.isoformat(),
                    zaman,
                    veri["notlar"],
                ),
            )
            yeni_id = int(imlec.lastrowid)
    return yanlis_soru_getir(yeni_id)


def yanlis_soru_guncelle(soru_id, ogrenci_id=None, an=None, **alanlar):
    """Kaydın içerik alanlarını günceller (durum için ayrı fonksiyonlar var)."""
    sid = _soru_id_dogrula(soru_id)
    izinli = {
        "ders",
        "makro_konu",
        "mikro_konu",
        "alt_konu",
        "hata_turu",
        "soru_metni",
        "kaynak",
        "soru_no",
        "notlar",
    }
    bilinmeyen = set(alanlar) - izinli
    if bilinmeyen:
        raise YanlisSoruHatasi(
            "Güncellenemeyen alan(lar): %s" % ", ".join(sorted(bilinmeyen))
        )
    if not alanlar:
        return yanlis_soru_getir(sid, ogrenci_id=ogrenci_id)
    degerler = {}
    for alan, deger in alanlar.items():
        if alan == "hata_turu":
            degerler[alan] = _hata_turu_dogrula(deger)
        elif alan in ("ders", "mikro_konu"):
            degerler[alan] = _metin(
                deger, alan.replace("_", " ").title(), zorunlu=True, ust_sinir=200
            )
        else:
            degerler[alan] = _metin(deger, alan.replace("_", " ").title())
    degerler["guncelleme_zamani"] = _zaman_yaz(_an_zamani(an))
    with _baglanti() as conn:
        with _islem(conn):
            mevcut = _soru_satiri(conn, sid, ogrenci_id)
            if mevcut["durum"] == DURUM_ARSIV:
                raise YanlisSoruHatasi(
                    "Arşivlenmiş kayıt düzenlenemez; önce arşivden çıkarın."
                )
            atama = ", ".join("%s = ?" % alan for alan in degerler)
            conn.execute(
                "UPDATE yanlis_sorular SET %s WHERE id = ?" % atama,
                list(degerler.values()) + [sid],
            )
    return yanlis_soru_getir(sid, ogrenci_id=ogrenci_id)


def _durum_yaz(conn, soru_id, degerler):
    """Verilen alanları tek UPDATE ile yazar (durum geçişleri için)."""
    atama = ", ".join("%s = ?" % alan for alan in degerler)
    conn.execute(
        "UPDATE yanlis_sorular SET %s WHERE id = ?" % atama,
        list(degerler.values()) + [int(soru_id)],
    )


def tekrar_sonucu_kaydet(soru_id, cozuldu, notlar=None, an=None, ogrenci_id=None):
    """Tekrar sonucunu işler.

    - `cozuldu=True`  : kayıt `Öğrenildi` olur, tekrar tarihi temizlenir ve
      kayda bağlı bekleyen program görevleri geçersiz kılınır.
    - `cozuldu=False` : kayıt yeniden havuza döner (`Tekrar Bekliyor`),
      bir sonraki tekrar `TEKRAR_ARALIGI_GUN` gün sonradır. Kayıt haftaya
      devrettiği için programdaki görev yerinde kalır (geçersiz kılınmaz).
    """
    sid = _soru_id_dogrula(soru_id)
    gun = _an_tarihi(an)
    zaman = _zaman_yaz(_an_zamani(an))
    with _baglanti() as conn:
        with _islem(conn):
            mevcut = _soru_satiri(conn, sid, ogrenci_id)
            if mevcut["durum"] == DURUM_ARSIV:
                raise YanlisSoruHatasi(
                    "Arşivlenmiş kayıt için tekrar sonucu kaydedilemez."
                )
            if mevcut["durum"] == DURUM_OGRENILDI:
                if cozuldu:
                    return mevcut  # aynı işlem iki kez çalışsa da sayaç artmaz
                raise YanlisSoruHatasi(
                    "Öğrenildi olarak işaretlenmiş kayıt yeniden açılmadan"
                    " 'yapamadım' olarak işaretlenemez."
                )
            alanlar = {
                "tekrar_sayisi": mevcut["tekrar_sayisi"] + 1,
                "son_tekrar_tarihi": gun.isoformat(),
                "guncelleme_zamani": zaman,
            }
            if notlar is not None:
                alanlar["notlar"] = _metin(notlar, "Notlar")
            if cozuldu:
                alanlar["durum"] = DURUM_OGRENILDI
                alanlar["ogrenme_tarihi"] = gun.isoformat()
                alanlar["sonraki_tekrar_tarihi"] = None
            else:
                alanlar["durum"] = DURUM_TEKRAR
                alanlar["sonraki_tekrar_tarihi"] = (
                    gun + timedelta(days=TEKRAR_ARALIGI_GUN)
                ).isoformat()
            _durum_yaz(conn, sid, alanlar)
    _kaynak_isi_bitti(sid, gecersiz_kil=bool(cozuldu), an=an)
    return yanlis_soru_getir(sid, ogrenci_id=ogrenci_id)


def ogrenildi_isaretle(soru_id, an=None, ogrenci_id=None):
    """Kaydı `Öğrenildi` yapar (kısa yol)."""
    return tekrar_sonucu_kaydet(soru_id, True, an=an, ogrenci_id=ogrenci_id)


def tekrar_edildi(soru_id, an=None, ogrenci_id=None):
    """Görev tamamlandı ama sonuç bildirilmedi: tekrar sayacını ilerletir.

    Öğrenilmiş / arşivlenmiş kayıt DEĞİŞMEZ; öğrenme durumu yalnızca açık
    sonuç bildirimiyle (`tekrar_sonucu_kaydet`) değişir.
    """
    sid = _soru_id_dogrula(soru_id)
    gun = _an_tarihi(an)
    zaman = _zaman_yaz(_an_zamani(an))
    with _baglanti() as conn:
        with _islem(conn):
            mevcut = _soru_satiri(conn, sid, ogrenci_id)
            if mevcut["durum"] not in AKTIF_DURUMLAR:
                return mevcut
            _durum_yaz(
                conn,
                sid,
                {
                    "tekrar_sayisi": mevcut["tekrar_sayisi"] + 1,
                    "son_tekrar_tarihi": gun.isoformat(),
                    "sonraki_tekrar_tarihi": (
                        gun + timedelta(days=TEKRAR_ARALIGI_GUN)
                    ).isoformat(),
                    "durum": DURUM_TEKRAR,
                    "guncelleme_zamani": zaman,
                },
            )
    return yanlis_soru_getir(sid, ogrenci_id=ogrenci_id)


def arsivle(soru_id, an=None, ogrenci_id=None):
    """Kaydı arşivler (silmez); bekleyen görev bağlantıları geçersiz kılınır."""
    sid = _soru_id_dogrula(soru_id)
    zaman = _zaman_yaz(_an_zamani(an))
    with _baglanti() as conn:
        with _islem(conn):
            mevcut = _soru_satiri(conn, sid, ogrenci_id)
            if mevcut["durum"] == DURUM_ARSIV:
                return mevcut
            _durum_yaz(
                conn,
                sid,
                {
                    "durum": DURUM_ARSIV,
                    "aktif": 0,
                    "sonraki_tekrar_tarihi": None,
                    "guncelleme_zamani": zaman,
                },
            )
    _kaynak_isi_bitti(sid, gecersiz_kil=True, an=an)
    return yanlis_soru_getir(sid, ogrenci_id=ogrenci_id)


def arsivden_cikar(soru_id, an=None, ogrenci_id=None):
    """Arşivdeki kaydı yeniden aktif havuza alır."""
    sid = _soru_id_dogrula(soru_id)
    gun = _an_tarihi(an)
    zaman = _zaman_yaz(_an_zamani(an))
    with _baglanti() as conn:
        with _islem(conn):
            mevcut = _soru_satiri(conn, sid, ogrenci_id)
            if mevcut["durum"] != DURUM_ARSIV:
                return mevcut
            _durum_yaz(
                conn,
                sid,
                {
                    "durum": DURUM_TEKRAR,
                    "aktif": 1,
                    "sonraki_tekrar_tarihi": gun.isoformat(),
                    "guncelleme_zamani": zaman,
                },
            )
    return yanlis_soru_getir(sid, ogrenci_id=ogrenci_id)


def yeniden_ac(soru_id, an=None, ogrenci_id=None):
    """`Öğrenildi` işaretini geri alır (soru yine yanlış çözüldüğünde)."""
    sid = _soru_id_dogrula(soru_id)
    gun = _an_tarihi(an)
    zaman = _zaman_yaz(_an_zamani(an))
    with _baglanti() as conn:
        with _islem(conn):
            mevcut = _soru_satiri(conn, sid, ogrenci_id)
            if mevcut["durum"] != DURUM_OGRENILDI:
                return mevcut
            _durum_yaz(
                conn,
                sid,
                {
                    "durum": DURUM_TEKRAR,
                    "aktif": 1,
                    "ogrenme_tarihi": None,
                    "sonraki_tekrar_tarihi": gun.isoformat(),
                    "guncelleme_zamani": zaman,
                },
            )
    return yanlis_soru_getir(sid, ogrenci_id=ogrenci_id)


# ==============================================================================
# OKUMA
# ==============================================================================
def yanlis_soru_getir(soru_id, ogrenci_id=None):
    """Tek kayıt (yoksa hata); `ogrenci_id` verilirse izolasyon uygulanır."""
    with _baglanti() as conn:
        return _soru_satiri(conn, soru_id, ogrenci_id)


def yanlis_sorulari_getir(
    ogrenci_id,
    ders=None,
    durum=None,
    sadece_aktif=False,
    arama=None,
    limit=None,
):
    """Öğrencinin defter kayıtları (yeni -> eski).

    `sadece_aktif=True` ise yalnızca `Yeni` / `Tekrar Bekliyor` kayıtları
    döner. `arama` ders, konu, soru metni ve notlarda büyük/küçük harf
    duyarsız arama yapar.
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    sorgu = "SELECT * FROM yanlis_sorular WHERE ogrenci_id = ?"
    degerler = [oid]
    if ders:
        sorgu += " AND ders = ?"
        degerler.append(_metin(ders, "Ders"))
    if durum:
        durum = _metin(durum, "Durum")
        if durum not in DURUMLAR:
            raise YanlisSoruHatasi("Geçersiz durum: %s" % durum)
        sorgu += " AND durum = ?"
        degerler.append(durum)
    elif sadece_aktif:
        sorgu += " AND durum IN (?, ?)"
        degerler.extend(AKTIF_DURUMLAR)
    metin = _metin(arama)
    if metin:
        sorgu += (
            " AND (ders LIKE ? OR IFNULL(makro_konu, '') LIKE ?"
            " OR mikro_konu LIKE ? OR IFNULL(alt_konu, '') LIKE ?"
            " OR IFNULL(soru_metni, '') LIKE ? OR IFNULL(notlar, '') LIKE ?)"
        )
        desen = "%%%s%%" % metin
        degerler.extend([desen] * 6)
    sorgu += " ORDER BY id DESC"
    if limit:
        try:
            sinir = max(1, int(limit))
        except (TypeError, ValueError):
            raise YanlisSoruHatasi("Geçersiz kayıt limiti.") from None
        sorgu += " LIMIT %d" % sinir
    with _baglanti() as conn:
        return [_satir_sozluk(satir) for satir in conn.execute(sorgu, degerler)]


def bekleyen_yanlis_sorular(ogrenci_id, gun=None, bitis=None, ders=None, limit=None):
    """Programa beslenecek bekleyen sorular (tekrar zamanı gelmiş olanlar).

    `bitis` verilirse o tarihe kadar tekrarı gelen kayıtlar da döner
    (haftalık planlama penceresi). Tekrar tarihi boş olan yeni kayıtlar her
    zaman havuza girer.
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    gun = _tarih_oku(gun, "Referans gün") if gun is not None else bugun()
    sinir = _tarih_oku(bitis, "Bitiş tarihi") if bitis is not None else gun
    if sinir < gun:
        sinir = gun
    sorgu = (
        "SELECT * FROM yanlis_sorular WHERE ogrenci_id = ?"
        " AND durum IN (?, ?)"
        " AND (sonraki_tekrar_tarihi IS NULL OR sonraki_tekrar_tarihi <= ?)"
    )
    degerler = [oid, AKTIF_DURUMLAR[0], AKTIF_DURUMLAR[1], sinir.isoformat()]
    if ders:
        sorgu += " AND ders = ?"
        degerler.append(_metin(ders, "Ders"))
    sorgu += " ORDER BY IFNULL(sonraki_tekrar_tarihi, '') ASC, id ASC"
    if limit:
        try:
            sorgu += " LIMIT %d" % max(1, int(limit))
        except (TypeError, ValueError):
            raise YanlisSoruHatasi("Geçersiz kayıt limiti.") from None
    with _baglanti() as conn:
        return [_satir_sozluk(satir, gun) for satir in conn.execute(sorgu, degerler)]


def yanlis_soru_ozeti(ogrenci_id, gun=None):
    """Defter sayaçları (ders kırılımı dahil)."""
    oid = _ogrenci_dogrula(ogrenci_id)
    gun = _tarih_oku(gun, "Referans gün") if gun is not None else bugun()
    with _baglanti() as conn:
        satirlar = conn.execute(
            "SELECT durum, ders, sonraki_tekrar_tarihi FROM yanlis_sorular"
            " WHERE ogrenci_id = ?",
            (oid,),
        ).fetchall()
    ozet = {
        "toplam": 0,
        "yeni": 0,
        "tekrar": 0,
        "ogrenildi": 0,
        "arsiv": 0,
        "bekleyen": 0,
        "gecikmis": 0,
        "bugun": 0,
        "dersler": {},
    }
    for satir in satirlar:
        durum = satir["durum"]
        ders = satir["ders"] or "-"
        ozet["toplam"] += 1
        ders_ozet = ozet["dersler"].setdefault(
            ders, {"toplam": 0, "bekleyen": 0, "ogrenildi": 0}
        )
        ders_ozet["toplam"] += 1
        if durum == DURUM_YENI:
            ozet["yeni"] += 1
        elif durum == DURUM_TEKRAR:
            ozet["tekrar"] += 1
        elif durum == DURUM_ARSIV:
            ozet["arsiv"] += 1
        else:
            ozet["ogrenildi"] += 1
            ders_ozet["ogrenildi"] += 1
        if durum in AKTIF_DURUMLAR:
            ozet["bekleyen"] += 1
            ders_ozet["bekleyen"] += 1
            tarih = satir["sonraki_tekrar_tarihi"]
            if tarih:
                fark = (gun - _tarih_oku(tarih)).days
                if fark > 0:
                    ozet["gecikmis"] += 1
                elif fark == 0:
                    ozet["bugun"] += 1
    return ozet
