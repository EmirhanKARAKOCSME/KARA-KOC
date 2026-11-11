"""FAZ 6A - Aralıklı tekrar motoru.

Tasarım ilkeleri:

- **Tekrar, gerçek öğrenme olayından doğar.** Haftalık programda bir konunun
  bulunması öğrenildiği anlamına gelmez. Kayıt yalnızca öğrenme görevinin
  checklist'i tamamen bittiğinde (FAZ 5B `gorev_durum_guncelle` 0 -> 1 geçişi)
  ve görevde tamamlanmış bir öğrenme adımı (`izle` / `not`) varsa oluşturulur.
- **Eski görevlerden geriye dönük öğrenilmişlik uydurulmaz.** Geçmişte
  tamamlanmış görevler için toplu kayıt üretilmez; migrasyon veri yazmaz.
- **Takvim günü aritmetiği.** Tekrar tarihi öğrenme günü + 3 / + 5 takvim
  günüdür. Hafta sonu veya tatil nedeniyle tarih kaydırılmaz, geciken tekrar
  taşınmaz veya silinmez; `Bekliyor` olarak korunur.
- **Mükerrer kayıt yok.** Aynı öğrenme olayı (görev) için aynı tekrar türünde
  ikinci kayıt açılmaz; aynı konu + tür için aynı anda tek `Bekliyor` kaydı
  bulunur. Bu kural veritabanı seviyesinde kısmi UNIQUE indekslerle güvence
  altındadır (sayfa yenilemesi / yeniden kaydetme çoğaltmaz).
- **Pedagojik sınıflandırma mevcuttan okunur.** 5 günlük özet notu tekrarı
  yalnızca görevin kalıcı `pedagoji_turu = 'Ezber'` değerinde ve kısa not adımı
  tamamlandığında planlanır; `Pekiştirme` görevlerine uygulanmaz. Burada yeni
  bir ders sınıflandırması tanımlanmaz.

Kayıtlar bağımsız `tekrar_kayitlari` tablosunda tutulur. FAZ 6A yalnızca
motoru ve sorgulanabilir veriyi üretir; haftalık programın öncelik algoritması
değiştirilmez (program entegrasyonu FAZ 6C).

Bu modül Streamlit'e bağımlı değildir; testler doğrudan çağırabilir.
"""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

from services import task_steps

TR_TZ = timezone(timedelta(hours=3))

DURUM_BEKLIYOR = "Bekliyor"
DURUM_TAMAMLANDI = "Tamamlandı"
DURUM_IPTAL = "İptal Edildi"
DURUMLAR = (DURUM_BEKLIYOR, DURUM_TAMAMLANDI, DURUM_IPTAL)

TEKRAR_TURU_3_GUN = "3 Günlük Tekrar"
TEKRAR_TURU_5_GUN_NOT = "5 Günlük Özet Notu"
TEKRAR_TURLERI = (TEKRAR_TURU_3_GUN, TEKRAR_TURU_5_GUN_NOT)

# Öğrenme gününden sonra eklenecek TAKVİM günü sayısı.
TEKRAR_GUN_SAYISI = 3
NOT_TEKRARI_GUN_SAYISI = 5

EZBER_PEDAGOJISI = "Ezber"

# Öğrenme olayı sayılmayan yer tutucu konular. main.py'deki program
# motorları gerçek müfredat adayı kalmadığında bu satırları üretir; bunlar
# öğrenilen bir konu değil, doldurma / prova bloğudur.
YER_TUTUCU_KONULAR = ("Soru Çözümü & Prova", "Özet Not Çalışması")

VARSAYILAN_DB_YOLU = "yks_veritabani.db"

_ZAMAN_KALIBI = "%Y-%m-%d %H:%M:%S"
_TARIH_KALIBI = "%Y-%m-%d"


class TekrarHatasi(ValueError):
    """Geçersiz tekrar işlemi veya doğrulama hatası."""


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


def _metin(deger):
    if deger is None:
        return None
    metin = str(deger).strip()
    return metin or None


def _tarih_oku(deger, ad="Tarih"):
    """date / datetime / 'YYYY-AA-GG' değerini TR takvim gününe çevirir."""
    if isinstance(deger, datetime):
        return deger.date()
    if isinstance(deger, date):
        return deger
    metin = _metin(deger)
    if not metin:
        raise TekrarHatasi("%s boş olamaz." % ad)
    try:
        return datetime.strptime(metin[:10], _TARIH_KALIBI).date()
    except ValueError:
        raise TekrarHatasi(
            "%s geçersiz (YYYY-AA-GG beklenir): %s" % (ad, deger)
        ) from None


def _an_tarihi(an=None):
    """Öğrenme/tamamlama anının TR takvim günü."""
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
    return datetime.combine(_tarih_oku(an), datetime.min.time(), tzinfo=TR_TZ)


def _ogrenci_dogrula(ogrenci_id):
    if isinstance(ogrenci_id, bool):
        raise TekrarHatasi("Geçersiz öğrenci bilgisi.")
    try:
        oid = int(ogrenci_id)
    except (TypeError, ValueError):
        raise TekrarHatasi("Geçersiz öğrenci bilgisi.") from None
    if oid <= 0:
        raise TekrarHatasi("Geçersiz öğrenci bilgisi.")
    return oid


def _tekrar_id_dogrula(tekrar_id):
    if isinstance(tekrar_id, bool):
        raise TekrarHatasi("Geçersiz tekrar numarası.")
    try:
        rid = int(tekrar_id)
    except (TypeError, ValueError):
        raise TekrarHatasi("Geçersiz tekrar numarası.") from None
    if rid <= 0:
        raise TekrarHatasi("Geçersiz tekrar numarası.")
    return rid


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
# ŞEMA (idempotent migrasyon - veri silmez, geçmiş görevlere dokunmaz)
# ==============================================================================
_SEMA = """
CREATE TABLE IF NOT EXISTS tekrar_kayitlari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    ders TEXT NOT NULL,
    makro_konu TEXT,
    mikro_konu TEXT NOT NULL,
    tekrar_turu TEXT NOT NULL,
    kaynak_gorev_id INTEGER,
    kaynak_adim_id INTEGER,
    planlanan_tarih TEXT NOT NULL,
    durum TEXT NOT NULL DEFAULT 'Bekliyor',
    ogrenme_tarihi TEXT NOT NULL,
    pedagoji_turu TEXT,
    hedef_soru INTEGER NOT NULL DEFAULT 0,
    aciklama TEXT,
    olusturma_zamani TEXT NOT NULL,
    guncelleme_zamani TEXT,
    tamamlanma_zamani TEXT,
    FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE,
    FOREIGN KEY(kaynak_gorev_id) REFERENCES calisma_programi_gorevler(id)
        ON DELETE SET NULL,
    FOREIGN KEY(kaynak_adim_id) REFERENCES calisma_gorev_alt_adimlari(id)
        ON DELETE SET NULL
)
"""

_EK_KOLONLAR = (
    ("ogrenme_tarihi", "TEXT"),
    ("pedagoji_turu", "TEXT"),
    ("hedef_soru", "INTEGER NOT NULL DEFAULT 0"),
    ("aciklama", "TEXT"),
    ("guncelleme_zamani", "TEXT"),
)

_INDEKSLER = (
    "CREATE INDEX IF NOT EXISTS idx_tekrar_ogrenci_tarih"
    " ON tekrar_kayitlari(ogrenci_id, planlanan_tarih)",
    "CREATE INDEX IF NOT EXISTS idx_tekrar_durum"
    " ON tekrar_kayitlari(ogrenci_id, durum, planlanan_tarih)",
    "CREATE INDEX IF NOT EXISTS idx_tekrar_kaynak_gorev"
    " ON tekrar_kayitlari(kaynak_gorev_id)",
    # Bir öğrenme olayı (görev) + tekrar türü için tek kayıt.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_tekrar_ogrenme_olayi"
    " ON tekrar_kayitlari(ogrenci_id, kaynak_gorev_id, tekrar_turu)"
    " WHERE kaynak_gorev_id IS NOT NULL",
    # Aynı konu + tür için aynı anda yalnızca BİR bekleyen tekrar.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_tekrar_tek_bekleyen"
    " ON tekrar_kayitlari(ogrenci_id, ders, COALESCE(makro_konu, ''),"
    " mikro_konu, tekrar_turu) WHERE durum = 'Bekliyor'",
)


def _tablo_kolonlari(conn, tablo):
    return [satir[1] for satir in conn.execute("PRAGMA table_info(%s)" % tablo)]


def init_db():
    """Tablo/indeksleri idempotent biçimde kurar (veri silmez).

    Birden fazla kez çağrılabilir; mevcut görev, program, oturum ve deneme
    kayıtlarına dokunmaz.
    """
    with _baglanti() as conn:
        with _islem(conn):
            conn.execute(_SEMA)
            mevcut = set(_tablo_kolonlari(conn, "tekrar_kayitlari"))
            for kolon, tip in _EK_KOLONLAR:
                if kolon not in mevcut:
                    conn.execute(
                        "ALTER TABLE tekrar_kayitlari ADD COLUMN %s %s"
                        % (kolon, tip)
                    )
            for sorgu in _INDEKSLER:
                conn.execute(sorgu)
    return True


# ==============================================================================
# TARİH HESABI (saf takvim günü; hafta sonu/tatil kaydırması YOK)
# ==============================================================================
def planlanan_tarih_hesapla(ogrenme_tarihi, gun_sayisi=TEKRAR_GUN_SAYISI):
    """Öğrenme tarihine takvim günü ekler ('2026-05-04' + 3 -> '2026-05-07').

    Hafta sonu, resmî tatil veya "iş gününe taşıma" kuralı uygulanmaz.
    """
    try:
        gun = int(gun_sayisi)
    except (TypeError, ValueError):
        raise TekrarHatasi("Gün sayısı sayı olmalıdır.") from None
    if gun <= 0:
        raise TekrarHatasi("Gün sayısı pozitif olmalıdır.")
    return (_tarih_oku(ogrenme_tarihi, "Öğrenme tarihi") + timedelta(days=gun)).isoformat()


def gun_farki(planlanan_tarih, gun=None):
    """Planlanan tarih ile referans gün arasındaki fark (gün).

    Negatif değer gecikmiş tekrar demektir; kayıt yine `Bekliyor` kalır.
    """
    hedef = _tarih_oku(planlanan_tarih, "Planlanan tarih")
    referans = bugun() if gun is None else _an_tarihi(gun)
    return (hedef - referans).days


# ==============================================================================
# OKUMA
# ==============================================================================
def _satir_sozluk(satir, gun=None):
    if satir is None:
        return None
    kayit = dict(satir)
    kayit["hedef_soru"] = int(kayit.get("hedef_soru") or 0)
    # Gecikmişlik türetilmiş bilgidir: kayıt `Bekliyor` kalır, tarihi değişmez.
    kayit["gecikmis"] = bool(
        kayit.get("durum") == DURUM_BEKLIYOR
        and gun_farki(satir["planlanan_tarih"], gun) < 0
    )
    return kayit


def _tekrar_satiri(conn, tekrar_id):
    rid = _tekrar_id_dogrula(tekrar_id)
    satir = conn.execute(
        "SELECT * FROM tekrar_kayitlari WHERE id = ?", (rid,)
    ).fetchone()
    if satir is None:
        raise TekrarHatasi("Tekrar kaydı bulunamadı (#%s)." % rid)
    return _satir_sozluk(satir)


def tekrar_getir(tekrar_id):
    """Tek tekrar kaydı (yoksa None)."""
    try:
        with _baglanti() as conn:
            return _tekrar_satiri(conn, tekrar_id)
    except TekrarHatasi:
        return None


def tekrar_listesi(ogrenci_id, durum=None, baslangic=None, bitis=None, gun=None):
    """Öğrencinin tekrar kayıtları (planlanan tarihe göre artan).

    `durum` verilmezse tüm durumlar döner. Tarih aralığı planlanan tarihe
    göre filtrelenir; gecikenler gizlenmez.
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    sorgu = "SELECT * FROM tekrar_kayitlari WHERE ogrenci_id = ?"
    params = [oid]
    if durum:
        durum_listesi = [durum] if isinstance(durum, str) else list(durum)
        gecersiz = [d for d in durum_listesi if d not in DURUMLAR]
        if gecersiz:
            raise TekrarHatasi("Geçersiz tekrar durumu: %s" % gecersiz[0])
        sorgu += " AND durum IN (%s)" % ", ".join("?" * len(durum_listesi))
        params.extend(durum_listesi)
    if baslangic:
        sorgu += " AND planlanan_tarih >= ?"
        params.append(_tarih_oku(baslangic, "Başlangıç tarihi").isoformat())
    if bitis:
        sorgu += " AND planlanan_tarih <= ?"
        params.append(_tarih_oku(bitis, "Bitiş tarihi").isoformat())
    sorgu += " ORDER BY planlanan_tarih ASC, id ASC"
    with _baglanti() as conn:
        satirlar = conn.execute(sorgu, tuple(params)).fetchall()
    return [_satir_sozluk(s, gun) for s in satirlar]


def bekleyen_tekrarlar(ogrenci_id, gun=None, sadece_bugun=False):
    """Bugün ve öncesinde planlanmış, hâlâ `Bekliyor` olan tekrarlar.

    Gecikmiş kayıtlar silinmez ve ileri bir tarihe taşınmaz; aynı sorguda
    `gecikmis = True` işaretiyle döner.
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    referans = _an_tarihi(gun)
    with _baglanti() as conn:
        if sadece_bugun:
            satirlar = conn.execute(
                "SELECT * FROM tekrar_kayitlari WHERE ogrenci_id = ? AND durum = ?"
                " AND planlanan_tarih = ? ORDER BY planlanan_tarih ASC, id ASC",
                (oid, DURUM_BEKLIYOR, referans.isoformat()),
            ).fetchall()
        else:
            satirlar = conn.execute(
                "SELECT * FROM tekrar_kayitlari WHERE ogrenci_id = ? AND durum = ?"
                " AND planlanan_tarih <= ? ORDER BY planlanan_tarih ASC, id ASC",
                (oid, DURUM_BEKLIYOR, referans.isoformat()),
            ).fetchall()
    return [_satir_sozluk(s, referans) for s in satirlar]


def gecikmis_tekrarlar(ogrenci_id, gun=None):
    """Planlanan tarihi geçmiş, hâlâ `Bekliyor` olan tekrarlar."""
    oid = _ogrenci_dogrula(ogrenci_id)
    referans = _an_tarihi(gun)
    with _baglanti() as conn:
        satirlar = conn.execute(
            "SELECT * FROM tekrar_kayitlari WHERE ogrenci_id = ? AND durum = ?"
            " AND planlanan_tarih < ? ORDER BY planlanan_tarih ASC, id ASC",
            (oid, DURUM_BEKLIYOR, referans.isoformat()),
        ).fetchall()
    return [_satir_sozluk(s, referans) for s in satirlar]


def tekrar_ozeti(ogrenci_id, gun=None):
    """Öğrencinin tekrar sayaçları (bekleyen / bugün / gecikmiş / biten)."""
    oid = _ogrenci_dogrula(ogrenci_id)
    referans = _an_tarihi(gun)
    gun_str = referans.isoformat()
    with _baglanti() as conn:
        satirlar = conn.execute(
            "SELECT durum, planlanan_tarih, COUNT(*) AS adet"
            " FROM tekrar_kayitlari WHERE ogrenci_id = ?"
            " GROUP BY durum, planlanan_tarih",
            (oid,),
        ).fetchall()
    ozet = {
        "bekleyen": 0,
        "bugun": 0,
        "gecikmis": 0,
        "tamamlanan": 0,
        "iptal": 0,
    }
    for satir in satirlar:
        adet = int(satir["adet"] or 0)
        durum = satir["durum"]
        if durum == DURUM_TAMAMLANDI:
            ozet["tamamlanan"] += adet
        elif durum == DURUM_IPTAL:
            ozet["iptal"] += adet
        elif durum == DURUM_BEKLIYOR:
            ozet["bekleyen"] += adet
            if satir["planlanan_tarih"] == gun_str:
                ozet["bugun"] += adet
            elif satir["planlanan_tarih"] < gun_str:
                ozet["gecikmis"] += adet
    return ozet


# ==============================================================================
# ÖĞRENME OLAYI -> TEKRAR PLANI
# ==============================================================================
def _gorev_getir(gorev_id):
    if gorev_id in (None, "", 0):
        return None
    try:
        gid = int(gorev_id)
    except (TypeError, ValueError):
        return None
    with _baglanti() as conn:
        satir = conn.execute(
            "SELECT * FROM calisma_programi_gorevler WHERE id = ?", (gid,)
        ).fetchone()
    return dict(satir) if satir is not None else None


def _ogrenme_gorevi_mi(gorev):
    """Görev gerçek bir öğrenme olayı mı?

    Yalnızca mevcut işaretler kullanılır: kalıcı `pedagoji_turu`, mevcut
    "Deneme Tekrarı" makro konusu ve bilinen günlük alıştırma / yer tutucu
    konular. Yalnızca soru bloğu içeren görevler `tekrar_planla` içinde
    checklist üzerinden elenir (tamamlanmış öğrenme adımı yok).
    """
    pedagoji = _metin(gorev.get("pedagoji_turu")) or "Pekiştirme"
    if pedagoji == "Tekrar":
        return False  # aralıklı tekrar görevi kendi tekrarını üretmez
    if _metin(gorev.get("makro_konu")) == "Deneme Tekrarı":
        return False  # deneme hatası incelemesi öğrenme olayı değildir
    ders = _metin(gorev.get("ders"))
    mikro = _metin(gorev.get("mikro_konu"))
    if not ders or not mikro:
        return False
    if mikro in task_steps.BOLUNMEZ_MIKROLAR:
        return False  # günlük paragraf alıştırması tekrar üretmez
    if mikro in YER_TUTUCU_KONULAR:
        return False
    return True


def _ilk_adim(adimlar, tur):
    for adim in adimlar:
        if adim.get("adim_turu") == tur:
            return adim
    return None


def _tekrar_verisi(gorev, tur, adim_id, gun_sayisi, ogrenme, pedagoji, aciklama):
    return {
        "ogrenci_id": int(gorev["ogrenci_id"]),
        "ders": _metin(gorev.get("ders")),
        "makro_konu": _metin(gorev.get("makro_konu")),
        "mikro_konu": _metin(gorev.get("mikro_konu")),
        "tekrar_turu": tur,
        "kaynak_gorev_id": int(gorev["id"]),
        "kaynak_adim_id": int(adim_id) if adim_id not in (None, "", 0) else None,
        "planlanan_tarih": (ogrenme + timedelta(days=gun_sayisi)).isoformat(),
        "ogrenme_tarihi": ogrenme.isoformat(),
        "pedagoji_turu": pedagoji,
        "hedef_soru": 0,  # FAZ 6A: tekrar ek soru zorunluluğu üretmez
        "aciklama": aciklama,
    }


def _bekleyen_var_mi(conn, veri):
    """Aynı öğrenme olayı veya aynı konu + tür için bekleyen kayıt var mı?"""
    satir = conn.execute(
        "SELECT id FROM tekrar_kayitlari WHERE ogrenci_id = ? AND tekrar_turu = ?"
        " AND ((kaynak_gorev_id IS NOT NULL AND kaynak_gorev_id = ?)"
        "      OR (durum = ? AND ders = ? AND COALESCE(makro_konu, '') = ?"
        "          AND mikro_konu = ?))"
        " LIMIT 1",
        (
            veri["ogrenci_id"],
            veri["tekrar_turu"],
            veri["kaynak_gorev_id"],
            DURUM_BEKLIYOR,
            veri["ders"],
            veri["makro_konu"] or "",
            veri["mikro_konu"],
        ),
    ).fetchone()
    return satir is not None


def _tekrar_ekle(conn, veri, zaman):
    """Tekrar kaydını yazar; mükerrer kayıt oluşursa None döner."""
    if _bekleyen_var_mi(conn, veri):
        return None
    try:
        imlec = conn.execute(
            "INSERT INTO tekrar_kayitlari"
            " (ogrenci_id, ders, makro_konu, mikro_konu, tekrar_turu,"
            "  kaynak_gorev_id, kaynak_adim_id, planlanan_tarih, durum,"
            "  ogrenme_tarihi, pedagoji_turu, hedef_soru, aciklama,"
            "  olusturma_zamani)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                veri["ogrenci_id"],
                veri["ders"],
                veri["makro_konu"],
                veri["mikro_konu"],
                veri["tekrar_turu"],
                veri["kaynak_gorev_id"],
                veri["kaynak_adim_id"],
                veri["planlanan_tarih"],
                DURUM_BEKLIYOR,
                veri["ogrenme_tarihi"],
                veri["pedagoji_turu"],
                veri["hedef_soru"],
                veri["aciklama"],
                zaman,
            ),
        )
    except sqlite3.IntegrityError as hata:
        if "UNIQUE" in str(hata).upper():
            return None  # yarış koşulu: indeks ikinci kaydı engelledi
        raise
    return _tekrar_satiri(conn, imlec.lastrowid)


def tekrar_planla(gorev_id, an=None):
    """Tamamlanan öğrenme görevi için aralıklı tekrar kayıtları oluşturur.

    Koşullar (hepsi sağlanmalı):
      - Görev gerçek bir öğrenme görevi (tekrar / deneme tekrarı / yer tutucu
        konu değil),
      - Checklist'in TAMAMI tamamlanmış (soru blokları gerçek oturumlardan),
      - En az bir öğrenme adımı (`izle` veya `not`) var.

    Plan:
      - Her öğrenme olayı için öğrenme günü + 3 gün: 3 Günlük Tekrar.
      - `pedagoji_turu == 'Ezber'` ve kısa not adımı varsa öğrenme günü
        + 5 gün: 5 Günlük Özet Notu (ek soru zorunluluğu yok).

    Idempotenttir: aynı görev için ikinci kez yeni kayıt üretmez; yalnızca bu
    çağrıda oluşturulan kayıtları döndürür.
    """
    gorev = _gorev_getir(gorev_id)
    if not gorev:
        return []
    if not _ogrenme_gorevi_mi(gorev):
        return []
    adimlar = task_steps.gorev_adimlari(gorev["id"])
    if not adimlar:
        return []  # checklist'siz eski görev: öğrenilmişlik uydurulmaz
    if not all(adim.get("tamam") for adim in adimlar):
        return []
    izle_adimi = _ilk_adim(adimlar, task_steps.ADIM_IZLE)
    not_adimi = _ilk_adim(adimlar, task_steps.ADIM_NOT)
    ogrenme_adimi = izle_adimi or not_adimi
    if ogrenme_adimi is None:
        return []  # yalnızca soru bloğu: öğrenme olayı değil

    ogrenme = _an_tarihi(an)
    zaman = _zaman_yaz(_an_zamani(an))
    pedagoji = _metin(gorev.get("pedagoji_turu")) or "Pekiştirme"
    mikro = _metin(gorev.get("mikro_konu"))

    planlar = [
        _tekrar_verisi(
            gorev,
            TEKRAR_TURU_3_GUN,
            ogrenme_adimi.get("id"),
            TEKRAR_GUN_SAYISI,
            ogrenme,
            pedagoji,
            "3 günlük aralıklı tekrar: '%s' özet notlarını oku ve gözden"
            " geçir (ek soru zorunlu değil)." % mikro,
        )
    ]
    if pedagoji == EZBER_PEDAGOJISI and not_adimi is not None:
        # Ezber derslerinde kısa not şartı: not adımı tamamlanmadan 5 günlük
        # not okuma tekrarı planlanmaz. Pekiştirme derslerine uygulanmaz.
        planlar.append(
            _tekrar_verisi(
                gorev,
                TEKRAR_TURU_5_GUN_NOT,
                not_adimi.get("id"),
                NOT_TEKRARI_GUN_SAYISI,
                ogrenme,
                pedagoji,
                "5 günlük özet notu tekrarı: '%s' için çıkardığın kısa özet"
                " notunu oku (ek soru zorunlu değil)." % mikro,
            )
        )

    olusan = []
    with _baglanti() as conn:
        with _islem(conn):
            for veri in planlar:
                kayit = _tekrar_ekle(conn, veri, zaman)
                if kayit is not None:
                    olusan.append(kayit)
    return olusan


# ==============================================================================
# DURUM GEÇİŞLERİ
# ==============================================================================
def tekrar_tamamla(tekrar_id, an=None):
    """Tekrarı tamamlar; GERÇEK tamamlanma zamanını kaydeder.

    `planlanan_tarih` değişmez. Zaten tamamlanmışsa kayıt aynen döner
    (idempotent); iptal edilmiş tekrar tamamlanamaz.
    """
    an = an or simdi()
    zaman = _zaman_yaz(_an_zamani(an))
    with _baglanti() as conn:
        with _islem(conn):
            kayit = _tekrar_satiri(conn, tekrar_id)
            if kayit["durum"] == DURUM_TAMAMLANDI:
                return kayit
            if kayit["durum"] == DURUM_IPTAL:
                raise TekrarHatasi(
                    "İptal edilmiş tekrar (#%s) tamamlanamaz." % kayit["id"]
                )
            imlec = conn.execute(
                "UPDATE tekrar_kayitlari SET durum = ?, tamamlanma_zamani = ?,"
                " guncelleme_zamani = ? WHERE id = ? AND durum = ?",
                (DURUM_TAMAMLANDI, zaman, zaman, kayit["id"], DURUM_BEKLIYOR),
            )
            if imlec.rowcount != 1:
                raise TekrarHatasi(
                    "Tekrar bu sırada başka bir işlemle kapandı; tekrar deneyin."
                )
            return _tekrar_satiri(conn, kayit["id"])


def tekrar_iptal(tekrar_id, an=None):
    """Bekleyen tekrarı iptal eder (silmez; geçmiş korunur)."""
    an = an or simdi()
    zaman = _zaman_yaz(_an_zamani(an))
    with _baglanti() as conn:
        with _islem(conn):
            kayit = _tekrar_satiri(conn, tekrar_id)
            if kayit["durum"] == DURUM_IPTAL:
                return kayit
            if kayit["durum"] == DURUM_TAMAMLANDI:
                raise TekrarHatasi(
                    "Tamamlanmış tekrar (#%s) iptal edilemez." % kayit["id"]
                )
            imlec = conn.execute(
                "UPDATE tekrar_kayitlari SET durum = ?, guncelleme_zamani = ?,"
                " tamamlanma_zamani = NULL WHERE id = ? AND durum = ?",
                (DURUM_IPTAL, zaman, kayit["id"], DURUM_BEKLIYOR),
            )
            if imlec.rowcount != 1:
                raise TekrarHatasi(
                    "Tekrar bu sırada başka bir işlemle kapandı; tekrar deneyin."
                )
            return _tekrar_satiri(conn, kayit["id"])
