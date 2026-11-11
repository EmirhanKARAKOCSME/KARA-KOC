import hashlib
import os
import re
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
# BİLDİRİM / FLASH MESSAGE YÖNETİMİ
# ==============================================================================
def set_flash_message(msg_type: str, message: str):
    st.session_state[f"flash_{msg_type}"] = message


def render_flash_messages():
    for mtype in ["success", "warning", "error", "info"]:
        key = f"flash_{mtype}"
        if key in st.session_state and st.session_state[key]:
            getattr(st, mtype)(st.session_state[key])
            st.session_state[key] = None


render_flash_messages()


# ==============================================================================
# GÜVENLİK VE KRİPTOGRAFİ (PBKDF2-HMAC-SHA256)
# ==============================================================================
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, 100000
    )
    return salt.hex() + ":" + pwd_hash.hex()


def verify_password(stored_password_hash: str, provided_password: str) -> bool:
    if not stored_password_hash or ":" not in stored_password_hash:
        return False
    try:
        salt_hex, hash_hex = stored_password_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        stored_pwd_hash = bytes.fromhex(hash_hex)
        new_pwd_hash = hashlib.pbkdf2_hmac(
            "sha256", provided_password.encode("utf-8"), salt, 100000
        )
        return stored_pwd_hash == new_pwd_hash
    except Exception:
        return False


# ==============================================================================
# ARAYÜZ VE ÖZELLEŞTİRİLMİŞ STİL (CSS)
# ==============================================================================
st.markdown(
    """
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        font-weight: 600;
        height: 3em;
        touch-action: manipulation;
    }
    
    .card-mega-buttons div[data-testid="stHorizontalBlock"] {
        gap: 8px !important;
    }
    
    .card-mega-buttons div[data-testid="stColumn"]:first-child button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        color: #ffffff !important;
        border: none !important;
        font-size: 1.5rem !important;
        font-weight: 800 !important;
        height: 100px !important;
        border-radius: 14px !important;
        box-shadow: 0 4px 14px rgba(16, 185, 129, 0.3) !important;
    }
    
    .card-mega-buttons div[data-testid="stColumn"]:last-child button {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
        color: #ffffff !important;
        border: none !important;
        font-size: 1.5rem !important;
        font-weight: 800 !important;
        height: 100px !important;
        border-radius: 14px !important;
        box-shadow: 0 4px 14px rgba(239, 68, 68, 0.3) !important;
    }

    .single-card-container {
        background-color: #ffffff;
        border: 2px solid #6366f1;
        border-radius: 16px;
        padding: 24px 16px;
        box-shadow: 0 8px 24px rgba(99, 102, 241, 0.12);
        margin: 12px 0;
        text-align: center;
    }
    .card-ders-title {
        color: #4f46e5;
        font-size: 1rem;
        font-weight: 700;
        text-transform: uppercase;
        background-color: #e0e7ff;
        display: inline-block;
        padding: 4px 14px;
        border-radius: 12px;
    }
    .card-konu-title {
        color: #0f172a;
        font-size: 1.8rem;
        font-weight: 800;
        margin: 12px 0;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        overflow-x: auto;
    }
    .stTabs [data-baseweb="tab"] {
        height: 42px;
        font-size: 0.9rem;
        font-weight: 600;
        border-radius: 8px;
    }

    .maarif-rozet {
        background-color: #e3f2fd;
        color: #0d47a1;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8em;
        font-weight: bold;
    }
    .klasik-rozet {
        background-color: #f3e5f5;
        color: #4a148c;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8em;
        font-weight: bold;
    }
    .streak-card {
        background-color: #fff3e0;
        border: 1.5px solid #ffe0b2;
        padding: 10px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        color: #e65100;
        margin-bottom: 10px;
    }
    .alarm-card-black {
        background-color: #111827;
        color: #f3f4f6;
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #9ca3af;
        margin-bottom: 12px;
    }
    .alarm-card-danger {
        background-color: #fef2f2;
        color: #991b1b;
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #ef4444;
        margin-bottom: 12px;
    }
    .alarm-card-purple {
        background-color: #faf5ff;
        color: #581c87;
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #a855f7;
        margin-bottom: 12px;
    }
    .alarm-card-warning {
        background-color: #fffbe6;
        color: #92400e;
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #f59e0b;
        margin-bottom: 12px;
    }
    .alarm-card-info {
        background-color: #eff6ff;
        color: #1e40af;
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #3b82f6;
        margin-bottom: 12px;
    }
    .sim-card {
        background-color: #f8fafc;
        border: 1.5px solid #e2e8f0;
        padding: 16px;
        border-radius: 12px;
        margin-top: 8px;
    }
    .focus-task-card {
        background-color: #ffffff;
        border: 1.5px solid #cbd5e1;
        border-left: 5px solid #6366f1;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    </style>
""",
    unsafe_allow_html=True,
)


# ==============================================================================
# VERİTABANI VE İLİŞKİSEL YÖNETİM
# ==============================================================================
def get_connection():
    conn = sqlite3.connect(
        "yks_veritabani.db", timeout=20, check_same_thread=False
    )
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def log_islem(ogrenci_id, islem, detay):
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
                hedef_alan TEXT DEFAULT 'Sayısal',
                sinif_seviyesi TEXT DEFAULT '12. Sınıf',
                alan_kilitli INTEGER DEFAULT 0,
                son_sinif_atlatma_yili INTEGER DEFAULT 0,
                rol TEXT DEFAULT 'ogrenci',
                hesap_durumu TEXT DEFAULT 'Aktif',
                lisans_bitis TEXT,
                streak_count INTEGER DEFAULT 1,
                son_aktif_tarih TEXT,
                diploma_notu REAL DEFAULT 100.0
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
                deneme_kategorisi TEXT DEFAULT 'Genel Deneme',
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

        # Varsayılan Admin Kaydı
        cursor.execute(
            "SELECT id FROM ogrenciler WHERE kullanici_adi = 'admin' OR tc_no ="
            " '99999999999'"
        )
        admin_user = cursor.fetchone()
        default_admin_pass = hash_password("karakoc123")

        if not admin_user:
            cursor.execute(
                """INSERT INTO ogrenciler 
                   (tc_no, kullanici_adi, sifre_hash, ad, hedef_alan, sinif_seviyesi, alan_kilitli, rol, hesap_durumu, diploma_notu) 
                   VALUES ('99999999999', 'admin', ?, 'Emirhan Karakoç (Koç)', 'Yönetim', 'Koç', 1, 'admin', 'Aktif', 100.0)""",
                (default_admin_pass,),
            )
        conn.commit()


init_db()

def sanitize_key(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(text))

def update_user_streak(user_id):
    with get_connection() as c:
        cur = c.cursor()
        cur.execute(
            "SELECT streak_count, son_aktif_tarih FROM ogrenciler WHERE id ="
            " ?",
            (user_id,),
        )
        res = cur.fetchone()
        if not res:
            return 1

        streak_count, son_aktif_str = res
        bugun_str = get_tr_now().strftime("%Y-%m-%d")

        if not son_aktif_str:
            cur.execute(
                "UPDATE ogrenciler SET streak_count = 1, son_aktif_tarih = ?"
                " WHERE id = ?",
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
                "UPDATE ogrenciler SET streak_count = ?, son_aktif_tarih = ?"
                " WHERE id = ?",
                (new_streak, bugun_str, user_id),
            )
            c.commit()
        elif fark > 1:
            new_streak = 1
            cur.execute(
                "UPDATE ogrenciler SET streak_count = 1, son_aktif_tarih = ?"
                " WHERE id = ?",
                (bugun_str, user_id),
            )
            c.commit()

        return new_streak


# ==============================================================================
# MÜFREDAT VE KONU ÇALIŞMA SÜRELERİ (DAKİKA)
# ==============================================================================
KONU_SURELERI_DK = {
    "Gerçek Sayıların Üslü ve Köklü Gösterimleri": 80,
    "Gerçek Sayı Aralıkları ile İşlemler": 60,
    "Sayı Kümeleri ve İşlem Özellikleri": 50,
    "İki Kare Farkı ve Tamkare Özdeşlikleri": 70,
    "Gerçek Sayılarda Tanımlı Doğrusal Fonksiyonlar ve Mutlak Değer": 90,
    "Fonksiyonların Nitel Özellikleri": 70,
    "Doğrusal Fonksiyonlarla İfade Edilen Denklem ve Eşitsizlikler": 75,
    "Algoritma Temelli Problemler": 60,
    "Mantık Bağlaçları ve Niceleyiciler": 60,
    "Üçgende Açı ve Kenar Özellikleri": 70,
    "Üçgende Açı İlişkileri": 60,
    "Üçgende Kenar İlişkileri": 60,
    "Geometrik Şekillerin Dönüşümleri (Yansıma, Öteleme, Dönme)": 60,
    "Üçgenlerde Eşlik ve Benzerlik Koşulları": 80,
    "Tek Nicel Değişken İçeren İstatistiksel Problem Oluşturma": 50,
    "Verileri Toplama ve Analize Hazırlama": 50,
    "Bulgulara Ulaşma ve Yorumlama": 60,
    "İstatistiksel Görsel ve Çıkarımları Değerlendirme": 50,
    "Günlük Hayatta Kimya ve Güvenlik": 40,
    "Kimyanın Alt Disiplinleri ve Kariyer": 40,
    "Atom Teorileri ve Elektron Dizilimi": 70,
    "Periyodik Tablo ve Periyodik Özellikler": 75,
    "Kimyasal Bağlar (Metalik, İyonik, Kovalent)": 80,
    "Lewis Nokta Yapısı ve Polarlık": 70,
    "Moleküller Arası Etkileşimler": 60,
    "Katılar, Sıvılar ve Özellikleri": 60,
    "Nanoparçacıklar ve Ekolojik Sürdürülebilirlik": 50,
    "Yeşil Kimyanın Atık Önleme İlkesi": 45,
    "Fizik Bilimi ve Alt Dalları": 40,
    "Fizik Bilimine Yön Verenler ve Kariyer Keşfi": 40,
    "Temel ve Türetilmiş Nicelikler": 50,
    "Skaler ve Vektörel Nicelikler": 60,
    "Doğadaki Temel Kuvvetler ve Hareket Türleri": 60,
    "Basınç ve Sıvılarda Basınç": 70,
    "Açık Hava Basıncı ve Kaldırma Kuvveti": 80,
    "Bernoulli İlkesi": 60,
    "Enerji, Isı, Öz Isı ve Sıcaklık İlişkisi": 70,
    "Hâl Değişimi ve Isıl Denge": 75,
    "Isı Aktarım Yolları ve İletim Hızı": 50,
    "Biyolojinin Önemi ve Bilim Etiği": 40,
    "Canlıların Ortak Özellikleri": 50,
    "Sınıflandırma ve Biyoçeşitlilik (3 Domain)": 60,
    "İnorganik Moleküller (Su ve Mineraller)": 50,
    "Organik Moleküller (Karbonhidrat, Yağ, Protein, Nükleik Asit, Vitamin)": 90,
    "Hücre Yapısı, Organeller ve Çekirdek": 80,
    "Hücre Zarından Madde Geçişleri": 75,
    "Hücreden Organ ve Sistem Organizasyonuna": 50,
    "Edebiyatın Sanat ve Bilimle İlişkisi": 40,
    "İletişim Öğeleri ve Göstergeler": 40,
    "Dilin İşlevleri ve Kullanım Türleri": 45,
    "Hikaye Türleri ve Gelişimi": 50,
    "Yazım ve Noktalama": 60,
    "İsimler": 50,
    "Şiir Bilgisi ve Türleri": 60,
    "Sıfatlar": 50,
    "Masal ve Fabl Özellikleri": 45,
    "Edat, Bağlaç, Ünlem": 50,
    "Roman Türleri ve Yapı Unsurları": 50,
    "Zamirler": 50,
    "Tiyatro Terimleri ve Geleneksel Türk Tiyatrosu": 50,
    "Zarflar": 50,
    "Biyografi ve Otobiyografi": 45,
    "CV, Dilekçe ve Tutanak": 40,
    "Fiiller": 60,
    "Mektup Türleri ve E-Posta": 40,
    "Günlük ve Blog": 40,
    "Tarih Öğrenmenin Faydaları ve Doğası": 40,
    "Tarihsel Bilgi Üretimi ve Dijitalleşme": 40,
    "Tarım Devriminin Yerleşmeye Etkisi": 50,
    "Eski Çağda Yönetim, Hukuk ve İnançlar": 50,
    "Türklerde Konargöçer Yaşam": 50,
    "Orta Çağ Göçleri ve Devlet Yapıları": 50,
    "Orta Çağ Ticaret Yolları ve Bilim Havzaları": 50,
    "Coğrafya Biliminin Konusu ve Gelişimi": 40,
    "Haritalar ve Türkiye'nin Konumu": 60,
    "Mekânsal Bilgi Teknolojileri Bileşenleri": 45,
    "Hava Olayları ve İklim Sistemleri": 60,
    "İklim Değişiklikleri": 50,
    "Nüfusun Tarihsel Değişimi ve Dağılışı": 50,
    "Demografik Dönüşüm ve Piramitler": 50,
    "Ekonomik Faaliyetleri Etkileyen Coğrafi Faktörler": 45,
    "Afet Türleri ve Bütüncül Afet Yönetimi": 45,
    "Bölge ve Bölge Sınırı Kavramı": 40,
    "İnsanın Yaratılışı, İbadet ve Dua": 40,
    "İman Esasları ve Toplumsal Boyutu": 40,
    "Temel İbadetler ve İnsan": 40,
    "Ahlakın Temel Unsurları ve Tutumlar": 40,
    "Hz. Muhammed'in Örnekliği ve Peygamberliği": 40,
    "Sözcükte Anlam": 40,
    "Söz Yorumu": 45,
    "Deyim ve Atasözü": 50,
    "Cümlede Anlam İlişkileri": 45,
    "Cümle Yorumu ve Kavramlar": 50,
    "Paragrafta Anlatım Teknikleri": 50,
    "Paragrafta Düşünceyi Geliştirme Yolları": 45,
    "Paragrafta Yapı": 60,
    "Paragrafta Konu-Ana Düşünce": 60,
    "Paragrafta Yardımcı Düşünce": 60,
    "Ses Bilgisi": 50,
    "Yazım Kuralları": 70,
    "Noktalama İşaretleri": 60,
    "Sözcükte Yapı ve Ekler": 75,
    "Edat – Bağlaç – Ünlem": 50,
    "Fiilde Anlam": 45,
    "Ek Fiil": 50,
    "Fiilimsi": 60,
    "Fiilde Çatı": 50,
    "Cümlenin Ögeleri": 75,
    "Anlatım Bozukluğu": 60,
    "Temel Kavramlar": 80,
    "Sayı Basamakları": 60,
    "Bölme ve Bölünebilme": 70,
    "EBOB – EKOK": 70,
    "Rasyonel Sayılar": 60,
    "Basit Eşitsizlikler": 65,
    "Mutlak Değer": 75,
    "Üslü Sayılar": 80,
    "Köklü Sayılar": 85,
    "Çarpanlara Ayırma": 80,
    "Oran Orantı": 60,
    "Denklem Çözme": 60,
    "Sayı Problemleri": 90,
    "Kesir Problemleri": 70,
    "Yaş Problemleri": 60,
    "Hareket Hız Problemleri": 90,
    "İşçi Emek Problemleri": 70,
    "Yüzde-Kâr-Zarar Problemleri": 90,
    "Karışım Problemleri": 75,
    "Grafik Problemleri": 70,
    "Kümeler – Kartezyen Çarpım": 70,
    "Mantık": 50,
    "Fonksiyonlar": 90,
    "Permütasyon ve Kombinasyon": 75,
    "Olasılık": 80,
    "Veri – İstatistik": 60,
    "Temel Kavramlar ve Doğruda Açılar": 50,
    "Üçgende Açılar": 60,
    "Dik Üçgen ve Pisagor": 75,
    "İkizkenar ve Eşkenar Üçgen": 70,
    "Açıortay ve Kenarortay": 70,
    "Üçgende Eşlik ve Benzerlik": 90,
    "Üçgende Alan": 70,
    "Çokgenler": 60,
    "Dörtgenler ve Özel Dörtgenler": 60,
    "Deltoid": 45,
    "Paralelkenar ve Eşkenar Dörtgen": 75,
    "Dikdörtgen ve Kare": 80,
    "Yamuk": 70,
    "Fizik Bilimine Giriş": 40,
    "Madde ve Özellikleri": 70,
    "Dayanıklılık ve Akışkanlar": 60,
    "Hareket ve Kuvvet": 75,
    "Newton'un Hareket Yasaları": 80,
    "Basınç": 75,
    "Sıvıların Kaldırma Kuvveti": 80,
    "Isı, Sıcaklık ve Genleşme": 80,
    "Elektrostatik": 70,
    "Elektrik Akımı ve Devreler": 85,
    "Mıknatıslar ve Manyetik Alan": 60,
    "Aydınlanma ve Aynalar": 75,
    "Kırılma ve Mercekler": 80,
    "Dalga Harekatı": 70,
    "Kimya Bilimi": 40,
    "Atom Yapısı ve Periyodik Sistem": 80,
    "Kimyasal Türler Arası Etkileşimler": 85,
    "Maddenin Halleri": 70,
    "Kimyanın Temel Kanunları": 70,
    "Mol Kavramı ve Kimyasal Hesaplamalar": 90,
    "Karışımlar ve Ayırma Yöntemleri": 75,
    "Asitler, Bazlar ve Tuzlar": 80,
    "Canlıların Temel Bileşenleri": 85,
    "Canlıların Sınıflandırılması": 85,
    "Mitoz ve Eşeysiz Üreme": 70,
    "Mayoz ve Eşeyli Üreme": 75,
    "Mendelyan Kalıtım": 80,
    "Ekosistem Ekolojisi": 70,
    "Tarih ve Zaman": 40,
    "İnsanlığın İlk Dönemleri": 55,
    "İlk ve Orta Çağlarda Türk Dünyası": 60,
    "İslam Medeniyetinin Doğuşu": 55,
    "Türk-İslam Devletleri": 60,
    "Beylikten Devlete Osmanlı Siyareti": 70,
    "Milli Mücadele ve Atatürkçülük": 80,
    "Doğa ve İnsan": 40,
    "Dünya’nın Şekli ve Hareketleri": 70,
    "Coğrafi Konum": 65,
    "Harita Bilgisi": 75,
    "İklim Bilgisi": 80,
    "Nüfus ve Yerleşme": 60,
    "Türkiye’nin Yer Şekilleri": 75,
    "Ekonomik Faaliyetler": 55,
    "Doğal Afetler ve Çevre": 60,
    "Felsefenin Konusu": 40,
    "Bilgi Felsefesi": 50,
    "Varlık Felsefesi": 50,
    "Ahlak Felsefesi": 50,
    "Bilgi ve İnanç": 40,
    "İslam ve İbadet": 45,
    "Ahlak ve Değerler": 40,
    "Polinomlar ve Çarpanlara Ayırma": 80,
    "İkinci Dereceden Denklemler": 75,
    "Karmaşık Sayılar": 60,
    "Parabol": 70,
    "İkinci Dereceden Eşitsizlik Sistemleri": 70,
    "Yönlü Açılar ve Trigonometrik Oranlar": 90,
    "Trigonometrik Denklemler": 75,
    "Üstel ve Logaritmik Fonksiyonlar": 85,
    "Aritmetik ve Geometrik Diziler": 75,
    "Limit ve Süreklilik": 80,
    "Türev Alma Kuralları": 90,
    "Türevin Geometrik Yorumu ve Maks-Min": 100,
    "Belirsiz İntegral": 80,
    "Belirli İntegral ve Alan Hesabı": 95,
    "Çemberde Açı": 60,
    "Çemberde Uzunluk": 75,
    "Dairede Çevre ve Alan": 70,
    "Noktanın Analitik İncelemesi": 55,
    "Doğrunun Analitik İncelemesi": 80,
    "Dönüşüm Geometrisi": 50,
    "Çemberin Analitik İncelemesi": 75,
    "Prizmalar ve Küp": 70,
    "Silindir ve Koni": 70,
    "Piramit ve Küre": 75,
    "Vektörler ve Bağıl Hareket": 70,
    "Newton'ın Hareket Yasaları": 80,
    "Atışlar": 85,
    "İş-Enerji Korunumu": 75,
    "İtme ve Çizgisel Momentum": 80,
    "Tork ve Dönme Dengesi": 85,
    "Elektriksel Kuvvet ve Elektrik Alan": 75,
    "Elektriksel Potansiyel": 70,
    "Düzgün Elektrik Alan ve Sığaçlar": 75,
    "Manyetik Alan ve Manyetik Kuvvet": 80,
    "İndüksiyon ve Alternatif Akım": 85,
    "Düzgün Çembersel Hareket": 80,
    "Açısal Momentum ve Kepler": 70,
    "Basit Harmonik Hareket": 80,
    "Dalga Mekaniği ve Doppler": 75,
    "Atom Fiziği ve Radyoaktivite": 70,
    "Fotoelektrik Olay": 75,
    "Modern Atom Teorisi": 75,
    "Gazlar ve Ideal Gaz Yasası": 85,
    "Sıvı Çözeltiler ve Çözünürlük": 80,
    "Kimyasal Tepkimelerde Enerji": 75,
    "Tepkime Hızları": 80,
    "Kimyasal Denge": 95,
    "Asit-Baz Dengesi": 90,
    "Çözünürlük Dengesi (KÇÇ)": 75,
    "Redoks ve Elektrokimya": 85,
    "Karbon Kimyasına Giriş": 70,
    "Organik Bileşikler": 120,
    "Sinir Sistemi ve Duyu Organları": 90,
    "Endokrin Sistem": 70,
    "Destek ve Hareket Sistemi": 65,
    "Sindirim Sistemi": 75,
    "Dolaşım ve Bağışıklık Sistemi": 90,
    "Solunum Sistemi": 70,
    "Üriner Sistem": 75,
    "Genden Proteine (Protein Sentezi)": 85,
    "Fotosentez ve Kemosentez": 80,
    "Hücresel Solunum": 85,
    "Bitkisel Dokular ve Organlar": 75,
    "Bitkilerde Büyüme ve Hareket": 70,
    "Komünite ve Popülasyon Ekolojisi": 80,
    "Polinomlar ve Parabol": 85,
    "İkinci Dereceden Eşitsizlikler": 70,
    "Trigonometri": 90,
    "Logaritma ve Diziler": 80,
    "Limit, Türev ve İntegral": 110,
    "Çemberde Açı ve Uzunluk": 75,
    "Analitik Geometri": 80,
    "Katı Cisimler": 70,
    "Şiir Bilgisi ve Edebi Sanatlar": 80,
    "İslamiyet Öncesi ve Geçiş Dönemi Türk Edebiyatı": 60,
    "Halk Edebiyatı": 75,
    "Divan Edebiyatı": 90,
    "Tanzimat ve Servet-i Fünun Edebiyatı": 80,
    "Milli Edebiyat Dönemi": 70,
    "Cumhuriyet Dönemi Edebiyatı": 100,
    "İlk Türk Devletleri ve İslam Medeniyeti": 60,
    "Beylikten Devlete Osmanlı": 70,
    "Dünya Gücü Osmanlı": 75,
    "XX. Yüzyıl Başlarında Osmanlı": 65,
    "Milli Mücadele Dönemi": 80,
    "Atatürk İlkeleri ve İnkılapları": 75,
    "Ekosistem ve Biyoçeşitlilik": 60,
    "Türkiye Ekonomisi ve Bölgeler": 75,
    "Küresel Ticaret ve Çevre": 60,
    "Edebi Sanatlar": 70,
    "Cumhuriyet Dönemi": 100,
    "İlk Uygarlıklar": 60,
    "Osmanlı Merkez Teşkilatı": 75,
    "İki Savaş Arası Dönem": 70,
    "Soğuk Savaş ve XXI. Yüzyıl": 75,
    "Türkiye'nin İklimi ve Yeryüzü Şekilleri": 80,
    "Küresel Örgütler ve Afetler": 65,
    "Felsefi Düşünce": 55,
    "Klasik Mantık ve Mantık-Dil": 75,
    "Sembolik Mantık": 70,
    "Psikolojinin Temel Süreçleri": 75,
    "Öğrenme ve Bellek": 70,
    "Sosyolojiye Giriş ve Toplumsal Yapı": 75,
    "Allah İnsan İlişkisi": 45,
    "Kur'an Kavramları": 50,
    "İslam Düşüncesinde Tasavvufi Yorumlar": 55,
    "Vocabulary & Collocations": 90,
    "Tenses & Modals": 80,
    "Clauses & Conjunctions": 85,
    "Cloze Test & Cümle Tamamlama": 75,
    "İngilizce-Türkçe Çeviri": 60,
    "Paragraf Okuma ve Anlama": 90,
    "Diyalog & Anlamı Bozan Cümle": 65,
}

# ==============================================================================
# ÖN KOŞUL KONTROLLERİ
# ==============================================================================
PEKISTIRME_DERSLERI = [
    "Matematik ve Veri",
    "TYT Matematik",
    "AYT Matematik",
    "TYT Geometri",
    "AYT Geometri",
    "TYT Fizik",
    "AYT Fizik",
    "Gramer ve Kelime",
    "Soru Tipleri",
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
    "TYT Kimya",
    "AYT Kimya",
    "YDT İngilizce",
]


def get_konu_pedagoji_turu(ders_adi, mikro_konu=""):
    if ders_adi in PEKISTIRME_DERSLERI:
        return "Pekiştirme"
    elif ders_adi in EZBER_DERSLERI:
        return "Ezber"
    else:
        return "Pekiştirme"


from typing import List, Dict, Set

SINIF_SEVIYE_SKORU = {
    "9. Sınıf": 1,
    "10. Sınıf": 2,
    "11. Sınıf": 3,
    "12. Sınıf": 4,
    "Mezun": 4
}

def acilabilir_konulari_getir(ogrenci_id: int, db_path: str = "karakoc.db") -> List[Dict[str, str]]:
    """
    Öğrencinin bilinen konularına göre şu an ÇALIŞMAYA UYGUN (kilidi açılmış)
    tüm mikro konuları listeler. Öğrenciye özel çalışma takvimi önerirken kullanılır.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Öğrenci Bilgileri
    cursor.execute("SELECT sinif_seviyesi FROM ogrenciler WHERE id = ?", (ogrenci_id,))
    usr = cursor.fetchone()
    if not usr:
        conn.close()
        return []
    
    sinif_seviyesi = usr[0]
    ogrenci_skoru = SINIF_SEVIYE_SKORU.get(sinif_seviyesi, 4)

    # 2. Tamamlanan Konular
    cursor.execute(
        "SELECT mikro_konu FROM konu_durumlari_detay WHERE ogrenci_id = ? AND durum = 'Biliyorum'",
        (ogrenci_id,)
    )
    bilinenler: Set[str] = set(r[0] for r in cursor.fetchall())
    conn.close()

    onerilen_konular = []

    for konu, kural in ON_KOSULLAR.items():
        # Zaten biliniyorsa tekrar önerme
        if konu in bilinenler:
            continue

        # AYT Matematik Kilidi Kontrolü
        if kural["ders"] == "AYT Matematik" and "Fonksiyonlar" not in bilinenler:
            continue

        # Sınıf Seviyesi Kontrolü
        if ogrenci_skoru < kural.get("min_sinif", 1):
            continue

        # Ön Koşul Tamamlanma Kontrolü
        eksikler = [ok for ok in kural.get("on_kosul", []) if ok not in bilinenler]
        if not eksikler:
            onerilen_konular.append({
                "mikro_konu": konu,
                "ders": kural["ders"],
                "durum": "Çalışmaya Hazır (Kilit Açık)"
            })

    return onerilen_konular

ON_KOSULLAR = {
    # --------------------------------------------------------------------------
    # 1. AYT MATEMATİK & GEOMETRİ (ZORUNLU KİLİT: TYT 'Fonksiyonlar')
    # --------------------------------------------------------------------------
    "Polinomlar ve Çarpanlara Ayırma": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Çarpanlara Ayırma"],
        "min_sinif": 3,
    },
    "İkinci Dereceden Denklemler": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Denklem Çözme"],
        "min_sinif": 3,
    },
    "Karmaşık Sayılar": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "İkinci Dereceden Denklemler"],
        "min_sinif": 3,
    },
    "Parabol": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "İkinci Dereceden Denklemler"],
        "min_sinif": 3,
    },
    "İkinci Dereceden Eşitsizlik Sistemleri": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "İkinci Dereceden Denklemler", "Parabol"],
        "min_sinif": 3,
    },
    "Yönlü Açılar ve Trigonometrik Oranlar": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Dik Üçgen ve Pisagor", "Üçgende Açılar"],
        "min_sinif": 3,
    },
    "Trigonometrik Denklemler": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Yönlü Açılar ve Trigonometrik Oranlar"],
        "min_sinif": 3,
    },
    "Üstel ve Logaritmik Fonksiyonlar": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Üslü Sayılar", "Polinomlar ve Çarpanlara Ayırma"],
        "min_sinif": 3,
    },
    "Aritmetik ve Geometrik Diziler": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Üstel ve Logaritmik Fonksiyonlar"],
        "min_sinif": 3,
    },
    "Limit ve Süreklilik": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Polinomlar ve Çarpanlara Ayırma"],
        "min_sinif": 4,
    },
    "Türev Alma Kuralları": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Limit ve Süreklilik"],
        "min_sinif": 4,
    },
    "Türevin Geometrik Yorumu ve Maks-Min": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Türev Alma Kuralları"],
        "min_sinif": 4,
    },
    "Belirsiz İntegral": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Türev Alma Kuralları"],
        "min_sinif": 4,
    },
    "Belirli İntegral ve Alan Hesabı": {
        "ders": "AYT Matematik",
        "on_kosul": ["Fonksiyonlar", "Belirsiz İntegral"],
        "min_sinif": 4,
    },
    "Dönüşüm Geometrisi": {
        "ders": "AYT Geometri",
        "on_kosul": ["Noktanın Analitik İncelemesi", "Doğrunun Analitik İncelemesi"],
        "min_sinif": 3,
    },
    "Çemberin Analitik İncelemesi": {
        "ders": "AYT Geometri",
        "on_kosul": ["Doğrunun Analitik İncelemesi", "Çemberde Uzunluk"],
        "min_sinif": 4,
    },

    # --------------------------------------------------------------------------
    # 2. TYT MATEMATİK
    # --------------------------------------------------------------------------
    "Sayı Problemleri": {
        "ders": "TYT Matematik",
        "on_kosul": ["Denklem Çözme", "Basit Eşitsizlikler"],
        "min_sinif": 1,
    },
    "Yaş Problemleri": {
        "ders": "TYT Matematik",
        "on_kosul": ["Denklem Çözme"],
        "min_sinif": 1,
    },
    "Hareket Hız Problemleri": {
        "ders": "TYT Matematik",
        "on_kosul": ["Oran Orantı", "Denklem Çözme"],
        "min_sinif": 1,
    },
    "Karışım Problemleri": {
        "ders": "TYT Matematik",
        "on_kosul": ["Oran Orantı"],
        "min_sinif": 1,
    },
    "Fonksiyonlar": {
        "ders": "TYT Matematik",
        "on_kosul": ["Kümeler – Kartezyen Çarpım", "Denklem Çözme"],
        "min_sinif": 2,
    },

    # --------------------------------------------------------------------------
    # 3. TYT & AYT FİZİK
    # --------------------------------------------------------------------------
    "Newton'ın Hareket Yasaları": {
        "ders": "AYT Fizik",
        "on_kosul": ["Vektörler ve Bağıl Hareket"],
        "min_sinif": 3,
    },
    "Atışlar": {
        "ders": "AYT Fizik",
        "on_kosul": ["Vektörler ve Bağıl Hareket"],
        "min_sinif": 3,
    },
    "Tork ve Dönme Dengesi": {
        "ders": "AYT Fizik",
        "on_kosul": ["Newton'ın Hareket Yasaları"],
        "min_sinif": 3,
    },
    "İtme ve Çizgisel Momentum": {
        "ders": "AYT Fizik",
        "on_kosul": ["İş-Enerji Korunumu"],
        "min_sinif": 3,
    },
    "Elektriksel Potansiyel": {
        "ders": "AYT Fizik",
        "on_kosul": ["Elektriksel Kuvvet ve Elektrik Alan"],
        "min_sinif": 3,
    },
    "Düzgün Elektrik Alan ve Sığaçlar": {
        "ders": "AYT Fizik",
        "on_kosul": ["Elektriksel Potansiyel"],
        "min_sinif": 3,
    },
    "Manyetik Alan ve Manyetik Kuvvet": {
        "ders": "AYT Fizik",
        "on_kosul": ["Elektrik Akımı ve Devreler"],
        "min_sinif": 3,
    },
    "İndüksiyon ve Alternatif Akım": {
        "ders": "AYT Fizik",
        "on_kosul": ["Manyetik Alan ve Manyetik Kuvvet"],
        "min_sinif": 3,
    },

    # --------------------------------------------------------------------------
    # 4. TYT & AYT KİMYA
    # --------------------------------------------------------------------------
    "Mol Kavramı ve Kimyasal Hesaplamalar": {
        "ders": "TYT Kimya",
        "on_kosul": ["Kimyanın Temel Kanunları"],
        "min_sinif": 1,
    },
    "Kimyasal Denge": {
        "ders": "AYT Kimya",
        "on_kosul": ["Tepkime Hızları"],
        "min_sinif": 3,
    },
    "Asit-Baz Dengesi": {
        "ders": "AYT Kimya",
        "on_kosul": ["Kimyasal Denge"],
        "min_sinif": 3,
    },
    "Çözünürlük Dengesi (KÇÇ)": {
        "ders": "AYT Kimya",
        "on_kosul": ["Kimyasal Denge"],
        "min_sinif": 3,
    },
    "Organik Bileşikler": {
        "ders": "AYT Kimya",
        "on_kosul": ["Karbon Kimyasına Giriş"],
        "min_sinif": 4,
    },

    # --------------------------------------------------------------------------
    # 5. TYT & AYT BİYOLOJİ
    # --------------------------------------------------------------------------
    "Hücre Zarından Madde Geçişleri": {
        "ders": "TYT Biyoloji",
        "on_kosul": ["Canlıların Temel Bileşenleri", "Hücre Yapısı ve Organeller"],
        "min_sinif": 1,
    },
    "Mayoz ve Eşeyli Üreme": {
        "ders": "TYT Biyoloji",
        "on_kosul": ["Mitoz ve Eşeysiz Üreme"],
        "min_sinif": 2,
    },
    "Mendelyan Kalıtım": {
        "ders": "TYT Biyoloji",
        "on_kosul": ["Mayoz ve Eşeyli Üreme"],
        "min_sinif": 2,
    },
    "İnsan Fizyolojisi - Sinir ve Endokrin Sistem": {
        "ders": "AYT Biyoloji",
        "on_kosul": ["Hücre Yapısı ve Organeller", "Hücre Zarından Madde Geçişleri"],
        "min_sinif": 3,
    },
    "İnsan Fizyolojisi - Dolaşım ve Bağışıklık": {
        "ders": "AYT Biyoloji",
        "on_kosul": ["İnsan Fizyolojisi - Sinir ve Endokrin Sistem"],
        "min_sinif": 3,
    },
    "İnsan Fizyolojisi - Solunum ve Boşaltım": {
        "ders": "AYT Biyoloji",
        "on_kosul": ["İnsan Fizyolojisi - Dolaşım ve Bağışıklık"],
        "min_sinif": 3,
    },
    "Nükleik Asitler ve Protein Sentezi": {
        "ders": "AYT Biyoloji",
        "on_kosul": ["Canlıların Temel Bileşenleri", "Hücre Yapısı ve Organeller"],
        "min_sinif": 4,
    },
    "Hücresel Solunum ve Fotosentez": {
        "ders": "AYT Biyoloji",
        "on_kosul": ["Canlıların Temel Bileşenleri", "Nükleik Asitler ve Protein Sentezi"],
        "min_sinif": 4,
    },
    "Bitki Biyolojisi - Madde Taşınması ve Beslenme": {
        "ders": "AYT Biyoloji",
        "on_kosul": ["Hücre Zarından Madde Geçişleri", "Hücresel Solunum ve Fotosentez"],
        "min_sinif": 4,
    },

    # --------------------------------------------------------------------------
    # 6. AYT EDEBİYAT & SOSYAL-1 / SOSYAL-2
    # --------------------------------------------------------------------------
    "Divan Edebiyaı": {
        "ders": "AYT Edebiyat",
        "on_kosul": ["Şiir Bilgisi ve Edebi Sanatlar", "İslamiyet Öncesi ve Geçiş Dönemi Türk Edebiyatı"],
        "min_sinif": 2,
    },
    "Tanzimat ve Servet-i Fünun Edebiyatı": {
        "ders": "AYT Edebiyat",
        "on_kosul": ["Şiir Bilgisi ve Edebi Sanatlar", "Divan Edebiyatı"],
        "min_sinif": 3,
    },
    "Cumhuriyet Dönemi Edebiyatı": {
        "ders": "AYT Edebiyat",
        "on_kosul": ["Tanzimat ve Servet-i Fünun Edebiyatı", "Milli Edebiyat Dönemi"],
        "min_sinif": 4,
    },
    "Türk-İslam Devletleri": {
        "ders": "AYT Tarih-1",
        "on_kosul": ["İlk ve Orta Çağlarda Türk Dünyası", "İslam Medeniyetinin Doğuşu"],
        "min_sinif": 1,
    },
    "Beylikten Devlete Osmanlı Siyaseti": {
        "ders": "AYT Tarih-1",
        "on_kosul": ["Türk-İslam Devletleri"],
        "min_sinif": 2,
    },
    "Milli Mücadele Dönemi": {
        "ders": "AYT Tarih-1",
        "on_kosul": ["XX. Yüzyıl Başlarında Osmanlı Devleti"],
        "min_sinif": 4,
    },
    "Atatürk İlkeleri ve İnkılapları": {
        "ders": "AYT Tarih-1",
        "on_kosul": ["Milli Mücadele Dönemi"],
        "min_sinif": 4,
    },
    "Soğuk Savaş ve XXI. Yüzyıl": {
        "ders": "AYT Tarih-2",
        "on_kosul": ["İki Savaş Arası Dönem"],
        "min_sinif": 4,
    },
    "Türkiye Ekonomisi ve Bölgeler": {
        "ders": "AYT Coğrafya-1",
        "on_kosul": ["İklim Bilgisi", "Türkiye’nin Yer Şekilleri"],
        "min_sinif": 3,
    },
    "Klasik Mantık": {
        "ders": "AYT Felsefe Grubu",
        "on_kosul": ["Felsefi Düşünce"],
        "min_sinif": 3,
    },
    "Sembolik Mantık": {
        "ders": "AYT Felsefe Grubu",
        "on_kosul": ["Klasik Mantık"],
        "min_sinif": 4,
    },

    # --------------------------------------------------------------------------
    # 7. YDT (İNGİLİZCE)
    # --------------------------------------------------------------------------
    "Clauses & Conjunctions": {
        "ders": "YDT İngilizce",
        "on_kosul": ["Tenses & Modals", "Vocabulary & Collocations"],
        "min_sinif": 2,
    },
    "Cloze Test & Cümle Tamamlama": {
        "ders": "YDT İngilizce",
        "on_kosul": ["Clauses & Conjunctions"],
        "min_sinif": 3,
    },
    "Paragraf Okuma ve Anlama": {
        "ders": "YDT İngilizce",
        "on_kosul": ["Cloze Test & Cümle Tamamlama"],
        "min_sinif": 3,
    },
    "İngilizce-Türkçe Çeviri": {
        "ders": "YDT İngilizce",
        "on_kosul": ["Paragraf Okuma ve Anlama"],
        "min_sinif": 4,
    },

    # --------------------------------------------------------------------------
    # 8. MAARİF MODELİ (9. SINIF MATEMATİK VE VERİ)
    # --------------------------------------------------------------------------
    "Gerçek Sayıların Üslü ve Köklü Gösterimleri": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Sayı Kümeleri ve İşlem Özellikleri"],
        "min_sinif": 1,
    },
    "Gerçek Sayı Aralıkları ile İşlemler": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Gerçek Sayıların Üslü ve Köklü Gösterimleri"],
        "min_sinif": 1,
    },
    "İki Kare Farkı ve Tamkare Özdeşlikleri": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Gerçek Sayı Aralıkları ile İşlemler"],
        "min_sinif": 1,
    },
    "Gerçek Sayılarda Tanımlı Doğrusal Fonksiyonlar ve Mutlak Değer": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["İki Kare Farkı ve Tamkare Özdeşlikleri"],
        "min_sinif": 1,
    },
    "Fonksiyonların Nitel Özellikleri": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Gerçek Sayılarda Tanımlı Doğrusal Fonksiyonlar ve Mutlak Değer"],
        "min_sinif": 1,
    },
    "Doğrusal Fonksiyonlarla İfade Edilen Denklem ve Eşitsizlikler": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Fonksiyonların Nitel Özellikleri"],
        "min_sinif": 1,
    },
    "Üçgende Açı İlişkileri": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Üçgende Açı ve Kenar Özellikleri"],
        "min_sinif": 1,
    },
    "Üçgende Kenar İlişkileri": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Üçgende Açı İlişkileri"],
        "min_sinif": 1,
    },
    "Üçgenlerde Eşlik ve Benzerlik Koşulları": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Üçgende Kenar İlişkileri", "Geometrik Şekillerin Dönüşümleri (Yansıma, Öteleme, Dönme)"],
        "min_sinif": 1,
    },
    "Verileri Toplama ve Analize Hazırlama": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Tek Nicel Değişken İçeren İstatistiksel Problem Oluşturma"],
        "min_sinif": 1,
    },
    "Bulgulara Ulaşma ve Yorumlama": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Verileri Toplama ve Analize Hazırlama"],
        "min_sinif": 1,
    },
    "İstatistiksel Görsel ve Çıkarımları Değerlendirme": {
        "ders": "Matematik ve Veri",
        "on_kosul": ["Bulgulara Ulaşma ve Yorumlama"],
        "min_sinif": 1,
    },
}

SORU_AGIRLIKLARI = {
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
    "Üçgenler ve Açılar": 14.0,
    "Çokgenler ve Dörtgenler": 14.0,
    "Dikdörtgen ve Kare": 7.5,
    "Çokgenler": 4.0,
    "Yamuk": 3.0,
    "Geometrik Şekiller": 10.0,
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
# (MAARİF & YKS) MÜFREDAT HEDEFLERİ
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
            "Organik Moleküller (Karbonhidrat, Yağ, Protein, Nükleik Asit, Vitamin)",
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
# HESAPLAMA MOTORU (ÖSYM PUAN & SIRALAMA)
# ==============================================================================
def hesapla_yks_puan_ve_siralama(netler: dict, diploma_notu: float, alan: str):
    obp_puan = min(100.0, max(50.0, diploma_notu)) * 5.0
    obp_katkisi = obp_puan * 0.12

    t_tur = netler.get("tyt_turkce", 0.0)
    t_mat = netler.get("tyt_mat", 0.0)
    t_sos = netler.get("tyt_sosyal", 0.0)
    t_fen = netler.get("tyt_fen", 0.0)

    a_mat = netler.get("ayt_mat", 0.0)
    a_fiz = netler.get("ayt_fizik", 0.0)
    a_kim = netler.get("ayt_kimya", 0.0)
    a_biy = netler.get("ayt_biyoloji", 0.0)

    a_edb = netler.get("ayt_edebiyat", 0.0)
    a_tar1 = netler.get("ayt_tarih1", 0.0)
    a_cog1 = netler.get("ayt_cog1", 0.0)
    a_tar2 = netler.get("ayt_tarih2", 0.0)
    a_cog2 = netler.get("ayt_cog2", 0.0)
    a_fel = netler.get("ayt_felsefe", 0.0)
    a_din = netler.get("ayt_din", 0.0)

    y_ing = netler.get("ydt_ing", 0.0)

    tyt_ham = (
        100.0 + (t_tur * 3.3) + (t_mat * 3.3) + (t_sos * 3.4) + (t_fen * 3.4)
    )
    tyt_ayt_katkisi = (
        (t_tur * 1.32) + (t_mat * 1.32) + (t_sos * 1.36) + (t_fen * 1.36)
    )

    say_ham = (
        100.0
        + tyt_ayt_katkisi
        + (a_mat * 3.0)
        + (a_fiz * 2.85)
        + (a_kim * 3.07)
        + (a_biy * 3.07)
    )
    ea_ham = (
        100.0
        + tyt_ayt_katkisi
        + (a_mat * 3.0)
        + (a_edb * 3.0)
        + (a_tar1 * 2.8)
        + (a_cog1 * 3.33)
    )
    soz_ham = (
        100.0
        + tyt_ayt_katkisi
        + (a_edb * 3.0)
        + (a_tar1 * 2.8)
        + (a_cog1 * 3.33)
        + (a_tar2 * 2.91)
        + (a_cog2 * 2.91)
        + (a_fel * 3.0)
        + (a_din * 3.33)
    )
    dil_ham = 100.0 + tyt_ayt_katkisi + (y_ing * 3.0)

    y_tyt = min(560.0, tyt_ham + obp_katkisi)
    y_say = min(560.0, say_ham + obp_katkisi)
    y_ea = min(560.0, ea_ham + obp_katkisi)
    y_soz = min(560.0, soz_ham + obp_katkisi)
    y_dil = min(560.0, dil_ham + obp_katkisi)

    def interpolate_rank(puan, points_map):
        sorted_p = sorted(points_map.keys(), reverse=True)
        if puan >= sorted_p[0]:
            return max(
                1, int(points_map[sorted_p[0]] * (500.0 / max(500.01, puan)))
            )
        if puan <= sorted_p[-1]:
            return int(points_map[sorted_p[-1]] * 1.3)
        for i in range(len(sorted_p) - 1):
            p1, p2 = sorted_p[i], sorted_p[i + 1]
            if p2 <= puan <= p1:
                r1, r2 = points_map[p1], points_map[p2]
                frac = (p1 - puan) / (p1 - p2)
                return int(r1 + frac * (r2 - r1))
        return 100000

    say_map = {
        500: 51,
        440: 22370,
        400: 58728,
        360: 100553,
        320: 153304,
        280: 228643,
        240: 344536,
    }
    ea_map = {
        500: 15,
        440: 874,
        400: 4545,
        360: 23452,
        320: 89520,
        280: 210499,
        240: 440752,
    }
    soz_map = {
        500: 5,
        440: 214,
        400: 1418,
        360: 10259,
        320: 47292,
        280: 148959,
        240: 360487,
    }
    tyt_map = {
        500: 51,
        440: 17050,
        400: 67394,
        360: 155008,
        320: 302758,
        280: 577094,
        240: 1045340,
    }

    siralamalar = {
        "TYT": interpolate_rank(y_tyt, tyt_map),
        "Sayısal": interpolate_rank(y_say, say_map),
        "Eşit Ağırlık": interpolate_rank(y_ea, ea_map),
        "Sözel": interpolate_rank(y_soz, soz_map),
        "Dil": interpolate_rank(y_dil, say_map),
    }

    return {
        "tyt_ham": round(tyt_ham, 2),
        "say_ham": round(say_ham, 2),
        "ea_ham": round(ea_ham, 2),
        "soz_ham": round(soz_ham, 2),
        "y_tyt": round(y_tyt, 2),
        "y_say": round(y_say, 2),
        "y_ea": round(y_ea, 2),
        "y_soz": round(y_soz, 2),
        "y_dil": round(y_dil, 2),
        "obp_katkisi": round(obp_katkisi, 2),
        "tahmini_siralama": siralamalar.get(alan, siralamalar["Sayısal"]),
    }


# ==============================================================================
# GİRİŞ FORMU VE OTURUM KONTROLÜ
# ==============================================================================
# ==============================================================================
# 🧠 SIRALI & SORU KOTALI AKILLI PROGRAM MOTORU (EK MODÜL)
# ==============================================================================
GUN_ADLARI_LISTE = [
    "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"
]

# Planlayıcıya özel ek ön koşullar (alarm motorunu etkilemez)
ON_KOSULLAR_EK = {
    "Üstel ve Logaritmik Fonksiyonlar": {"on_kosul": ["Polinomlar ve Çarpanlara Ayırma", "İkinci Dereceden Denklemler"], "min_sinif": 1},
    "Parabol": {"on_kosul": ["İkinci Dereceden Denklemler"], "min_sinif": 1},
    "Karmaşık Sayılar": {"on_kosul": ["İkinci Dereceden Denklemler"], "min_sinif": 1},
    "İkinci Dereceden Eşitsizlik Sistemleri": {"on_kosul": ["İkinci Dereceden Denklemler", "Parabol"], "min_sinif": 1},
    "Limit ve Süreklilik": {"on_kosul": ["Fonksiyonlar"], "min_sinif": 1},
    "Yönlü Açılar ve Trigonometrik Oranlar": {"on_kosul": ["Dik Üçgen ve Pisagor"], "min_sinif": 1},
    "Newton'ın Hareket Yasaları": {"on_kosul": ["Vektörler ve Bağıl Hareket"], "min_sinif": 1},
    "Atışlar": {"on_kosul": ["Vektörler ve Bağıl Hareket"], "min_sinif": 1},
    "Tork ve Dönme Dengesi": {"on_kosul": ["Newton'ın Hareket Yasaları"], "min_sinif": 1},
    "İtme ve Çizgisel Momentum": {"on_kosul": ["İş-Enerji Korunumu"], "min_sinif": 1},
    "Elektriksel Potansiyel": {"on_kosul": ["Elektriksel Kuvvet ve Elektrik Alan"], "min_sinif": 1},
    "Düzgün Elektrik Alan ve Sığaçlar": {"on_kosul": ["Elektriksel Potansiyel"], "min_sinif": 1},
    "İndüksiyon ve Alternatif Akım": {"on_kosul": ["Manyetik Alan ve Manyetik Kuvvet"], "min_sinif": 1},
    "Kimyasal Denge": {"on_kosul": ["Tepkime Hızları"], "min_sinif": 1},
    "Asit-Baz Dengesi": {"on_kosul": ["Kimyasal Denge"], "min_sinif": 1},
    "Çözünürlük Dengesi (KÇÇ)": {"on_kosul": ["Kimyasal Denge"], "min_sinif": 1},
    "Organik Bileşikler": {"on_kosul": ["Karbon Kimyasına Giriş"], "min_sinif": 1},
    "Mol Kavramı ve Kimyasal Hesaplamalar": {"on_kosul": ["Kimyanın Temel Kanunları"], "min_sinif": 1},
    "Hareket Hız Problemleri": {"on_kosul": ["Oran Orantı"], "min_sinif": 1},
    "Yaş Problemleri": {"on_kosul": ["Denklem Çözme"], "min_sinif": 1},
    "Karışım Problemleri": {"on_kosul": ["Oran Orantı"], "min_sinif": 1},
}


def init_program_motoru_db():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS konu_soru_ilerleme (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                ders TEXT,
                mikro_konu TEXT,
                cozulen_soru INTEGER DEFAULT 0,
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_soru_ilerleme_unique
            ON konu_soru_ilerleme(ogrenci_id, ders, mikro_konu)
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ogrenci_hiz_gecmisi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                tarih TEXT,
                planlanan_gorev INTEGER,
                planlanan_soru INTEGER,
                kullanilan_katsayi REAL DEFAULT 1.0,
                biten_gorev INTEGER,
                biten_soru INTEGER,
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)
        conn.commit()


init_program_motoru_db()

SORU_ILERLEME_ATLANACAK = ("Günlük Paragraf", "Soru Çözümü & Prova", "Özet Not Çalışması")


def konu_soru_hedefi_hesapla(makro, mikro_sayisi, aktif_yanlis=0):
    """Konunun kredi puanından türeyen toplam soru kotası (5'in katı, 40-300 arası)."""
    makro_kredi = SORU_AGIRLIKLARI.get(makro, 10.0)
    mikro_kredi = makro_kredi / max(1, mikro_sayisi)
    zorluk = 1.0 + min(0.3, 0.05 * aktif_yanlis)
    hedef = int(round(mikro_kredi * 10.0 * zorluk))
    hedef = max(40, min(300, hedef))
    return int(round(hedef / 5.0) * 5)


def kolaydan_zora_dagilim(soru, oran):
    """Kota ilerledikçe zorluk artar: kolay ➔ orta ➔ zor."""
    if oran < 0.34:
        p = (0.6, 0.3, 0.1)
    elif oran < 0.67:
        p = (0.3, 0.5, 0.2)
    else:
        p = (0.1, 0.4, 0.5)
    kolay = int(round(soru * p[0]))
    orta = int(round(soru * p[1]))
    zor = max(0, soru - kolay - orta)
    return f"{kolay} kolay ➔ {orta} orta ➔ {zor} zor"


def soru_borcu_baslat(ogrenci_id, ders, mikro_listesi):
    """Öğrenci bir konuyu 'Biliyorum' işaretlediğinde soru kotası takibini başlatır."""
    try:
        with get_connection() as c:
            cur = c.cursor()
            for m in mikro_listesi:
                cur.execute(
                    "INSERT OR IGNORE INTO konu_soru_ilerleme (ogrenci_id, ders,"
                    " mikro_konu, cozulen_soru) VALUES (?, ?, ?, 0)",
                    (ogrenci_id, ders, m),
                )
            c.commit()
    except Exception:
        pass


def soru_ilerleme_isle(gorev_id, tamamlandi):
    """Görev işaretlenince/işareti kalkınca çözülen soru sayısını konuya yazar."""
    try:
        with get_connection() as c:
            cur = c.cursor()
            cur.execute(
                "SELECT ogrenci_id, ders, mikro_konu, hedef_soru, pedagoji_turu"
                " FROM calisma_programi_gorevler WHERE id = ?",
                (gorev_id,),
            )
            r = cur.fetchone()
            if not r:
                return
            oid, ders, mikro, soru, ped = r
            if (not soru) or soru <= 0 or ped == "Tekrar" or mikro in SORU_ILERLEME_ATLANACAK:
                return
            delta = soru if tamamlandi else -soru
            cur.execute(
                "INSERT OR IGNORE INTO konu_soru_ilerleme (ogrenci_id, ders,"
                " mikro_konu, cozulen_soru) VALUES (?, ?, ?, 0)",
                (oid, ders, mikro),
            )
            cur.execute(
                "UPDATE konu_soru_ilerleme SET cozulen_soru = MAX(0, cozulen_soru + ?)"
                " WHERE ogrenci_id = ? AND ders = ? AND mikro_konu = ?",
                (delta, oid, ders, mikro),
            )
            c.commit()
    except Exception:
        pass


def hiz_gecmisi_kaydet(ogrenci_id):
    """Program yenilenmeden hemen önce, eski programın başarı oranını kaydeder."""
    try:
        with get_connection() as c:
            cur = c.cursor()
            cur.execute(
                "SELECT id, tarih FROM ogrenci_hiz_gecmisi WHERE ogrenci_id = ?"
                " AND biten_gorev IS NULL ORDER BY id DESC LIMIT 1",
                (ogrenci_id,),
            )
            r = cur.fetchone()
            if not r:
                return
            kid, tarih_str = r
            bugun = get_tr_now().date()
            yas = (bugun - datetime.strptime(tarih_str, "%Y-%m-%d").date()).days
            if yas < 3:  # çok yeni programı yenilemek hız ölçümünü bozmasın
                cur.execute("DELETE FROM ogrenci_hiz_gecmisi WHERE id = ?", (kid,))
                c.commit()
                return
            cur.execute(
                """SELECT COUNT(*), COALESCE(SUM(durum), 0),
                          COALESCE(SUM(CASE WHEN pedagoji_turu != 'Tekrar' THEN hedef_soru ELSE 0 END), 0),
                          COALESCE(SUM(CASE WHEN pedagoji_turu != 'Tekrar' AND durum = 1 THEN hedef_soru ELSE 0 END), 0)
                   FROM calisma_programi_gorevler WHERE ogrenci_id = ? AND tarih <= ?""",
                (ogrenci_id, bugun.strftime("%Y-%m-%d")),
            )
            toplam, biten, plan_soru, biten_soru = cur.fetchone()
            if not toplam:
                cur.execute("DELETE FROM ogrenci_hiz_gecmisi WHERE id = ?", (kid,))
            else:
                cur.execute(
                    "UPDATE ogrenci_hiz_gecmisi SET planlanan_gorev = ?, planlanan_soru = ?,"
                    " biten_gorev = ?, biten_soru = ? WHERE id = ?",
                    (toplam, plan_soru, biten, biten_soru, kid),
                )
            c.commit()
    except Exception:
        pass


def hesapla_hiz_katsayisi(ogrenci_id):
    """Öğrencinin gerçek hızını otomatik hesaplar (soru sormaz). 1.0 = standart."""
    try:
        with get_connection() as c:
            cur = c.cursor()
            cur.execute(
                "SELECT planlanan_gorev, planlanan_soru, biten_gorev, biten_soru,"
                " kullanilan_katsayi FROM ogrenci_hiz_gecmisi WHERE ogrenci_id = ?"
                " AND biten_gorev IS NOT NULL ORDER BY id DESC LIMIT 1",
                (ogrenci_id,),
            )
            r = cur.fetchone()
    except Exception:
        return 1.0
    if not r:
        return 1.0
    plan_g, plan_s, bit_g, bit_s, eski_k = r
    if plan_s and plan_s > 0:
        oran = (bit_s or 0) / plan_s
    elif plan_g and plan_g > 0:
        oran = (bit_g or 0) / plan_g
    else:
        return 1.0
    ayar = max(0.6, min(1.25, oran / 0.85))  # %85 tamamlama = ideal tempo
    return round(max(0.5, min(1.6, (eski_k or 1.0) * ayar)), 2)


def program_durumu_yukle(ogrenci_id):
    with get_connection() as c:
        df_b = pd.read_sql_query(
            "SELECT mikro_konu FROM konu_durumlari_detay WHERE ogrenci_id = ?"
            " AND durum = 'Biliyorum'", c, params=(ogrenci_id,),
        )
        df_s = pd.read_sql_query(
            "SELECT ders, mikro_konu, cozulen_soru FROM konu_soru_ilerleme"
            " WHERE ogrenci_id = ?", c, params=(ogrenci_id,),
        )
        df_y = pd.read_sql_query(
            "SELECT ders, konu_adi, SUM(yanlis_adedi) AS y FROM deneme_konu_yanlislari"
            " WHERE ogrenci_id = ? AND (durum IS NULL OR durum = 'Aktif')"
            " GROUP BY ders, konu_adi", c, params=(ogrenci_id,),
        )
    return {
        "bilinen_mikro": set(df_b["mikro_konu"].tolist()),
        "cozulen": {
            (r["ders"], r["mikro_konu"]): int(r["cozulen_soru"] or 0)
            for _, r in df_s.iterrows()
        },
        "yanlis_konu": {
            (r["ders"], r["konu_adi"]): int(r["y"] or 0) for _, r in df_y.iterrows()
        },
    }


def _on_kosul_coz(mikro, sim_bilinen, kurallar, konu_index, derinlik=0):
    """Eksik ön koşul zincirinin en dibindeki çalışılabilir konuyu döndürür."""
    kural = kurallar.get(mikro)
    if not kural or derinlik > 4:
        return mikro
    for ok in kural["on_kosul"]:
        if ok not in sim_bilinen and ok in konu_index:
            return _on_kosul_coz(ok, sim_bilinen, kurallar, konu_index, derinlik + 1)
    return mikro


def akilli_program_motoru_uygula(
    cursor, ogrenci_id, aktif_mufredat, alarmlar,
    ana_blok_sayisi, blok_soru_butcesi, paragraf_hedef,
):
    """Sıralı + soru kotalı + hıza duyarlı 7 günlük program üretir.
    Veritabanına EN SON yazar; hata olursa hiçbir şey yazılmaz (eski motor devreye girer)."""
    durum = program_durumu_yukle(ogrenci_id)
    sim_bilinen = set(durum["bilinen_mikro"])
    sim_cozulen = dict(durum["cozulen"])
    takipli = set(durum["cozulen"].keys())
    yanlis_konu = durum["yanlis_konu"]
    kurallar = {**ON_KOSULLAR_EK, **ON_KOSULLAR}

    # Müfredat sırası (dict sırası = konu sırası)
    ders_sirasi, konu_index = {}, {}
    for d_ad, m_dict in aktif_mufredat.items():
        if not isinstance(m_dict, dict):
            continue
        liste = []
        for mak, mik_l in m_dict.items():
            if isinstance(mik_l, list):
                for mik in mik_l:
                    liste.append((mak, mik, len(mik_l)))
                    konu_index.setdefault(mik, (d_ad, mak, len(mik_l)))
        ders_sirasi[d_ad] = liste

    k = hesapla_hiz_katsayisi(ogrenci_id)
    slot_soru = max(10, int(round(blok_soru_butcesi * k / 5.0) * 5))

    alarm_bonus = {}
    for kat, skor in (("siyah", 100.0), ("kirmizi", 80.0), ("turuncu", 40.0), ("mor", 10.0)):
        for a in alarmlar.get(kat, []):
            alarm_bonus[a["ders"]] = max(alarm_bonus.get(a["ders"], 0.0), skor)

    hata_kuyrugu, goruldu = [], set()
    for kat in ("siyah", "kirmizi", "mor"):
        for a in alarmlar.get(kat, []):
            key = (a["ders"], a["konu"])
            if key not in goruldu:
                goruldu.add(key)
                hata_kuyrugu.append(a)

    def _ders_adayi(d_ad):
        for mak, mik, n in ders_sirasi[d_ad]:
            if mik in sim_bilinen:
                if (d_ad, mik) in takipli:
                    hedef = konu_soru_hedefi_hesapla(mak, n, yanlis_konu.get((d_ad, mik), 0))
                    coz = sim_cozulen.get((d_ad, mik), 0)
                    if coz < hedef:  # konu bitti ama soru kotası dolmadı
                        return {"tur": "soru", "ders": d_ad, "makro": mak,
                                "mikro": mik, "hedef": hedef, "cozulen": coz}
                continue
            t = _on_kosul_coz(mik, sim_bilinen, kurallar, konu_index)
            if t != mik:
                d2, m2, n2 = konu_index[t]
            else:
                d2, m2, n2 = d_ad, mak, n
            hedef = konu_soru_hedefi_hesapla(m2, n2, yanlis_konu.get((d2, t), 0))
            return {"tur": "anlatim", "ders": d2, "makro": m2, "mikro": t,
                    "hedef": hedef, "cozulen": sim_cozulen.get((d2, t), 0)}
        return None

    def _skor(c, bugun_dersler):
        kredi = SORU_AGIRLIKLARI.get(c["makro"], 8.0)
        s = kredi * 0.8 + alarm_bonus.get(c["ders"], 0.0) * 0.2
        if c["tur"] == "soru":
            s += 6.0  # başlanan işi bitir
        if c["ders"] in bugun_dersler:
            s *= 0.35  # aynı gün farklı derslere dağıt
        return s

    rows = []
    bugun_dt = get_tr_now()
    yari = max(1, ana_blok_sayisi // 2)

    for idx in range(7):
        tarih_dt = bugun_dt + timedelta(days=idx)
        tarih_str = tarih_dt.strftime("%Y-%m-%d")
        gun_adi = GUN_ADLARI_LISTE[tarih_dt.weekday()]
        bugun_dersler = set()

        rows.append((
            gun_adi, "TYT Türkçe", "Paragraf", "Günlük Paragraf",
            f"📖 PARAGRAF: {paragraf_hedef} Paragraf Sorusu Çöz (~30 dk)",
            paragraf_hedef, "Ezber", tarih_str,
        ))

        if idx < len(hata_kuyrugu):
            h = hata_kuyrugu[idx]
            h_soru = min(15, slot_soru)
            rows.append((
                gun_adi, h["ders"], "Deneme Tekrarı", h["konu"],
                f"🔁 HATA TEKRARI: {h['konu']} ➔ {h_soru} soru çöz "
                f"({kolaydan_zora_dagilim(h_soru, 0.0)}). Denemede yanlış yaptığın soru tiplerini öne al.",
                h_soru, "Pekiştirme", tarih_str,
            ))

        for blok_no in range(ana_blok_sayisi):
            istenen = "Pekiştirme" if blok_no < yari else "Ezber"
            adaylar = {}
            for d_ad in ders_sirasi:
                a = _ders_adayi(d_ad)
                if a:
                    adaylar[(a["ders"], a["mikro"])] = a
            adaylar = list(adaylar.values())

            if not adaylar:
                if istenen == "Pekiştirme":
                    d, m, mi, ped = "TYT Matematik", "Karma Soru", "Soru Çözümü & Prova", "Pekiştirme"
                else:
                    d, m, mi, ped = "TYT Biyoloji", "Kavram Tekrarı", "Özet Not Çalışması", "Ezber"
                rows.append((
                    gun_adi, d, m, mi,
                    f"📌 GENEL TEKRAR: {slot_soru} karma soru çöz "
                    f"({kolaydan_zora_dagilim(slot_soru, 0.5)}) [Tahmini ~{int(slot_soru * 1.5)} dk]",
                    slot_soru, ped, tarih_str,
                ))
                continue

            tercih = [a for a in adaylar if get_konu_pedagoji_turu(a["ders"]) == istenen] or adaylar
            sec = max(tercih, key=lambda c: _skor(c, bugun_dersler))
            d, m, mi, hedef = sec["ders"], sec["makro"], sec["mikro"], sec["hedef"]
            ped = get_konu_pedagoji_turu(d, mi)
            bugun_dersler.add(d)

            if sec["tur"] == "anlatim":
                soru = max(1, min(max(10, slot_soru // 2), hedef))
                video = max(1, int(round(KONU_SURELERI_DK.get(mi, 60) / 30.0)))
                tahmini = KONU_SURELERI_DK.get(mi, 60) + int(soru * 1.5)
                tanim = (
                    f"📌 KONU + SORU: {mi} ➔ {video} ders videosu izle ve kısa özet çıkar, "
                    f"ardından {soru} soru çöz ({kolaydan_zora_dagilim(soru, 0.0)}). "
                    f"Bu konunun toplam soru kotası: {hedef} — kota dolmadan sonraki konuya geçilmez. "
                    f"[Tahmini ~{tahmini} dk]"
                )
                rows.append((gun_adi, d, m, mi, tanim, soru, ped, tarih_str))
                sim_bilinen.add(mi)
                takipli.add((d, mi))
                sim_cozulen[(d, mi)] = sim_cozulen.get((d, mi), 0) + soru

                if idx + 3 <= 6:  # 3 gün sonra aralıklı tekrar
                    t3 = bugun_dt + timedelta(days=idx + 3)
                    rows.append((
                        GUN_ADLARI_LISTE[t3.weekday()], d, m, mi,
                        f"🔄 3 GÜNLÜK ARALIKLI TEKRAR: '{mi}' özet notlarını oku, 5 hatırlatma sorusu çöz.",
                        0, "Tekrar", t3.strftime("%Y-%m-%d"),
                    ))
            else:
                kalan = hedef - sec["cozulen"]
                soru = max(1, min(slot_soru, kalan))
                oran = sec["cozulen"] / float(max(1, hedef))
                tanim = (
                    f"🧩 SORU PEKİŞTİRME: {mi} ➔ {soru} soru çöz "
                    f"({kolaydan_zora_dagilim(soru, oran)}). "
                    f"Konu kotası: {sec['cozulen'] + soru}/{hedef} soru — kota dolmadan sonraki konuya geçilmez. "
                    f"[Tahmini ~{int(soru * 1.5)} dk]"
                )
                rows.append((gun_adi, d, m, mi, tanim, soru, ped, tarih_str))
                sim_cozulen[(d, mi)] = sim_cozulen.get((d, mi), 0) + soru

    cursor.executemany(
        """INSERT INTO calisma_programi_gorevler
           (ogrenci_id, gun, ders, makro_konu, mikro_konu, gorev_tanimi, hedef_soru, pedagoji_turu, durum, tarih)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
        [(ogrenci_id,) + r for r in rows],
    )
    plan_soru = sum(r[5] for r in rows if r[6] != "Tekrar")
    cursor.execute(
        "INSERT INTO ogrenci_hiz_gecmisi (ogrenci_id, tarih, planlanan_gorev,"
        " planlanan_soru, kullanilan_katsayi) VALUES (?, ?, ?, ?, ?)",
        (ogrenci_id, bugun_dt.strftime("%Y-%m-%d"), len(rows), plan_soru, k),
    )
    return True
# ==============================================================================
# 🔬 ALT BAŞLIKLAR
# ==============================================================================
def _alt_ayristir(ham_sozluk):
    sonuc = {}
    for anahtar, metin in ham_sozluk.items():
        sonuc[anahtar] = [p.strip() for p in metin.split("|") if p.strip()]
    return sonuc


# --- PARÇA 1: TYT (klasik müfredat) ---
_ALT_TYT = {
    # TYT MATEMATİK
    "Temel Kavramlar": "Rakam, sayı ve sayı kümeleri|Tek-çift sayılar ve işlem kuralları|Pozitif ve negatif sayılar|Asal sayılar ve asal çarpanlara ayırma|Ardışık sayılar ve toplam formülleri|Faktöriyel kavramı",
    "Sayı Basamakları": "Basamak değeri ve çözümleme|Basamak sayısı ve rakam değişimi problemleri|Taban aritmetiği ve taban dönüştürme",
    "Bölme ve Bölünebilme": "Bölme algoritması|Bölünebilme kuralları (2, 3, 4, 5, 8, 9, 10, 11)|Aralarında asal çarpanlara bölünme|Kalan aritmetiği",
    "EBOB – EKOK": "Asal çarpanlarla EBOB-EKOK hesabı|EBOB-EKOK bağıntıları|Periyodik problemler (zil, nöbet, tur)|Boyut eşitleme problemleri",
    "Rasyonel Sayılar": "Kesir türleri|Dört işlem ve işlem önceliği|Sonsuz merdivenli kesirler|Ondalık ve devirli ondalık sayılar|Rasyonel sayılarda sıralama",
    "Basit Eşitsizlikler": "Eşitsizlik özellikleri ve yön değiştirme|Taraf tarafa toplama ve çarpma|Üslü ifadeli eşitsizlikler|İfade aralığı belirleme",
    "Mutlak Değer": "Mutlak değerin uzaklık tanımı|Mutlak değerli denklemler|Mutlak değerli eşitsizlikler|Üçgen eşitsizliği|En küçük ve en büyük değer problemleri",
    "Üslü Sayılar": "Özellikler ve negatif üs|Toplama, çıkarma, çarpma, bölme|Üssün üssü ve parantez önceliği|Üslü denklemler (taban/üs analizi)|Üslü ifadelerde sıralama",
    "Köklü Sayılar": "Kök derecesi ve tanımlılık şartları|Kök dışına çıkarma, içeri alma, derece sadeleştirme|Köklü ifadelerde dört işlem|Eşlenik ile paydayı kökten kurtarma|Köklü denklemler ve yalancı kök",
    "Çarpanlara Ayırma": "Ortak çarpan parantezine alma|Gruplandırarak çarpanlara ayırma|Özdeşliklerle çarpanlara ayırma|ax²+bx+c üç terimlileri|Terim ekleyip çıkarma|Rasyonel ifadelerin sadeleştirilmesi",
    "Oran Orantı": "Oran ve orantı sabiti|Doğru, ters ve bileşik orantı|Aritmetik, geometrik, harmonik ortalama|Orantı problemleri",
    "Denklem Çözme": "Bir ve iki bilinmeyenli denklemler|Denklem sistemleri|Sonsuz çözüm / boş küme şartları|Parametrik denklemler ve değişken eleme",
    "Sayı Problemleri": "Denklem kurma|Sıra ve kuyruk problemleri|Merdiven problemleri|Bilet dağıtım problemleri",
    "Kesir Problemleri": "Tel kesme ve orta nokta kayması|Parça alma problemleri|Depo ve havuz doluluk oranları",
    "Yaş Problemleri": "Yaş farkının sabitliği|Doğum yılı bağıntıları|Yaş ortalamaları",
    "Hareket Hız Problemleri": "x=v·t ve ortalama hız|Karşılıklı ve aynı yönde hareket|Dairesel pist|Akıntı ve rüzgâr|Tren-tünel problemleri",
    "İşçi Emek Problemleri": "Birim zamanda yapılan iş|Birlikte çalışma denklemleri|İş gücü ve süre değişimi",
    "Yüzde-Kâr-Zarar Problemleri": "Yüzde hesapları|Maliyet, etiket fiyatı, kâr ve zarar|Zam ve indirim|Enflasyon ve alım gücü",
    "Karışım Problemleri": "Karışım oranı|Saf madde/su ekleme ve buharlaştırma|Karışımları birleştirme",
    "Grafik Problemleri": "Daire grafiği|Sütun ve çizgi grafiği okuma|Zamana bağlı değişim grafikleri",
    "Kümeler – Kartezyen Çarpım": "Küme tanımı ve gösterimler|Alt küme sayısı formülleri|Küme işlemleri|Küme problemleri|Kartezyen çarpım",
    "Mantık": "Önerme ve denk önermeler|Bağlaçlar (ve, veya, ya da)|Koşullu ve iki yönlü koşullu önerme|De Morgan ve sadeleştirme|Niceleyiciler|Açık önermeler ve doğruluk kümesi|Teorem ve ispat yöntemleri",
    "Fonksiyonlar": "Fonksiyon kavramı, tanım ve değer kümesi|Fonksiyon olma şartı|Fonksiyon türleri|Bileşke fonksiyon|Ters fonksiyon|Grafik okuma ve eksen kesim noktaları",
    "Permütasyon ve Kombinasyon": "Toplama ve çarpma yoluyla sayma|Permütasyon|Tekrarlı permütasyon|Dairesel permütasyon|Kombinasyon|Seçim ve geometri problemleri|Binom açılımı",
    "Olasılık": "Örnek uzay ve olay kavramları|Teorik ve deneysel olasılık|Ayrık ve ayrık olmayan olaylar|Bağımsız olaylar ve bileşik olasılık|Koşullu olasılık ve Bayes|Geometrik olasılık",
    "Veri – İstatistik": "Aritmetik ortalama, medyan, mod|Açıklık, çeyrekler açıklığı, standart sapma|Veri toplama ve örneklem|Grafik yorumlama (kutu, serpme, çizgi, sütun)",
    # TYT TÜRKÇE
    "Sözcükte Anlam": "Gerçek, yan, mecaz ve terim anlam|Somut-soyut ve genel-özel anlam|Eş anlamlı, zıt anlamlı, eş sesli|Anlam aktarmaları ve ad aktarması|Somutlaştırma ve soyutlaştırma",
    "Söz Yorumu": "Mecaz ve yan anlamlı söz yorumu|Duyular arası ve insandan doğaya aktarımlı sözler|Soyut-somut kavram yorumu",
    "Deyim ve Atasözü": "Deyimlerin kalıplaşmış yapısı|Deyimlerin cümleye kattığı anlamlar|Atasözlerinin mecaz/gerçek anlamı|Deyim ve atasözü eşleştirme",
    "Cümlede Anlam İlişkileri": "Neden-sonuç cümleleri|Amaç-sonuç cümleleri|Koşul-sonuç cümleleri|Öznel ve nesnel yargılar|Doğrudan ve dolaylı anlatım",
    "Cümle Yorumu ve Kavramlar": "Örtülü anlam|Cümleye hâkim duygular (pişmanlık, sitem, öz eleştiri...)|Cümle tamamlama ve birleştirme|Cümleden kesin yargı çıkarma",
    "Paragrafta Anlatım Teknikleri": "Anlatım biçimleri (açıklayıcı, tartışmacı, öyküleyici, betimleyici)|Anlatıcı türleri ve bakış açıları",
    "Paragrafta Düşünceyi Geliştirme Yolları": "Tanımlama ve örneklendirme|Tanık gösterme|Karşılaştırma ve benzetme|Sayısal verilerden yararlanma|Somutlama",
    "Paragrafta Yapı": "Giriş-gelişme-sonuç bölümleri|Paragrafı ikiye bölme|Düşüncenin akışını bozan cümle|Cümle yerleştirme ve yer değiştirme|Karma (çoklu) paragraf soruları",
    "Paragrafta Konu-Ana Düşünce": "Paragrafın konusu|Ana düşünce|Başlık bulma",
    "Paragrafta Yardımcı Düşünce": "Yardımcı düşünceler|Çıkarılamayacak yargılar|Paragraftan kesin yargı",
    "Ses Bilgisi": "Büyük ve küçük ünlü uyumu|Ünlü düşmesi, türemesi, daralması, değişimi|Ünsüz yumuşaması ve sertleşmesi|Ünsüz düşmesi ve türemesi|Dudak ünsüzlerinin benzeşmesi (n-b)|Kaynaştırma harfleri|Ulama",
    "Yazım Kuralları": "Büyük harflerin kullanımı|de/da yazımı|ki yazımı|mi yazımı|Sayıların yazımı|Kısaltmalar|Birleşik sözcüklerin yazımı|İkileme ve pekiştirmeler|Düzeltme işareti",
    "Noktalama İşaretleri": "Nokta, virgül, noktalı virgül, iki nokta|Üç nokta, soru ve ünlem işareti|Kısa çizgi, uzun çizgi, eğik çizgi|Tırnak ve tek tırnak|Parantez, köşeli ayraç, kesme işareti|İşlevler ve yanlış kullanımlar",
    "Sözcükte Yapı ve Ekler": "Kök türleri|Yapım ekleri|İsim çekim ekleri|Fiil çekim ekleri|Basit, türemiş, birleşik sözcük",
    "İsimler": "Özel-cins, tekil-çoğul-topluluk, somut-soyut isimler|İsim tamlamaları",
    "Zamirler": "Kişi zamirleri|İşaret zamirleri|Belgisiz ve soru zamirleri|Dönüşlülük zamiri|İyelik ve ilgi zamiri (ki)",
    "Sıfatlar": "Niteleme sıfatları|Belirtme sıfatları (işaret, sayı, belgisiz, soru)|Sıfat tamlaması ve adlaşmış sıfat|Pekiştirme ve küçültme",
    "Zarflar": "Durum zarfı|Zaman zarfı|Miktar zarfı|Yer-yön zarfı|Soru zarfı",
    "Edat – Bağlaç – Ünlem": "Edat (ilgeç)|Bağlaç|Ünlem",
    "Fiilde Anlam": "İş, durum, oluş fiilleri|Haber ve dilek kipleri|Kişi, olumsuzluk ve soru biçimleri|Zaman/kip kayması",
    "Ek Fiil": "İsim soylu sözcükleri yüklem yapma|Birleşik zamanlı fiiller (idi, imiş, ise)|Ek fiilin görevleri",
    "Fiilimsi": "İsim-fiil (mastar)|Sıfat-fiil (ortaç)|Zarf-fiil (ulaç)",
    "Fiilde Çatı": "Etken ve edilgen|Dönüşlü ve işteş|Geçişli ve geçişsiz|Oldurgan ve ettirgen",
    "Cümlenin Ögeleri": "Yüklem|Özne türleri|Nesne (belirtili/belirtisiz)|Dolaylı tümleç|Zarf tümleci ve edat tümleci|Ara söz, ara cümle ve vurgu",
    "Anlatım Bozukluğu": "Gereksiz ve çelişen sözcükler|Yanlış anlam ve yer kullanımı|Mantık ve sıralama hatası|Deyim ve atasözü yanlışları|Özne-yüklem uyumsuzluğu|Öge eksikliği|Ek ve tamlama yanlışları|Çatı uyumsuzluğu",
    # TYT GEOMETRİ
    "Temel Kavramlar ve Doğruda Açılar": "Nokta, doğru, düzlem, ışın|Komşu, tümler, bütünler, ters açılar|Paralel doğrular ve kesen (Z, U, M, kalem ucu)",
    "Üçgende Açılar": "İç ve dış açı toplamı|Dış açı eşitliği|Üçgen eşitsizliği|Açı-kenar bağıntıları|Dar, dik, geniş açılı üçgenlerde kenar sınırları",
    "Dik Üçgen ve Pisagor": "Pisagor teoremi|Öklid bağıntıları|Özel açılı dik üçgenler|Özel kenarlı dik üçgenler (3-4-5 vb.)",
    "İkizkenar ve Eşkenar Üçgen": "İkizkenar üçgende taban dikmesi (YAĞİ)|Taban üzerindeki noktadan dikmeler|Eşkenar üçgen alan ve yükseklik|Eşkenar üçgende iç nokta dikmeleri",
    "Açıortay ve Kenarortay": "İç açıortay teoremi|Dış açıortay teoremi|Teğet çember merkezleri|Kenarortay ve ağırlık merkezi|Muhteşem üçlü|Kenarortay formülü ve orta taban",
    "Üçgende Eşlik ve Benzerlik": "Eşlik kuralları (KAK, AKA, KKK)|Benzerlik kuralları (AA, KAK, KKK)|Thales ve temel orantı teoremi|Kelebek benzerliği|Benzerlik oranı: çevre ve alan",
    "Üçgende Alan": "Taban × yükseklik / 2|Sinüslü alan formülü|Heron formülü|İç teğet çember (A=u·r)|Çevrel çember (A=abc/4R)|Alan oranlama ve kaydırma",
    "Çokgenler": "İç ve dış açı toplamları|Köşegen sayısı|Düzgün çokgenler",
    "Dörtgenler ve Özel Dörtgenler": "Genel dörtgen özellikleri|Köşegenleri dik kesişen dörtgenler|Alan formülleri",
    "Deltoid": "Deltoid özellikleri|Köşegen dikliği ve açıortaylık|Deltoid alanı",
    "Paralelkenar ve Eşkenar Dörtgen": "Paralelkenar özellikleri|Paralelkenar alanı|Eşkenar dörtgen köşegenleri|Eşkenar dörtgen alanı",
    "Dikdörtgen ve Kare": "Köşegen özellikleri|İç nokta kuralları|Alan ve çevre",
    "Yamuk": "İkizkenar ve dik yamuk|Orta taban|Yamuk alanı",
    # TYT FİZİK
    "Fizik Bilimine Giriş": "Fiziğin tanımı ve alt dalları|Diğer bilimlerle ilişkisi|Bilim insanları ve tarihsel gelişim|Kariyer alanları ve araştırma merkezleri",
    "Madde ve Özellikleri": "Kütle, hacim, özkütle|Özkütle grafikleri|Karışımların özkütlesi",
    "Dayanıklılık ve Akışkanlar": "Katılarda dayanıklılık|Adezyon ve kohezyon|Yüzey gerilimi|Kılcallık",
    "Hareket ve Kuvvet": "4 temel kuvvet ve hareket türleri|Konum, yer değiştirme, yol, hız, sürat|Düzgün doğrusal hareket|x-t, v-t, a-t grafikleri",
    "Newton'un Hareket Yasaları": "Eylemsizlik ilkesi|Temel yasa (F=m·a)|Etki-tepki|Sürtünme kuvveti|Eğik düzlem|Bloklar ve makaralı sistemler",
    "Basınç": "Katı basıncı|Sıvı basıncı ve basınç kuvveti|U boruları|Pascal ilkesi ve hidrolik sistemler",
    "Sıvıların Kaldırma Kuvveti": "Açık hava basıncı ve barometre|Gaz basıncı ve manometre|Arşimet ilkesi|Yüzme, askıda kalma, batma|Taşırma kapları",
    "Isı, Sıcaklık ve Genleşme": "Sıcaklık, ısı, iç enerji|Termometreler ve sıcaklık dönüşümleri|Öz ısı ve Q=m·c·ΔT|Hâl değişimi ve gizli ısı|Isıl denge|Isı iletim yolları|Genleşme ve suyun anomalisi",
    "Elektrostatik": "Yük ve yükün korunumu|Elektriklenme türleri|Elektroskop|Coulomb yasası|Elektrik alan",
    "Elektrik Akımı ve Devreler": "Akım, potansiyel fark, direnç|Ohm yasası ve direnç formülü|Seri ve paralel bağlama|Kirchhoff yasaları|Üreteçler ve iç direnç|Elektriksel güç ve enerji",
    "Mıknatıslar ve Manyetik Alan": "Mıknatıs türleri ve kutuplar|Manyetik alan çizgileri|Akım geçen tel, halka, selenoid alanı",
    "Aydınlanma ve Aynalar": "Işık şiddeti, akısı, aydınlanma|Gölge ve tutulmalar|Düzlem ayna|Küresel aynalar",
    "Kırılma ve Mercekler": "Kırılma indisi ve Snell yasası|Tam yansıma ve sınır açısı|Görünür derinlik|Mercekler|Göz kusurları",
    "Dalga Harekatı": "Dalga parametreleri|Yay dalgaları|Su dalgaları|Kırınım ve girişim|Elektromanyetik spektrum",
    # TYT KİMYA
    "Kimya Bilimi": "Simyadan kimyaya|Kimyanın alt disiplinleri|Kimya meslekleri|Maddelerin sağlık ve çevre etkisi|Laboratuvar güvenliği ve piktogramlar|Laboratuvar cam malzemeleri",
    "Atom Yapısı ve Periyodik Sistem": "Atom modelleri|Temel tanecikler (Z, A, iyon yükü)|İzotop, izobar, izoton, izoelektronik|Elektron dizilimi kuralları|Periyodik sistemin yapısı|Periyodik özellikler (yarıçap, iyonlaşma enerjisi, EN)",
    "Kimyasal Türler Arası Etkileşimler": "Kimyasal türler|İyonik bağ|Kovalent bağ|Metalik bağ|Lewis yapısı|Molekül polarlığı|Van der Waals kuvvetleri|Hidrojen bağı",
    "Maddenin Halleri": "Plazma hali|Katı türleri|Viskozite|Buharlaşma ve buhar basıncı|Kaynama|Bağıl nem|Hâl değişim grafikleri",
    "Kimyanın Temel Kanunları": "Kütlenin korunumu (Lavoisier)|Sabit oranlar (Proust)|Katlı oranlar (Dalton)",
    "Mol Kavramı ve Kimyasal Hesaplamalar": "Mol, Avogadro, molar kütle|Denklem denkleştirme ve tepkime türleri|Tepkime hesaplamaları|Sınırlayıcı bileşen|Yüzde verim ve saflık|Formül bulma",
    "Karışımlar ve Ayırma Yöntemleri": "Homojen ve heterojen karışımlar|Çözünme ve benzer benzeri çözer|Derişim birimleri|Seyreltme ve deriştirme|Koligatif özellikler|Ayırma teknikleri|Çözünürlük eğrileri",
    "Asitler, Bazlar ve Tuzlar": "Asit-baz özellikleri ve pH|Arrhenius ve Brønsted-Lowry|Kuvvetli ve zayıf asit/bazlar|Nötralleşme ve metallerle tepkime|Tuzlar",
    # TYT BİYOLOJİ
    "Canlıların Ortak Özellikleri": "Hücresel yapı|Beslenme|Solunum|Boşaltım|Hareket|Uyarılara tepki ve uyum|Organizasyon basamakları|Üreme, büyüme, gelişme|Homeostazi ve metabolizma",
    "Canlıların Temel Bileşenleri": "Su ve mineraller|Asit, baz, pH|Karbonhidratlar|Lipitler|Proteinler|Enzimler|Vitaminler|Nükleik asitler|ATP",
    "Hücre Yapısı ve Organeller": "Prokaryot ve ökaryot hücre|Hücre zarı yapısı|Zarsız organeller|Tek zarlı organeller|Çift zarlı organeller|Çekirdek|Hücreden organizmaya organizasyon",
    "Hücre Zarından Madde Geçişleri": "Difüzyon ve kolaylaştırılmış difüzyon|Ozmoz|Aktif taşıma|Endositoz ve ekzositoz",
    "Canlıların Sınıflandırılması": "Yapay ve doğal sınıflandırma|İkili adlandırma|Sınıflandırma kategorileri|3 domain sistemi|Bakteriler ve arkeler|Protistler ve mantarlar|Bitkiler|Hayvanlar|Virüsler",
    "Mitoz ve Eşeysiz Üreme": "Hücre döngüsü|Mitoz evreleri|Sitokinez|Kontrol noktaları ve kanser|Eşeysiz üreme türleri",
    "Mayoz ve Eşeyli Üreme": "Mayoz I|Mayoz II|Mitoz-mayoz farkları|Gamet oluşumu ve döllenme",
    "Mendelyan Kalıtım": "Mendel ilkeleri ve terimler|Monohibrit ve dihibrit çaprazlama|Test çaprazlaması|Eksik ve eş baskınlık|Çok alellilik (kan grupları)|Eşey belirlenmesi ve eşeye bağlı kalıtım|Soyağacı analizi",
    "Ekosistem Ekolojisi": "Abiyotik ve biyotik bileşenler|Besin zinciri, ağı ve ekolojik piramitler|Madde döngüleri (C, N, su)|Biyobirikim",
    # TYT TARİH
    "Tarih ve Zaman": "Tarihin konusu ve yöntemi|Tarihsel araştırmanın 5 T aşaması|Birincil ve ikincil kaynaklar|Tarihe yardımcı bilimler|Takvim sistemleri",
    "İnsanlığın İlk Dönemleri": "Taş ve maden çağları|Neolitik devrim ve ilk yerleşmeler|Mezopotamya uygarlıkları|Mısır uygarlığı|Anadolu uygarlıkları|Doğu Akdeniz, Hint ve Çin uygarlıkları|İlk çağda hukuk",
    "İlk ve Orta Çağlarda Türk Dünyası": "Türk adı, ana yurt ve konargöçer yaşam|Asya Hun Devleti|Kavimler Göçü ve Avrupa Hun Devleti|Kök Türk devletleri|Uygur Devleti|Diğer Türk boyları|Kültür ve medeniyet",
    "İslam Medeniyetinin Doğuşu": "Cahiliye dönemi|Hz. Muhammed dönemi|Dört Halife dönemi|Emeviler|Abbasiler",
    "Türk-İslam Devletleri": "Karahanlılar|Gazneliler|Büyük Selçuklu Devleti|Mısır'da kurulan Türk devletleri",
    "Beylikten Devlete Osmanlı Siyareti": "Kuruluş ve ilk beyler|Ankara Savaşı ve Fetret|İskan ve istimalet politikası|Fatih dönemi|II. Bayezid ve Yavuz|Kanuni dönemi|Merkez ve taşra teşkilatı|Tımar sistemi",
    "Milli Mücadele ve Atatürkçülük": "XX. yüzyıl başı savaşlar|I. Dünya Savaşı|Mondros ve işgaller|Kongreler dönemi|TBMM ve ayaklanmalar|Cepheler|Lozan|Atatürk ilkeleri|İnkılaplar",
    # TYT COĞRAFYA
    "Doğa ve İnsan": "Coğrafyanın tanımı ve bölümleri|Fiziki ve beşeri alt dallar|Temel ilkeler|Doğa-insan etkileşimi",
    "Dünya’nın Şekli ve Hareketleri": "Geoit şekil ve sonuçları|Küresel şeklin sonuçları|Günlük hareket|Yıllık hareket ve eksen eğikliği|Özel tarihler",
    "Coğrafi Konum": "Mutlak konum (paralel, meridyen)|Yerel ve ulusal saat|Türkiye'nin mutlak konumu|Özel konum",
    "Harita Bilgisi": "Harita elemanları|Ölçek|Projeksiyonlar|Yer şekillerini gösterme yöntemleri|İzohips okuma|CBS, uzaktan algılama, GPS",
    "İklim Bilgisi": "Atmosfer katmanları|Sıcaklık|Basınç ve rüzgârlar|Nem ve yağış|Büyük iklim tipleri|Türkiye iklimi",
    "Nüfus ve Yerleşme": "Nüfusun tarihsel değişimi|Dağılışı etkileyen faktörler|Demografik göstergeler|Nüfus piramitleri|Göç türleri|Kırsal yerleşme|Şehirsel yerleşme",
    "Türkiye’nin Yer Şekilleri": "Dağlar (kıvrım, kırık, volkanik)|Platolar|Ovalar|Akarsu ve göller",
    "Ekonomik Faaliyetler": "Birincil faaliyetler|İkincil faaliyetler|Üçüncül faaliyetler|Dördüncül ve beşincil faaliyetler|Türkiye ekonomisi|Bölge kavramı ve türleri",
    "Doğal Afetler ve Çevre": "İklim değişikliği ve sera etkisi|Jeolojik afetler|Meteorolojik ve hidrolojik afetler|Beşeri/teknolojik afetler|Afet yönetimi safhaları|Küresel ve bölgesel örgütler",
    # TYT FELSEFE & DİN
    "Felsefenin Konusu": "Felsefenin anlamı|Felsefi düşüncenin özellikleri|Felsefe-bilim-din-sanat|Soru sorma ve argümantasyon",
    "Bilgi Felsefesi": "Temel kavramlar|Bilgi türleri|Şüphecilik|Rasyonalizm|Empirizm|Kritisizm|Pozitivizm ve diğer akımlar",
    "Varlık Felsefesi": "Ontolojinin soruları|Monizm, düalizm, plüralizm|Oluş ve madde (materyalizm)|İdealizm|Fenomen ve varoluşçuluk",
    "Ahlak Felsefesi": "Etiğin temel kavramları|Özgürlük ve determinizm|Ahlak yasasını reddedenler|Utilitarizm ve sezgicilik|Erdem ve ödev etiği",
    "Bilgi ve İnanç": "İslam'da bilginin kaynakları|İman kavramı ve iman-amel ilişkisi|Allah'ın sıfatları|Peygamberlerin sıfatları|Hz. Muhammed'in örnekliği",
    "İslam ve İbadet": "İbadet kavramı ve çeşitleri|İslam'ın şartları ve imanın esasları|Mükellefiyet dereceleri|Dua, tövbe, istiğfar, tevekkül",
    "Ahlak ve Değerler": "Ahlakın kaynakları|Övülen ahlaki erdemler|Yerilen davranışlar",
}

# --- PARÇA 2: AYT SAYISAL ---
_ALT_AYT_SAYISAL = {
    # AYT MATEMATİK
    "Polinomlar ve Çarpanlara Ayırma": "Polinom tanımı, derece, katsayılar toplamı|Polinomlarda dört işlem|Bölme algoritması ve kalan teoremi|Kök-katsayı ilişkileri|Çarpanlara ayırma yöntemleri",
    "İkinci Dereceden Denklemler": "Diskriminant analizi|Kök bulma formülleri|Vieta formülleri|Kökleri verilen denklemi kurma",
    "Karmaşık Sayılar": "Sanal birim ve i'nin kuvvetleri|Standart form, reel ve sanal kısım|Karmaşık eşlenik|Dört işlem",
    "Parabol": "İkinci dereceden fonksiyon grafiği|Tepe noktası|Eksenleri kestiği noktalar|Parabol denklemi yazma|Parabol-doğru ilişkisi|Optimizasyon problemleri",
    "İkinci Dereceden Eşitsizlik Sistemleri": "İşaret tablosu|Tek ve çift katlı kökler|Payda ve rasyonel eşitsizlik|Mutlak değerli eşitsizlikler|Kesişim kümesi bulma",
    "Yönlü Açılar ve Trigonometrik Oranlar": "Yönlü açılar, derece-radyan|Birim çember ve trigonometrik oranlar|Trigonometrik özdeşlikler|Bölgelere göre işaret ve açı dönüştürme|Sinüs ve kosinüs teoremi|Periyot ve grafikler|Ters trigonometrik fonksiyonlar|Toplam-fark formülleri|İki kat açı formülleri",
    "Trigonometrik Denklemler": "sinx = sina|cosx = cosa|tanx = tana|Genel çözüm kümeleri",
    "Üstel ve Logaritmik Fonksiyonlar": "Üstel fonksiyon ve grafiği|Logaritma fonksiyonu ve tanım kümesi|Onluk ve doğal logaritma|Logaritma özellikleri|Logaritmik denklem ve eşitsizlikler|Gerçek hayat problemleri",
    "Aritmetik ve Geometrik Diziler": "Dizi kavramı ve genel terim|Aritmetik dizi|Aritmetik dizide toplam|Geometrik dizi|Geometrik dizide toplam|Sonsuz toplam ve yakınsaklık",
    "Limit ve Süreklilik": "Yaklaşım, sağdan ve soldan limit|Limit özellikleri ve kuralları|0/0 belirsizliği|Bir noktada süreklilik|Süreksizlik türleri|Parçalı fonksiyonlarda limit ve süreklilik",
    "Türev Alma Kuralları": "Türevin limit tanımı|Polinom, rasyonel, köklü ifadelerin türevi|Çarpım ve bölüm türevi|Zincir kuralı|Parçalı ve mutlak değerli fonksiyonların türevi",
    "Türevin Geometrik Yorumu ve Maks-Min": "Teğet ve normal doğruları|Artan-azalan aralıklar|Ekstremum noktalar|Maksimum-minimum problemleri",
    "Belirsiz İntegral": "Ters türev ve belirsiz integral|İntegral alma kuralları|Değişken değiştirme yöntemi",
    "Belirli İntegral ve Alan Hesabı": "Belirli integral ve Riemann toplamı|Newton-Leibniz ve özellikleri|Parçalı ve simetrik fonksiyonlar|Eğri altında kalan alan|İki eğri arasında kalan alan|Eksenlere göre alan",
    # AYT GEOMETRİ
    "Çemberde Açı": "Merkez, çevre, teğet-kiriş açılar|İç ve dış açılar|Aynı yayı gören açılar|Kirişler dörtgeni",
    "Çemberde Uzunluk": "Teğet özellikleri|Teğetler dörtgeni|Çemberde kuvvet|Kirişe inilen dikme",
    "Dairede Çevre ve Alan": "Çevre ve yay uzunluğu|Daire alanı|Daire dilimi alanı",
    "Noktanın Analitik İncelemesi": "Dik koordinat sistemi|İki nokta arası uzaklık|Orta nokta ve bölen nokta",
    "Doğrunun Analitik İncelemesi": "Eğim|Doğru denklemi yazma|Eksenleri kestiği noktalar|Paralellik ve diklik|Kesim noktası|Noktanın doğruya uzaklığı",
    "Dönüşüm Geometrisi": "Öteleme|Yansıma (simetri)|Dönme|Bileşke dönüşümler",
    "Çemberin Analitik İncelemesi": "Standart denklem|Merkezil çember|Genel denklem|Doğru ile çemberin durumu|Teğet denklemi",
    "Prizmalar ve Küp": "Dik prizma: yanal alan, toplam alan, hacim|Küp: alan, hacim, cisim köşegeni",
    "Silindir ve Koni": "Dik dairesel silindir|Dik dairesel koni ve açınımı",
    "Piramit ve Küre": "Dik piramit ve düzgün dörtyüzlü|Küre: yüzey alanı, hacim, kesit",
    # AYT FİZİK
    "Vektörler ve Bağıl Hareket": "Vektör özellikleri|Toplama-çıkarma yöntemleri|Bileşke vektör ve özel durumlar|Bağıl hız|Nehirde hareket",
    "Newton'ın Hareket Yasaları": "Birinci ve üçüncü yasa|Temel yasa ve sürtünme|Eğik düzlem|Bloklar ve makaralı sistemler",
    "Atışlar": "Serbest düşme|Limit hız ve hava direnci|Düşey atış|Yatay atış|Eğik atış",
    "İş-Enerji Korunumu": "İş ve güç|Kinetik ve potansiyel enerji|Esneklik potansiyel enerjisi ve Hooke yasası|İş-enerji teoremi|Mekanik enerjinin korunumu",
    "İtme ve Çizgisel Momentum": "İtme ve momentum|İtme-momentum değişimi ve F-t grafiği|Momentumun korunumu|Esnek çarpışmalar|Esnek olmayan çarpışmalar|Patlamalar ve roket hareketi",
    "Tork ve Dönme Dengesi": "Tork ve yönü|Dönme dengesi ve kuvvet dengesi|Lami teoremi|Kütle ve ağırlık merkezi",
    "Elektriksel Kuvvet ve Elektrik Alan": "Elektrik yükleri ve elektriklenme|Elektroskop|Coulomb yasası|Elektrik alan ve alan çizgileri|Yüklü iletken küre",
    "Elektriksel Potansiyel": "Elektriksel potansiyel enerji|Elektriksel potansiyel|Elektriksel iş (W=q·ΔV)",
    "Düzgün Elektrik Alan ve Sığaçlar": "Düzgün elektrik alan ve sapma hareketi|Sığa ve kondansatörler|Depolanan enerji",
    "Manyetik Alan ve Manyetik Kuvvet": "Akım geçen tel, halka, selenoid alanı|Akım taşıyan tele etkiyen kuvvet|Yüklü parçacığa etkiyen kuvvet|Manyetik akı",
    "İndüksiyon ve Alternatif Akım": "Faraday ve Lenz yasaları|Öz-indüksiyon|Alternatif akım (R, XL, XC, rezonans)|Transformatörler",
    "Düzgün Çembersel Hareket": "Çizgisel hız, açısal hız, periyot, frekans|Merkezcil ivme ve kuvvet|Yatay, düşey ve virajlı çembersel hareket",
    "Açısal Momentum ve Kepler": "Eylemsizlik momenti ve dönme kinetik enerjisi|Açısal momentum ve korunumu|Kepler yasaları|Kütle çekim kuvveti ve çekim ivmesi",
    "Basit Harmonik Hareket": "BHH tanımı ve büyüklükler|Konum-hız-ivme denklemleri|Yaylı sarkaç|Basit sarkaç",
    "Dalga Mekaniği ve Doppler": "Dalga parametreleri ve yay dalgaları|Su dalgaları: kırınım ve girişim|Işıkta girişim ve kırınım (Young)|Elektromanyetik dalgalar|Doppler olayı",
    "Atom Fiziği ve Radyoaktivite": "Atom modellerinin gelişimi|Bohr modeli|Atomun uyarılması|Işıma serileri|Radyoaktivite (α, β, γ)|Yarılanma ömrü, fisyon ve füzyon",
    "Fotoelektrik Olay": "Foton ve fotoelektrik denklemi|Bağlanma enerjisi ve kesme potansiyeli|Compton saçılması ve de Broglie dalga boyu",
    # AYT KİMYA
    "Modern Atom Teorisi": "Kuantum sayıları|Orbitaller ve orbital şemaları|Elektron dizilimi kuralları (Aufbau, Pauli, Hund)|Küresel simetri, uyarılmış atom, iyon dizilimleri",
    "Gazlar ve Ideal Gaz Yasası": "Gazların genel özellikleri|Gaz yasaları (Boyle, Charles, Gay-Lussac)|İdeal gaz denklemi|Gaz karışımları ve kısmi basınç|Difüzyon ve gerçek gazlar",
    "Sıvı Çözeltiler ve Çözünürlük": "Çözünme ve çözücü-çözünen etkileşimi|Derişim birimleri (molarite, molalite, mol kesri)|Koligatif özellikler|Çözünürlük eğrileri ve etkileyen faktörler",
    "Kimyasal Tepkimelerde Enerji": "Entalpi, endotermik-ekzotermik|Potansiyel enerji grafikleri|Oluşum entalpisi|Bağ enerjileri|Hess yasası",
    "Tepkime Hızları": "Hız tanımı|Çarpışma teorisi ve aktifleşme enerjisi|Hız bağıntısı ve mertebe|Mekanizmalı tepkimeler|Hızı etkileyen faktörler",
    "Kimyasal Denge": "Dinamik denge|Denge sabiti Kc|Kp ve Kp-Kc ilişkisi|Qc ile denge kontrolü|Le Chatelier ilkesi",
    "Asit-Baz Dengesi": "Su oto-iyonizasyonu|Ka, Kb ve iyonlaşma yüzdesi|Tampon çözeltiler|Tuz hidrolizi|Titrasyon",
    "Çözünürlük Dengesi (KÇÇ)": "Çözünürlük çarpımı (Kçç)|Çökelme şartları (Qc-Kçç)|Ortak iyon etkisi",
    "Redoks ve Elektrokimya": "Yükseltgenme basamağı|Redoks denkleştirme|Galvanik hücre|Standart elektrot potansiyeli|Nernst denklemi|Derişim pilleri|Elektroliz|Faraday kanunları|Korozyon",
    "Karbon Kimyasına Giriş": "Hibritleşme|Sigma ve pi bağları|VSEPR ve molekül geometrisi|Karbon allotropları|Organik-anorganik farkları",
    "Organik Bileşikler": "Fonksiyonel gruplar ve adlandırma|Alkanlar|Alkenler|Alkinler|Aromatik bileşikler|Alkoller ve eterler|Aldehitler ve ketonlar|Karboksilik asitler ve esterler",
    # AYT BİYOLOJİ
    "Sinir Sistemi ve Duyu Organları": "Nöron yapısı ve çeşitleri|İmpuls oluşumu ve iletimi|Sinapslar|Merkezi sinir sistemi|Çevresel sinir sistemi|Duyu organları",
    "Endokrin Sistem": "Endokrin bezler ve hormonlar|Hormonal geri bildirim",
    "Destek ve Hareket Sistemi": "İskelet sistemi|Kas doku türleri|Kayan iplikler ve kasılma",
    "Sindirim Sistemi": "Sindirim organları|Yardımcı organlar|Mekanik ve kimyasal sindirim|Emilim",
    "Dolaşım ve Bağışıklık Sistemi": "Kalp ve kardiyak döngü|Kan damarları|Kanın yapısı|Lenf dolaşımı|Doğal bağışıklık|Kazanılmış bağışıklık|Aşı ve serum",
    "Solunum Sistemi": "Solunum organları|Soluk alıp verme|Gazların taşınması",
    "Üriner Sistem": "Böbrek ve nefron yapısı|Süzülme|Geri emilim|Salgılama",
    "Genden Proteine (Protein Sentezi)": "Genetik şifre, kodon, antikodon|DNA replikasyonu|Santral dogma|Transkripsiyon ve translasyon",
    "Fotosentez ve Kemosentez": "Kloroplast yapısı|Işığa bağımlı reaksiyonlar|Calvin döngüsü|Fotosentez hızını etkileyen faktörler|Kemosentez",
    "Hücresel Solunum": "Glikoliz|Oksijenli solunum (pirüvat oksidasyonu, Krebs, ETS)|Oksijensiz solunum|Fermentasyon",
    "Bitkisel Dokular ve Organlar": "Meristem doku|Temel doku|İletim doku|Örtü doku|Kök, gövde, yaprak kesitleri|Stoma hareketleri|Bitkide madde taşınması",
    "Bitkilerde Büyüme ve Hareket": "Bitkisel hormonlar|Tropizma ve nasti hareketleri|Fotoperiyodizm",
    "Komünite ve Popülasyon Ekolojisi": "Rekabet ve av-avcı ilişkisi|Simbiyotik ilişkiler|Süksesyon|Popülasyon yoğunluğu ve yaş piramitleri|J ve S tipi büyüme eğrileri",
}

MIKRO_ALT_KONULAR = {}
MIKRO_ALT_KONULAR.update(_alt_ayristir(_ALT_TYT))
MIKRO_ALT_KONULAR.update(_alt_ayristir(_ALT_AYT_SAYISAL))
# PARÇA 3 (9. sınıf Maarif, EA, Sözel, YDT) gelince şu şekilde eklenecek:
# MIKRO_ALT_KONULAR.update(_alt_ayristir(_ALT_DIGER))


def init_alt_konu_db():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alt_konu_durumlari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                ders TEXT,
                makro_konu TEXT,
                mikro_konu TEXT,
                alt_konu TEXT,
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_alt_konu_unique
            ON alt_konu_durumlari(ogrenci_id, ders, mikro_konu, alt_konu)
        """)
        cur.execute("PRAGMA table_info(calisma_programi_gorevler)")
        kolonlar = [r[1] for r in cur.fetchall()]
        if "alt_konu" not in kolonlar:
            cur.execute("ALTER TABLE calisma_programi_gorevler ADD COLUMN alt_konu TEXT")
        conn.commit()


init_alt_konu_db()


def alt_konu_haritasi_denetle(aktif_mufredat):
    """Müfredatta olup alt başlığı tanımlanmamış mikro konuları döndürür (yazım hatası kontrolü)."""
    mikrolar = set()
    for d_v in aktif_mufredat.values():
        if isinstance(d_v, dict):
            for m_v in d_v.values():
                if isinstance(m_v, list):
                    mikrolar.update(m_v)
    return sorted(m for m in mikrolar if m not in MIKRO_ALT_KONULAR)


def alt_durumlari_yukle(ogrenci_id):
    """Tamamlanmış alt başlıklar: {(ders, mikro, alt)}. Eski toplu işaretlemeler de dahil."""
    try:
        with get_connection() as c:
            df_a = pd.read_sql_query(
                "SELECT ders, mikro_konu, alt_konu FROM alt_konu_durumlari WHERE ogrenci_id = ?",
                c, params=(ogrenci_id,),
            )
            df_b = pd.read_sql_query(
                "SELECT ders, mikro_konu FROM konu_durumlari_detay"
                " WHERE ogrenci_id = ? AND durum = 'Biliyorum'",
                c, params=(ogrenci_id,),
            )
    except Exception:
        return set()
    sonuc = set(zip(df_a["ders"], df_a["mikro_konu"], df_a["alt_konu"]))
    satirli = set(zip(df_a["ders"], df_a["mikro_konu"]))
    for d, m in zip(df_b["ders"], df_b["mikro_konu"]):
        if (d, m) not in satirli:  # eski/toplu işaretleme: hepsi tamam sayılır
            for a in MIKRO_ALT_KONULAR.get(m, []):
                sonuc.add((d, m, a))
    return sonuc


def alt_konu_isaretle(ogrenci_id, ders, makro, mikro, alt, isaretli):
    """Tek bir alt başlığı işaretler/kaldırır; hepsi bitince mikro konuyu otomatik 'Biliyorum' yapar."""
    alts = MIKRO_ALT_KONULAR.get(mikro, [])
    if alt not in alts:
        return
    tam = False
    try:
        with get_connection() as c:
            cur = c.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM alt_konu_durumlari WHERE ogrenci_id = ? AND ders = ? AND mikro_konu = ?",
                (ogrenci_id, ders, mikro),
            )
            satir_sayisi = cur.fetchone()[0]
            cur.execute(
                "SELECT 1 FROM konu_durumlari_detay WHERE ogrenci_id = ? AND ders = ?"
                " AND mikro_konu = ? AND durum = 'Biliyorum'",
                (ogrenci_id, ders, mikro),
            )
            bilinen = cur.fetchone() is not None
            if bilinen and satir_sayisi == 0:  # toplu işaretlenmiş konu: önce hepsini somutlaştır
                for a in alts:
                    cur.execute(
                        "INSERT OR IGNORE INTO alt_konu_durumlari (ogrenci_id, ders, makro_konu,"
                        " mikro_konu, alt_konu) VALUES (?, ?, ?, ?, ?)",
                        (ogrenci_id, ders, makro, mikro, a),
                    )
            if isaretli:
                cur.execute(
                    "INSERT OR IGNORE INTO alt_konu_durumlari (ogrenci_id, ders, makro_konu,"
                    " mikro_konu, alt_konu) VALUES (?, ?, ?, ?, ?)",
                    (ogrenci_id, ders, makro, mikro, alt),
                )
            else:
                cur.execute(
                    "DELETE FROM alt_konu_durumlari WHERE ogrenci_id = ? AND ders = ?"
                    " AND mikro_konu = ? AND alt_konu = ?",
                    (ogrenci_id, ders, mikro, alt),
                )
            cur.execute(
                "SELECT COUNT(*) FROM alt_konu_durumlari WHERE ogrenci_id = ? AND ders = ? AND mikro_konu = ?",
                (ogrenci_id, ders, mikro),
            )
            biten = cur.fetchone()[0]
            cur.execute(
                "DELETE FROM konu_durumlari_detay WHERE ogrenci_id = ? AND ders = ? AND mikro_konu = ?",
                (ogrenci_id, ders, mikro),
            )
            if biten >= len(alts):
                cur.execute(
                    "INSERT INTO konu_durumlari_detay (ogrenci_id, ders, makro_konu, mikro_konu, durum)"
                    " VALUES (?, ?, ?, ?, 'Biliyorum')",
                    (ogrenci_id, ders, makro, mikro),
                )
                tam = True
            c.commit()
        if tam:
            soru_borcu_baslat(ogrenci_id, ders, [mikro])
    except Exception:
        pass


def alt_konulari_senkronla(ogrenci_id, ders, makro, mikro_listesi, tamam):
    """Mikro konu seviyesinde yapılan toplu işlemlerde alt başlıkları da aynı duruma getirir."""
    try:
        with get_connection() as c:
            cur = c.cursor()
            for mik in mikro_listesi:
                alts = MIKRO_ALT_KONULAR.get(mik, [])
                if not alts:
                    continue
                cur.execute(
                    "DELETE FROM alt_konu_durumlari WHERE ogrenci_id = ? AND ders = ? AND mikro_konu = ?",
                    (ogrenci_id, ders, mik),
                )
                if tamam:
                    for a in alts:
                        cur.execute(
                            "INSERT OR IGNORE INTO alt_konu_durumlari (ogrenci_id, ders, makro_konu,"
                            " mikro_konu, alt_konu) VALUES (?, ?, ?, ?, ?)",
                            (ogrenci_id, ders, makro, mik, a),
                        )
            c.commit()
        for mik in mikro_listesi:
            for a in MIKRO_ALT_KONULAR.get(mik, []):
                st.session_state.pop(f"alt_{ders}_{makro}_{mik}_{a}", None)
    except Exception:
        pass


def alt_oturum_temizle(ders, makro, mikro):
    try:
        for a in MIKRO_ALT_KONULAR.get(mikro, []):
            st.session_state.pop(f"alt_{ders}_{makro}_{mikro}_{a}", None)
        st.session_state.pop(f"chk_{ders}_{makro}_{mikro}", None)
        st.session_state.pop(f"toplu_{ders}_{makro}", None)
    except Exception:
        pass


def alt_konu_degisti(ders, makro, mikro, alt, key_name):
    uid = (st.session_state.get("active_user") or {}).get("id")
    if not uid:
        return
    val = bool(st.session_state.get(key_name, False))
    alt_konu_isaretle(uid, ders, makro, mikro, alt, val)
    st.session_state.pop(f"chk_{ders}_{makro}_{mikro}", None)   # mikro kutusu DB'den yeniden okunsun
    st.session_state.pop(f"toplu_{ders}_{makro}", None)
    log_islem(uid, "SUBTOPIC_TOGGLE", f"{ders} -> {mikro} -> {alt}")


def alt_konu_arayuzu_ciz(ders_adi, makro_adi, mikro_ad, alt_set):
    """Tab 2'de her mikro konunun altına alt başlık kutularını çizer."""
    alts = MIKRO_ALT_KONULAR.get(mikro_ad, [])
    if not alts:
        return
    biten = sum(1 for a in alts if (ders_adi, mikro_ad, a) in alt_set)
    goster = st.checkbox(
        f"🔽 Alt başlıkları göster ({biten}/{len(alts)})",
        key=f"goster_{ders_adi}_{makro_adi}_{mikro_ad}",
    )
    if not goster:
        return
    for a in alts:
        key = f"alt_{ders_adi}_{makro_adi}_{mikro_ad}_{a}"
        if key not in st.session_state:
            st.session_state[key] = (ders_adi, mikro_ad, a) in alt_set
        st.checkbox(
            f"▫️ {a}",
            key=key,
            on_change=alt_konu_degisti,
            args=(ders_adi, makro_adi, mikro_ad, a, key),
        )


def gorev_alt_konu_isle(gorev_id, tamamlandi):
    """Alt başlık içeren görev işaretlenince ilgili alt başlıkları otomatik işaretler/geri alır."""
    try:
        with get_connection() as c:
            cur = c.cursor()
            cur.execute(
                "SELECT ogrenci_id, ders, makro_konu, mikro_konu, alt_konu"
                " FROM calisma_programi_gorevler WHERE id = ?",
                (gorev_id,),
            )
            r = cur.fetchone()
        if not r or not r[4]:
            return
        oid, ders, makro, mikro, alt_str = r
        for a in [x.strip() for x in alt_str.split("||") if x.strip()]:
            alt_konu_isaretle(oid, ders, makro, mikro, a, bool(tamamlandi))
        alt_oturum_temizle(ders, makro, mikro)
    except Exception:
        pass


def akilli_program_motoru_v2_uygula(
    cursor, ogrenci_id, aktif_mufredat, alarmlar,
    ana_blok_sayisi, blok_soru_butcesi, paragraf_hedef,
):
    """Alt başlık düzeyinde çalışan sıralı + soru kotalı + hıza duyarlı 7 günlük program.
    Veritabanına EN SON yazar; hata olursa hiçbir şey yazılmaz."""
    durum = program_durumu_yukle(ogrenci_id)
    sim_bilinen = set(durum["bilinen_mikro"])
    sim_cozulen = dict(durum["cozulen"])
    sim_alt = set(alt_durumlari_yukle(ogrenci_id))
    takipli = set(durum["cozulen"].keys())
    yanlis_konu = durum["yanlis_konu"]
    kurallar = {**ON_KOSULLAR_EK, **ON_KOSULLAR}

    ders_sirasi, konu_index = {}, {}
    for d_ad, m_dict in aktif_mufredat.items():
        if not isinstance(m_dict, dict):
            continue
        liste = []
        for mak, mik_l in m_dict.items():
            if isinstance(mik_l, list):
                for mik in mik_l:
                    liste.append((mak, mik, len(mik_l)))
                    konu_index.setdefault(mik, (d_ad, mak, len(mik_l)))
        ders_sirasi[d_ad] = liste

    k = hesapla_hiz_katsayisi(ogrenci_id)
    slot_soru = max(10, int(round(blok_soru_butcesi * k / 5.0) * 5))

    alarm_bonus = {}
    for kat, skor in (("siyah", 100.0), ("kirmizi", 80.0), ("turuncu", 40.0), ("mor", 10.0)):
        for a in alarmlar.get(kat, []):
            alarm_bonus[a["ders"]] = max(alarm_bonus.get(a["ders"], 0.0), skor)

    hata_kuyrugu, goruldu = [], set()
    for kat in ("siyah", "kirmizi", "mor"):
        for a in alarmlar.get(kat, []):
            key = (a["ders"], a["konu"])
            if key not in goruldu:
                goruldu.add(key)
                hata_kuyrugu.append(a)

    def _alt_dk(mikro):
        alts = MIKRO_ALT_KONULAR.get(mikro, [])
        toplam = KONU_SURELERI_DK.get(mikro, 60)
        if not alts:
            return toplam
        return max(10, int(round(toplam / float(len(alts)) / 5.0) * 5))

    def _ders_adayi(d_ad):
        for mak, mik, n in ders_sirasi[d_ad]:
            if mik in sim_bilinen:
                if (d_ad, mik) in takipli:
                    hedef = konu_soru_hedefi_hesapla(mak, n, yanlis_konu.get((d_ad, mik), 0))
                    coz = sim_cozulen.get((d_ad, mik), 0)
                    if coz < hedef:  # konu bitti ama soru kotası dolmadı
                        return {"tur": "soru", "ders": d_ad, "makro": mak,
                                "mikro": mik, "hedef": hedef, "cozulen": coz}
                continue
            t = _on_kosul_coz(mik, sim_bilinen, kurallar, konu_index)
            if t != mik:
                d2, m2, n2 = konu_index[t]
            else:
                d2, m2, n2 = d_ad, mak, n
            alts_t = MIKRO_ALT_KONULAR.get(t, [])
            if alts_t and all((d2, t, a) in sim_alt for a in alts_t):
                continue  # tüm alt başlıklar bitmiş, kayıt tutarsızlığı: atla
            hedef = konu_soru_hedefi_hesapla(m2, n2, yanlis_konu.get((d2, t), 0))
            return {"tur": "anlatim", "ders": d2, "makro": m2, "mikro": t,
                    "hedef": hedef, "cozulen": sim_cozulen.get((d2, t), 0)}
        return None

    def _skor(c, bugun_dersler):
        kredi = SORU_AGIRLIKLARI.get(c["makro"], 8.0)
        s = kredi * 0.8 + alarm_bonus.get(c["ders"], 0.0) * 0.2
        if c["tur"] == "soru":
            s += 6.0  # başlanan işi bitir
        if c["ders"] in bugun_dersler:
            s *= 0.35  # aynı gün farklı derslere dağıt
        return s

    rows = []
    bugun_dt = get_tr_now()
    yari = max(1, ana_blok_sayisi // 2)

    for idx in range(7):
        tarih_dt = bugun_dt + timedelta(days=idx)
        tarih_str = tarih_dt.strftime("%Y-%m-%d")
        gun_adi = GUN_ADLARI_LISTE[tarih_dt.weekday()]
        bugun_dersler = set()

        rows.append((
            gun_adi, "TYT Türkçe", "Paragraf", "Günlük Paragraf",
            f"📖 PARAGRAF: {paragraf_hedef} Paragraf Sorusu Çöz (~30 dk)",
            paragraf_hedef, "Ezber", tarih_str, "",
        ))

        if idx < len(hata_kuyrugu):
            h = hata_kuyrugu[idx]
            h_soru = min(15, slot_soru)
            rows.append((
                gun_adi, h["ders"], "Deneme Tekrarı", h["konu"],
                f"🔁 HATA TEKRARI: {h['konu']} ➔ {h_soru} soru çöz "
                f"({kolaydan_zora_dagilim(h_soru, 0.0)}). Denemede yanlış yaptığın soru tiplerini öne al.",
                h_soru, "Pekiştirme", tarih_str, "",
            ))

        for blok_no in range(ana_blok_sayisi):
            istenen = "Pekiştirme" if blok_no < yari else "Ezber"
            adaylar = {}
            for d_ad in ders_sirasi:
                a = _ders_adayi(d_ad)
                if a:
                    adaylar[(a["ders"], a["mikro"])] = a
            adaylar = list(adaylar.values())

            if not adaylar:
                if istenen == "Pekiştirme":
                    d, m, mi, ped = "TYT Matematik", "Karma Soru", "Soru Çözümü & Prova", "Pekiştirme"
                else:
                    d, m, mi, ped = "TYT Biyoloji", "Kavram Tekrarı", "Özet Not Çalışması", "Ezber"
                rows.append((
                    gun_adi, d, m, mi,
                    f"📌 GENEL TEKRAR: {slot_soru} karma soru çöz "
                    f"({kolaydan_zora_dagilim(slot_soru, 0.5)}) [Tahmini ~{int(slot_soru * 1.5)} dk]",
                    slot_soru, ped, tarih_str, "",
                ))
                continue

            tercih = [a for a in adaylar if get_konu_pedagoji_turu(a["ders"]) == istenen] or adaylar
            sec = max(tercih, key=lambda c: _skor(c, bugun_dersler))
            d, m, mi, hedef = sec["ders"], sec["makro"], sec["mikro"], sec["hedef"]
            ped = get_konu_pedagoji_turu(d, mi)
            bugun_dersler.add(d)

            if sec["tur"] == "anlatim":
                alts = MIKRO_ALT_KONULAR.get(mi, [])
                paket = []
                if alts:
                    nano_dk = _alt_dk(mi)
                    paket_dk = 0
                    for a in alts:
                        if (d, mi, a) in sim_alt:
                            continue
                        paket.append(a)
                        paket_dk += nano_dk
                        sim_alt.add((d, mi, a))
                        if len(paket) >= 3 or paket_dk >= 30:
                            break
                    mikro_bitti = all((d, mi, a) in sim_alt for a in alts)
                    per_nano = max(5, int(round(hedef / float(len(alts)) / 5.0) * 5))
                    soru = max(5, min(slot_soru, per_nano * len(paket), hedef))
                    liste_str = " | ".join(
                        f"{no}) {a} (~{nano_dk} dk)" for no, a in enumerate(paket, 1)
                    )
                    ogrenme_dk = paket_dk
                    bas = (
                        f"📌 ALT BAŞLIK + SORU: {mi} ➔ bugünün alt başlıkları: {liste_str}. "
                        "Her biri için ders videosunu izle ve 3-4 satır not çıkar; "
                    )
                    son_not = (
                        f" ✅ Bu görev bitince '{mi}' tamamlanmış olur, ardından soru kotası devreye girer."
                        if mikro_bitti else ""
                    )
                else:
                    soru = max(1, min(max(10, slot_soru // 2), hedef))
                    video = max(1, int(round(KONU_SURELERI_DK.get(mi, 60) / 30.0)))
                    ogrenme_dk = KONU_SURELERI_DK.get(mi, 60)
                    mikro_bitti = True
                    bas = f"📌 KONU + SORU: {mi} ➔ {video} ders videosu izle ve kısa özet çıkar, "
                    son_not = ""
                tahmini = ogrenme_dk + int(soru * 1.5)
                tanim = (
                    bas
                    + f"ardından {soru} soru çöz ({kolaydan_zora_dagilim(soru, 0.0)}). "
                    + f"Bu konunun toplam soru kotası: {hedef}, kota dolmadan sonraki konuya geçilmez."
                    + son_not
                    + f" [Tahmini ~{tahmini} dk]"
                )
                rows.append((gun_adi, d, m, mi, tanim, soru, ped, tarih_str, "||".join(paket)))
                if mikro_bitti:
                    sim_bilinen.add(mi)
                    takipli.add((d, mi))
                sim_cozulen[(d, mi)] = sim_cozulen.get((d, mi), 0) + soru

                if idx + 3 <= 6:  # 3 gün sonra aralıklı tekrar
                    t3 = bugun_dt + timedelta(days=idx + 3)
                    kapsam = ", ".join(paket) if paket else mi
                    rows.append((
                        GUN_ADLARI_LISTE[t3.weekday()], d, m, mi,
                        f"🔄 3 GÜNLÜK ARALIKLI TEKRAR: '{mi}' ({kapsam}) notlarını oku, 5 hatırlatma sorusu çöz.",
                        0, "Tekrar", t3.strftime("%Y-%m-%d"), "",
                    ))
            else:
                kalan = hedef - sec["cozulen"]
                soru = max(1, min(slot_soru, kalan))
                oran = sec["cozulen"] / float(max(1, hedef))
                tanim = (
                    f"🧩 SORU PEKİŞTİRME: {mi} ➔ {soru} soru çöz "
                    f"({kolaydan_zora_dagilim(soru, oran)}). "
                    f"Konu kotası: {sec['cozulen'] + soru}/{hedef} soru, kota dolmadan sonraki konuya geçilmez. "
                    f"[Tahmini ~{int(soru * 1.5)} dk]"
                )
                rows.append((gun_adi, d, m, mi, tanim, soru, ped, tarih_str, ""))
                sim_cozulen[(d, mi)] = sim_cozulen.get((d, mi), 0) + soru

    cursor.executemany(
        """INSERT INTO calisma_programi_gorevler
           (ogrenci_id, gun, ders, makro_konu, mikro_konu, gorev_tanimi, hedef_soru,
            pedagoji_turu, durum, tarih, alt_konu)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
        [(ogrenci_id,) + r for r in rows],
    )
    plan_soru = sum(r[5] for r in rows if r[6] != "Tekrar")
    cursor.execute(
        "INSERT INTO ogrenci_hiz_gecmisi (ogrenci_id, tarih, planlanan_gorev,"
        " planlanan_soru, kullanilan_katsayi) VALUES (?, ?, ?, ?, ?)",
        (ogrenci_id, bugun_dt.strftime("%Y-%m-%d"), len(rows), plan_soru, k),
    )
    return True
if "active_user" not in st.session_state:
    st.session_state.active_user = None

if "active_main_tab" not in st.session_state:
    st.session_state.active_main_tab = 0

if not st.session_state.active_user:
    st.title("🎯 KARAKOÇ YKS Akıllı Koçluk Sistemi")
    st.markdown("Kullanıcı adınız ve şifrenizle giriş yapabilirsiniz.")

    with st.form("login_form"):
        user_input = st.text_input(
            "Kullanıcı Adı veya T.C. Kimlik No:", placeholder="Örn: emirhan_k"
        )
        pass_input = st.text_input(
            "Şifre:", type="password", placeholder="••••••••"
        )
        submit_btn = st.form_submit_button(
            "Sisteme Giriş Yap", type="primary"
        )

        if submit_btn:
            if not user_input.strip() or not pass_input.strip():
                st.error("Lütfen tüm alanları doldurunuz!")
            else:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """SELECT id, tc_no, kullanici_adi, sifre_hash, ad, hedef_alan, sinif_seviyesi, 
                                   alan_kilitli, rol, hesap_durumu, lisans_bitis, streak_count, diploma_notu 
                           FROM ogrenciler 
                           WHERE kullanici_adi = ? OR tc_no = ?""",
                        (user_input.strip(), user_input.strip()),
                    )
                    user = cursor.fetchone()

                if user:
                    stored_hash = user[3]
                    hesap_durumu = user[9]
                    lisans_bitis_str = user[10]

                    if hesap_durumu == "Pasif":
                        st.error(
                            "🚫 Hesabınız dondurulmuştur/pasif durumdadır."
                            " Lütfen koçunuzla iletişime geçin."
                        )
                    elif hesap_durumu == "İptal Edildi":
                        st.error(
                            "❌ Üyeliğiniz iptal edilmiştir. Sisteme giriş"
                            " yapamazsınız."
                        )
                    elif (
                        lisans_bitis_str
                        and datetime.strptime(
                            lisans_bitis_str, "%Y-%m-%d"
                        ).date()
                        < get_tr_now().date()
                    ):
                        st.error(
                            "⏳ Üyelik süreniz dolmuştur! Lütfen koçunuzla"
                            " iletişime geçin."
                        )
                    elif stored_hash and verify_password(
                        stored_hash, pass_input.strip()
                    ):
                        updated_streak = update_user_streak(user[0])
                        st.session_state.active_user = {
                            "id": user[0],
                            "tc_no": user[1],
                            "kullanici_adi": user[2],
                            "ad": user[4],
                            "hedef_alan": user[5],
                            "sinif_seviyesi": user[6],
                            "alan_kilitli": user[7],
                            "rol": user[8],
                            "streak_count": updated_streak,
                            "diploma_notu": user[12] if user[12] else 85.0,
                        }
                        log_islem(
                            user[0], "LOGIN", "Kullanıcı başarıyla giriş yaptı."
                        )
                        set_flash_message(
                            "success", f"Hoş geldin, {user[4]}."
                        )
                        st.rerun()
                    else:
                        st.error("❌ Hatalı şifre veya kullanıcı adı!")
                else:
                    st.error("❌ Böyle bir kullanıcı bulunamadı.")
    st.stop()

current_user = st.session_state.active_user


# ==============================================================================
# MÜFREDAT VE ALARM YARDIMCI FONKSİYONLARI (GÜNCELLENMİŞ MİMARİ & BUG FIXES)
# ==============================================================================
def build_student_curriculum(sinif, alan):
    if sinif == "9. Sınıf":
        return mufredat_maarif_9
    elif sinif == "10. Sınıf":
        return mufredat_klasik.get("TYT", {})
    else:
        birlesik_mufredat = {}
        tyt_dict = mufredat_klasik.get("TYT", {})
        for ders_k, ders_v in tyt_dict.items():
            clean_key = ders_k if ders_k.startswith("TYT") else f"TYT {ders_k}"
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
            "SELECT ders, mikro_konu FROM konu_durumlari_detay WHERE ogrenci_id"
            " = ? AND durum = 'Biliyorum'",
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


# GÜNCELLENMİŞ ALARM ENGINE: 3 FARKLI DENEME KONTROLÜ VE YENİ UYARI METİNLERİ
def hesapla_tum_alarmlar(ogrenci_id, mevcut_sinif, aktif_mufredat):
    alarmlar = {"siyah": [], "kirmizi": [], "mor": [], "turuncu": [], "mavi": []}
    ogrenci_skor = SINIF_SEVIYE_SKORU.get(mevcut_sinif, 4)

    with get_connection() as c:
        df_bilinen = pd.read_sql_query(
            "SELECT ders, makro_konu, mikro_konu FROM konu_durumlari_detay"
            " WHERE ogrenci_id = ? AND durum = 'Biliyorum'",
            c,
            params=(ogrenci_id,),
        )
        df_yanlislar = pd.read_sql_query(
            "SELECT id, deneme_adi, tarih, ders, makro_konu, konu_adi, yanlis_adedi, yanlis_nedeni"
            " FROM deneme_konu_yanlislari WHERE ogrenci_id = ? AND (durum IS"
            " NULL OR durum = 'Aktif') ORDER BY id ASC",
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
            # Farklı denemelerdeki performans dizisini al
            distinct_exams = group.drop_duplicates(subset=["deneme_adi"], keep="last")
            yanlis_listesi = distinct_exams["yanlis_adedi"].tolist()
            son_yanlis = yanlis_listesi[-1] if yanlis_listesi else 0
            son_neden = group["yanlis_nedeni"].iloc[-1]

            cta_text = (
                "Bu konudaki eksiğini haftalarca tek başına kapatmaya çalışmak yerine "
                "1-2 saatlik birebir özel ders seansıyla anında çözebilirsin."
            )

            # ⬛ Siyah Alarm: En az 3 FARKLI denemede yanlış sayısı sürekli ivmelenerek artıyorsa (1 -> 2 -> 4)
            if (
                len(yanlis_listesi) >= 3
                and yanlis_listesi[-3] < yanlis_listesi[-2] < yanlis_listesi[-1]
            ):
                alarmlar["siyah"].append({
                    "id_list": yanlis_ids,
                    "ders": ders,
                    "konu": konu,
                    "detay": (
                        f"Son 3 farklı denemedir yanlış sayısı ivmelenerek artıyor! "
                        f"({yanlis_listesi[-3]} ➔ {yanlis_listesi[-2]} ➔ {yanlis_listesi[-1]})"
                    ),
                    "aksiyon": cta_text,
                    "neden": son_neden,
                })

            # 🟣 Mor Alarm: Ancak ve ancak aynı konuda EN AZ 3 FARKLI denemedir KESİNTİSİZ yanlış yapılmışsa
            elif len(yanlis_listesi) >= 3 and all(
                y > 0 for y in yanlis_listesi[-3:]
            ):
                alarmlar["mor"].append({
                    "id_list": yanlis_ids,
                    "ders": ders,
                    "konu": konu,
                    "detay": (
                        "Son 3 farklı denemedir bu konuda düzenli olarak yanlış yapılıyor."
                    ),
                    "aksiyon": cta_text,
                    "neden": son_neden,
                })

            # 🔴 Kırmızı Alarm: "Biliyorum" olarak işaretlenen müfredat konusunda yanlış yapıldığında
            if (ders, konu) in bilinen_pairs:
                alarmlar["kirmizi"].append({
                    "id_list": yanlis_ids,
                    "ders": ders,
                    "konu": konu,
                    "detay": (
                        f"Tamamlandı ('Biliyorum') olarak işaretlenen konuda {son_yanlis} yanlış yapıldı!"
                    ),
                    "aksiyon": cta_text,
                    "neden": son_neden,
                })

    for hedef_konu, kural in ON_KOSULLAR.items():
        min_sinif = kural["min_sinif"]
        on_kosul_listesi = kural["on_kosul"]
        hedef_ders = kural.get("ders", "")

        if hedef_konu in bilinen_mikro_set or hedef_konu in bilinen_makro_set:
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
                    if (
                        ok not in bilinen_mikro_set
                        and ok not in bilinen_makro_set
                    ):
                        alarmlar["turuncu"].append({
                            "ders": (
                                hedef_ders
                                if hedef_ders
                                else "İleri Seviye Odak Konusu"
                            ),
                            "konu": f"{hedef_konu} (Temel Eksik: {ok})",
                            "detay": (
                                f"'{hedef_konu}' konusunu iyi anlamak için önce"
                                f" **'{ok}'** konusunu tamamlamalısınız."
                            ),
                            "aksiyon": (
                                f"Önce '{ok}' konusunun temelini çalışın."
                            ),
                            "neden": "Ön Koşul Eksikliği",
                        })

    (
        tyt_o,
        ayt_o,
        gercek_tamamlanma_orani,
    ) = hesapla_tyt_ayt_tamamlanma(ogrenci_id, aktif_mufredat)
    ay_adi, hedef_yuzde = get_aylik_mufredat_hedevi(mevcut_sinif)
    delta_yuzde = round(gercek_tamamlanma_orani - hedef_yuzde, 1)

    if delta_yuzde < 0 and gercek_tamamlanma_orani < 100.0:
        alarmlar["mavi"].append({
            "ders": "Müfredat Takvimi",
            "konu": (
                f"{ay_adi} Ayı Hedefi (%{abs(delta_yuzde)} Geride)"
            ),
            "detay": (
                f"{ay_adi} ayı hedeflenen tamamlama oranının"
                f" **-%{abs(delta_yuzde)}** gerisindesiniz."
            ),
            "aksiyon": "Haftalık çalışma temanıza 1 ek çalışma bloğu ekleyin.",
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

    return alarmlar, saglik_skoru, delta_yuzde, gercek_tamamlanma_orani, hedef_yuzde


# ==============================================================================
# 👑 ADMİN / YÖNETİCİ PANELİ
# ==============================================================================
if current_user["rol"] == "admin":
    st.title("👑 KARAKOÇ KOÇLUK YÖNETİCİ PANELİ")
    st.markdown(
        f"Hoş Geldiniz, **{current_user['ad']}**. Tüm öğrencileri buradan"
        " yönetebilir, düzenleyebilir ve ders taleplerini inceleyebilirsiniz."
    )

    admin_tab1, admin_tab2, admin_tab3 = st.tabs([
        "➕ 1. Yeni Öğrenci Ekle",
        "👥 2. Öğrenci Düzenleme & Yönetim",
        "🛒 3. Özel Ders Talepleri",
    ])

    with admin_tab1:
        st.subheader("📝 Yeni Öğrenci Kaydı")
        with st.form("admin_create_user_form"):
            col_u1, col_u2 = st.columns(2)
            with col_u1:
                new_ad = st.text_input(
                    "Ad Soyad:", placeholder="Örn: Ahmet Yılmaz"
                )
                new_username = st.text_input(
                    "Kullanıcı Adı:", placeholder="Örn: ahmet_yilmaz"
                )
                new_pass = st.text_input(
                    "Şifre:", type="password", placeholder="••••••••"
                )
                new_tc = st.text_input(
                    "T.C. Kimlik No:", max_chars=11, placeholder="11 Haneli TC"
                )
            with col_u2:
                new_alan = st.selectbox(
                    "YKS Alanı:", ["Sayısal", "Eşit Ağırlık", "Sözel", "Dil"]
                )
                new_sinif = st.selectbox(
                    "Sınıf Seviyesi:",
                    ["9. Sınıf", "10. Sınıf", "11. Sınıf", "12. Sınıf", "Mezun"],
                )
                new_obp = st.number_input(
                    "Diploma Notu (OBP):",
                    min_value=50.0,
                    max_value=100.0,
                    value=85.0,
                    step=0.1,
                )
                new_lisans_gun = st.number_input(
                    "Lisans Süresi (Gün):",
                    min_value=30,
                    max_value=730,
                    value=365,
                )

            if st.form_submit_button(
                "🚀 Öğrenci Kaydını Oluştur", type="primary"
            ):
                if (
                    not new_ad.strip()
                    or not new_username.strip()
                    or not new_pass.strip()
                    or not new_tc.strip()
                ):
                    st.error("Lütfen zorunlu alanları doldurunuz!")
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
                                   (tc_no, kullanici_adi, sifre_hash, ad, hedef_alan, sinif_seviyesi, alan_kilitli, rol, hesap_durumu, lisans_bitis, streak_count, son_aktif_tarih, diploma_notu) 
                                   VALUES (?, ?, ?, ?, ?, ?, 1, 'ogrenci', 'Aktif', ?, 1, ?, ?)""",
                                (
                                    new_tc.strip(),
                                    new_username.strip(),
                                    pass_h,
                                    new_ad.strip(),
                                    new_alan,
                                    new_sinif,
                                    lisans_tarihi,
                                    get_tr_now().strftime("%Y-%m-%d"),
                                    new_obp,
                                ),
                            )
                            conn.commit()
                        log_islem(
                            current_user["id"],
                            "ADMIN_CREATE_USER",
                            f"Kullanıcı eklendi: {new_username}",
                        )
                        set_flash_message(
                            "success",
                            f"🎉 '{new_ad}' kaydı başarıyla oluşturuldu!",
                        )
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error(
                            "⚠️ Bu Kullanıcı Adı veya T.C. Kimlik Numarası"
                            " sistemde zaten var!"
                        )

    with admin_tab2:
        st.subheader("👥 Öğrenci Listesi ve Tam Yetkili Düzenleme")
        with get_connection() as conn:
            df_ogrenciler = pd.read_sql_query(
                "SELECT id, kullanici_adi, tc_no, ad, hedef_alan, sinif_seviyesi,"
                " diploma_notu, hesap_durumu, lisans_bitis FROM ogrenciler"
                " WHERE rol != 'admin'",
                conn,
            )

        if not df_ogrenciler.empty:
            st.dataframe(df_ogrenciler, width="stretch")

            st.markdown("---")
            st.subheader("🛠️ Seçili Öğrenci Bilgilerini Düzenle")
            selected_user_id = st.selectbox(
                "İşlem Yapılacak Öğrenciyi Seçin:",
                options=df_ogrenciler["id"].tolist(),
                format_func=lambda x: (
                    f"{df_ogrenciler[df_ogrenciler['id']==x]['ad'].values[0]}"
                    " ("
                    f"{df_ogrenciler[df_ogrenciler['id']==x]['kullanici_adi'].values[0]}"
                    ")"
                ),
            )

            ogr_row = df_ogrenciler[
                df_ogrenciler["id"] == selected_user_id
            ].iloc[0]

            with st.form("admin_edit_full_user_form"):
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    edit_ad = st.text_input("Ad Soyad:", value=ogr_row["ad"])
                    edit_username = st.text_input(
                        "Kullanıcı Adı:", value=ogr_row["kullanici_adi"]
                    )
                    edit_tc = st.text_input(
                        "T.C. Kimlik No:", value=ogr_row["tc_no"], max_chars=11
                    )
                    edit_pass = st.text_input(
                        "Yeni Şifre (Boş bırakılırsa değişmez):",
                        type="password",
                    )
                with col_e2:
                    edit_alan = st.selectbox(
                        "Hedef Alan:",
                        ["Sayısal", "Eşit Ağırlık", "Sözel", "Dil"],
                        index=[
                            "Sayısal",
                            "Eşit Ağırlık",
                            "Sözel",
                            "Dil",
                        ].index(ogr_row["hedef_alan"]),
                    )
                    edit_sinif = st.selectbox(
                        "Sınıf Seviyesi:",
                        [
                            "9. Sınıf",
                            "10. Sınıf",
                            "11. Sınıf",
                            "12. Sınıf",
                            "Mezun",
                        ],
                        index=[
                            "9. Sınıf",
                            "10. Sınıf",
                            "11. Sınıf",
                            "12. Sınıf",
                            "Mezun",
                        ].index(ogr_row["sinif_seviyesi"]),
                    )
                    edit_obp = st.number_input(
                        "Diploma Notu (OBP):",
                        min_value=50.0,
                        max_value=100.0,
                        value=float(ogr_row["diploma_notu"]),
                        step=0.1,
                    )
                    edit_durum = st.selectbox(
                        "Üyelik / Hesap Durumu:",
                        ["Aktif", "Pasif", "İptal Edildi"],
                        index=["Aktif", "Pasif", "İptal Edildi"].index(
                            ogr_row["hesap_durumu"]
                        ),
                    )

                col_sub1, col_sub2 = st.columns(2)
                with col_sub1:
                    save_btn = st.form_submit_button(
                        "💾 Değişiklikleri Kaydet", type="primary"
                    )
                with col_sub2:
                    delete_btn = st.form_submit_button(
                        "🗑️ Öğrenci Kaydını Tamamen Sil"
                    )

                if save_btn:
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        if edit_pass.strip():
                            new_h = hash_password(edit_pass.strip())
                            cursor.execute(
                                """UPDATE ogrenciler 
                                   SET ad=?, kullanici_adi=?, tc_no=?, hedef_alan=?, sinif_seviyesi=?, diploma_notu=?, hesap_durumu=?, sifre_hash=? 
                                   WHERE id=?""",
                                (
                                    edit_ad.strip(),
                                    edit_username.strip(),
                                    edit_tc.strip(),
                                    edit_alan,
                                    edit_sinif,
                                    edit_obp,
                                    edit_durum,
                                    new_h,
                                    selected_user_id,
                                ),
                            )
                        else:
                            cursor.execute(
                                """UPDATE ogrenciler 
                                   SET ad=?, kullanici_adi=?, tc_no=?, hedef_alan=?, sinif_seviyesi=?, diploma_notu=?, hesap_durumu=? 
                                   WHERE id=?""",
                                (
                                    edit_ad.strip(),
                                    edit_username.strip(),
                                    edit_tc.strip(),
                                    edit_alan,
                                    edit_sinif,
                                    edit_obp,
                                    edit_durum,
                                    selected_user_id,
                                ),
                            )
                        conn.commit()
                    log_islem(
                        current_user["id"],
                        "ADMIN_UPDATE_USER",
                        f"ID {selected_user_id} güncellendi.",
                    )
                    set_flash_message(
                        "success", "Öğrenci bilgileri güncellendi!"
                    )
                    st.rerun()

                if delete_btn:
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "DELETE FROM ogrenciler WHERE id = ?",
                            (selected_user_id,),
                        )
                        conn.commit()
                    log_islem(
                        current_user["id"],
                        "ADMIN_DELETE_USER",
                        f"ID {selected_user_id} silindi.",
                    )
                    set_flash_message("warning", "Öğrenci kaydı silindi!")
                    st.rerun()
        else:
            st.info("Sistemde henüz kayıtlı öğrenci bulunmuyor.")

    with admin_tab3:
        st.subheader("📜 Öğrenci Özel Ders Talepleri")
        with get_connection() as conn:
            df_all_talepler = pd.read_sql_query(
                "SELECT t.id, o.ad as ogrenci_adi, t.ders, t.konu, t.alarm_turu,"
                " t.talep_tarihi, t.durum FROM pazaryeri_talepler t JOIN"
                " ogrenciler o ON t.ogrenci_id = o.id ORDER BY t.id DESC",
                conn,
            )
        if not df_all_talepler.empty:
            for idx, r in df_all_talepler.iterrows():
                col_adm1, col_adm2 = st.columns([4, 1])
                with col_adm1:
                    st.write(
                        f"👤 **{r['ogrenci_adi']}** | 📘 **{r['ders']} -"
                        f" {r['konu']}** | Tarih: `{r['talep_tarihi']}` | Durum:"
                        f" `{r['durum']}`"
                    )
                with col_adm2:
                    if r["durum"] != "Tamamlandı":
                        if st.button(
                            "✔️ Talebi Onayla", key=f"adm_btn_{r['id']}"
                        ):
                            with get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "UPDATE pazaryeri_talepler SET durum ="
                                    " 'Tamamlandı' WHERE id = ?",
                                    (r["id"],),
                                )
                                conn.commit()
                            log_islem(
                                current_user["id"],
                                "ADMIN_APPROVE",
                                f"Talep ID {r['id']} onaylandı.",
                            )
                            set_flash_message("success", "Talep tamamlandı!")
                            st.rerun()
                st.markdown("---")
        else:
            st.info("Henüz özel ders talebi yok.")

    st.markdown("---")
    if st.button("🚪 Yönetici Oturumunu Kapat"):
        st.session_state.active_user = None
        st.rerun()
    st.stop()


# ==============================================================================
# ÖĞRENCİ KOKPİT ARAYÜZÜ (GÜNCELLENMİŞ 6-TABLI SIRA & YENİ ARAYÜZ MİMARİSİ)
# ==============================================================================
is_maarif = current_user["sinif_seviyesi"] in ["9. Sınıf", "10. Sınıf"]
(
    alarmlar_db,
    saglik_skoru,
    delta_yuzde,
    gercek_orand,
    hedef_yuzd,
) = hesapla_tum_alarmlar(
    current_user["id"], current_user["sinif_seviyesi"], aktif_mufredat_hiyerarsisi
)
tyt_orani, ayt_orani, genel_tamamlanma_orani = hesapla_tyt_ayt_tamamlanma(
    current_user["id"], aktif_mufredat_hiyerarsisi
)

with st.sidebar:
    st.title("🎓 Öğrenci Profili")
    st.write(f"**Öğrenci:** {current_user['ad']}")
    st.write(f"**Kullanıcı Adı:** `{current_user['kullanici_adi']}`")
    st.write(f"**Alan:** `{current_user['hedef_alan']}`")
    st.write(f"**Sınıf:** `{current_user['sinif_seviyesi']}`")
    st.write(
        "**Diploma Notu (OBP):**"
        f" `{current_user.get('diploma_notu', 85.0)}`"
    )

    st.markdown(
        """<div class="streak-card">🔥 <b>Çalışma Serisi:"""
        f" {current_user['streak_count']} Gün</b></div>",
        unsafe_allow_html=True,
    )

    st.markdown(f"**TYT Müfredatı:** `%{tyt_orani}`")
    st.markdown(f"**AYT Müfredatı:** `%{ayt_orani}`")

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
    st.subheader("⚙️ Profil Bilgileri")
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
                [
                    "9. Sınıf",
                    "10. Sınıf",
                    "11. Sınıf",
                    "12. Sınıf",
                    "Mezun",
                ].index(current_user["sinif_seviyesi"])
                if current_user["sinif_seviyesi"]
                in ["9. Sınıf", "10. Sınıf", "11. Sınıf", "12. Sınıf", "Mezun"]
                else 3
            ),
        )
        yeni_obp = st.number_input(
            "Diploma Notu (OBP):",
            min_value=50.0,
            max_value=100.0,
            value=float(current_user.get("diploma_notu", 85.0)),
            step=0.1,
        )

        if st.form_submit_button("Profili Güncelle", type="secondary"):
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE ogrenciler SET hedef_alan = ?, sinif_seviyesi = ?,"
                    " diploma_notu = ? WHERE id = ?",
                    (yeni_alan, yeni_sinif, yeni_obp, current_user["id"]),
                )
                conn.commit()
            st.session_state.active_user["hedef_alan"] = yeni_alan
            st.session_state.active_user["sinif_seviyesi"] = yeni_sinif
            st.session_state.active_user["diploma_notu"] = yeni_obp
            log_islem(
                current_user["id"],
                "UPDATE_PROFILE",
                f"Alan: {yeni_alan}, OBP: {yeni_obp}",
            )
            set_flash_message("success", "Profiliniz güncellendi!")
            st.rerun()

    st.markdown("---")
    if st.button("🚪 Oturumu Kapat"):
        st.session_state.active_user = None
        st.rerun()

st.title(
    "🎯 KARAKOÇ YKS Akıllı Koçluk Paneli ("
    f"{current_user['hedef_alan']} - {current_user['sinif_seviyesi']})"
)

toplam_alarm_sayisi = sum(len(v) for v in alarmlar_db.values())
ay_adi_kokpit, _ = get_aylik_mufredat_hedevi(current_user["sinif_seviyesi"])

m1, m2, m3, m4 = st.columns(4)
m1.metric("🏥 Genel İlerleme Skoru", f"%{saglik_skoru}")
m2.metric("🔥 Çalışma Serisi", f"{current_user['streak_count']} Gün")
m3.metric("🚨 Dikkat Edilecek Konu", f"{toplam_alarm_sayisi} Adet")
delta_label = (
    f"+%{delta_yuzde} İleride"
    if delta_yuzde >= 0
    else f"-%{abs(delta_yuzde)} Geride"
)
m4.metric(
    f"📅 {ay_adi_kokpit} Ayı Takvimi",
    f"%{round(gercek_orand, 1)}",
    delta=delta_label,
)

st.markdown("---")

# KRİTİK ALARMLAR BANNERLARI
if alarmlar_db["siyah"]:
    for a in alarmlar_db["siyah"]:
        st.markdown(
            '<div class="alarm-card-black"><b>⬛ [KRİTİK İVMELENEN YANLIŞ UYARISI]'
            f" {a['ders']} - {a['konu']}</b><br>• {a['detay']}<br>👉"
            f" <b>{a['aksiyon']}</b></div>",
            unsafe_allow_html=True,
        )

if alarmlar_db["kirmizi"]:
    for a in alarmlar_db["kirmizi"]:
        st.error(
            f"🔴 **[DİKKAT - TAMAMLANAN KONUDA YANLIŞ]** **{a['ders']} - {a['konu']}** | {a['detay']}\n\n👉"
            f" **{a['aksiyon']}**"
        )

# YENİ ARAYÜZ MİMARİSİ: 6 SEKMELİ DÜZEN VE SEKME SIÇRAMA KORUMASI
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🎯 Bugünün Görevleri (Odak Ekranı)",
    "📚 Konu Takip & İlerleme",
    "📝 Deneme Analizi",
    "🚨 Konu Uyarıları & Alarmlar",
    "📅 Haftalık Çalışma Programı & ÖSYM Simülatörü",
    "🤝 Özel Ders & Raporlar",
])


def on_mikro_change(ders_adi, makro_adi, mikro_ad, key_name):
    val = st.session_state.get(key_name, False)
    with get_connection() as c:
        cur = c.cursor()
        if val:
            cur.execute(
                "INSERT INTO konu_durumlari_detay (ogrenci_id, ders,"
                " makro_konu, mikro_konu, durum) VALUES (?, ?, ?, ?,"
                " 'Biliyorum') ON CONFLICT DO UPDATE SET durum='Biliyorum'",
                (current_user["id"], ders_adi, makro_adi, mikro_ad),
            )
        else:
            cur.execute(
                "DELETE FROM konu_durumlari_detay WHERE ogrenci_id = ? AND"
                " ders = ? AND makro_konu = ? AND mikro_konu = ?",
                (current_user["id"], ders_adi, makro_adi, mikro_ad),
            )
        c.commit()
    log_islem(current_user["id"], "TOPIC_TOGGLE", f"{ders_adi} -> {mikro_ad}")
    if val:
        soru_borcu_baslat(current_user["id"], ders_adi, [mikro_ad])
        alt_konulari_senkronla(current_user["id"], ders_adi, makro_adi, [mikro_ad], val)


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
                    "INSERT INTO konu_durumlari_detay (ogrenci_id, ders,"
                    " makro_konu, mikro_konu, durum) VALUES (?, ?, ?, ?,"
                    " 'Biliyorum')",
                    (current_user["id"], ders_adi, makro_adi, m),
                )
        c.commit()
        if val:
            soru_borcu_baslat(current_user["id"], ders_adi, mikro_listesi)
    for m in mikro_listesi:
        st.session_state.pop(f"chk_{ders_adi}_{makro_adi}_{m}", None)
        alt_konulari_senkronla(current_user["id"], ders_adi, makro_adi, mikro_listesi, val)


def on_ders_tamamen_bitir(ders_adi, makro_dict, bitir_mi=True):
    with get_connection() as c:
        cur = c.cursor()
        cur.execute(
            "DELETE FROM konu_durumlari_detay WHERE ogrenci_id = ? AND ders ="
            " ?",
            (current_user["id"], ders_adi),
        )
        if bitir_mi:
            for makro_ad, mikro_listesi in makro_dict.items():
                if isinstance(mikro_listesi, list):
                    for mik_ad in mikro_listesi:
                        cur.execute(
                            "INSERT INTO konu_durumlari_detay (ogrenci_id,"
                            " ders, makro_konu, mikro_konu, durum) VALUES (?,"
                            " ?, ?, ?, 'Biliyorum')",
                            (current_user["id"], ders_adi, makro_ad, mik_ad),
                        )
        c.commit()

    for makro_ad, mikro_listesi in makro_dict.items():
        if isinstance(mikro_listesi, list):
            for mik_ad in mikro_listesi:
                st.session_state.pop(
                    f"chk_{ders_adi}_{makro_ad}_{mik_ad}", None
                )
            st.session_state.pop(f"toplu_{ders_adi}_{makro_ad}", None)
    for makro_ad, mikro_listesi in makro_dict.items():
        if isinstance(mikro_listesi, list):
            alt_konulari_senkronla(
                current_user["id"], ders_adi, makro_ad, mikro_listesi, bitir_mi
            )


def resolve_alarm(id_list):
    if not id_list:
        return
    with get_connection() as c:
        cur = c.cursor()
        placeholders = ",".join("?" * len(id_list))
        cur.execute(
            "UPDATE deneme_konu_yanlislari SET durum = 'Çözüldü' WHERE id IN"
            f" ({placeholders})",
            id_list,
        )
        c.commit()


# ==============================================================================
# TAB 1: BUGÜNÜN GÖREVLERİ (ODAK EKRANI)
# ==============================================================================
with tab1:
    st.header("🎯 Bugünün Görevleri (Odak Ekranı)")
    st.markdown(
        "Gününüzü dağıtmadan tam odakla bitirmeniz gereken **3-4 net çalışma görevi** aşağıdadır."
    )

    bugun_dt = get_tr_now()
    bugun_str = bugun_dt.strftime("%Y-%m-%d")
    gun_adlari_tr = {
        "Monday": "Pazartesi",
        "Tuesday": "Salı",
        "Wednesday": "Çarşamba",
        "Thursday": "Perşembe",
        "Friday": "Cuma",
        "Saturday": "Cumartesi",
        "Sunday": "Pazar",
    }
    bugun_gun_adi = gun_adlari_tr.get(bugun_dt.strftime("%A"), "Pazartesi")

    with get_connection() as conn:
        df_bugun = pd.read_sql_query(
            "SELECT id, ders, makro_konu, mikro_konu, gorev_tanimi, hedef_soru, pedagoji_turu, durum "
            "FROM calisma_programi_gorevler WHERE ogrenci_id = ? AND (tarih = ? OR gun = ?)",
            conn,
            params=(current_user["id"], bugun_str, bugun_gun_adi),
        )

    if not df_bugun.empty:
        biten_cnt = len(df_bugun[df_bugun["durum"] == 1])
        toplam_cnt = len(df_bugun)
        yuzde_bugun = int((biten_cnt / toplam_cnt) * 100) if toplam_cnt > 0 else 0

        col_t1, col_t2 = st.columns([3, 1])
        with col_t1:
            st.subheader(f"📅 Bugüne Ait İlerleme (%{yuzde_bugun})")
            st.progress(yuzde_bugun / 100.0)
        with col_t2:
            st.metric("Tamamlanan Görev", f"{biten_cnt} / {toplam_cnt}")

        st.markdown("---")

        for _, g_row in df_bugun.iterrows():
            g_id = g_row["id"]
            is_done = bool(g_row["durum"])
            ped = g_row["pedagoji_turu"]

            st.markdown(
                f'<div class="focus-task-card">'
                f'<h4>{"✅" if is_done else "📌"} {g_row["ders"]} - {g_row["mikro_konu"]}</h4>'
                f'<p style="font-size: 1.05rem; margin-bottom: 8px;">{g_row["gorev_tanimi"]}</p>'
                f'<span style="background-color:#e0e7ff; color:#3730a3; padding:2px 8px; border-radius:6px; font-size:0.85rem; font-weight:600;">{ped}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            col_chk1, col_chk2 = st.columns([4, 1])
            with col_chk2:
                chk_val = st.checkbox(
                    "Tamamladım",
                    value=is_done,
                    key=f"focus_chk_{g_id}",
                )
                if chk_val != is_done:
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE calisma_programi_gorevler SET durum = ? WHERE id = ?",
                            (1 if chk_val else 0, g_id),
                        )
                        conn.commit()
                    log_islem(
                        current_user["id"],
                        "TASK_TOGGLE_FOCUS",
                        f"Gorev ID {g_id} -> {chk_val}",
                    )
                    soru_ilerleme_isle(g_id, chk_val)
                    gorev_alt_konu_isle(g_id, chk_val)
                    st.rerun()
    else:
        st.info("💡 Bugüne tanımlanmış henüz bir çalışma görevi bulunmuyor. 'Tab 5: Haftalık Çalışma Programı' sekmesinden akıllı programınızı tek tıkla oluşturabilirsiniz!")


# ==============================================================================
# TAB 2: KONU TAKİP & İLERLEME
# ==============================================================================
with tab2:
    st.header("📚 Konu Takip Listesi")
    with get_connection() as conn:
        df_tum_bilinenler = pd.read_sql_query(
            "SELECT ders, makro_konu, mikro_konu FROM konu_durumlari_detay"
            " WHERE ogrenci_id = ? AND durum = 'Biliyorum'",
            conn,
            params=(current_user["id"],),
        )
    bilinen_pairs_set = set(
        zip(df_tum_bilinenler["ders"], df_tum_bilinenler["mikro_konu"])
    )
    alt_durum_seti = set(alt_durumlari_yukle(current_user["id"]))

    if aktif_mufredat_hiyerarsisi:
        ders_tablari = st.tabs(list(aktif_mufredat_hiyerarsisi.keys()))

        for i, (ders_adi, makro_konular) in enumerate(
            aktif_mufredat_hiyerarsisi.items()
        ):
            with ders_tablari[i]:
                st.subheader(f"📖 {ders_adi}")
                col_btn1, col_btn2 = st.columns([3, 1])
                with col_btn1:
                    if st.button(
                        f"🚀 {ders_adi} Dersinin Tümünü Tamamla",
                        key=f"btn_full_finish_{ders_adi}",
                        type="primary",
                    ):
                        on_ders_tamamen_bitir(
                            ders_adi, makro_konular, bitir_mi=True
                        )
                        set_flash_message(
                            "success",
                            f"🎉 {ders_adi} dersinin tüm konuları tamamlandı!",
                        )
                        st.rerun()
                with col_btn2:
                    if st.button(
                        f"🧹 {ders_adi} Sıfırla",
                        key=f"btn_full_reset_{ders_adi}",
                        type="secondary",
                    ):
                        on_ders_tamamen_bitir(
                            ders_adi, makro_konular, bitir_mi=False
                        )
                        set_flash_message(
                            "warning", f"{ders_adi} dersi konuları sıfırlandı."
                        )
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
                                f"{'✅' if yuzde == 100 else '📌'} {makro_adi}"
                                f" (%{yuzde} Tamamlandı)"
                            )
                            with st.expander(
                                expander_baslik, expanded=(yuzde < 100)
                            ):
                                st.progress(yuzde / 100.0)
                                col_ak1, col_ak2 = st.columns([3, 1])
                                with col_ak1:
                                    st.write("**Alt Konular:**")
                                    for mikro_ad in mikro_listesi:
                                        key_name = (
                                            f"chk_{ders_adi}_{makro_adi}_{mikro_ad}"
                                        )
                                        is_completed = (
                                            ders_adi,
                                            mikro_ad,
                                        ) in bilinen_pairs_set
                                        if key_name not in st.session_state:
                                            st.session_state[key_name] = (
                                                is_completed
                                            )

                                        sure_dk = KONU_SURELERI_DK.get(
                                            mikro_ad, 60
                                        )
                                        label_str = (
                                            f"{mikro_ad} ⏱️ (~{sure_dk} dk"
                                            " Çalışma Süresi)"
                                        )

                                        st.checkbox(
                                            label_str,
                                            key=key_name,
                                            on_change=on_mikro_change,
                                            args=(
                                                ders_adi,
                                                makro_adi,
                                                mikro_ad,
                                                key_name,
                                            ),
                                        )
                                        alt_konu_arayuzu_ciz(
                                            ders_adi, makro_adi, mikro_ad, alt_durum_seti
                                        )

                                with col_ak2:
                                    st.write("**Hızlı Seçim:**")
                                    toplu_key = f"toplu_{ders_adi}_{makro_adi}"
                                    if toplu_key not in st.session_state:
                                        st.session_state[toplu_key] = (
                                            yuzde == 100 and toplam_mikro > 0
                                        )
                                    st.checkbox(
                                        "Tümünü Tamamla",
                                        key=toplu_key,
                                        on_change=on_toplu_change,
                                        args=(
                                            ders_adi,
                                            makro_adi,
                                            mikro_listesi,
                                            toplu_key,
                                        ),
                                    )

# ==============================================================================
# TAB 3: DENEME ANALİZİ (YANLIŞ PAYLAŞTIRMA VE SIFIRDAN KATLANMA BUG-FIX)
# ==============================================================================
with tab3:
    st.header("📝 Deneme Analizi ve Net Girişi")
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
            '<div class="sim-card"><h3>1. Adım: Sınav Bilgileri</h3><p>Analiz'
            " etmek istediğiniz <b>Genel Deneme</b> veya <b>Branş"
            " Denemesi</b> bilgilerini giriniz.</p></div>",
            unsafe_allow_html=True,
        )
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            st.session_state.wiz_kategori = st.radio(
                "Deneme Türü:", ["Genel Deneme", "Branş Denemesi"], horizontal=True
            )
            st.session_state.wiz_tur = st.radio(
                "Sınav Kategorisi:",
                options=izinli_sinav_turleri,
                horizontal=True,
            )
            st.session_state.wiz_adi = st.text_input(
                "Deneme Sınavının Adı veya Yayın Evi:",
                placeholder="Örn: 3D TYT 2. Deneme",
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
                    or (
                        st.session_state.wiz_tur == "AYT"
                        and d.startswith("AYT")
                    )
                    or (
                        st.session_state.wiz_tur == "YDT"
                        and ("YDT" in d or "İngilizce" in d)
                    )
                ]
                if not uyumlu_dersler:
                    uyumlu_dersler = list(aktif_mufredat_hiyerarsisi.keys())
                st.session_state.wiz_brans_dersi = st.selectbox(
                    "Ders Seçimi:", options=uyumlu_dersler
                )
                max_net_val = (
                    40.0
                    if "Matematik" in st.session_state.wiz_brans_dersi
                    or "Türkçe" in st.session_state.wiz_brans_dersi
                    else 80.0
                )
                st.session_state.wiz_net = st.number_input(
                    "Branş Netiniz:",
                    min_value=0.0,
                    max_value=max_net_val,
                    value=min(25.0, max_net_val),
                    step=0.25,
                )
            else:
                st.session_state.wiz_brans_dersi = None
                max_genel_net = (
                    120.0 if st.session_state.wiz_tur == "TYT" else 80.0
                )
                st.session_state.wiz_net = st.number_input(
                    "Toplam Netiniz:",
                    min_value=0.0,
                    max_value=max_genel_net,
                    value=min(75.0, max_genel_net),
                    step=0.25,
                )
            if st.session_state.wiz_kategori == "Branş Denemesi":
                ders_secenekleri = [
                    "TYT Türkçe", "TYT Matematik", "TYT Fen", "TYT Sosyal",
                    "AYT Matematik", "AYT Fizik", "AYT Kimya", "AYT Biyoloji", "AYT Edebiyat"
                ]
                st.selectbox(
                    "Branş Dersi Seçin:",
                    options=ders_secenekleri,
                    key="wiz_brans_dersi",
                )
        if st.button("İleri ➔ Ders Seçimine Geç", type="primary"):
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
                st.error("Lütfen denemenin adını giriniz!")

    elif st.session_state.wiz_step == 2:
        st.markdown(
            '<div class="sim-card"><h3>2. Adım: Yanlış Yapılan Dersler</h3><p>Bu'
            " denemede yanlış veya boş bıraktığınız dersleri seçiniz.</p></div>",
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
                    in [
                        "Matematik ve Veri",
                        "Gramer ve Kelime",
                        "Soru Tipleri",
                    ]
                )
            )
            or (secilen_tur == "AYT" and d.startswith("AYT"))
            or (secilen_tur == "YDT" and ("YDT" in d or "İngilizce" in d))
        ]
        if not filtrated_dersler:
            filtrated_dersler = list(aktif_mufredat_hiyerarsisi.keys())

        seçilen_dersler = st.multiselect(
            f"Yanlış Bulunan {secilen_tur} Dersleri:",
            options=filtrated_dersler,
            default=(
                filtrated_dersler[:2]
                if len(filtrated_dersler) >= 2
                else filtrated_dersler
            ),
        )
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("⬅️ Geri Dön"):
                st.session_state.wiz_step = 1
                st.rerun()
        with col_b2:
            if st.button("İleri ➔ Konu İncelemesine Başla 🚀", type="primary"):
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
                    st.warning("En az 1 ders seçmelisiniz!")

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
            f"Konu Kontrolü: {card_idx + 1} / {toplam_kart} ➔"
            f" **{current_card['ders']}**"
        )

        col_hdr1, col_hdr2 = st.columns([3, 1])
        with col_hdr1:
            st.markdown(
                f'<div class="card-ders-title">📘 {current_card["ders"]}</div>',
                unsafe_allow_html=True,
            )
        with col_hdr2:
            if st.button(
                "⚡ Kalan Konuları Temiz Geç", key=f"btn_fp_{card_idx}"
            ):
                cur_ders = current_card["ders"]
                while (
                    st.session_state.wiz_card_idx < len(queue)
                    and queue[st.session_state.wiz_card_idx]["ders"]
                    == cur_ders
                ):
                    st.session_state.wiz_card_idx += 1
                st.session_state.wiz_show_details = False
                set_flash_message(
                    "success", f"{cur_ders} dersinin kalan konuları geçildi."
                )
                st.rerun()

        st.markdown(
            f'<div class="single-card-container"><div'
            f' class="card-konu-title">{current_card["makro"]}</div><p'
            ' style="font-size: 1.1rem; color: #374151;">Bu konuda yanlış'
            " veya boşunuz var mı?</p></div>",
            unsafe_allow_html=True,
        )

        if not st.session_state.wiz_show_details:
            st.markdown(
                '<div class="card-mega-buttons">', unsafe_allow_html=True
            )
            col_no, col_yes = st.columns(2)
            with col_no:
                if st.button("🟢 HAYIR (SORUN YOK)", key=f"btn_mega_no_{card_idx}"):
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
                f"⚠️ **{current_card['makro']}** konusu detaylarını seçin:"
            )
            secili_mikrolar = st.multiselect(
                "Hangi Alt Konuda Yanlış Yaşadınız?",
                options=current_card["mikro_listesi"],
                key=f"card_mikro_{card_idx}",
            )

            # ÇARPAN BUG'I ÇÖZÜMÜ: Alt konulara özel yanlış sayısı girilmesi
            mikro_yanlis_map = {}
            if secili_mikrolar:
                st.write("**Seçilen Her Alt Konunun Yanlış Sayısını Giriniz:**")
                for mik_item in secili_mikrolar:
                    mikro_yanlis_map[mik_item] = st.number_input(
                        f"• '{mik_item}' Yanlış Sayısı:",
                        min_value=1,
                        max_value=20,
                        value=1,
                        key=f"card_y_num_{card_idx}_{mik_item}",
                    )

            nedenler = st.multiselect(
                "Hata Nedeni:",
                [
                    "Konu Eksikliği",
                    "İşlem / Dikkat Hatası",
                    "Süre Yetişmedi",
                    "İki Şık Arasında Kaldım",
                    "Soruyu Yanlış Okudum",
                ],
                default=["Konu Eksikliği"],
                key=f"card_neden_{card_idx}",
            )
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                if st.button("⬅️ İptal Et (Hayır Say)"):
                    st.session_state.wiz_show_details = False
                    st.rerun()
            with col_c2:
                if st.button(
                    "Kaydet ve Devam Et ➔", type="primary"
                ):
                    if secili_mikrolar:
                        for mik in secili_mikrolar:
                            st.session_state.wiz_draft_mistakes.append({
                                "ders": current_card["ders"],
                                "makro": current_card["makro"],
                                "mikro": mik,
                                "yanlis_adedi": mikro_yanlis_map[mik],
                                "nedenler": ", ".join(nedenler),
                            })
                        st.session_state.wiz_card_idx += 1
                        st.session_state.wiz_show_details = False
                        st.rerun()
                    else:
                        st.error("En az 1 alt konu seçiniz!")

    elif st.session_state.wiz_step == 4:
        st.markdown(
            '<div class="sim-card"><h3>🎉 Deneme Analiziniz'
            " Kaydedildi!</h3><p><b>"
            f"[{st.session_state.wiz_kategori}] {st.session_state.wiz_tur} - {st.session_state.wiz_adi} ({st.session_state.wiz_net} Net)</b>"
            " kaydı oluşturuldu.</p></div>",
            unsafe_allow_html=True,
        )
        drafts = st.session_state.wiz_draft_mistakes
        if drafts:
            st.subheader("📌 Çalışma Listesine Eklenen Konular:")
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
            st.dataframe(pd.DataFrame(drafts), width="stretch")
            log_islem(
                current_user["id"],
                "FINISH_EXAM_ANALYSIS",
                f"{st.session_state.wiz_adi}: {len(drafts)} yanlış kaydedildi.",
            )
        else:
            st.info("Bu denemede yanlış konusu bulunmuyor. Tebrikler!")

        if st.button("🚀 Yeni Deneme Ekle", type="primary"):
            st.session_state.wiz_step = 1
            st.session_state.wiz_draft_mistakes = []
            st.session_state.wiz_selected_dersler = []
            st.session_state.wiz_card_idx = 0
            st.session_state.wiz_show_details = False
            st.rerun()

    st.markdown("---")
    st.subheader("📊 Net Gelişim Grafikleri ve Filtreleme")
    
    # BRANŞ VE GENEL DENEME KESİN AYRIM FİLTRESİ
    kat_filter = st.selectbox(
        "Grafik İçin Deneme Türü Filtresi:",
        ["Tümü", "Genel Deneme", "Branş Denemesi"]
    )

    grafik_tab1, grafik_tab2, grafik_tab3 = st.tabs(
        ["📈 TYT Denemeleri", "📈 AYT Denemeleri", "🔍 Hata Nedenleri"]
    )

    with grafik_tab1:
        with get_connection() as conn:
            query = "SELECT deneme_adi, MAX(net_bilgisi) as net_bilgisi FROM deneme_konu_yanlislari WHERE ogrenci_id = ? AND deneme_turu = 'TYT'"
            params = [current_user["id"]]
            if kat_filter != "Tümü":
                query += " AND deneme_kategorisi = ?"
                params.append(kat_filter)
            query += " GROUP BY deneme_adi ORDER BY id ASC"
            df_tyt_genel = pd.read_sql_query(query, conn, params=params)

        if not df_tyt_genel.empty:
            st.line_chart(df_tyt_genel.set_index("deneme_adi")["net_bilgisi"])
        else:
            st.info("Seçili kritere uygun TYT denemesi bulunamadı.")

    with grafik_tab2:
        target_tur = "YDT" if current_user["hedef_alan"] == "Dil" else "AYT"
        with get_connection() as conn:
            query = "SELECT deneme_adi, MAX(net_bilgisi) as net_bilgisi FROM deneme_konu_yanlislari WHERE ogrenci_id = ? AND deneme_turu = ?"
            params = [current_user["id"], target_tur]
            if kat_filter != "Tümü":
                query += " AND deneme_kategorisi = ?"
                params.append(kat_filter)
            query += " GROUP BY deneme_adi ORDER BY id ASC"
            df_ayt_genel = pd.read_sql_query(query, conn, params=params)

        if not df_ayt_genel.empty:
            st.line_chart(df_ayt_genel.set_index("deneme_adi")["net_bilgisi"])
        else:
            st.info(f"Seçili kritere uygun {target_tur} denemesi bulunamadı.")

    with grafik_tab3:
        with get_connection() as conn:
            df_nedenler = pd.read_sql_query(
                "SELECT yanlis_nedeni, SUM(yanlis_adedi) as toplam_yanlis FROM"
                " deneme_konu_yanlislari WHERE ogrenci_id = ? GROUP BY"
                " yanlis_nedeni",
                conn,
                params=(current_user["id"],),
            )
        if not df_nedenler.empty:
            st.bar_chart(df_nedenler.set_index("yanlis_nedeni")["toplam_yanlis"])
        else:
            st.info("Henüz hata verisi bulunmuyor.")

# ==============================================================================
# TAB 4: AKILLI ALARMLAR VE MONETIZATION CALL TO ACTION (CTA)
# ==============================================================================
with tab4:
    st.header("🚨 Konu Uyarıları ve Risk Listesi")
    col_al1, col_al2 = st.columns(2)
    with col_al1:
        st.subheader("⚠️ Öncelikli Yanlış Uyarıları")
        if (
            not alarmlar_db["siyah"]
            and not alarmlar_db["kirmizi"]
            and not alarmlar_db["mor"]
        ):
            st.success("Tebrikler! Öncelikli bir uyarınız bulunmuyor.")
        else:
            for idx, a in enumerate(alarmlar_db["siyah"]):
                st.markdown(
                    f'<div class="alarm-card-black"><b>⬛ [KRİTİK İVMELENEN YANLIŞ]</b> {a["ders"]} ➔ {a["konu"]}<br>'
                    f'• {a["detay"]}<br><br>'
                    f'<b>👉 {a["aksiyon"]}</b></div>',
                    unsafe_allow_html=True,
                )
                col_btn_a, col_btn_b = st.columns(2)
                with col_btn_a:
                    if st.button("🛒 Özel Ders İste", key=f"btn_cta_siyah_{idx}"):
                        simdi_str = get_tr_now().strftime("%Y-%m-%d %H:%M:%S")
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO pazaryeri_talepler (ogrenci_id, ders, konu, alarm_turu, talep_tarihi) VALUES (?, ?, ?, 'Siyah Alarm', ?)",
                                (current_user["id"], a["ders"], a["konu"], simdi_str),
                            )
                            conn.commit()
                        set_flash_message("success", "Özel ders talebiniz koçunuza iletildi!")
                        st.rerun()
                with col_btn_b:
                    if st.button("✅ Eksik Kapatıldı", key=f"siyah_clr_{idx}"):
                        resolve_alarm(a["id_list"])
                        set_flash_message("success", "Uyarı kaldırıldı.")
                        st.rerun()

            for idx, a in enumerate(alarmlar_db["kirmizi"]):
                st.markdown(
                    f'<div class="alarm-card-danger"><b>🔴 [BİLİNEN KONUDA YANLIŞ]</b> {a["ders"]} ➔ {a["konu"]}<br>'
                    f'• {a["detay"]}<br><br>'
                    f'<b>👉 {a["aksiyon"]}</b></div>',
                    unsafe_allow_html=True,
                )
                col_btn_a, col_btn_b = st.columns(2)
                with col_btn_a:
                    if st.button("🛒 Özel Ders İste", key=f"btn_cta_kirmizi_{idx}"):
                        simdi_str = get_tr_now().strftime("%Y-%m-%d %H:%M:%S")
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO pazaryeri_talepler (ogrenci_id, ders, konu, alarm_turu, talep_tarihi) VALUES (?, ?, ?, 'Kırmızı Alarm', ?)",
                                (current_user["id"], a["ders"], a["konu"], simdi_str),
                            )
                            conn.commit()
                        set_flash_message("success", "Özel ders talebiniz koçunuza iletildi!")
                        st.rerun()
                with col_btn_b:
                    if st.button("✅ Tekrar Edildi", key=f"kirmizi_clr_{idx}"):
                        resolve_alarm(a["id_list"])
                        set_flash_message("success", "Uyarı kaldırıldı.")
                        st.rerun()

            for idx, a in enumerate(alarmlar_db["mor"]):
                st.markdown(
                    f'<div class="alarm-card-purple"><b>🟣 [3 DENEMEDİR TEKRAR EDEN HATA]</b> {a["ders"]} ➔ {a["konu"]}<br>'
                    f'• {a["detay"]}<br><br>'
                    f'<b>👉 {a["aksiyon"]}</b></div>',
                    unsafe_allow_html=True,
                )
                col_btn_a, col_btn_b = st.columns(2)
                with col_btn_a:
                    if st.button("🛒 Özel Ders İste", key=f"btn_cta_mor_{idx}"):
                        simdi_str = get_tr_now().strftime("%Y-%m-%d %H:%M:%S")
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO pazaryeri_talepler (ogrenci_id, ders, konu, alarm_turu, talep_tarihi) VALUES (?, ?, ?, 'Mor Alarm', ?)",
                                (current_user["id"], a["ders"], a["konu"], simdi_str),
                            )
                            conn.commit()
                        set_flash_message("success", "Özel ders talebiniz koçunuza iletildi!")
                        st.rerun()
                with col_btn_b:
                    if st.button("✅ Çözüldü", key=f"mor_clr_{idx}"):
                        resolve_alarm(a["id_list"])
                        set_flash_message("success", "Uyarı kaldırıldı.")
                        st.rerun()

    with col_al2:
        st.subheader("📙 Temel Eksik ve Takvim Uyarıları")
        if not alarmlar_db["turuncu"] and not alarmlar_db["mavi"]:
            st.success("Müfredat akışınızda bir aksama bulunmuyor.")
        else:
            for a in alarmlar_db["turuncu"]:
                st.markdown(
                    '<div class="alarm-card-warning"><h4>📙 [ÖN KOŞUL KİLİDİ]'
                    f" {a['konu']}</h4><p><b>Detay:</b>"
                    f" {a['detay']}</p><p>👉 <b>{a['aksiyon']}</b></p></div>",
                    unsafe_allow_html=True,
                )
            for a in alarmlar_db["mavi"]:
                st.markdown(
                    '<div class="alarm-card-info"><h4>🔵 [TAKVİM GECİKMESİ]'
                    f" {a['konu']}</h4><p><b>Detay:</b>"
                    f" {a['detay']}</p><p>👉 <b>{a['aksiyon']}</b></p></div>",
                    unsafe_allow_html=True,
                )

# ==============================================================================
# TAB 5: HAFTALIK ÇALIŞMA PROGRAMI (ÖN KOŞUL KİLİTLİ ALGORİTMA & MİKRO SÜRE HESABI)
# ==============================================================================
with tab5:
    st.header("📅 Haftalık Çalışma Programı Motoru (Ultra-Think)")
    col_p1, col_p2 = st.columns([1, 1])

    with col_p1:
        st.subheader("⚙️ Program Oluşturma Ayarları")
        gunluk_saat = st.slider("Günlük Çalışma Süresi (Saat):", 2, 12, 6)

        toplam_gunluk_dakika = gunluk_saat * 60
        maks_soru_kapasitesi = int(toplam_gunluk_dakika / 1.5)

        if gunluk_saat <= 4:
            ana_gorev_blok_sayisi = 2
        elif 5 <= gunluk_saat <= 7:
            ana_gorev_blok_sayisi = 4
        else:
            ana_gorev_blok_sayisi = 6

        günlük_paragraf_hedef = min(30, 10 + (gunluk_saat * 2))
        kalan_soru_kapasitesi = max(
            20, maks_soru_kapasitesi - günlük_paragraf_hedef
        )
        blok_basi_soru_bütcesi = int(
            kalan_soru_kapasitesi / ana_gorev_blok_sayisi
        )

        st.info(
            f"📊 Günlük **{gunluk_saat} Saat** ({toplam_gunluk_dakika} dk) çalışma planı ➔"
            f" **{ana_gorev_blok_sayisi} Ana Çalışma Bloğu** ve ön koşul kilitli sıralama ile oluşturulacaktır."
        )

        if st.button("🚀 Akıllı Haftalık Programımı Oluştur", type="primary"):
            hiz_gecmisi_kaydet(current_user["id"])
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM calisma_programi_gorevler WHERE ogrenci_id ="
                    " ?",
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

                backlog_pekistirme = []
                backlog_ezber = []

                # 1. Yanlışlar ve Alarmlardan Gelen Konular
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
                        p_score = (kredi * 0.8) + (alarm_skor * 0.2)
                        p_tip = get_konu_pedagoji_turu(
                            item["ders"], item["konu"]
                        )
                        obj = {
                            "p_score": p_score,
                            "ders": item["ders"],
                            "makro": "Deneme Tekrarı",
                            "mikro": item["konu"],
                            "neden": item.get("neden", "Deneme Eksiği"),
                            "pedagoji": p_tip,
                        }
                        if p_tip == "Pekiştirme":
                            backlog_pekistirme.append(obj)
                        else:
                            backlog_ezber.append(obj)

                # 2. Müfredatta Eksik Olan Konular
                df_bilinen_tab4 = pd.read_sql_query(
                    "SELECT ders, mikro_konu FROM konu_durumlari_detay WHERE"
                    " ogrenci_id = ? AND durum = 'Biliyorum'",
                    conn,
                    params=(current_user["id"],),
                )
                bilinen_mikro_set = set(df_bilinen_tab4["mikro_konu"].tolist())

                for d_ad, m_dict in aktif_mufredat_hiyerarsisi.items():
                    if isinstance(m_dict, dict):
                        for mak_ad, mik_l in m_dict.items():
                            if isinstance(mik_l, list):
                                for mik_ad in mik_l:
                                    if mik_ad not in bilinen_mikro_set:
                                        kredi = SORU_AGIRLIKLARI.get(
                                            mak_ad, 8.0
                                        )
                                        p_score = kredi
                                        p_tip = get_konu_pedagoji_turu(
                                            d_ad, mik_ad
                                        )
                                        obj = {
                                            "p_score": p_score,
                                            "ders": d_ad,
                                            "makro": mak_ad,
                                            "mikro": mik_ad,
                                            "neden": "Sıradaki Konu",
                                            "pedagoji": p_tip,
                                        }
                                        if p_tip == "Pekiştirme":
                                            backlog_pekistirme.append(obj)
                                        else:
                                            backlog_ezber.append(obj)

                # ÖN KOŞUL KİLİDİ (DEPENDENCY TREE) FİLTRESİ
                def on_kosul_uygun_mu(item):
                    mik_konu = item["mikro"]
                    if mik_konu in ON_KOSULLAR:
                        gerekenler = ON_KOSULLAR[mik_konu]["on_kosul"]
                        for g in gerekenler:
                            if g not in bilinen_mikro_set:
                                return False
                    return True

                filtered_pekistirme = [x for x in backlog_pekistirme if on_kosul_uygun_mu(x)]
                filtered_ezber = [x for x in backlog_ezber if on_kosul_uygun_mu(x)]

                filtered_pekistirme.sort(key=lambda x: x["p_score"], reverse=True)
                filtered_ezber.sort(key=lambda x: x["p_score"], reverse=True)

                yari_blok = max(1, ana_gorev_blok_sayisi // 2)
                
                yeni_motor_calisti = False
                try:
                    yeni_motor_calisti = akilli_program_motoru_v2_uygula(
                        cursor,
                        current_user["id"],
                        aktif_mufredat_hiyerarsisi,
                        alarmlar_db,
                        ana_gorev_blok_sayisi,
                        blok_basi_soru_bütcesi,
                        günlük_paragraf_hedef,
                    )
                except Exception as motor_hata_v2:
                    yeni_motor_calisti = False
                    cursor.execute(
                        "DELETE FROM calisma_programi_gorevler WHERE ogrenci_id = ?",
                        (current_user["id"],),
                    )
                    try:
                        yeni_motor_calisti = akilli_program_motoru_uygula(
                            cursor,
                            current_user["id"],
                            aktif_mufredat_hiyerarsisi,
                            alarmlar_db,
                            ana_gorev_blok_sayisi,
                            blok_basi_soru_bütcesi,
                            günlük_paragraf_hedef,
                        )
                        set_flash_message(
                            "warning",
                            f"Alt başlık motoru çalışmadı, önceki motor kullanıldı: {motor_hata_v2}",
                        )
                    except Exception as motor_hata:
                        yeni_motor_calisti = False
                        cursor.execute(
                            "DELETE FROM calisma_programi_gorevler WHERE ogrenci_id = ?",
                            (current_user["id"],),
                        )
                        set_flash_message(
                            "warning",
                            f"Yeni program motorları çalışmadı, eski motor kullanıldı: {motor_hata}",
                        )
                    for idx, g in enumerate(gunler):
                        tarih_dt = get_tr_now() + timedelta(days=idx)
                        tarih_str = tarih_dt.strftime("%Y-%m-%d")

                        # Paragraf Rutini
                        cursor.execute(
                            """INSERT INTO calisma_programi_gorevler 
                               (ogrenci_id, gun, ders, makro_konu, mikro_konu, gorev_tanimi, hedef_soru, pedagoji_turu, durum, tarih) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                            (
                                current_user["id"],
                                g,
                                "TYT Türkçe",
                                "Paragraf",
                                "Günlük Paragraf",
                                f"📖 PARAGRAF: {günlük_paragraf_hedef} Paragraf Sorusu Çöz (~30 dk)",
                                günlük_paragraf_hedef,
                                "Ezber",
                                tarih_str,
                            ),
                        )

                        # Uygulama & Soru Çözüm Blokları (MİKRO SÜRE FORMÜLÜ)
                        for _ in range(yari_blok):
                            curr_item = (
                                filtered_pekistirme.pop(0)
                                if filtered_pekistirme
                                else {
                                    "ders": "TYT Matematik",
                                    "makro": "Karma Soru",
                                    "mikro": "Soru Çözümü & Prova",
                                    "neden": "Genel Tekrar",
                                }
                            )
                            slot_soru = blok_basi_soru_bütcesi
                            konu_anlatim_dk = KONU_SURELERI_DK.get(curr_item["mikro"], 60)
                            soru_cozum_dk = int(slot_soru * 1.5)
                            toplam_gorev_suresi = konu_anlatim_dk + soru_cozum_dk

                            tanim = (
                                f"📌 UYGULAMA & SORU: Konu/Tekrar ({konu_anlatim_dk} dk) + {slot_soru} Soru ({soru_cozum_dk} dk) "
                                f"[Toplam ~{toplam_gorev_suresi} dk | Odak: {curr_item['neden']}]"
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
                                    "Pekiştirme",
                                    tarih_str,
                                ),
                            )

                        # Kavram & Özet Blokları (3 GÜN SONRAKİ ARALIKLI TEKRAR EKLEME)
                        for _ in range(yari_blok):
                            curr_item = (
                                filtered_ezber.pop(0)
                                if filtered_ezber
                                else {
                                    "ders": "TYT Biyoloji",
                                    "makro": "Kavram Tekrarı",
                                    "mikro": "Özet Not Çalışması",
                                    "neden": "Genel Tekrar",
                                }
                            )
                            slot_soru = blok_basi_soru_bütcesi
                            konu_anlatim_dk = KONU_SURELERI_DK.get(curr_item["mikro"], 50)
                            soru_cozum_dk = int(slot_soru * 1.5)
                            toplam_gorev_suresi = konu_anlatim_dk + soru_cozum_dk

                            tanim = (
                                f"📝 KAVRAM & ÖZET: Konu Çalış ({konu_anlatim_dk} dk) + {slot_soru} Soru ({soru_cozum_dk} dk) "
                                f"[Toplam ~{toplam_gorev_suresi} dk | Odak: {curr_item['neden']}]"
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
                                    "Ezber",
                                    tarih_str,
                                ),
                            )

                            # 3 Günlük Aralıklı Tekrar (Spaced Repetition & datetime +3 Gün)
                            geceler_3_gun = (tarih_dt + timedelta(days=3)).strftime("%Y-%m-%d")
                            geceler_gun_ad = gunler[(idx + 3) % 7]
                            tekrar_tanim = (
                                f"🔄 3 GÜNLÜK ARALIKLI TEKRAR: '{curr_item['mikro']}' Notlarını 20 dk Gözden Geçir."
                            )
                            cursor.execute(
                                """INSERT INTO calisma_programi_gorevler 
                                   (ogrenci_id, gun, ders, makro_konu, mikro_konu, gorev_tanimi, hedef_soru, pedagoji_turu, durum, tarih) 
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                                (
                                    current_user["id"],
                                    geceler_gun_ad,
                                    curr_item["ders"],
                                    curr_item["makro"],
                                    curr_item["mikro"],
                                    tekrar_tanim,
                                    0,
                                    "Tekrar",
                                    geceler_3_gun,
                                ),
                            )

                conn.commit()
            log_islem(
                current_user["id"],
                "CREATE_PROGRAM",
                "Haftalık Çalışma Programı Oluşturuldu (Spaced Repetition & Dependency Tree).",
            )
            set_flash_message(
                "success", "🎉 Ön koşul kilitli ve aralıklı tekrarlı haftalık programınız oluşturuldu!"
            )
            st.rerun()

    with col_p2:
        st.subheader("🏆 Tahmini ÖSYM Sıralama Simülatörü")

        with st.expander("📊 Sınav Netlerinizi Giriniz", expanded=True):
            col_sim1, col_sim2 = st.columns(2)
            with col_sim1:
                st.markdown("**TYT Netleriniz:**")
                s_t_tur = st.number_input(
                    "TYT Türkçe (40):", 0.0, 40.0, 25.0, 0.5
                )
                s_t_mat = st.number_input(
                    "TYT Matematik (40):", 0.0, 40.0, 20.0, 0.5
                )
                s_t_sos = st.number_input(
                    "TYT Sosyal (20):", 0.0, 20.0, 12.0, 0.5
                )
                s_t_fen = st.number_input("TYT Fen (20):", 0.0, 20.0, 10.0, 0.5)

            sim_netler = {
                "tyt_turkce": s_t_tur,
                "tyt_mat": s_t_mat,
                "tyt_sosyal": s_t_sos,
                "tyt_fen": s_t_fen,
            }
            target_alan = current_user["hedef_alan"]

            with col_sim2:
                st.markdown(f"**{target_alan} AYT/YDT Netleriniz:**")
                if target_alan == "Sayısal":
                    sim_netler["ayt_mat"] = st.number_input(
                        "AYT Matematik (40):", 0.0, 40.0, 22.0, 0.5
                    )
                    sim_netler["ayt_fizik"] = st.number_input(
                        "AYT Fizik (14):", 0.0, 14.0, 7.0, 0.5
                    )
                    sim_netler["ayt_kimya"] = st.number_input(
                        "AYT Kimya (13):", 0.0, 13.0, 6.0, 0.5
                    )
                    sim_netler["ayt_biyoloji"] = st.number_input(
                        "AYT Biyoloji (13):", 0.0, 13.0, 6.0, 0.5
                    )
                elif target_alan == "Eşit Ağırlık":
                    sim_netler["ayt_mat"] = st.number_input(
                        "AYT Matematik (40):", 0.0, 40.0, 20.0, 0.5
                    )
                    sim_netler["ayt_edebiyat"] = st.number_input(
                        "AYT Edebiyat (24):", 0.0, 24.0, 15.0, 0.5
                    )
                    sim_netler["ayt_tarih1"] = st.number_input(
                        "AYT Tarih-1 (10):", 0.0, 10.0, 6.0, 0.5
                    )
                    sim_netler["ayt_cog1"] = st.number_input(
                        "AYT Coğrafya-1 (6):", 0.0, 6.0, 4.0, 0.5
                    )
                elif target_alan == "Sözel":
                    sim_netler["ayt_edebiyat"] = st.number_input(
                        "AYT Edebiyat (24):", 0.0, 24.0, 18.0, 0.5
                    )
                    sim_netler["ayt_tarih1"] = st.number_input(
                        "AYT Tarih-1 (10):", 0.0, 10.0, 7.0, 0.5
                    )
                    sim_netler["ayt_cog1"] = st.number_input(
                        "AYT Coğrafya-1 (6):", 0.0, 6.0, 5.0, 0.5
                    )
                    sim_netler["ayt_tarih2"] = st.number_input(
                        "AYT Tarih-2 (11):", 0.0, 11.0, 7.0, 0.5
                    )
                    sim_netler["ayt_cog2"] = st.number_input(
                        "AYT Coğrafya-2 (11):", 0.0, 11.0, 8.0, 0.5
                    )
                    sim_netler["ayt_felsefe"] = st.number_input(
                        "AYT Felsefe Gr. (12):", 0.0, 12.0, 8.0, 0.5
                    )
                    sim_netler["ayt_din"] = st.number_input(
                        "AYT Din Kültürü (6):", 0.0, 6.0, 4.0, 0.5
                    )
                elif target_alan == "Dil":
                    sim_netler["ydt_ing"] = st.number_input(
                        "YDT İngilizce (80):", 0.0, 80.0, 60.0, 1.0
                    )

            hesap_sonuc = hesapla_yks_puan_ve_siralama(
                sim_netler,
                float(current_user.get("diploma_notu", 85.0)),
                current_user["hedef_alan"],
            )

        st.markdown(
            '<div class="sim-card"><h4>🎯 Tahmini Yerleştirme ve Sıralama</h4></div>',
            unsafe_allow_html=True,
        )
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.metric("📊 TYT Yerleştirme Puanı", f"{hesap_sonuc['y_tyt']}")
            yerlesme_puan = (
                hesap_sonuc["y_say"]
                if target_alan == "Sayısal"
                else (
                    hesap_sonuc["y_ea"]
                    if target_alan == "Eşit Ağırlık"
                    else (
                        hesap_sonuc["y_soz"]
                        if target_alan == "Sözel"
                        else hesap_sonuc["y_dil"]
                    )
                )
            )
            st.metric(f"🎓 Yerleştirme ({target_alan})", f"{yerlesme_puan}")
            st.caption(f"➕ OBP Katkısı (+{hesap_sonuc['obp_katkisi']} Puan)")
        with col_res2:
            st.metric(
                "🏆 Tahmini Türkiye Sıralaması",
                f"~{hesap_sonuc['tahmini_siralama']:,} / {target_alan}",
            )

    st.markdown("---")
    st.subheader("📋 7 Günlük Genel Çalışma Çizelgesi")
    with get_connection() as conn:
        df_program_full = pd.read_sql_query(
            "SELECT id, gun, ders, makro_konu, mikro_konu, gorev_tanimi,"
            " hedef_soru, pedagoji_turu, durum FROM calisma_programi_gorevler"
            " WHERE ogrenci_id = ?",
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
                                '<div class="alarm-card-info">🔄 <b>[3 GÜNLÜK'
                                f" ARALIKLI TEKRAR GÖREVİ]</b> {row['ders']} -"
                                f" {row['mikro_konu']}<br>•"
                                f" {row['gorev_tanimi']}</div>",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                '<div class="sim-card">📌 <b>'
                                f" {row['ders']} - {row['mikro_konu']}</b><br>•"
                                f" {row['gorev_tanimi']}</div>",
                                unsafe_allow_html=True,
                            )

                        col_g1, col_g2 = st.columns([3, 1])
                        with col_g1:
                            st.write(
                                f"📌 **{row['makro_konu']}** ➔"
                                f" *{row['mikro_konu']}*"
                            )
                        with col_g2:
                            is_t = bool(row["durum"])
                            chk_g = st.checkbox(
                                "Tamamlandı",
                                value=is_t,
                                key=f"prog_chk_{row['id']}",
                            )
                            if chk_g != is_t:
                                with get_connection() as conn:
                                    soru_ilerleme_isle(row["id"], chk_g)
                                    gorev_alt_konu_isle(row["id"], chk_g)
                                    cursor = conn.cursor()
                                    cursor.execute(
                                        "UPDATE calisma_programi_gorevler SET"
                                        " durum = ? WHERE id = ?",
                                        (1 if chk_g else 0, row["id"]),
                                    )
                                    conn.commit()
                                st.rerun()
                        st.markdown("---")
                else:
                    st.info("Bu gün için planlanmış bir çalışma görevi bulunmuyor.")

# ==============================================================================
# TAB 6: ÖZEL DERS & RAPORLAR
# ==============================================================================
with tab6:
    st.header("🤝 Özel Ders Talepleri & Çalışma Raporları")
    
    rep_tab1, rep_tab2 = st.tabs([
        "🛒 Özel Ders Taleplerim",
        "📊 Detaylı Performans & İletişim Logları",
    ])
    
    with rep_tab1:
        st.subheader("📌 Mevcut Özel Ders Talepleri")
        with get_connection() as conn:
            df_taleplerim = pd.read_sql_query(
                "SELECT id, ders, konu, alarm_turu, talep_tarihi, durum FROM pazaryeri_talepler WHERE ogrenci_id = ? ORDER BY id DESC",
                conn,
                params=(current_user["id"],),
            )
        
        if not df_taleplerim.empty:
            st.dataframe(df_taleplerim, width="stretch")
        else:
            st.info("Henüz oluşturulmuş bir özel ders talebiniz bulunmuyor.")
            
        st.markdown("---")
        st.subheader("➕ Yeni Özel Ders / Birebir Seans Talebi Oluştur")
        with st.form("yeni_ozel_ders_talep_formu"):
            talep_ders = st.selectbox("Ders Seçiniz:", list(aktif_mufredat_hiyerarsisi.keys()))
            
            secili_ders_dict = aktif_mufredat_hiyerarsisi.get(talep_ders, {})
            konu_listesi = []
            if isinstance(secili_ders_dict, dict):
                for k, v in secili_ders_dict.items():
                    if isinstance(v, list):
                        konu_listesi.extend(v)
                    else:
                        konu_listesi.append(k)
            if not konu_listesi:
                konu_listesi = ["Genel Soru Çözümü / Birebir Koçluk"]
                
            talep_konu = st.selectbox("Destek Almak İstediğiniz Konu:", konu_listesi)
            talep_notu = st.text_area("Koçunuza İletmek İstediğiniz Not (Opsiyonel):", placeholder="Örn: Bu konuda çıkmış soruları birlikte çözmek istiyorum.")
            
            if st.form_submit_button("📩 Özel Ders Talebini Gönder", type="primary"):
                simdi_str = get_tr_now().strftime("%Y-%m-%d %H:%M:%S")
                konu_full = f"{talep_konu} ({talep_notu})" if talep_notu.strip() else talep_konu
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO pazaryeri_talepler (ogrenci_id, ders, konu, alarm_turu, talep_tarihi, durum) VALUES (?, ?, ?, 'Birebir Talep', ?, 'Talep Alındı')",
                        (current_user["id"], talep_ders, konu_full, simdi_str),
                    )
                    conn.commit()
                log_islem(current_user["id"], "PRIVATE_LESSON_REQUEST", f"{talep_ders} - {talep_konu}")
                set_flash_message("success", "🎉 Özel ders talebiniz koçunuza iletildi!")
                st.rerun()

    with rep_tab2:
        st.subheader("📜 Sistem İletişim ve Aktivite Logları")
        with get_connection() as conn:
            df_loglar = pd.read_sql_query(
                "SELECT islem, detay, tarih FROM sistem_loglari WHERE ogrenci_id = ? ORDER BY id DESC LIMIT 50",
                conn,
                params=(current_user["id"],),
            )
        if not df_loglar.empty:
            st.dataframe(df_loglar, width="stretch")
        else:
            st.info("Henüz sistem aktivite kaydı oluşmadı.")