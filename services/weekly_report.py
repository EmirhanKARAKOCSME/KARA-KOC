"""FAZ 7 - Haftalık performans raporu, hedef takibi ve gelişim analizi.

Tasarım ilkesi: **rapor bir katmandır, veri kaynağı değildir.**

- Metrikler HER ZAMAN kaynak tablolardan okunur; haftalık metrik snapshot'ı
  tutulmaz. Böylece geçmiş bir çalışma oturumu düzeltildiğinde rapor ile
  ham veri arasında tutarsızlık oluşmaz.
- Kalıcı olarak saklanan tek şey öğrencinin KENDİ beyanlarıdır:
  haftalık hedefler (`haftalik_hedefler`) ve haftalık değerlendirmeler
  (`haftalik_degerlendirmeler`).
- Hafta: Pazartesi başlangıçlı, Pazar bitişli (TR saati, UTC+3).

Veri kaynakları (tek doğruluk kaynağı):
- `calisma_oturumlari`       -> gerçek süre, gerçek soru, ders/mikro kırılımı
- `calisma_programi_gorevler` -> planlanan görev, hedef, tahmini süre, durum
- `calisma_gorev_devirleri`  -> devreden / devralan görevler
- `tekrar_kayitlari`         -> aralıklı tekrar planı ve tamamlanması
- `yanlis_sorular`           -> bireysel yanlış soru defteri akışı
- `denemeler`, `deneme_ders_sonuclari` -> deneme sayısı, net, ders kırılımı
- `mikro_konu_ilerleme`      -> mikro konu öğrenme/soru hedefi durumu
- `konu_durumlari_detay`     -> öğrencinin "biliyorum" beyanı (haftalık değil)

Dürüstlük kuralları (bilinçli kısıtlar):
- Hedeflenen soru çözülmüş soru sayılmaz; yalnızca tamamlanmış oturumlar
  sayılır ve oturumun `cozulen_soru` alanı kullanılır.
- Görev hedef süresi gerçek çalışma süresi sayılmaz; ikisi ayrı raporlanır.
- Deneme soruları normal çalışma sorularına EKLENMEZ (mükerrer sayım yok).
- Yanlış soru defteri sayaçları oturum sayılarıyla toplanmaz; ayrı bölümdür.
- `konu_durumlari_detay` zaman damgası taşımadığı için haftalık "öğrenildi"
  sayısı ÜRETİLMEZ; yalnızca güncel durum ayrı etiketle gösterilir.
- Arşivleme zamanı tutulmadığı için geçmiş haftaların defter stokları
  "bugünkü duruma göre" hesaplanır ve raporda bu şekilde etiketlenir.

Bu modül Streamlit'e bağımlı değildir; testler doğrudan çağırabilir.
"""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

TR_TZ = timezone(timedelta(hours=3))

VARSAYILAN_DB_YOLU = "yks_veritabani.db"
_ZAMAN_KALIBI = "%Y-%m-%d %H:%M:%S"
_TARIH_KALIBI = "%Y-%m-%d"

GUN_ADLARI = (
    "Pazartesi",
    "Salı",
    "Çarşamba",
    "Perşembe",
    "Cuma",
    "Cumartesi",
    "Pazar",
)
AY_ADLARI = (
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
)

# Rapor dönemindeki hafta sayısı üst sınırı (performans koruması).
MAKS_SERI_HAFTA = 26
VARSAYILAN_SERI_HAFTA = 8

# Grafiklerde "yeterli veri" eşikleri.
GRAFIK_MIN_HAFTA = 2
GRAFIK_MIN_DENEME = 2

# Bir günün "aktif çalışma günü" sayılması için gereken en küçük gerçek süre.
# Çalışma serisi (study_sessions.GUNLUK_SERI_ESIK_DK) ile aynı eşik.
AKTIF_GUN_ESIK_DK = 15

MAKS_METIN = 600


# ------------------------------------------------------------------------------
# HEDEF TÜRLERİ
# ------------------------------------------------------------------------------
HEDEF_TURLERI = {
    "calisma_suresi": {
        "etiket": "Haftalık çalışma süresi",
        "birim": "dk",
        "maks": 10080,
        "ders_gerekli": False,
    },
    "soru": {
        "etiket": "Haftalık soru hedefi",
        "birim": "soru",
        "maks": 20000,
        "ders_gerekli": False,
    },
    "aktif_gun": {
        "etiket": "Aktif çalışma günü",
        "birim": "gün",
        "maks": 7,
        "ders_gerekli": False,
    },
    "gorev": {
        "etiket": "Tamamlanan görev",
        "birim": "görev",
        "maks": 500,
        "ders_gerekli": False,
    },
    "deneme": {
        "etiket": "Haftalık deneme",
        "birim": "deneme",
        "maks": 30,
        "ders_gerekli": False,
    },
    "program_uyumu": {
        "etiket": "Program uyumu",
        "birim": "%",
        "maks": 100,
        "ders_gerekli": False,
    },
    "ders_suresi": {
        "etiket": "Ders çalışma süresi",
        "birim": "dk",
        "maks": 10080,
        "ders_gerekli": True,
    },
    "ders_soru": {
        "etiket": "Ders soru hedefi",
        "birim": "soru",
        "maks": 20000,
        "ders_gerekli": True,
    },
}

HEDEF_DURUM_TAMAM = "Tamamlandı"
HEDEF_DURUM_YAKIN = "Yaklaşıyor"
HEDEF_DURUM_DEVAM = "Devam Ediyor"
HEDEF_DURUM_VERI = "Veri Bekliyor"
HEDEF_DURUM_BASLAMADI = "Henüz Kayıt Yok"

# Öğrenci değerlendirme alanları: (kolon, soru metni)
DEGERLENDIRME_ALANLARI = (
    ("en_iyi", "Bu hafta en iyi yaptığım şey neydi?"),
    ("zorlanilan", "En çok zorlandığım konu neydi?"),
    ("ise_yarayan", "Hangi çalışma alışkanlığım işe yaradı?"),
    ("degistirilecek", "Gelecek hafta neyi değiştirmek istiyorum?"),
)


class HaftalikRaporHatasi(ValueError):
    """Geçersiz hafta/hedef işlemi veya doğrulama hatası."""


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


def _tablo_var_mi(conn, tablo):
    """Rapor katmanı, uygulama tarafından kurulmamış tablolara tolere eder."""
    satir = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (tablo,),
    ).fetchone()
    return satir is not None


def _kolonlar(conn, tablo):
    return [satir[1] for satir in conn.execute("PRAGMA table_info(%s)" % tablo)]


def _ogrenci_dogrula(ogrenci_id):
    try:
        oid = int(ogrenci_id)
    except (TypeError, ValueError):
        raise HaftalikRaporHatasi("Geçersiz öğrenci numarası.") from None
    if oid <= 0:
        raise HaftalikRaporHatasi("Geçersiz öğrenci numarası.")
    with _baglanti() as conn:
        if not _tablo_var_mi(conn, "ogrenciler"):
            raise HaftalikRaporHatasi(
                "Öğrenci tablosu bulunamadı; veritabanı hazır değil."
            )
        satir = conn.execute(
            "SELECT id FROM ogrenciler WHERE id = ?", (oid,)
        ).fetchone()
    if satir is None:
        raise HaftalikRaporHatasi("Öğrenci bulunamadı (#%s)." % oid)
    return oid


# ==============================================================================
# HAFTA YARDIMCILARI (Pazartesi -> Pazar, TR takvimi)
# ==============================================================================
def _tarih_oku(deger, ad="Tarih"):
    """date / datetime / 'YYYY-AA-GG' (+ saat) değerini takvim gününe çevirir."""
    if isinstance(deger, datetime):
        if deger.tzinfo is not None:
            return deger.astimezone(TR_TZ).date()
        return deger.date()
    if isinstance(deger, date):
        return deger
    metin = "" if deger is None else str(deger).strip()
    if not metin:
        raise HaftalikRaporHatasi("%s boş olamaz." % ad)
    try:
        return datetime.strptime(metin[:10], _TARIH_KALIBI).date()
    except ValueError:
        raise HaftalikRaporHatasi(
            "%s geçersiz (YYYY-AA-GG beklenir): %s" % (ad, deger)
        ) from None


def hafta_basi(gun=None):
    """Verilen günün (veya bugünün) Pazartesi'si."""
    if gun is None:
        gun = bugun()
    else:
        gun = _tarih_oku(gun, "Hafta günü")
    return gun - timedelta(days=gun.weekday())


def hafta_araligi(gun=None):
    """(Pazartesi, Pazar) tarih çifti."""
    bas = hafta_basi(gun)
    return bas, bas + timedelta(days=6)


def hafta_iso(gun=None):
    """Hafta anahtarı: Pazartesi'nin ISO tarihi."""
    return hafta_basi(gun).isoformat()


def hafta_etiketi(gun=None):
    """'9 Kasım Pazartesi – 15 Kasım Pazar' biçiminde okunur etiket."""
    bas, bit = hafta_araligi(gun)
    return "%d %s %s – %d %s %s" % (
        bas.day,
        AY_ADLARI[bas.month - 1],
        GUN_ADLARI[bas.weekday()],
        bit.day,
        AY_ADLARI[bit.month - 1],
        GUN_ADLARI[bit.weekday()],
    )


def _kisa_tarih(gun):
    return "%d %s" % (gun.day, AY_ADLARI[gun.month - 1])


def hafta_secenekleri(adet=12, an=None):
    """Son `adet` hafta (en yeni önce) - arayüzdeki hafta seçimi için."""
    try:
        adet = max(1, min(MAKS_SERI_HAFTA, int(adet)))
    except (TypeError, ValueError):
        adet = 12
    referans = hafta_basi(an if an is not None else bugun())
    mevcut_bas = hafta_basi()
    secenekler = []
    for sira in range(adet):
        bas = referans - timedelta(days=7 * sira)
        bit = bas + timedelta(days=6)
        secenekler.append(
            {
                "baslangic": bas.isoformat(),
                "bitis": bit.isoformat(),
                "etiket": hafta_etiketi(bas),
                "kisa": "%s – %s" % (_kisa_tarih(bas), _kisa_tarih(bit)),
                "devam_ediyor": bas == mevcut_bas,
                "bu_hafta": bas == mevcut_bas,
                "gecen_hafta": bas == mevcut_bas - timedelta(days=7),
            }
        )
    return secenekler


def onceki_hafta(gun=None):
    return hafta_basi(gun) - timedelta(days=7)


def sonraki_hafta(gun=None):
    return hafta_basi(gun) + timedelta(days=7)


def _gun_metni(deger):
    """DB'den gelen tarih/zaman metninin ilk 10 karakteri (yoksa None)."""
    if deger is None:
        return None
    metin = str(deger).strip()
    if len(metin) < 10:
        return None
    return metin[:10]


def _metin_say(deger, ad=None):
    metin = None if deger is None else str(deger).strip()
    if metin and len(metin) > MAKS_METIN:
        raise HaftalikRaporHatasi(
            "%s çok uzun (en fazla %d karakter)." % (ad or "Metin", MAKS_METIN)
        )
    return metin or None


# ==============================================================================
# ŞEMA (idempotent; veri silmez, geçmiş kayıtlara dokunmaz)
# ==============================================================================
_SEMA_HEDEF = """
CREATE TABLE IF NOT EXISTS haftalik_hedefler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    hafta_baslangici TEXT NOT NULL,
    hedef_turu TEXT NOT NULL,
    ders TEXT NOT NULL DEFAULT '',
    hedef_deger REAL NOT NULL,
    onceki_deger REAL,
    guncelleme_sayisi INTEGER NOT NULL DEFAULT 0,
    olusturma_zamani TEXT NOT NULL,
    guncelleme_zamani TEXT,
    UNIQUE(ogrenci_id, hafta_baslangici, hedef_turu, ders),
    FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
)
"""

_SEMA_DEGERLENDIRME = """
CREATE TABLE IF NOT EXISTS haftalik_degerlendirmeler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    hafta_baslangici TEXT NOT NULL,
    en_iyi TEXT,
    zorlanilan TEXT,
    ise_yarayan TEXT,
    degistirilecek TEXT,
    olusturma_zamani TEXT NOT NULL,
    guncelleme_zamani TEXT,
    UNIQUE(ogrenci_id, hafta_baslangici),
    FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
)
"""

_EK_KOLONLAR_HEDEF = (
    ("onceki_deger", "REAL"),
    ("guncelleme_sayisi", "INTEGER NOT NULL DEFAULT 0"),
)

_INDEKSLER = (
    "CREATE INDEX IF NOT EXISTS idx_hedef_ogrenci_hafta"
    " ON haftalik_hedefler(ogrenci_id, hafta_baslangici)",
    "CREATE INDEX IF NOT EXISTS idx_degerlendirme_ogrenci"
    " ON haftalik_degerlendirmeler(ogrenci_id, hafta_baslangici)",
)


def init_db():
    """Tablo/indeksleri idempotent biçimde kurar (veri silmez).

    Birden fazla kez çağrılabilir; çalışma oturumları, görevler, denemeler,
    tekrar ve yanlış soru kayıtlarına dokunmaz.
    """
    with _baglanti() as conn:
        with _islem(conn):
            conn.execute(_SEMA_HEDEF)
            conn.execute(_SEMA_DEGERLENDIRME)
            mevcut = set(_kolonlar(conn, "haftalik_hedefler"))
            for kolon, tip in _EK_KOLONLAR_HEDEF:
                if mevcut and kolon not in mevcut:
                    conn.execute(
                        "ALTER TABLE haftalik_hedefler ADD COLUMN %s %s"
                        % (kolon, tip)
                    )
            for sorgu in _INDEKSLER:
                conn.execute(sorgu)
    return True



# ==============================================================================
# KAYNAK OKUMA (tek bağlantı, tarih aralığına göre filtreli sorgular)
# ==============================================================================
# Durum sabitleri, ilgili servislerle AYNI kaynaktan gelir (anlam kayması yok).
try:  # pragma: no cover - import yolu her zaman aynı
    from services.study_sessions import DURUM_TAMAMLANDI as OTURUM_TAMAM
    from services.spaced_repetition import (
        DURUM_BEKLIYOR as TEKRAR_BEKLIYOR,
        DURUM_TAMAMLANDI as TEKRAR_TAMAM,
        DURUM_IPTAL as TEKRAR_IPTAL,
    )
    from services.wrong_questions import (
        AKTIF_DURUMLAR as DEFTER_AKTIF,
        DURUM_ARSIV as DEFTER_ARSIV,
        DURUM_OGRENILDI as DEFTER_OGRENILDI,
    )
except Exception:  # pragma: no cover - servisler yoksa güvenli varsayılan
    OTURUM_TAMAM = "Tamamlandı"
    TEKRAR_BEKLIYOR, TEKRAR_TAMAM, TEKRAR_IPTAL = (
        "Bekliyor",
        "Tamamlandı",
        "İptal Edildi",
    )
    DEFTER_AKTIF = ("Yeni", "Tekrar Bekliyor")
    DEFTER_ARSIV = "Arşivlendi"
    DEFTER_OGRENILDI = "Öğrenildi"


def net_hesapla(dogru, yanlis):
    """Net = Doğru - (Yanlış / 4). main.py `ders_net_hesapla` ile aynı formül."""
    try:
        d = float(dogru or 0)
        y = float(yanlis or 0)
    except (TypeError, ValueError):
        return None
    if d < 0 or y < 0:
        return None
    return round(d - (y / 4.0), 2)


def _deneme_neti(satir):
    net = satir["net_bilgisi"]
    if net is not None:
        try:
            return round(float(net), 2)
        except (TypeError, ValueError):
            return None
    if satir["dogru_adedi"] is None and satir["yanlis_adedi"] is None:
        return None
    return net_hesapla(satir["dogru_adedi"], satir["yanlis_adedi"])


def _oturum_satirlari(conn, oid, bas, bit):
    if not _tablo_var_mi(conn, "calisma_oturumlari"):
        return []
    return conn.execute(
        "SELECT id, gorev_id, ders, makro_konu, mikro_konu, alt_konu,"
        " gercek_sure_dk, cozulen_soru, dogru, yanlis, bos,"
        " substr(baslangic_zamani, 1, 10) AS gun"
        " FROM calisma_oturumlari"
        " WHERE ogrenci_id = ? AND durum = ?"
        "   AND substr(baslangic_zamani, 1, 10) BETWEEN ? AND ?",
        (oid, OTURUM_TAMAM, bas.isoformat(), bit.isoformat()),
    ).fetchall()


def _gorev_satirlari(conn, oid, bas, bit):
    if not _tablo_var_mi(conn, "calisma_programi_gorevler"):
        return [], 0
    kolonlar = set(_kolonlar(conn, "calisma_programi_gorevler"))
    gecersiz = "IFNULL(gecersiz, 0)" if "gecersiz" in kolonlar else "0"
    tarih_var = "tarih" in kolonlar
    kosul = "tarih BETWEEN ? AND ?" if tarih_var else "1 = 1"
    parametreler = [oid]
    if tarih_var:
        parametreler.extend([bas.isoformat(), bit.isoformat()])
    satirlar = conn.execute(
        "SELECT id, tarih, ders, makro_konu, mikro_konu, alt_konu, hedef_soru,"
        " tahmini_sure_dk, durum, %s AS gecersiz,"
        " kaynak_gorev_id FROM calisma_programi_gorevler"
        " WHERE ogrenci_id = ? AND %s" % (gecersiz, kosul),
        tuple(parametreler),
    ).fetchall()
    tarihsiz = conn.execute(
        "SELECT COUNT(*) AS adet FROM calisma_programi_gorevler"
        " WHERE ogrenci_id = ? AND (tarih IS NULL OR TRIM(tarih) = '')",
        (oid,),
    ).fetchone()["adet"]
    return satirlar, int(tarihsiz or 0)


def _devir_satirlari(conn, oid):
    if not _tablo_var_mi(conn, "calisma_gorev_devirleri"):
        return []
    return conn.execute(
        "SELECT kaynak_gorev_id, hedef_gorev_id, devredilen_soru,"
        " devredilen_sure_dk FROM calisma_gorev_devirleri WHERE ogrenci_id = ?",
        (oid,),
    ).fetchall()



def _tekrar_satirlari(conn, oid, bas, bit):
    """Pencerede planlanan VEYA pencerede tamamlanan tekrar kayıtları."""
    if not _tablo_var_mi(conn, "tekrar_kayitlari"):
        return []
    return conn.execute(
        "SELECT id, ders, makro_konu, mikro_konu, alt_konu, planlanan_tarih,"
        " durum, substr(tamamlanma_zamani, 1, 10) AS tamam_gun,"
        " tamamlanma_zamani FROM tekrar_kayitlari"
        " WHERE ogrenci_id = ? AND ("
        "   planlanan_tarih BETWEEN ? AND ?"
        "   OR (tamamlanma_zamani IS NOT NULL"
        "       AND substr(tamamlanma_zamani, 1, 10) BETWEEN ? AND ?))",
        (
            oid,
            bas.isoformat(),
            bit.isoformat(),
            bas.isoformat(),
            bit.isoformat(),
        ),
    ).fetchall()


def _bekleyen_tekrar_stogu(conn, oid, bit):
    if not _tablo_var_mi(conn, "tekrar_kayitlari"):
        return 0, []
    satirlar = conn.execute(
        "SELECT ders, makro_konu, mikro_konu, alt_konu, planlanan_tarih"
        " FROM tekrar_kayitlari WHERE ogrenci_id = ? AND durum = ?"
        "   AND planlanan_tarih <= ?"
        " ORDER BY planlanan_tarih ASC, id ASC LIMIT 50",
        (oid, TEKRAR_BEKLIYOR, bit.isoformat()),
    ).fetchall()
    return len(satirlar), satirlar


def _yanlis_soru_satirlari(conn, oid):
    if not _tablo_var_mi(conn, "yanlis_sorular"):
        return []
    return conn.execute(
        "SELECT id, ders, makro_konu, mikro_konu, alt_konu, durum,"
        " substr(olusturma_zamani, 1, 10) AS eklenme_gun, ogrenme_tarihi,"
        " son_tekrar_tarihi, sonraki_tekrar_tarihi, tekrar_sayisi,"
        " substr(guncelleme_zamani, 1, 10) AS guncelleme_gun"
        " FROM yanlis_sorular WHERE ogrenci_id = ?",
        (oid,),
    ).fetchall()


def _deneme_satirlari(conn, oid, bas, bit):
    if not _tablo_var_mi(conn, "denemeler"):
        return []
    return conn.execute(
        "SELECT id, substr(tarih, 1, 10) AS gun, deneme_adi,"
        " deneme_kategorisi, deneme_turu, net_bilgisi, dogru_adedi,"
        " yanlis_adedi, bos_adedi FROM denemeler"
        " WHERE ogrenci_id = ? AND substr(tarih, 1, 10) BETWEEN ? AND ?"
        " ORDER BY tarih ASC, id ASC",
        (oid, bas.isoformat(), bit.isoformat()),
    ).fetchall()


def _deneme_ders_satirlari(conn, oid, bas, bit):
    if not _tablo_var_mi(conn, "deneme_ders_sonuclari"):
        return []
    return conn.execute(
        "SELECT s.deneme_id, s.ders, s.dogru, s.yanlis, s.bos, s.net"
        " FROM deneme_ders_sonuclari s JOIN denemeler d ON d.id = s.deneme_id"
        " WHERE d.ogrenci_id = ? AND substr(d.tarih, 1, 10) BETWEEN ? AND ?",
        (oid, bas.isoformat(), bit.isoformat()),
    ).fetchall()


def _mikro_ilerleme_satirlari(conn, oid):
    if not _tablo_var_mi(conn, "mikro_konu_ilerleme"):
        return []
    return conn.execute(
        "SELECT ders, makro_konu, mikro_konu, alt_konu, ogrenme_tamam,"
        " hedef_soru, cozulen_soru, tamamlandi, guncelleme_zamani"
        " FROM mikro_konu_ilerleme WHERE ogrenci_id = ?",
        (oid,),
    ).fetchall()


def _beyan_sayisi(conn, oid):
    """Öğrencinin 'Biliyorum' beyanı - GÜNCEL durum (zaman damgası yok)."""
    if not _tablo_var_mi(conn, "konu_durumlari_detay"):
        return 0
    satir = conn.execute(
        "SELECT COUNT(*) AS adet FROM konu_durumlari_detay"
        " WHERE ogrenci_id = ? AND durum = 'Biliyorum'",
        (oid,),
    ).fetchone()
    return int(satir["adet"] or 0)


def _yanlis_gorev_baglari(conn, oid):
    """Yanlış soru defterine bağlı görevler (süre kırılımı için)."""
    if not _tablo_var_mi(conn, "calisma_gorev_kaynaklari"):
        return {}
    satirlar = conn.execute(
        "SELECT gorev_id, kaynak_id, cozuldu FROM calisma_gorev_kaynaklari"
        " WHERE ogrenci_id = ? AND kaynak_turu = 'yanlis_soru'",
        (oid,),
    ).fetchall()
    sonuc = {}
    for satir in satirlar:
        sonuc.setdefault(int(satir["gorev_id"]), []).append(
            {
                "kaynak_id": int(satir["kaynak_id"]),
                "cozuldu": bool(int(satir["cozuldu"] or 0)),
            }
        )
    return sonuc



# ==============================================================================
# TOPLAMA (saf fonksiyonlar: aynı satırlar -> aynı metrik)
# ==============================================================================
def _gun_araligi(bas, bit):
    gunler = []
    gun = bas
    while gun <= bit:
        gunler.append(gun.isoformat())
        gun += timedelta(days=1)
    return gunler


def _calisma_ozeti(oturumlar, bas, bit):
    """Gerçek süre/soru; yalnızca tamamlanmış oturumlardan."""
    dk = 0
    soru = 0
    dogru = yanlis = bos = 0
    kirilim_oturum = 0
    gunler = {}
    for satir in oturumlar:
        sdk = int(satir["gercek_sure_dk"] or 0)
        ssoru = int(satir["cozulen_soru"] or 0)
        dk += sdk
        soru += ssoru
        gun = satir["gun"] or (bas.isoformat())
        kayit = gunler.setdefault(gun, {"dk": 0, "soru": 0, "oturum": 0})
        kayit["dk"] += sdk
        kayit["soru"] += ssoru
        kayit["oturum"] += 1
        if (
            satir["dogru"] is not None
            and satir["yanlis"] is not None
            and satir["bos"] is not None
        ):
            dogru += int(satir["dogru"] or 0)
            yanlis += int(satir["yanlis"] or 0)
            bos += int(satir["bos"] or 0)
            kirilim_oturum += 1
    # Aktif gün: en az bir geçerli (süre > 0 veya soru > 0) oturum bulunan gün.
    aktif_gun = sum(
        1
        for kayit in gunler.values()
        if kayit["dk"] > 0 or kayit["soru"] > 0
    )
    seri_gun = sum(
        1 for kayit in gunler.values() if kayit["dk"] >= AKTIF_GUN_ESIK_DK
    )
    toplam_isaretli = dogru + yanlis + bos
    return {
        "dk": dk,
        "soru": soru,
        "oturum": len(oturumlar),
        "aktif_gun": aktif_gun,
        "seri_gun": seri_gun,
        "aktif_gun_esik_dk": AKTIF_GUN_ESIK_DK,
        "gunler": gunler,
        "gun_listesi": [
            gun for gun in _gun_araligi(bas, bit) if gun in gunler
        ],
        "dogru": dogru if kirilim_oturum else None,
        "yanlis": yanlis if kirilim_oturum else None,
        "bos": bos if kirilim_oturum else None,
        "kirilim_oturum": kirilim_oturum,
        "basari_orani": (
            round(dogru / toplam_isaretli * 100, 1)
            if kirilim_oturum and toplam_isaretli
            else None
        ),
        "veri_var": bool(oturumlar),
    }


def _saat_metni(dk):
    """255 -> '4 sa 15 dk' (arayüz ve yorumlar aynı biçimi kullanır)."""
    try:
        dk = int(dk or 0)
    except (TypeError, ValueError):
        return "0 dk"
    isaret = "-" if dk < 0 else ""
    dk = abs(dk)
    saat, kalan = divmod(dk, 60)
    if saat and kalan:
        return "%s%d sa %d dk" % (isaret, saat, kalan)
    if saat:
        return "%s%d sa" % (isaret, saat)
    return "%s%d dk" % (isaret, kalan)


def sure_metni(dk):
    """Arayüz için süre metni (yorumlarla aynı biçim: '4 sa 15 dk')."""
    return _saat_metni(dk)


def _ders_dagilimi(oturumlar, gorevler, deneme_dersleri):
    """Ders bazlı süre, soru, doğru/yanlış ve deneme netleri."""
    dersler = {}

    def _kayit(ders):
        return dersler.setdefault(
            ders,
            {
                "ders": ders,
                "dk": 0,
                "soru": 0,
                "oturum": 0,
                "dogru": 0,
                "yanlis": 0,
                "bos": 0,
                "kirilim_oturum": 0,
                "gorev_tamam": 0,
                "mikro": set(),
                "deneme_adet": 0,
                "deneme_net_toplam": 0.0,
                "deneme_net_adet": 0,
            },
        )

    for satir in oturumlar:
        kayit = _kayit(_metin_say(satir["ders"]) or "Diğer")
        kayit["dk"] += int(satir["gercek_sure_dk"] or 0)
        kayit["soru"] += int(satir["cozulen_soru"] or 0)
        kayit["oturum"] += 1
        if satir["mikro_konu"]:
            kayit["mikro"].add(
                (
                    _metin_say(satir["makro_konu"]) or "",
                    _metin_say(satir["mikro_konu"]),
                    _metin_say(satir["alt_konu"]) or "",
                )
            )
        if (
            satir["dogru"] is not None
            and satir["yanlis"] is not None
            and satir["bos"] is not None
        ):
            kayit["dogru"] += int(satir["dogru"] or 0)
            kayit["yanlis"] += int(satir["yanlis"] or 0)
            kayit["bos"] += int(satir["bos"] or 0)
            kayit["kirilim_oturum"] += 1

    for satir in gorevler:
        if int(satir["gecersiz"] or 0):
            continue
        if int(satir["durum"] or 0) != 1:
            continue
        kayit = _kayit(_metin_say(satir["ders"]) or "Diğer")
        kayit["gorev_tamam"] += 1

    for satir in deneme_dersleri:
        kayit = _kayit(_metin_say(satir["ders"]) or "Diğer")
        kayit["deneme_adet"] += 1
        net = satir["net"]
        if net is None:
            net = net_hesapla(satir["dogru"], satir["yanlis"])
        if net is not None:
            kayit["deneme_net_toplam"] += float(net)
            kayit["deneme_net_adet"] += 1

    sonuc = []
    for kayit in dersler.values():
        isaretli = kayit["dogru"] + kayit["yanlis"] + kayit["bos"]
        kayit["mikro_sayisi"] = len(kayit.pop("mikro"))
        kayit["soru_saat"] = (
            round(kayit["soru"] / (kayit["dk"] / 60.0), 1)
            if kayit["dk"] >= 15
            else None
        )
        kayit["basari_orani"] = (
            round(kayit["dogru"] / isaretli * 100, 1)
            if kayit["kirilim_oturum"] and isaretli
            else None
        )
        kayit["deneme_net_ort"] = (
            round(kayit["deneme_net_toplam"] / kayit["deneme_net_adet"], 2)
            if kayit["deneme_net_adet"]
            else None
        )
        if kayit["kirilim_oturum"] == 0:
            kayit["dogru"] = None
            kayit["yanlis"] = None
            kayit["bos"] = None
        sonuc.append(kayit)
    sonuc.sort(key=lambda k: (-k["dk"], -k["soru"], k["ders"]))
    return sonuc



def _gorev_ozeti(
    gorevler, tarihsiz, devirler, oturumlar, yanlis_baglari, bugun_iso
):
    """Program uyumu, devir ve planlanan/gerçekleşen süre.

    Program uyumu = tamamlanan uygun görev / o dönemde tamamlanması beklenen
    uygun görev. Geçersiz (iptal/bağsız kalmış) görevler paydaya girmez;
    gelecek tarihli görevler rapor dönemine girmediği için paydada yoktur.
    """
    uygun = [s for s in gorevler if not int(s["gecersiz"] or 0)]
    gecersiz = [s for s in gorevler if int(s["gecersiz"] or 0)]
    tamamlanan = [s for s in uygun if int(s["durum"] or 0) == 1]
    bekleyen = [s for s in uygun if int(s["durum"] or 0) == 0]
    pencere_idler = {int(s["id"]) for s in gorevler}
    devir_gelen = [s for s in uygun if s["kaynak_gorev_id"]]
    devir_giden = [d for d in devirler if int(d["kaynak_gorev_id"]) in pencere_idler]

    planlanan_dk = 0
    sure_bilinen = 0
    for satir in uygun:
        if satir["tahmini_sure_dk"] is not None:
            planlanan_dk += int(satir["tahmini_sure_dk"])
            sure_bilinen += 1

    gercek_dk = sum(int(s["gercek_sure_dk"] or 0) for s in oturumlar)
    program_disi_dk = 0
    yanlis_gorev_dk = 0
    for satir in oturumlar:
        sdk = int(satir["gercek_sure_dk"] or 0)
        gorev_id = satir["gorev_id"]
        if gorev_id is None or int(gorev_id) not in pencere_idler:
            program_disi_dk += sdk
        elif int(gorev_id) in yanlis_baglari:
            yanlis_gorev_dk += sdk

    def _gorev_karti(satir, gecikti):
        return {
            "id": int(satir["id"]),
            "tarih": satir["tarih"],
            "ders": satir["ders"],
            "makro_konu": satir["makro_konu"],
            "mikro_konu": satir["mikro_konu"],
            "alt_konu": satir["alt_konu"],
            "hedef_soru": int(satir["hedef_soru"] or 0),
            "tahmini_sure_dk": satir["tahmini_sure_dk"],
            "gecikmis": gecikti,
        }

    bekleyen_kartlar = [
        _gorev_karti(s, bool(s["tarih"] and str(s["tarih"])[:10] < bugun_iso))
        for s in sorted(bekleyen, key=lambda x: (str(x["tarih"] or ""), x["id"]))
    ]
    return {
        "planlanan": len(uygun),
        "tamamlanan": len(tamamlanan),
        "bekleyen": len(bekleyen),
        "gecersiz": len(gecersiz),
        "tarihsiz": tarihsiz,
        "devir_gelen": len(devir_gelen),
        "devir_giden": len(devir_giden),
        "devredilen_soru": sum(
            int(d["devredilen_soru"] or 0) for d in devir_giden
        ),
        "uyum": (
            round(len(tamamlanan) / len(uygun) * 100, 1) if uygun else None
        ),
        "uyum_hesaplanabilir": bool(uygun),
        "planlanan_dk": planlanan_dk if sure_bilinen else None,
        "sure_bilinen": sure_bilinen,
        "gercek_dk": gercek_dk,
        "program_disi_dk": program_disi_dk,
        "yanlis_gorev_dk": yanlis_gorev_dk,
        "ders_tamam": _ders_tamam(gorevler),
        "bekleyen_kartlar": bekleyen_kartlar[:40],
        "tamamlanmayan_sayisi": len(bekleyen),
        "veri_var": bool(gorevler),
    }


def _ders_tamam(gorevler):
    sonuc = {}
    for satir in gorevler:
        if int(satir["gecersiz"] or 0) or int(satir["durum"] or 0) != 1:
            continue
        ders = _metin_say(satir["ders"]) or "Diğer"
        sonuc[ders] = sonuc.get(ders, 0) + 1
    return sonuc


def _deneme_ozeti(denemeler, ders_sonuclari):
    netler = []
    turler = {}
    for satir in denemeler:
        net = _deneme_neti(satir)
        tur = (_metin_say(satir["deneme_turu"]) or "Diğer").upper()
        kayit = turler.setdefault(tur, {"adet": 0, "net_toplam": 0.0, "net_adet": 0})
        kayit["adet"] += 1
        if net is not None:
            kayit["net_toplam"] += float(net)
            kayit["net_adet"] += 1
        netler.append(
            {
                "id": int(satir["id"]),
                "gun": satir["gun"],
                "ad": _metin_say(satir["deneme_adi"]) or "Deneme",
                "tur": tur,
                "kategori": _metin_say(satir["deneme_kategorisi"]) or "",
                "net": net,
                "dogru": satir["dogru_adedi"],
                "yanlis": satir["yanlis_adedi"],
                "bos": satir["bos_adedi"],
            }
        )
    for kayit in turler.values():
        kayit["net_ort"] = (
            round(kayit["net_toplam"] / kayit["net_adet"], 2)
            if kayit["net_adet"]
            else None
        )

    dersler = {}
    for satir in ders_sonuclari:
        ders = _metin_say(satir["ders"]) or "Diğer"
        kayit = dersler.setdefault(
            ders,
            {
                "ders": ders,
                "adet": 0,
                "dogru": 0,
                "yanlis": 0,
                "bos": 0,
                "net_toplam": 0.0,
                "net_adet": 0,
            },
        )
        kayit["adet"] += 1
        kayit["dogru"] += int(satir["dogru"] or 0)
        kayit["yanlis"] += int(satir["yanlis"] or 0)
        kayit["bos"] += int(satir["bos"] or 0)
        net = satir["net"]
        if net is None:
            net = net_hesapla(satir["dogru"], satir["yanlis"])
        if net is not None:
            kayit["net_toplam"] += float(net)
            kayit["net_adet"] += 1
    ders_listesi = []
    for kayit in dersler.values():
        kayit["net_ort"] = (
            round(kayit["net_toplam"] / kayit["net_adet"], 2)
            if kayit["net_adet"]
            else None
        )
        ders_listesi.append(kayit)
    ders_listesi.sort(key=lambda k: (-k["adet"], k["ders"]))

    gecerli_netler = [n["net"] for n in netler if n["net"] is not None]
    return {
        "adet": len(denemeler),
        "netler": netler,
        "turler": turler,
        "dersler": ders_listesi,
        "net_ort": (
            round(sum(gecerli_netler) / len(gecerli_netler), 2)
            if gecerli_netler
            else None
        ),
        "net_sayisi": len(gecerli_netler),
        "veri_var": bool(denemeler),
    }



def _konu_anahtari(ders, makro, mikro, alt):
    return (
        _metin_say(ders) or "Diğer",
        _metin_say(makro) or "",
        _metin_say(mikro) or "Belirtilmemiş",
        _metin_say(alt) or "",
    )


def _mikro_ozeti(
    oturumlar, mikro_satirlari, bekleyen_tekrarlar, yanlis_satirlar, beyan
):
    """Mikro konu bazlı haftalık çalışma + öğrenme durumu (ayrı kavramlar).

    "Çalışıldı", "soru çözüldü", "hedef soruya ulaşıldı", "öğrenme adımları
    tamamlandı" ve "öğrenci öğrenildi olarak işaretledi" AYRI alanlardır;
    tek bir yüzdeye indirgenmez.
    """
    durum_map = {}
    for satir in mikro_satirlari:
        anahtar = _konu_anahtari(
            satir["ders"],
            satir["makro_konu"],
            satir["mikro_konu"],
            satir["alt_konu"],
        )
        durum_map[anahtar] = {
            "ogrenme_tamam": bool(int(satir["ogrenme_tamam"] or 0)),
            "hedef_soru": int(satir["hedef_soru"] or 0),
            "cozulen_soru": int(satir["cozulen_soru"] or 0),
            "tamamlandi": bool(int(satir["tamamlandi"] or 0)),
        }

    toplam = {}
    for satir in oturumlar:
        anahtar = _konu_anahtari(
            satir["ders"],
            satir["makro_konu"],
            satir["mikro_konu"],
            satir["alt_konu"],
        )
        kayit = toplam.setdefault(
            anahtar,
            {
                "ders": anahtar[0],
                "makro_konu": anahtar[1],
                "mikro_konu": anahtar[2],
                "alt_konu": anahtar[3] or None,
                "dk": 0,
                "soru": 0,
                "oturum": 0,
                "gunler": set(),
            },
        )
        kayit["dk"] += int(satir["gercek_sure_dk"] or 0)
        kayit["soru"] += int(satir["cozulen_soru"] or 0)
        kayit["oturum"] += 1
        if satir["gun"]:
            kayit["gunler"].add(satir["gun"])

    calisilan = []
    for anahtar, kayit in toplam.items():
        durum = durum_map.get(anahtar, {})
        hedef_soru = int(durum.get("hedef_soru") or 0)
        cozulen = int(durum.get("cozulen_soru") or 0)
        kayit["gun_sayisi"] = len(kayit["gunler"])
        kayit["gunler"] = sorted(kayit["gunler"])
        kayit["ogrenme_tamam"] = bool(durum.get("ogrenme_tamam"))
        kayit["ogrenme_adimi_bilgisi"] = bool(durum)
        kayit["tamamlandi"] = bool(durum.get("tamamlandi"))
        kayit["hedef_soru"] = hedef_soru
        kayit["cozulen_soru"] = cozulen
        # Konunun TOPLAM çözülen sorusu ile haftalık soru ayrı alanlardır.
        kayit["hedefe_ulasti"] = bool(hedef_soru and cozulen >= hedef_soru)
        calisilan.append(kayit)
    calisilan.sort(key=lambda k: (-k["dk"], -k["soru"], k["ders"], k["mikro_konu"]))

    bekleyen_konular = []
    for satir in mikro_satirlari:
        if int(satir["tamamlandi"] or 0):
            continue
        cozulen = int(satir["cozulen_soru"] or 0)
        hedef = int(satir["hedef_soru"] or 0)
        if cozulen <= 0 and not int(satir["ogrenme_tamam"] or 0):
            continue
        bekleyen_konular.append(
            {
                "ders": _metin_say(satir["ders"]) or "Diğer",
                "makro_konu": _metin_say(satir["makro_konu"]) or "",
                "mikro_konu": _metin_say(satir["mikro_konu"]) or "Belirtilmemiş",
                "alt_konu": _metin_say(satir["alt_konu"]),
                "hedef_soru": hedef,
                "cozulen_soru": cozulen,
                "kalan": max(0, hedef - cozulen),
                "ogrenme_tamam": bool(int(satir["ogrenme_tamam"] or 0)),
            }
        )
    bekleyen_konular.sort(key=lambda k: (-k["kalan"], -k["hedef_soru"]))
    bekleyen_konular = bekleyen_konular[:20]

    tekrar_listesi = [
        {
            "ders": satir["ders"],
            "makro_konu": satir["makro_konu"],
            "mikro_konu": satir["mikro_konu"],
            "alt_konu": satir["alt_konu"],
            "planlanan_tarih": satir["planlanan_tarih"],
        }
        for satir in bekleyen_tekrarlar
    ]

    biriken = {}
    for satir in yanlis_satirlar:
        if satir["durum"] not in tuple(DEFTER_AKTIF):
            continue
        anahtar = (
            _metin_say(satir["ders"]) or "Diğer",
            _metin_say(satir["mikro_konu"]) or "Belirtilmemiş",
        )
        biriken[anahtar] = biriken.get(anahtar, 0) + 1
    yanlis_biriken = [
        {"ders": anahtar[0], "mikro_konu": anahtar[1], "adet": adet}
        for anahtar, adet in sorted(
            biriken.items(), key=lambda x: (-x[1], x[0][0], x[0][1])
        )
    ][:20]

    return {
        "calisilan": calisilan,
        "calisilan_mikro_sayisi": len(
            {(k["ders"], k["mikro_konu"]) for k in calisilan}
        ),
        "tamamlanan": [k for k in calisilan if k["tamamlandi"]],
        "hedefe_ulasan": [k for k in calisilan if k["hedefe_ulasti"]],
        "ogrenildi_beyan_edilen_hafta": [
            k for k in calisilan if k["ogrenme_tamam"]
        ],
        "bekleyen_konular": bekleyen_konular,
        "tekrar_bekleyen": tekrar_listesi,
        "yanlis_biriken": yanlis_biriken,
        "beyan_ogrenildi": beyan,
        "beyan_notu": (
            "Bu sayı uygulamadaki güncel 'Biliyorum' beyanıdır; haftalık "
            "değişim hesaplanmaz."
        ),
        "veri_var": bool(
            calisilan or bekleyen_konular or tekrar_listesi or yanlis_biriken
        ),
    }



def _tekrar_ozeti(tekrar_satirlari, stok_adet, bas_iso, bit_iso, bugun_iso):
    planlanan = [
        s
        for s in tekrar_satirlari
        if s["planlanan_tarih"]
        and bas_iso <= str(s["planlanan_tarih"])[:10] <= bit_iso
    ]
    tamamlanan = [s for s in planlanan if s["durum"] == TEKRAR_TAMAM]
    bekleyen = [s for s in planlanan if s["durum"] == TEKRAR_BEKLIYOR]
    iptal = [s for s in planlanan if s["durum"] == TEKRAR_IPTAL]
    gecikmis_tamamlanan = [
        s
        for s in tekrar_satirlari
        if s["planlanan_tarih"]
        and str(s["planlanan_tarih"])[:10] < bas_iso
        and s["tamam_gun"]
        and bas_iso <= s["tamam_gun"] <= bit_iso
        and s["durum"] == TEKRAR_TAMAM
    ]
    gecikmis_bekleyen = [
        s
        for s in planlanan
        if s["durum"] == TEKRAR_BEKLIYOR
        and str(s["planlanan_tarih"])[:10] < bugun_iso
    ]
    return {
        "planlanan": len(planlanan),
        "tamamlanan": len(tamamlanan),
        "bekleyen": len(bekleyen),
        "iptal": len(iptal),
        "gecikmis_tamamlanan": len(gecikmis_tamamlanan),
        "gecikmis_bekleyen": len(gecikmis_bekleyen),
        "tamamlama_orani": (
            round(len(tamamlanan) / len(planlanan) * 100, 1)
            if planlanan
            else None
        ),
        "stok_bekleyen": int(stok_adet or 0),
        "kartlar": [
            {
                "ders": s["ders"],
                "makro_konu": s["makro_konu"],
                "mikro_konu": s["mikro_konu"],
                "alt_konu": s["alt_konu"],
                "planlanan_tarih": s["planlanan_tarih"],
                "durum": s["durum"],
                "tamam_gun": s["tamam_gun"],
            }
            for s in planlanan
        ][:40],
        "veri_var": bool(planlanan or gecikmis_tamamlanan or stok_adet),
    }


def _defter_ozeti(yanlis_satirlar, bas_iso, bit_iso):
    """Yanlış soru defteri akışı (soru kimliği ≠ tekrar geçmişi).

    - `eklenen` / `ogrenilen`: ilgili tarih alanı pencereye düşen kayıtlar.
    - `yeniden_cozulen`: SON tekrar tarihi pencereye düşen kayıtlar; aynı soru
      hafta içinde iki kez çözülse bile BİR soru sayılır (alt sınır).
    - `baslangic_bekleyen` / `bitis_bekleyen`: bugünkü duruma göre yeniden
      kurulur (arşivleme tarihi tutulmadığı için arşivlenenler hariçtir).
    """
    eklenen = []
    yeniden = []
    ogrenilen = []
    arsivlenen = []
    baslangic_bekleyen = 0
    bitis_bekleyen = 0
    aktif_toplam = 0
    for satir in yanlis_satirlar:
        eklenme = satir["eklenme_gun"]
        ogrenme = satir["ogrenme_tarihi"]
        son_tekrar = satir["son_tekrar_tarihi"]
        durum = satir["durum"]
        if durum in tuple(DEFTER_AKTIF):
            aktif_toplam += 1
        if eklenme and bas_iso <= eklenme <= bit_iso:
            eklenen.append(satir)
        if son_tekrar and bas_iso <= str(son_tekrar)[:10] <= bit_iso:
            yeniden.append(satir)
        if ogrenme and bas_iso <= str(ogrenme)[:10] <= bit_iso:
            ogrenilen.append(satir)
        if durum == DEFTER_ARSIV and satir["guncelleme_gun"]:
            if bas_iso <= satir["guncelleme_gun"] <= bit_iso:
                arsivlenen.append(satir)
        if durum == DEFTER_ARSIV:
            continue
        # Hafta BAŞINDA bekleyen: hafta içinde eklenen kayıtlar hafta başında
        # henüz yoktu; bu yüzden başlangıç sınırı DIŞLAYICI karşılaştırılır.
        if eklenme and eklenme < bas_iso and (
            not ogrenme or str(ogrenme)[:10] >= bas_iso
        ):
            baslangic_bekleyen += 1
        if eklenme and eklenme <= bit_iso and (
            not ogrenme or str(ogrenme)[:10] > bit_iso
        ):
            bitis_bekleyen += 1
    return {
        "baslangic_bekleyen": baslangic_bekleyen,
        "bitis_bekleyen": bitis_bekleyen,
        "eklenen": len(eklenen),
        "yeniden_cozulen": len(yeniden),
        "ogrenilen": len(ogrenilen),
        "arsivlenen": len(arsivlenen),
        "aktif_toplam": aktif_toplam,
        "degisim": bitis_bekleyen - baslangic_bekleyen,
        "toplam_kayit": len(yanlis_satirlar),
        "veri_var": bool(yanlis_satirlar),
        "not": (
            "Hafta başı/sonu bekleyen sayıları bugünkü kayıtlardan yeniden "
            "kurulur; arşivleme tarihi tutulmadığı için arşivlenen kayıtlar "
            "stokta sayılmaz."
        ),
    }



def _metrikler(conn, oid, bas, bit, hafif=False, bugun_tarih=None):
    """Bir tarih aralığının tüm rapor metriklerini TEK geçişte üretir."""
    bugun_t = bugun_tarih or bugun()
    bas_iso, bit_iso = bas.isoformat(), bit.isoformat()

    oturumlar = _oturum_satirlari(conn, oid, bas, bit)
    gorev_satirlar, tarihsiz = _gorev_satirlari(conn, oid, bas, bit)
    tekrar_satirlar = _tekrar_satirlari(conn, oid, bas, bit)
    yanlis_satirlar = _yanlis_soru_satirlari(conn, oid)
    deneme_satirlar = _deneme_satirlari(conn, oid, bas, bit)
    stok_adet, stok_satirlar = _bekleyen_tekrar_stogu(conn, oid, bit)

    if hafif:
        devirler = []
        deneme_dersleri = []
        mikro_satirlari = []
        beyan = 0
        yanlis_baglari = {}
    else:
        devirler = _devir_satirlari(conn, oid)
        deneme_dersleri = _deneme_ders_satirlari(conn, oid, bas, bit)
        mikro_satirlari = _mikro_ilerleme_satirlari(conn, oid)
        beyan = _beyan_sayisi(conn, oid)
        yanlis_baglari = _yanlis_gorev_baglari(conn, oid)

    calisma = _calisma_ozeti(oturumlar, bas, bit)
    gorevler = _gorev_ozeti(
        gorev_satirlar,
        tarihsiz,
        devirler,
        oturumlar,
        yanlis_baglari,
        bugun_t.isoformat(),
    )
    denemeler = _deneme_ozeti(deneme_satirlar, deneme_dersleri)
    tekrar = _tekrar_ozeti(
        tekrar_satirlar, stok_adet, bas_iso, bit_iso, bugun_t.isoformat()
    )
    defter = _defter_ozeti(yanlis_satirlar, bas_iso, bit_iso)
    dersler = (
        _ders_dagilimi(oturumlar, gorev_satirlar, deneme_dersleri)
        if not hafif
        else []
    )
    mikro = (
        _mikro_ozeti(
            oturumlar, mikro_satirlari, stok_satirlar, yanlis_satirlar, beyan
        )
        if not hafif
        else None
    )

    degerler = {
        "dk": calisma["dk"],
        "soru": calisma["soru"],
        "aktif_gun": calisma["aktif_gun"],
        "uyum": gorevler["uyum"],
        "tamamlanan_gorev": gorevler["tamamlanan"],
        "planlanan_gorev": gorevler["planlanan"],
        "deneme_net": denemeler["net_ort"],
        "deneme_adet": denemeler["adet"],
        "tamamlanan_tekrar": tekrar["tamamlanan"],
        "tekrar_planlanan": tekrar["planlanan"],
        "bekleyen_yanlis": defter["bitis_bekleyen"],
        "yanlis_eklenen": defter["eklenen"],
    }
    return {
        "calisma": calisma,
        "dersler": dersler,
        "gorevler": gorevler,
        "denemeler": denemeler,
        "mikro": mikro,
        "tekrar": tekrar,
        "defter": defter,
        "degerler": degerler,
        "ders_dk": _ders_sureleri(oturumlar),
    }


def _ders_sureleri(oturumlar):
    """Ders bazlı GERÇEK süre (hafif modda da hesaplanır; grafikler için)."""
    sonuc = {}
    for satir in oturumlar:
        ders = _metin_say(satir["ders"]) or "Diğer"
        sonuc[ders] = sonuc.get(ders, 0) + int(satir["gercek_sure_dk"] or 0)
    return sonuc


def _karsilastirma(metrik, onceki, donem_esit):
    """Önceki haftayla sayısal değişim (veri yoksa karşılaştırma üretilmez)."""
    alanlar = (
        ("dk", "Çalışma süresi", "dk"),
        ("soru", "Çözülen soru", "soru"),
        ("aktif_gun", "Aktif gün", "gün"),
        ("uyum", "Program uyumu", "puan"),
        ("deneme_net", "Deneme neti", "net"),
        ("tamamlanan_tekrar", "Tamamlanan tekrar", "tekrar"),
        ("bekleyen_yanlis", "Bekleyen yanlış soru", "soru"),
    )
    # Haftada hiç kayıt yoksa "0 = 0" gibi anlamsız satırlar üretilmez.
    simdiki_veri = bool(
        metrik["calisma"]["veri_var"]
        or metrik["gorevler"]["planlanan"]
        or metrik["denemeler"]["adet"]
        or metrik["tekrar"]["planlanan"]
        or metrik["defter"]["eklenen"]
    )
    onceki_veri = bool(
        onceki
        and (
            onceki["calisma"]["veri_var"]
            or onceki["gorevler"]["planlanan"]
            or onceki["denemeler"]["adet"]
            or onceki["tekrar"]["planlanan"]
        )
    )
    gecerli = []
    # Önceki dönemde hiç kayıt yoksa "90 dk → 0 dk" gibi yanıltıcı değişim
    # üretilmez: 0, "kayıt yok" ile "kayıtlı sıfır" arasında ayrım yapılamaz.
    if simdiki_veri and onceki_veri:
        for anahtar, etiket, birim in alanlar:
            simdiki = metrik["degerler"].get(anahtar)
            eski = onceki["degerler"].get(anahtar) if onceki else None
            if simdiki is None or eski is None:
                continue
            fark = round(float(simdiki) - float(eski), 2)
            if abs(fark) < 0.005:
                fark = 0.0
            gecerli.append(
                {
                    "alan": anahtar,
                    "etiket": etiket,
                    "birim": birim,
                    "gercek": simdiki,
                    "onceki": eski,
                    "fark": fark,
                    "yuzde": (
                        round(fark / float(eski) * 100, 1) if eski else None
                    ),
                }
            )
    return {
        "kullanilabilir": bool(gecerli),
        "donem": "esit_uzunluk" if donem_esit else "tam_hafta",
        "alanlar": gecerli,
        "onceki_veri_var": onceki_veri,
    }



# ==============================================================================
# YORUM MOTORU (deterministik, kural tabanlı; harici AI yok)
# ==============================================================================
YORUM_MAKS = 6
_TUR_SIRASI = {"dikkat": 0, "olumlu": 1, "bilgi": 2}


def _yorum_ekle(liste, kod, tur, baslik, gozlem, oneri=None, oncelik=50):
    liste.append(
        {
            "kod": kod,
            "tur": tur,
            "baslik": baslik,
            "gozlem": gozlem,
            "oneri": oneri,
            "oncelik": int(oncelik),
        }
    )


def _haftalik_verim(metrik):
    dk = metrik["degerler"]["dk"]
    soru = metrik["degerler"]["soru"]
    if not dk or dk < 60:
        return None
    return soru / (dk / 60.0)


def _yorumlar(metrik, onceki, seri, hedefler, donem_etiketi="geçen hafta"):
    """Metriklerden açıklanabilir gözlem + öneri üretir.

    Her kural tek bir veriye dayanır ve ürettiği sayıları cümlede gösterir.
    Veri yetersizse o kural hiç çalışmaz (uydurma yorum yok).
    """
    yorumlar = []
    calisma = metrik["calisma"]
    gorevler = metrik["gorevler"]
    denemeler = metrik["denemeler"]
    tekrar = metrik["tekrar"]
    defter = metrik["defter"]
    dk = metrik["degerler"]["dk"]
    soru = metrik["degerler"]["soru"]
    aktif_gun = metrik["degerler"]["aktif_gun"]
    tam_hafta = bool(metrik.get("tam_hafta", True))

    veri_var = bool(
        calisma["veri_var"]
        or gorevler["planlanan"]
        or denemeler["adet"]
        or tekrar["planlanan"]
        or defter["eklenen"]
        or (metrik.get("mikro") or {}).get("calisilan")
    )
    if not veri_var and not hedefler:
        _yorum_ekle(
            yorumlar,
            "veri_yok",
            "bilgi",
            "Bu hafta için kayıt bulunmuyor",
            "Seçilen haftada tamamlanmış çalışma oturumu, program görevi, "
            "deneme veya tekrar kaydı yok. Bu hafta için gerçekleşen veri "
            "olmadığı için karşılaştırma üretilmedi.",
            "Haftalık programını oluşturup çalışma oturumu başlatarak bu "
            "haftanın verisini oluşturabilirsin.",
            5,
        )
        return yorumlar

    # --- 1) Süre değişimi -----------------------------------------------------
    onceki_dk = onceki["degerler"]["dk"] if onceki else None
    if onceki is not None and onceki_dk is not None and dk:
        fark = dk - onceki_dk
        esik = max(30, int(round(onceki_dk * 0.1)))
        if onceki_dk >= 30 and abs(fark) >= esik:
            if fark > 0:
                _yorum_ekle(
                    yorumlar,
                    "sure_artis",
                    "olumlu",
                    "Çalışma süresi arttı",
                    "Bu hafta %s çalıştın; %s %s idi (+%s)."
                    % (
                        _saat_metni(dk),
                        donem_etiketi,
                        _saat_metni(onceki_dk),
                        _saat_metni(fark),
                    ),
                    "Artan süreyi korumak için haftalık süre hedefini bu "
                    "seviyede tutabilirsin.",
                    40,
                )
            else:
                _yorum_ekle(
                    yorumlar,
                    "sure_dusus",
                    "dikkat",
                    "Çalışma süresi azaldı",
                    "Bu hafta %s çalıştın; %s %s idi (%s)."
                    % (
                        _saat_metni(dk),
                        donem_etiketi,
                        _saat_metni(onceki_dk),
                        _saat_metni(fark),
                    ),
                    "Gelecek hafta için süre hedefini küçük bir adımla "
                    "yeniden belirlemek (ör. +%s) başlamayı kolaylaştırır."
                    % _saat_metni(max(30, abs(fark))),
                    20,
                )

    # --- 2) Süre/soru verimi --------------------------------------------------
    if dk >= 120 and tam_hafta:
        verim = _haftalik_verim(metrik)
        onceki_verimler = [
            v
            for v in (_haftalik_verim(m) for m in (seri or [])[:-1])
            if v is not None
        ]
        if verim is not None and len(onceki_verimler) >= 2:
            ortalama = sum(onceki_verimler) / len(onceki_verimler)
            if ortalama >= 1 and verim < ortalama * 0.75:
                _yorum_ekle(
                    yorumlar,
                    "soru_verimi_dusuk",
                    "dikkat",
                    "Süreye göre soru sayısı düşük",
                    "Bu hafta %s çalışmada %d soru çözdün (≈%d soru/saat). "
                    "Son %d haftanın ortalaması ≈%d soru/saat."
                    % (
                        _saat_metni(dk),
                        soru,
                        round(verim),
                        len(onceki_verimler),
                        round(ortalama),
                    ),
                    "Soru bloğunu kısaltıp (ör. 25 dk) blok sonunda kaç soru "
                    "çözdüğünü kontrol etmek verimini görünür kılar.",
                    25,
                )
            elif ortalama >= 1 and verim > ortalama * 1.3:
                _yorum_ekle(
                    yorumlar,
                    "soru_verimi_yuksek",
                    "olumlu",
                    "Soru verimi yüksek",
                    "Bu hafta saat başına ≈%d soru çözdün; son haftaların "
                    "ortalaması ≈%d." % (round(verim), round(ortalama)),
                    "Hız arttığında doğruluk düşebilir; doğru/yanlış "
                    "dağılımını da izlemen faydalı olur.",
                    55,
                )


    # --- 3) Gün dağılımı ------------------------------------------------------
    if tam_hafta and calisma["veri_var"]:
        if aktif_gun <= 2 and dk >= 60:
            _yorum_ekle(
                yorumlar,
                "gun_dagilimi_dusuk",
                "dikkat",
                "Çalışma az sayıda güne toplandı",
                "Bu hafta %s çalışma %d günde toplandı."
                % (_saat_metni(dk), aktif_gun),
                "Haftalık toplam aynı kalsa bile çalışmayı 4-5 güne yaymak "
                "kalıcılığı artırır.",
                30,
            )
        elif aktif_gun >= 6:
            _yorum_ekle(
                yorumlar,
                "gun_dagilimi_iyi",
                "olumlu",
                "Düzenli çalışma",
                "Bu hafta %d gün çalıştın (toplam %s)."
                % (aktif_gun, _saat_metni(dk)),
                "Bu düzeni korumak için gelecek hafta dinlenme gününü "
                "planına bilinçli olarak ekleyebilirsin.",
                60,
            )

    # --- 4) Program uyumu -----------------------------------------------------
    uyum = gorevler["uyum"]
    if uyum is not None and gorevler["planlanan"] >= 4:
        if uyum < 60:
            _yorum_ekle(
                yorumlar,
                "program_uyumu_dusuk",
                "dikkat",
                "Program uyumu düşük",
                "Planlanan %d görevin %d tanesi tamamlandı (uyum %%%s). "
                "%d görev bekliyor."
                % (
                    gorevler["planlanan"],
                    gorevler["tamamlanan"],
                    ("%.1f" % uyum).rstrip("0").rstrip("."),
                    gorevler["bekleyen"],
                ),
                "Gelecek haftanın planını oluştururken günlük görev sayısını "
                "azaltmak veya tamamlanmayan görevleri devretmek uyumu "
                "yükseltir.",
                15,
            )
        elif uyum >= 90:
            _yorum_ekle(
                yorumlar,
                "program_uyumu_iyi",
                "olumlu",
                "Program uyumu yüksek",
                "Planlanan %d görevin %d tanesi tamamlandı (uyum %%%s)."
                % (
                    gorevler["planlanan"],
                    gorevler["tamamlanan"],
                    ("%.1f" % uyum).rstrip("0").rstrip("."),
                ),
                "Bu uyumu korurken soru hedeflerini küçük artışlarla "
                "yükseltebilirsin.",
                65,
            )
    if gorevler["devir_giden"]:
        _yorum_ekle(
            yorumlar,
            "gorev_devri",
            "bilgi",
            "Devreden görevler var",
            "Bu haftanın %d görevi sonraki haftaya devretti (%d soru)."
            % (gorevler["devir_giden"], gorevler["devredilen_soru"]),
            "Devreden görevleri gelecek haftanın planında görünür tutup "
            "öncelik sırasını yeniden değerlendirebilirsin.",
            50,
        )

    # --- 5) Aralıklı tekrar ---------------------------------------------------
    if tekrar["planlanan"] >= 3 and tekrar["tamamlama_orani"] is not None:
        if tekrar["tamamlama_orani"] >= 80:
            _yorum_ekle(
                yorumlar,
                "tekrar_iyi",
                "olumlu",
                "Tekrarların çoğu tamamlandı",
                "Planlanan %d tekrarın %d tanesi tamamlandı (%%%s)."
                % (
                    tekrar["planlanan"],
                    tekrar["tamamlanan"],
                    ("%.1f" % tekrar["tamamlama_orani"]).rstrip("0").rstrip("."),
                ),
                "Tekrar aralığını korumak, öğrenmenin kalıcılığını artırır.",
                70,
            )
        elif tekrar["tamamlama_orani"] <= 40:
            _yorum_ekle(
                yorumlar,
                "tekrar_zayif",
                "dikkat",
                "Tekrarların önemli bölümü bekliyor",
                "Planlanan %d tekrarın %d tanesi tamamlandı; %d tanesi "
                "bekliyor." % (
                    tekrar["planlanan"],
                    tekrar["tamamlanan"],
                    tekrar["bekleyen"],
                ),
                "Gelecek haftanın programında tekrar görevlerine sabit bir "
                "zaman bloğu ayırmak (ör. günde 20 dk) birikmeyi önler.",
                18,
            )
    if tekrar["gecikmis_bekleyen"]:
        _yorum_ekle(
            yorumlar,
            "tekrar_gecikme",
            "dikkat",
            "Gecikmiş tekrar var",
            "Bu hafta planlanan %d tekrarın plan tarihi geçmiş durumda."
            % tekrar["gecikmis_bekleyen"],
            "Gecikmiş tekrarları haftanın ilk günlerine almak, birikmenin "
            "büyümesini engeller.",
            22,
        )

    # --- 6) Yanlış soru defteri ----------------------------------------------
    if defter["degisim"] >= 3:
        _yorum_ekle(
            yorumlar,
            "bekleyen_yanlis_artis",
            "dikkat",
            "Bekleyen yanlış soru sayısı arttı",
            "Defterde bekleyen soru sayısı %d → %d oldu (hafta içinde %d "
            "soru eklendi, %d soru öğrenildi)."
            % (
                defter["baslangic_bekleyen"],
                defter["bitis_bekleyen"],
                defter["eklenen"],
                defter["ogrenilen"],
            ),
            "Gelecek haftanın programında yanlış sorular için ayrı çalışma "
            "blokları ayırmak birikmeyi azaltır.",
            16,
        )
    elif defter["degisim"] <= -3:
        _yorum_ekle(
            yorumlar,
            "bekleyen_yanlis_azalis",
            "olumlu",
            "Bekleyen yanlış soru sayısı azaldı",
            "Defterde bekleyen soru sayısı %d → %d oldu."
            % (defter["baslangic_bekleyen"], defter["bitis_bekleyen"]),
            "Azalan kayıtları kapatmaya devam etmek için haftada en az bir "
            "yanlış soru bloğu planlayabilirsin.",
            68,
        )


    # --- 7) Hedefler ----------------------------------------------------------
    tamamlanan_hedefler = [
        h for h in (hedefler or []) if h["durum"] == HEDEF_DURUM_TAMAM
    ]
    geride_hedefler = [
        h
        for h in (hedefler or [])
        if h["durum"] == HEDEF_DURUM_DEVAM
        and h["oran"] is not None
        and h["oran"] < 70
    ]
    if tamamlanan_hedefler:
        _yorum_ekle(
            yorumlar,
            "hedef_tamam",
            "olumlu",
            (
                "Hedef tamamlandı"
                if len(tamamlanan_hedefler) == 1
                else "Hedefler tamamlandı"
            ),
            "; ".join(
                "%s: %s / %s"
                % (h["etiket"], _deger_metni(h), _deger_metni(h, hedef_degeri=True))
                for h in tamamlanan_hedefler[:3]
            ),
            "Aynı hedefi gelecek haftaya aynen taşımak yerine küçük bir "
            "artışla güncelleyebilirsin.",
            75,
        )
    if geride_hedefler:
        en_geride = min(geride_hedefler, key=lambda h: h["oran"])
        _yorum_ekle(
            yorumlar,
            "hedef_geride",
            "dikkat",
            "Hedefe henüz ulaşılmadı",
            "%s: %s / %s (%%%s)."
            % (
                en_geride["etiket"],
                _deger_metni(en_geride),
                _deger_metni(en_geride, hedef_degeri=True),
                ("%.0f" % en_geride["oran"]),
            ),
            "Gelecek haftada bu hedefi korumak ve günlük plana küçük "
            "bloklar eklemek farkı kapatmayı kolaylaştırır.",
            28,
        )
    elif not hedefler and (calisma["veri_var"] or gorevler["planlanan"]):
        _yorum_ekle(
            yorumlar,
            "hedef_yok",
            "bilgi",
            "Bu hafta için hedef belirlenmemiş",
            "Seçilen hafta için kayıtlı bir haftalık hedef bulunmuyor; "
            "ilerleme yüzdesi hesaplanamaz.",
            "Süre, soru veya ders bazlı bir hedef belirlemek gelişimini "
            "ölçmeyi kolaylaştırır.",
            45,
        )

    # --- 8) Ders bazlı çok haftalık düşüş ------------------------------------
    if tam_hafta and seri and len(seri) >= 3:
        son_uc = seri[-3:]
        en_buyuk = None
        for ders in set(son_uc[0].get("ders_dk") or {}):
            degerler = [(m.get("ders_dk") or {}).get(ders) for m in son_uc]
            if any(d is None for d in degerler):
                continue
            ilk, orta, son = degerler
            if ilk < 60 or not (son < orta < ilk):
                continue
            azalma = ilk - son
            if azalma < 30 or azalma < ilk * 0.2:
                continue
            if en_buyuk is None or azalma > en_buyuk[1]:
                en_buyuk = (ders, azalma, ilk, orta, son)
        if en_buyuk:
            _yorum_ekle(
                yorumlar,
                "ders_dusus",
                "dikkat",
                "Bir derste süre azalıyor",
                "%s çalışma süren son üç haftada %s → %s → %s oldu."
                % (
                    en_buyuk[0],
                    _saat_metni(en_buyuk[2]),
                    _saat_metni(en_buyuk[3]),
                    _saat_metni(en_buyuk[4]),
                ),
                "Gelecek hafta %s için ayırdığın süreyi yeniden "
                "değerlendirebilirsin." % en_buyuk[0],
                24,
            )


    # --- 9) Deneme ------------------------------------------------------------
    netler = [n for n in denemeler["netler"] if n["net"] is not None]
    if len(netler) >= 2:
        ilk = netler[0]["net"]
        son = netler[-1]["net"]
        fark = round(float(son) - float(ilk), 2)
        if abs(fark) >= 2:
            _yorum_ekle(
                yorumlar,
                "deneme_degisim",
                "olumlu" if fark > 0 else "bilgi",
                "Hafta içi deneme neti değişti",
                "Bu haftaki denemelerde net %.2f → %.2f oldu (%+.2f). Bu bir "
                "gözlemdir; tek deneme farkı kalıcı eğilim sayılmaz."
                % (ilk, son, fark),
                "Net değişimini ders bazında da kontrol edip zayıf kalan "
                "derse bir sonraki hafta ağırlık verebilirsin.",
                52 if fark > 0 else 35,
            )

    net_trendi = [
        m.get("deneme_net")
        for m in (seri or [])
        if m.get("deneme_net") is not None
    ]
    if tam_hafta and len(net_trendi) >= 3:
        ilk_ort = sum(net_trendi[:2]) / 2.0
        son_ort = sum(net_trendi[-2:]) / 2.0
        if abs(son_ort - ilk_ort) >= 2:
            _yorum_ekle(
                yorumlar,
                "deneme_trend",
                "olumlu" if son_ort > ilk_ort else "bilgi",
                "Deneme neti eğilimi",
                "Son %d haftanın ilk iki haftasında ortalama net %.1f, son "
                "iki haftasında %.1f." % (len(net_trendi), ilk_ort, son_ort),
                "Eğilimi tek haftalık dalgalanmalarla değil, birkaç deneme "
                "üzerinden değerlendirmek daha güvenilir.",
                58,
            )

    onceki_ders_netleri = {
        k["ders"]: k["net_ort"]
        for k in ((onceki or {}).get("denemeler") or {}).get("dersler", [])
        if k.get("net_ort") is not None
    }
    if denemeler["adet"] and onceki_ders_netleri:
        degisimler = []
        for kart in denemeler["dersler"]:
            eski = onceki_ders_netleri.get(kart["ders"])
            if eski is None or kart.get("net_ort") is None:
                continue
            degisimler.append((kart["ders"], eski, kart["net_ort"]))
        if degisimler:
            degisimler.sort(key=lambda x: -abs(x[2] - x[1]))
            ders, eski, yeni = degisimler[0]
            if abs(yeni - eski) >= 1.5:
                _yorum_ekle(
                    yorumlar,
                    "deneme_ders_degisim",
                    "olumlu" if yeni > eski else "bilgi",
                    "Ders bazlı deneme değişimi",
                    "%s net ortalaması %s dönemine göre %.2f → %.2f oldu."
                    % (ders, donem_etiketi, eski, yeni),
                    "Tek denemedeki değişim kalıcı gerileme sayılmaz; birkaç "
                    "deneme sonrası eğilimi yeniden kontrol et.",
                    56,
                )

    if denemeler["adet"] == 0 and tam_hafta and veri_var:
        _yorum_ekle(
            yorumlar,
            "deneme_yok",
            "bilgi",
            "Bu hafta deneme kaydı yok",
            "Seçilen haftada deneme sonucu girilmemiş; deneme analizi "
            "bölümü bu hafta için hesaplanamıyor.",
            "Bir sonraki denemeyi girdiğinde net değişimini ve ders "
            "kırılımını burada görebilirsin.",
            72,
        )

    yorumlar.sort(
        key=lambda y: (
            _TUR_SIRASI.get(y["tur"], 3),
            -y["oncelik"],
            y["kod"],
        )
    )
    return yorumlar


def _kodlar(yorumlar):
    return {y["kod"] for y in yorumlar}



# ==============================================================================
# HAFTALIK HEDEFLER (kalıcı; haftaya bağlı; öğrenci bazlı izolasyon)
# ==============================================================================
_TAM_SAYI_BIRIMLERI = ("gün", "görev", "deneme", "soru")


def _hedef_tanimi(tur):
    tanim = HEDEF_TURLERI.get(str(tur or "").strip())
    if tanim is None:
        raise HaftalikRaporHatasi(
            "Geçersiz hedef türü: %s. Geçerli türler: %s"
            % (tur, ", ".join(HEDEF_TURLERI))
        )
    return tanim


def _hedef_deger_dogrula(tur, deger, tanim):
    if isinstance(deger, bool) or deger is None or deger == "":
        raise HaftalikRaporHatasi("Hedef değeri boş olamaz.")
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        raise HaftalikRaporHatasi("Hedef değeri sayı olmalıdır.") from None
    if sayi <= 0:
        raise HaftalikRaporHatasi("Hedef değeri sıfırdan büyük olmalıdır.")
    if sayi > tanim["maks"]:
        raise HaftalikRaporHatasi(
            "Hedef değeri en fazla %d olabilir." % tanim["maks"]
        )
    if tanim["birim"] in _TAM_SAYI_BIRIMLERI:
        return float(int(round(sayi)))
    return round(sayi, 1)


def _hedef_satiri(satir):
    tanim = HEDEF_TURLERI.get(satir["hedef_turu"], {})
    ders = _metin_say(satir["ders"]) or ""
    etiket = tanim.get("etiket", satir["hedef_turu"])
    if ders:
        etiket = "%s — %s" % (etiket, ders)
    return {
        "id": int(satir["id"]),
        "ogrenci_id": int(satir["ogrenci_id"]),
        "hafta_baslangici": satir["hafta_baslangici"],
        "hedef_turu": satir["hedef_turu"],
        "ders": ders,
        "hedef_deger": float(satir["hedef_deger"]),
        "onceki_deger": (
            None if satir["onceki_deger"] is None else float(satir["onceki_deger"])
        ),
        "guncelleme_sayisi": int(satir["guncelleme_sayisi"] or 0),
        "olusturma_zamani": satir["olusturma_zamani"],
        "guncelleme_zamani": satir["guncelleme_zamani"],
        "etiket": etiket,
        "birim": tanim.get("birim", ""),
        "kisa_etiket": tanim.get("etiket", satir["hedef_turu"]),
    }


def hedefleri_getir(ogrenci_id, hafta=None):
    """Belirtilen haftanın hedefleri (hafta yoksa bu hafta)."""
    oid = _ogrenci_dogrula(ogrenci_id)
    hafta_anahtar = hafta_iso(hafta)
    with _baglanti() as conn:
        if not _tablo_var_mi(conn, "haftalik_hedefler"):
            return []
        satirlar = conn.execute(
            "SELECT * FROM haftalik_hedefler WHERE ogrenci_id = ?"
            " AND hafta_baslangici = ? ORDER BY hedef_turu, ders, id",
            (oid, hafta_anahtar),
        ).fetchall()
    return [_hedef_satiri(s) for s in satirlar]


def hedef_kaydet(ogrenci_id, hafta=None, hedef_turu=None, deger=None, ders=None,
                 an=None):
    """Hedefi oluşturur veya günceller (aynı hafta+tür+ders tekildir).

    Değer değişmediyse yazma yapılmaz; bu sayede Streamlit rerun'ları
    gereksiz kayıt/güncelleme üretmez.
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    tanim = _hedef_tanimi(hedef_turu)
    tur = str(hedef_turu).strip()
    ders_metni = _metin_say(ders) or ""
    if tanim["ders_gerekli"] and not ders_metni:
        raise HaftalikRaporHatasi("%s hedefi için ders seçilmelidir." % tanim["etiket"])
    if not tanim["ders_gerekli"]:
        ders_metni = ""
    deger_sayi = _hedef_deger_dogrula(tur, deger, tanim)
    hafta_anahtar = hafta_iso(hafta)
    zaman = _zaman_yaz(an or simdi())

    with _baglanti() as conn:
        if not _tablo_var_mi(conn, "haftalik_hedefler"):
            raise HaftalikRaporHatasi("Haftalık hedef tablosu bulunamadı.")
        with _islem(conn):
            mevcut = conn.execute(
                "SELECT * FROM haftalik_hedefler WHERE ogrenci_id = ?"
                " AND hafta_baslangici = ? AND hedef_turu = ? AND ders = ?",
                (oid, hafta_anahtar, tur, ders_metni),
            ).fetchone()
            if mevcut is None:
                conn.execute(
                    "INSERT INTO haftalik_hedefler"
                    " (ogrenci_id, hafta_baslangici, hedef_turu, ders,"
                    "  hedef_deger, olusturma_zamani)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (oid, hafta_anahtar, tur, ders_metni, deger_sayi, zaman),
                )
                yeni = True
            elif abs(float(mevcut["hedef_deger"]) - deger_sayi) < 0.0001:
                return _hedef_satiri(mevcut)  # değişiklik yok: yazma yok
            else:
                conn.execute(
                    "UPDATE haftalik_hedefler SET hedef_deger = ?,"
                    " onceki_deger = ?, guncelleme_sayisi = guncelleme_sayisi + 1,"
                    " guncelleme_zamani = ? WHERE id = ?",
                    (deger_sayi, float(mevcut["hedef_deger"]), zaman, mevcut["id"]),
                )
                yeni = False
    kayit = hedefleri_getir(oid, hafta_anahtar)
    for satir in kayit:
        if satir["hedef_turu"] == tur and satir["ders"] == ders_metni:
            satir["yeni"] = yeni
            return satir
    return None


def hedef_sil(hedef_id, ogrenci_id=None):
    """Hedefi siler. Öğrenci kimliği verilirse sahiplik doğrulanır."""
    try:
        hid = int(hedef_id)
    except (TypeError, ValueError):
        raise HaftalikRaporHatasi("Geçersiz hedef numarası.") from None
    with _baglanti() as conn:
        if not _tablo_var_mi(conn, "haftalik_hedefler"):
            return False
        with _islem(conn):
            if ogrenci_id is None:
                imlec = conn.execute(
                    "DELETE FROM haftalik_hedefler WHERE id = ?", (hid,)
                )
            else:
                imlec = conn.execute(
                    "DELETE FROM haftalik_hedefler WHERE id = ? AND ogrenci_id = ?",
                    (hid, int(ogrenci_id)),
                )
            silinen = imlec.rowcount or 0
    return bool(silinen)



def hedefleri_kopyala(ogrenci_id, kaynak_hafta, hedef_hafta=None, an=None):
    """Önceki haftanın hedeflerini yeni haftaya kopyalar (var olanı ezmez)."""
    oid = _ogrenci_dogrula(ogrenci_id)
    kaynak = hafta_iso(kaynak_hafta) if kaynak_hafta is not None else hafta_iso(
        onceki_hafta()
    )
    if hedef_hafta is None:
        hedef = hafta_iso(sonraki_hafta(kaynak))
    else:
        hedef = hafta_iso(hedef_hafta)
    if kaynak == hedef:
        raise HaftalikRaporHatasi("Kaynak ve hedef hafta aynı olamaz.")
    kaynak_hedefler = hedefleri_getir(oid, kaynak)
    mevcut = {
        (h["hedef_turu"], h["ders"]) for h in hedefleri_getir(oid, hedef)
    }
    kopyalanan = 0
    for hedef_kayit in kaynak_hedefler:
        anahtar = (hedef_kayit["hedef_turu"], hedef_kayit["ders"])
        if anahtar in mevcut:
            continue
        hedef_kaydet(
            oid,
            hedef,
            hedef_kayit["hedef_turu"],
            hedef_kayit["hedef_deger"],
            ders=hedef_kayit["ders"] or None,
            an=an,
        )
        kopyalanan += 1
    return {
        "kaynak_hafta": kaynak,
        "hedef_hafta": hedef,
        "kopyalanan": kopyalanan,
        "kaynak_adet": len(kaynak_hedefler),
    }


def _deger_metni(hedef, hedef_degeri=False):
    """Hedef/gerçekleşen değerin okunur metni (dk -> '4 sa 15 dk')."""
    if hedef_degeri:
        deger = hedef.get("hedef_deger")
    else:
        deger = hedef.get("gercek")
    if deger is None:
        return "—"
    birim = hedef.get("birim") or ""
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        return str(deger)
    if birim == "dk":
        return _saat_metni(sayi)
    if birim == "%":
        return ("%.1f" % sayi).rstrip("0").rstrip(".") + "%"
    if abs(sayi - round(sayi)) < 0.001:
        return "%d %s" % (int(round(sayi)), birim) if birim else "%d" % int(round(sayi))
    return ("%.1f" % sayi) + (" %s" % birim if birim else "")


def _hedef_gercek(hedef, metrik):
    """Hedef türüne göre gerçekleşen değer (veri yoksa (None, False))."""
    tur = hedef["hedef_turu"]
    degerler = metrik["degerler"]
    if tur == "calisma_suresi":
        return (degerler["dk"], True)
    if tur == "soru":
        return (degerler["soru"], True)
    if tur == "aktif_gun":
        return (degerler["aktif_gun"], True)
    if tur == "gorev":
        return (degerler["tamamlanan_gorev"], True)
    if tur == "deneme":
        return (degerler["deneme_adet"], True)
    if tur == "program_uyumu":
        return (degerler["uyum"], degerler["uyum"] is not None)
    if tur in ("ders_suresi", "ders_soru"):
        kart = next(
            (k for k in (metrik.get("dersler") or []) if k["ders"] == hedef["ders"]),
            None,
        )
        if kart is None:
            return (0.0, False)
        return (
            kart["dk"] if tur == "ders_suresi" else kart["soru"],
            True,
        )
    return (None, False)


def hedef_karti(hedef, metrik):
    """Hedefin ilerleme kartı: hedef, gerçek, kalan, oran ve durum."""
    gercek, veri_var = _hedef_gercek(hedef, metrik)
    hedef_deger = float(hedef["hedef_deger"])
    if gercek is None:
        oran_ham = None
        kalan = None
        durum = HEDEF_DURUM_VERI
    else:
        oran_ham = round(float(gercek) / hedef_deger * 100, 1) if hedef_deger else None
        kalan = max(0.0, hedef_deger - float(gercek))
        if oran_ham is not None and oran_ham >= 100:
            durum = HEDEF_DURUM_TAMAM
        elif not veri_var:
            durum = HEDEF_DURUM_BASLAMADI if not gercek else HEDEF_DURUM_DEVAM
        elif oran_ham >= 80:
            durum = HEDEF_DURUM_YAKIN
        elif float(gercek) > 0:
            durum = HEDEF_DURUM_DEVAM
        else:
            durum = HEDEF_DURUM_BASLAMADI
    kart = dict(hedef)
    kart.update(
        {
            "gercek": gercek,
            "kalan": kalan,
            "oran": (
                None if oran_ham is None else min(100.0, max(0.0, oran_ham))
            ),
            "oran_ham": oran_ham,
            "asildi": bool(oran_ham is not None and oran_ham > 100),
            "durum": durum,
            "veri_var": veri_var,
        }
    )
    kart["gercek_metin"] = _deger_metni(kart)
    kart["hedef_metin"] = _deger_metni(kart, hedef_degeri=True)
    kart["kalan_metin"] = _deger_metni(dict(kart, gercek=kalan))
    return kart


def hedef_ilerlemeleri(
    ogrenci_id, hafta=None, an=None, rapor=None, hedefler=None, metrik=None
):
    """Haftalık hedeflerin gerçekleşme durumunu döndürür."""
    if rapor is not None:
        kayitlar = rapor["hedefler"]["kayitli"]
        metrik = rapor["_metrik"]
    else:
        oid = _ogrenci_dogrula(ogrenci_id)
        kayitlar = hedefler if hedefler is not None else hedefleri_getir(oid, hafta)
        if metrik is None:
            raise HaftalikRaporHatasi(
                "Hedef ilerlemesi için rapor metrikleri gerekir."
            )
    return [hedef_karti(k, metrik) for k in kayitlar]


def hedefleri_ozetle(kartlar):
    """Arayüz/yorumlar için hedef özeti."""
    kartlar = kartlar or []
    return {
        "adet": len(kartlar),
        "tamamlanan": sum(1 for k in kartlar if k["durum"] == HEDEF_DURUM_TAMAM),
        "yaklasan": sum(1 for k in kartlar if k["durum"] == HEDEF_DURUM_YAKIN),
        "devam": sum(1 for k in kartlar if k["durum"] == HEDEF_DURUM_DEVAM),
        "baslamadi": sum(
            1 for k in kartlar if k["durum"] == HEDEF_DURUM_BASLAMADI
        ),
        "veri_bekleyen": sum(
            1 for k in kartlar if k["durum"] == HEDEF_DURUM_VERI
        ),
        "ortalama_oran": (
            round(sum(k["oran"] for k in kartlar if k["oran"] is not None)
                  / max(1, len([k for k in kartlar if k["oran"] is not None])), 1)
            if any(k["oran"] is not None for k in kartlar)
            else None
        ),
    }



# ==============================================================================
# HAFTALIK ÖĞRENCİ DEĞERLENDİRMESİ (isteğe bağlı notlar)
# ==============================================================================
def _degerlendirme_satiri(satir):
    if satir is None:
        return None
    kayit = {
        "id": int(satir["id"]),
        "ogrenci_id": int(satir["ogrenci_id"]),
        "hafta_baslangici": satir["hafta_baslangici"],
        "olusturma_zamani": satir["olusturma_zamani"],
        "guncelleme_zamani": satir["guncelleme_zamani"],
    }
    for kolon, _soru in DEGERLENDIRME_ALANLARI:
        kayit[kolon] = satir[kolon]
    kayit["dolu"] = any(kayit[k] for k, _s in DEGERLENDIRME_ALANLARI)
    return kayit


def degerlendirme_getir(ogrenci_id, hafta=None):
    oid = _ogrenci_dogrula(ogrenci_id)
    hafta_anahtar = hafta_iso(hafta)
    with _baglanti() as conn:
        if not _tablo_var_mi(conn, "haftalik_degerlendirmeler"):
            return None
        satir = conn.execute(
            "SELECT * FROM haftalik_degerlendirmeler WHERE ogrenci_id = ?"
            " AND hafta_baslangici = ?",
            (oid, hafta_anahtar),
        ).fetchone()
    return _degerlendirme_satiri(satir)


def degerlendirmeleri_getir(ogrenci_id, limit=12):
    """Geçmiş haftaların notları (en yeni önce)."""
    oid = _ogrenci_dogrula(ogrenci_id)
    try:
        limit = max(1, min(60, int(limit)))
    except (TypeError, ValueError):
        limit = 12
    with _baglanti() as conn:
        if not _tablo_var_mi(conn, "haftalik_degerlendirmeler"):
            return []
        satirlar = conn.execute(
            "SELECT * FROM haftalik_degerlendirmeler WHERE ogrenci_id = ?"
            " ORDER BY hafta_baslangici DESC LIMIT ?",
            (oid, limit),
        ).fetchall()
    kayitlar = [_degerlendirme_satiri(s) for s in satirlar]
    for kayit in kayitlar:
        kayit["etiket"] = hafta_etiketi(kayit["hafta_baslangici"])
    return kayitlar


def degerlendirme_kaydet(
    ogrenci_id,
    hafta=None,
    en_iyi=None,
    zorlanilan=None,
    ise_yarayan=None,
    degistirilecek=None,
    an=None,
):
    """Haftalık notları kaydeder (öğrenci+hafta tekil).

    Tüm alanlar boşsa ve kayıt yoksa yazma yapılmaz (rerun gürültüsü yok).
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    hafta_anahtar = hafta_iso(hafta)
    degerler = {
        "en_iyi": _metin_say(en_iyi, DEGERLENDIRME_ALANLARI[0][1]),
        "zorlanilan": _metin_say(zorlanilan, DEGERLENDIRME_ALANLARI[1][1]),
        "ise_yarayan": _metin_say(ise_yarayan, DEGERLENDIRME_ALANLARI[2][1]),
        "degistirilecek": _metin_say(degistirilecek, DEGERLENDIRME_ALANLARI[3][1]),
    }
    zaman = _zaman_yaz(an or simdi())
    with _baglanti() as conn:
        if not _tablo_var_mi(conn, "haftalik_degerlendirmeler"):
            raise HaftalikRaporHatasi("Değerlendirme tablosu bulunamadı.")
        with _islem(conn):
            mevcut = conn.execute(
                "SELECT * FROM haftalik_degerlendirmeler WHERE ogrenci_id = ?"
                " AND hafta_baslangici = ?",
                (oid, hafta_anahtar),
            ).fetchone()
            if mevcut is None:
                if not any(degerler.values()):
                    return None
                conn.execute(
                    "INSERT INTO haftalik_degerlendirmeler"
                    " (ogrenci_id, hafta_baslangici, en_iyi, zorlanilan,"
                    "  ise_yarayan, degistirilecek, olusturma_zamani)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        oid,
                        hafta_anahtar,
                        degerler["en_iyi"],
                        degerler["zorlanilan"],
                        degerler["ise_yarayan"],
                        degerler["degistirilecek"],
                        zaman,
                    ),
                )
            else:
                ayni = all(
                    (mevcut[k] or None) == degerler[k] for k in degerler
                )
                if ayni:
                    return _degerlendirme_satiri(mevcut)
                conn.execute(
                    "UPDATE haftalik_degerlendirmeler SET en_iyi = ?,"
                    " zorlanilan = ?, ise_yarayan = ?, degistirilecek = ?,"
                    " guncelleme_zamani = ? WHERE id = ?",
                    (
                        degerler["en_iyi"],
                        degerler["zorlanilan"],
                        degerler["ise_yarayan"],
                        degerler["degistirilecek"],
                        zaman,
                        mevcut["id"],
                    ),
                )
    return degerlendirme_getir(oid, hafta_anahtar)


# ==============================================================================
# RAPOR ÜRETİMİ
# ==============================================================================
def _hafta_bilgisi(bas, bugun_t):
    """Haftanın durumu: tamamlandı / devam ediyor / gelecek."""
    bit = bas + timedelta(days=6)
    if bit < bugun_t:
        durum = "tamamlandi"
        bit_etkin = bit
    elif bas <= bugun_t <= bit:
        durum = "devam"
        bit_etkin = bugun_t
    else:
        durum = "gelecek"
        bit_etkin = bas - timedelta(days=1)
    olculen = (bit_etkin - bas).days + 1
    olculen = max(0, min(7, olculen))
    durum_metni = {
        "tamamlandi": "Tamamlandı",
        "devam": "Devam ediyor",
        "gelecek": "Henüz başlamadı",
    }[durum]
    return {
        "baslangic": bas.isoformat(),
        "bitis": bit.isoformat(),
        "baslangic_tarih": bas,
        "bitis_tarih": bit,
        "etiket": hafta_etiketi(bas),
        "kisa": "%s – %s" % (_kisa_tarih(bas), _kisa_tarih(bit)),
        "durum": durum,
        "durum_metni": durum_metni,
        "devam_ediyor": durum == "devam",
        "tamamlandi": durum == "tamamlandi",
        "gelecek": durum == "gelecek",
        "olculen_gun": olculen,
        "toplam_gun": 7,
        "bitis_etkin": bit_etkin.isoformat(),
        "bugun": bugun_t.isoformat(),
    }


def _rapor_metrigi(conn, oid, bas, bit_etkin, bugun_t, durum):
    metrik = _metrikler(
        conn, oid, bas, bit_etkin, hafif=False, bugun_tarih=bugun_t
    )
    metrik["tam_hafta"] = durum == "tamamlandi"
    metrik["devam_ediyor"] = durum == "devam"
    metrik["baslangic"] = bas.isoformat()
    metrik["bitis"] = bit_etkin.isoformat()
    return metrik


def rapor_uret(ogrenci_id, hafta=None, an=None, hedefler_dahil=True):
    """Haftalık performans raporunu kaynak verilerden üretir (snapshot yok).

    `hafta`: herhangi bir gün (date / datetime / 'YYYY-AA-GG'); o haftanın
    Pazartesi'si esas alınır. Verilmezse içinde bulunulan hafta.
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    referans = an if an is not None else simdi()
    if isinstance(referans, datetime):
        bugun_t = referans.date()
    else:
        bugun_t = _tarih_oku(referans, "Rapor tarihi")
    bas = hafta_basi(hafta if hafta is not None else bugun_t)
    bilgi = _hafta_bilgisi(bas, bugun_t)
    bit_etkin = _tarih_oku(bilgi["bitis_etkin"])

    with _baglanti() as conn:
        metrik = _rapor_metrigi(
            conn, oid, bas, bit_etkin, bugun_t, bilgi["durum"]
        )
        # Önceki dönem: hafta tamamlandıysa tam hafta, devam ediyorsa eşit
        # uzunlukta kesilmiş dönem. Gelecek haftada karşılaştırma yapılmaz.
        onceki = None
        onceki_onceki = None
        donem_esit = False
        donem_etiketi = "geçen hafta"
        if bilgi["durum"] != "gelecek":
            onceki_bas = bas - timedelta(days=7)
            if bilgi["durum"] == "tamamlandi":
                onceki_bit = onceki_bas + timedelta(days=6)
                onceki_durum = "tamamlandi"
            else:
                onceki_bit = onceki_bas + (bit_etkin - bas)
                onceki_durum = "devam"
                donem_esit = True
                donem_etiketi = "geçen haftanın aynı dönemi"
            onceki = _metrikler(
                conn,
                oid,
                onceki_bas,
                onceki_bit,
                hafif=True,
                bugun_tarih=bugun_t,
            )
            onceki["tam_hafta"] = onceki_durum == "tamamlandi"
            onceki_onceki = _metrikler(
                conn,
                oid,
                onceki_bas - timedelta(days=7),
                onceki_bas - timedelta(days=1),
                hafif=True,
                bugun_tarih=bugun_t,
            )
            onceki_onceki["tam_hafta"] = True

    kayitlar = hedefleri_getir(oid, bas)
    hedef_kartlari = (
        [hedef_karti(k, metrik) for k in kayitlar] if hedefler_dahil else []
    )

    seri_mini = [m for m in (onceki_onceki, onceki, metrik) if m is not None]
    yorumlar = _yorumlar(
        metrik, onceki, seri_mini, hedef_kartlari, donem_etiketi
    )
    gecen_kodlar = set()
    if onceki is not None and onceki_onceki is not None:
        gecen_kodlar = _kodlar(
            _yorumlar(onceki, onceki_onceki, [], [], donem_etiketi)
        )
    for yorum in yorumlar:
        yorum["tekrar"] = yorum["kod"] in gecen_kodlar
    # Tekrar eden öneriler listenin sonuna düşer; haftanın yeni gözlemleri
    # öne çıkar (aynı öneri her hafta gündemin başına geçmez).
    yorumlar.sort(
        key=lambda y: (
            1 if y["tekrar"] else 0,
            _TUR_SIRASI.get(y["tur"], 3),
            -y["oncelik"],
            y["kod"],
        )
    )
    yorumlar = yorumlar[:YORUM_MAKS]

    veri_var = bool(
        metrik["calisma"]["veri_var"]
        or metrik["gorevler"]["planlanan"]
        or metrik["denemeler"]["adet"]
        or metrik["tekrar"]["planlanan"]
        or metrik["defter"]["eklenen"]
    )
    return {
        "ogrenci_id": oid,
        "olusturma_zamani": _zaman_yaz(simdi()),
        "hafta": bilgi,
        "veri_var": veri_var,
        "calisma": metrik["calisma"],
        "dersler": metrik["dersler"],
        "gorevler": metrik["gorevler"],
        "denemeler": metrik["denemeler"],
        "mikro": metrik["mikro"],
        "tekrar": metrik["tekrar"],
        "defter": metrik["defter"],
        "ozet": metrik["degerler"],
        "karsilastirma": _karsilastirma(metrik, onceki, donem_esit),
        "yorumlar": yorumlar,
        "hedefler": {
            "kayitli": kayitlar,
            "ilerleme": hedef_kartlari,
            "ozet": hedefleri_ozetle(hedef_kartlari),
        },
        "degerlendirme": (
            degerlendirme_getir(oid, bas) if hedefler_dahil else None
        ),
        "snapshot": False,  # rapor her açılışta canlı veriden üretilir
        "_metrik": metrik,
    }



def haftalik_seri(ogrenci_id, hafta_sayisi=VARSAYILAN_SERI_HAFTA, an=None):
    """Son N haftanın hafif metrik serisi (en eski -> en yeni)."""
    oid = _ogrenci_dogrula(ogrenci_id)
    try:
        hafta_sayisi = max(1, min(MAKS_SERI_HAFTA, int(hafta_sayisi)))
    except (TypeError, ValueError):
        hafta_sayisi = VARSAYILAN_SERI_HAFTA
    referans = an if an is not None else simdi()
    if isinstance(referans, datetime):
        bugun_t = referans.date()
    else:
        bugun_t = _tarih_oku(referans, "Seri tarihi")
    son_bas = hafta_basi(bugun_t)

    seri = []
    with _baglanti() as conn:
        for sira in range(hafta_sayisi - 1, -1, -1):
            bas = son_bas - timedelta(days=7 * sira)
            bilgi = _hafta_bilgisi(bas, bugun_t)
            bit_etkin = _tarih_oku(bilgi["bitis_etkin"])
            metrik = _metrikler(
                conn, oid, bas, bit_etkin, hafif=True, bugun_tarih=bugun_t
            )
            degerler = metrik["degerler"]
            seri.append(
                {
                    "baslangic": bilgi["baslangic"],
                    "bitis": bilgi["bitis"],
                    "etiket": bilgi["etiket"],
                    "kisa": bilgi["kisa"],
                    "durum": bilgi["durum"],
                    "devam_ediyor": bilgi["devam_ediyor"],
                    "olculen_gun": bilgi["olculen_gun"],
                    "dk": degerler["dk"],
                    "soru": degerler["soru"],
                    "aktif_gun": degerler["aktif_gun"],
                    "uyum": degerler["uyum"],
                    "deneme_adet": degerler["deneme_adet"],
                    "deneme_net": degerler["deneme_net"],
                    "bekleyen_yanlis": degerler["bekleyen_yanlis"],
                    "tamamlanan_tekrar": degerler["tamamlanan_tekrar"],
                    "tamamlanan_gorev": degerler["tamamlanan_gorev"],
                    "ders_dk": metrik["ders_dk"],
                    "veri_var": bool(
                        metrik["calisma"]["veri_var"]
                        or metrik["gorevler"]["planlanan"]
                        or metrik["denemeler"]["adet"]
                    ),
                }
            )
    return seri


def seri_ortalamasi(seri, alan, hafta=4):
    """Son `hafta` haftanın ortalaması (yalnızca veri bulunan haftalar)."""
    if not seri:
        return None
    try:
        hafta = max(1, int(hafta))
    except (TypeError, ValueError):
        hafta = 4
    degerler = [
        s.get(alan)
        for s in seri[-hafta:]
        if s.get(alan) is not None and s.get("veri_var")
    ]
    if not degerler:
        return None
    return round(sum(degerler) / len(degerler), 1)


def trend_yeterli_mi(seri, en_az=GRAFIK_MIN_HAFTA):
    """Grafik için yeterli veri var mı? (veri bulunan hafta sayısı)"""
    return sum(1 for s in (seri or []) if s.get("veri_var")) >= en_az


def seri_ortalama_serisi(seri, alan, hafta=4):
    """Her hafta için o haftaya kadarki (son `hafta` haftalık) ortalama.

    Grafiklerde kısa vadeli dalgalanmayı yumuşatmadan yalnızca toplamı
    göstermek yanıltıcı olduğu için ham seri ve ortalama birlikte sunulur.
    """
    ortalama = []
    for indeks in range(len(seri or [])):
        ortalama.append(seri_ortalamasi(seri[: indeks + 1], alan, hafta))
    return ortalama

