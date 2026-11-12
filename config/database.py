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
