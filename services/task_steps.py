"""FAZ 5B - Mikro görev alt adımları (checklist), soru blokları ve süre planı.

Tasarım ilkeleri:

- **Planlanan != gerçekleşen.** `calisma_programi_gorevler.hedef_soru` planlanan
  sorudur; gerçek soru yalnızca FAZ 4 çalışma oturumlarından okunur. Checklist
  kutusunu işaretlemek gerçek soru ilerlemesi **üretmez**: soru adımlarının
  durumu tamamen gerçek oturumlardan türetilir.
- **Ana görev tamamlanması alt adımlara bağlıdır.** Tüm adımlar bitmeden görev
  tamamlanmış sayılmaz (`gorev_durum_guncelle`).
- **Süreler iki kez sayılmaz.** `KONU_SURELERI_DK` konu anlatımı (teori)
  süresidir; soru çözüm süresi ayrı hesaplanır ve eklenir.
- Tahmini süreler öğrencinin GERÇEK oturumlarından (en az 3 geçerli ölçüm)
  kişiselleştirilir; yeterli veri yoksa varsayılanlar kullanılır.

Bu modül Streamlit'e bağımlı değildir.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

TR_TZ = timezone(timedelta(hours=3))

ADIM_IZLE = "izle"
ADIM_NOT = "not"
ADIM_SORU = "soru"
ADIM_TEKRAR = "tekrar"
ADIM_GENEL = "genel"
ADIM_TURLERI = (ADIM_IZLE, ADIM_NOT, ADIM_SORU, ADIM_TEKRAR, ADIM_GENEL)
# Yalnızca gerçek çalışma kayıtlarından türetilen adım türü
TURETILEN_ADIMLAR = (ADIM_SORU,)

MAKS_ADIM_SAYISI = 24
MAKS_SORU = 2000
MIN_SORU_BLOGU = 5
MAKS_SORU_BLOGU = 10
NOT_SURESI_DK = 6
VARSAYILAN_KONU_SURESI_DK = 60
MIN_KONU_ANLATIM_DK = 10
VARSAYILAN_SORU_SURESI_DK = 1.5
MIN_GERCEK_OLCUM = 3
VARSAYILAN_DB_YOLU = "yks_veritabani.db"

# Ders bazlı soru çözme süresi (dakika/soru). Eski sürümde tüm dersler için
# tek katsayı (1.5) kullanılıyordu; burada ders zorluğuna göre ayrıştırıldı.
# Değerler başlangıç varsayılanlarıdır; öğrencinin gerçek oturumları biriktikçe
# otomatik olarak kişiselleştirilir.
SORU_SURE_KATSAYISI_DK = {
    "TYT Türkçe": 1.2,
    "TYT Matematik": 1.5,
    "TYT Geometri": 1.8,
    "TYT Fizik": 1.4,
    "TYT Kimya": 1.2,
    "TYT Biyoloji": 1.0,
    "TYT Tarih": 1.0,
    "TYT Coğrafya": 1.0,
    "TYT Felsefe": 0.9,
    "TYT Din Kültürü": 0.9,
    "AYT Matematik": 1.9,
    "AYT Geometri": 2.0,
    "AYT Fizik": 1.6,
    "AYT Kimya": 1.6,
    "AYT Biyoloji": 1.4,
    "AYT Edebiyat": 1.2,
    "AYT Tarih": 1.1,
    "AYT Coğrafya": 1.1,
    "AYT Felsefe": 1.0,
    "YDT İngilizce": 1.0,
    "Matematik ve Veri": 1.6,
}

# Tek oturuşta çözülmesi gereken, soru bloklarına BÖLÜNMEYECEK görevler.
BOLUNMEZ_MIKROLAR = ("Günlük Paragraf",)
BOLUNMEZ_MAKROLAR = ("Paragraf",)

_ZAMAN_KALIBI = "%Y-%m-%d %H:%M:%S"


class AdimHatasi(ValueError):
    """Geçersiz alt adım işlemi."""


# ==============================================================================
# YAPILANDIRMA (testler için enjekte edilebilir)
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


def _metin(deger):
    if deger is None:
        return None
    metin = str(deger).strip()
    return metin or None


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
CREATE TABLE IF NOT EXISTS calisma_gorev_alt_adimlari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gorev_id INTEGER NOT NULL,
    baslik TEXT NOT NULL,
    adim_turu TEXT NOT NULL DEFAULT 'genel',
    sira INTEGER NOT NULL DEFAULT 0,
    hedef_soru INTEGER NOT NULL DEFAULT 0,
    durum INTEGER NOT NULL DEFAULT 0,
    olusturma_zamani TEXT NOT NULL,
    tamamlanma_zamani TEXT,
    FOREIGN KEY(gorev_id) REFERENCES calisma_programi_gorevler(id)
        ON DELETE CASCADE
)
"""

_INDEKSLER = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_alt_adim_gorev_sira"
    " ON calisma_gorev_alt_adimlari(gorev_id, sira)",
    "CREATE INDEX IF NOT EXISTS idx_alt_adim_durum"
    " ON calisma_gorev_alt_adimlari(gorev_id, durum)",
)

# FAZ 5D: GÜNLÜK GÖREV tamamlanmasından BAĞIMSIZ mikro konu ilerlemesi.
# Bir mikro konu (alt başlık) yalnızca öğrenme adımları bitip GERÇEK çözülen
# soru sayısı mikro konunun tam hedefine ulaştığında tamamlanır. Günlük görevin
# kapanması bu kaydı kapatmaz; kalan sorular sonraki plana devreder.
_SEMA_MIKRO_ILERLEME = """
CREATE TABLE IF NOT EXISTS mikro_konu_ilerleme (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    ders TEXT NOT NULL,
    makro_konu TEXT,
    mikro_konu TEXT NOT NULL,
    alt_konu TEXT NOT NULL,
    ogrenme_tamam INTEGER NOT NULL DEFAULT 0,
    hedef_soru INTEGER NOT NULL DEFAULT 0,
    cozulen_soru INTEGER NOT NULL DEFAULT 0,
    tamamlandi INTEGER NOT NULL DEFAULT 0,
    son_gorev_id INTEGER,
    olusturma_zamani TEXT,
    guncelleme_zamani TEXT,
    UNIQUE(ogrenci_id, ders, mikro_konu, alt_konu),
    FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
)
"""

_INDEKSLER_MIKRO_ILERLEME = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_mikro_ilerleme_tek"
    " ON mikro_konu_ilerleme(ogrenci_id, ders, mikro_konu, alt_konu)",
    "CREATE INDEX IF NOT EXISTS idx_mikro_ilerleme_durum"
    " ON mikro_konu_ilerleme(ogrenci_id, tamamlandi)",
)


# ==============================================================================
# SORU BLOKLARI
# ==============================================================================
def soru_bloklara_bol(soru_sayisi):
    """Soru sayısını 5-10 soruluk dengeli bloklara böler.

    Kurallar:
      - Toplam değişmez, hiçbir soru kaybolmaz.
      - Gereksiz fazla blok üretilmez (blok sayısı ceil(n/10)).
      - Bloklar mümkün olduğunca dengelidir (fark en fazla 1).
      - 5'in altındaki artık ayrı blok olarak korunur (tek blok kalırsa da).
      - Sıfır/negatif/geçersiz girişlerde boş liste döner.
    """
    if isinstance(soru_sayisi, bool):
        return []
    try:
        n = int(soru_sayisi)
    except (TypeError, ValueError):
        return []
    if n <= 0:
        return []
    if n <= MAKS_SORU_BLOGU:
        return [n]
    blok_sayisi = -(-n // MAKS_SORU_BLOGU)  # ceil
    temel = n // blok_sayisi
    artan = n % blok_sayisi
    return [temel + 1] * artan + [temel] * (blok_sayisi - artan)


def bolunmez_mi(ders=None, makro_konu=None, mikro_konu=None, pedagoji_turu=None):
    """Tek oturuşta yapılması gereken görevler bölünmez (örn. TYT paragraf)."""
    mikro = _metin(mikro_konu) or ""
    makro = _metin(makro_konu) or ""
    if mikro in BOLUNMEZ_MIKROLAR or makro in BOLUNMEZ_MAKROLAR:
        return True
    if "paragraf" in mikro.lower() and (ders or "").lower().find("türkçe") >= 0:
        return True
    return False


def soru_blogu_uret(hedef_soru, ders=None, makro_konu=None, mikro_konu=None,
                    pedagoji_turu=None):
    """Görev için uygulanacak soru blokları (bölünmez görevlerde tek blok)."""
    if bolunmez_mi(ders, makro_konu, mikro_konu, pedagoji_turu):
        try:
            n = int(hedef_soru or 0)
        except (TypeError, ValueError):
            return []
        return [n] if n > 0 else []
    return soru_bloklara_bol(hedef_soru)


# ==============================================================================
# CHECKLIST (ALT ADIMLAR)
# ==============================================================================
def _adim(baslik, tur, hedef_soru=0):
    return {"baslik": baslik, "adim_turu": tur, "hedef_soru": int(hedef_soru or 0)}


def adimlari_uret(gorev):
    """Görev sözlüğünden alt adım listesi üretir.

    - Öğrenme görevi (`gorev_turu='anlatim'`): video izle → kısa not → soru blokları.
    - Soru/pekiştirme görevi (`gorev_turu` soru türleri): yalnızca soru blokları.
    - Tekrar görevi: notları oku → hatırlatma soruları.
    - Deneme tekrarı: yanlışları incele → soru bloğu.
    `gorev_turu` verilmezse (eski motorlar) öğrenme görevi varsayılır.
    """
    gorev = gorev or {}
    ders = _metin(gorev.get("ders"))
    makro = _metin(gorev.get("makro_konu"))
    mikro = _metin(gorev.get("mikro_konu")) or ""
    pedagoji = _metin(gorev.get("pedagoji_turu")) or "Pekiştirme"
    gorev_turu = _metin(gorev.get("gorev_turu")) or "anlatim"
    try:
        hedef = max(0, int(gorev.get("hedef_soru") or 0))
    except (TypeError, ValueError):
        hedef = 0

    adimlar = []
    if pedagoji == "Tekrar":
        adimlar.append(_adim("Özet notlarını oku ve gözden geçir.", ADIM_TEKRAR))
        hatirlatma = 5 if hedef <= 0 else min(hedef, 10)
        if hatirlatma > 0:
            adimlar.append(
                _adim("%d hatırlatma sorusu çöz." % hatirlatma, ADIM_SORU, hatirlatma)
            )
        return adimlar

    if gorev_turu == "anlatim":
        if makro == "Deneme Tekrarı":
            adimlar.append(_adim("Denemede yanlış yaptığın soruları incele.", ADIM_NOT))
        elif bolunmez_mi(ders, makro, mikro, pedagoji):
            adimlar.append(_adim("Konu anlatımını izle / tekrar et.", ADIM_IZLE))
            adimlar.append(_adim("Kısa not çıkar.", ADIM_NOT))
        else:
            adimlar.append(_adim("Konu anlatım videosunu izle.", ADIM_IZLE))
            adimlar.append(_adim("3-4 satırlık kısa not çıkar.", ADIM_NOT))
    elif makro == "Deneme Tekrarı":
        adimlar.append(_adim("Denemede yanlış yaptığın soruları incele.", ADIM_NOT))

    for blok in soru_blogu_uret(hedef, ders, makro, mikro, pedagoji):
        adimlar.append(_adim("%d soru çöz." % blok, ADIM_SORU, blok))

    if not adimlar:
        adimlar.append(_adim("Görevi tamamla.", ADIM_GENEL))
    return adimlar[:MAKS_ADIM_SAYISI]


def adimlari_kaydet(gorev_id, adimlar, conn=None, an=None):
    """Alt adımları yazar. Var olan adımlar korunur (idempotent)."""
    try:
        gid = int(gorev_id)
    except (TypeError, ValueError):
        raise AdimHatasi("Geçersiz görev numarası.") from None
    zaman = _zaman_yaz(an or simdi())
    kayitlar = []
    for sira, adim in enumerate(adimlar or [], 1):
        baslik = _metin(adim.get("baslik"))
        tur = _metin(adim.get("adim_turu")) or ADIM_GENEL
        if tur not in ADIM_TURLERI:
            raise AdimHatasi("Geçersiz adım türü: %s" % tur)
        if not baslik:
            raise AdimHatasi("%d. adımın başlığı boş olamaz." % sira)
        hedef = int(adim.get("hedef_soru") or 0)
        if tur == ADIM_SORU and hedef <= 0:
            raise AdimHatasi("Soru adımı için hedef soru pozitif olmalıdır.")
        kayitlar.append((gid, baslik[:200], tur, sira, max(0, hedef), 0, zaman))

    def _yaz(baglanti):
        mevcut = baglanti.execute(
            "SELECT COUNT(*) FROM calisma_gorev_alt_adimlari WHERE gorev_id = ?",
            (gid,),
        ).fetchone()[0]
        if mevcut:
            return mevcut
        baglanti.executemany(
            "INSERT INTO calisma_gorev_alt_adimlari"
            " (gorev_id, baslik, adim_turu, sira, hedef_soru, durum,"
            "  olusturma_zamani) VALUES (?, ?, ?, ?, ?, ?, ?)",
            kayitlar,
        )
        return len(kayitlar)

    if conn is not None:
        return _yaz(conn)
    with _baglanti() as baglanti:
        with _islem(baglanti):
            return _yaz(baglanti)



def init_db():
    """Tablo/indeksleri idempotent kurar (veri silmez)."""
    with _baglanti() as conn:
        with _islem(conn):
            conn.execute(_SEMA)
            for sorgu in _INDEKSLER:
                conn.execute(sorgu)
            conn.execute(_SEMA_MIKRO_ILERLEME)
            for sorgu in _INDEKSLER_MIKRO_ILERLEME:
                conn.execute(sorgu)
    return True



# ==============================================================================
# GERÇEK SORU / ADIM DURUMU (türetilmiş)
# ==============================================================================
def _gercek_cozulen(conn, gorev_id):
    """Görevdeki TAMAMLANMIŞ oturumlardan gerçek çözülen soru toplamı."""
    try:
        satir = conn.execute(
            "SELECT COALESCE(SUM(cozulen_soru), 0) AS soru FROM calisma_oturumlari"
            " WHERE gorev_id = ? AND durum = ?",
            (gorev_id, "Tamamlandı"),
        ).fetchone()
    except sqlite3.Error:
        return 0
    return int(satir["soru"] or 0)


def _adimlari_turet(satirlar, gercek_soru):
    """Soru adımlarını gerçek çalışma toplamından sırayla doldurur.

    10 + 10 blok hedefinde 12 soru çözüldüyse: 1. blok 10/10 tamam,
    2. blok 2/10 yarım. Böylece planlanan soru gerçek gibi sayılmaz.
    """
    kalan = max(0, int(gercek_soru or 0))
    sonuc = []
    for satir in satirlar:
        adim = dict(satir)
        tur = adim.get("adim_turu")
        hedef = int(adim.get("hedef_soru") or 0)
        if tur == ADIM_SORU:
            adim_gercek = min(hedef, kalan) if hedef > 0 else 0
            kalan -= adim_gercek
            adim["gercek_soru"] = adim_gercek
            adim["tamam"] = bool(hedef > 0 and adim_gercek >= hedef)
            adim["turetildi"] = True
        else:
            adim["gercek_soru"] = 0
            adim["tamam"] = bool(adim.get("durum"))
            adim["turetildi"] = False
        adim["hedef_soru"] = hedef
        sonuc.append(adim)
    return sonuc


def gorev_adimlari(gorev_id):
    """Görevin alt adımları + türetilmiş tamamlanma durumları."""
    try:
        gid = int(gorev_id)
    except (TypeError, ValueError):
        return []
    with _baglanti() as conn:
        satirlar = conn.execute(
            "SELECT * FROM calisma_gorev_alt_adimlari WHERE gorev_id = ?"
            " ORDER BY sira ASC, id ASC",
            (gid,),
        ).fetchall()
        if not satirlar:
            return []
        gercek = _gercek_cozulen(conn, gid)
    return _adimlari_turet(satirlar, gercek)


def adim_durum_degistir(adim_id, tamam=True, an=None):
    """Manuel adımı işaretler/kaldırır. Soru adımları elle değiştirilemez."""
    try:
        aid = int(adim_id)
    except (TypeError, ValueError):
        raise AdimHatasi("Geçersiz adım numarası.") from None
    zaman = _zaman_yaz(an or simdi())
    with _baglanti() as conn:
        with _islem(conn):
            satir = conn.execute(
                "SELECT * FROM calisma_gorev_alt_adimlari WHERE id = ?", (aid,)
            ).fetchone()
            if satir is None:
                raise AdimHatasi("Alt adım bulunamadı (#%s)." % aid)
            if satir["adim_turu"] in TURETILEN_ADIMLAR:
                raise AdimHatasi(
                    "Soru adımları elle işaretlenemez; durumları yalnızca"
                    " tamamlanmış çalışma oturumlarından türetilir."
                )
            yeni = 1 if tamam else 0
            conn.execute(
                "UPDATE calisma_gorev_alt_adimlari SET durum = ?,"
                " tamamlanma_zamani = ? WHERE id = ?",
                (yeni, zaman if yeni else None, aid),
            )
            gorev_id = satir["gorev_id"]
    gorev_durum_guncelle(gorev_id, an=an)
    return True


def gorev_tamam_mi(gorev_id):
    """Görev tamamlandı mı? (adımların tamamı bitmişse True).

    Alt adımı olmayan (eski) görevler için None döner: bu görevlerde manuel
    `durum` alanı geçerlidir.
    """
    adimlar = gorev_adimlari(gorev_id)
    if not adimlar:
        return None
    return all(adim["tamam"] for adim in adimlar)


def _tekrarlari_planla(gorev_id, an=None):
    """FAZ 6A köprüsü: tamamlanan öğrenme görevinden aralıklı tekrar üretir."""
    try:
        from services import spaced_repetition
    except ImportError:  # pragma: no cover - servis yoksa görev akışı bozulmaz
        return []
    try:
        return spaced_repetition.tekrar_planla(gorev_id, an=an)
    except Exception:  # pragma: no cover - tekrar hatası görev işaretini bozmaz
        return []


def _kaynaklari_ilerlet(gorev_id, an=None):
    """FAZ 6C köprüsü: görevin bağlı kaynaklarını (defter/tekrar) ilerletir.

    Görev tamamlanınca bağlı yanlış soru kayıtları `tekrar_edildi`, bağlı
    aralıklı tekrar kayıtları `tekrar_tamamla` ile kapanır. Köprü hatası görev
    işaretini bozmaz.
    """
    try:
        from services import gorev_kaynaklari
    except ImportError:  # pragma: no cover - FAZ 6C modülü yoksa sessiz geç
        return {}
    try:
        return gorev_kaynaklari.gorev_tamamlandi(gorev_id, an=an)
    except Exception:  # pragma: no cover - köprü hatası görev durumunu bozmaz
        return {}


def gorev_durum_guncelle(gorev_id, an=None):
    """Görev `durum` alanını alt adımlardan türetir (adım yoksa dokunmaz).

    FAZ 6A: aralıklı tekrar yalnızca tamamlanmamış -> tamamlanmış (0 -> 1)
    geçişinde planlanır. Böylece sayfa yenilemesi, yeniden kaydetme veya
    geçmişte tamamlanmış görevler mükerrer/geriye dönük tekrar üretmez.
    FAZ 6C: aynı geçişte görevin bağlı kaynakları (yanlış soru defteri /
    bekleyen tekrar kaydı) ilerletilir.
    """
    tamam = gorev_tamam_mi(gorev_id)
    # FAZ 5D: mikro konu ilerlemesi günlük görev durumundan BAĞIMSIZDIR; her
    # kayıtta gerçek adım/oturumlardan tazelenir (eski görevlerde de çalışır).
    try:
        mikro_ilerleme_guncelle(gorev_id, an=an)
    except Exception:  # pragma: no cover - ilerleme hatası görevi bozmaz
        pass
    if tamam is None:
        return None
    try:
        gid = int(gorev_id)
    except (TypeError, ValueError):
        return None
    with _baglanti() as conn:
        with _islem(conn):
            satir = conn.execute(
                "SELECT durum FROM calisma_programi_gorevler WHERE id = ?", (gid,)
            ).fetchone()
            if satir is None:
                return None
            onceki = int(satir["durum"] or 0)
            conn.execute(
                "UPDATE calisma_programi_gorevler SET durum = ? WHERE id = ?",
                (1 if tamam else 0, gid),
            )
    if tamam and onceki == 0:
        _kaynaklari_ilerlet(gid, an)
        _tekrarlari_planla(gid, an)
    return bool(tamam)


def gorev_ilerleme(gorev_id):
    """Kart gösterimi için özet: adım sayısı, gerçek soru, tamamlanma."""
    adimlar = gorev_adimlari(gorev_id)
    hedef = sum(a["hedef_soru"] for a in adimlar if a["adim_turu"] == ADIM_SORU)
    gercek = sum(a["gercek_soru"] for a in adimlar if a["adim_turu"] == ADIM_SORU)
    return {
        "adim_sayisi": len(adimlar),
        "tamamlanan_adim": sum(1 for a in adimlar if a["tamam"]),
        "hedef_soru": hedef,
        "gercek_soru": gercek,
        "tamam": bool(adimlar) and all(a["tamam"] for a in adimlar),
    }


# ==============================================================================
# FAZ 5D: MİKRO KONU İLERLEMESİ (günlük görevden BAĞIMSIZ)
# ==============================================================================
def _kolon_var_mi(conn, tablo, kolon):
    """Tabloda kolon var mı (eski şemalarla uyum için)."""
    try:
        return kolon in [satir[1] for satir in conn.execute("PRAGMA table_info(%s)" % tablo)]
    except sqlite3.Error:  # pragma: no cover - tablo yoksa
        return False


def _mikro_gorev_satiri(conn, gorev_id):
    """Görevin mikro konu kimliği + hedefleri (alt konu yoksa None)."""
    try:
        gid = int(gorev_id)
    except (TypeError, ValueError):
        return None
    mikro_hedef = (
        "mikro_hedef_soru"
        if _kolon_var_mi(conn, "calisma_programi_gorevler", "mikro_hedef_soru")
        else "NULL"
    )
    satir = conn.execute(
        "SELECT id, ogrenci_id, ders, makro_konu, mikro_konu, alt_konu,"
        " hedef_soru, %s AS mikro_hedef_soru"
        " FROM calisma_programi_gorevler WHERE id = ?" % mikro_hedef,
        (gid,),
    ).fetchone()
    if satir is None:
        return None
    ders = _metin(satir["ders"])
    mikro = _metin(satir["mikro_konu"])
    alt = _metin(satir["alt_konu"])
    if not (ders and mikro and alt):
        return None
    return {
        "id": int(satir["id"]),
        "ogrenci_id": satir["ogrenci_id"],
        "ders": ders,
        "makro_konu": _metin(satir["makro_konu"]),
        "mikro_konu": mikro,
        "alt_konu": alt,
        "hedef_soru": int(satir["hedef_soru"] or 0),
        "mikro_hedef_soru": int(satir["mikro_hedef_soru"] or 0),
    }


def _mikro_gercek_durum(conn, gorev):
    """Aynı mikro konunun (alt başlığın) GERÇEK toplamları.

    Dönüş: (öğrenme adımı sayısı, biten adım sayısı, çözülen soru, hedef soru)

    - Adımlar ve oturumlar mikro konunun TÜM görevlerinden toplanır; böylece
      haftaya bölünen (10 + 10) bir mikro konu ancak toplam hedef dolunca
      tamamlanır.
    - Hedef, görevlerin en büyük mikro hedefidir (planlanan parça değil).
    """
    params = (gorev["ogrenci_id"], gorev["ders"], gorev["mikro_konu"], gorev["alt_konu"])
    adim_satirlari = conn.execute(
        "SELECT COALESCE(a.durum, 0) AS durum FROM calisma_gorev_alt_adimlari a"
        " JOIN calisma_programi_gorevler g ON g.id = a.gorev_id"
        " WHERE g.ogrenci_id = ? AND g.ders = ? AND g.mikro_konu = ?"
        " AND COALESCE(g.alt_konu, '') = ? AND a.adim_turu IN (?, ?, ?)",
        params + (ADIM_IZLE, ADIM_NOT, ADIM_TEKRAR),
    ).fetchall()
    toplam_adim = len(adim_satirlari)
    biten_adim = sum(1 for satir in adim_satirlari if int(satir["durum"] or 0))

    mikro_hedef = (
        "mikro_hedef_soru"
        if _kolon_var_mi(conn, "calisma_programi_gorevler", "mikro_hedef_soru")
        else "NULL"
    )
    gorevler = conn.execute(
        "SELECT hedef_soru, %s AS mikro_hedef_soru FROM calisma_programi_gorevler"
        " WHERE ogrenci_id = ? AND ders = ? AND mikro_konu = ?"
        " AND COALESCE(alt_konu, '') = ?" % mikro_hedef,
        params,
    ).fetchall()
    hedefler = []
    for satir in gorevler:
        try:
            deger = int(satir["mikro_hedef_soru"] or 0)
        except (TypeError, ValueError):
            deger = 0
        if deger <= 0:
            deger = int(satir["hedef_soru"] or 0)
        hedefler.append(max(0, deger))
    hedef_soru = max(hedefler) if hedefler else 0

    try:
        cozulen = conn.execute(
            "SELECT COALESCE(SUM(o.cozulen_soru), 0) AS soru"
            " FROM calisma_oturumlari o"
            " JOIN calisma_programi_gorevler g ON g.id = o.gorev_id"
            " WHERE o.durum = ? AND g.ogrenci_id = ? AND g.ders = ?"
            " AND g.mikro_konu = ? AND COALESCE(g.alt_konu, '') = ?",
            ("Tamamlandı",) + params,
        ).fetchone()
        cozulen_soru = int(cozulen["soru"] or 0)
    except sqlite3.Error:  # pragma: no cover - oturum tablosu yoksa
        cozulen_soru = 0
    return toplam_adim, biten_adim, max(0, cozulen_soru), hedef_soru


def mikro_ilerleme_guncelle(gorev_id, an=None):
    """Mikro konu ilerlemesini GERÇEK adım/oturumlardan yeniden türetir.

    FAZ 5D kuralları:
      - `ogrenme_tamam`: video/not/tekrar adımlarının tamamı bitti.
      - `hedef_soru`: mikro konunun TAM hedefi (görevin parçası değil).
      - `cozulen_soru`: mikro konunun tüm görevlerinde çözülen gerçek soru.
      - `tamamlandi`: öğrenme bitti VE hedef soru (varsa) doldu.

    Günlük görevin kapanması bu kaydı KAPATMAZ; kalan soru sonraki plana
    devreder. Bu yüzden fonksiyon görev `durum` alanına hiç bakmaz.
    """
    with _baglanti() as conn:
        with _islem(conn):
            gorev = _mikro_gorev_satiri(conn, gorev_id)
            if gorev is None:
                return None
            toplam_adim, biten_adim, cozulen, hedef = _mikro_gercek_durum(conn, gorev)
            ogrenme_tamam = 1 if (toplam_adim > 0 and biten_adim >= toplam_adim) else 0
            if hedef > 0:
                tamam = 1 if (ogrenme_tamam and cozulen >= hedef) else 0
            else:
                tamam = ogrenme_tamam
            zaman = _zaman_yaz(an or simdi())
            anahtar = (
                gorev["ogrenci_id"], gorev["ders"], gorev["mikro_konu"], gorev["alt_konu"],
            )
            mevcut = conn.execute(
                "SELECT id FROM mikro_konu_ilerleme WHERE ogrenci_id = ? AND ders = ?"
                " AND mikro_konu = ? AND alt_konu = ?",
                anahtar,
            ).fetchone()
            if mevcut is None:
                conn.execute(
                    "INSERT INTO mikro_konu_ilerleme (ogrenci_id, ders, makro_konu,"
                    " mikro_konu, alt_konu, ogrenme_tamam, hedef_soru, cozulen_soru,"
                    " tamamlandi, son_gorev_id, olusturma_zamani, guncelleme_zamani)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        gorev["ogrenci_id"], gorev["ders"], gorev["makro_konu"],
                        gorev["mikro_konu"], gorev["alt_konu"], ogrenme_tamam,
                        hedef, cozulen, tamam, gorev["id"], zaman, zaman,
                    ),
                )
            else:
                conn.execute(
                    "UPDATE mikro_konu_ilerleme SET makro_konu = ?, ogrenme_tamam = ?,"
                    " hedef_soru = ?, cozulen_soru = ?, tamamlandi = ?,"
                    " son_gorev_id = ?, guncelleme_zamani = ? WHERE id = ?",
                    (
                        gorev["makro_konu"], ogrenme_tamam, hedef, cozulen, tamam,
                        gorev["id"], zaman, int(mevcut["id"]),
                    ),
                )
    return {
        "ders": gorev["ders"],
        "mikro_konu": gorev["mikro_konu"],
        "alt_konu": gorev["alt_konu"],
        "ogrenme_tamam": bool(ogrenme_tamam),
        "hedef_soru": hedef,
        "cozulen_soru": cozulen,
        "kalan_soru": max(0, hedef - cozulen),
        "tamamlandi": bool(tamam),
    }


def _mikro_ilerleme_satiri_sozluk(satir):
    """`mikro_konu_ilerleme` satırını sözlüğe çevirir."""
    return {
        "ogrenci_id": satir["ogrenci_id"],
        "ders": satir["ders"],
        "makro_konu": satir["makro_konu"],
        "mikro_konu": satir["mikro_konu"],
        "alt_konu": satir["alt_konu"],
        "ogrenme_tamam": bool(satir["ogrenme_tamam"]),
        "hedef_soru": int(satir["hedef_soru"] or 0),
        "cozulen_soru": int(satir["cozulen_soru"] or 0),
        "kalan_soru": max(
            0, int(satir["hedef_soru"] or 0) - int(satir["cozulen_soru"] or 0)
        ),
        "tamamlandi": bool(satir["tamamlandi"]),
        "son_gorev_id": satir["son_gorev_id"],
        "guncelleme_zamani": satir["guncelleme_zamani"],
    }


def mikro_ilerleme(ogrenci_id, ders, mikro_konu, alt_konu=None):
    """Tek mikro konunun ilerleme kaydı (yoksa None)."""
    alt = _metin(alt_konu)
    sorgu = (
        "SELECT * FROM mikro_konu_ilerleme WHERE ogrenci_id = ? AND ders = ?"
        " AND mikro_konu = ?"
    )
    params = [ogrenci_id, ders, mikro_konu]
    if alt:
        sorgu += " AND alt_konu = ?"
        params.append(alt)
    try:
        with _baglanti() as conn:
            satir = conn.execute(sorgu, tuple(params)).fetchone()
    except sqlite3.Error:  # pragma: no cover - tablo yoksa
        return None
    return _mikro_ilerleme_satiri_sozluk(satir) if satir is not None else None


def mikro_ilerleme_listesi(ogrenci_id, ders=None, makro_konu=None, sadece_tamam=False):
    """Öğrencinin mikro konu ilerlemeleri (ders/ana konu filtreli)."""
    sorgu = "SELECT * FROM mikro_konu_ilerleme WHERE ogrenci_id = ?"
    params = [ogrenci_id]
    if ders:
        sorgu += " AND ders = ?"
        params.append(ders)
    if makro_konu:
        sorgu += " AND makro_konu = ?"
        params.append(makro_konu)
    if sadece_tamam:
        sorgu += " AND tamamlandi = 1"
    sorgu += " ORDER BY ders ASC, makro_konu ASC, mikro_konu ASC, alt_konu ASC"
    try:
        with _baglanti() as conn:
            satirlar = conn.execute(sorgu, tuple(params)).fetchall()
    except sqlite3.Error:  # pragma: no cover - tablo yoksa
        return []
    return [_mikro_ilerleme_satiri_sozluk(satir) for satir in satirlar]


def mikro_tamamlananlar(ogrenci_id):
    """Tamamlanmış mikro konular: {(ders, mikro_konu, alt_konu)}.

    Planlayıcı bu kümeyi kullanır: tamamlanan mikro konu yeniden ÜRETİLMEZ.
    """
    return {
        (kayit["ders"], kayit["mikro_konu"], kayit["alt_konu"])
        for kayit in mikro_ilerleme_listesi(ogrenci_id, sadece_tamam=True)
    }


# ==============================================================================
# SÜRE TAHMİNİ (planlanan süre; gerçek süre FAZ 4 oturumlarından gelir)
# ==============================================================================
def _yuvarla5(deger):
    return int(round(float(deger) / 5.0) * 5)


def _medyan(degerler):
    sirali = sorted(degerler)
    n = len(sirali)
    if not n:
        return None
    orta = n // 2
    if n % 2:
        return float(sirali[orta])
    return (sirali[orta - 1] + sirali[orta]) / 2.0


def _sure_degeri(deger):
    """Pozitif sayıya çevirir; geçersiz/sıfır değerde None döner."""
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        return None
    return sayi if sayi > 0 else None


def mikro_anlatim_suresi(ogrenci_id, ders, mikro_konu, alt_konu=None,
                         konu_sureleri=None):
    """TEK süre kaynağı: bir mikro konunun anlatım süresi (dakika).

    Öncelik sırası (FAZ 5D):
      1) Mikro konuya ÖZEL tanımlı süre (`konu_sureleri[alt_konu]`).
      2) Bu mikro konuda en az 3 GERÇEK ölçüm varsa medyan.
      3) Alt başlığı olmayan (kendisi planlama birimi olan) konularda tanımlı süre.
      4) Makul varsayılan (`VARSAYILAN_KONU_SURESI_DK`).

    Ana konunun süresi alt başlıklara BÖLÜNMEZ ve her alt başlığa KOPYALANMAZ;
    böylece "Polinomlar 80 dk" beş mikro konuya 16'şar dakika olarak yazılmaz.
    """
    konu_sureleri = konu_sureleri or {}
    alt = _metin(alt_konu)
    if alt:
        tohum = _sure_degeri(konu_sureleri.get(alt))
        if tohum:
            return max(MIN_KONU_ANLATIM_DK, _yuvarla5(tohum))
    medyan = konu_suresi_medyani(ogrenci_id, ders, mikro_konu, alt)
    if medyan:
        return max(MIN_KONU_ANLATIM_DK, _yuvarla5(medyan))
    if not alt:
        tohum = _sure_degeri(konu_sureleri.get(_metin(mikro_konu) or ""))
        if tohum:
            return max(MIN_KONU_ANLATIM_DK, _yuvarla5(tohum))
    return max(MIN_KONU_ANLATIM_DK, _yuvarla5(VARSAYILAN_KONU_SURESI_DK))


def konu_anlatim_dk(mikro_konu, alt_sayisi=1, konu_sureleri=None,
                    konu_suresi_dk=None):
    """Mikro konunun konu anlatımı süresi.

    `konu_sureleri` (KONU_SURELERI_DK) konu anlatımı süresidir; soru çözümü
    ayrı hesaplandığı için burada iki kez sayılmaz. Görev, mikro konunun
    yalnızca birkaç alt başlığını kapsıyorsa süre alt başlık sayısına bölünür.

    FAZ 5D: `konu_suresi_dk` verilirse (ana konunun süresi mikro konulara
    paylaştırılmışsa) bölme yapılmaz; bu görevin kendi anlatım süresi kullanılır.
    """
    if konu_suresi_dk not in (None, "", 0):
        try:
            pay = float(konu_suresi_dk)
        except (TypeError, ValueError):
            pay = 0.0
        if pay > 0:
            return max(MIN_KONU_ANLATIM_DK, int(round(pay)))
    konu_sureleri = konu_sureleri or {}
    anahtar = _metin(mikro_konu) or ""
    toplam = konu_sureleri.get(anahtar, VARSAYILAN_KONU_SURESI_DK)
    try:
        toplam = float(toplam)
    except (TypeError, ValueError):
        toplam = float(VARSAYILAN_KONU_SURESI_DK)
    try:
        alt = max(1, int(alt_sayisi or 1))
    except (TypeError, ValueError):
        alt = 1
    return max(MIN_KONU_ANLATIM_DK, _yuvarla5(toplam / alt))


def mikro_sure_paylari(toplam_dk, mikrolar, agirliklar=None,
                       taban=MIN_KONU_ANLATIM_DK):
    """Ana konunun anlatım süresini mikro konulara tam sayı olarak paylaştırır.

    - Paylar ağırlığa (iş yükü) göre dağıtılır; ağırlık yoksa eşit bölünür.
    - Payların toplamı `toplam_dk`'ya EŞİTTİR (yuvarlama artığı en büyük
      kalan yöntemiyle dağıtılır) — süre kaybı/şişmesi olmaz.
    - Yeterli süre varsa her mikro en az `taban` dakika alır; yetmiyorsa
      eşit bölünür (küçük sürelerde taban zorlanmaz).
    - Hiçbir mikro sıfır süre almaz (pay 0 ise taban uygulanır).
    """
    liste = [m for m in (mikrolar or []) if m]
    if not liste:
        return {}
    try:
        toplam = max(0, int(round(float(toplam_dk or 0))))
    except (TypeError, ValueError):
        toplam = 0
    if toplam <= 0:
        return {m: 0 for m in liste}
    agirliklar = agirliklar or {}
    ham = []
    for mikro in liste:
        try:
            agirlik = float(agirliklar.get(mikro, 1.0))
        except (TypeError, ValueError):
            agirlik = 1.0
        ham.append(max(0.1, agirlik))
    toplam_agirlik = sum(ham)
    kesirli = {m: toplam * w / toplam_agirlik for m, w in zip(liste, ham)}
    sonuc = {m: int(kesirli[m]) for m in liste}
    kalan = toplam - sum(sonuc.values())
    if kalan > 0:
        sirali = sorted(liste, key=lambda m: (kesirli[m] - sonuc[m]), reverse=True)
        for i in range(kalan):
            sonuc[sirali[i % len(sirali)]] += 1
    if toplam >= taban * len(liste):
        eksik = [m for m in liste if sonuc[m] < taban]
        for mikro in eksik:
            acik = taban - sonuc[mikro]
            verenler = sorted(
                (m for m in liste if sonuc[m] > taban),
                key=lambda m: sonuc[m],
                reverse=True,
            )
            for veren in verenler:
                if acik <= 0:
                    break
                fazla = min(acik, sonuc[veren] - taban)
                sonuc[veren] -= fazla
                sonuc[mikro] += fazla
                acik -= fazla
    return sonuc


def _ders_oturumlari(conn, ogrenci_id, ders=None, mikro_konu=None,
                     alt_konu=None):
    sorgu = (
        "SELECT gercek_sure_dk, cozulen_soru FROM calisma_oturumlari"
        " WHERE ogrenci_id = ? AND durum = ? AND gercek_sure_dk > 0"
    )
    params = [ogrenci_id, "Tamamlandı"]
    if ders:
        sorgu += " AND ders = ?"
        params.append(ders)
    if mikro_konu:
        sorgu += " AND mikro_konu = ?"
        params.append(mikro_konu)
    if alt_konu:
        sorgu += " AND alt_konu = ?"
        params.append(alt_konu)
    return conn.execute(sorgu, tuple(params)).fetchall()


def ogrenci_soru_hizi(ogrenci_id, ders):
    """Öğrencinin o dersteki GERÇEK dakika/soru hızı (yeterli veri varsa).

    En az `MIN_GERCEK_OLCUM` tamamlanmış oturum ve toplam 15 soru gerekir.
    Aksi hâlde None döner (varsayılan katsayı kullanılır). Ders bazlı
    değerlendirildiği için bir dersteki hız diğerlerine uygulanmaz.
    """
    if not ogrenci_id or not ders:
        return None
    try:
        with _baglanti() as conn:
            satirlar = _ders_oturumlari(conn, int(ogrenci_id), ders=ders)
    except (sqlite3.Error, ValueError):
        return None
    gecerli = [s for s in satirlar if int(s["cozulen_soru"] or 0) > 0]
    if len(gecerli) < MIN_GERCEK_OLCUM:
        return None
    toplam_soru = sum(int(s["cozulen_soru"] or 0) for s in gecerli)
    toplam_dk = sum(int(s["gercek_sure_dk"] or 0) for s in gecerli)
    if toplam_soru < 15 or toplam_dk <= 0:
        return None
    varsayilan = SORU_SURE_KATSAYISI_DK.get(ders, VARSAYILAN_SORU_SURESI_DK)
    hiz = float(toplam_dk) / float(toplam_soru)
    hiz = max(varsayilan * 0.5, min(varsayilan * 1.8, hiz))
    return round(hiz, 2)


def konu_suresi_medyani(ogrenci_id, ders, mikro_konu, alt_konu=None):
    """Aynı ders+mikro konuda en az 3 geçerli oturum varsa medyan süre (dk).

    FAZ 5D: `alt_konu` verilirse medyan MİKRO KONU (alt başlık) bazında
    hesaplanır; böylece ana konunun bir alt başlığındaki gerçek süre diğer
    alt başlıklara uygulanmaz. Verilmezse davranış eskisiyle aynıdır.
    """
    if not ogrenci_id or not (ders and mikro_konu):
        return None
    try:
        with _baglanti() as conn:
            satirlar = _ders_oturumlari(
                conn, int(ogrenci_id), ders=ders, mikro_konu=mikro_konu,
                alt_konu=alt_konu,
            )
    except (sqlite3.Error, ValueError):
        return None
    degerler = [int(s["gercek_sure_dk"] or 0) for s in satirlar]
    degerler = [d for d in degerler if d > 0]
    if len(degerler) < MIN_GERCEK_OLCUM:
        return None
    medyan = _medyan(degerler)
    temiz = [d for d in degerler if medyan * 0.4 <= d <= medyan * 2.2]
    if len(temiz) >= MIN_GERCEK_OLCUM:
        medyan = _medyan(temiz)
    return int(round(medyan or 0))


def _soru_bloklari_suresi(bloklar, katsayi):
    toplam = 0.0
    for blok in bloklar:
        try:
            adet = float(blok)
        except (TypeError, ValueError):
            continue
        if adet >= 10:
            carpan = 0.95  # uzun bloklarda ısınma maliyeti dağılır
        elif adet >= 7:
            carpan = 1.0
        else:
            carpan = 1.08  # kısa bloklarda geçiş/odaklanma maliyeti
        toplam += adet * float(katsayi) * carpan
    return int(round(toplam))


def sure_plani(
    ders,
    mikro_konu=None,
    hedef_soru=0,
    alt_sayisi=1,
    adimlar=None,
    konu_sureleri=None,
    ogrenci_id=None,
    pedagoji_turu=None,
    makro_konu=None,
    gorev_turu="anlatim",
    alt_konu=None,
    konu_suresi_dk=None,
):
    """Görevin PLANLANAN süre dökümü (dk).

    - Konu anlatımı: `konu_suresi_dk` (mikro konuya özel) → gerçek medyan →
      makul varsayılan. Ana konu süresi alt başlıklara bölünmez.
    - Not: sabit kısa süre (adım varsa).
    - Soru çözümü: blok büyüklüğü × ders katsayısı (öğrenci hızı varsa o).
    - Yeterli gerçek ölçüm varsa (>=3 oturum) süre medyana göre ölçeklenir.
    """
    if adimlar is None:
        adimlar = adimlari_uret(
            {
                "ders": ders,
                "makro_konu": makro_konu,
                "mikro_konu": mikro_konu,
                "hedef_soru": hedef_soru,
                "pedagoji_turu": pedagoji_turu,
                "gorev_turu": gorev_turu,
            }
        )
    turler = [a.get("adim_turu") for a in adimlar]
    soru_bloklari = [
        int(a.get("hedef_soru") or 0) for a in adimlar if a.get("adim_turu") == ADIM_SORU
    ]
    soru_bloklari = [b for b in soru_bloklari if b > 0]

    ogrenme = 0
    if ADIM_TEKRAR in turler:
        ogrenme = 20  # tekrar görevi: notları gözden geçirme
    elif ADIM_IZLE in turler:
        if konu_suresi_dk not in (None, "", 0):
            try:
                ogrenme = max(MIN_KONU_ANLATIM_DK, int(round(float(konu_suresi_dk))))
            except (TypeError, ValueError):
                ogrenme = 0
        if not ogrenme:
            # FAZ 5D: TEK süre kaynağı → mikro tohumu, gerçek medyan, varsayılan.
            # Ana konu süresi alt başlıklara bölünmez/kopyalanmaz.
            ogrenme = mikro_anlatim_suresi(
                ogrenci_id, ders, mikro_konu, alt_konu, konu_sureleri
            )
    not_dk = NOT_SURESI_DK if ADIM_NOT in turler else 0

    hiz = ogrenci_soru_hizi(ogrenci_id, ders)
    if hiz:
        katsayi, hiz_kaynagi = hiz, "gercek"
    else:
        katsayi = SORU_SURE_KATSAYISI_DK.get(ders, VARSAYILAN_SORU_SURESI_DK)
        hiz_kaynagi = "varsayilan"
    soru_dk = _soru_bloklari_suresi(soru_bloklari, katsayi)

    ham = ogrenme + not_dk + soru_dk
    kaynak = "varsayilan"
    medyan = konu_suresi_medyani(ogrenci_id, ders, mikro_konu, alt_konu)
    if medyan and ham > 0:
        oran = max(0.5, min(2.0, float(medyan) / float(ham)))
        if ogrenme > 0:
            ogrenme = max(5, _yuvarla5(ogrenme * oran))
        elif soru_dk > 0:
            soru_dk = max(5, _yuvarla5(soru_dk * oran))
        kaynak = "gercek"

    toplam = max(5, ogrenme + not_dk + soru_dk)
    return {
        "ogrenme_dk": ogrenme,
        "not_dk": not_dk,
        "soru_dk": soru_dk,
        "toplam_dk": toplam,
        "soru_katsayisi": round(float(katsayi), 2),
        "kaynak": kaynak,
        "hiz_kaynagi": hiz_kaynagi,
        "gercek_medyan_dk": medyan,
    }


def gorev_suresi_hesapla(gorev, ogrenci_id=None, konu_sureleri=None, alt_sayisi=1,
                         adimlar=None):
    """Görev sözlüğü için planlanan süre (kısayol).

    FAZ 5D: görev sözlüğünde `konu_suresi_dk` varsa (ana konu süresi mikro
    konulara paylaştırılmışsa) o mikro konunun kendi anlatım süresi kullanılır;
    `alt_konu` varsa gerçek süre medyanı mikro konu bazında okunur.
    """
    gorev = gorev or {}
    return sure_plani(
        ders=gorev.get("ders"),
        mikro_konu=gorev.get("mikro_konu"),
        hedef_soru=gorev.get("hedef_soru") or 0,
        alt_sayisi=alt_sayisi,
        adimlar=adimlar,
        konu_sureleri=konu_sureleri,
        ogrenci_id=ogrenci_id,
        pedagoji_turu=gorev.get("pedagoji_turu"),
        makro_konu=gorev.get("makro_konu"),
        gorev_turu=gorev.get("gorev_turu") or "anlatim",
        alt_konu=gorev.get("alt_konu"),
        konu_suresi_dk=gorev.get("konu_suresi_dk"),
    )


def gorev_zenginlestir(gorev, ogrenci_id=None, konu_sureleri=None, alt_sayisi=1):
    """Göreve alt adımları (checklist) ve planlanan süreyi ekler."""
    adimlar = adimlari_uret(gorev)
    plan = gorev_suresi_hesapla(
        gorev,
        ogrenci_id=ogrenci_id,
        konu_sureleri=konu_sureleri,
        alt_sayisi=alt_sayisi,
        adimlar=adimlar,
    )
    yeni = dict(gorev)
    yeni["adimlar"] = adimlar
    yeni["tahmini_sure_dk"] = plan["toplam_dk"]
    yeni["sure_plani"] = plan
    return yeni


def sure_metni(dk):
    """'90' -> '1 sa 30 dk', '45' -> '45 dk'."""
    try:
        dk = int(dk or 0)
    except (TypeError, ValueError):
        return "-"
    if dk <= 0:
        return "-"
    saat, kalan = divmod(dk, 60)
    if saat and kalan:
        return "%d sa %d dk" % (saat, kalan)
    if saat:
        return "%d sa" % saat
    return "%d dk" % kalan

