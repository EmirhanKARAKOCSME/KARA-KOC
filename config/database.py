"""Veritabanı bağlantısı ve başlangıç (bootstrap) yönetimi.

Tek sorumluluk: uygulamanın hangi veritabanını kullanacağını belirlemek,
bağlantıyı üretmek ve tüm şema/migration adımlarını **tek bir çağrıyla**
doğru sırayla çalıştırmak (`bootstrap_database`).

Güvenlik kuralları (değiştirilmemeli):
- SQLite **bağlantısı asla cache'lenmez**; her kullanım kendi bağlantısını
  açar/kapatır (`with get_connection() as conn:`).
- Yalnızca "başlangıç tamamlandı" bilgisi cache'lenir; cache anahtarı
  `(mutlak DB yolu, şema sürümü)` çiftidir.
- Bootstrap hata verirse başarı bilgisi cache'e yazılmaz (Streamlit istisna
  durumunda değeri saklamaz).
- Farklı DB yolları birbirinin cache sonucunu kullanamaz; testler geçici DB
  ile gerçek DB'yi karıştırmaz.
- Şema/migration kodu değişince `config.settings.DB_BOOTSTRAP_SURUMU`
  artırılır; bu, cache anahtarını değiştirip başlangıcı yeniden çalıştırır.
"""
import shutil
import sqlite3
from pathlib import Path

import streamlit as st

from config.settings import (
    DB_BOOTSTRAP_SURUMU,
    get_tr_now,
    varsayilan_db_yolu,
)


def db_yolu(yol=None) -> str:
    """Verilen yolu mutlak/normalize eder; verilmezse ayarlardaki yolu döner."""
    if yol:
        return str(Path(yol).expanduser().resolve())
    return varsayilan_db_yolu()


def get_connection(db_path=None):
    """Yeni bir SQLite bağlantısı üretir (foreign_keys açık, WAL modu).

    Bağlantı nesnesi paylaşılmaz/cache'lenmez: çağıran `with` bloğu ile
    kapatır. `db_path` verilmezse uygulamanın varsayılan veritabanı kullanılır.
    """
    conn = sqlite3.connect(db_yolu(db_path), timeout=20, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def log_islem(ogrenci_id, islem, detay):
    """İşlem günlüğü (log yazımı başarısız olsa da uygulama durmaz)."""
    try:
        with get_connection() as c:
            cur = c.cursor()
            simdi_str = get_tr_now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute(
                "INSERT INTO sistem_loglari (ogrenci_id, islem, detay, tarih)"
                " VALUES (?, ?, ?, ?)",
                (ogrenci_id, islem, detay, simdi_str),
            )
            c.commit()
    except Exception:
        pass


# ==============================================================================
# YEDEKLEME / BÜTÜNLÜK / GERİ YÜKLEME (SQLite Backup API)
# ==============================================================================
# Geçerli bir SQLite dosyasının ilk 16 baytı sabittir.
_SQLITE_BASLIK = b"SQLite format 3\x00"


def butunluk_kontrol(db_path=None) -> str:
    """`PRAGMA integrity_check` sonucunu döndürür ('ok' = sağlıklı)."""
    conn = sqlite3.connect(db_yolu(db_path))
    try:
        return str(conn.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        conn.close()


def tablo_sayisi(db_path=None) -> int:
    """Veritabanındaki tablo sayısı (geri yükleme sonrası sağlık kontrolü)."""
    conn = sqlite3.connect(db_yolu(db_path))
    try:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0]
        )
    finally:
        conn.close()


def ogrenci_sayisi(db_path=None) -> int:
    """Kayıtlı öğrenci sayısı (tablo yoksa 0)."""
    conn = sqlite3.connect(db_yolu(db_path))
    try:
        return int(conn.execute("SELECT COUNT(*) FROM ogrenciler").fetchone()[0])
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def yedek_al(hedef_yol, db_path=None) -> str:
    """SQLite Backup API ile TUTARLI bir yedek dosyası üretir.

    Düz dosya kopyası yerine `sqlite3.Connection.backup` kullanılır; WAL
    modundaki commit'ler de yedeğe dâhil edilir ve yedek alınırken okuma
    kilitlenmesi olmaz. Üretilen yedek `integrity_check` ile doğrulanır.
    """
    kaynak = db_yolu(db_path)
    hedef = Path(hedef_yol).expanduser().resolve()
    hedef.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(kaynak)
    try:
        dst = sqlite3.connect(str(hedef))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    kontrol = sqlite3.connect(str(hedef))
    try:
        sonuc = str(kontrol.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        kontrol.close()
    if sonuc != "ok":
        raise sqlite3.DatabaseError("Yedek bütünlük kontrolü başarısız: %s" % sonuc)
    return str(hedef)


def geri_yukle(icerik, db_path=None) -> dict:
    """Yedek baytlarını aktif veritabanına güvenli biçimde geri yükler.

    Adımlar:
    1. SQLite başlığı doğrulanır (geçersiz dosya reddedilir).
    2. Mevcut veritabanı `.bak` güvenlik kopyasına alınır.
    3. WAL/SHM artıkları temizlenir (geri yüklenen dosyayı bozmasın).
    4. Geri yükleme sonrası `integrity_check` yapılır.

    Geri yükleme yalnızca yönetici tarafından çağrılmalıdır.
    """
    if not isinstance(icerik, (bytes, bytearray)):
        raise sqlite3.DatabaseError("Yedek içeriği bayt dizisi olmalı.")
    if not bytes(icerik).startswith(_SQLITE_BASLIK):
        raise sqlite3.DatabaseError("Geçersiz dosya: SQLite veritabanı değil.")

    hedef = Path(db_yolu(db_path))
    guvenlik = None
    if hedef.exists():
        guvenlik = hedef.with_name(hedef.name + ".bak")
        shutil.copy2(hedef, guvenlik)

    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_bytes(bytes(icerik))
    for uzanti in ("-wal", "-shm"):
        artik = hedef.with_name(hedef.name + uzanti)
        if artik.exists():
            try:
                artik.unlink()
            except OSError:
                pass

    sonuc = butunluk_kontrol(db_path)
    if sonuc != "ok":
        raise sqlite3.DatabaseError("Geri yükleme sonrası bütünlük hatası: %s" % sonuc)
    return {
        "butunluk": sonuc,
        "yol": str(hedef),
        "guvenlik_kopyasi": str(guvenlik) if guvenlik else None,
        "tablo_sayisi": tablo_sayisi(db_path),
        "ogrenci_sayisi": ogrenci_sayisi(db_path),
    }


def _veritabani_tablolari(conn):
    """SQLite sistem tabloları hariç tablo adları."""
    return {
        satir[0]
        for satir in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        )
    }


def _tablo_satir_sayisi(conn, tablo):
    """Bir tablodaki satır sayısı (tablo yoksa None)."""
    try:
        return int(conn.execute("SELECT COUNT(*) FROM %s" % tablo).fetchone()[0])
    except sqlite3.Error:
        return None


def yedek_dogrula(yedek_yolu, kaynak_db_path=None) -> dict:
    """Yedeğin açılabildiğini, bütünlüğünü ve kaynakla eşleşmesini doğrular.

    - Bütünlük: `PRAGMA integrity_check` = `ok`.
    - Tablo kümesi: yedek, kaynak DB'deki tüm tabloları içeriyor mu?
    - Öğrenci sayısı: yedek ile kaynak eşit mi?

    Kaynak veritabanı **yalnızca okunur**, değiştirilmez. Gerçek üretim
    verisini test etmek yerine bu fonksiyon geçici kopyalarla kullanılmalıdır.
    """
    yedek = Path(yedek_yolu).expanduser().resolve()
    if not yedek.exists():
        raise FileNotFoundError("Yedek dosyası bulunamadı: %s" % yedek)

    y_conn = sqlite3.connect(str(yedek))
    try:
        butunluk = str(y_conn.execute("PRAGMA integrity_check").fetchone()[0])
        y_tablolar = _veritabani_tablolari(y_conn)
        y_ogrenci = _tablo_satir_sayisi(y_conn, "ogrenciler")
    finally:
        y_conn.close()

    sonuc = {
        "yol": str(yedek),
        "butunluk": butunluk,
        "tablo_sayisi": len(y_tablolar),
        "tablolar": sorted(y_tablolar),
        "ogrenci_sayisi": y_ogrenci,
        "eksik_tablolar": [],
        "kaynak_tablo_sayisi": None,
        "kaynak_ogrenci_sayisi": None,
        "tablolar_esit": None,
        "ogrenci_sayisi_esit": None,
    }

    if kaynak_db_path is not None:
        k_conn = sqlite3.connect(db_yolu(kaynak_db_path))
        try:
            k_tablolar = _veritabani_tablolari(k_conn)
            k_ogrenci = _tablo_satir_sayisi(k_conn, "ogrenciler")
        finally:
            k_conn.close()
        eksik = k_tablolar - y_tablolar
        sonuc["kaynak_tablo_sayisi"] = len(k_tablolar)
        sonuc["kaynak_ogrenci_sayisi"] = k_ogrenci
        sonuc["eksik_tablolar"] = sorted(eksik)
        sonuc["tablolar_esit"] = not eksik
        sonuc["ogrenci_sayisi_esit"] = k_ogrenci == y_ogrenci

    sonuc["saglikli"] = (
        butunluk == "ok"
        and not sonuc["eksik_tablolar"]
        and sonuc["ogrenci_sayisi_esit"] in (None, True)
    )
    return sonuc


@st.cache_resource(show_spinner=False)
def _bootstrap(yol: str, surum: str) -> bool:
    """Şema/migration adımlarını bir kez çalıştırır (DB yolu + sürüm anahtarı).

    `surum` yalnızca cache anahtarının parçasıdır; gövdede kullanılmaz.
    """
    # Yerel import: config.database <-> services döngüsünü önler ve veri
    # modüllerinin import edilmesi migration başlatmaz.
    from services import (
        core_schema,
        gorev_kaynaklari,
        kamp_motoru,
        planner,
        program_motoru,
        programs,
        ranking_engine,
        spaced_repetition,
        study_sessions,
        task_steps,
        topic_progress,
        weekly_report,
        wrong_questions,
    )

    # 1) Bütün servisler AYNI veritabanı dosyasına yönlendirilir.
    servisler = (
        study_sessions,
        programs,
        task_steps,
        planner,
        spaced_repetition,
        wrong_questions,
        gorev_kaynaklari,
        weekly_report,
        ranking_engine,
        kamp_motoru,
    )
    for servis in servisler:
        servis.db_yolu_ayarla(yol)

    # 2) Çekirdek tablolar (ogrenciler, konu durumları, denemeler, loglar).
    core_schema.init_db(yol)

    # 3) Servis şemaları - mevcut FAZ sırası korunur.
    study_sessions.init_db()      # FAZ 4: çalışma oturumları
    programs.init_db()            # FAZ 5A: program sürümleme
    task_steps.init_db()          # FAZ 5B: mikro görev adımları
    planner.init_db()             # FAZ 5C: günlük müsaitlik
    spaced_repetition.init_db()   # FAZ 6A: aralıklı tekrar
    wrong_questions.init_db()     # FAZ 6B: yanlış soru defteri
    gorev_kaynaklari.init_db()    # FAZ 6C: görev <-> kaynak bağları
    weekly_report.init_db()       # FAZ 7: haftalık rapor hedefleri
    ranking_engine.init_db()      # FAZ 8: hedef net tablosu
    kamp_motoru.init_db()         # v2.3: KARAKOÇ YKS KAMP oturum/dilim

    # 4) Program motoru ve alt konu şeması (çekirdek tablolara bağlı).
    program_motoru.init_program_motoru_db(yol)
    topic_progress.init_alt_konu_db(yol)
    return True


def bootstrap_database(db_path=None, schema_version=None) -> bool:
    """Uygulama başlangıcında tek çağrı noktası.

    Aynı süreçte aynı (yol, sürüm) için ikinci çağrı cache'ten döner; her
    rerun'da migration tekrar çalışmaz.
    """
    return _bootstrap(db_yolu(db_path), schema_version or DB_BOOTSTRAP_SURUMU)


def bootstrap_onbellegini_temizle():
    """Başlangıç cache'ini temizler (testler ve sürüm yükseltmeleri için)."""
    _bootstrap.clear()
