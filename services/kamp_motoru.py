"""v2.3 "KARAKOÇ YKS KAMP" çekirdek motoru.

Streamlit'ten **bağımsız** çalışır: oturum, makro ünite kilidi, atomik mikro
dilimleme, %75 doğruluk eşiği, yorgunluk merdiveni ve 24 saatlik telafi
entegrasyonunu yönetir. Görünüm katmanı (`views/kamp_kokpiti.py`) yalnızca bu
servisi çağırır.

Katmanlar:
- Saf mantık: `aktif_makro_unite_hesapla`, `mikro_dilimle`, `basari_orani`,
  `yorgunluk_onerisi` (DB/Streamlit gerektirmez, kolay test edilir).
- DB: `init_db`, `oturum_baslat`, `mikro_gorev_baslat`, `mikro_gorev_tamamla`,
  `oturum_bitir`, `son_24s_telafi` (yalnızca `_baglanti` üzerinden okuma/yazma).
"""
import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta

from data import curriculum_meta as cm

VARSAYILAN_DB_YOLU = "yks_veritabani.db"

# ---------------------------------------------------------------------------
# SABİTLER
# ---------------------------------------------------------------------------
# Atomik mikro dilim: 10-15 soru, ~15-25 dk.
KAMP_MAKS_DILIM_SORU = 15
KAMP_MIN_DILIM_SORU = 10
DILIM_DK_MIN = 15
DILIM_DK_MAX = 25
# Doğruluk eşiği: < %75 -> sonraki konuya geçilmez, analiz kartı gelir.
BASARI_ESIGI = 75.0
# Yanlış/boş analizi zorunlu kart süresi.
ANALIZ_DAKIKA = 5
MOLA_DAKIKA = 5
# Telafi penceresi.
TELAFI_PENCERE_SAAT = 24

DURUM_AKTIF = "aktif"
DURUM_TAMAM = "tamamlandi"
DURUM_BOZUK = "bozuldu"
DURUM_TEKRAR = "tekrar_gerek"

# Soğuk uzay temaları (arayüz de bu listeyi kullanır).
TEMA_PALETLERI = {
    "Kozmik Lacivert": "#0A182E",
    "Galaktik Mor": "#160D29",
    "Kuzey Zümrüdü": "#081F1A",
    "Kızıl Tutulma": "#21090E",
    "Siber Siyah-Pembe": "#1F0B19",
}
# v2.4: her temanın 3 duraklı uzay gradyanı (merkez ➔ orta ➔ kenar).
# Varsayılan "Kozmik Lacivert" derin kozmik lacivert / uzay siyahına iner.
TEMA_GRADYANLARI = {
    "Kozmik Lacivert": ("#0A182E", "#050B18", "#020306"),
    "Galaktik Mor": ("#160D29", "#0B0616", "#020208"),
    "Kuzey Zümrüdü": ("#081F1A", "#040F0D", "#010402"),
    "Kızıl Tutulma": ("#21090E", "#100407", "#020103"),
    "Siber Siyah-Pembe": ("#1F0B19", "#0F050C", "#020104"),
}
VARSAYILAN_TEMA = "Kozmik Lacivert"


class KampHatasi(ValueError):
    """Geçersiz kamp işlemi/verisi."""


# ---------------------------------------------------------------------------
# YAPILANDIRMA (testler için enjekte edilebilir)
# ---------------------------------------------------------------------------
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
    """Testlerde duvar saatini sabitlemek için (None = gerçek saat)."""
    global _saat_fonksiyonu
    _saat_fonksiyonu = fonksiyon


def simdi():
    if _saat_fonksiyonu is not None:
        return _saat_fonksiyonu()
    return datetime.now()


def unix_ts():
    """Kronometre için GERÇEK zaman damgası (`time.time()`).

    `saat_fonksiyonu` (duvar saati) bu değeri ETKİLEMEZ; geçen süre sayfa
    yenilense/mobil uykuya girse bile `time.time() - baslangic_ts` ile
    kayıpsız hesaplanır.
    """
    return float(time.time())


def _zaman_yaz(deger):
    if not deger:
        return None
    return deger.strftime("%Y-%m-%d %H:%M:%S")


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
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ---------------------------------------------------------------------------
# ŞEMA
# ---------------------------------------------------------------------------
_SEMA_OTURUM = """
CREATE TABLE IF NOT EXISTS kamp_oturumlari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    baslangic_zamani TEXT,
    bitis_zamani TEXT,
    durum TEXT NOT NULL DEFAULT 'aktif',
    secilen_tema TEXT,
    toplam_sure_sn INTEGER NOT NULL DEFAULT 0,
    tamamlanan_mikro_sayisi INTEGER NOT NULL DEFAULT 0,
    toplam_soru INTEGER NOT NULL DEFAULT 0,
    toplam_dogru INTEGER NOT NULL DEFAULT 0,
    toplam_yanlis INTEGER NOT NULL DEFAULT 0,
    toplam_bos INTEGER NOT NULL DEFAULT 0
)
"""

_SEMA_MIKRO = """
CREATE TABLE IF NOT EXISTS kamp_mikro_kayitlari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    oturum_id INTEGER NOT NULL,
    ogrenci_id INTEGER NOT NULL,
    ders TEXT,
    makro_unite TEXT,
    ana_konu TEXT,
    mikro_konu TEXT,
    dilim_no INTEGER NOT NULL DEFAULT 1,
    toplam_dilim INTEGER NOT NULL DEFAULT 1,
    hedef_soru INTEGER NOT NULL DEFAULT 0,
    yanlis_sayisi INTEGER NOT NULL DEFAULT 0,
    bos_sayisi INTEGER NOT NULL DEFAULT 0,
    basari_orani REAL NOT NULL DEFAULT 0,
    baslangic_ts REAL,
    bitis_ts REAL,
    gecen_sure_sn INTEGER NOT NULL DEFAULT 0,
    durum TEXT NOT NULL DEFAULT 'aktif',
    FOREIGN KEY(oturum_id) REFERENCES kamp_oturumlari(id) ON DELETE CASCADE
)
"""


# v2.5: pedagojik görev bilgisi. EKLEMELİ migrasyon: eski satırlar korunur,
# yalnızca eksik kolonlar eklenir (idempotent).
_EK_KOLONLAR = (
    ("pedagoji_turu", "TEXT"),
    ("gorev_turu", "TEXT"),
    ("adimlar_json", "TEXT"),
    ("soru_gerekli", "INTEGER NOT NULL DEFAULT 1"),
)


def _tablo_kolonlari(conn, tablo):
    """Bir tablodaki kolon adları (tablo yoksa boş küme)."""
    try:
        return {satir[1] for satir in conn.execute("PRAGMA table_info(%s)" % tablo)}
    except sqlite3.Error:
        return set()


def init_db():
    """Kamp tablolarını oluşturur ve yeni kolonları ekler (idempotent).

    Eski `kamp_mikro_kayitlari` satırları silinmez; pedagojik bilgi kolonları
    yoksa `ALTER TABLE ... ADD COLUMN` ile eklenir.
    """
    with _baglanti() as conn:
        with _islem(conn):
            conn.execute(_SEMA_OTURUM)
            conn.execute(_SEMA_MIKRO)
            mevcut = _tablo_kolonlari(conn, "kamp_mikro_kayitlari")
            for ad, tip in _EK_KOLONLAR:
                if ad not in mevcut:
                    conn.execute(
                        "ALTER TABLE kamp_mikro_kayitlari ADD COLUMN %s %s"
                        % (ad, tip)
                    )
    return True


# ===========================================================================
# SAF MANTIK (DB / Streamlit gerektirmez)
# ===========================================================================
def basari_orani(hedef_soru, yanlis_sayisi, bos_sayisi):
    """Doğruluk oranı (%): ((hedef - yanlis - bos) / max(1, hedef)) * 100."""
    try:
        hedef = max(1, int(hedef_soru or 0))
        yanlis = max(0, int(yanlis_sayisi or 0))
        bos = max(0, int(bos_sayisi or 0))
    except (TypeError, ValueError):
        return 0.0
    oran = ((hedef - yanlis - bos) / float(max(1, hedef))) * 100.0
    return max(0.0, min(100.0, oran))


def dilim_sayisi(hedef_soru):
    """Bir mikro konunun hedefini 10-15 soruluk kaç dilime böleceğini döndürür."""
    hedef = max(1, int(hedef_soru or 0))
    if hedef <= KAMP_MAKS_DILIM_SORU:
        return 1
    adet = -(-hedef // KAMP_MAKS_DILIM_SORU)  # ceil(hedef / 15)
    while adet > 1 and (hedef / float(adet)) < KAMP_MIN_DILIM_SORU:
        adet -= 1
    return max(1, adet)


def mikro_dilimle(hedef_soru):
    """Hedef soru sayısını 10-15 soruluk ATOMİK dilimlere böler.

    Dönen: `[{"dilim_no", "toplam_dilim", "hedef_soru"}, ...]`.
    """
    hedef = max(1, int(hedef_soru or 0))
    adet = dilim_sayisi(hedef)
    taban = hedef // adet
    artik = hedef - taban * adet
    dilimler = []
    for i in range(adet):
        boy = taban + (1 if i < artik else 0)
        dilimler.append({
            "dilim_no": i + 1,
            "toplam_dilim": adet,
            "hedef_soru": boy,
        })
    return dilimler


def aktif_makro_unite_hesapla(ders, mufredat, bilinen=(), biten=(),
                              sinif_seviyesi=None, alan=None):
    """Ders için bitmemiş İLK makro üniteyi kilitler (havuz + çekirdek).

    - Sınıf/alan havuzuna göre süzülür (`havuz_suz`).
    - AYT dersleri için `CEKIRDEK_TYT_ONKOSULLAR` kilidi uygulanır (11. sınıf
      istisnası hariç).
    - Aktif makro ünitenin TÜM mikro konuları %100 bitmeden sonraki makroya
      GEÇİLMEZ.

    Dönen: `{"ders", "makro_unite", "mikrolar": [bitmemiş mikro...]}` veya None.
    """
    havuz = cm.havuz_suz(mufredat or {}, sinif_seviyesi, alan)
    makro_dict = havuz.get(ders) or {}
    if not isinstance(makro_dict, dict) or not makro_dict:
        return None
    if str(ders).startswith("AYT"):
        if cm.sinif_seviyesi_sayisi(sinif_seviyesi) != 11 and not cm.cekirdek_acik_mi(
            ders, bilinen, biten
        ):
            return None
    biten_set = {(str(d), str(m)) for d, m in (biten or ())}
    bilinen_set = set(bilinen or ())
    sira = cm.sira_no_haritasi(havuz)
    adaylar = []
    for makro, mikrolar in makro_dict.items():
        if not isinstance(mikrolar, list) or not mikrolar:
            continue
        kalan = [
            m for m in mikrolar
            if m not in bilinen_set and (str(ders), str(m)) not in biten_set
        ]
        if kalan:
            ilk_sira = min(
                (sira.get((ders, m), 10 ** 6) for m in kalan), default=10 ** 6
            )
            adaylar.append((ilk_sira, makro, kalan))
    if not adaylar:
        return None
    adaylar.sort(key=lambda c: c[0])
    ilk = adaylar[0]
    return {"ders": ders, "makro_unite": ilk[1], "mikrolar": ilk[2]}


def sonraki_adim(basari_orani_degeri):
    """%75 eşiğine göre sıradaki adım: 'mikro' (devam) veya 'analiz'."""
    if float(basari_orani_degeri or 0) >= BASARI_ESIGI:
        return "mikro"
    return "analiz"


def yorgunluk_kademeleri():
    """3 kademeli yorgunluk merdiveni (arayüz sırayla sunar)."""
    return [
        {
            "kademe": 1,
            "tur": "sozel",
            "baslik": "Sözel derse geç",
            "mesaj": "Sayısal dersten TYT Türkçe'ye geçerek kampı bozmadan devam et.",
        },
        {
            "kademe": 2,
            "tur": "mola",
            "baslik": "%d dk göz dinlendirme" % MOLA_DAKIKA,
            "mesaj": "Su iç, gözlerini dinlendir; zorunlu ihtiyaç molası.",
        },
        {
            "kademe": 3,
            "tur": "bitir",
            "baslik": "Kampı Kesinlikle Bitir",
            "mesaj": "Odağımı hiç toplayamıyorum — oturumu kapat ve özet fişini gör.",
        },
    ]


# Yorgunluk merdiveni: yalnızca SAYISAL derslerde sözel derse geçiş önerilir.
_SAYISAL_BRANSLAR = {"Matematik", "Geometri", "Fizik", "Kimya"}


def yorgunluk_onerisi(ders):
    """'Yoruldum' tetiklendiğinde ilk öneri.

    Sayısal dersteyse (Mat/Geo/Fiz/Kim) sözel derse geçiş, zaten sözel/ezber
    dersteyse doğrudan %d dk göz dinlendirme molası önerilir.
    """
    if cm.ana_brans(ders) in _SAYISAL_BRANSLAR:
        return {
            "tur": "sozel",
            "oneri": "TYT Türkçe",
            "mesaj": "Kampı bozmadan sözel derse (TYT Türkçe) geç.",
        }
    return {
        "tur": "mola",
        "oneri": None,
        "mesaj": "%d dk göz dinlendirme molası ver." % MOLA_DAKIKA,
    }


# ===========================================================================
# DB: OTURUM / MİKRO GÖREV / ÖZET
# ===========================================================================
def _kayit_getir(kayit_id):
    try:
        with _baglanti() as conn:
            satir = conn.execute(
                "SELECT * FROM kamp_mikro_kayitlari WHERE id = ?", (int(kayit_id),)
            ).fetchone()
    except (sqlite3.Error, TypeError, ValueError):
        return None
    return dict(satir) if satir is not None else None


def oturum_getir(oturum_id):
    try:
        with _baglanti() as conn:
            satir = conn.execute(
                "SELECT * FROM kamp_oturumlari WHERE id = ?", (int(oturum_id),)
            ).fetchone()
    except (sqlite3.Error, TypeError, ValueError):
        return None
    return dict(satir) if satir is not None else None


def oturum_baslat(ogrenci_id, tema=None, an=None):
    """Yeni kamp oturumu açar ('aktif'); oturum sözlüğünü döndürür."""
    oid = int(ogrenci_id)
    secilen = _metin(tema) or VARSAYILAN_TEMA
    zaman = _zaman_yaz(an or simdi())
    with _baglanti() as conn:
        with _islem(conn):
            imlec = conn.execute(
                "INSERT INTO kamp_oturumlari (ogrenci_id, baslangic_zamani,"
                " durum, secilen_tema) VALUES (?, ?, ?, ?)",
                (oid, zaman, DURUM_AKTIF, secilen),
            )
            oturum_id = imlec.lastrowid
    return oturum_getir(oturum_id)


def gorev_plani_uret(ders, makro_unite, mikro_konu, hedef_soru):
    """Kamp mikro görevi için pedagojik çalışma planı üretir.

    Kamp mikro görevleri **ilk kez çalışılan** konulardır. Mevcut
    `task_steps.adimlari_uret` kullanılır; yeni bir sınıflandırma yazılmaz.

    - Ezber dersleri: konu anlatımı + kısa not + aktif hatırlama + düşük soru.
    - Pekiştirme dersleri: konu anlatımı + kısa not + kolay→orta→zor soru.

    Dönen sözlük: `pedagoji_turu`, `gorev_turu`, `adimlar`, `soru_gerekli`,
    `hedef_soru`.
    """
    from data.pedagogy import get_konu_pedagoji_turu
    from services import task_steps

    pedagoji = get_konu_pedagoji_turu(ders)
    hedef = max(0, int(hedef_soru or 0))
    gorev = {
        "ders": ders,
        "makro_konu": makro_unite,
        "mikro_konu": mikro_konu,
        "hedef_soru": hedef,
        "pedagoji_turu": pedagoji,
        # Ezber: zorunlu konu anlatımı + kavram; Pekiştirme: standart öğrenme.
        "gorev_turu": "konu_anlatimi" if pedagoji == "Ezber" else "anlatim",
    }
    try:
        adimlar = task_steps.adimlari_uret(gorev)
    except Exception:  # noqa: BLE001 - plan üretilemezse temel adım
        adimlar = [{"baslik": "Konuyu çalış.", "adim_turu": "genel", "hedef_soru": 0}]
    soru_gerekli = 1 if any(a.get("adim_turu") == "soru" for a in adimlar) else 0
    return {
        "pedagoji_turu": pedagoji,
        "gorev_turu": "konu_ogrenme",
        "adimlar": adimlar,
        "soru_gerekli": soru_gerekli,
        "hedef_soru": hedef,
    }


def tekrar_gorev_plani(ders, makro_unite, mikro_konu):
    """Soru gerektirmeyen tekrar/telafi görevi planı.

    Tekrar görevi soru çözme görevi değildir; öğrenciden yanlış/boş sayısı
    istenmez. Mevcut aralıklı tekrar mantığını bozmadan yalnızca not okuma
    adımı sunulur.
    """
    return {
        "pedagoji_turu": "Tekrar",
        "gorev_turu": "tekrar",
        "adimlar": [
            {
                "baslik": "Özet notlarını oku ve gözden geçir.",
                "adim_turu": "tekrar",
                "hedef_soru": 0,
            }
        ],
        "soru_gerekli": 0,
        "hedef_soru": 0,
    }


def mikro_gorev_baslat(oturum_id, ogrenci_id, ders, makro_unite, ana_konu,
                       mikro_konu, hedef_soru, dilim_no=1, toplam_dilim=1,
                       pedagoji_turu=None, gorev_turu=None, adimlar=None,
                       soru_gerekli=1):
    """Aktif mikro görevi başlatır ve `baslangic_ts = time.time()` damgalar.

    Sayfa yenilense/mobil uykuya girse de geçen süre `time.time()-baslangic_ts`
    ile kayıpsız hesaplanır. Pedagojik görev bilgisi (tür, adımlar, soru
    gerekip gerekmediği) kayıtla birlikte saklanır.
    """
    hedef = max(1, int(hedef_soru or 0))
    ts = unix_ts()
    adimlar_json = None
    if adimlar:
        try:
            adimlar_json = json.dumps(adimlar, ensure_ascii=False)
        except (TypeError, ValueError):
            adimlar_json = None
    with _baglanti() as conn:
        with _islem(conn):
            imlec = conn.execute(
                "INSERT INTO kamp_mikro_kayitlari (oturum_id, ogrenci_id, ders,"
                " makro_unite, ana_konu, mikro_konu, dilim_no, toplam_dilim,"
                " hedef_soru, pedagoji_turu, gorev_turu, adimlar_json,"
                " soru_gerekli, baslangic_ts, durum)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    int(oturum_id), int(ogrenci_id), _metin(ders),
                    _metin(makro_unite), _metin(ana_konu), _metin(mikro_konu),
                    int(dilim_no or 1), int(toplam_dilim or 1), hedef,
                    _metin(pedagoji_turu), _metin(gorev_turu), adimlar_json,
                    1 if soru_gerekli else 0, ts, DURUM_AKTIF,
                ),
            )
            kayit_id = imlec.lastrowid
    return _kayit_getir(kayit_id)


def mikro_gorev_tamamla(kayit_id, yanlis_sayisi=0, bos_sayisi=0):
    """Mikro dilimi kapatır; başarı oranını ve geçen süreyi hesaplar.

    Dönen sözlükte `basari_orani`, `gecen_sure_sn`, `analiz_gerekli`
    (`< %75`) ve `sonraki` ('mikro' | 'analiz') bulunur.
    """
    kayit = _kayit_getir(kayit_id)
    if not kayit:
        raise KampHatasi("Kamp mikro kaydı bulunamadı.")
    # Mükerrer tamamlama koruması: sayfa yenilemesi / çift tıklama aynı
    # kaydı ikinci kez işlemez (toplamlar şişmez).
    if (kayit.get("durum") or DURUM_AKTIF) != DURUM_AKTIF:
        sonuc = dict(kayit)
        oran_onceki = float(kayit.get("basari_orani") or 0)
        sonuc["analiz_gerekli"] = oran_onceki < BASARI_ESIGI
        sonuc["sonraki"] = sonraki_adim(oran_onceki)
        sonuc["mukerrer"] = True
        return sonuc
    ts = unix_ts()
    baslangic = float(kayit.get("baslangic_ts") or ts)
    gecen = int(max(0, ts - baslangic))

    # Soru gerektirmeyen görev (konu/not/tekrar): başarı %100, soru toplamı
    # değişmez; öğrenciden yanlış/boş girişi istenmez. Kolon yoksa (eski kayıt)
    # varsayılan "soru gerekli" kabul edilir.
    _soru_gerekli = kayit.get("soru_gerekli")
    if _soru_gerekli is not None and int(_soru_gerekli) == 0:
        with _baglanti() as conn:
            with _islem(conn):
                conn.execute(
                    "UPDATE kamp_mikro_kayitlari SET yanlis_sayisi = 0,"
                    " bos_sayisi = 0, basari_orani = 100, bitis_ts = ?,"
                    " gecen_sure_sn = ?, durum = ? WHERE id = ?",
                    (ts, gecen, DURUM_TAMAM, int(kayit_id)),
                )
                conn.execute(
                    "UPDATE kamp_oturumlari SET toplam_sure_sn = toplam_sure_sn + ?,"
                    " tamamlanan_mikro_sayisi = tamamlanan_mikro_sayisi + 1"
                    " WHERE id = ?",
                    (gecen, int(kayit.get("oturum_id") or 0)),
                )
        sonuc = _kayit_getir(kayit_id)
        sonuc["analiz_gerekli"] = False
        sonuc["sonraki"] = "mikro"
        return sonuc

    hedef = int(kayit.get("hedef_soru") or 0)
    yanlis = max(0, int(yanlis_sayisi or 0))
    bos = max(0, int(bos_sayisi or 0))
    if yanlis > hedef:
        yanlis = hedef
    if yanlis + bos > hedef:
        bos = max(0, hedef - yanlis)
    oran = basari_orani(hedef, yanlis, bos)
    durum = DURUM_TAMAM if oran >= BASARI_ESIGI else DURUM_TEKRAR
    with _baglanti() as conn:
        with _islem(conn):
            conn.execute(
                "UPDATE kamp_mikro_kayitlari SET yanlis_sayisi = ?,"
                " bos_sayisi = ?, basari_orani = ?, bitis_ts = ?,"
                " gecen_sure_sn = ?, durum = ? WHERE id = ?",
                (yanlis, bos, oran, ts, gecen, durum, int(kayit_id)),
            )
            conn.execute(
                "UPDATE kamp_oturumlari SET toplam_soru = toplam_soru + ?,"
                " toplam_dogru = toplam_dogru + ?,"
                " toplam_yanlis = toplam_yanlis + ?,"
                " toplam_bos = toplam_bos + ?,"
                " toplam_sure_sn = toplam_sure_sn + ?,"
                " tamamlanan_mikro_sayisi = tamamlanan_mikro_sayisi + ?"
                " WHERE id = ?",
                (
                    hedef, max(0, hedef - yanlis - bos), yanlis, bos, gecen,
                    1 if durum == DURUM_TAMAM else 0,
                    int(kayit.get("oturum_id") or 0),
                ),
            )
    sonuc = _kayit_getir(kayit_id)
    sonuc["analiz_gerekli"] = oran < BASARI_ESIGI
    sonuc["sonraki"] = sonraki_adim(oran)
    return sonuc


def oturum_bitir(oturum_id, durum=DURUM_TAMAM, an=None):
    """Oturumu kapatır ('tamamlandi' veya 'bozuldu') ve özet fişini döndürür."""
    if durum not in (DURUM_TAMAM, DURUM_BOZUK):
        durum = DURUM_TAMAM
    zaman = _zaman_yaz(an or simdi())
    with _baglanti() as conn:
        with _islem(conn):
            conn.execute(
                "UPDATE kamp_oturumlari SET durum = ?, bitis_zamani = ? WHERE id = ?",
                (durum, zaman, int(oturum_id)),
            )
    return oturum_ozeti(oturum_id)


def oturum_ozeti(oturum_id):
    """Kamp Özeti Fişi: oturum + mikro kayıtları."""
    oturum = oturum_getir(oturum_id)
    if not oturum:
        return {}
    try:
        with _baglanti() as conn:
            satirlar = conn.execute(
                "SELECT * FROM kamp_mikro_kayitlari WHERE oturum_id = ?"
                " ORDER BY id ASC", (int(oturum_id),),
            ).fetchall()
    except sqlite3.Error:
        satirlar = []
    ozet = dict(oturum)
    ozet["kayitlar"] = [dict(s) for s in satirlar]
    return ozet


def son_24s_telafi(ogrenci_id, ders=None):
    """Son 24 saatte tetiklenmiş aktif telafi adayları.

    - Kamp mikro kayıtları: `basari_orani < %75` ve son 24 saat içinde.
    - Deneme yanlışları: aktif (kapatılmamış) kayıtlar.

    Yeni konuya geçmeden ÖNCE ilk mikro kart olarak telafi görevi sunulur.
    """
    esik_ts = unix_ts() - TELAFI_PENCERE_SAAT * 3600
    sonuc = []
    try:
        with _baglanti() as conn:
            sor = (
                "SELECT * FROM kamp_mikro_kayitlari WHERE ogrenci_id = ?"
                " AND basari_orani < ? AND (bitis_ts IS NULL OR bitis_ts >= ?)"
            )
            params = [int(ogrenci_id), BASARI_ESIGI, esik_ts]
            if ders:
                sor += " AND ders = ?"
                params.append(ders)
            for satir in conn.execute(sor, tuple(params)).fetchall():
                kayit = dict(satir)
                sonuc.append({
                    "tur": "kamp",
                    "ders": kayit.get("ders"),
                    "makro_unite": kayit.get("makro_unite"),
                    "mikro_konu": kayit.get("mikro_konu"),
                    "basari_orani": kayit.get("basari_orani"),
                })
    except sqlite3.Error:
        pass
    try:
        with _baglanti() as conn:
            sor = (
                "SELECT ders, konu_adi FROM deneme_konu_yanlislari"
                " WHERE ogrenci_id = ? AND (durum IS NULL OR durum = 'Aktif')"
            )
            params = [int(ogrenci_id)]
            if ders:
                sor += " AND ders = ?"
                params.append(ders)
            for satir in conn.execute(sor, tuple(params)).fetchall():
                sonuc.append({
                    "tur": "deneme",
                    "ders": satir[0],
                    "mikro_konu": satir[1],
                })
    except sqlite3.Error:
        pass
    return sonuc

