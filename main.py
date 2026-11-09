import hashlib
import os
import sqlite3
from datetime import datetime, timedelta, timezone
import pandas as pd
import streamlit as st

# ==============================================================================
# SİSTEM VE ZAMAN DİLİMİ AYARLARI (UTC+3 TÜRKİYE SAATİ)
# ==============================================================================
TR_TZ = timezone(timedelta(hours=3))


def get_tr_now():
  return datetime.now(TR_TZ)


st.set_page_config(
    page_title="KARAKOÇ YKS Akıllı Koçluk Sistemi",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="auto",
)

# ==============================================================================
# GÜVENLİK VE KRİPTOGRAFİ FONKSİYONLARI (PBKDF2-HMAC-SHA256)
# ==============================================================================


def hash_password(password: str) -> str:
  """Şifreyi Rastgele Salt ile PBKDF2-HMAC-SHA256 kullanarak şifreler."""
  salt = os.urandom(16)
  pwd_hash = hashlib.pbkdf2_hmac(
      'sha256', password.encode('utf-8'), salt, 100000
  )
  return salt.hex() + ':' + pwd_hash.hex()


def verify_password(stored_password_hash: str, provided_password: str) -> bool:
  """Girilen şifrenin hash doğrulamasını yapar."""
  if not stored_password_hash or ':' not in stored_password_hash:
    return False
  try:
    salt_hex, hash_hex = stored_password_hash.split(':')
    salt = bytes.fromhex(salt_hex)
    stored_pwd_hash = bytes.fromhex(hash_hex)
    new_pwd_hash = hashlib.pbkdf2_hmac(
        'sha256', provided_password.encode('utf-8'), salt, 100000
    )
    return stored_pwd_hash == new_pwd_hash
  except Exception:
    return False


# ==============================================================================
# RESPONSIVE CSS MİMARİSİ
# ==============================================================================
st.markdown(
    """
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        font-weight: bold;
        height: 3.2em;
        touch-action: manipulation;
    }
    
    .card-mega-buttons div[data-testid="stHorizontalBlock"] {
        gap: 6px !important;
    }
    .card-mega-buttons div[data-testid="column"], 
    .card-mega-buttons div[data-testid="stColumn"] {
        padding: 0px !important;
    }
    
    .card-mega-buttons div[data-testid="stColumn"]:first-child button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        color: #ffffff !important;
        border: none !important;
        font-size: 1.8rem !important;
        font-weight: 900 !important;
        height: 120px !important;
        min-height: 120px !important;
        border-radius: 18px 6px 6px 18px !important;
        box-shadow: 0 8px 20px -4px rgba(16, 185, 129, 0.4) !important;
        width: 100% !important;
    }
    .card-mega-buttons div[data-testid="stColumn"]:first-child button:hover {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
    }
    
    .card-mega-buttons div[data-testid="stColumn"]:last-child button {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
        color: #ffffff !important;
        border: none !important;
        font-size: 1.8rem !important;
        font-weight: 900 !important;
        height: 120px !important;
        min-height: 120px !important;
        border-radius: 6px 18px 18px 6px !important;
        box-shadow: 0 8px 20px -4px rgba(239, 68, 68, 0.4) !important;
        width: 100% !important;
    }
    .card-mega-buttons div[data-testid="stColumn"]:last-child button:hover {
        background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%) !important;
    }

    .fast-pass-top-btn > button {
        background-color: #ffffff !important;
        color: #4b5563 !important;
        border: 2px dashed #9ca3af !important;
        height: 2.6em !important;
        font-size: 0.85rem !important;
        font-weight: bold !important;
        border-radius: 10px !important;
    }
    
    .single-card-container {
        background-color: #ffffff;
        border: 3px solid #6366f1;
        border-radius: 20px;
        padding: 30px 20px;
        box-shadow: 0 12px 30px -8px rgba(99, 102, 241, 0.18);
        margin: 15px 0 10px 0;
        text-align: center;
    }
    .card-ders-title {
        color: #4f46e5;
        font-size: 1.1rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        background-color: #e0e7ff;
        display: inline-block;
        padding: 6px 16px;
        border-radius: 16px;
    }
    .card-konu-title {
        color: #0f172a;
        font-size: 2.2rem;
        font-weight: 900;
        margin: 15px 0;
        line-height: 1.2;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        overflow-x: auto;
        white-space: nowrap;
        flex-wrap: nowrap;
        padding-bottom: 5px;
        -webkit-overflow-scrolling: touch;
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        white-space: nowrap;
        font-size: 0.95rem;
        font-weight: 600;
        border-radius: 8px;
        padding: 0 16px;
    }

    .maarif-rozet {
        background-color: #e3f2fd;
        color: #0d47a1;
        padding: 4px 12px;
        border-radius: 8px;
        font-size: 0.85em;
        font-weight: bold;
    }
    .klasik-rozet {
        background-color: #f3e5f5;
        color: #4a148c;
        padding: 4px 12px;
        border-radius: 8px;
        font-size: 0.85em;
        font-weight: bold;
    }
    .streak-card {
        background-color: #fff3e0;
        border: 2px solid #ffe0b2;
        padding: 12px;
        border-radius: 12px;
        text-align: center;
        font-weight: bold;
        color: #e65100;
        margin-bottom: 12px;
    }
    .siyah-alarm-card {
        background-color: #1a1a1a;
        color: #ff4d4d;
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #ff0000;
        margin-bottom: 10px;
    }
    .deneme-slot-card {
        background-color: #ede7f6;
        color: #4a148c;
        padding: 14px;
        border-radius: 10px;
        border-left: 5px solid #7c4dff;
        margin-bottom: 10px;
        font-weight: bold;
    }
    .turuncu-alarm-card {
        background-color: #fff3e0;
        color: #e65100;
        padding: 14px;
        border-radius: 12px;
        border-left: 5px solid #ff9800;
        margin-bottom: 10px;
    }
    .mavi-alarm-card {
        background-color: #e3f2fd;
        color: #0d47a1;
        padding: 14px;
        border-radius: 12px;
        border-left: 5px solid #2196f3;
        margin-bottom: 10px;
    }
    .pazar-kart {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 14px;
        border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 10px;
    }
    .karakoc-bot-box {
        background-color: #f0f4f8;
        border-left: 5px solid #0288d1;
        padding: 14px;
        border-radius: 10px;
        margin-bottom: 15px;
    }
    .pedagoji-card-pekistirme {
        background-color: #e8f5e9;
        border-left: 5px solid #2e7d32;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    .pedagoji-card-ezber {
        background-color: #fff8e1;
        border-left: 5px solid #f57f17;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    .pedagoji-card-tekrar {
        background-color: #e0f7fa;
        border-left: 5px solid #00acc1;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    .simulator-card {
        background-color: #eef2ff;
        border: 2px solid #c7d2fe;
        padding: 16px;
        border-radius: 12px;
        margin-top: 10px;
    }

    @media screen and (max-width: 768px) {
        .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
        }

        .single-card-container {
            padding: 18px 10px !important;
            border-width: 2px !important;
            border-radius: 16px !important;
        }
        .card-konu-title {
            font-size: 1.4rem !important;
            margin: 10px 0 !important;
        }
        .card-ders-title {
            font-size: 0.8rem !important;
            padding: 4px 8px !important;
        }

        .card-mega-buttons div[data-testid="stColumn"]:first-child button,
        .card-mega-buttons div[data-testid="stColumn"]:last-child button {
            height: 75px !important;
            min-height: 75px !important;
            font-size: 1.05rem !important;
            font-weight: 800 !important;
            border-radius: 12px !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.3rem !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.78rem !important;
        }

        .stTabs [data-baseweb="tab"] {
            font-size: 0.82rem !important;
            padding: 0 10px !important;
            height: 38px !important;
        }
    }

    @media screen and (max-width: 480px) {
        .card-mega-buttons div[data-testid="stColumn"]:first-child button,
        .card-mega-buttons div[data-testid="stColumn"]:last-child button {
            height: 65px !important;
            min-height: 65px !important;
            font-size: 0.9rem !important;
        }
        .card-konu-title {
            font-size: 1.25rem !important;
        }
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ==============================================================================
# VERİTABANI İŞLEMLERİ VE MİGRASYON YÖNETİMİ
# ==============================================================================


def get_connection():
  conn = sqlite3.connect(
      'yks_veritabani.db', timeout=20, check_same_thread=False
  )
  conn.execute('PRAGMA foreign_keys = ON;')
  conn.execute('PRAGMA journal_mode = WAL;')
  return conn


def log_islem(ogrenci_id, islem, detay):
  try:
    with get_connection() as c:
      cur = c.cursor()
      simdi_str = get_tr_now().strftime('%Y-%m-%d %H:%M:%S')
      cur.execute(
          'INSERT INTO sistem_loglari (ogrenci_id, islem, detay, tarih)'
          ' VALUES (?, ?, ?, ?)',
          (ogrenci_id, islem, detay, simdi_str),
      )
      c.commit()
  except Exception:
    pass


def init_db():
  with get_connection() as conn:
    cursor = conn.cursor()

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS ogrenciler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tc_no TEXT UNIQUE,
                kullanici_adi TEXT UNIQUE,
                sifre_hash TEXT,
                ad TEXT,
                hedef_alan TEXT DEFAULT 'Belirtilmedi',
                sinif_seviyesi TEXT DEFAULT 'Belirtilmedi',
                alan_kilitli INTEGER DEFAULT 0,
                son_sinif_atlatma_yili INTEGER DEFAULT 0,
                rol TEXT DEFAULT 'ogrenci',
                hesap_durumu TEXT DEFAULT 'Aktif',
                lisans_bitis TEXT,
                streak_count INTEGER DEFAULT 1,
                son_aktif_tarih TEXT
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS konu_durumlari_detay (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                ders TEXT,
                makro_konu TEXT,
                mikro_konu TEXT,
                durum TEXT DEFAULT 'Başlanmadı',
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)

    cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_konu_detay_unique 
            ON konu_durumlari_detay(ogrenci_id, ders, makro_konu, mikro_konu)
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS deneme_konu_yanlislari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                deneme_kategorisi TEXT DEFAULT 'Genel',
                brans_dersi TEXT,
                deneme_turu TEXT,
                deneme_adi TEXT,
                net_bilgisi REAL,
                ders TEXT,
                makro_konu TEXT,
                konu_adi TEXT,
                yanlis_adedi INTEGER,
                yanlis_nedeni TEXT DEFAULT 'Konu Eksikliği',
                durum TEXT DEFAULT 'Aktif',
                tarih TEXT,
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)

    cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deneme_yanlis_perf 
            ON deneme_konu_yanlislari(ogrenci_id, deneme_turu, durum)
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS calisma_programi_gorevler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                gun TEXT,
                ders TEXT,
                makro_konu TEXT,
                mikro_konu TEXT,
                gorev_tanimi TEXT,
                hedef_soru INTEGER,
                pedagoji_turu TEXT DEFAULT 'Pekiştirme',
                durum INTEGER DEFAULT 0,
                tarih TEXT,
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS pazaryeri_talepler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                ders TEXT,
                konu TEXT,
                alarm_turu TEXT,
                talep_tarihi TEXT,
                durum TEXT DEFAULT 'Talep Alındı',
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS sistem_loglari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                islem TEXT,
                detay TEXT,
                tarih TEXT,
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)

    # Migration
    cursor.execute("PRAGMA table_info(ogrenciler)")
    cols = [column[1] for column in cursor.fetchall()]
    if "kullanici_adi" not in cols:
      cursor.execute(
          "ALTER TABLE ogrenciler ADD COLUMN kullanici_adi TEXT UNIQUE"
      )
    if "sifre_hash" not in cols:
      cursor.execute("ALTER TABLE ogrenciler ADD COLUMN sifre_hash TEXT")
    if "hesap_durumu" not in cols:
      cursor.execute(
          "ALTER TABLE ogrenciler ADD COLUMN hesap_durumu TEXT DEFAULT 'Aktif'"
      )
    if "lisans_bitis" not in cols:
      cursor.execute("ALTER TABLE ogrenciler ADD COLUMN lisans_bitis TEXT")

    # Admin Kullanıcısı Tanımlama
    cursor.execute(
        "SELECT id FROM ogrenciler WHERE kullanici_adi = 'admin' OR tc_no ="
        " '99999999999'"
    )
    admin_user = cursor.fetchone()
    default_admin_pass = hash_password("karakoc123")

    if not admin_user:
      cursor.execute(
          """INSERT INTO ogrenciler 
                   (tc_no, kullanici_adi, sifre_hash, ad, hedef_alan, sinif_seviyesi, alan_kilitli, rol, hesap_durumu) 
                   VALUES ('99999999999', 'admin', ?, 'Emirhan Karakoç (Koç)', 'Yönetim', 'Koç', 1, 'admin', 'Aktif')""",
          (default_admin_pass,),
      )
    else:
      cursor.execute(
          "UPDATE ogrenciler SET kullanici_adi = 'admin', sifre_hash = ?"
          " WHERE id = ?",
          (default_admin_pass, admin_user[0]),
      )

    conn.commit()


init_db()


def update_user_streak(user_id):
  with get_connection() as c:
    cur = c.cursor()
    cur.execute(
        "SELECT streak_count, son_aktif_tarih FROM ogrenciler WHERE id = ?",
        (user_id,),
    )
    res = cur.fetchone()
    if not res:
      return 1

    streak_count, son_aktif_str = res
    bugun_str = get_tr_now().strftime("%Y-%m-%d")

    if not son_aktif_str:
      cur.execute(
          "UPDATE ogrenciler SET streak_count = 1, son_aktif_tarih = ? WHERE"
          " id = ?",
          (bugun_str, user_id),
      )
      c.commit()
      return 1

    son_tarih = datetime.strptime(son_aktif_str, "%Y-%m-%d").date()
    bugun_tarih = get_tr_now().date()
    fark = (bugun_tarih - son_tarih).days

    new_streak = streak_count
    if fark == 1:
      new_streak = streak_count + 1
      cur.execute(
          "UPDATE ogrenciler SET streak_count = ?, son_aktif_tarih = ? WHERE"
          " id = ?",
          (new_streak, bugun_str, user_id),
      )
      c.commit()
    elif fark > 1:
      new_streak = 1
      cur.execute(
          "UPDATE ogrenciler SET streak_count = 1, son_aktif_tarih = ? WHERE"
          " id = ?",
          (bugun_str, user_id),
      )
      c.commit()

    return new_streak


# ==============================================================================
# 100% KAPSAMLI ÖSYM ÇIKMIŞ SORU KREDİLERİ VE YILLIK ORTALAMA SIKLIKLARI
# ==============================================================================
PEKISTIRME_DERSLERI = [
    "Matematik ve Veri",
    "TYT Matematik",
    "AYT Matematik",
    "TYT Geometri",
    "AYT Geometri",
    "TYT Fizik",
    "AYT Fizik",
    "TYT Kimya",
    "AYT Kimya",
    "Gramer ve Kelime",
    "Soru Tipleri",
    "YDT İngilizce",
]

EZBER_DERSLERI = [
    "TYT Biyoloji",
    "AYT Biyoloji",
    "TYT Türkçe",
    "TYT Tarih",
    "AYT Tarih-1",
    "AYT Tarih-2",
    "TYT Coğrafya",
    "AYT Coğrafya-1",
    "AYT Coğrafya-2",
    "TYT Felsefe & Din",
    "AYT Felsefe Grubu",
    "AYT Din Kültürü",
    "AYT Edebiyat",
]

SINIF_SEVIYE_SKORU = {
    "9. Sınıf": 1,
    "10. Sınıf": 2,
    "11. Sınıf": 3,
    "12. Sınıf": 4,
    "Mezun": 4,
}

ON_KOSULLAR = {
    "Anlık Değişim Oranı ve Türev Kuralları": {
        "ders": "AYT Matematik",
        "on_kosul": ["Denklem ve Eşitsizlikler", "Limit ve Süreklilik"],
        "min_sinif": 4,
    },
    "Türevin Geometrik Yorumu ve Maks-Min": {
        "ders": "AYT Matematik",
        "on_kosul": ["Anlık Değişim Oranı ve Türev Kuralları"],
        "min_sinif": 4,
    },
    "Belirsiz İntegral": {
        "ders": "AYT Matematik",
        "on_kosul": ["Anlık Değişim Oranı ve Türev Kuralları"],
        "min_sinif": 4,
    },
    "Belirli İntegral ve Alan Hesabı": {
        "ders": "AYT Matematik",
        "on_kosul": ["Belirsiz İntegral"],
        "min_sinif": 4,
    },
    "Trigonometrik Denklemler": {
        "ders": "AYT Matematik",
        "on_kosul": ["Üçgenler ve Açılar"],
        "min_sinif": 3,
    },
    "Sayı Problemleri": {
        "ders": "TYT Matematik",
        "on_kosul": ["Gerçek Sayılarda Tanımlı Doğrusal Fonksiyonlar"],
        "min_sinif": 1,
    },
    "Elektromanyetizma": {
        "ders": "AYT Fizik",
        "on_kosul": ["Elektrik, Optik ve Dalgalar"],
        "min_sinif": 3,
    },
}

# TÜM MÜFREDAT MAKRO KONULARININ ÖSYM SORU AĞIRLIK KREDİLERİ (100% KAPSAMA)
SORU_AGIRLIKLARI = {
    # TYT TÜRKÇE & MAARİF
    "Paragraf": 99.5,
    "Cümlede Anlam": 16.0,
    "Sözcükte Anlam": 13.5,
    "Dil Bilgisi ve Yapı": 12.5,
    "Yazım Kuralları": 8.0,
    "Noktalama İşaretleri": 7.0,
    "Ses Bilgisi": 3.0,
    "Sözcük Türleri": 12.0,
    "Fiiller ve Cümle": 8.0,
    "1. Ünite: GİRİŞ": 4.0,
    "2. Ünite: HİKAYE (ÖYKÜ)": 6.0,
    "3. Ünite: ŞİİR": 6.0,
    "4. Ünite: MASAL / FABL": 4.0,
    "5. Ünite: ROMAN": 6.0,
    "6. Ünite: TİYATRO": 4.0,
    "7. Ünite: BİYOGRAFİ / OTOBİYOGRAFİ": 4.0,
    "8. Ünite: MEKTUP / E-POSTA": 3.0,
    "9. Ünite: GÜNLÜK / BLOG": 3.0,
    # TYT MATEMATİK & MAARİF
    "Sayı Problemleri": 47.5,
    "Problemler": 47.5,
    "Temel Sayılar ve Cebir": 9.0,
    "Temel Kavramlar": 9.0,
    "Rasyonel Sayılar": 6.5,
    "Sayı Basamakları": 5.5,
    "Denklem ve Eşitsizlikler": 8.0,
    "Kümeler, Mantık ve Olasılık": 12.0,
    "Permütasyon ve Kombinasyon": 9.0,
    "Olasılık": 9.0,
    "Basit Eşitsizlikler": 4.5,
    "Mutlak Değer": 4.5,
    "Üslü Sayılar": 3.5,
    "Köklü Sayılar": 4.0,
    "Denklem Çözme": 2.5,
    "Bölme ve Bölünebilme": 2.5,
    "Fonksiyonlar": 5.0,
    "Veri - İstatistik": 2.5,
    "Nicelikler ve Değişim": 12.0,
    "Veri Analizi ve İstatistik": 8.0,
    "1. Ünite: Sayılar": 8.0,
    "2. Ünite: Nicelikler ve Değişimler": 12.0,
    "3. Ünite: Algoritma ve Bilişim": 6.0,
    "4. Ünite: Geometrik Şekiller": 10.0,
    "5. Ünite: Eşlik ve Benzerlik": 8.0,
    "6. Ünite: İstatistiksel Araştırma": 4.0,
    "7. Ünite: Veriden Olasılığa": 6.0,
    # TYT GEOMETRİ
    "Üçgenler ve Açılar": 14.0,
    "Çokgenler ve Dörtgenler": 14.0,
    "Katı Cisimler": 7.5,
    "Dikdörtgen ve Kare": 7.5,
    "Çokgenler": 4.0,
    "Yamuk": 3.0,
    "Analitik Geometri": 2.0,
    "Çember ve Daire": 1.5,
    "Geometrik Şekiller": 10.0,
    # TYT FİZİK & MAARİF
    "Fizik Bilimi ve Madde": 4.0,
    "Kuvvet, Basınç ve Isı": 6.0,
    "Elektrik, Optik ve Dalgalar": 8.0,
    "Optik": 5.5,
    "Isı, Sıcaklık ve Genleşme": 3.5,
    "Madde ve Özellikleri": 3.0,
    "Hareket ve Kuvvet": 3.5,
    "Elektrik Akımı ve Devreler": 3.5,
    "Elektrostatik": 1.5,
    "Kaldırma Kuvveti": 2.0,
    "Basınç": 1.5,
    "Dalga Harekatı": 2.5,
    "1. Ünite: FİZİK BİLİMİ VE KARİYER": 4.0,
    "2. Ünite: KUVVET VE HAREKET": 6.0,
    "3. Ünite: AKIŞKANLAR": 4.0,
    "4. Ünite: ENERJİ": 4.0,
    # TYT KİMYA & MAARİF
    "Kimya Bilimi ve Atom": 6.0,
    "Hesaplamalar ve Karışımlar": 8.0,
    "Kimya Bilimi": 4.0,
    "Maddenin Halleri": 4.0,
    "Kimyasal Türler Arası Etkileşimler": 4.0,
    "Asitler, Bazlar ve Tuzlar": 3.5,
    "Karışımlar ve Ayırma Yöntemleri": 3.5,
    "Atom Yapısı ve Periyodik Sistem": 4.5,
    "1. Ünite: ETKİLEŞİM": 6.0,
    "2. Ünite: ÇEŞİTLİLİK": 6.0,
    "3. Ünite: SÜRDÜRÜLEBİLİRLİK": 2.0,
    # TYT BİYOLOJİ & MAARİF
    "Hücre ve Canlılık": 6.0,
    "Üreme ve Ekoloji": 6.0,
    "Canlıların Sınıflandırılması": 4.0,
    "Mendelyan Kalıtım": 4.0,
    "Mitoz ve Eşeysiz Üreme": 4.0,
    "Canlıların Temel Bileşenleri": 3.0,
    "Hücre Yapısı ve Organeller": 2.5,
    "Ekosistem Ekolojisi": 2.5,
    "Canlıların Ortak Özellikleri": 1.5,
    "1. Ünite: YAŞAM": 4.0,
    "2. Ünite: ORGANİZASYON": 8.0,
    # TYT TARİH & COĞRAFYA & FELSEFE & DİN
    "Tarih Bilimi ve İlk Uygarlıklar": 4.0,
    "İslam ve Osmanlı Tarihi": 6.0,
    "1. Ünite: GEÇMİŞİN İNŞA SÜRECİNDE TARİH": 4.0,
    "2. Ünite: ESKİ ÇAĞ MEDENİYETLERİ": 6.0,
    "3. Ünite: ORTA ÇAĞ MEDENİYETLERİ": 4.0,
    "Doğal Sistemler": 6.0,
    "Beşeri Sistemler ve Afetler": 4.0,
    "1. Ünite: COĞRAFYANIN DOĞASI": 2.0,
    "2. Ünite: MEKANSAL BİLGİ TEKNOLOJİLERİ": 4.0,
    "3. Ünite: DOĞAL SİSTEMLER VE SÜREÇLER": 6.0,
    "4. Ünite: BEŞERİ SİSTEMLER VE SÜREÇLER": 4.0,
    "5. Ünite: EKONOMİK FAALİYETLER": 2.0,
    "6. Ünite: AFETLER VE SÜRDÜRÜLEBİLİR ÇEVRE": 2.0,
    "7. Ünite: BÖLGELER VE ÜLKELER": 2.0,
    "Felsefe": 4.0,
    "Din Kültürü": 4.0,
    "1. Ünite: ALLAH-İNSAN İLİŞKİSİ": 2.0,
    "2. Ünite: İSLAM'DA İNANÇ ESASLARI": 2.0,
    "3. Ünite: İSLAM'DA İBADETLER": 2.0,
    "4. Ünite: İSLAM'DA AHLAK İLKELERİ": 2.0,
    "5. Ünite: HZ. MUHAMMED (S.A.V)": 2.0,
    # AYT MATEMATİK & GEOMETRİ
    "İleri Cebir ve Fonksiyonlar": 25.0,
    "İleri Cebir": 25.0,
    "Trigonometri, Logaritma ve Diziler": 43.7,
    "Trigonometri": 43.7,
    "Analiz (Limit, Türev, İntegral)": 66.8,
    "Analiz": 66.8,
    "Limit ve Süreklilik": 14.1,
    "Türev Alma Kuralları": 23.1,
    "Belirsiz İntegral": 29.6,
    "Permütasyon- Kombinasyon- Olasılık- Binom": 27.0,
    "Polinomlar": 14.1,
    "Aritmetik ve Geometrik Diziler": 12.9,
    "Karmaşık Sayılar": 5.1,
    "Parabol": 6.4,
    "İkinci Dereceden Denklemler": 10.3,
    "Çember ve Daire": 28.3,
    "Analitik Geometri": 24.4,
    "Katı Cisimler": 19.3,
    "Çember ve Analitik": 35.0,
    "Dönüşüm Geometrisi": 7.7,
    # AYT FEN BİLİMLERİ
    "Mekanik": 20.6,
    "Elektromanyetizma": 21.9,
    "Modern Fizik": 19.3,
    "Düzgün Çembersel Hareket": 10.3,
    "Basit Harmonik Hareket": 9.0,
    "Modern Atom ve Gazlar": 18.0,
    "Termodinamik ve Denge": 25.7,
    "Elektrokimya ve Organik": 16.7,
    "Organik Kimya": 16.7,
    "Sistemler Fizyolojisi": 36.0,
    "Genetik ve Enerji": 18.0,
    "Bitki Biyolojisi ve Ekoloji": 28.3,
    # AYT SOSYAL & YDT
    "Metinler ve Şiir": 38.6,
    "Şiir ve Metinler": 38.6,
    "Dönem Edebiyatları": 27.0,
    "Divan Edebiyatı": 36.0,
    "Cumhuriyet Dönemi Edebiyatı": 27.0,
    "Tarih ve Osmanlı": 43.7,
    "İnkılap Tarihi": 47.6,
    "Milli Mücadele Dönemi": 47.6,
    "İlk Çağ ve Çağdaş Tarih": 30.0,
    "Ekosistem ve Türkiye": 30.9,
    "Mekansal Sentez": 24.4,
    "Felsefe ve Mantık": 20.0,
    "Psikoloji ve Sosyoloji": 20.0,
    "İnanç ve İbadet": 16.0,
    "Gramer ve Kelime": 24.0,
    "Soru Tipleri": 56.0,
}

# TÜM MÜFREDAT MAKRO KONULARININ YILLIK ÖSYM ORTALAMA SORU SIKLIKLARI
YILLIK_ORTALAMA_SORU = {
    "Paragraf": 24.88,
    "Cümlede Anlam": 4.00,
    "Sözcükte Anlam": 3.38,
    "Dil Bilgisi ve Yapı": 3.13,
    "Yazım Kuralları": 2.00,
    "Noktalama İşaretleri": 1.75,
    "Sözcük Türleri": 3.00,
    "Fiiller ve Cümle": 2.00,
    "1. Ünite: GİRİŞ": 1.00,
    "2. Ünite: HİKAYE (ÖYKÜ)": 1.50,
    "3. Ünite: ŞİİR": 1.50,
    "4. Ünite: MASAL / FABL": 1.00,
    "5. Ünite: ROMAN": 1.50,
    "6. Ünite: TİYATRO": 1.00,
    "7. Ünite: BİYOGRAFİ / OTOBİYOGRAFİ": 1.00,
    "8. Ünite: MEKTUP / E-POSTA": 0.75,
    "9. Ünite: GÜNLÜK / BLOG": 0.75,
    "Sayı Problemleri": 11.88,
    "Problemler": 11.88,
    "Temel Sayılar ve Cebir": 2.25,
    "Denklem ve Eşitsizlikler": 2.00,
    "Rasyonel Sayılar": 1.63,
    "Kümeler, Mantık ve Olasılık": 3.00,
    "1. Ünite: Sayılar": 2.00,
    "2. Ünite: Nicelikler ve Değişimler": 3.00,
    "3. Ünite: Algoritma ve Bilişim": 1.50,
    "4. Ünite: Geometrik Şekiller": 2.50,
    "5. Ünite: Eşlik ve Benzerlik": 2.00,
    "6. Ünite: İstatistiksel Araştırma": 1.00,
    "7. Ünite: Veriden Olasılığa": 1.50,
    "Üçgenler ve Açılar": 3.50,
    "Çokgenler ve Dörtgenler": 3.50,
    "Çember ve Daire": 3.14,
    "Analitik Geometri": 2.71,
    "Katı Cisimler": 2.14,
    "Çember ve Analitik": 4.50,
    "Fizik Bilimi ve Madde": 1.00,
    "Kuvvet, Basınç ve Isı": 1.50,
    "Elektrik, Optik ve Dalgalar": 2.00,
    "Optik": 1.38,
    "1. Ünite: FİZİK BİLİMİ VE KARİYER": 1.00,
    "2. Ünite: KUVVET VE HAREKET": 1.50,
    "3. Ünite: AKIŞKANLAR": 1.00,
    "4. Ünite: ENERJİ": 1.00,
    "Kimya Bilimi ve Atom": 1.50,
    "Hesaplamalar ve Karışımlar": 2.00,
    "1. Ünite: ETKİLEŞİM": 1.50,
    "2. Ünite: ÇEŞİTLİLİK": 1.50,
    "3. Ünite: SÜRDÜRÜLEBİLİRLİK": 0.50,
    "Hücre ve Canlılık": 1.50,
    "Üreme ve Ekoloji": 1.50,
    "1. Ünite: YAŞAM": 1.00,
    "2. Ünite: ORGANİZASYON": 2.00,
    "Tarih Bilimi ve İlk Uygarlıklar": 1.00,
    "İslam ve Osmanlı Tarihi": 1.50,
    "1. Ünite: GEÇMİŞİN İNŞA SÜRECİNDE TARİH": 1.00,
    "2. Ünite: ESKİ ÇAĞ MEDENİYETLERİ": 1.50,
    "3. Ünite: ORTA ÇAĞ MEDENİYETLERİ": 1.00,
    "Doğal Sistemler": 1.50,
    "Beşeri Sistemler ve Afetler": 1.00,
    "1. Ünite: COĞRAFYANIN DOĞASI": 0.50,
    "2. Ünite: MEKANSAL BİLGİ TEKNOLOJİLERİ": 1.00,
    "3. Ünite: DOĞAL SİSTEMLER VE SÜREÇLER": 1.50,
    "4. Ünite: BEŞERİ SİSTEMLER VE SÜREÇLER": 1.00,
    "5. Ünite: EKONOMİK FAALİYETLER": 0.50,
    "6. Ünite: AFETLER VE SÜRDÜRÜLEBİLİR ÇEVRE": 0.50,
    "7. Ünite: BÖLGELER VE ÜLKELER": 0.50,
    "Felsefe": 1.00,
    "Din Kültürü": 1.00,
    "1. Ünite: ALLAH-İNSAN İLİŞKİSİ": 0.50,
    "2. Ünite: İSLAM'DA İNANÇ ESASLARI": 0.50,
    "3. Ünite: İSLAM'DA İBADETLER": 0.50,
    "4. Ünite: İSLAM'DA AHLAK İLKELERİ": 0.50,
    "5. Ünite: HZ. MUHAMMED (S.A.V)": 0.50,
    "İleri Cebir ve Fonksiyonlar": 5.50,
    "İleri Cebir": 5.50,
    "Trigonometri, Logaritma ve Diziler": 8.72,
    "Trigonometri": 4.86,
    "Analiz (Limit, Türev, İntegral)": 7.86,
    "Analiz": 7.86,
    "Limit ve Süreklilik": 1.57,
    "Türev Alma Kuralları": 3.00,
    "Belirsiz İntegral": 3.29,
    "Polinomlar": 1.57,
    "Diziler": 1.43,
    "Logaritma": 2.43,
    "Elektromanyetizma": 2.43,
    "Modern Fizik": 2.14,
    "Mekanik": 2.29,
    "Termodinamik ve Denge": 2.86,
    "Modern Atom ve Gazlar": 2.00,
    "Elektrokimya ve Organik": 1.86,
    "Organik Kimya": 1.86,
    "Gazlar": 1.86,
    "Sistemler Fizyolojisi": 4.00,
    "Genetik ve Enerji": 2.00,
    "Bitki Biyolojisi ve Ekoloji": 3.14,
    "Metinler ve Şiir": 4.29,
    "Şiir ve Metinler": 4.29,
    "Dönem Edebiyatları": 3.00,
    "Divan Edebiyatı": 4.00,
    "Cumhuriyet Dönemi Edebiyatı": 3.00,
    "Tarih ve Osmanlı": 4.86,
    "İnkılap Tarihi": 5.29,
    "Milli Mücadele Dönemi": 5.29,
    "İlk Çağ ve Çağdaş Tarih": 3.33,
    "Ekosistem ve Türkiye": 3.43,
    "Mekansal Sentez": 2.71,
    "Felsefe ve Mantık": 2.22,
    "Psikoloji ve Sosyoloji": 2.22,
    "İnanç ve İbadet": 1.78,
    "Gramer ve Kelime": 15.00,
    "Soru Tipleri": 35.00,
}


def get_aylik_mufredat_hedevi(sinif_seviyesi="12. Sınıf"):
  simdi = get_tr_now()
  ay = simdi.month
  ay_adlari = {
      1: "Ocak",
      2: "Şubat",
      3: "Mart",
      4: "Nisan",
      5: "Mayıs",
      6: "Haziran",
      7: "Temmuz",
      8: "Ağustos",
      9: "Eylül",
      10: "Ekim",
      11: "Kasım",
      12: "Aralık",
  }

  if sinif_seviyesi == "Mezun":
    HEDEFLER = {
        8: 10,
        9: 25,
        10: 40,
        11: 55,
        12: 70,
        1: 80,
        2: 90,
        3: 100,
        4: 100,
        5: 100,
        6: 100,
        7: 100,
    }
  elif sinif_seviyesi == "12. Sınıf":
    HEDEFLER = {
        8: 5,
        9: 15,
        10: 30,
        11: 45,
        12: 60,
        1: 75,
        2: 85,
        3: 100,
        4: 100,
        5: 100,
        6: 100,
        7: 100,
    }
  else:
    HEDEFLER = {
        8: 5,
        9: 10,
        10: 20,
        11: 30,
        12: 42,
        1: 54,
        2: 66,
        3: 78,
        4: 88,
        5: 100,
        6: 100,
        7: 100,
    }

  return ay_adlari.get(ay, "Mevcut Ay"), HEDEFLER.get(ay, 30)


# ==============================================================================
# HİYERARŞİK MÜFREDAT VERİ YAPILARI (MAARİF MODELİ & KLASİK YKS)
# ==============================================================================
mufredat_maarif_9 = {
    "Matematik ve Veri": {
        "1. Ünite: Sayılar": [
            "Gerçek Sayıların Üslü ve Köklü Gösterimleri",
            "Gerçek Sayı Aralıkları ile İşlemler",
            "Sayı Kümeleri ve İşlem Özellikleri",
            "İki Kare Farkı ve Tamkare Özdeşlikleri",
        ],
        "2. Ünite: Nicelikler ve Değişimler": [
            "Gerçek Sayılarda Tanımlı Doğrusal Fonksiyonlar ve Mutlak Değer",
            "Fonksiyonların Nitel Özellikleri",
            "Doğrusal Fonksiyonlarla İfade Edilen Denklem ve Eşitsizlikler",
        ],
        "3. Ünite: Algoritma ve Bilişim": [
            "Algoritma Temelli Problemler",
            "Mantık Bağlaçları ve Niceleyiciler",
        ],
        "4. Ünite: Geometrik Şekiller": [
            "Üçgende Açı ve Kenar Özellikleri",
            "Üçgende Açı İlişkileri",
            "Üçgende Kenar İlişkileri",
        ],
        "5. Ünite: Eşlik ve Benzerlik": [
            "Geometrik Şekillerin Dönüşümleri (Yansıma, Öteleme, Dönme)",
            "Üçgenlerde Eşlik ve Benzerlik Koşulları",
        ],
        "6. Ünite: İstatistiksel Araştırma": [
            "Tek Nicel Değişken İçeren İstatistiksel Problem Oluşturma"
        ],
        "7. Ünite: Veriden Olasılığa": [
            "Verileri Toplama ve Analize Hazırlama",
            "Bulgulara Ulaşma ve Yorumlama",
            "İstatistiksel Görsel ve Çıkarımları Değerlendirme",
        ],
    },
    "TYT Kimya": {
        "1. Ünite: ETKİLEŞİM": [
            "Günlük Hayatta Kimya ve Güvenlik",
            "Kimyanın Alt Disiplinleri ve Kariyer",
            "Atom Teorileri ve Elektron Dizilimi",
            "Periyodik Tablo ve Periyodik Özellikler",
        ],
        "2. Ünite: ÇEŞİTLİLİK": [
            "Kimyasal Bağlar (Metalik, İyonik, Kovalent)",
            "Lewis Nokta Yapısı ve Polarlık",
            "Moleküller Arası Etkileşimler",
            "Katılar, Sıvılar ve Özellikleri",
        ],
        "3. Ünite: SÜRDÜRÜLEBİLİRLİK": [
            "Nanoparçacıklar ve Ekolojik Sürdürülebilirlik",
            "Yeşil Kimyanın Atık Önleme İlkesi",
        ],
    },
    "TYT Fizik": {
        "1. Ünite: FİZİK BİLİMİ VE KARİYER": [
            "Fizik Bilimi ve Alt Dalları",
            "Fizik Bilimine Yön Verenler ve Kariyer Keşfi",
        ],
        "2. Ünite: KUVVET VE HAREKET": [
            "Temel ve Türetilmiş Nicelikler",
            "Skaler ve Vektörel Nicelikler",
            "Doğadaki Temel Kuvvetler ve Hareket Türleri",
        ],
        "3. Ünite: AKIŞKANLAR": [
            "Basınç ve Sıvılarda Basınç",
            "Açık Hava Basıncı ve Kaldırma Kuvveti",
            "Bernoulli İlkesi",
        ],
        "4. Ünite: ENERJİ": [
            "Enerji, Isı, Öz Isı ve Sıcaklık İlişkisi",
            "Hâl Değişimi ve Isıl Denge",
            "Isı Aktarım Yolları ve İletim Hızı",
        ],
    },
    "TYT Biyoloji": {
        "1. Ünite: YAŞAM": [
            "Biyolojinin Önemi ve Bilim Etiği",
            "Canlıların Ortak Özellikleri",
            "Sınıflandırma ve Biyoçeşitlilik (3 Domain)",
        ],
        "2. Ünite: ORGANİZASYON": [
            "İnorganik Moleküller (Su ve Mineraller)",
            (
                "Organik Moleküller (Karbonhidrat, Yağ, Protein, Nükleik Asit,"
                " Vitamin)"
            ),
            "Hücre Yapısı, Organeller ve Çekirdek",
            "Hücre Zarından Madde Geçişleri",
            "Hücreden Organ ve Sistem Organizasyonuna",
        ],
    },
    "TYT Türkçe": {
        "1. Ünite: GİRİŞ": [
            "Edebiyatın Sanat ve Bilimle İlişkisi",
            "İletişim Öğeleri ve Göstergeler",
            "Dilin İşlevleri ve Kullanım Türleri",
        ],
        "2. Ünite: HİKAYE (ÖYKÜ)": [
            "Hikaye Türleri ve Gelişimi",
            "Yazım ve Noktalama",
            "İsimler",
        ],
        "3. Ünite: ŞİİR": ["Şiir Bilgisi ve Türleri", "Sıfatlar"],
        "4. Ünite: MASAL / FABL": [
            "Masal ve Fabl Özellikleri",
            "Edat, Bağlaç, Ünlem",
        ],
        "5. Ünite: ROMAN": ["Roman Türleri ve Yapı Unsurları", "Zamirler"],
        "6. Ünite: TİYATRO": [
            "Tiyatro Terimleri ve Geleneksel Türk Tiyatrosu",
            "Zarflar",
        ],
        "7. Ünite: BİYOGRAFİ / OTOBİYOGRAFİ": [
            "Biyografi ve Otobiyografi",
            "CV, Dilekçe ve Tutanak",
            "Fiiller",
        ],
        "8. Ünite: MEKTUP / E-POSTA": ["Mektup Türleri ve E-Posta"],
        "9. Ünite: GÜNLÜK / BLOG": ["Günlük ve Blog"],
    },
    "TYT Tarih": {
        "1. Ünite: GEÇMİŞİN İNŞA SÜRECİNDE TARİH": [
            "Tarih Öğrenmenin Faydaları ve Doğası",
            "Tarihsel Bilgi Üretimi ve Dijitalleşme",
        ],
        "2. Ünite: ESKİ ÇAĞ MEDENİYETLERİ": [
            "Tarım Devriminin Yerleşmeye Etkisi",
            "Eski Çağda Yönetim, Hukuk ve İnançlar",
            "Türklerde Konargöçer Yaşam",
        ],
        "3. Ünite: ORTA ÇAĞ MEDENİYETLERİ": [
            "Orta Çağ Göçleri ve Devlet Yapıları",
            "Orta Çağ Ticaret Yolları ve Bilim Havzaları",
        ],
    },
    "TYT Coğrafya": {
        "1. Ünite: COĞRAFYANIN DOĞASI": [
            "Coğrafya Biliminin Konusu ve Gelişimi"
        ],
        "2. Ünite: MEKANSAL BİLGİ TEKNOLOJİLERİ": [
            "Haritalar ve Türkiye'nin Konumu",
            "Mekânsal Bilgi Teknolojileri Bileşenleri",
        ],
        "3. Ünite: DOĞAL SİSTEMLER VE SÜREÇLER": [
            "Hava Olayları ve İklim Sistemleri",
            "İklim Değişiklikleri",
        ],
        "4. Ünite: BEŞERİ SİSTEMLER VE SÜREÇLER": [
            "Nüfusun Tarihsel Değişimi ve Dağılışı",
            "Demografik Dönüşüm ve Piramitler",
        ],
        "5. Ünite: EKONOMİK FAALİYETLER": [
            "Ekonomik Faaliyetleri Etkileyen Coğrafi Faktörler"
        ],
        "6. Ünite: AFETLER VE SÜRDÜRÜLEBİLİR ÇEVRE": [
            "Afet Türleri ve Bütüncül Afet Yönetimi"
        ],
        "7. Ünite: BÖLGELER VE ÜLKELER": ["Bölge ve Bölge Sınırı Kavramı"],
    },
    "TYT Felsefe & Din": {
        "1. Ünite: ALLAH-İNSAN İLİŞKİSİ": ["İnsanın Yaratılışı, İbadet ve Dua"],
        "2. Ünite: İSLAM'DA İNANÇ ESASLARI": [
            "İman Esasları ve Toplumsal Boyutu"
        ],
        "3. Ünite: İSLAM'DA İBADETLER": ["Temel İbadetler ve İnsan"],
        "4. Ünite: İSLAM'DA AHLAK İLKELERİ": [
            "Ahlakın Temel Unsurları ve Tutumlar"
        ],
        "5. Ünite: HZ. MUHAMMED (S.A.V)": [
            "Hz. Muhammed'in Örnekliği ve Peygamberliği"
        ],
    },
}

mufredat_klasik = {
    "TYT": {
        "TYT Türkçe": {
            "Sözcükte Anlam": [
                "Sözcükte Anlam",
                "Söz Yorumu",
                "Deyim ve Atasözü",
            ],
            "Cümlede Anlam": [
                "Cümlede Anlam İlişkileri",
                "Cümle Yorumu ve Kavramlar",
            ],
            "Paragraf": [
                "Paragrafta Anlatım Teknikleri",
                "Paragrafta Düşünceyi Geliştirme Yolları",
                "Paragrafta Yapı",
                "Paragrafta Konu-Ana Düşünce",
                "Paragrafta Yardımcı Düşünce",
            ],
            "Dil Bilgisi ve Yapı": [
                "Ses Bilgisi",
                "Yazım Kuralları",
                "Noktalama İşaretleri",
                "Sözcükte Yapı ve Ekler",
            ],
            "Sözcük Türleri": [
                "İsimler",
                "Zamirler",
                "Sıfatlar",
                "Zarflar",
                "Edat – Bağlaç – Ünlem",
            ],
            "Fiiller ve Cümle": [
                "Fiilde Anlam",
                "Ek Fiil",
                "Fiilimsi",
                "Fiilde Çatı",
                "Cümlenin Ögeleri",
                "Anlatım Bozukluğu",
            ],
        },
        "TYT Matematik": {
            "Temel Sayılar ve Cebir": [
                "Temel Kavramlar",
                "Sayı Basamakları",
                "Bölme ve Bölünebilme",
                "EBOB – EKOK",
                "Rasyonel Sayılar",
            ],
            "Denklem ve Eşitsizlikler": [
                "Basit Eşitsizlikler",
                "Mutlak Değer",
                "Üslü Sayılar",
                "Köklü Sayılar",
                "Çarpanlara Ayırma",
                "Oran Orantı",
                "Denklem Çözme",
            ],
            "Problemler": [
                "Sayı Problemleri",
                "Kesir Problemleri",
                "Yaş Problemleri",
                "Hareket Hız Problemleri",
                "İşçi Emek Problemleri",
                "Yüzde-Kâr-Zarar Problemleri",
                "Karışım Problemleri",
                "Grafik Problemleri",
            ],
            "Kümeler, Mantık ve Olasılık": [
                "Kümeler – Kartezyen Çarpım",
                "Mantık",
                "Fonksiyonlar",
                "Permütasyon ve Kombinasyon",
                "Olasılık",
                "Veri – İstatistik",
            ],
        },
        "TYT Geometri": {
            "Üçgenler ve Açılar": [
                "Temel Kavramlar ve Doğruda Açılar",
                "Üçgende Açılar",
                "Dik Üçgen ve Pisagor",
                "İkizkenar ve Eşkenar Üçgen",
                "Açıortay ve Kenarortay",
                "Üçgende Eşlik ve Benzerlik",
                "Üçgende Alan",
            ],
            "Çokgenler ve Dörtgenler": [
                "Çokgenler",
                "Dörtgenler ve Özel Dörtgenler",
                "Deltoid",
                "Paralelkenar ve Eşkenar Dörtgen",
                "Dikdörtgen ve Kare",
                "Yamuk",
            ],
        },
        "TYT Fizik": {
            "Fizik Bilimi ve Madde": [
                "Fizik Bilimine Giriş",
                "Madde ve Özellikleri",
                "Dayanıklılık ve Akışkanlar",
            ],
            "Kuvvet, Basınç ve Isı": [
                "Hareket ve Kuvvet",
                "Newton'un Hareket Yasaları",
                "Basınç",
                "Sıvıların Kaldırma Kuvveti",
                "Isı, Sıcaklık ve Genleşme",
            ],
            "Elektrik, Optik ve Dalgalar": [
                "Elektrostatik",
                "Elektrik Akımı ve Devreler",
                "Mıknatıslar ve Manyetik Alan",
                "Aydınlanma ve Aynalar",
                "Kırılma ve Mercekler",
                "Dalga Harekatı",
            ],
        },
        "TYT Kimya": {
            "Kimya Bilimi ve Atom": [
                "Kimya Bilimi",
                "Atom Yapısı ve Periyodik Sistem",
                "Kimyasal Türler Arası Etkileşimler",
                "Maddenin Halleri",
            ],
            "Hesaplamalar ve Karışımlar": [
                "Kimyanın Temel Kanunları",
                "Mol Kavramı ve Kimyasal Hesaplamalar",
                "Karışımlar ve Ayırma Yöntemleri",
                "Asitler, Bazlar ve Tuzlar",
            ],
        },
        "TYT Biyoloji": {
            "Hücre ve Canlılık": [
                "Canlıların Ortak Özellikleri",
                "Canlıların Temel Bileşenleri",
                "Hücre Yapısı ve Organeller",
                "Hücre Zarından Madde Geçişleri",
                "Canlıların Sınıflandırılması",
            ],
            "Üreme ve Ekoloji": [
                "Mitoz ve Eşeysiz Üreme",
                "Mayoz ve Eşeyli Üreme",
                "Mendelyan Kalıtım",
                "Ekosistem Ekolojisi",
            ],
        },
        "TYT Tarih": {
            "Tarih Bilimi ve İlk Uygarlıklar": [
                "Tarih ve Zaman",
                "İnsanlığın İlk Dönemleri",
                "İlk ve Orta Çağlarda Türk Dünyası",
            ],
            "İslam ve Osmanlı Tarihi": [
                "İslam Medeniyetinin Doğuşu",
                "Türk-İslam Devletleri",
                "Beylikten Devlete Osmanlı Siyareti",
                "Milli Mücadele ve Atatürkçülük",
            ],
        },
        "TYT Coğrafya": {
            "Doğal Sistemler": [
                "Doğa ve İnsan",
                "Dünya’nın Şekli ve Hareketleri",
                "Coğrafi Konum",
                "Harita Bilgisi",
                "İklim Bilgisi",
            ],
            "Beşeri Sistemler ve Afetler": [
                "Nüfus ve Yerleşme",
                "Türkiye’nin Yer Şekilleri",
                "Ekonomik Faaliyetler",
                "Doğal Afetler ve Çevre",
            ],
        },
        "TYT Felsefe & Din": {
            "Felsefe": [
                "Felsefenin Konusu",
                "Bilgi Felsefesi",
                "Varlık Felsefesi",
                "Ahlak Felsefesi",
            ],
            "Din Kültürü": [
                "Bilgi ve İnanç",
                "İslam ve İbadet",
                "Ahlak ve Değerler",
            ],
        },
    },
    "AYT": {
        "Sayısal": {
            "AYT Matematik": {
                "İleri Cebir ve Fonksiyonlar": [
                    "Polinomlar ve Çarpanlara Ayırma",
                    "İkinci Dereceden Denklemler",
                    "Karmaşık Sayılar",
                    "Parabol",
                    "İkinci Dereceden Eşitsizlik Sistemleri",
                ],
                "Trigonometri, Logaritma ve Diziler": [
                    "Yönlü Açılar ve Trigonometrik Oranlar",
                    "Trigonometrik Denklemler",
                    "Üstel ve Logaritmik Fonksiyonlar",
                    "Aritmetik ve Geometrik Diziler",
                ],
                "Analiz (Limit, Türev, İntegral)": [
                    "Limit ve Süreklilik",
                    "Türev Alma Kuralları",
                    "Türevin Geometrik Yorumu ve Maks-Min",
                    "Belirsiz İntegral",
                    "Belirli İntegral ve Alan Hesabı",
                ],
            },
            "AYT Geometri": {
                "Çember ve Daire": [
                    "Çemberde Açı",
                    "Çemberde Uzunluk",
                    "Dairede Çevre ve Alan",
                ],
                "Analitik Geometri": [
                    "Noktanın Analitik İncelemesi",
                    "Doğrunun Analitik İncelemesi",
                    "Dönüşüm Geometrisi",
                    "Çemberin Analitik İncelemesi",
                ],
                "Katı Cisimler": [
                    "Prizmalar ve Küp",
                    "Silindir ve Koni",
                    "Piramit ve Küre",
                ],
            },
            "AYT Fizik": {
                "Mekanik": [
                    "Vektörler ve Bağıl Hareket",
                    "Newton'ın Hareket Yasaları",
                    "Atışlar",
                    "İş-Enerji Korunumu",
                    "İtme ve Çizgisel Momentum",
                    "Tork ve Dönme Dengesi",
                ],
                "Elektromanyetizma": [
                    "Elektriksel Kuvvet ve Elektrik Alan",
                    "Elektriksel Potansiyel",
                    "Düzgün Elektrik Alan ve Sığaçlar",
                    "Manyetik Alan ve Manyetik Kuvvet",
                    "İndüksiyon ve Alternatif Akım",
                ],
                "Modern Fizik": [
                    "Düzgün Çembersel Hareket",
                    "Açısal Momentum ve Kepler",
                    "Basit Harmonik Hareket",
                    "Dalga Mekaniği ve Doppler",
                    "Atom Fiziği ve Radyoaktivite",
                    "Fotoelektrik Olay",
                ],
            },
            "AYT Kimya": {
                "Modern Atom ve Gazlar": [
                    "Modern Atom Teorisi",
                    "Gazlar ve Ideal Gaz Yasası",
                    "Sıvı Çözeltiler ve Çözünürlük",
                ],
                "Termodinamik ve Denge": [
                    "Kimyasal Tepkimelerde Enerji",
                    "Tepkime Hızları",
                    "Kimyasal Denge",
                    "Asit-Baz Dengesi",
                    "Çözünürlük Dengesi (KÇÇ)",
                ],
                "Elektrokimya ve Organik": [
                    "Redoks ve Elektrokimya",
                    "Karbon Kimyasına Giriş",
                    "Organik Bileşikler",
                ],
            },
            "AYT Biyoloji": {
                "Sistemler Fizyolojisi": [
                    "Sinir Sistemi ve Duyu Organları",
                    "Endokrin Sistem",
                    "Destek ve Hareket Sistemi",
                    "Sindirim Sistemi",
                    "Dolaşım ve Bağışıklık Sistemi",
                    "Solunum Sistemi",
                    "Üriner Sistem",
                ],
                "Genetik ve Enerji": [
                    "Genden Proteine (Protein Sentezi)",
                    "Fotosentez ve Kemosentez",
                    "Hücresel Solunum",
                ],
                "Bitki Biyolojisi ve Ekoloji": [
                    "Bitkisel Dokular ve Organlar",
                    "Bitkilerde Büyüme ve Hareket",
                    "Komünite ve Popülasyon Ekolojisi",
                ],
            },
        },
        "Eşit Ağırlık": {
            "AYT Matematik": {
                "İleri Cebir": [
                    "Polinomlar ve Parabol",
                    "İkinci Dereceden Eşitsizlikler",
                    "Trigonometri",
                    "Logaritma ve Diziler",
                    "Limit, Türev ve İntegral",
                ],
            },
            "AYT Geometri": {
                "Çember ve Analitik": [
                    "Çemberde Açı ve Uzunluk",
                    "Analitik Geometri",
                    "Katı Cisimler",
                ],
            },
            "AYT Edebiyat": {
                "Metinler ve Şiir": [
                    "Şiir Bilgisi ve Edebi Sanatlar",
                    "İslamiyet Öncesi ve Geçiş Dönemi Türk Edebiyatı",
                    "Halk Edebiyatı",
                    "Divan Edebiyatı",
                ],
                "Dönem Edebiyatları": [
                    "Tanzimat ve Servet-i Fünun Edebiyatı",
                    "Milli Edebiyat Dönemi",
                    "Cumhuriyet Dönemi Edebiyatı",
                ],
            },
            "AYT Tarih-1": {
                "Tarih ve Osmanlı": [
                    "İlk Türk Devletleri ve İslam Medeniyeti",
                    "Beylikten Devlete Osmanlı",
                    "Dünya Gücü Osmanlı",
                ],
                "İnkılap Tarihi": [
                    "XX. Yüzyıl Başlarında Osmanlı",
                    "Milli Mücadele Dönemi",
                    "Atatürk İlkeleri ve İnkılapları",
                ],
            },
            "AYT Coğrafya-1": {
                "Ekosistem ve Türkiye": [
                    "Ekosistem ve Biyoçeşitlilik",
                    "Türkiye Ekonomisi ve Bölgeler",
                    "Küresel Ticaret ve Çevre",
                ],
            },
        },
        "Sözel": {
            "AYT Edebiyat": {
                "Şiir ve Metinler": [
                    "Edebi Sanatlar",
                    "Divan Edebiyatı",
                    "Halk Edebiyatı",
                    "Cumhuriyet Dönemi",
                ],
            },
            "AYT Tarih-2": {
                "İlk Çağ ve Çağdaş Tarih": [
                    "İlk Uygarlıklar",
                    "Osmanlı Merkez Teşkilatı",
                    "İki Savaş Arası Dönem",
                    "Soğuk Savaş ve XXI. Yüzyıl",
                ],
            },
            "AYT Coğrafya-2": {
                "Mekansal Sentez": [
                    "Türkiye'nin İklimi ve Yeryüzü Şekilleri",
                    "Küresel Örgütler ve Afetler",
                ],
            },
            "AYT Felsefe Grubu": {
                "Felsefe ve Mantık": [
                    "Felsefi Düşünce",
                    "Klasik Mantık ve Mantık-Dil",
                    "Sembolik Mantık",
                ],
                "Psikoloji ve Sosyoloji": [
                    "Psikolojinin Temel Süreçleri",
                    "Öğrenme ve Bellek",
                    "Sosyolojiye Giriş ve Toplumsal Yapı",
                ],
            },
            "AYT Din Kültürü": {
                "İnanç ve İbadet": [
                    "Allah İnsan İlişkisi",
                    "Kur'an Kavramları",
                    "İslam Düşüncesinde Tasavvufi Yorumlar",
                ],
            },
        },
    },
    "YDT (Dil)": {
        "YDT İngilizce": {
            "Gramer ve Kelime": [
                "Vocabulary & Collocations",
                "Tenses & Modals",
                "Clauses & Conjunctions",
            ],
            "Soru Tipleri": [
                "Cloze Test & Cümle Tamamlama",
                "İngilizce-Türkçe Çeviri",
                "Paragraf Okuma ve Anlama",
                "Diyalog & Anlamı Bozan Cümle",
            ],
        }
    },
}

# ==============================================================================
# ONLINE KULLANICI GİRİŞİ VE OTURUM YÖNETİMİ
# ==============================================================================
if "active_user" not in st.session_state:
  st.session_state.active_user = None

if not st.session_state.active_user:
  st.title("🎯 KARAKOÇ YKS Akıllı Koçluk Sistemine Giriş")
  st.markdown(
      "Koçunuz tarafından size verilen **Kullanıcı Adı / T.C. No** ve"
      " **Şifreniz** ile giriş yapın."
  )

  with st.form("login_form"):
    user_input = st.text_input(
        "Kullanıcı Adınız veya T.C. Kimlik No:",
        placeholder="Örn: emirhan_k veya 11 Haneli TC",
    )
    pass_input = st.text_input(
        "Şifreniz:", type="password", placeholder="••••••••"
    )
    submit_btn = st.form_submit_button(
        "Sisteme Güvenli Giriş Yap", type="primary"
    )

    if submit_btn:
      if not user_input.strip() or not pass_input.strip():
        st.error("Lütfen kullanıcı adınızı/TC numaranızı ve şifrenizi giriniz!")
      else:
        with get_connection() as conn:
          cursor = conn.cursor()
          cursor.execute(
              """SELECT id, tc_no, kullanici_adi, sifre_hash, ad, hedef_alan, sinif_seviyesi, 
                                   alan_kilitli, rol, hesap_durumu, lisans_bitis, streak_count 
                            FROM ogrenciler 
                            WHERE kullanici_adi = ? OR tc_no = ?""",
              (user_input.strip(), user_input.strip()),
          )
          user = cursor.fetchone()

        if user:
          stored_hash = user[3]
          hesap_durumu = user[9]
          lisans_bitis_str = user[10]

          if hesap_durumu != "Aktif":
            st.error(
                "🚫 Hesabınız pasife alınmıştır! Lütfen koçunuzla iletişime"
                " geçin."
            )
          elif (
              lisans_bitis_str
              and datetime.strptime(lisans_bitis_str, "%Y-%m-%d").date()
              < get_tr_now().date()
          ):
            st.error(
                "⏳ Üyelik/Lisans süreniz dolmuştur! Lütfen koçunuzla"
                " iletişime geçin."
            )
          elif stored_hash and verify_password(
              stored_hash, pass_input.strip()
          ):
            st.session_state.active_user = {
                "id": user[0],
                "tc_no": user[1],
                "kullanici_adi": user[2],
                "ad": user[4],
                "hedef_alan": user[5],
                "sinif_seviyesi": user[6],
                "alan_kilitli": user[7],
                "rol": user[8],
                "streak_count": user[11],
            }
            log_islem(
                user[0], "LOGIN", "Kullanıcı başarıyla giriş yaptı."
            )
            st.success(f"Giriş başarılı! Hoş geldin, {user[4]}.")
            st.rerun()
          else:
            st.error("❌ Hatalı şifre veya kullanıcı adı!")
        else:
          st.error(
              "❌ Sistemde bu kullanıcı adına veya T.C. numarasına ait bir"
              " üyelik bulunamadı."
          )
  st.stop()

current_user = st.session_state.active_user
current_user["streak_count"] = update_user_streak(current_user["id"])


def build_student_curriculum(sinif, alan):
  if sinif == "9. Sınıf":
    return mufredat_maarif_9
  elif sinif == "10. Sınıf":
    return mufredat_klasik.get("TYT", {})
  else:
    birlesik_mufredat = {}
    tyt_dict = mufredat_klasik.get("TYT", {})
    for ders_k, ders_v in tyt_dict.items():
      clean_key = (
          ders_k if ders_k.startswith("TYT") else f"TYT {ders_k}"
      )
      birlesik_mufredat[clean_key] = ders_v

    if alan in mufredat_klasik.get("AYT", {}):
      ayt_alan_dict = mufredat_klasik["AYT"][alan]
      for ders_k, ders_v in ayt_alan_dict.items():
        birlesik_mufredat[ders_k] = ders_v

    if alan == "Dil":
      ydt_dict = mufredat_klasik.get("YDT (Dil)", {})
      for ders_k, ders_v in ydt_dict.items():
        birlesik_mufredat[ders_k] = ders_v

    return birlesik_mufredat


aktif_mufredat_hiyerarsisi = build_student_curriculum(
    current_user["sinif_seviyesi"], current_user["hedef_alan"]
)


def hesapla_tyt_ayt_tamamlanma(ogrenci_id, aktif_mufredat):
  with get_connection() as c:
    df_bilinen = pd.read_sql_query(
        "SELECT ders, mikro_konu FROM konu_durumlari_detay WHERE ogrenci_id = ?"
        " AND durum = 'Biliyorum'",
        c,
        params=(ogrenci_id,),
    )
  bilinen_pairs = set(zip(df_bilinen["ders"], df_bilinen["mikro_konu"]))

  tyt_toplam, tyt_biten = 0.0, 0.0
  ayt_toplam, ayt_biten = 0.0, 0.0

  for d_k, d_v in aktif_mufredat.items():
    is_tyt = d_k.startswith("TYT") or d_k in [
        "Matematik ve Veri",
        "Gramer ve Kelime",
        "Soru Tipleri",
    ]
    if isinstance(d_v, dict):
      for m_k, m_v in d_v.items():
        if isinstance(m_v, list) and len(m_v) > 0:
          makro_kredi = SORU_AGIRLIKLARI.get(m_k, 10.0)
          mikro_kredi = makro_kredi / len(m_v)

          for mik in m_v:
            if is_tyt:
              tyt_toplam += mikro_kredi
              if (d_k, mik) in bilinen_pairs:
                tyt_biten += mikro_kredi
            else:
              ayt_toplam += mikro_kredi
              if (d_k, mik) in bilinen_pairs:
                ayt_biten += mikro_kredi

  tyt_oran = (
      round((tyt_biten / tyt_toplam) * 100.0, 1) if tyt_toplam > 0 else 0.0
  )
  ayt_oran = (
      round((ayt_biten / ayt_toplam) * 100.0, 1) if ayt_toplam > 0 else 0.0
  )
  genel_oran = (
      round(((tyt_biten + ayt_biten) / (tyt_toplam + ayt_toplam)) * 100.0, 1)
      if (tyt_toplam + ayt_toplam) > 0
      else 0.0
  )

  return tyt_oran, ayt_oran, genel_oran


def hesapla_tum_alarmlar(ogrenci_id, mevcut_sinif, aktif_mufredat):
  alarmlar = {"siyah": [], "kirmizi": [], "mor": [], "turuncu": [], "mavi": []}
  ogrenci_skor = SINIF_SEVIYE_SKORU.get(mevcut_sinif, 4)

  with get_connection() as c:
    df_bilinen = pd.read_sql_query(
        "SELECT ders, makro_konu, mikro_konu FROM konu_durumlari_detay WHERE"
        " ogrenci_id = ? AND durum = 'Biliyorum'",
        c,
        params=(ogrenci_id,),
    )
    df_yanlislar = pd.read_sql_query(
        "SELECT id, ders, makro_konu, konu_adi, yanlis_adedi, yanlis_nedeni FROM"
        " deneme_konu_yanlislari WHERE ogrenci_id = ? AND (durum IS NULL OR"
        " durum = 'Aktif') ORDER BY id ASC",
        c,
        params=(ogrenci_id,),
    )
    df_gorevler = pd.read_sql_query(
        "SELECT makro_konu, mikro_konu FROM calisma_programi_gorevler WHERE"
        " ogrenci_id = ?",
        c,
        params=(ogrenci_id,),
    )

  bilinen_pairs = set(zip(df_bilinen["ders"], df_bilinen["mikro_konu"]))
  bilinen_mikro_set = set(df_bilinen["mikro_konu"].tolist())
  bilinen_makro_set = set(df_bilinen["makro_konu"].tolist())
  bilinen_dersler_set = set(df_bilinen["ders"].tolist())

  yanlis_konular_set = (
      set(df_yanlislar["konu_adi"].tolist())
      if not df_yanlislar.empty
      else set()
  )
  aktif_gorevler_set = (
      set(df_gorevler["mikro_konu"].tolist()).union(
          set(df_gorevler["makro_konu"].tolist())
      )
      if not df_gorevler.empty
      else set()
  )

  if not df_yanlislar.empty:
    grouped = df_yanlislar.groupby(["ders", "konu_adi"])
    for (ders, konu), group in grouped:
      yanlis_ids = group["id"].tolist()
      yanlis_listesi = group["yanlis_adedi"].tolist()
      son_yanlis = yanlis_listesi[-1]
      son_neden = group["yanlis_nedeni"].iloc[-1]

      if (
          len(yanlis_listesi) >= 3
          and yanlis_listesi[-3] < yanlis_listesi[-2] < yanlis_listesi[-1]
      ):
        alarmlar["siyah"].append({
            "id_list": yanlis_ids,
            "ders": ders,
            "konu": konu,
            "detay": (
                "Yanlış sayısı ivmelenerek arttı!"
                f" ({yanlis_listesi[-3]} ➔ {yanlis_listesi[-2]} ➔"
                f" {yanlis_listesi[-1]})"
            ),
            "aksiyon": (
                "🔴 ACİL: Birebir 1'e 1 Özel Ders Seansı almalısınız! (Sistem"
                " Öğretmen İnisiyatifine Yönlendirir)"
            ),
            "neden": son_neden,
        })
      elif len(yanlis_listesi) >= 3 and all(y > 0 for y in yanlis_listesi[-3:]):
        alarmlar["mor"].append({
            "id_list": yanlis_ids,
            "ders": ders,
            "konu": konu,
            "detay": (
                "Son 3 denemedir bu konudan kronik (stabil) yanlış yapılıyor."
            ),
            "aksiyon": (
                "🟣 Aksiyon: Birebir Özel Ders Destek Talebi Açıldı (P_score"
                " Katsayısı: 0.1)."
            ),
            "neden": son_neden,
        })

      if (ders, konu) in bilinen_pairs:
        alarmlar["kirmizi"].append({
            "id_list": yanlis_ids,
            "ders": ders,
            "konu": konu,
            "detay": (
                f"'Biliyorum' dediniz ancak denemede {son_yanlis} yanlış"
                " yapıldı!"
            ),
            "aksiyon": (
                "🔴 Aksiyon: Özel Ders Pazaryerinden seans talep"
                " edebilirsiniz."
            ),
            "neden": son_neden,
        })

  for hedef_konu, kural in ON_KOSULLAR.items():
    min_sinif = kural["min_sinif"]
    on_kosul_listesi = kural["on_kosul"]
    hedef_ders = kural.get("ders", "")

    if (
        hedef_konu in bilinen_mikro_set
        or hedef_konu in bilinen_makro_set
    ):
      continue

    if ogrenci_skor >= min_sinif:
      ders_aktif_mi = hedef_ders in bilinen_dersler_set or any(
          d == hedef_ders for d in df_yanlislar["ders"].tolist()
      )
      baglam_tetiklendi = ders_aktif_mi and (
          hedef_konu in yanlis_konular_set
          or hedef_konu in aktif_gorevler_set
          or len(bilinen_makro_set) >= 3
      )

      if baglam_tetiklendi:
        for ok in on_kosul_listesi:
          if ok not in bilinen_mikro_set and ok not in bilinen_makro_set:
            alarmlar["turuncu"].append({
                "ders": (
                    hedef_ders if hedef_ders else "İleri Seviye Odak Konusu"
                ),
                "konu": f"{hedef_konu} (Eksik Ön Koşul: {ok})",
                "detay": (
                    f"Hedeflenen '{hedef_konu}' konusuna başlanabilmesi için"
                    f" temel ön koşul olan **'{ok}'** konusunun tamamlanması"
                    " gerekmektedir."
                ),
                "aksiyon": (
                    f"📙 Aksiyon: Ön koşul konusu '{ok}' için konu çalışması"
                    " başlatın."
                ),
                "neden": "Ön Koşul Tıkanması",
            })

  tyt_o, ayt_o, gercek_tamamlanma_orani = hesapla_tyt_ayt_tamamlanma(
      ogrenci_id, aktif_mufredat
  )
  ay_adi, hedef_yuzde = get_aylik_mufredat_hedevi(mevcut_sinif)
  delta_yuzde = round(gercek_tamamlanma_orani - hedef_yuzde, 1)

  if delta_yuzde < 0 and gercek_tamamlanma_orani < 100.0:
    alarmlar["mavi"].append({
        "ders": "Müfredat Zamanlama Akışı",
        "konu": f"{ay_adi} Ayı Müfredat Hedefi (Eksi %{abs(delta_yuzde)} Geride)",
        "detay": (
            f"{ay_adi} ayı itibarıyla {mevcut_sinif} seviyesi için hedeflenen"
            f" %{hedef_yuzde} müfredat tamamlama oranının"
            f" **-%{abs(delta_yuzde)}** gerisindesiniz! (Tamamlanan Kredi"
            f" Oranı: %{gercek_tamamlanma_orani})"
        ),
        "aksiyon": "🔵 Aksiyon: Haftalık konu tamamlama ivmesini artırın.",
        "neden": "Takvim Geriliği",
    })

  mufredat_cezasi = abs(delta_yuzde) * 1.5 if delta_yuzde < 0 else 0.0
  alarm_cezasi = (
      len(alarmlar["siyah"]) * 8.0
      + len(alarmlar["kirmizi"]) * 5.0
      + len(alarmlar["mor"]) * 3.0
      + len(alarmlar["turuncu"]) * 2.0
  )

  if (
      gercek_tamamlanma_orani >= 100.0
      and sum(len(v) for v in alarmlar.values()) == 0
  ):
    saglik_skoru = 100
  else:
    saglik_skoru = max(
        25, min(100, int(100.0 - mufredat_cezasi - alarm_cezasi))
    )

  return (
      alarmlar,
      saglik_skoru,
      delta_yuzde,
      gercek_tamamlanma_orani,
      hedef_yuzde,
  )


# ==============================================================================
# 👑 ADMİN / YÖNETİCİ PANELİ
# ==============================================================================
if current_user["rol"] == "admin":
  st.title("👑 KARAKOÇ KOÇLUK YÖNETİCİ KOMUTA MERKEZİ")
  st.markdown(
      f"Hoş Geldiniz, **{current_user['ad']}**. Buradan öğrencilerinize üyelik"
      " tanımlayabilir, şifre belirleyebilir ve gelişim skorlarını"
      " izleyebilirsiniz."
  )

  admin_tab1, admin_tab2, admin_tab3 = st.tabs([
      "➕ 1. Yeni Öğrenci Üyeliği Oluştur",
      "👥 2. Kayıtlı Öğrenci & Şifre Yönetimi",
      "🛒 3. Özel Ders Talepleri Yönetimi",
  ])

  with admin_tab1:
    st.subheader("📝 Yeni Öğrenci Hesabı Oluştur")
    with st.form("admin_create_user_form"):
      col_u1, col_u2 = st.columns(2)
      with col_u1:
        new_ad = st.text_input(
            "Öğrenci Adı Soyadı:", placeholder="Örn: Ahmet Yılmaz"
        )
        new_username = st.text_input(
            "Kullanıcı Adı:", placeholder="Örn: ahmet_yilmaz"
        )
        new_pass = st.text_input(
            "Başlangıç Şifresi:", type="password", placeholder="••••••••"
        )
        new_tc = st.text_input(
            "T.C. Kimlik / No:", max_chars=11, placeholder="11 Haneli TC"
        )
      with col_u2:
        new_alan = st.selectbox(
            "YKS Alanı:", ["Sayısal", "Eşit Ağırlık", "Sözel", "Dil"]
        )
        new_sinif = st.selectbox(
            "Sınıf Seviyesi:",
            ["9. Sınıf", "10. Sınıf", "11. Sınıf", "12. Sınıf", "Mezun"],
        )
        new_lisans_gun = st.number_input(
            "Lisans Süresi (Gün):", min_value=30, max_value=730, value=365
        )

      if st.form_submit_button("🚀 Öğrenci Hesabını Oluştur", type="primary"):
        if (
            not new_ad.strip()
            or not new_username.strip()
            or not new_pass.strip()
            or not new_tc.strip()
        ):
          st.error("Lütfen tüm zorunlu alanları doldurunuz!")
        else:
          lisans_tarihi = (
              get_tr_now() + timedelta(days=new_lisans_gun)
          ).strftime("%Y-%m-%d")
          pass_h = hash_password(new_pass.strip())
          try:
            with get_connection() as conn:
              cursor = conn.cursor()
              cursor.execute(
                  """INSERT INTO ogrenciler 
                                   (tc_no, kullanici_adi, sifre_hash, ad, hedef_alan, sinif_seviyesi, alan_kilitli, rol, hesap_durumu, lisans_bitis, streak_count, son_aktif_tarih) 
                                   VALUES (?, ?, ?, ?, ?, ?, 1, 'ogrenci', 'Aktif', ?, 1, ?)""",
                  (
                      new_tc.strip(),
                      new_username.strip(),
                      pass_h,
                      new_ad.strip(),
                      new_alan,
                      new_sinif,
                      lisans_tarihi,
                      get_tr_now().strftime("%Y-%m-%d"),
                  ),
              )
              conn.commit()
            log_islem(
                current_user["id"],
                "ADMIN_CREATE_USER",
                f"Kullanıcı oluşturuldu: {new_username}",
            )
            st.success(
                f"🎉 '{new_ad}' hesabı oluşturuldu! Kullanıcı Adı:"
                f" `{new_username}` | Lisans Bitiş: `{lisans_tarihi}`"
            )
          except sqlite3.IntegrityError:
            st.error(
                "⚠️ Bu Kullanıcı Adı veya T.C. Kimlik Numarası sistemde zaten"
                " kayıtlı!"
            )

  with admin_tab2:
    st.subheader("📊 Kayıtlı Öğrenci Listesi & İşlemler")
    with get_connection() as conn:
      df_ogrenciler = pd.read_sql_query(
          "SELECT id, kullanici_adi, tc_no, ad, hedef_alan, sinif_seviyesi,"
          " hesap_durumu, lisans_bitis FROM ogrenciler WHERE rol != 'admin'",
          conn,
      )

    if not df_ogrenciler.empty:
      skorlar = []
      for _, ogr in df_ogrenciler.iterrows():
        ogr_mufredat = build_student_curriculum(
            ogr["sinif_seviyesi"], ogr["hedef_alan"]
        )
        _, s_skor, _, _, _ = hesapla_tum_alarmlar(
            ogr["id"], ogr["sinif_seviyesi"], ogr_mufredat
        )
        skorlar.append(f"%{s_skor}")

      df_ogrenciler["Gelişim Skoru"] = skorlar
      st.dataframe(df_ogrenciler, use_container_width=True)

      st.markdown("---")
      st.subheader("🔑 Öğrenci Şifre / Durum Güncelleme")
      selected_user_id = st.selectbox(
          "İşlem Yapılacak Öğrenci:",
          options=df_ogrenciler["id"].tolist(),
          format_func=lambda x: (
              f"{df_ogrenciler[df_ogrenciler['id']==x]['ad'].values[0]}"
              f" ({df_ogrenciler[df_ogrenciler['id']==x]['kullanici_adi'].values[0]})"
          ),
      )

      col_m1, col_m2 = st.columns(2)
      with col_m1:
        yeni_sifre_input = st.text_input(
            "Yeni Şifre Tanımla:", type="password", key="adm_new_pass_input"
        )
        if st.button("🔑 Şifreyi Güncelle", type="secondary"):
          if yeni_sifre_input.strip():
            new_h = hash_password(yeni_sifre_input.strip())
            with get_connection() as conn:
              cursor = conn.cursor()
              cursor.execute(
                  "UPDATE ogrenciler SET sifre_hash = ? WHERE id = ?",
                  (new_h, selected_user_id),
              )
              conn.commit()
            st.success("Öğrenci şifresi güncellendi!")
            st.rerun()
          else:
            st.error("Şifre boş olamaz!")
      with col_m2:
        yeni_durum = st.selectbox(
            "Hesap Durumu:", ["Aktif", "Pasif"], key="adm_status_select"
        )
        if st.button("🔄 Durumu Kaydet"):
          with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE ogrenciler SET hesap_durumu = ? WHERE id = ?",
                (yeni_durum, selected_user_id),
            )
            conn.commit()
          st.success(f"Hesap durumu '{yeni_durum}' olarak güncellendi!")
          st.rerun()
    else:
      st.info("Sistemde henüz bir öğrenci hesabı bulunmuyor.")

  with admin_tab3:
    st.subheader("📜 Öğrencilerden Gelen Özel Ders Talepleri")
    with get_connection() as conn:
      df_all_talepler = pd.read_sql_query(
          "SELECT t.id, o.ad as ogrenci_adi, t.ders, t.konu, t.alarm_turu,"
          " t.talep_tarihi, t.durum FROM pazaryeri_talepler t JOIN ogrenciler"
          " o ON t.ogrenci_id = o.id ORDER BY t.id DESC",
          conn,
      )
    if not df_all_talepler.empty:
      for idx, r in df_all_talepler.iterrows():
        col_adm1, col_adm2 = st.columns([4, 1])
        with col_adm1:
          st.write(
              f"👤 **{r['ogrenci_adi']}** | 📘 **{r['ders']} - {r['konu']}** |"
              f" Tarih: `{r['talep_tarihi']}` | Durum: `{r['durum']}`"
          )
        with col_adm2:
          if r["durum"] != "Tamamlandı":
            if st.button("✔️ Talebi Onayla", key=f"adm_btn_{r['id']}"):
              with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE pazaryeri_talepler SET durum = 'Tamamlandı' WHERE"
                    " id = ?",
                    (r["id"],),
                )
                conn.commit()
              log_islem(
                  current_user["id"],
                  "ADMIN_APPROVE",
                  f"Talep ID {r['id']} onaylandı.",
              )
              st.success("Talep tamamlandı!")
              st.rerun()
        st.markdown("---")
    else:
      st.info("Henüz bekleyen bir özel ders talebi yok.")

  st.markdown("---")
  if st.button("🚪 Yönetici Oturumunu Kapat"):
    st.session_state.active_user = None
    st.rerun()
  st.stop()

# ==============================================================================
# ÖĞRENCİ PANELİ VE KOKPİT ARAYÜZÜ (STUDENT DASHBOARD)
# ==============================================================================
is_maarif = current_user["sinif_seviyesi"] in ["9. Sınıf", "10. Sınıf"]
(
    alarmlar_db,
    saglik_skoru,
    delta_yuzde,
    gercek_orand,
    hedef_yuzd,
) = hesapla_tum_alarmlar(
    current_user["id"],
    current_user["sinif_seviyesi"],
    aktif_mufredat_hiyerarsisi,
)
tyt_orani, ayt_orani, genel_tamamlanma_orani = hesapla_tyt_ayt_tamamlanma(
    current_user["id"], aktif_mufredat_hiyerarsisi
)

with st.sidebar:
  st.title("🎓 Öğrenci Profili")
  st.write(f"**Öğrenci:** {current_user['ad']}")
  st.write(f"**Kullanıcı Adı:** `{current_user['kullanici_adi']}`")
  st.write(f"**Aktif Alan:** `{current_user['hedef_alan']}`")
  st.write(f"**Sınıf Seviyesi:** `{current_user['sinif_seviyesi']}`")

  st.markdown(
      f"""<div class="streak-card">
        🔥 <b>Çalışma Serisi: {current_user['streak_count']} Gün Kesintisiz!</b>
        </div>""",
      unsafe_allow_html=True,
  )

  st.markdown(f"**TYT Müfredat:** `%{tyt_orani}`")
  st.markdown(f"**AYT Müfredat:** `%{ayt_orani}`")

  if is_maarif:
    st.markdown(
        '<span class="maarif-rozet">📘 Türkiye Yüzyılı Maarif Modeli</span>',
        unsafe_allow_html=True,
    )
  else:
    st.markdown(
        '<span class="klasik-rozet">📕 YKS Müfredat Sistemi</span>',
        unsafe_allow_html=True,
    )

  st.markdown("---")
  st.subheader("⚙️ Profil / Sınıf Güncelle")
  with st.form("sidebar_profil_guncelle_form"):
    yeni_alan = st.selectbox(
        "Hedef Alan:",
        ["Sayısal", "Eşit Ağırlık", "Sözel", "Dil"],
        index=(
            ["Sayısal", "Eşit Ağırlık", "Sözel", "Dil"].index(
                current_user["hedef_alan"]
            )
            if current_user["hedef_alan"]
            in ["Sayısal", "Eşit Ağırlık", "Sözel", "Dil"]
            else 0
        ),
    )
    yeni_sinif = st.selectbox(
        "Sınıf Seviyesi:",
        ["9. Sınıf", "10. Sınıf", "11. Sınıf", "12. Sınıf", "Mezun"],
        index=(
            ["9. Sınıf", "10. Sınıf", "11. Sınıf", "12. Sınıf", "Mezun"].index(
                current_user["sinif_seviyesi"]
            )
            if current_user["sinif_seviyesi"]
            in ["9. Sınıf", "10. Sınıf", "11. Sınıf", "12. Sınıf", "Mezun"]
            else 3
        ),
    )
    if st.form_submit_button("Profilimi Güncelle", type="secondary"):
      with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE ogrenciler SET hedef_alan = ?, sinif_seviyesi = ? WHERE id"
            " = ?",
            (yeni_alan, yeni_sinif, current_user["id"]),
        )
        conn.commit()
      st.session_state.active_user["hedef_alan"] = yeni_alan
      st.session_state.active_user["sinif_seviyesi"] = yeni_sinif
      log_islem(
          current_user["id"],
          "UPDATE_PROFILE",
          f"Alan: {yeni_alan}, Sınıf: {yeni_sinif}",
      )
      st.success("Profil başarıyla güncellendi!")
      st.rerun()

  st.markdown("---")
  if st.button("🚪 Oturumu Kapat"):
    st.session_state.active_user = None
    st.rerun()

st.title(
    "🎯 KARAKOÇ YKS Akıllı Koçluk Paneli"
    f" ({current_user['hedef_alan']} - {current_user['sinif_seviyesi']})"
)

toplam_alarm_sayisi = sum(len(v) for v in alarmlar_db.values())
ay_adi_kokpit, _ = get_aylik_mufredat_hedevi(current_user["sinif_seviyesi"])

m1, m2, m3, m4 = st.columns(4)
m1.metric("🏥 Genel Gelişim Skoru", f"%{saglik_skoru}")
m2.metric("🔥 Çalışma Serisi", f"{current_user['streak_count']} Gün")
m3.metric("🚨 Odaklanılacak Kritik Nokta", f"{toplam_alarm_sayisi} Konu")

delta_label = (
    f"+%{delta_yuzde} İleride"
    if delta_yuzde >= 0
    else f"-%{abs(delta_yuzde)} Geride"
)
m4.metric(
    f"📅 {ay_adi_kokpit} Takvim Durumu",
    f"%{round(gercek_orand, 1)}",
    delta=delta_label,
)

st.markdown("---")

if alarmlar_db["siyah"]:
  for a in alarmlar_db["siyah"]:
    st.markdown(
        f"""<div class="siyah-alarm-card"><h3>⬛ [KRİTİK UYARI] {a['ders']} - {a['konu']}</h3><p><b>Durum:</b> {a['detay']}</p><p>👉 <b>{a['aksiyon']}</b></p></div>""",
        unsafe_allow_html=True,
    )

if alarmlar_db["kirmizi"]:
  for a in alarmlar_db["kirmizi"]:
    st.error(
        f"🔴 **[DİKKAT UYARISI]**: **{a['ders']} - {a['konu']}** |"
        f" {a['detay']}\n\n🛒 **Aksiyon:** {a['aksiyon']}"
    )

st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📚 1. Konu Takip ve İlerleme Paneli",
    "📝 2. Genel & Branş Deneme Analizi",
    "🚨 3. Akıllı Uyarı & Risk Paneli",
    "📅 4. Haftalık Telafi & Çalışma Programı",
    "🛒 5. Özel Ders & Performans Raporu",
])


def on_mikro_change(ders_adi, makro_adi, mikro_ad, key_name):
  val = st.session_state.get(key_name, False)
  with get_connection() as c:
    cur = c.cursor()
    if val:
      cur.execute(
          "INSERT INTO konu_durumlari_detay (ogrenci_id, ders, makro_konu,"
          " mikro_konu, durum) VALUES (?, ?, ?, ?, 'Biliyorum') ON CONFLICT DO"
          " UPDATE SET durum='Biliyorum'",
          (current_user["id"], ders_adi, makro_adi, mikro_ad),
      )
    else:
      cur.execute(
          "DELETE FROM konu_durumlari_detay WHERE ogrenci_id = ? AND ders = ?"
          " AND makro_konu = ? AND mikro_konu = ?",
          (current_user["id"], ders_adi, makro_adi, mikro_ad),
      )
    c.commit()
  log_islem(
      current_user["id"], "TOPIC_TOGGLE", f"{ders_adi} -> {mikro_ad}: {val}"
  )


def on_toplu_change(ders_adi, makro_adi, mikro_listesi, toplu_key):
  val = st.session_state.get(toplu_key, False)
  with get_connection() as c:
    cur = c.cursor()
    cur.execute(
        "DELETE FROM konu_durumlari_detay WHERE ogrenci_id = ? AND ders = ?"
        " AND makro_konu = ?",
        (current_user["id"], ders_adi, makro_adi),
    )
    if val:
      for m in mikro_listesi:
        cur.execute(
            "INSERT INTO konu_durumlari_detay (ogrenci_id, ders, makro_konu,"
            " mikro_konu, durum) VALUES (?, ?, ?, ?, 'Biliyorum')",
            (current_user["id"], ders_adi, makro_adi, m),
        )
        st.session_state[f"chk_{ders_adi}_{makro_adi}_{m}"] = True
    else:
      for m in mikro_listesi:
        st.session_state[f"chk_{ders_adi}_{makro_adi}_{m}"] = False
    c.commit()


def on_ders_tamamen_bitir(ders_adi, makro_dict, bitir_mi=True):
  with get_connection() as c:
    cur = c.cursor()
    cur.execute(
        "DELETE FROM konu_durumlari_detay WHERE ogrenci_id = ? AND ders = ?",
        (current_user["id"], ders_adi),
    )
    if bitir_mi:
      for makro_ad, mikro_listesi in makro_dict.items():
        if isinstance(mikro_listesi, list):
          for mik_ad in mikro_listesi:
            cur.execute(
                "INSERT INTO konu_durumlari_detay (ogrenci_id, ders,"
                " makro_konu, mikro_konu, durum) VALUES (?, ?, ?, ?,"
                " 'Biliyorum')",
                (current_user["id"], ders_adi, makro_ad, mik_ad),
            )
            st.session_state[f"chk_{ders_adi}_{makro_ad}_{mik_ad}"] = True
          st.session_state[f"toplu_{ders_adi}_{makro_ad}"] = True
    else:
      for makro_ad, mikro_listesi in makro_dict.items():
        if isinstance(mikro_listesi, list):
          for mik_ad in mikro_listesi:
            st.session_state[f"chk_{ders_adi}_{makro_ad}_{mik_ad}"] = False
          st.session_state[f"toplu_{ders_adi}_{makro_ad}"] = False
    c.commit()
  log_islem(
      current_user["id"],
      "COURSE_BATCH_FINISH",
      f"{ders_adi} bitir={bitir_mi}",
  )


def resolve_alarm(id_list):
  if not id_list:
    return
  with get_connection() as c:
    cur = c.cursor()
    placeholders = ",".join("?" * len(id_list))
    cur.execute(
        f"UPDATE deneme_konu_yanlislari SET durum = 'Çözüldü' WHERE id IN"
        f" ({placeholders})",
        id_list,
    )
    c.commit()
  log_islem(
      current_user["id"],
      "RESOLVE_ALARM",
      f"Alarm ID'leri temizlendi: {id_list}",
  )


with tab1:
  st.header("🌳 Konu Takip & İlerleme Tablosu")
  with get_connection() as conn:
    df_tum_bilinenler = pd.read_sql_query(
        "SELECT ders, makro_konu, mikro_konu FROM konu_durumlari_detay WHERE"
        " ogrenci_id = ? AND durum = 'Biliyorum'",
        conn,
        params=(current_user["id"],),
    )
  bilinen_pairs_set = set(
      zip(df_tum_bilinenler["ders"], df_tum_bilinenler["mikro_konu"])
  )

  if aktif_mufredat_hiyerarsisi:
    ders_tablari = st.tabs(list(aktif_mufredat_hiyerarsisi.keys()))

    for i, (ders_adi, makro_konular) in enumerate(
        aktif_mufredat_hiyerarsisi.items()
    ):
      with ders_tablari[i]:
        st.subheader(f"📖 {ders_adi} Konu Listesi")
        col_btn1, col_btn2 = st.columns([3, 1])
        with col_btn1:
          if st.button(
              f"🚀 {ders_adi} Dersini Komple Bitir (%100)",
              key=f"btn_full_finish_{ders_adi}",
              type="primary",
          ):
            on_ders_tamamen_bitir(ders_adi, makro_konular, bitir_mi=True)
            st.success(
                f"🎉 {ders_adi} dersinin tüm konuları %100 olarak tamamlandı!"
            )
            st.rerun()
        with col_btn2:
          if st.button(
              f"🧹 {ders_adi} Sıfırla (%0)",
              key=f"btn_full_reset_{ders_adi}",
              type="secondary",
          ):
            on_ders_tamamen_bitir(ders_adi, makro_konular, bitir_mi=False)
            st.warning(f"🧹 {ders_adi} dersi konuları sıfırlandı!")
            st.rerun()

        st.markdown("---")

        if isinstance(makro_konular, dict):
          for makro_adi, mikro_listesi in makro_konular.items():
            if isinstance(mikro_listesi, list):
              tamamlananlar = [
                  m
                  for m in mikro_listesi
                  if (ders_adi, m) in bilinen_pairs_set
              ]
              toplam_mikro = len(mikro_listesi)
              tamamlanan_sayi = len(tamamlananlar)
              yuzde = (
                  int((tamamlanan_sayi / toplam_mikro) * 100)
                  if toplam_mikro > 0
                  else 0
              )

              expander_baslik = (
                  f"{'✅' if yuzde == 100 else '📌'} {makro_adi} (%{yuzde}"
                  " Tamamlandı)"
              )
              with st.expander(expander_baslik, expanded=(yuzde < 100)):
                st.progress(yuzde / 100.0)
                col_ak1, col_ak2 = st.columns([3, 1])
                with col_ak1:
                  st.write("**Alt Konular:**")
                  for mikro_ad in mikro_listesi:
                    key_name = f"chk_{ders_adi}_{makro_adi}_{mikro_ad}"
                    is_completed = (
                        ders_adi,
                        mikro_ad,
                    ) in bilinen_pairs_set
                    if key_name not in st.session_state:
                      st.session_state[key_name] = is_completed
                    st.checkbox(
                        mikro_ad,
                        key=key_name,
                        on_change=on_mikro_change,
                        args=(ders_adi, makro_adi, mikro_ad, key_name),
                    )

                with col_ak2:
                  st.write("**Hızlı İşlem:**")
                  toplu_key = f"toplu_{ders_adi}_{makro_adi}"
                  if toplu_key not in st.session_state:
                    st.session_state[toplu_key] = (
                        yuzde == 100 and toplam_mikro > 0
                    )
                  st.checkbox(
                      "Tümünü Bitti İşaretle (%100)",
                      key=toplu_key,
                      on_change=on_toplu_change,
                      args=(ders_adi, makro_adi, mikro_listesi, toplu_key),
                  )

with tab2:
  st.header("📝 Oyunlaştırılmış Genel & Branş Denemesi Analizi")
  if "wiz_step" not in st.session_state:
    st.session_state.wiz_step = 1
  if "wiz_kategori" not in st.session_state:
    st.session_state.wiz_kategori = "Genel Deneme"
  if "wiz_brans_dersi" not in st.session_state:
    st.session_state.wiz_brans_dersi = ""
  if "wiz_tur" not in st.session_state:
    st.session_state.wiz_tur = "TYT"
  if "wiz_adi" not in st.session_state:
    st.session_state.wiz_adi = ""
  if "wiz_net" not in st.session_state:
    st.session_state.wiz_net = 0.0
  if "wiz_selected_dersler" not in st.session_state:
    st.session_state.wiz_selected_dersler = []
  if "wiz_card_idx" not in st.session_state:
    st.session_state.wiz_card_idx = 0
  if "wiz_queue" not in st.session_state:
    st.session_state.wiz_queue = []
  if "wiz_draft_mistakes" not in st.session_state:
    st.session_state.wiz_draft_mistakes = []
  if "wiz_show_details" not in st.session_state:
    st.session_state.wiz_show_details = False

  ogrenci_alan = current_user["hedef_alan"]
  if ogrenci_alan == "Dil":
    izinli_sinav_turleri = ["TYT", "YDT"]
  elif current_user["sinif_seviyesi"] in ["9. Sınıf", "10. Sınıf"]:
    izinli_sinav_turleri = ["TYT"]
  else:
    izinli_sinav_turleri = ["TYT", "AYT"]

  if st.session_state.wiz_step == 1:
    st.markdown(
        f"""<div class="simulator-card"><h3>🎮 Adım 1: Sınav Formatını ve Detaylarını Girin</h3><p>Selam <b>{current_user['ad']}</b>! Analiz etmek istediğin <b>Genel Deneme</b> veya <b>Branş Denemesi</b> bilgilerini girerek başlayalım.</p></div>""",
        unsafe_allow_html=True,
    )
    col_w1, col_w2 = st.columns(2)
    with col_w1:
      st.session_state.wiz_kategori = st.radio(
          "Deneme Formatı:", ["Genel Deneme", "Branş Denemesi"], horizontal=True
      )
      st.session_state.wiz_tur = st.radio(
          "Sınav Türü:", options=izinli_sinav_turleri, horizontal=True
      )
      st.session_state.wiz_adi = st.text_input(
          "Deneme Adı / Yayın Eviniz:",
          placeholder=(
              "Örn: 3D TYT 2. Genel Deneme veya Bilgi Sarmal AYT Mat Branş"
          ),
      )
    with col_w2:
      if st.session_state.wiz_kategori == "Branş Denemesi":
        uyumlu_dersler = [
            d
            for d in aktif_mufredat_hiyerarsisi.keys()
            if (
                st.session_state.wiz_tur == "TYT"
                and (
                    d.startswith("TYT")
                    or d
                    in [
                        "Matematik ve Veri",
                        "Gramer ve Kelime",
                        "Soru Tipleri",
                    ]
                )
            )
            or (st.session_state.wiz_tur == "AYT" and d.startswith("AYT"))
            or (
                st.session_state.wiz_tur == "YDT"
                and ("YDT" in d or "İngilizce" in d)
            )
        ]
        if not uyumlu_dersler:
          uyumlu_dersler = list(aktif_mufredat_hiyerarsisi.keys())
        st.session_state.wiz_brans_dersi = st.selectbox(
            "Branş Denemesi Yapılan Ders:", options=uyumlu_dersler
        )
        max_net_val = (
            40.0
            if "Matematik" in st.session_state.wiz_brans_dersi
            or "Türkçe" in st.session_state.wiz_brans_dersi
            else 80.0
        )
        st.session_state.wiz_net = st.number_input(
            "Branş Denemesi Netiniz:",
            min_value=0.0,
            max_value=max_net_val,
            value=min(25.0, max_net_val),
            step=0.25,
        )
      else:
        st.session_state.wiz_brans_dersi = None
        max_genel_net = 120.0 if st.session_state.wiz_tur == "TYT" else 80.0
        st.session_state.wiz_net = st.number_input(
            "Genel Deneme Total Netiniz:",
            min_value=0.0,
            max_value=max_genel_net,
            value=min(75.0, max_genel_net),
            step=0.25,
        )

    if st.button("İleri ➔ Analiz Adımına Geç", type="primary"):
      if st.session_state.wiz_adi.strip():
        if st.session_state.wiz_kategori == "Branş Denemesi":
          st.session_state.wiz_selected_dersler = [
              st.session_state.wiz_brans_dersi
          ]
          queue = []
          mak_dict = aktif_mufredat_hiyerarsisi.get(
              st.session_state.wiz_brans_dersi, {}
          )
          if isinstance(mak_dict, dict):
            for mak_k, mik_v in mak_dict.items():
              queue.append({
                  "ders": st.session_state.wiz_brans_dersi,
                  "makro": mak_k,
                  "mikro_listesi": mik_v,
              })
          st.session_state.wiz_queue = queue
          st.session_state.wiz_card_idx = 0
          st.session_state.wiz_show_details = False
          st.session_state.wiz_step = 3
          st.rerun()
        else:
          st.session_state.wiz_step = 2
          st.rerun()
      else:
        st.error("Lütfen deneme sınavının adını yazınız!")

  elif st.session_state.wiz_step == 2:
    st.markdown(
        f"""<div class="simulator-card"><h3>🎯 Adım 2: Hangi {st.session_state.wiz_tur} Derslerinden Yanlışınız Var?</h3><p>Sadece <b>{current_user['hedef_alan']}</b> alanınıza ait <b>{st.session_state.wiz_tur}</b> dersleri aşağıda listelenmiştir.</p></div>""",
        unsafe_allow_html=True,
    )
    secilen_tur = st.session_state.wiz_tur
    filtrated_dersler = [
        d
        for d in aktif_mufredat_hiyerarsisi.keys()
        if (
            secilen_tur == "TYT"
            and (
                d.startswith("TYT")
                or d
                in ["Matematik ve Veri", "Gramer ve Kelime", "Soru Tipleri"]
            )
        )
        or (secilen_tur == "AYT" and d.startswith("AYT"))
        or (secilen_tur == "YDT" and ("YDT" in d or "İngilizce" in d))
    ]
    if not filtrated_dersler:
      filtrated_dersler = list(aktif_mufredat_hiyerarsisi.keys())

    seçilen_dersler = st.multiselect(
        f"Yanlış / Boş Olan {secilen_tur} Dersleri:",
        options=filtrated_dersler,
        default=(
            filtrated_dersler[:2]
            if len(filtrated_dersler) >= 2
            else filtrated_dersler
        ),
    )
    col_b1, col_b2 = st.columns(2)
    with col_b1:
      if st.button("⬅️ Başa Dön"):
        st.session_state.wiz_step = 1
        st.rerun()
    with col_b2:
      if st.button("İleri ➔ Hızlı Analize Başla 🚀", type="primary"):
        if seçilen_dersler:
          st.session_state.wiz_selected_dersler = seçilen_dersler
          queue = []
          for d_ad in seçilen_dersler:
            mak_dict = aktif_mufredat_hiyerarsisi.get(d_ad, {})
            if isinstance(mak_dict, dict):
              for mak_k, mik_v in mak_dict.items():
                queue.append({
                    "ders": d_ad,
                    "makro": mak_k,
                    "mikro_listesi": mik_v,
                })
          st.session_state.wiz_queue = queue
          st.session_state.wiz_card_idx = 0
          st.session_state.wiz_show_details = False
          st.session_state.wiz_step = 3
          st.rerun()
        else:
          st.warning("Analiz yapmak için en az 1 ders seçmelisiniz!")

  elif st.session_state.wiz_step == 3:
    queue = st.session_state.wiz_queue
    card_idx = st.session_state.wiz_card_idx
    if card_idx >= len(queue):
      st.session_state.wiz_step = 4
      st.rerun()

    current_card = queue[card_idx]
    toplam_kart = len(queue)
    progress_val = (card_idx + 1) / toplam_kart
    st.progress(progress_val)
    st.caption(
        f"Konu İlerlemesi: {card_idx + 1} / {toplam_kart} ➔"
        f" **{current_card['ders']}**"
    )

    col_hdr1, col_hdr2 = st.columns([3, 1])
    with col_hdr1:
      st.markdown(
          f'<div class="card-ders-title">📘 {current_card["ders"]}</div>',
          unsafe_allow_html=True,
      )
    with col_hdr2:
      st.markdown('<div class="fast-pass-top-btn">', unsafe_allow_html=True)
      if st.button("⚡ Kalan Konuları Geç", key=f"btn_fp_{card_idx}"):
        cur_ders = current_card["ders"]
        while (
            st.session_state.wiz_card_idx < len(queue)
            and queue[st.session_state.wiz_card_idx]["ders"] == cur_ders
        ):
          st.session_state.wiz_card_idx += 1
        st.session_state.wiz_show_details = False
        st.success(f"⚡ {cur_ders} dersinin kalan konuları temiz geçildi!")
        st.rerun()
      st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        f"""<div class="single-card-container"><div class="card-konu-title">{current_card['makro']}</div><p style="font-size: 1.1rem; color: #374151; font-weight: 600;">Bu konudan yanlışınız, boşunuz veya tereddüdünüz var mı?</p></div>""",
        unsafe_allow_html=True,
    )

    if not st.session_state.wiz_show_details:
      st.markdown('<div class="card-mega-buttons">', unsafe_allow_html=True)
      col_no, col_yes = st.columns(2)
      with col_no:
        if st.button("🟢 HAYIR (TEMİZ)", key=f"btn_mega_no_{card_idx}"):
          st.session_state.wiz_card_idx += 1
          st.session_state.wiz_show_details = False
          st.rerun()
      with col_yes:
        if st.button("🔴 EVET (YANLIŞ VAR)", key=f"btn_mega_yes_{card_idx}"):
          st.session_state.wiz_show_details = True
          st.rerun()
      st.markdown("</div>", unsafe_allow_html=True)
    else:
      st.warning(
          f"⚠️ **{current_card['makro']}** konusu için detayları seçin:"
      )
      secili_mikrolar = st.multiselect(
          "Hangi Alt Konuda Yanlış Yaşadınız?",
          options=current_card["mikro_listesi"],
          key=f"card_mikro_{card_idx}",
      )
      y_adedi = st.number_input(
          "Kaç Yanlış Yaptınız?",
          min_value=1,
          max_value=20,
          value=1,
          key=f"card_y_num_{card_idx}",
      )
      nedenler = st.multiselect(
          "Hata Nedeni / Nedenleri (Çoklu Seçilebilir):",
          [
              "Konu Eksikliği",
              "İşlem / Dikkat Hatası",
              "Süre Yetişmedi",
              "İki Şık Arasında Kaldım (Şans Doğrusu)",
              "Soruyu Yanlış Okudum",
          ],
          default=["Konu Eksikliği"],
          key=f"card_neden_{card_idx}",
      )
      col_c1, col_c2 = st.columns(2)
      with col_c1:
        if st.button("⬅️ Vazgeç (Hayır İşaretle)"):
          st.session_state.wiz_show_details = False
          st.rerun()
      with col_c2:
        if st.button("Kaydet ve Sonraki Karta Geç ➔", type="primary"):
          if secili_mikrolar:
            for mik in secili_mikrolar:
              st.session_state.wiz_draft_mistakes.append({
                  "ders": current_card["ders"],
                  "makro": current_card["makro"],
                  "mikro": mik,
                  "yanlis_adedi": y_adedi,
                  "nedenler": ", ".join(nedenler),
              })
            st.session_state.wiz_card_idx += 1
            st.session_state.wiz_show_details = False
            st.rerun()
          else:
            st.error("Lütfen en az 1 alt konu seçiniz!")

  elif st.session_state.wiz_step == 4:
    st.markdown(
        f"""<div class="simulator-card"><h3>🎉 Deneme Analizi Tamamlandı!</h3><p><b>[{st.session_state.wiz_kategori}] {st.session_state.wiz_tur} - {st.session_state.wiz_adi} ({st.session_state.wiz_net} Net)</b> sınavı veritabanına kaydedildi.</p></div>""",
        unsafe_allow_html=True,
    )
    drafts = st.session_state.wiz_draft_mistakes
    if drafts:
      st.subheader("📌 Çalışma Listesine Eklenen Yanlış Konular:")
      simdi_s = get_tr_now().strftime("%Y-%m-%d %H:%M:%S")
      with get_connection() as conn:
        cursor = conn.cursor()
        for item in drafts:
          cursor.execute(
              """INSERT INTO deneme_konu_yanlislari 
                               (ogrenci_id, deneme_kategorisi, brans_dersi, deneme_turu, deneme_adi, net_bilgisi, ders, makro_konu, konu_adi, yanlis_adedi, yanlis_nedeni, durum, tarih) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Aktif', ?)""",
              (
                  current_user["id"],
                  st.session_state.wiz_kategori,
                  st.session_state.wiz_brans_dersi,
                  st.session_state.wiz_tur,
                  st.session_state.wiz_adi,
                  st.session_state.wiz_net,
                  item["ders"],
                  item["makro"],
                  item["mikro"],
                  item["yanlis_adedi"],
                  item["nedenler"],
                  simdi_s,
              ),
          )
        conn.commit()
      st.dataframe(pd.DataFrame(drafts), use_container_width=True)
      log_islem(
          current_user["id"],
          "FINISH_MEGA_CARD_EXAM",
          f"{st.session_state.wiz_adi}: {len(drafts)} yanlış kaydedildi.",
      )
    else:
      st.info(
          "Bu denemede herhangi bir yanlış konusu işaretlemediniz. Harika bir"
          " performans!"
      )

    if st.button("🚀 Yeni Deneme Girişi Yap / Sıfırla", type="primary"):
      st.session_state.wiz_step = 1
      st.session_state.wiz_draft_mistakes = []
      st.session_state.wiz_selected_dersler = []
      st.session_state.wiz_card_idx = 0
      st.session_state.wiz_show_details = False
      st.rerun()

  st.markdown("---")
  st.subheader("📊 Ayrıştırılmış Performans ve Net Grafikleri")
  grafik_tab1, grafik_tab2, grafik_tab3, grafik_tab4 = st.tabs([
      "📈 TYT Genel Denemeler",
      "📈 AYT Genel Denemeler",
      "🎯 Branş Denemeleri",
      "🔍 Hata Nedenleri Dağılımı",
  ])

  with grafik_tab1:
    st.markdown("#### 📘 TYT Genel Deneme Net Gelişimi")
    with get_connection() as conn:
      df_tyt_genel = pd.read_sql_query(
          "SELECT deneme_adi, MAX(net_bilgisi) as net_bilgisi FROM"
          " deneme_konu_yanlislari WHERE ogrenci_id = ? AND deneme_turu = 'TYT'"
          " AND (deneme_kategorisi = 'Genel Deneme' OR deneme_kategorisi IS"
          " NULL OR deneme_kategorisi = 'Genel') GROUP BY deneme_adi ORDER BY"
          " id ASC",
          conn,
          params=(current_user["id"],),
      )
    if not df_tyt_genel.empty:
      st.line_chart(df_tyt_genel.set_index("deneme_adi")["net_bilgisi"])
    else:
      st.info("Henüz TYT Genel Denemesi verisi girilmedi.")

  with grafik_tab2:
    st.markdown("#### 📕 AYT / YDT Genel Deneme Net Gelişimi")
    target_tur = "YDT" if current_user["hedef_alan"] == "Dil" else "AYT"
    with get_connection() as conn:
      df_ayt_genel = pd.read_sql_query(
          "SELECT deneme_adi, MAX(net_bilgisi) as net_bilgisi FROM"
          " deneme_konu_yanlislari WHERE ogrenci_id = ? AND deneme_turu = ? AND"
          " (deneme_kategorisi = 'Genel Deneme' OR deneme_kategorisi IS NULL OR"
          " deneme_kategorisi = 'Genel') GROUP BY deneme_adi ORDER BY id ASC",
          conn,
          params=(current_user["id"], target_tur),
      )
    if not df_ayt_genel.empty:
      st.line_chart(df_ayt_genel.set_index("deneme_adi")["net_bilgisi"])
    else:
      st.info(f"Henüz {target_tur} Genel Denemesi verisi girilmedi.")

  with grafik_tab3:
    st.markdown("#### 🎯 Ders Bazlı Branş Denemeleri Takibi")
    with get_connection() as conn:
      df_brans_all = pd.read_sql_query(
          "SELECT brans_dersi, deneme_adi, MAX(net_bilgisi) as net_bilgisi FROM"
          " deneme_konu_yanlislari WHERE ogrenci_id = ? AND deneme_kategorisi ="
          " 'Branş Denemesi' AND brans_dersi IS NOT NULL GROUP BY brans_dersi,"
          " deneme_adi ORDER BY id ASC",
          conn,
          params=(current_user["id"],),
      )
    if not df_brans_all.empty:
      mevcut_branslar = df_brans_all["brans_dersi"].unique().tolist()
      secilen_brans_grafik = st.selectbox(
          "Grafiğini İncelemek İstediğiniz Branş:", options=mevcut_branslar
      )
      df_filtreli_brans = df_brans_all[
          df_brans_all["brans_dersi"] == secilen_brans_grafik
      ]
      st.line_chart(df_filtreli_brans.set_index("deneme_adi")["net_bilgisi"])
    else:
      st.info("Henüz kayıtlara geçmiş Branş Denemesi bulunmuyor.")

  with grafik_tab4:
    st.markdown("#### 🔍 Soru Yanlış Nedenleri Analizi")
    with get_connection() as conn:
      df_nedenler = pd.read_sql_query(
          "SELECT yanlis_nedeni, SUM(yanlis_adedi) as toplam_yanlis FROM"
          " deneme_konu_yanlislari WHERE ogrenci_id = ? GROUP BY yanlis_nedeni",
          conn,
          params=(current_user["id"],),
      )
    if not df_nedenler.empty:
      st.bar_chart(df_nedenler.set_index("yanlis_nedeni")["toplam_yanlis"])
    else:
      st.info("Henüz analiz edilecek veri yok.")

with tab3:
  st.header("🚨 Akıllı Uyarı & Risk Paneli")
  col_al1, col_al2 = st.columns(2)
  with col_al1:
    st.subheader("⬛ / 🔴 / 🟣 Öncelikli Yanlış Alarmları")
    if (
        not alarmlar_db["siyah"]
        and not alarmlar_db["kirmizi"]
        and not alarmlar_db["mor"]
    ):
      st.success("Tebrikler! Kritik deneme uyarınız bulunmuyor.")
    else:
      for idx, a in enumerate(alarmlar_db["siyah"]):
        st.error(
            f"⬛ **[KRİTİK UYARI]** {a['ders']} -> {a['konu']}\n\n{a['detay']}\n\n👉"
            f" {a['aksiyon']}"
        )
        if st.button(
            f"✅ '{a['konu']}' Çalışması Tamamlandı", key=f"siyah_clr_{idx}"
        ):
          resolve_alarm(a["id_list"])
          st.success("Uyarı temizlendi!")
          st.rerun()

      for idx, a in enumerate(alarmlar_db["kirmizi"]):
        st.error(
            f"🔴 **[DİKKAT UYARISI]** {a['ders']} ->"
            f" {a['konu']}\n\n{a['detay']}\n\n👉 {a['aksiyon']}"
        )
        if st.button(
            f"✅ '{a['konu']}' Tekrar Edildi", key=f"kirmizi_clr_{idx}"
        ):
          resolve_alarm(a["id_list"])
          st.success("Uyarı temizlendi!")
          st.rerun()

      for idx, a in enumerate(alarmlar_db["mor"]):
        st.warning(
            f"🟣 **[KRONİK YANLIŞ]** {a['ders']} -> {a['konu']}\n\n{a['detay']}\n\n👉"
            f" {a['aksiyon']}"
        )
        if st.button(
            f"✅ '{a['konu']}' Özel Ders/Fasikülü Çözüldü", key=f"mor_clr_{idx}"
        ):
          resolve_alarm(a["id_list"])
          st.success("Uyarı temizlendi!")
          st.rerun()

  with col_al2:
    st.subheader("🟧 Ön Koşul ve 🔵 Takvim Uyarısı")
    if not alarmlar_db["turuncu"] and not alarmlar_db["mavi"]:
      st.success("Müfredat akışınızda ve ön koşullarınızda sorun yok.")
    else:
      for a in alarmlar_db["turuncu"]:
        st.markdown(
            f"""<div class="turuncu-alarm-card"><h4>🟧 [ÖN KOŞUL UYARISI] {a['konu']}</h4><p><b>Detay:</b> {a['detay']}</p><p>👉 <b>{a['aksiyon']}</b></p></div>""",
            unsafe_allow_html=True,
        )
      for a in alarmlar_db["mavi"]:
        st.markdown(
            f"""<div class="mavi-alarm-card"><h4>🔵 [TAKVİM UYARISI] {a['konu']}</h4><p><b>Detay:</b> {a['detay']}</p><p>👉 <b>{a['aksiyon']}</b></p></div>""",
            unsafe_allow_html=True,
        )

with tab4:
  st.header("📅 Haftalık Telafi & Çalışma Programı")
  col_p1, col_p2 = st.columns([1, 1])

  with col_p1:
    st.subheader("⚙️ Akıllı Çalışma Programı Ayarları")
    gunluk_saat = st.slider("Günlük Çalışma Kapasitesi (Saat):", 2, 12, 6)

    # 1.5 dk / soru tabanlı günlük maksimum gerçekçi soru kapasitesi
    toplam_gunluk_dakika = gunluk_saat * 60
    maks_soru_kapasitesi = int(toplam_gunluk_dakika / 1.5)  # örn: 6 saat = 240 soru

    # Dinamik Ana Görev Blok Sayısı Hesabı
    if gunluk_saat <= 4:
      ana_gorev_blok_sayisi = 2
    elif gunluk_saat == 5:
      ana_gorev_blok_sayisi = 3
    elif 6 <= gunluk_saat <= 7:
      ana_gorev_blok_sayisi = 4
    elif 8 <= gunluk_saat <= 9:
      ana_gorev_blok_sayisi = 5
    else:
      ana_gorev_blok_sayisi = 6

    # Zorunlu Günlük Paragraf Rutini Hesabı
    günlük_paragraf_hedef = min(30, 10 + (gunluk_saat * 2))
    kalan_soru_kapasitesi = max(20, maks_soru_kapasitesi - günlük_paragraf_hedef)
    blok_basi_soru_bütcesi = int(kalan_soru_kapasitesi / ana_gorev_blok_sayisi)

    st.info(
        f"📊 **Program Mimarisi ($1.5 \\text{{ dk/soru}}$ Kısıtı):** Günlük"
        f" **{gunluk_saat} Saat** ({toplam_gunluk_dakika} Dk) ➔ **Maksimum"
        f" {maks_soru_kapasitesi} Soru Kapasitesi**\n\n• **{günlük_paragraf_hedef}"
        f" Soru Paragraf Rutini** + **{ana_gorev_blok_sayisi} Ana Görev Bloğu**"
        f" (Blok Başına ~{blok_basi_soru_bütcesi} Soru)"
    )

    with get_connection() as conn:
      df_deneme_varmi = pd.read_sql_query(
          "SELECT COUNT(*) as sayi FROM deneme_konu_yanlislari WHERE ogrenci_id ="
          " ?",
          conn,
          params=(current_user["id"],),
      )
    deneme_girmis_mi = df_deneme_varmi["sayi"].iloc[0] > 0
    is_mufredat_yuzde100 = genel_tamamlanma_orani >= 100.0

    if is_mufredat_yuzde100:
      st.markdown(
          '<div class="karakoc-bot-box">🔥 <b>%100 Müfredat Modu Aktif:</b> Tüm'
          " konular bitti. Programınız tamamen <b>Deneme Yanlışlarınızdan Gelen"
          " Eksik Konu Havuzu</b> üzerinden P_score katsayılarına göre"
          " oluşturulacaktır.</div>",
          unsafe_allow_html=True,
      )
    else:
      st.markdown(
          f'<div class="karakoc-bot-box">📘 <b>Dinamik Müfredat ve Öncelik Modu'
          f' (%{genel_tamamlanma_orani}):</b> ÖSYM çıkmış soru kredisi yüksek'
          " olan konular ve takvim eksikleriniz öncelikli yerleştirilir.</div>",
          unsafe_allow_html=True,
      )

    if st.button(
        "🚀 7 Günlük Kişiselleştirilmiş Programımı Oluştur", type="primary"
    ):
      if is_mufredat_yuzde100 and not deneme_girmis_mi:
        st.warning(
            "⚠️ Müfredatınız %100 tamamlanmış! Telafi programı oluşturabilmek"
            " için lütfen öncelikle Tab 2'den en az 1 deneme analizi giriniz."
        )
      else:
        with get_connection() as conn:
          cursor = conn.cursor()
          cursor.execute(
              "DELETE FROM calisma_programi_gorevler WHERE ogrenci_id = ?",
              (current_user["id"],),
          )
          gunler = [
              "Pazartesi",
              "Salı",
              "Çarşamba",
              "Perşembe",
              "Cuma",
              "Cumartesi",
              "Pazar",
          ]

          backlog = []

          # 1. Deneme Alarmları ve Eksik Konular
          for cat_name, val_list in alarmlar_db.items():
            alarm_skor = (
                100.0
                if cat_name == "siyah"
                else (
                    80.0
                    if cat_name == "kirmizi"
                    else (10.0 if cat_name == "mor" else 40.0)
                )
            )
            for item in val_list:
              kredi = SORU_AGIRLIKLARI.get(item["konu"], 10.0)
              neden_str = item.get("neden", "Konu Eksikliği")
              neden_carpan = (
                  100.0
                  if neden_str == "Konu Eksikliği"
                  else (80.0 if "İki Şık" in neden_str else 40.0)
              )

              # P_score = (Çıkmış Soru Kredisi * 0.8) + (Alarm * 0.1) + (Neden * 0.1)
              p_score = (
                  (kredi * 0.8) + (alarm_skor * 0.1) + (neden_carpan * 0.1)
              )
              backlog.append({
                  "p_score": p_score,
                  "ders": item["ders"],
                  "makro": "Deneme Telafisi",
                  "mikro": item["konu"],
                  "neden": neden_str,
              })

          # 2. Tamamlanmamış Müfredat Konuları
          df_bilinen_tab4 = pd.read_sql_query(
              "SELECT ders, mikro_konu FROM konu_durumlari_detay WHERE"
              " ogrenci_id = ? AND durum = 'Biliyorum'",
              conn,
              params=(current_user["id"],),
          )
          bilinen_mikro_set = set(
              zip(df_bilinen_tab4["ders"], df_bilinen_tab4["mikro_konu"])
          )

          for d_ad, m_dict in aktif_mufredat_hiyerarsisi.items():
            if isinstance(m_dict, dict):
              for mak_ad, mik_l in m_dict.items():
                if isinstance(mik_l, list):
                  for mik_ad in mik_l:
                    if (d_ad, mik_ad) not in bilinen_mikro_set and not any(
                        b["mikro"] == mik_ad for b in backlog
                    ):
                      kredi = SORU_AGIRLIKLARI.get(mak_ad, 8.0)
                      p_score = (kredi * 0.8) + (50.0 * 0.1) + (50.0 * 0.1)
                      backlog.append({
                          "p_score": p_score,
                          "ders": d_ad,
                          "makro": mak_ad,
                          "mikro": mik_ad,
                          "neden": "Önemli Müfredat Konusu",
                      })

          backlog.sort(key=lambda x: x["p_score"], reverse=True)

          # Gün gün görev dağıtımı
          for idx, g in enumerate(gunler):
            tarih_dt = get_tr_now() + timedelta(days=idx)
            tarih_str = tarih_dt.strftime("%Y-%m-%d")

            # A) HER GÜNE ZORUNLU PARAGRAF RUTİNİ
            cursor.execute(
                """INSERT INTO calisma_programi_gorevler 
                               (ogrenci_id, gun, ders, makro_konu, mikro_konu, gorev_tanimi, hedef_soru, pedagoji_turu, durum, tarih) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    current_user["id"],
                    g,
                    "TYT Türkçe",
                    "Paragraf Rutini",
                    "Günlük Seri Paragraf",
                    (
                        f"📖 GÜNLÜK RUTİN: {günlük_paragraf_hedef} Paragraf"
                        f" Sorusu Çöz (~{int(günlük_paragraf_hedef * 1.5)} Dk"
                        " Süre Takipli)"
                    ),
                    günlük_paragraf_hedef,
                    "Ezber",
                    tarih_str,
                ),
            )

            # B) GÜNLÜK ANA GÖREV BLOKLARININ KAPASİTEYE GÖRE YERLEŞTİRİLMESİ
            for b_idx in range(ana_gorev_blok_sayisi):
              if backlog:
                curr_item = backlog.pop(0)
              else:
                curr_item = {
                    "ders": "TYT Matematik",
                    "makro": "Genel Tekrar",
                    "mikro": "Seri Problem & Geometri Provası",
                    "neden": "Rutin",
                }

              is_ezber = curr_item["ders"] in EZBER_DERSLERI
              pedagoji_turu = "Ezber" if is_ezber else "Pekiştirme"

              # Soru Hesabı: Öğrencinin günlük zaman-soru kapasitesine göre ayarlanır
              slot_soru = blok_basi_soru_bütcesi
              slot_dakika = int(slot_soru * 1.5)

              if is_ezber:
                tanim = (
                    f"📝 ÖZET ÇIKART & NOT AL ➔ {slot_soru} Soru Çöz"
                    f" (~{slot_dakika} Dk | Odak: {curr_item['neden']})"
                )
              else:
                tanim = (
                    f"📌 PEKİŞTİRME & SORU ÇÖZÜMÜ ➔ Formül Açık {slot_soru} Soru"
                    f" Çöz (~{slot_dakika} Dk | Odak: {curr_item['neden']})"
                )

              cursor.execute(
                  """INSERT INTO calisma_programi_gorevler 
                               (ogrenci_id, gun, ders, makro_konu, mikro_konu, gorev_tanimi, hedef_soru, pedagoji_turu, durum, tarih) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                  (
                      current_user["id"],
                      g,
                      curr_item["ders"],
                      curr_item["makro"],
                      curr_item["mikro"],
                      tanim,
                      slot_soru,
                      pedagoji_turu,
                      tarih_str,
                  ),
              )

              # EZBER DERSİ İÇİN 1 HAFTA SONRASINA (7 GÜN) TEKRAR GÖREVİ EKLEME
              if is_ezber:
                gelecek_7_gun = (tarih_dt + timedelta(days=7)).strftime(
                    "%Y-%m-%d"
                )
                gelecek_gun_ad = gunler[(idx + 7) % 7]
                tek_tanim = (
                    "🔄 1 HAFTA TEKRARI:"
                    f" '{curr_item['mikro']}' için çıkardığın özel notları 20 dk"
                    " tekrar et."
                )
                cursor.execute(
                    """INSERT INTO calisma_programi_gorevler 
                                   (ogrenci_id, gun, ders, makro_konu, mikro_konu, gorev_tanimi, hedef_soru, pedagoji_turu, durum, tarih) 
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                    (
                        current_user["id"],
                        gelecek_gun_ad,
                        curr_item["ders"],
                        curr_item["makro"],
                        curr_item["mikro"],
                        tek_tanim,
                        0,
                        "Tekrar",
                        gelecek_7_gun,
                    ),
                )

          conn.commit()
        log_islem(
            current_user["id"],
            "CREATE_SPRINT_PROGRAM",
            "Dinamik telafi programı oluşturuldu.",
        )
        st.success(
            "🎉 P_score Öncelikleri ve 1.5 dk/Soru Kapasitesine Göre 7 Günlük"
            " Özel Çalışma Programınız Oluşturuldu!"
        )
        st.rerun()

  with col_p2:
    st.subheader("🎯 Tahmini Net & Sıralama Kazanımı")
    with get_connection() as conn:
      df_program = pd.read_sql_query(
          "SELECT makro_konu, mikro_konu, hedef_soru, durum FROM"
          " calisma_programi_gorevler WHERE ogrenci_id = ?",
          conn,
          params=(current_user["id"],),
      )
      df_bilinen_net = pd.read_sql_query(
          "SELECT mikro_konu FROM konu_durumlari_detay WHERE ogrenci_id = ? AND"
          " durum = 'Biliyorum'",
          conn,
          params=(current_user["id"],),
      )
    bilinen_set_net = set(df_bilinen_net["mikro_konu"].tolist())

    toplam_dinamik_katki = 0.0
    if not df_program.empty:
      for _, r in df_program.iterrows():
        kredi = SORU_AGIRLIKLARI.get(r["makro_konu"], 8.0)
        carpan = 0.25 if r["mikro_konu"] in bilinen_set_net else 1.0
        katki = (kredi / 20.0) * (r["hedef_soru"] / 150.0) * carpan
        toplam_dinamik_katki += katki

      min_net_katki = round(toplam_dinamik_katki * 0.7, 1)
      max_net_katki = round(toplam_dinamik_katki * 1.2, 1)
      st.info(
          "💡 **Beklanan Net Artışı:** **+"
          f"{min_net_katki} Net – +{max_net_katki} Net**"
      )
    else:
      min_net_katki, max_net_katki = 0.0, 0.0
      st.info("💡 Program henüz oluşturulmadı.")

    st.markdown(
        """<div class="simulator-card"><h4>🏆 Gelecek Net & Sıralama Tahmini</h4></div>""",
        unsafe_allow_html=True,
    )
    with get_connection() as conn:
      df_son_deneme = pd.read_sql_query(
          "SELECT MAX(net_bilgisi) as son_net FROM deneme_konu_yanlislari WHERE"
          " ogrenci_id = ?",
          conn,
          params=(current_user["id"],),
      )
    mevcut_net = (
        df_son_deneme["son_net"].iloc[0]
        if not df_son_deneme.empty
        and df_son_deneme["son_net"].iloc[0] is not None
        else 65.0
    )
    tahmini_gelecek_net = round(mevcut_net + min_net_katki, 1)

    alan = current_user["hedef_alan"]
    if alan == "Sayısal":
      base_rank = max(100, int(500000 * (1 - (mevcut_net / 115.0) ** 2)))
      proj_rank = max(
          100, int(500000 * (1 - (tahmini_gelecek_net / 115.0) ** 2))
      )
    elif alan == "Eşit Ağırlık":
      base_rank = max(100, int(400000 * (1 - (mevcut_net / 110.0) ** 2)))
      proj_rank = max(
          100, int(400000 * (1 - (tahmini_gelecek_net / 110.0) ** 2))
      )
    else:
      base_rank = max(100, int(300000 * (1 - (mevcut_net / 100.0) ** 2)))
      proj_rank = max(
          100, int(300000 * (1 - (tahmini_gelecek_net / 100.0) ** 2))
      )

    col_s1, col_s2 = st.columns(2)
    with col_s1:
      st.metric("📊 Mevcut Tahmini Sıralama", f"~{base_rank:,} / {alan}")
    with col_s2:
      st.metric(
          "🚀 Program Sonrası Tahmin",
          f"~{proj_rank:,} / {alan}",
          delta=f"-{base_rank - proj_rank:,} Derece İlerleme",
      )

  st.markdown("---")
  st.subheader("📋 7 Günlük Detaylı Çalışma Çizelgesi")
  with get_connection() as conn:
    df_program_full = pd.read_sql_query(
        "SELECT id, gun, ders, makro_konu, mikro_konu, gorev_tanimi, hedef_soru,"
        " pedagoji_turu, durum FROM calisma_programi_gorevler WHERE ogrenci_id"
        " = ?",
        conn,
        params=(current_user["id"],),
    )

  if not df_program_full.empty:
    biten_gorev = len(df_program_full[df_program_full["durum"] == 1])
    toplam_gorev = len(df_program_full)
    p_yuzde = (
        int((biten_gorev / toplam_gorev) * 100) if toplam_gorev > 0 else 0
    )

    st.write(
        f"**Tamamlanan Görev Oranı:** %{p_yuzde} ({biten_gorev}/{toplam_gorev}"
        " Görev Bitti)"
    )
    st.progress(p_yuzde / 100.0)

    gun_listesi = [
        "Pazartesi",
        "Salı",
        "Çarşamba",
        "Perşembe",
        "Cuma",
        "Cumartesi",
        "Pazar",
    ]
    gun_tablari = st.tabs(gun_listesi)

    for g_idx, g_ad in enumerate(gun_listesi):
      with gun_tablari[g_idx]:
        df_gunluk = df_program_full[df_program_full["gun"] == g_ad]
        if not df_gunluk.empty:
          for _, row in df_gunluk.iterrows():
            p_turu = row["pedagoji_turu"]

            if p_turu == "Tekrar":
              st.markdown(
                  f"""<div class="pedagoji-card-tekrar">🔄 <b>[1 HAFTA SONRA TEKRAR GÖREVİ]</b> {row['ders']} - {row['mikro_konu']}<br>• <i>Yöntem:</i> {row['gorev_tanimi']}</div>""",
                  unsafe_allow_html=True,
              )
            elif p_turu == "Ezber":
              st.markdown(
                  f"""<div class="pedagoji-card-ezber">🟡 <b>[TEKRAR VE NOT ALMAYA DAYALI DERS]</b> {row['ders']} - {row['mikro_konu']}<br>• <i>Yöntem:</i> {row['gorev_tanimi']}</div>""",
                  unsafe_allow_html=True,
              )
            else:
              st.markdown(
                  f"""<div class="pedagoji-card-pekistirme">🟢 <b>[UYGULAMA VE SORU DERSİ]</b> {row['ders']} - {row['mikro_konu']}<br>• <i>Yöntem:</i> {row['gorev_tanimi']}</div>""",
                  unsafe_allow_html=True,
              )

            col_g1, col_g2 = st.columns([3, 1])
            with col_g1:
              st.write(
                  f"📌 **{row['makro_konu']}** ➔ *{row['mikro_konu']}*"
              )
            with col_g2:
              is_t = bool(row["durum"])
              chk_g = st.checkbox(
                  "Bitti", value=is_t, key=f"prog_chk_{row['id']}"
              )
              if chk_g != is_t:
                with get_connection() as conn:
                  cursor = conn.cursor()
                  cursor.execute(
                      "UPDATE calisma_programi_gorevler SET durum = ? WHERE"
                      " id = ?",
                      (1 if chk_g else 0, row["id"]),
                  )
                  conn.commit()
                st.rerun()
            st.markdown("---")
        else:
          st.info(f"🎉 {g_ad} günü hafif tekrar veya dinlenme günüdür.")
  else:
    st.info(
        "💡 Henüz bir çalışma programı oluşturulmadı. Yukarıdaki parametreleri"
        " seçip **🚀 7 Günlük Kişiselleştirilmiş Programımı Oluştur** butonuna"
        " basınız."
    )

with tab5:
  st.header("🛒 Birebir Özel Ders Destek & Performans Raporu")
  pazar_tab1, pazar_tab2 = st.tabs(
      ["🤝 1. Birebir Özel Ders Destek Talebi", "📄 2. Performans Raporu Al"]
  )

  with pazar_tab1:
    st.subheader("🎯 Acil Destek Gerektiren Konular")
    st.write(
        "Sistemde tespit edilen kritik eksikleriniz için Koçunuzdan Özel Ders"
        " Talebi Oluşturabilirsiniz:"
    )
    acil_konular = (
        alarmlar_db["siyah"]
        + alarmlar_db["kirmizi"]
        + alarmlar_db["mor"]
        + alarmlar_db["turuncu"]
    )

    if acil_konular:
      with get_connection() as conn:
        df_mevcut_talepler = pd.read_sql_query(
            "SELECT ders, konu FROM pazaryeri_talepler WHERE ogrenci_id = ?",
            conn,
            params=(current_user["id"],),
        )
      talep_set = set(
          zip(df_mevcut_talepler["ders"], df_mevcut_talepler["konu"])
      )

      for idx, k in enumerate(acil_konular):
        st.markdown(
            f"""<div class="pazar-kart"><h4>🚨 {k['ders']} - {k['konu']}</h4><p><b>Tespit Edilen Durum:</b> {k['detay']}</p><p><b>Önerilen Seans:</b> 45 Dk Birebir Özel Ders Seansı</p></div>""",
            unsafe_allow_html=True,
        )
        is_requested = (k["ders"], k["konu"]) in talep_set

        if is_requested:
          st.button(
              f"✔️ '{k['konu']}' İçin Talep Alındı (Koç İnceliyor)",
              key=f"pazar_btn_dis_{idx}_{k['ders']}_{k['konu']}",
              disabled=True,
          )
        else:
          if st.button(
              f"📩 '{k['konu']}' İçin Özel Ders Talebi Oluştur",
              key=f"pazar_btn_{idx}_{k['ders']}_{k['konu']}",
          ):
            simdi_str = get_tr_now().strftime("%Y-%m-%d %H:%M:%S")
            with get_connection() as conn:
              cursor = conn.cursor()
              cursor.execute(
                  "INSERT INTO pazaryeri_talepler (ogrenci_id, ders, konu,"
                  " alarm_turu, talep_tarihi) VALUES (?, ?, ?, 'Kritik Alarm',"
                  " ?)",
                  (current_user["id"], k["ders"], k["konu"], simdi_str),
              )
              conn.commit()
            log_islem(
                current_user["id"],
                "REQUEST_TUTORING",
                f"{k['ders']} -> {k['konu']}",
            )
            st.success(
                f"✔️ '{k['konu']}' için özel ders talebiniz koçunuza iletildi!"
            )
            st.rerun()
    else:
      st.success(
          "🎉 Şu anda acil özel ders gerektiren kritik bir konunuz yok!"
      )

    st.markdown("---")
    st.subheader("📜 Mevcut Özel Ders Talepleriniz")
    with get_connection() as conn:
      df_talepler = pd.read_sql_query(
          "SELECT ders, konu, alarm_turu, talep_tarihi, durum FROM"
          " pazaryeri_talepler WHERE ogrenci_id = ?",
          conn,
          params=(current_user["id"],),
      )
    if not df_talepler.empty:
      st.dataframe(df_talepler, use_container_width=True)
    else:
      st.info("Henüz oluşturulmuş bir özel ders talebiniz bulunmuyor.")

  with pazar_tab2:
    st.subheader("📄 Performans Raporu İndirme Alanı")
    col_ex1, col_ex2 = st.columns(2)
    with col_ex1:
      st.markdown("#### 📊 Excel / CSV Tablosu İndir")
      with get_connection() as conn:
        df_deneme_exp = pd.read_sql_query(
            "SELECT * FROM deneme_konu_yanlislari WHERE ogrenci_id = ?",
            conn,
            params=(current_user["id"],),
        )
      csv_buffer = df_deneme_exp.to_csv(index=False).encode("utf-8")
      st.download_button(
          label="📥 Deneme Yanlışları Listesini İndir (CSV)",
          data=csv_buffer,
          file_name=(
              f"KARAKOÇ_Deneme_Yanlislari_{get_tr_now().strftime('%Y%m%d')}.csv"
          ),
          mime="text/csv",
      )

    with col_ex2:
      st.markdown("#### 📝 Yazdırılabilir Özet Koçluk Raporu")
      rapor_text = f"""
====================================================
      KARAKOÇ YKS AKILLI KOÇLUK PERFORMANS RAPORU
====================================================
Tarih: {get_tr_now().strftime('%Y-%m-%d %H:%M')}
Öğrenci: {current_user['ad']} (Kullanıcı Adı: {current_user['kullanici_adi']})
Hedef Alan: {current_user['hedef_alan']} | Sınıf: {current_user['sinif_seviyesi']}
Gelişim Skoru: %{saglik_skoru}
TYT Tamamlanma Oranı: %{tyt_orani}
AYT Tamamlanma Oranı: %{ayt_orani}
Müfredat İlerleme Durumu: %{delta_yuzde}

----------------------------------------------------
1. AKILLI ALARM VE RİSK DURUMU:
----------------------------------------------------
- Siyah Alarmlar (Kritik Artış): {len(alarmlar_db['siyah'])} adet
- Kırmızı Alarmlar (Dikkat): {len(alarmlar_db['kirmizi'])} adet
- Mor Alarmlar (Kronik Yanlış): {len(alarmlar_db['mor'])} adet
- Turuncu Alarmlar (Ön Koşul Tıkanması): {len(alarmlar_db['turuncu'])} adet
- Mavi Alarmlar (Takvim Geriliği): {len(alarmlar_db['mavi'])} adet

====================================================
            """
      st.download_button(
          label="📄 Özet Raporu Metin Formatında İndir",
          data=rapor_text.encode("utf-8"),
          file_name=(
              f"KARAKOÇ_Kocluk_Raporu_{get_tr_now().strftime('%Y%m%d')}.txt"
          ),
          mime="text/plain",
      )