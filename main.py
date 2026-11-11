import hashlib
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
import pandas as pd
import streamlit as st

from services import study_sessions
from services import programs as program_service
from services import task_steps
from services import planner
from services import spaced_repetition
from services import wrong_questions
from services import gorev_kaynaklari
from services import weekly_report
from services import osym_verisi
from services import ranking_engine

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
    /* FAZ 5B: mobil görünüm - kartlar ve checklist dar ekranda taşmaz */
    .focus-task-card, .sim-card, .alarm-card-info, .alarm-card-warning {
        box-sizing: border-box;
        max-width: 100%;
        overflow-wrap: break-word;
    }
    @media (max-width: 640px) {
        .focus-task-card {
            padding: 12px;
            border-radius: 10px;
        }
        .focus-task-card h4 {
            font-size: 1rem;
            line-height: 1.35;
        }
        .focus-task-card p {
            font-size: 0.92rem;
        }
        .focus-task-card span {
            display: inline-block;
            margin-top: 6px;
        }
        .block-container {
            padding-left: 0.7rem;
            padding-right: 0.7rem;
        }
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


# ==============================================================================
# FAZ 2: DENEME VERİ MODELİ (BAŞLIK TABLOSU + YANLIŞ DETAYLARI) VE MİGRASYON
# ==============================================================================
DENEME_KATEGORI_GENEL = "Genel Deneme"
DENEME_KATEGORI_BRANS = "Branş Denemesi"
DENEME_KATEGORILERI = [DENEME_KATEGORI_GENEL, DENEME_KATEGORI_BRANS]
DENEME_TURLERI = ["TYT", "AYT", "YDT"]
DENEME_KAYNAK_WIZARD = "wizard"
DENEME_KAYNAK_MIGRASYON = "migrasyon"


def kategori_normalize(deger):
    """'Genel' / 'Genel Deneme' / 'Branş Denemesi' -> kanonik kategori adı."""
    metin = str(deger or "").strip()
    if metin in (DENEME_KATEGORI_BRANS, "Branş", "Brans Denemesi", "Brans"):
        return DENEME_KATEGORI_BRANS
    if metin in (DENEME_KATEGORI_GENEL, "Genel"):
        return DENEME_KATEGORI_GENEL
    return None


def tur_normalize(deger):
    """Sınav türünü TYT / AYT / YDT olarak döndürür (geçersizse None)."""
    metin = str(deger or "").strip().upper()
    return metin if metin in DENEME_TURLERI else None


# Maarif modeli (9/10. sınıf) müfredatında TYT dersleri öneksiz adlandırılır.
TYT_ONEKSIZ_DERSLER = ("Matematik ve Veri", "Gramer ve Kelime", "Soru Tipleri")


def brans_tur_uyumlu(brans_dersi, deneme_turu):
    """Branş dersinin sınav türüyle uyumlu olup olmadığını söyler."""
    brans = str(brans_dersi or "").strip()
    tur = str(deneme_turu or "").strip().upper()
    if not brans or tur not in DENEME_TURLERI:
        return False
    if brans.upper().startswith(tur):
        return True
    if tur == "TYT" and brans in TYT_ONEKSIZ_DERSLER:
        return True
    if tur == "YDT" and ("YDT" in brans or "İngilizce" in brans):
        return True
    return False


def tarih_gunu(deger):
    """'2026-11-10 10:39:17' veya date/datetime -> 'YYYY-MM-DD'. Geçersizse None."""
    if deger is None:
        return None
    if hasattr(deger, "strftime"):
        try:
            return deger.strftime("%Y-%m-%d")
        except Exception:
            return None
    metin = str(deger).strip()
    if len(metin) >= 10 and re.match(r"^\d{4}-\d{2}-\d{2}", metin):
        return metin[:10]
    for kalip in ("%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(metin, kalip).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ==============================================================================
# FAZ 3: DERS BAZLI DENEME SONUÇLARI (GENEL DENEMENİN ALT KIRILIMI)
# ==============================================================================
DERS_SONUC_MIN_SORU = 1
DERS_SONUC_MAKS_SORU = 200

# TYT genel denemesi: resmî test grupları ve varsayılan soru sayıları.
TYT_GENEL_DERS_SORU_SAYILARI = [
    ("TYT Türkçe", 40),
    ("TYT Matematik", 40),
    ("TYT Sosyal Bilimler", 20),
    ("TYT Fen Bilimleri", 20),
]

# AYT genel denemesi: öğrencinin alanına göre test grupları.
# Soru sayıları varsayılandır; giriş ekranında ders bazında değiştirilebilir.
# NOT: ÖSYM düzeninde AYT Geometri soruları Matematik Testinin İÇİNDEDİR;
# matematik testi toplam 40 sorudur. Bu yüzden genel denemede ayrı bir
# "AYT Geometri" satırı yoktur (çift sayım olmasın diye). Geometri ayrı takip
# edilmek istenirse branş denemesi olarak girilir; müfredattaki AYT Geometri
# konu takibi ve "AYT Geometri" branş dersi seçeneği bundan etkilenmez.
AYT_GENEL_DERS_SORU_SAYILARI = {
    "Sayısal": [
        ("AYT Matematik", 40),
        ("AYT Fizik", 14),
        ("AYT Kimya", 13),
        ("AYT Biyoloji", 13),
    ],
    "Eşit Ağırlık": [
        ("AYT Matematik", 40),
        ("AYT Edebiyat", 24),
        ("AYT Tarih-1", 10),
        ("AYT Coğrafya-1", 6),
    ],
    "Sözel": [
        ("AYT Edebiyat", 24),
        ("AYT Tarih-1", 10),
        ("AYT Coğrafya-1", 6),
        ("AYT Tarih-2", 11),
        ("AYT Coğrafya-2", 11),
        ("AYT Felsefe Grubu", 12),
        ("AYT Din Kültürü", 6),
    ],
    "Dil": [("YDT İngilizce", 80)],
}

_TR_HARF_ESLEME = str.maketrans("ışğüöçâİŞĞÜÖÇ", "isguocaISGUOC")


def alan_normalize(alan):
    """'sayısal' / 'EA' / 'SÖZ' gibi yazımları kanonik alan adına çevirir."""
    metin = str(alan or "").strip().translate(_TR_HARF_ESLEME).lower()
    metin = " ".join(metin.split())
    if metin in ("sayisal", "say", "mf"):
        return "Sayısal"
    if metin in ("esit agirlik", "ea", "esit", "tm"):
        return "Eşit Ağırlık"
    if metin in ("sozel", "soz", "ts"):
        return "Sözel"
    if metin in ("dil", "ydt", "yabanci dil"):
        return "Dil"
    return None


def genel_ders_secenekleri(deneme_turu, hedef_alan=None):
    """Genel denemede ders bazlı sonuç girilebilecek dersler: [(ders, soru)].

    TYT -> Türkçe / Matematik / Sosyal Bilimler / Fen Bilimleri
    AYT -> öğrencinin alanına göre test grupları
    YDT -> YDT İngilizce
    """
    tur = tur_normalize(deneme_turu)
    if tur == "TYT":
        return [(d, int(s)) for d, s in TYT_GENEL_DERS_SORU_SAYILARI]
    if tur == "AYT":
        alan = alan_normalize(hedef_alan)
        return [
            (d, int(s)) for d, s in AYT_GENEL_DERS_SORU_SAYILARI.get(alan, [])
        ]
    if tur == "YDT":
        return [(d, int(s)) for d, s in AYT_GENEL_DERS_SORU_SAYILARI["Dil"]]
    return []


def ders_net_hesapla(dogru, yanlis):
    """Ders neti: Net = Doğru - (Yanlış / 4), iki ondalık."""
    try:
        d = float(dogru or 0)
        y = float(yanlis or 0)
    except (TypeError, ValueError) as hata:
        raise ValueError(
            "Doğru ve yanlış sayıları sayısal olmalıdır."
        ) from hata
    if d < 0 or y < 0:
        raise ValueError("Doğru ve yanlış sayıları negatif olamaz.")
    return round(d - (y / 4.0), 2)


def ders_sonucu_dogrula(
    ders, dogru=0, yanlis=0, bos=0, soru_sayisi=None, sure_dk=None
):
    """Tek bir ders sonucunu doğrular ve normalize eder.

    Kurallar:
    - Ders adı boş olamaz.
    - Doğru / yanlış / boş negatif veya ondalıklı olamaz.
    - Doğru + yanlış + boş, dersin soru sayısını aşamaz.
    - Net her zaman Doğru - (Yanlış / 4) olarak YENİDEN hesaplanır.

    Dönüş: {"ders", "soru_sayisi", "dogru", "yanlis", "bos", "net",
            "sure_dk"}. Hatalı girişte ValueError.
    """
    ad = str(ders or "").strip()
    if not ad:
        raise ValueError("Ders adı boş olamaz.")

    def _tam(deger, etiket, varsayilan=0):
        if deger is None or (isinstance(deger, str) and not deger.strip()):
            return varsayilan
        try:
            sayi = float(deger)
        except (TypeError, ValueError) as hata:
            raise ValueError(
                f"{ad}: {etiket} sayısal olmalıdır."
            ) from hata
        if sayi != int(sayi):
            raise ValueError(f"{ad}: {etiket} tam sayı olmalıdır.")
        sayi = int(sayi)
        if sayi < 0:
            raise ValueError(f"{ad}: {etiket} negatif olamaz.")
        return sayi

    d = _tam(dogru, "doğru")
    y = _tam(yanlis, "yanlış")
    b = _tam(bos, "boş")
    isaretli = d + y + b
    if soru_sayisi is None or (
        isinstance(soru_sayisi, str) and not soru_sayisi.strip()
    ):
        ss = isaretli
    else:
        ss = _tam(soru_sayisi, "soru sayısı")
        if ss < DERS_SONUC_MIN_SORU:
            raise ValueError(
                f"{ad}: soru sayısı en az {DERS_SONUC_MIN_SORU} olmalıdır."
            )
        if ss > DERS_SONUC_MAKS_SORU:
            raise ValueError(
                f"{ad}: soru sayısı en fazla {DERS_SONUC_MAKS_SORU} olabilir."
            )
        if isaretli > ss:
            raise ValueError(
                f"{ad}: doğru+yanlış+boş toplamı ({isaretli}) dersin soru"
                f" sayısını ({ss}) aşıyor."
            )
    sure = None if sure_dk in (None, "") else _tam(sure_dk, "süre")
    return {
        "ders": ad,
        "soru_sayisi": ss,
        "dogru": d,
        "yanlis": y,
        "bos": b,
        "net": ders_net_hesapla(d, y),
        "sure_dk": sure,
    }


def ders_sonuclari_dogrula(sonuclar, deneme_turu=None):
    """Ders sonucu listesini topluca doğrular.

    - Tamamen boş satırlar sessizce atlanır (sıfır uydurulmaz).
    - Aynı ders iki kez verilemez.
    - Ders adı sınav türüyle uyumlu olmalı (TYT denemesine AYT dersi girilemez).
    """
    tur = tur_normalize(deneme_turu)
    temiz = []
    gorulen = set()
    for ham in list(sonuclar or []):
        if not isinstance(ham, dict):
            raise ValueError("Her ders sonucu sözlük (dict) olmalıdır.")
        satir = ders_sonucu_dogrula(
            ham.get("ders"),
            ham.get("dogru", 0),
            ham.get("yanlis", 0),
            ham.get("bos", 0),
            ham.get("soru_sayisi"),
            ham.get("sure_dk"),
        )
        if satir["dogru"] + satir["yanlis"] + satir["bos"] == 0:
            continue
        if tur and not brans_tur_uyumlu(satir["ders"], tur):
            raise ValueError(
                f"'{satir['ders']}' dersi {tur} genel denemesiyle uyumlu"
                " değil."
            )
        if satir["ders"] in gorulen:
            raise ValueError(
                f"'{satir['ders']}' dersi bu denemede birden fazla kez"
                " girildi."
            )
        gorulen.add(satir["ders"])
        temiz.append(satir)
    return temiz


def ders_toplam_neti(sonuclar):
    """Ders sonuçlarının toplam neti."""
    return round(sum(float(s.get("net") or 0) for s in (sonuclar or [])), 2)


def net_ozeti(netler):
    """Net serisinin özeti; yetersiz veride uydurma yapmaz.

    - "son" / "en_yuksek": en az 1 deneme varsa dolu.
    - "son_uc_ortalama": en az 3 deneme varsa dolu.
    - "gelisim": en az 6 deneme varsa dolu (son 3 ort. - önceki 3 ort.).
    """
    degerler = []
    for n in netler or []:
        if n is None:
            continue
        try:
            degerler.append(float(n))
        except (TypeError, ValueError):
            continue
    ozet = {
        "adet": len(degerler),
        "son": None,
        "en_yuksek": None,
        "son_uc_ortalama": None,
        "onceki_uc_ortalama": None,
        "gelisim": None,
    }
    if not degerler:
        return ozet
    ozet["son"] = round(degerler[-1], 2)
    ozet["en_yuksek"] = round(max(degerler), 2)
    if len(degerler) >= 3:
        ozet["son_uc_ortalama"] = round(sum(degerler[-3:]) / 3.0, 2)
    if len(degerler) >= 6:
        ozet["onceki_uc_ortalama"] = round(sum(degerler[-6:-3]) / 3.0, 2)
        ozet["gelisim"] = round(
            ozet["son_uc_ortalama"] - ozet["onceki_uc_ortalama"], 2
        )
    return ozet


def ders_seri_listesi(df_sonuclar, deneme_turu, kategori=DENEME_KATEGORI_GENEL):
    """Bir sınav türünde ders sonucu bulunan dersleri kanonik sırada döndürür."""
    if df_sonuclar is None or len(df_sonuclar.index) == 0:
        return []
    df = df_sonuclar.copy()
    for kolon in ("deneme_turu", "deneme_kategorisi", "ders"):
        if kolon not in df.columns:
            return []
        df[kolon] = df[kolon].fillna("").astype(str)
    alt = df[
        (df["deneme_turu"] == str(deneme_turu))
        & (df["deneme_kategorisi"] == str(kategori))
    ]
    bulunan = {d.strip() for d in alt["ders"].tolist() if str(d).strip()}
    kanonik = [d for d, _ in genel_ders_secenekleri(deneme_turu)]
    return sorted(
        bulunan,
        key=lambda d: (kanonik.index(d) if d in kanonik else 999, d),
    )


def ders_net_serisi(
    df_sonuclar, deneme_turu, ders, kategori=DENEME_KATEGORI_GENEL
):
    """Tek bir dersin net serisini kronolojik olarak döndürür.

    Genel denemenin ders sonuçları ile branş denemeleri asla birleşmez:
    `kategori` varsayılan olarak "Genel Deneme"dir ve deneme başına tek
    nokta üretilir.
    """
    if df_sonuclar is None or len(df_sonuclar.index) == 0:
        return df_sonuclar
    df = df_sonuclar.copy()
    for kolon in ("ders", "deneme_turu", "deneme_kategorisi"):
        if kolon not in df.columns:
            return df.iloc[0:0]
        df[kolon] = df[kolon].fillna("").astype(str)
    if "tarih" not in df.columns:
        df["tarih"] = ""
    df["tarih"] = df["tarih"].fillna("").astype(str)
    mask = (df["ders"] == str(ders)) & (df["deneme_turu"] == str(deneme_turu))
    if kategori:
        mask &= df["deneme_kategorisi"] == str(kategori)
    seri = df[mask].copy()
    if seri.empty:
        return seri
    seri["net"] = pd.to_numeric(seri["net"], errors="coerce")
    seri["deneme_id"] = (
        pd.to_numeric(seri["deneme_id"], errors="coerce").fillna(0).astype(int)
    )
    seri = seri.dropna(subset=["net"])
    seri = seri.sort_values(["tarih", "deneme_id"], kind="stable")
    seri = seri.drop_duplicates(subset=["deneme_id"], keep="last")
    return seri.reset_index(drop=True)


def deneme_kaydet(
    conn,
    ogrenci_id,
    deneme_adi,
    deneme_kategorisi,
    deneme_turu,
    brans_dersi,
    net_bilgisi,
    tarih,
    yanlislar=None,
    dogru_adedi=None,
    yanlis_adedi=None,
    bos_adedi=None,
    sure_dk=None,
    kayit_kaynagi=DENEME_KAYNAK_WIZARD,
    ders_sonuclari=None,
):
    """Deneme başlığını, (varsa) ders sonuçlarını ve yanlış detaylarını yazar.

    - Başlık, yanlış listesi boş olsa bile mutlaka oluşturulur.
    - Genel denemede `brans_dersi` NULL'a zorlanır; branş denemesinde zorunludur.
    - FAZ 3: `ders_sonuclari` verilirse her dersin neti doğru/yanlıştan
      otomatik hesaplanır ve `deneme_ders_sonuclari`'na yazılır. Toplam net
      ders netlerinin toplamıyla uyuşmak zorundadır; `net_bilgisi=None`
      verilirse toplam net ders sonuçlarından hesaplanır.
    - Branş denemesinde tek ders satırı otomatik oluşturulur; ders detayı
      (doğru/yanlış/boş) verilmişse net bu değerlerden hesaplanır.
    - Hata olursa SAVEPOINT ile geri alınır, yarım kayıt kalmaz.

    Dönüş: oluşturulan `denemeler.id`
    """
    yanlislar = list(yanlislar or [])
    ad = str(deneme_adi or "").strip()
    if not ad:
        raise ValueError("Deneme adı boş olamaz.")

    kategori = kategori_normalize(deneme_kategorisi)
    if kategori is None:
        raise ValueError(f"Geçersiz deneme kategorisi: {deneme_kategorisi!r}")

    tur = tur_normalize(deneme_turu)
    if tur is None:
        raise ValueError(f"Geçersiz deneme türü: {deneme_turu!r}")

    brans = str(brans_dersi or "").strip() or None
    if kategori == DENEME_KATEGORI_GENEL:
        brans = None
    elif brans is None:
        raise ValueError("Branş denemesinde branş dersi zorunludur.")
    elif not brans_tur_uyumlu(brans, tur):
        raise ValueError(f"'{brans}' dersi {tur} sınav türüyle uyumlu değil.")

    gun = tarih_gunu(tarih)
    if gun is None:
        raise ValueError(f"Geçersiz deneme tarihi: {tarih!r}")

    sonuclar = ders_sonuclari_dogrula(ders_sonuclari, tur)
    if kategori == DENEME_KATEGORI_BRANS and sonuclar:
        if len(sonuclar) > 1 or sonuclar[0]["ders"] != brans:
            raise ValueError(
                "Branş denemesinde yalnızca seçilen branş dersinin sonucu"
                " kaydedilebilir."
            )

    if net_bilgisi is None:
        if not sonuclar:
            raise ValueError("Net bilgisi zorunludur.")
        net = ders_toplam_neti(sonuclar)
    else:
        try:
            net = float(net_bilgisi)
        except (TypeError, ValueError) as hata:
            raise ValueError("Net bilgisi sayısal olmalıdır.") from hata
        if sonuclar:
            ders_net = ders_toplam_neti(sonuclar)
            if abs(net - ders_net) > 0.05:
                raise ValueError(
                    f"Toplam net ({net:.2f}) ders sonuçlarının toplamıyla"
                    f" ({ders_net:.2f}) uyuşmuyor."
                )
    if net < 0:
        raise ValueError("Net bilgisi negatif olamaz.")

    if kategori == DENEME_KATEGORI_BRANS and not sonuclar:
        # FAZ 3: branş sonucu her zaman ders sonuçları tablosuna bağlanır.
        if dogru_adedi is None and yanlis_adedi is None and bos_adedi is None:
            sonuclar = [{
                "ders": brans,
                "soru_sayisi": None,
                "dogru": None,
                "yanlis": None,
                "bos": None,
                "net": net,
                "sure_dk": sure_dk,
            }]
        else:
            satir = ders_sonucu_dogrula(
                brans, dogru_adedi, yanlis_adedi, bos_adedi, None, sure_dk
            )
            net = satir["net"]  # net yalnızca doğru/yanlıştan hesaplanır
            sonuclar = [satir]

    if yanlis_adedi is None:
        yanlis_adedi = int(sum(int(y.get("yanlis_adedi") or 0) for y in yanlislar))

    simdi_s = get_tr_now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.cursor()
    cur.execute("SAVEPOINT faz2_deneme_kaydet")
    try:
        cur.execute(
            """INSERT INTO denemeler
               (ogrenci_id, tarih, deneme_adi, deneme_kategorisi, deneme_turu,
                brans_dersi, net_bilgisi, dogru_adedi, yanlis_adedi, bos_adedi,
                sure_dk, kayit_kaynagi, legacy_signature, olusturma_zamani)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)""",
            (
                ogrenci_id,
                gun,
                ad,
                kategori,
                tur,
                brans,
                net,
                dogru_adedi,
                yanlis_adedi,
                bos_adedi,
                sure_dk,
                kayit_kaynagi,
                simdi_s,
            ),
        )
        deneme_id = cur.lastrowid

        # FAZ 3: ders bazlı sonuçlar (genel deneme) veya branş ders sonucu.
        for s in sonuclar:
            cur.execute(
                """INSERT INTO deneme_ders_sonuclari
                   (deneme_id, ders, soru_sayisi, dogru, yanlis, bos, net,
                    sure_dk)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    deneme_id,
                    s["ders"],
                    s["soru_sayisi"],
                    s["dogru"],
                    s["yanlis"],
                    s["bos"],
                    s["net"],
                    s["sure_dk"],
                ),
            )

        for y in yanlislar:
            konu = str(y.get("mikro") or y.get("konu_adi") or "").strip()
            if not konu:
                continue
            cur.execute(
                """INSERT INTO deneme_konu_yanlislari
                   (ogrenci_id, deneme_kategorisi, brans_dersi, deneme_turu,
                    deneme_adi, net_bilgisi, ders, makro_konu, konu_adi,
                    yanlis_adedi, yanlis_nedeni, durum, tarih, deneme_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Aktif', ?, ?)""",
                (
                    ogrenci_id,
                    kategori,
                    brans,
                    tur,
                    ad,
                    net,
                    str(y.get("ders") or brans or "").strip(),
                    y.get("makro"),
                    konu,
                    int(y.get("yanlis_adedi") or 0),
                    y.get("nedenler") or "Konu Eksikliği",
                    gun,
                    deneme_id,
                ),
            )
        cur.execute("RELEASE faz2_deneme_kaydet")
        conn.commit()
    except Exception:
        cur.execute("ROLLBACK TO faz2_deneme_kaydet")
        cur.execute("RELEASE faz2_deneme_kaydet")
        conn.commit()
        raise
    return int(deneme_id)


def migrasyon_denemeleri(conn):
    """Eski `deneme_konu_yanlislari` kayıtlarından `denemeler` başlıkları üretir.

    Eşleştirme imzası: ogrenci_id + TRIM(deneme_adi) + tarih + kategori + tür +
    brans_dersi + net_bilgisi. Branş denemelerinde `brans_dersi` boşsa ve o
    denemedeki tüm detaylar TEK bir derse aitse ders üzerinden türetilir; tek
    derse indirgenemeyen gruplar güvenilmez sayılır ve bağlanmaz.

    Idempotent: `legacy_signature` üzerindeki UNIQUE indeks sayesinde aynı imza
    için ikinci başlık oluşmaz, deneme_id'si dolu detaylara dokunulmaz.
    """
    rapor = {
        "durum": "calisti",
        "toplam_detay": 0,
        "zaten_bagli": 0,
        "olusturulan_deneme": 0,
        "baglanan_detay": 0,
        "eslesmeyen_detay": 0,
        "eslesmeyen_gruplar": [],
    }
    cur = conn.cursor()
    cur.row_factory = sqlite3.Row
    cur.execute("SELECT COUNT(*) AS n FROM deneme_konu_yanlislari")
    rapor["toplam_detay"] = cur.fetchone()["n"]
    cur.execute(
        "SELECT COUNT(*) AS n FROM deneme_konu_yanlislari"
        " WHERE deneme_id IS NOT NULL"
    )
    rapor["zaten_bagli"] = cur.fetchone()["n"]

    if rapor["toplam_detay"] == 0 or rapor["zaten_bagli"] >= rapor["toplam_detay"]:
        rapor["durum"] = "atlandi"
        return rapor

    satirlar = cur.execute(
        """SELECT id, ogrenci_id, TRIM(COALESCE(deneme_adi, '')) AS ad,
                  COALESCE(tarih, '') AS tarih, deneme_kategorisi, deneme_turu,
                  brans_dersi, ders, net_bilgisi
           FROM deneme_konu_yanlislari
           WHERE deneme_id IS NULL
           ORDER BY id"""
    ).fetchall()

    gruplar = {}
    for satir in satirlar:
        anahtar = (
            satir["ogrenci_id"],
            satir["ad"],
            satir["tarih"],
            kategori_normalize(satir["deneme_kategorisi"]),
            tur_normalize(satir["deneme_turu"]),
            None
            if satir["net_bilgisi"] is None
            else round(float(satir["net_bilgisi"]), 4),
        )
        gruplar.setdefault(anahtar, []).append(satir)

    simdi_s = get_tr_now().strftime("%Y-%m-%d %H:%M:%S")
    ogrenci_ozet = {}
    cur.execute("SAVEPOINT faz2_migrasyon")
    try:
        for anahtar, kayitlar in gruplar.items():
            ogrenci_id, ad, tarih, kategori, tur, net = anahtar
            idler = [k["id"] for k in kayitlar]
            acik_branslar = {
                str(k["brans_dersi"]).strip()
                for k in kayitlar
                if k["brans_dersi"] is not None and str(k["brans_dersi"]).strip()
            }
            dersler = {
                str(k["ders"]).strip()
                for k in kayitlar
                if str(k["ders"] or "").strip()
            }
            brans = None
            sorun = None
            if not ad:
                sorun = "deneme adı boş"
            elif kategori is None:
                sorun = "kategori tanımsız"
            elif tur is None:
                sorun = "sınav türü tanımsız"
            elif net is None:
                sorun = "net bilgisi boş"
            elif kategori == DENEME_KATEGORI_GENEL:
                if acik_branslar:
                    sorun = "genel denemede branş dersi dolu"
            elif len(acik_branslar) > 1:
                sorun = "birden fazla branş dersi"
            elif len(acik_branslar) == 1:
                brans = next(iter(acik_branslar))
            elif len(dersler) == 1:
                brans = next(iter(dersler))
            else:
                sorun = "branş dersi türetilemedi"

            if sorun is None and kategori == DENEME_KATEGORI_BRANS:
                if len(dersler) > 1:
                    sorun = "branş denemesinde birden fazla ders"
                elif not brans_tur_uyumlu(brans, tur):
                    sorun = "branş dersi sınav türüyle uyumlu değil"


            if sorun is not None:
                rapor["eslesmeyen_detay"] += len(idler)
                rapor["eslesmeyen_gruplar"].append({
                    "deneme_adi": ad,
                    "tarih": tarih,
                    "kategori": kategori,
                    "tur": tur,
                    "brans_dersi": brans,
                    "detay_sayisi": len(idler),
                    "neden": sorun,
                })
                continue

            imza = (
                f"legacy|{ogrenci_id}|{ad}|{tarih}|{kategori}|{tur}|"
                f"{brans or '-'}|{net:.2f}"
            )
            gun = tarih_gunu(tarih) or tarih
            cur.execute(
                """INSERT OR IGNORE INTO denemeler
                   (ogrenci_id, tarih, deneme_adi, deneme_kategorisi, deneme_turu,
                    brans_dersi, net_bilgisi, kayit_kaynagi, legacy_signature,
                    olusturma_zamani)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ogrenci_id,
                    gun,
                    ad,
                    kategori,
                    tur,
                    brans,
                    net,
                    DENEME_KAYNAK_MIGRASYON,
                    imza,
                    simdi_s,
                ),
            )
            yeni_mi = cur.rowcount > 0
            cur.execute("SELECT id FROM denemeler WHERE legacy_signature = ?", (imza,))
            deneme_id = cur.fetchone()["id"]
            if yeni_mi:
                rapor["olusturulan_deneme"] += 1

            cur.executemany(
                "UPDATE deneme_konu_yanlislari SET deneme_id = ?"
                " WHERE id = ? AND deneme_id IS NULL",
                [(deneme_id, i) for i in idler],
            )
            rapor["baglanan_detay"] += cur.rowcount
            ozet = ogrenci_ozet.setdefault(ogrenci_id, {"deneme": 0, "detay": 0})
            ozet["deneme"] += 1
            ozet["detay"] += len(idler)

        for ogrenci_id, ozet in ogrenci_ozet.items():
            cur.execute(
                "INSERT INTO sistem_loglari (ogrenci_id, islem, detay, tarih)"
                " VALUES (?, ?, ?, ?)",
                (
                    ogrenci_id,
                    "DENEME_MIGRASYON",
                    f"Eski yanlış kayıtlarından {ozet['deneme']} deneme başlığı"
                    f" oluşturuldu/eşleştirildi, {ozet['detay']} detay bağlandı.",
                    simdi_s,
                ),
            )
        cur.execute("RELEASE faz2_migrasyon")
        conn.commit()
    except Exception:
        cur.execute("ROLLBACK TO faz2_migrasyon")
        cur.execute("RELEASE faz2_migrasyon")
        conn.commit()
        raise
    return rapor


def denemeleri_getir(conn, ogrenci_id):
    """Öğrencinin tüm deneme başlıklarını kronolojik sırada getirir."""
    return pd.read_sql_query(
        "SELECT id, tarih, deneme_adi, deneme_kategorisi, deneme_turu,"
        " brans_dersi, net_bilgisi, dogru_adedi, yanlis_adedi, bos_adedi,"
        " sure_dk, kayit_kaynagi, legacy_signature"
        " FROM denemeler WHERE ogrenci_id = ? ORDER BY tarih ASC, id ASC",
        conn,
        params=(ogrenci_id,),
    )


def deneme_ders_sonuclari_getir(conn, ogrenci_id):
    """Öğrencinin tüm ders bazlı deneme sonuçlarını (başlık bilgisiyle) getirir."""
    return pd.read_sql_query(
        "SELECT s.id, s.deneme_id, s.ders, s.soru_sayisi, s.dogru,"
        " s.yanlis, s.bos, s.net, s.sure_dk,"
        " d.tarih AS tarih, d.deneme_adi AS deneme_adi,"
        " d.deneme_kategorisi AS deneme_kategorisi,"
        " d.deneme_turu AS deneme_turu, d.brans_dersi AS brans_dersi"
        " FROM deneme_ders_sonuclari s"
        " JOIN denemeler d ON d.id = s.deneme_id"
        " WHERE d.ogrenci_id = ?"
        " ORDER BY d.tarih ASC, d.id ASC, s.ders ASC",
        conn,
        params=(ogrenci_id,),
    )


def deneme_ders_sonucu_ekle(
    conn,
    deneme_id,
    ders,
    dogru=0,
    yanlis=0,
    bos=0,
    soru_sayisi=None,
    sure_dk=None,
):
    """Var olan bir denemeye tek ders sonucu ekler.

    Aynı deneme + ders için ikinci kayıt UNIQUE indeks ile engellenir;
    çakışma ValueError'a çevrilir (sessizce üzerine yazılmaz).
    """
    satir = ders_sonucu_dogrula(
        ders, dogru, yanlis, bos, soru_sayisi, sure_dk
    )
    baslik = conn.execute(
        "SELECT deneme_turu FROM denemeler WHERE id = ?", (int(deneme_id),)
    ).fetchone()
    if baslik is None:
        raise ValueError(f"Deneme bulunamadı: {deneme_id}")
    tur = baslik[0] if not hasattr(baslik, "keys") else baslik["deneme_turu"]
    if not brans_tur_uyumlu(satir["ders"], tur):
        raise ValueError(
            f"'{satir['ders']}' dersi {tur} sınav türüyle uyumlu değil."
        )
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO deneme_ders_sonuclari
               (deneme_id, ders, soru_sayisi, dogru, yanlis, bos, net, sure_dk)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                int(deneme_id),
                satir["ders"],
                satir["soru_sayisi"],
                satir["dogru"],
                satir["yanlis"],
                satir["bos"],
                satir["net"],
                satir["sure_dk"],
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError as hata:
        conn.rollback()
        raise ValueError(
            f"'{satir['ders']}' dersi bu deneme için zaten kayıtlı."
        ) from hata
    return int(cur.lastrowid)


def baglanmamis_yanlis_sayisi(conn, ogrenci_id):
    """deneme_id'si hâlâ NULL olan aktif yanlış detayı sayısı."""
    satir = conn.execute(
        "SELECT COUNT(*) FROM deneme_konu_yanlislari WHERE ogrenci_id = ?"
        " AND deneme_id IS NULL AND (durum IS NULL OR durum = 'Aktif')",
        (ogrenci_id,),
    ).fetchone()
    return int(satir[0] if satir else 0)


def grafik_seri_secenekleri(df_denemeler, deneme_turu, df_ders=None):
    """Grafik için ayrık seri seçenekleri.

    FAZ 2: genel deneme toplamı + her branş ayrı seri.
    FAZ 3: genel denemenin ders bazlı netleri (varsa) ayrı seriler; böylece
    "TYT Matematik • Ders Bazlı" (genel deneme) ile "TYT Matematik" (branş)
    hiçbir zaman aynı seride birleşmez.
    """
    secenekler = []
    if df_denemeler is None or df_denemeler.empty:
        return secenekler
    alt = df_denemeler[df_denemeler["deneme_turu"] == deneme_turu]
    if alt.empty:
        return secenekler
    if not alt[alt["deneme_kategorisi"] == DENEME_KATEGORI_GENEL].empty:
        secenekler.append(
            {
                "etiket": f"{deneme_turu} Genel Deneme",
                "kategori": DENEME_KATEGORI_GENEL,
                "brans_dersi": None,
                "kaynak": "toplam",
            }
        )
    for ders in ders_seri_listesi(df_ders, deneme_turu, DENEME_KATEGORI_GENEL):
        secenekler.append(
            {
                "etiket": f"{ders} • Ders Bazlı",
                "kategori": DENEME_KATEGORI_GENEL,
                "brans_dersi": None,
                "kaynak": "ders",
                "ders": ders,
            }
        )
    branslar = {
        str(b).strip()
        for b in alt[alt["deneme_kategorisi"] == DENEME_KATEGORI_BRANS][
            "brans_dersi"
        ].tolist()
        if pd.notna(b) and str(b).strip() and str(b) != "None"
    }
    for brans in sorted(branslar):
        secenekler.append(
            {
                "etiket": brans,
                "kategori": DENEME_KATEGORI_BRANS,
                "brans_dersi": brans,
                "kaynak": "toplam",
            }
        )
    return secenekler


def seri_filtrele(df_denemeler, kategori, brans_dersi=None):
    """Tek bir grafik serisini (kategori + branş) kronolojik olarak döndürür."""
    if df_denemeler is None or df_denemeler.empty:
        return df_denemeler
    mask = df_denemeler["deneme_kategorisi"] == kategori
    if kategori == DENEME_KATEGORI_BRANS:
        mask = mask & (
            df_denemeler["brans_dersi"].fillna("").astype(str)
            == str(brans_dersi or "")
        )
    else:
        mask = mask & df_denemeler["brans_dersi"].isna()
    return (
        df_denemeler[mask]
        .sort_values(["tarih", "id"], kind="stable")
        .reset_index(drop=True)
    )


def kohort_yanlis_serileri(df_yanlislar):
    """Bağlı yanlış detaylarını (ders, konu, sınav kohortu) bazında serilere çevirir.

    Kohort = (ders, konu, sınav türü, deneme kategorisi, branş dersi). Böylece
    TYT genel denemesi ile TYT Matematik branş denemesi, TYT Türkçe ile TYT
    Matematik ve AYT Matematik ile TYT Matematik asla birleşmez.

    Aynı denemeye ait birden fazla satır TEK nokta sayılır; yanlış adedi aynı
    konu için MAX ile tekilleştirilir (eski çift kayıt şişirmesi engellenir).

    Dönüş: {(ders, konu, tur, kategori, brans): [{"deneme_id", "tarih",
            "yanlis", "ids", "neden"}, ...]}  (tarih, sonra deneme_id sırasıyla)
    """
    seriler = {}
    if df_yanlislar is None or len(df_yanlislar.index) == 0:
        return seriler
    df = df_yanlislar.copy()
    for kolon in ("deneme_turu", "deneme_kategorisi", "brans_dersi"):
        if kolon not in df.columns:
            df[kolon] = ""
        df[kolon] = df[kolon].fillna("").astype(str)
    df["tarih"] = (
        df["deneme_tarih"].fillna("").astype(str)
        if "deneme_tarih" in df.columns
        else ""
    )
    for kolon in ("deneme_id", "yanlis_adedi", "id"):
        df[kolon] = pd.to_numeric(df[kolon], errors="coerce").fillna(0).astype(int)

    for anahtar, grup in df.groupby(
        ["ders", "konu_adi", "deneme_turu", "deneme_kategorisi", "brans_dersi"],
        dropna=False,
    ):
        noktalar = []
        for deneme_id, alt in grup.groupby("deneme_id"):
            neden = (
                alt["yanlis_nedeni"].iloc[-1] if "yanlis_nedeni" in alt.columns else ""
            )
            noktalar.append({
                "deneme_id": int(deneme_id),
                "tarih": str(alt["tarih"].iloc[0]),
                "yanlis": int(alt["yanlis_adedi"].max()),
                "ids": [int(i) for i in alt["id"].tolist()],
                "neden": neden,
            })
        noktalar.sort(key=lambda n: (n["tarih"], n["deneme_id"]))
        seriler[anahtar] = noktalar
    return seriler


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

        # FAZ 2: Deneme başlığı ayrı bir varlık olarak tutulur. Yanlış detayları
        # bu başlığa `deneme_id` ile bağlanır; böylece aynı adı taşıyan iki
        # deneme asla tek kayıt gibi değerlendirilmez.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS denemeler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                tarih TEXT,
                deneme_adi TEXT,
                deneme_kategorisi TEXT DEFAULT 'Genel Deneme',
                deneme_turu TEXT,
                brans_dersi TEXT,
                net_bilgisi REAL,
                dogru_adedi INTEGER,
                yanlis_adedi INTEGER,
                bos_adedi INTEGER,
                sure_dk INTEGER,
                kayit_kaynagi TEXT DEFAULT 'wizard',
                legacy_signature TEXT,
                olusturma_zamani TEXT,
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
            )
        """)

        # Migrasyonun idempotent olmasını sağlayan kısmi tekil indeks.
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_denemeler_legacy
            ON denemeler(legacy_signature)
            WHERE legacy_signature IS NOT NULL
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_denemeler_ogrenci
            ON denemeler(ogrenci_id, deneme_turu, deneme_kategorisi, brans_dersi)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_denemeler_tarih
            ON denemeler(ogrenci_id, tarih)
        """)

        # FAZ 3: genel denemenin ders bazlı sonuçları. Eski denemeler için
        # geriye dönük kayıt ÜRETİLMEZ; tablo yalnızca yeni girişleri tutar.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deneme_ders_sonuclari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deneme_id INTEGER NOT NULL,
                ders TEXT NOT NULL,
                soru_sayisi INTEGER,
                dogru INTEGER DEFAULT 0,
                yanlis INTEGER DEFAULT 0,
                bos INTEGER DEFAULT 0,
                net REAL DEFAULT 0,
                sure_dk INTEGER,
                FOREIGN KEY(deneme_id) REFERENCES denemeler(id)
                    ON DELETE CASCADE
            )
        """)

        # Aynı denemede aynı ders için ikinci sonuç kaydını engeller.
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_deneme_ders_tekil
            ON deneme_ders_sonuclari(deneme_id, ders)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deneme_ders_ders
            ON deneme_ders_sonuclari(ders, deneme_id)
        """)

        mevcut_kolonlar = [
            satir[1] for satir in cursor.execute(
                "PRAGMA table_info(deneme_konu_yanlislari)"
            )
        ]
        if "deneme_id" not in mevcut_kolonlar:
            cursor.execute(
                "ALTER TABLE deneme_konu_yanlislari"
                " ADD COLUMN deneme_id INTEGER REFERENCES denemeler(id)"
            )
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deneme_yanlis_deneme_id
            ON deneme_konu_yanlislari(deneme_id)
        """)

        # FAZ 2: Eski yanlış kayıtlarını güvenilir imza eşleşmesiyle başlıklara
        # bağla. Idempotenttir; başarısız olursa hiçbir yarım veri bırakmaz.
        try:
            migrasyon_denemeleri(conn)
        except Exception as hata:
            cursor.execute(
                "INSERT INTO sistem_loglari (ogrenci_id, islem, detay, tarih)"
                " VALUES (NULL, 'DENEME_MIGRASYON_HATA', ?, ?)",
                (str(hata), get_tr_now().strftime("%Y-%m-%d %H:%M:%S")),
            )

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

# FAZ 4: gerçek çalışma oturumları tablosu/indeksleri (idempotent, veri silmez).
study_sessions.init_db()

# FAZ 5A: program sürümleme şeması (idempotent; eski görevler korunur).
program_service.init_db()

# FAZ 5B: mikro görev alt adımları (checklist) şeması.
task_steps.init_db()

# FAZ 5C: günlük müsaitlik şeması.
planner.init_db()

# FAZ 6A: aralıklı tekrar kayıtları (idempotent; veri silmez, geçmişi değiştirmez).
spaced_repetition.init_db()

# FAZ 6B: bireysel yanlış soru defteri (idempotent; veri silmez).
wrong_questions.init_db()

# FAZ 6C: görev <-> kaynak (tekrar kaydı / yanlış soru) bağları.
gorev_kaynaklari.init_db()

# FAZ 7: haftalık performans raporu hedef + değerlendirme şeması
# (idempotent; rapor anlık görüntü almaz, canlı veriden üretilir).
weekly_report.init_db()

# FAZ 8: hedef net tablosu (idempotent; mevcut netlerin üzerine yazmaz).
ranking_engine.init_db()

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
# FAZ 8: ÖSYM PUAN & SIRALAMA HESABI SERVİS KATMANINA TAŞINDI
# ==============================================================================
# Eski sürümde burada, kaynağı doğrulanmamış sabit puan-sıra tabloları ve
# tek formüle gömülü katsayılar bulunuyordu. FAZ 8 ile:
#   - hesaplama  -> services/ranking_engine.py
#   - yıl kuralları + puan-sıra referans verisi -> services/osym_verisi.py
#   - arayüz     -> "🎯 YKS Simülatörü" sekmesi (9. sekme)
# Resmî kaynakla doğrulanmamış hiçbir sıralama sayısı üretilmez.

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

# FAZ 4: `SORU_ILERLEME_ATLANACAK` listesi, kaldırılan `soru_ilerleme_isle()`
# ile birlikte geçersiz kaldı; planlanan soru artık ilerlemeye yazılmıyor.


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


# FAZ 4: `soru_ilerleme_isle()` KALDIRILDI.
#
# Eski davranış: görev "Tamamlandı" işaretlenince `hedef_soru` (PLANLANAN soru
# sayısı) kadar soru çözülmüş gibi `konu_soru_ilerleme` tablosuna yazıyordu.
# Bu, hiç çözülmemiş soruları çözülmüş gibi gösteriyordu.
#
# Yeni kural: soru ilerlemesi YALNIZCA services/study_sessions.py üzerinden
# kaydedilen TAMAMLANMIŞ çalışma oturumlarından (cozulen_soru) hesaplanır.
# Görev checkbox'ları yalnızca görev durumunu (calisma_programi_gorevler.durum)
# değiştirir. Eski `konu_soru_ilerleme` kayıtları silinmez, yeniden yazılmaz.


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


# ==============================================================================
# PROGRAM MOTORLARI (FAZ 5A)
# Motorlar artık VERİTABANINA YAZMAZ: yalnızca görev listesi üretir. Programın
# tek transaction'da yazılmasını `program_service.program_olustur` üstlenir.
# Böylece bir motor hata verse bile eski program, eski görevler ve gerçek
# çalışma oturumları korunur (hiçbir yerde DELETE yoktur).
# ==============================================================================
GOREV_SUTUNLARI = (
    "gun",
    "ders",
    "makro_konu",
    "mikro_konu",
    "gorev_tanimi",
    "hedef_soru",
    "pedagoji_turu",
    "tarih",
    "alt_konu",
)


def _satirlardan_gorevler(rows):
    """(gun, ders, ...) demetlerini görev sözlüklerine çevirir."""
    gorevler = []
    for satir in rows:
        gorev = {alan: None for alan in GOREV_SUTUNLARI}
        for alan, deger in zip(GOREV_SUTUNLARI, satir):
            gorev[alan] = deger
        gorevler.append(gorev)
    return gorevler


def akilli_program_motoru_gorevleri(
    ogrenci_id, aktif_mufredat, alarmlar,
    ana_blok_sayisi, blok_soru_butcesi, paragraf_hedef,
):
    """Sıralı + soru kotalı + hıza duyarlı 7 günlük görev listesi üretir.

    FAZ 5A: yalnızca bellek içinde çalışır; veritabanına yazmaz.
    """
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
                    f"📌 {d} için {slot_soru} karma soru çöz "
                    f"({kolaydan_zora_dagilim(slot_soru, 0.5)}).",
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
                tanim = (
                    f"📌 {mi} ➔ konu anlatımını izle ve kısa özet çıkar, "
                    f"ardından {soru} soru çöz ({kolaydan_zora_dagilim(soru, 0.0)})."
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
                    f"🧩 {mi} ➔ {soru} soru çöz "
                    f"({kolaydan_zora_dagilim(soru, oran)})."
                )
                rows.append((gun_adi, d, m, mi, tanim, soru, ped, tarih_str))
                sim_cozulen[(d, mi)] = sim_cozulen.get((d, mi), 0) + soru

    # FAZ 5A: yazma yok - görev listesi döndürülür (eski program korunur).
    return _satirlardan_gorevler(rows)
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
        # FAZ 5D: mikro konunun tam soru hedefi (görev bu hedefin parçası olabilir).
        if "mikro_hedef_soru" not in kolonlar:
            cur.execute(
                "ALTER TABLE calisma_programi_gorevler ADD COLUMN mikro_hedef_soru INTEGER"
            )
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
    """Tamamlanmış alt başlıklar: {(ders, mikro, alt)}.

    FAZ 5D: mikro konu, GÜNLÜK GÖREV tamamlanmasıyla değil, gerçek ilerleme
    kaydıyla (`task_steps.mikro_konu_ilerleme`) kapanır. Bu yüzden manuel/eski
    işaretlemelerin yanına otomatik tamamlanan mikro konular da eklenir; böylece
    tamamlanmış mikro konu yeniden planlanmaz.
    """
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
    try:  # FAZ 5D: gerçek ilerlemeden kapanan mikro konular
        sonuc.update(task_steps.mikro_tamamlananlar(ogrenci_id))
    except Exception:
        pass
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
    """Görev işaretlenince mikro konu ilerlemesini tazeler (FAZ 5D).

    GÜNLÜK GÖREV tamamlanması mikro konuyu KAPATMAZ. Mikro konu yalnızca
    öğrenme adımları bitip gerçek soru hedefi dolunca kapanır; bu durum
    `task_steps.mikro_ilerleme_guncelle` tarafından gerçek adım/oturumlardan
    türetilir. Burada eski alt başlık işaretleri korunur (geri alınmaz),
    yalnızca mikro konuya ait oturum/widget durumu tazelenir.
    """
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
        try:
            task_steps.mikro_ilerleme_guncelle(gorev_id)
        except Exception:
            pass
        alt_oturum_temizle(ders, makro, mikro)
    except Exception:
        pass


def gorev_chk_durum_senkron(anahtar, veritaban_degeri):
    """Görev checkbox'ının oturum değerini veritabanıyla eşitler.

    Aynı görev hem "Bugünün Görevleri" hem "Haftalık Program" sekmesinde
    işaretlenebildiği için, bir sekmede yapılan değişiklik diğer sekmedeki
    eski widget değeriyle çakışıyor; iki sekme birbirini geri alıp sonsuz
    `st.rerun()` döngüsüne giriyordu. Veritabanı değeri değiştiğinde widget
    oturum değeri burada güncellenir.
    """
    isaret = anahtar + "__db"
    yeni = bool(veritaban_degeri)
    if st.session_state.get(isaret) != yeni:
        st.session_state[anahtar] = yeni
        st.session_state[isaret] = yeni


def akilli_program_motoru_v2_gorevleri(
    ogrenci_id, aktif_mufredat, alarmlar,
    ana_blok_sayisi, blok_soru_butcesi, paragraf_hedef,
):
    """Alt başlık düzeyinde çalışan sıralı + soru kotalı + hıza duyarlı 7 günlük
    görev listesi üretir. FAZ 5A: yalnızca bellekte çalışır; yazma/silme yok."""
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
            f"📖 Günlük paragraf: {paragraf_hedef} soru çöz.",
            paragraf_hedef, "Ezber", tarih_str, "",
        ))

        if idx < len(hata_kuyrugu):
            h = hata_kuyrugu[idx]
            h_soru = min(15, slot_soru)
            rows.append((
                gun_adi, h["ders"], "Deneme Tekrarı", h["konu"],
                f"🔁 {h['konu']} ➔ denemede yanlış yaptığın soruları incele ve "
                f"{h_soru} soru çöz ({kolaydan_zora_dagilim(h_soru, 0.0)}).",
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
                        # FAZ 5D: her görev TEK mikro konu içerir; alt başlıklar
                        # birleştirilmez. Sıradaki mikro konular sonraki günlere
                        # (gerekirse sonraki haftaya) kalır.
                        paket.append(a)
                        paket_dk += nano_dk
                        sim_alt.add((d, mi, a))
                        break
                    mikro_bitti = all((d, mi, a) in sim_alt for a in alts)
                    per_nano = max(5, int(round(hedef / float(len(alts)) / 5.0) * 5))
                    soru = max(5, min(slot_soru, per_nano * len(paket), hedef))
                    liste_str = " | ".join(
                        f"{no}) {a} (~{nano_dk} dk)" for no, a in enumerate(paket, 1)
                    )
                    ogrenme_dk = paket_dk
                    bas = (
                        f"📌 {mi} ➔ mikro konu: {liste_str}. "
                        "Konu anlatımını izle ve 3-4 satır not çıkar; "
                    )
                    son_not = (
                        f" ✅ Bu görev bitince '{mi}' tamamlanmış olur."
                        if mikro_bitti else ""
                    )
                else:
                    soru = max(1, min(max(10, slot_soru // 2), hedef))
                    video = max(1, int(round(KONU_SURELERI_DK.get(mi, 60) / 30.0)))
                    ogrenme_dk = KONU_SURELERI_DK.get(mi, 60)
                    mikro_bitti = True
                    bas = f"📌 {mi} ➔ konu anlatımını izle ve kısa özet çıkar, "
                    son_not = ""
                tanim = (
                    bas
                    + f"ardından {soru} soru çöz ({kolaydan_zora_dagilim(soru, 0.0)})."
                    + son_not
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
                    f"🧩 {mi} ➔ {soru} soru çöz "
                    f"({kolaydan_zora_dagilim(soru, oran)})."
                )
                rows.append((gun_adi, d, m, mi, tanim, soru, ped, tarih_str, ""))
                sim_cozulen[(d, mi)] = sim_cozulen.get((d, mi), 0) + soru

    # FAZ 5A: yazma yok - görev listesi döndürülür (eski program korunur).
    return _satirlardan_gorevler(rows)


def eski_program_motoru_gorevleri(
    gunler,
    paragraf_hedef,
    blok_soru_butcesi,
    ana_gorev_blok_sayisi,
    filtered_pekistirme,
    filtered_ezber,
):
    """Son çare (temel) motor. FAZ 5A: yalnızca görev listesi üretir.

    Eski sürümde bu motor doğrudan tabloya yazıyor ve önce mevcut görevleri
    siliyordu. Artık ne yazar ne siler; plan yalnızca bellekte kurulur.
    """
    gorevler = []
    yari_blok = max(1, int(ana_gorev_blok_sayisi or 2) // 2)
    pekistirme_havuzu = list(filtered_pekistirme or [])
    ezber_havuzu = list(filtered_ezber or [])
    bugun_dt = get_tr_now()
    slot_soru = max(5, int(blok_soru_butcesi or 10))

    for idx, g in enumerate(gunler):
        tarih_dt = bugun_dt + timedelta(days=idx)
        tarih_str = tarih_dt.strftime("%Y-%m-%d")

        gorevler.append({
            "gun": g,
            "ders": "TYT Türkçe",
            "makro_konu": "Paragraf",
            "mikro_konu": "Günlük Paragraf",
            "gorev_tanimi": (
                f"📖 PARAGRAF: {paragraf_hedef} Paragraf Sorusu Çöz (~30 dk)"
            ),
            "hedef_soru": paragraf_hedef,
            "pedagoji_turu": "Ezber",
            "tarih": tarih_str,
            "alt_konu": None,
        })

        for _ in range(yari_blok):
            curr_item = (
                pekistirme_havuzu.pop(0)
                if pekistirme_havuzu
                else {
                    "ders": "TYT Matematik",
                    "makro": "Karma Soru",
                    "mikro": "Soru Çözümü & Prova",
                    "neden": "Genel Tekrar",
                }
            )
            konu_anlatim_dk = KONU_SURELERI_DK.get(curr_item["mikro"], 60)
            soru_cozum_dk = int(slot_soru * 1.5)
            toplam_gorev_suresi = konu_anlatim_dk + soru_cozum_dk
            gorevler.append({
                "gun": g,
                "ders": curr_item["ders"],
                "makro_konu": curr_item["makro"],
                "mikro_konu": curr_item["mikro"],
                "gorev_tanimi": (
                    f"📌 UYGULAMA & SORU: Konu/Tekrar ({konu_anlatim_dk} dk) + "
                    f"{slot_soru} Soru ({soru_cozum_dk} dk) "
                    f"[Toplam ~{toplam_gorev_suresi} dk | Odak: {curr_item['neden']}]"
                ),
                "hedef_soru": slot_soru,
                "pedagoji_turu": "Pekiştirme",
                "tarih": tarih_str,
                "alt_konu": None,
            })

        for _ in range(yari_blok):
            curr_item = (
                ezber_havuzu.pop(0)
                if ezber_havuzu
                else {
                    "ders": "TYT Biyoloji",
                    "makro": "Kavram Tekrarı",
                    "mikro": "Özet Not Çalışması",
                    "neden": "Genel Tekrar",
                }
            )
            konu_anlatim_dk = KONU_SURELERI_DK.get(curr_item["mikro"], 50)
            soru_cozum_dk = int(slot_soru * 1.5)
            toplam_gorev_suresi = konu_anlatim_dk + soru_cozum_dk
            gorevler.append({
                "gun": g,
                "ders": curr_item["ders"],
                "makro_konu": curr_item["makro"],
                "mikro_konu": curr_item["mikro"],
                "gorev_tanimi": (
                    f"📝 KAVRAM & ÖZET: Konu Çalış ({konu_anlatim_dk} dk) + "
                    f"{slot_soru} Soru ({soru_cozum_dk} dk) "
                    f"[Toplam ~{toplam_gorev_suresi} dk | Odak: {curr_item['neden']}]"
                ),
                "hedef_soru": slot_soru,
                "pedagoji_turu": "Ezber",
                "tarih": tarih_str,
                "alt_konu": None,
            })

            tekrar_dt = tarih_dt + timedelta(days=3)
            gorevler.append({
                "gun": GUN_ADLARI_LISTE[tekrar_dt.weekday()],
                "ders": curr_item["ders"],
                "makro_konu": curr_item["makro"],
                "mikro_konu": curr_item["mikro"],
                "gorev_tanimi": (
                    f"🔄 3 GÜNLÜK ARALIKLI TEKRAR: '{curr_item['mikro']}' "
                    "Notlarını 20 dk Gözden Geçir."
                ),
                "hedef_soru": 0,
                "pedagoji_turu": "Tekrar",
                "tarih": tekrar_dt.strftime("%Y-%m-%d"),
                "alt_konu": None,
            })
    return gorevler


def _gorevleri_zenginlestir(gorevler, ogrenci_id):
    """FAZ 5B/5D: görevleri MİKRO KONU bazında böler; checklist + süre ekler.

    FAZ 5D: Fallback motorları (alt başlık / soru kotalı / temel) ana konu
    seviyesinde görev üretse bile buradan geçen her görev tek mikro konuya
    ayrılır. Böylece hangi motor çalışırsa çalışsın hiyerarşi aynıdır:
    ders → ana konu → mikro konu → checklist. Bölme idempotenttir; zaten tek
    mikro konu içeren görev olduğu gibi kalır.
    """
    try:
        tamamlanan_altlar = alt_durumlari_yukle(ogrenci_id)
    except Exception:  # noqa: BLE001 - tablo yoksa bölme yine çalışır
        tamamlanan_altlar = set()
    sonuc = []
    for gorev in planner.mikro_gorevlere_ayir(
        gorevler or [],
        MIKRO_ALT_KONULAR,
        KONU_SURELERI_DK,
        tamamlanan_altlar=tamamlanan_altlar,
        ogrenci_id=ogrenci_id,
    ):
        alt_sayisi = 1
        alt = gorev.get("alt_konu")
        if alt:
            alt_sayisi = max(1, len([p for p in str(alt).split("||") if p.strip()]))
        sonuc.append(
            task_steps.gorev_zenginlestir(
                gorev,
                ogrenci_id=ogrenci_id,
                konu_sureleri=KONU_SURELERI_DK,
                alt_sayisi=alt_sayisi,
            )
        )
    return sonuc


def _gercek_cozulen_haritasi(ogrenci_id):
    """Ders+mikro bazında GERÇEK çözülen soru (yalnızca tamamlanmış oturumlar)."""
    sonuc = {}
    try:
        with get_connection() as conn:
            satirlar = conn.execute(
                "SELECT COALESCE(ders, 'Diğer') AS ders, mikro_konu,"
                " COALESCE(SUM(cozulen_soru), 0) AS soru"
                " FROM calisma_oturumlari WHERE ogrenci_id = ? AND durum = ?"
                " GROUP BY COALESCE(ders, 'Diğer'), mikro_konu",
                (ogrenci_id, "Tamamlandı"),
            ).fetchall()
    except Exception:  # noqa: BLE001 - tablo yoksa boş harita
        return sonuc
    for ders, mikro, soru in satirlar:
        if mikro:
            sonuc[(ders, mikro)] = int(soru or 0)
    return sonuc


def _gercek_mikro_cozulen_haritasi(ogrenci_id):
    """(ders, ana konu, MİKRO KONU) bazında gerçek çözülen soru.

    FAZ 5D: oturumlar `mikro_konu` (ana konu) + `alt_konu` (mikro konu) saklar.
    Böylece bir mikro konunun ilerlemesi diğerlerine yazılmaz.
    """
    sonuc = {}
    try:
        with get_connection() as conn:
            satirlar = conn.execute(
                "SELECT COALESCE(ders, 'Diğer') AS ders, mikro_konu, alt_konu,"
                " COALESCE(SUM(cozulen_soru), 0) AS soru"
                " FROM calisma_oturumlari WHERE ogrenci_id = ? AND durum = ?"
                " AND alt_konu IS NOT NULL AND TRIM(alt_konu) <> ''"
                " GROUP BY COALESCE(ders, 'Diğer'), mikro_konu, alt_konu",
                (ogrenci_id, "Tamamlandı"),
            ).fetchall()
    except Exception:  # noqa: BLE001 - tablo yoksa boş harita
        return sonuc
    for ders, mikro, alt, soru in satirlar:
        if ders and mikro and alt:
            sonuc[(ders, mikro, alt)] = int(soru or 0)
    return sonuc


def _planlama_onceki_gorevler(ogrenci_id):
    """Aktif programdaki görevler (devredilebilir kalan miktarla birlikte)."""
    sonuc = []
    try:
        aktif = program_service.aktif_program(ogrenci_id)
        if not aktif:
            return sonuc
        for gorev in program_service.program_gorevleri(aktif["id"]):
            kalan = program_service.devredilebilir_kalan(gorev["id"])
            gorev["gercek_soru"] = kalan["gercek_soru"]
            gorev["devredilen_soru"] = kalan["devredilen_soru"]
            sonuc.append(gorev)
    except Exception:  # noqa: BLE001
        return []
    return sonuc


def _alarm_konulari(alarmlar_db):
    """Alarm konularını öncelik sırasıyla düz listeye çevirir."""
    sonuc = []
    for kat in ("siyah", "kirmizi", "mor", "turuncu"):
        for alarm in (alarmlar_db or {}).get(kat, []) or []:
            ders = alarm.get("ders")
            konu = alarm.get("konu")
            if ders and konu:
                sonuc.append({"ders": ders, "konu": konu, "seviye": kat})
    return sonuc


def planlama_baglami_olustur(ogrenci_id, aktif_mufredat, alarmlar_db,
                             paragraf_soru=None):
    """FAZ 5C: akıllı plan motorunun girdilerini hazırlar (yalnızca okuma)."""
    durum = program_durumu_yukle(ogrenci_id)
    pedagoji = {}
    for ders, makro_dict in (aktif_mufredat or {}).items():
        if not isinstance(makro_dict, dict):
            continue
        for makro, mikrolar in makro_dict.items():
            if not isinstance(mikrolar, list):
                continue
            for mikro in mikrolar:
                pedagoji[(ders, mikro)] = get_konu_pedagoji_turu(ders, mikro)
    try:
        tamamlanan_altlar = alt_durumlari_yukle(ogrenci_id)
    except Exception:  # noqa: BLE001
        tamamlanan_altlar = set()
    return {
        "ogrenci_id": ogrenci_id,
        "baslangic": get_tr_now().date(),
        "gun_sayisi": 7,
        "musaitlik": planner.musaitlik_yukle(ogrenci_id),
        "mufredat": aktif_mufredat,
        "konu_sureleri": KONU_SURELERI_DK,
        "soru_agirliklari": SORU_AGIRLIKLARI,
        "on_kosullar": {**ON_KOSULLAR_EK, **ON_KOSULLAR},
        "mikro_alt": MIKRO_ALT_KONULAR,
        "bilinen_mikro": set(durum["bilinen_mikro"]),
        "gercek_cozulen": _gercek_cozulen_haritasi(ogrenci_id),
        "mikro_cozulen": _gercek_mikro_cozulen_haritasi(ogrenci_id),
        "onceki_gorevler": _planlama_onceki_gorevler(ogrenci_id),
        "paragraf_soru": max(10, int(paragraf_soru or 20)),
        "pedagoji": pedagoji,
        "tamamlanan_altlar": tamamlanan_altlar,
        "alarm_konular": _alarm_konulari(alarmlar_db),
    }


def haftalik_program_gorevleri_uret(
    ogrenci_id,
    aktif_mufredat,
    alarmlar,
    ana_gorev_blok_sayisi,
    blok_soru_butcesi,
    paragraf_hedef,
    gunler,
    filtered_pekistirme,
    filtered_ezber,
    plan_baglami=None,
):
    """Motor zinciri: akıllı plan (5C) → alt başlık → soru kotalı → temel.

    Hiçbir aşamada veritabanına yazılmaz veya silinmez; yalnızca görev listesi
    döner. Yazmayı `program_service.program_olustur` tek transaction'da yapar;
    hata olursa hiçbir şey değişmez (eski program aktif kalır).
    """
    uyarilar = []

    # FAZ 5C: kredi puanı + gerçek ilerleme + günlük kapasiteye dayalı motor
    if plan_baglami:
        try:
            sonuc = planner.plan_uret(plan_baglami)
            if sonuc.get("gorevler"):
                uyarilar.extend(sonuc.get("uyarilar") or [])
                return sonuc["gorevler"], "Akıllı plan", uyarilar
            uyarilar.append("Akıllı plan boş döndü.")
        except Exception as hata:  # noqa: BLE001
            uyarilar.append("Akıllı plan çalışmadı: %s" % hata)

    try:
        gorevler = akilli_program_motoru_v2_gorevleri(
            ogrenci_id,
            aktif_mufredat,
            alarmlar,
            ana_gorev_blok_sayisi,
            blok_soru_butcesi,
            paragraf_hedef,
        )
        if gorevler:
            return _gorevleri_zenginlestir(gorevler, ogrenci_id), "Alt başlık motoru", uyarilar
        uyarilar.append("Alt başlık motoru boş plan üretti.")
    except Exception as hata:  # noqa: BLE001 - motor çökse de program korunur
        uyarilar.append("Alt başlık motoru çalışmadı: %s" % hata)

    try:
        gorevler = akilli_program_motoru_gorevleri(
            ogrenci_id,
            aktif_mufredat,
            alarmlar,
            ana_gorev_blok_sayisi,
            blok_soru_butcesi,
            paragraf_hedef,
        )
        if gorevler:
            return (
                _gorevleri_zenginlestir(gorevler, ogrenci_id),
                "Soru kotalı motor",
                uyarilar,
            )
        uyarilar.append("Soru kotalı motor boş plan üretti.")
    except Exception as hata:  # noqa: BLE001
        uyarilar.append("Soru kotalı motor çalışmadı: %s" % hata)

    gorevler = eski_program_motoru_gorevleri(
        gunler,
        paragraf_hedef,
        blok_soru_butcesi,
        ana_gorev_blok_sayisi,
        filtered_pekistirme,
        filtered_ezber,
    )
    uyarilar.append("Temel program motoru kullanıldı.")
    return _gorevleri_zenginlestir(gorevler, ogrenci_id), "Temel motor", uyarilar


if "active_user" not in st.session_state:
    st.session_state.active_user = None

# SEKME DURUMU (FAZ 1): Sekme seçimi artık sunucu tarafında kalıcıdır.
# Her sekme grubu kendi anahtarını kullanır (st.tabs(key=..., on_change="rerun")):
#   kt_main_tabs, kt_ders_tabs, kt_deneme_grafik_tabs,
#   kt_program_gun_tabs, kt_rapor_tabs, kt_admin_tabs
# Eski "active_main_tab" değişkeni hiçbir yerde okunmadığı için kaldırıldı.

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

# FAZ 4: Çalışma serisi artık GİRİŞ tarihine değil GERÇEK ÇALIŞMAYA bağlı.
# `update_user_streak()` giriş günlerini sayıyordu; bu gerçek çalışma serisi
# değildir. Seri, tamamlanmış çalışma oturumlarından hesaplanır (bir günde
# toplam en az 15 dk tamamlanmış çalışma o günü saydırır). Eski giriş bazlı
# değer veritabanında korunur (silinmez), yalnızca ekranda gerçek seri
# gösterilir. Profil tasarımı değiştirilmez.
try:
    current_user["streak_count"] = study_sessions.gercek_calisma_serisi(
        current_user["id"]
    )
except Exception:
    current_user["streak_count"] = current_user.get("streak_count", 0)


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
        # FAZ 2: Alarm yalnızca deneme başlığına BAĞLI yanlış kayıtlarıyla
        # hesaplanır. deneme_id'si NULL olan eski kayıtlar sessizce yutulmaz;
        # arayüzde "bağlanmamış kayıt" uyarısıyla raporlanır.
        df_yanlislar = pd.read_sql_query(
            "SELECT y.id, y.deneme_id, y.deneme_adi, y.tarih, y.ders,"
            " y.makro_konu, y.konu_adi, y.yanlis_adedi, y.yanlis_nedeni,"
            " d.tarih AS deneme_tarih, d.deneme_turu AS deneme_turu,"
            " d.deneme_kategorisi AS deneme_kategorisi,"
            " d.brans_dersi AS brans_dersi"
            " FROM deneme_konu_yanlislari y"
            " JOIN denemeler d ON d.id = y.deneme_id"
            " WHERE y.ogrenci_id = ? AND (y.durum IS NULL OR y.durum = 'Aktif')"
            " ORDER BY y.id ASC",
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
        # FAZ 2: Sınav kohortu bazlı seri. Her nokta TEK bir deneme_id'dir;
        # sıralama deneme tarihine, eşitlik durumunda deneme_id'ye göredir.
        kohortler = kohort_yanlis_serileri(df_yanlislar)
        for (ders, konu, _tur, _kategori, _brans), seri in kohortler.items():
            yanlis_ids = [i for nokta in seri for i in nokta["ids"]]
            # Farklı denemelerdeki performans dizisi (deneme_id başına tek nokta)
            yanlis_listesi = [nokta["yanlis"] for nokta in seri]
            son_yanlis = yanlis_listesi[-1] if yanlis_listesi else 0
            son_neden = seri[-1]["neden"] if seri else ""

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

    admin_tab1, admin_tab2, admin_tab3 = st.tabs(
        [
            "➕ 1. Yeni Öğrenci Ekle",
            "👥 2. Öğrenci Düzenleme & Yönetim",
            "🛒 3. Özel Ders Talepleri",
        ],
        key="kt_admin_tabs",
        on_change="rerun",
    )

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

# YENİ ARAYÜZ MİMARİSİ: 9 SEKMELİ DÜZEN VE SEKME SIÇRAMA KORUMASI
# FAZ 6B: "📕 Yanlış Soru Defteri" sekmesi Deneme Analizi'nden hemen sonra
# gelir (akış: deneme gir -> yanlış soruları deftere işle -> program üret).
# FAZ 8: "🎯 YKS Simülatörü" sekmesi sona eklendi (puan + sıralama tahmini).
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(
    [
        "🎯 Bugünün Görevleri",
        "📚 Konu Takip & İlerleme",
        "📝 Deneme Analizi",
        "📕 Yanlış Soru Defteri",
        "🚨 Konu Uyarıları & Alarmlar",
        "📅 Haftalık Çalışma Programı",
        "🤝 Özel Ders & Raporlar",
        "📈 Haftalık Performans",
        "🎯 YKS Simülatörü",
    ],
    key="kt_main_tabs",
    on_change="rerun",
)



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
# FAZ 4: GERÇEK ÇALIŞMA ZAMANLAYICISI (ARAYÜZ KATMANI)
# ==============================================================================
# İş mantığının tamamı services/study_sessions.py içindedir; burada yalnızca
# gösterim ve kullanıcı etkileşimi yapılır.
CALISMA_BITIR_ANAHTARI = "calisma_bitir_oturum_id"

_CALISMA_SAYAC_CSS = """
<style>
.calisma-sayac{background:#eef2ff;border:1px solid #c7d2fe;border-radius:12px;
    padding:12px 16px;margin:6px 0 10px 0;}
.calisma-sayac .etiket{display:block;font-size:0.78rem;letter-spacing:0.06em;
    color:#4338ca;font-weight:700;}
.calisma-sayac .sure{display:block;font-size:2rem;font-weight:800;
    font-variant-numeric:tabular-nums;color:#1e1b4b;line-height:1.15;}
.calisma-sayac .konu{display:block;font-size:0.85rem;color:#475569;}
</style>
"""


def sure_bicimle(saniye):
    """Saniyeyi SS:DD:SS biçimine çevirir."""
    saniye = max(0, int(saniye or 0))
    return f"{saniye // 3600:02d}:{(saniye % 3600) // 60:02d}:{saniye % 60:02d}"


def dakika_bicimle(dakika):
    """Dakikayı '2 saat 35 dakika' biçiminde okunur hâle getirir."""
    dakika = max(0, int(dakika or 0))
    saat, kalan = divmod(dakika, 60)
    if saat and kalan:
        return f"{saat} saat {kalan} dakika"
    if saat:
        return f"{saat} saat"
    return f"{kalan} dakika"


def _calisma_hata_goster(hata):
    st.error(f"⚠️ {hata}")


def _oturum_sayac_icerigi(oturum_id):
    """Aktif oturumun geçen süresini çizer (yalnız bu parça yenilenir)."""
    oturum = study_sessions.oturum_getir(oturum_id)
    if not oturum or oturum["durum"] not in study_sessions.AKTIF_DURUMLAR:
        return
    mola_mi = oturum["durum"] == study_sessions.DURUM_MOLA
    konu = oturum.get("mikro_konu") or ""
    st.markdown(
        f'<div class="calisma-sayac">'
        f'<span class="etiket">'
        f'{"☕ MOLADASINIZ" if mola_mi else "⏱️ ÇALIŞMA SÜRÜYOR"}</span>'
        f'<span class="sure">{sure_bicimle(study_sessions.gecen_saniye(oturum))}</span>'
        f'<span class="konu">{oturum.get("ders") or ""}'
        f'{" • " + konu if konu else ""}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


# Streamlit 1.37+: sayaç yalnız kendi parçasını saniyede bir yeniler; tüm
# uygulama her saniye yeniden çalışmaz. Eski sürümlerde süre her etkileşimde
# veya sayfa yenilemesinde güncellenir (fallback).
if hasattr(st, "fragment"):
    _oturum_sayaci = st.fragment(run_every=1.0)(_oturum_sayac_icerigi)
else:
    _oturum_sayaci = _oturum_sayac_icerigi


def _aktif_oturum_paneli(oturum):
    """Aktif oturumun sayacı + Mola Ver / Devam Et / Bitir / İptal işlemleri."""
    oid = int(oturum["id"])
    st.markdown(_CALISMA_SAYAC_CSS, unsafe_allow_html=True)
    _oturum_sayaci(oid)

    mola_mi = oturum["durum"] == study_sessions.DURUM_MOLA
    col_a, col_b = st.columns(2)
    with col_a:
        if mola_mi:
            if st.button(
                "▶️ Çalışmaya Devam Et",
                key=f"calisma_devam_{oid}",
                type="primary",
            ):
                try:
                    study_sessions.oturum_devam_ettir(oid)
                except study_sessions.CalismaOturumHatasi as hata:
                    _calisma_hata_goster(hata)
                else:
                    st.rerun()
        else:
            if st.button("☕ Mola Ver", key=f"calisma_mola_{oid}"):
                try:
                    study_sessions.oturum_duraklat(oid)
                except study_sessions.CalismaOturumHatasi as hata:
                    _calisma_hata_goster(hata)
                else:
                    st.rerun()
    with col_b:
        if st.button(
            "⏹️ Çalışmayı Bitir",
            key=f"calisma_bitir_{oid}",
            type="secondary",
        ):
            try:
                # Süre dondurulur; kayıt ekranında öğrenci kontrol eder.
                study_sessions.oturum_duraklat(oid)
            except study_sessions.CalismaOturumHatasi as hata:
                _calisma_hata_goster(hata)
            else:
                st.session_state[CALISMA_BITIR_ANAHTARI] = oid
                st.rerun()

    with st.expander("⚙️ Bu çalışmayı iptal et"):
        st.caption(
            "Yanlışlıkla başlatıldıysa iptal edebilirsiniz. Kayıt silinmez,"
            " çalışma istatistiklerine katılmaz."
        )
        if st.button("🚫 Oturumu iptal et", key=f"calisma_iptal_{oid}"):
            try:
                study_sessions.oturum_iptal(oid)
            except study_sessions.CalismaOturumHatasi as hata:
                _calisma_hata_goster(hata)
            else:
                st.session_state.pop(CALISMA_BITIR_ANAHTARI, None)
                st.rerun()


def _oturum_bitirme_formu(oturum, planlanan_soru=0):
    """Çalışma bitirme ekranı: gerçek süre + gerçek çözülen soru sayısı."""
    oid = int(oturum["id"])
    olculen = study_sessions.gecen_saniye(oturum)
    max_dk = study_sessions.MAKS_GERCEK_SURE_DK
    olculen_dk = min(max_dk, int(round(olculen / 60.0)))
    konu = oturum.get("mikro_konu") or "-"

    st.markdown("#### 📝 Çalışma Kaydı")
    st.caption(f"{oturum.get('ders') or ''} • {konu}")
    st.markdown(f"**Zamanlayıcının ölçtüğü süre:** `{sure_bicimle(olculen)}`")
    st.caption(
        "Uygulama kapalıyken geçen süre ölçüme dâhil olmuş olabilir."
        " Gerçek odak süreniz farklıysa aşağıdan düzeltin."
    )

    with st.form(f"calisma_kayit_form_{oid}"):
        gercek_dk = st.number_input(
            "Gerçek çalışma süresi (dakika)",
            min_value=0,
            max_value=max_dk,
            value=olculen_dk,
            step=1,
            key=f"calisma_kayit_dk_{oid}",
        )
        cozulen = st.number_input(
            "Gerçek çözülen soru sayısı",
            min_value=0,
            max_value=study_sessions.MAKS_COZULEN_SORU,
            value=0,
            step=1,
            key=f"calisma_kayit_soru_{oid}",
            help="Bu çalışmada gerçekten üzerinden geçtiğiniz soru sayısı.",
        )
        if planlanan_soru:
            st.caption(
                f"Planlanan soru: **{planlanan_soru}** (plan verisi)."
                " Buraya planı değil gerçekte çözdüğünüz soru sayısını yazın."
            )
        kirilim_var = st.checkbox(
            "Soruları doğru / yanlış / boş olarak ayırdım",
            value=False,
            key=f"calisma_kayit_kirilim_{oid}",
            help="Takip etmiyorsanız işaretlemeyin; bu alanlar boş (NULL) kalır.",
        )
        dogru = yanlis = bos = None
        if kirilim_var:
            col_d, col_y, col_b = st.columns(3)
            with col_d:
                dogru = st.number_input(
                    "Doğru",
                    min_value=0,
                    max_value=study_sessions.MAKS_COZULEN_SORU,
                    value=0,
                    step=1,
                    key=f"calisma_kayit_dogru_{oid}",
                )
            with col_y:
                yanlis = st.number_input(
                    "Yanlış",
                    min_value=0,
                    max_value=study_sessions.MAKS_COZULEN_SORU,
                    value=0,
                    step=1,
                    key=f"calisma_kayit_yanlis_{oid}",
                )
            with col_b:
                bos = st.number_input(
                    "Boş",
                    min_value=0,
                    max_value=study_sessions.MAKS_COZULEN_SORU,
                    value=0,
                    step=1,
                    key=f"calisma_kayit_bos_{oid}",
                )
            st.caption(
                "Doğru + yanlış + boş toplamı çözülen soru sayısına eşit"
                " olmalıdır; eşleşmezse kayıt reddedilir."
            )
        notu = st.text_area(
            "Öğrenci notu (isteğe bağlı)",
            placeholder="Örn: Zor sorularda zorlandım, yarın buradan devam edeceğim.",
            max_chars=study_sessions.MAKS_NOT_UZUNLUK,
            key=f"calisma_kayit_not_{oid}",
        )
        col_kaydet, col_vazgec = st.columns(2)
        with col_kaydet:
            kaydet = st.form_submit_button("💾 Kaydet", type="primary")
        with col_vazgec:
            vazgec = st.form_submit_button("Vazgeç")

    if vazgec:
        st.session_state.pop(CALISMA_BITIR_ANAHTARI, None)
        st.rerun()
    if kaydet:
        try:
            kaydedilen = study_sessions.oturum_tamamla(
                oid,
                cozulen_soru=cozulen,
                gercek_sure_dk=gercek_dk,
                dogru=dogru,
                yanlis=yanlis,
                bos=bos,
                ogrenci_notu=notu,
            )
        except study_sessions.CalismaOturumHatasi as hata:
            _calisma_hata_goster(hata)
        else:
            # FAZ 5B: gerçek çalışma kaydı görevin alt adımlarını ilerletir;
            # tüm adımlar bittiyse görev otomatik tamamlanır.
            try:
                if kaydedilen and kaydedilen.get("gorev_id"):
                    task_steps.gorev_durum_guncelle(kaydedilen["gorev_id"])
            except Exception:
                pass
            st.session_state.pop(CALISMA_BITIR_ANAHTARI, None)
            set_flash_message("success", "✅ Çalışma kaydedildi.")
            st.rerun()


def _gercek_calisma_ozeti(ogrenci_id, aktif_oturum):
    """Bugün / bu hafta GERÇEK çalışma metrikleri + ders bazlı özet."""
    ozet = study_sessions.gunluk_haftalik_ozet(ogrenci_id)
    col_1, col_2, col_3 = st.columns(3)
    col_1.metric("⏱️ Bugün", dakika_bicimle(ozet["bugun_dk"]))
    col_2.metric("📅 Bu hafta", dakika_bicimle(ozet["hafta_dk"]))
    col_3.metric("✍️ Bu hafta çözülen soru", f"{ozet['hafta_soru']}")
    if aktif_oturum:
        devam_dk = int(study_sessions.gecen_saniye(aktif_oturum) // 60)
        st.caption(
            f"⏳ Devam eden çalışma: {dakika_bicimle(devam_dk)}"
            " (bitirince toplama eklenir)"
        )

    dersler = study_sessions.ders_bazli_ozet(ogrenci_id, gun_sayisi=7)
    with st.expander("📊 Derslere göre gerçek çalışma (son 7 gün)"):
        if dersler:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Ders": d["ders"],
                            "Süre": dakika_bicimle(d["dk"]),
                            "Çözülen soru": d["soru"],
                            "Oturum": d["oturum"],
                        }
                        for d in dersler
                    ]
                ),
                hide_index=True,
            )
        else:
            st.caption("Son 7 günde kaydedilmiş tamamlanmış çalışma yok.")
        gecmis = study_sessions.oturum_gecmisi(ogrenci_id, limit=5)
        if gecmis:
            st.markdown("**Son çalışmalar**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Tarih": (
                                o.get("bitis_zamani")
                                or o.get("baslangic_zamani")
                                or ""
                            )[:16],
                            "Ders": o.get("ders") or "-",
                            "Konu": o.get("mikro_konu") or "-",
                            "Süre": f"{int(o.get('gercek_sure_dk') or 0)} dk",
                            "Soru": int(o.get("cozulen_soru") or 0),
                            "Not": (o.get("ogrenci_notu") or "")[:40],
                        }
                        for o in gecmis
                    ]
                ),
                hide_index=True,
            )


def _gorev_gercek_soru_ozeti(gorev, ogrenci_id):
    """Planlanan / gerçekleşen / kalan soru özeti (görev kartının altı)."""
    g_id = int(gorev["id"])
    plan = int(gorev.get("hedef_soru") or 0)
    gercek = study_sessions.gorev_cozulen_soru(ogrenci_id, g_id)
    if plan <= 0 and not gercek["cozulen"] and not gercek["sure_dk"]:
        return
    parcalar = []
    if plan > 0:
        parcalar.append(f"Planlanan {plan} soru")
    parcalar.append(f"Gerçekleşen {gercek['cozulen']} soru")
    if plan > 0:
        parcalar.append(f"Kalan {max(0, plan - gercek['cozulen'])} soru")
    if gercek["sure_dk"]:
        parcalar.append(f"{dakika_bicimle(gercek['sure_dk'])} çalışma")
    st.caption("📊 " + " • ".join(parcalar))


def _gorev_adimlari_senkron(gorev_id, kayitli_durum):
    """Adımları okur; türetilen tamamlanma kayıtlı durumdan farklıysa eşitler.

    Görev tamamlanması alt adımlara bağlıdır: soru blokları gerçek çalışma
    oturumlarından dolduğunda görev kendiliğinden tamamlanır.
    """
    adimlar = task_steps.gorev_adimlari(gorev_id)
    if not adimlar:
        return []
    tamam = all(a["tamam"] for a in adimlar)
    if bool(kayitli_durum) != tamam:
        try:
            task_steps.gorev_durum_guncelle(gorev_id)
        except Exception:
            pass
    return adimlar


def _gorev_adim_listesi(adimlar):
    """FAZ 5B: mikro görev checklist'i.

    - Elle yapılan adımlar (video izle, not çıkar) checkbox olarak tutulur ve
      durumları veritabanına yazılır; sayfa yenilenince korunur.
    - Soru blokları salt okunurdur: tamamlanma durumları yalnızca GERÇEK
      çalışma oturumlarından türetilir. Kutuya tıklamak soru ilerlemesi
      üretmez (tek gerçek kaynak FAZ 4 oturumlarıdır).
    """
    if not adimlar:
        return
    st.markdown("**Yapılacaklar**")
    for adim in adimlar:
        if adim.get("adim_turu") == task_steps.ADIM_SORU:
            gercek = int(adim.get("gercek_soru") or 0)
            hedef = int(adim.get("hedef_soru") or 0)
            ikon = "✅" if adim.get("tamam") else "🔢"
            st.markdown(
                f"{ikon} **{adim['baslik']}** · gerçekleşen **{gercek}/{hedef}**"
            )
            if hedef > 0:
                st.progress(min(1.0, gercek / float(hedef)))
            continue
        anahtar = "adim_chk_%s" % adim["id"]
        gorev_chk_durum_senkron(anahtar, bool(adim.get("tamam")))
        secili = st.checkbox(adim["baslik"], key=anahtar)
        if secili != bool(adim.get("tamam")):
            try:
                task_steps.adim_durum_degistir(adim["id"], secili)
            except task_steps.AdimHatasi as hata:
                _calisma_hata_goster(hata)
            st.rerun()


def _calisma_basla_butonu(gorev, ogrenci_id):
    """Görev kartındaki 'Çalışmaya Başla' butonu."""
    g_id = int(gorev["id"])
    if st.button("▶️ Çalışmaya Başla", key=f"calisma_basla_{g_id}", type="primary"):
        try:
            study_sessions.oturum_baslat(
                ogrenci_id,
                gorev_id=g_id,
                ders=gorev.get("ders"),
                makro_konu=gorev.get("makro_konu"),
                mikro_konu=gorev.get("mikro_konu"),
                alt_konu=gorev.get("alt_konu"),
            )
        except study_sessions.CalismaOturumHatasi as hata:
            _calisma_hata_goster(hata)
        else:
            st.rerun()


def _oturum_paneli_veya_form(oturum, planlanan_soru=0):
    """Bitirme ekranı istenmişse formu, aksi hâlde sayacı gösterir."""
    if st.session_state.get(CALISMA_BITIR_ANAHTARI) == oturum["id"]:
        _oturum_bitirme_formu(oturum, planlanan_soru)
    else:
        _aktif_oturum_paneli(oturum)


# ==============================================================================
# FAZ 5A: ÖNCEKİ PROGRAMLARIM (geçmiş sürümler - salt okunur)
# ==============================================================================
def _onceki_programlar_bolumu(ogrenci_id):
    """Geçmiş program sürümlerinin sade özeti. Hiçbir kayıt silinmez/değişmez."""
    try:
        gecmis = program_service.gecmis_ozeti(ogrenci_id, limit=8)
    except Exception as hata:  # noqa: BLE001 - arayüz çökmemeli
        st.caption("Program geçmişi okunamadı: %s" % hata)
        return
    kayitlar = list(gecmis.get("programlar") or [])
    eski = gecmis.get("eski_kayitlar")
    if eski:
        kayitlar.append(eski)
    if not kayitlar:
        return
    with st.expander("📚 Önceki Programlarım", expanded=False):
        st.caption(
            "Program yenilemek geçmişinizi silmez: tamamlanan görevler, yarım"
            " kalanlar ve gerçek çalışma süreleri burada saklı kalır."
        )
        for kayit in kayitlar:
            bas = kayit.get("baslangic_tarihi") or "-"
            bit = kayit.get("bitis_tarihi") or "-"
            oran = int(kayit.get("oran") or 0)
            st.markdown(
                f"**{bas} ➔ {bit}** · {kayit.get('durum') or '-'}  \n"
                f"✅ Tamamlanan: {kayit.get('tamamlanan', 0)} · "
                f"⏳ Yarım kalan: {kayit.get('yarim', 0)} · "
                f"%{oran} tamamlandı · "
                f"⏱️ {kayit.get('gercek_sure_dk', 0)} dk gerçek çalışma"
            )
            st.progress(max(0.0, min(1.0, oran / 100.0)))
        st.caption(
            "Geçmiş kayıtlar salt okunurdur; bu bölümden hiçbir görev"
            " değiştirilmez veya silinmez."
        )


# ==============================================================================
# TAB 1: BUGÜNÜN GÖREVLERİ (ODAK EKRANI)
# ==============================================================================
with tab1:
    st.header("🎯 Bugünün Görevleri")
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

    # FAZ 5A: günün görevleri TAM TARİH + aktif program + öğrenci üzerinden
    # filtrelenir. Eski `(tarih = ? OR gun = ?)` birleşimi kaldırıldı; böylece
    # geçen haftaların aynı gün adına ait görevleri bugüne sızmaz. Program
    # bağlantısı olmayan eski kayıtlar yalnızca aktif program yokken gösterilir.
    BUGUN_GOREV_SUTUNLARI = [
        "id",
        "ders",
        "makro_konu",
        "mikro_konu",
        "alt_konu",
        "gorev_tanimi",
        "hedef_soru",
        "tahmini_sure_dk",
        "pedagoji_turu",
        "durum",
        "program_id",
        "kaynak_gorev_id",
    ]
    df_bugun = pd.DataFrame(
        program_service.gun_gorevleri(current_user["id"], bugun_str),
        columns=BUGUN_GOREV_SUTUNLARI,
    )

    # FAZ 4: aktif çalışma oturumu veritabanından okunur; sayfa yenilense,
    # başka sekmeye geçilse veya uygulama kapansa da kaybolmaz.
    ogrenci_id = current_user["id"]
    aktif_oturum = study_sessions.aktif_oturum_getir(ogrenci_id)
    gosterilen_gorevler = set()

    st.markdown("#### ⏱️ Gerçek Çalışma Özeti")
    _gercek_calisma_ozeti(ogrenci_id, aktif_oturum)
    st.markdown("---")

    # FAZ 5B: adımlar bir kez okunur; görev tamamlanması adımlardan türetilir.
    adim_onbellek = {
        int(satir["id"]): _gorev_adimlari_senkron(int(satir["id"]), satir["durum"])
        for _, satir in df_bugun.iterrows()
    }

    if not df_bugun.empty:
        biten_cnt = 0
        for _, satir in df_bugun.iterrows():
            adimlar = adim_onbellek.get(int(satir["id"])) or []
            bitti = all(a["tamam"] for a in adimlar) if adimlar else bool(satir["durum"])
            biten_cnt += 1 if bitti else 0
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
            g_id = int(g_row["id"])
            ped = g_row["pedagoji_turu"]
            # FAZ 5B: alt adımları olan görevlerde tamamlanma adımlardan türetilir.
            adimlar = adim_onbellek.get(g_id) or []
            is_done = (
                all(a["tamam"] for a in adimlar) if adimlar else bool(g_row["durum"])
            )
            sure_dk = g_row.get("tahmini_sure_dk")
            try:
                sure_dk = int(sure_dk) if sure_dk == sure_dk else 0
            except (TypeError, ValueError):
                sure_dk = 0
            alt_konu = g_row.get("alt_konu")
            mikro_satiri = (
                f'<p style="margin:2px 0 6px 0; color:#475569;">'
                f"<b>Mikro konu:</b> {alt_konu}</p>"
                if isinstance(alt_konu, str) and alt_konu.strip()
                else ""
            )
            sure_etiketi = (
                f'<span style="background-color:#dcfce7; color:#166534;'
                f" padding:2px 8px; border-radius:6px; font-size:0.85rem;"
                f' font-weight:600;">⏱️ {task_steps.sure_metni(sure_dk)}</span> '
                if sure_dk > 0
                else ""
            )

            st.markdown(
                f'<div class="focus-task-card">'
                f'<h4>{"✅" if is_done else "📌"} {g_row["ders"]} — {g_row["mikro_konu"]}</h4>'
                f"{mikro_satiri}"
                f'<p style="font-size: 1.05rem; margin-bottom: 8px;">{g_row["gorev_tanimi"]}</p>'
                f"{sure_etiketi}"
                f'<span style="background-color:#e0e7ff; color:#3730a3; padding:2px 8px; border-radius:6px; font-size:0.85rem; font-weight:600;">{ped}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

            if adimlar:
                # FAZ 5B: mikro görev checklist'i (soru blokları salt okunur)
                _gorev_adim_listesi(adimlar)
            else:
                col_chk1, col_chk2 = st.columns([4, 1])
                with col_chk2:
                    chk_anahtar = f"focus_chk_{g_id}"
                    # FAZ 4: aynı görev haftalık program sekmesinde de
                    # işaretlenebildiği için oturum değeri veritabanıyla eşitlenir.
                    gorev_chk_durum_senkron(chk_anahtar, is_done)
                    chk_val = st.checkbox(
                        "Tamamladım",
                        key=chk_anahtar,
                    )
                    if chk_val != is_done:
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "UPDATE calisma_programi_gorevler SET durum = ?"
                                " WHERE id = ?",
                                (1 if chk_val else 0, g_id),
                            )
                            conn.commit()
                        log_islem(
                            current_user["id"],
                            "TASK_TOGGLE_FOCUS",
                            f"Gorev ID {g_id} -> {chk_val}",
                        )
                        # FAZ 4: checkbox yalnızca görev durumunu değiştirir.
                        # Soru ilerlemesi planlanan sorudan DEĞİL, gerçek çalışma
                        # oturumlarından hesaplanır (soru_ilerleme_isle kaldırıldı).
                        gorev_alt_konu_isle(g_id, chk_val)
                        st.rerun()

            # FAZ 4: görev kartının altında çalışma zamanlayıcısı
            gosterilen_gorevler.add(int(g_id))
            if aktif_oturum and int(aktif_oturum.get("gorev_id") or 0) == int(g_id):
                _oturum_paneli_veya_form(
                    aktif_oturum, int(g_row.get("hedef_soru") or 0)
                )
            else:
                _gorev_gercek_soru_ozeti(g_row, ogrenci_id)
                _calisma_basla_butonu(g_row, ogrenci_id)
                if aktif_oturum:
                    st.caption(
                        "⏳ Başka bir görevde çalışma sürüyor; önce onu"
                        " bitirin veya iptal edin."
                    )

        # Aktif oturum bugünün listesinde olmayan bir göreve aitse yine
        # görünür olsun (görev silinse bile çalışma kaybolmaz).
        if (
            aktif_oturum
            and int(aktif_oturum.get("gorev_id") or 0) not in gosterilen_gorevler
        ):
            st.markdown("---")
            st.markdown("#### ⏳ Devam eden çalışma")
            _oturum_paneli_veya_form(aktif_oturum)
    else:
        if aktif_oturum:
            st.markdown("#### ⏳ Devam eden çalışma")
            _oturum_paneli_veya_form(aktif_oturum)
            st.markdown("---")
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
        ders_tablari = st.tabs(
            list(aktif_mufredat_hiyerarsisi.keys()),
            key="kt_ders_tabs",
            on_change="rerun",
        )

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
    if "wiz_tarih" not in st.session_state:
        st.session_state.wiz_tarih = get_tr_now().date()
    if "wiz_kayit_sonuc" not in st.session_state:
        st.session_state.wiz_kayit_sonuc = None

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
        ders_girdileri = []
        ders_hatalari = []
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
            # FAZ 2: Denemenin GERÇEK tarihi. Grafik ve alarm sıralaması giriş
            # sırasına değil bu tarihe göre yapılır.
            st.session_state.wiz_tarih = st.date_input(
                "Deneme Tarihi:",
                value=st.session_state.wiz_tarih,
                max_value=get_tr_now().date(),
                format="DD/MM/YYYY",
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
                # FAZ 2: TEK branş dersi seçimi. Widget anahtarı ayrı tutulur,
                # seçim `wiz_brans_dersi` state'ine yazılır; böylece sihirbazın
                # sonraki adımlarında (widget ekranda yokken) değer korunur.
                secilen_brans = st.selectbox(
                    "Branş Dersi Seçimi:",
                    options=uyumlu_dersler,
                    key="wiz_brans_secim",
                )
                st.session_state.wiz_brans_dersi = secilen_brans
                max_net_val = (
                    40.0
                    if "Matematik" in secilen_brans or "Türkçe" in secilen_brans
                    else 80.0
                )
                st.session_state.wiz_net = st.number_input(
                    "Branş Netiniz:",
                    min_value=0.0,
                    max_value=max_net_val,
                    value=min(25.0, max_net_val),
                    step=0.25,
                )
                # FAZ 3: branş sonucu ders tablosuna bağlanır. Doğru/yanlış
                # girilirse net otomatik hesaplanır ve başlığa o değer yazılır.
                wiz_brans_detay = None
                with st.expander("🔍 Ders Detayı (opsiyonel)", expanded=False):
                    st.caption(
                        "Doğru / yanlış sayılarınızı girerseniz net"
                        " **Doğru − Yanlış/4** olarak otomatik hesaplanır ve"
                        " ders bazlı grafikte görünür. Girmezseniz yalnızca"
                        " toplam branş neti kaydedilir."
                    )
                    detay_col1, detay_col2 = st.columns(2)
                    with detay_col1:
                        detay_soru = st.number_input(
                            "Soru Sayısı:",
                            min_value=DERS_SONUC_MIN_SORU,
                            max_value=DERS_SONUC_MAKS_SORU,
                            value=40 if st.session_state.wiz_tur != "YDT" else 80,
                            step=1,
                            key="wiz_brans_soru",
                        )
                        detay_dogru = st.number_input(
                            "Doğru:",
                            min_value=0,
                            max_value=DERS_SONUC_MAKS_SORU,
                            value=0,
                            step=1,
                            key="wiz_brans_dogru",
                        )
                    with detay_col2:
                        detay_yanlis = st.number_input(
                            "Yanlış:",
                            min_value=0,
                            max_value=DERS_SONUC_MAKS_SORU,
                            value=0,
                            step=1,
                            key="wiz_brans_yanlis",
                        )
                        detay_bos = st.number_input(
                            "Boş:",
                            min_value=0,
                            max_value=DERS_SONUC_MAKS_SORU,
                            value=0,
                            step=1,
                            key="wiz_brans_bos",
                        )
                    if detay_dogru + detay_yanlis > 0:
                        try:
                            wiz_brans_detay = ders_sonucu_dogrula(
                                secilen_brans,
                                detay_dogru,
                                detay_yanlis,
                                detay_bos,
                                detay_soru,
                            )
                        except ValueError as detay_hata:
                            st.error(f"⚠️ {detay_hata}")
                            wiz_brans_detay = None
                        if wiz_brans_detay:
                            st.session_state.wiz_net = wiz_brans_detay["net"]
                            st.info(
                                "Doğru/yanlışa göre hesaplanan net:"
                                f" **{wiz_brans_detay['net']:.2f}** — kayıtta bu"
                                " değer kullanılacak."
                            )
                st.session_state.wiz_brans_detay = wiz_brans_detay
                st.session_state.wiz_ders_sonuclari = (
                    [wiz_brans_detay] if wiz_brans_detay else []
                )
            else:
                st.session_state.wiz_brans_dersi = None
                st.session_state.wiz_brans_detay = None
                ders_secenekleri = genel_ders_secenekleri(
                    st.session_state.wiz_tur, ogrenci_alan
                )
                mod_secenekleri = ["Ders Bazlı", "Sadece Toplam Net"]
                if not ders_secenekleri:
                    mod_secenekleri = ["Sadece Toplam Net"]
                if st.session_state.get("wiz_ders_modu") not in mod_secenekleri:
                    st.session_state.wiz_ders_modu = mod_secenekleri[0]
                # FAZ 3: genel denemenin ders bazlı netleri. Net her zaman
                # doğru/yanlıştan hesaplanır; aynı bilgi ikinci kez sorulmaz.
                st.radio(
                    "Genel Deneme Giriş Yöntemi:",
                    options=mod_secenekleri,
                    horizontal=True,
                    key="wiz_ders_modu",
                    help=(
                        "Ders bazlı sonuçlarınız varsa her ders için doğru /"
                        " yanlış / boş girin. Elinizde ders kırılımı yoksa"
                        " 'Sadece Toplam Net' seçeneğini kullanın."
                    ),
                )
                if st.session_state.wiz_ders_modu == "Ders Bazlı":
                    st.caption(
                        "Her ders için doğru / yanlış / boş sayısını girin."
                        " Netler otomatik hesaplanır; boş bıraktığınız ders"
                        " kaydedilmez."
                    )
                    if st.session_state.wiz_tur == "AYT":
                        st.caption(
                            "ℹ️ ÖSYM düzeninde AYT Geometri soruları Matematik"
                            " Testinin içindedir (toplam 40 soru); bu yüzden"
                            " ayrı geometri satırı yoktur. Geometriyi ayrı"
                            " takip etmek isterseniz branş denemesi girin."
                        )
                    varsayilan_satirlar = [
                        {
                            "Ders": d_ad,
                            "Soru Sayısı": int(soru),
                            "Doğru": 0,
                            "Yanlış": 0,
                            "Boş": 0,
                        }
                        for d_ad, soru in ders_secenekleri
                    ]
                    duzenlenen = st.data_editor(
                        pd.DataFrame(varsayilan_satirlar),
                        key=(
                            "wiz_ders_editor_"
                            + sanitize_key(st.session_state.wiz_tur)
                            + "_"
                            + sanitize_key(
                                ders_secenekleri[0][0] if ders_secenekleri else "x"
                            )
                        ),
                        hide_index=True,
                        disabled=["Ders"],
                        column_config={
                            "Ders": st.column_config.TextColumn("Ders"),
                            "Soru Sayısı": st.column_config.NumberColumn(
                                "Soru Sayısı",
                                min_value=DERS_SONUC_MIN_SORU,
                                max_value=DERS_SONUC_MAKS_SORU,
                                step=1,
                                help="Dersin toplam soru sayısı",
                            ),
                            "Doğru": st.column_config.NumberColumn(
                                "Doğru", min_value=0, max_value=DERS_SONUC_MAKS_SORU, step=1
                            ),
                            "Yanlış": st.column_config.NumberColumn(
                                "Yanlış", min_value=0, max_value=DERS_SONUC_MAKS_SORU, step=1
                            ),
                            "Boş": st.column_config.NumberColumn(
                                "Boş", min_value=0, max_value=DERS_SONUC_MAKS_SORU, step=1
                            ),
                        },
                    )
                    for _, satir in duzenlenen.iterrows():
                        try:
                            kayit = ders_sonucu_dogrula(
                                satir.get("Ders"),
                                satir.get("Doğru"),
                                satir.get("Yanlış"),
                                satir.get("Boş"),
                                satir.get("Soru Sayısı"),
                            )
                        except ValueError as satir_hata:
                            ders_hatalari.append(str(satir_hata))
                            continue
                        if kayit["dogru"] + kayit["yanlis"] + kayit["bos"] == 0:
                            continue
                        ders_girdileri.append(kayit)
                    toplam_ders_neti = ders_toplam_neti(ders_girdileri)
                    olcu1, olcu2 = st.columns(2)
                    olcu1.metric(
                        "Derslerden Hesaplanan Toplam Net",
                        f"{toplam_ders_neti:.2f}",
                    )
                    olcu2.metric(
                        "Sonuç Girilen Ders",
                        f"{len(ders_girdileri)} / {len(ders_secenekleri)}",
                    )
                    if ders_girdileri:
                        st.caption(
                            "Ders netleri: "
                            + " • ".join(
                                f"{g['ders']} {g['net']:.2f}"
                                for g in ders_girdileri
                            )
                        )
                    for hata_metni in ders_hatalari:
                        st.error(f"⚠️ {hata_metni}")
                    st.session_state.wiz_net = toplam_ders_neti
                    st.session_state.wiz_ders_sonuclari = ders_girdileri
                else:
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
                    st.session_state.wiz_ders_sonuclari = []
        if st.button("İleri ➔ Ders Seçimine Geç", type="primary"):
            if not st.session_state.wiz_adi.strip():
                st.error("Lütfen denemenin adını giriniz!")
            elif ders_hatalari:
                st.error(
                    "Ders sonuçlarında hata var, lütfen düzeltiniz: "
                    + " | ".join(ders_hatalari)
                )
            elif (
                st.session_state.wiz_kategori == "Genel Deneme"
                and st.session_state.get("wiz_ders_modu") == "Ders Bazlı"
                and not st.session_state.wiz_ders_sonuclari
            ):
                st.error(
                    "Ders bazlı giriş seçtiniz ancak hiçbir derse sonuç"
                    " girmediniz. En az bir ders için doğru/yanlış girin ya da"
                    " 'Sadece Toplam Net' seçeneğine geçin."
                )
            elif st.session_state.wiz_kategori == "Branş Denemesi":
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
            # FAZ 2: Deneme başlığı + yanlış detayları TEK transaction'da ve
            # YALNIZCA BİR KEZ burada yazılır. (Eski akışta 4. adım her
            # rerun'unda yeniden INSERT ediyordu -> çift kayıt.)
            kayit_sonuc = {"deneme_id": None, "hata": None}
            try:
                with get_connection() as _conn:
                    kayit_sonuc["deneme_id"] = deneme_kaydet(
                        _conn,
                        ogrenci_id=current_user["id"],
                        deneme_adi=st.session_state.wiz_adi,
                        deneme_kategorisi=st.session_state.wiz_kategori,
                        deneme_turu=st.session_state.wiz_tur,
                        brans_dersi=st.session_state.wiz_brans_dersi,
                        net_bilgisi=float(st.session_state.wiz_net or 0.0),
                        tarih=st.session_state.wiz_tarih,
                        yanlislar=st.session_state.wiz_draft_mistakes,
                        ders_sonuclari=list(
                            st.session_state.get("wiz_ders_sonuclari") or []
                        ),
                    )
            except Exception as kayit_hatasi:
                kayit_sonuc["hata"] = str(kayit_hatasi)
            st.session_state.wiz_kayit_sonuc = kayit_sonuc
            if kayit_sonuc["hata"] is None:
                log_islem(
                    current_user["id"],
                    "FINISH_EXAM_ANALYSIS",
                    f"{st.session_state.wiz_adi}:"
                    f" {len(st.session_state.wiz_draft_mistakes)} yanlış"
                    f" kaydedildi (deneme_id={kayit_sonuc['deneme_id']}).",
                )
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
        kayit_sonuc = st.session_state.wiz_kayit_sonuc or {}
        drafts = st.session_state.wiz_draft_mistakes
        if kayit_sonuc.get("hata"):
            st.error(
                "❌ Deneme kaydı oluşturulamadı: " + str(kayit_sonuc["hata"])
            )
        else:
            st.markdown(
                '<div class="sim-card"><h3>🎉 Deneme Analiziniz'
                " Kaydedildi!</h3><p><b>"
                f"[{st.session_state.wiz_kategori}] {st.session_state.wiz_tur} -"
                f" {st.session_state.wiz_adi}"
                f" ({st.session_state.wiz_net} Net)</b>"
                " kaydı oluşturuldu.</p></div>",
                unsafe_allow_html=True,
            )
            st.caption(
                f"Deneme ID: {kayit_sonuc.get('deneme_id')} • Tarih:"
                f" {st.session_state.wiz_tarih}"
            )
            kaydedilen_dersler = list(
                st.session_state.get("wiz_ders_sonuclari") or []
            )
            if kaydedilen_dersler:
                st.caption(
                    f"Ders bazlı {len(kaydedilen_dersler)} sonuç kaydedildi: "
                    + " • ".join(
                        f"{d['ders']} {float(d['net']):.2f}"
                        for d in kaydedilen_dersler
                    )
                )
        if drafts:
            st.subheader("📌 Çalışma Listesine Eklenen Konular:")
            st.dataframe(pd.DataFrame(drafts), width="stretch")
        else:
            st.info(
                "Bu denemede yanlış konusu bulunmuyor. Deneme kaydı yine de"
                " oluşturuldu. Tebrikler!"
            )

        # FAZ 6B: toplu yanlış sayılarından bağımsız olarak, hatırlanan tek
        # tek soruların yanlış soru defterine hızlı eklenmesi.
        if drafts and not kayit_sonuc.get("hata"):
            with st.expander("📕 Bu denemenin yanlışlarını deftere ekle"):
                st.caption(
                    "Konu bazlı yanlış sayısı deneme analizinde tutulur. Burada"
                    " tek tek hatırladığınız soruları deftere işleyebilirsiniz;"
                    " tekrar zamanı gelen sorular programa görev olarak eklenir."
                )
                hizli_etiketler = [
                    "%s › %s" % (d["ders"], d["mikro"]) for d in drafts
                ]
                with st.form("defter_deneme_hizli_ekle"):
                    hizli_secim = st.selectbox(
                        "Konu", hizli_etiketler, key="wiz_defter_konu"
                    )
                    hizli_hata = st.selectbox(
                        "Hata türü",
                        wrong_questions.HATA_TURLERI,
                        key="wiz_defter_hata",
                    )
                    hizli_soru = st.text_area(
                        "Soru metni / kısa açıklama",
                        key="wiz_defter_soru",
                        height=80,
                    )
                    hizli_no = st.text_input(
                        "Soru numarası", key="wiz_defter_no"
                    )
                    if st.form_submit_button("📕 Deftere Ekle"):
                        hizli_draft = drafts[hizli_etiketler.index(hizli_secim)]
                        try:
                            hizli_kayit = wrong_questions.yanlis_soru_ekle(
                                current_user["id"],
                                hizli_draft["ders"],
                                hizli_draft["mikro"],
                                makro_konu=hizli_draft.get("makro"),
                                hata_turu=hizli_hata,
                                soru_metni=hizli_soru,
                                soru_no=hizli_no,
                                deneme_id=kayit_sonuc.get("deneme_id"),
                                deneme_tarihi=st.session_state.wiz_tarih,
                            )
                        except wrong_questions.YanlisSoruHatasi as hizli_hatasi:
                            st.error(str(hizli_hatasi))
                        else:
                            log_islem(
                                current_user["id"],
                                "WRONG_QUESTION_ADD",
                                "#%d %s › %s (deneme %s)"
                                % (
                                    hizli_kayit["id"],
                                    hizli_draft["ders"],
                                    hizli_draft["mikro"],
                                    kayit_sonuc.get("deneme_id"),
                                ),
                            )
                            set_flash_message(
                                "success",
                                "📕 Soru deftere eklendi (#%d)."
                                % hizli_kayit["id"],
                            )
                            st.rerun()

        if st.button("🚀 Yeni Deneme Ekle", type="primary"):
            st.session_state.wiz_step = 1
            st.session_state.wiz_draft_mistakes = []
            st.session_state.wiz_selected_dersler = []
            st.session_state.wiz_card_idx = 0
            st.session_state.wiz_show_details = False
            st.session_state.wiz_kayit_sonuc = None
            st.session_state.wiz_brans_dersi = ""
            st.session_state.wiz_brans_detay = None
            st.session_state.wiz_ders_sonuclari = []
            st.session_state.wiz_ders_modu = "Ders Bazlı"
            st.rerun()

    st.markdown("---")
    st.subheader("📊 Net Gelişim Grafikleri ve Filtreleme")

    # FAZ 2: Grafikler `denemeler` tablosundan, FAZ 3 ders bazlı seriler
    # `deneme_ders_sonuclari` tablosundan beslenir. Genel deneme (TYT / AYT),
    # genel denemenin ders netleri ve her branş denemesi AYRI seridir.
    with get_connection() as conn:
        df_denemeler = denemeleri_getir(conn, current_user["id"])
        df_ders_sonuclari = deneme_ders_sonuclari_getir(conn, current_user["id"])
        baglanmamis_adet = baglanmamis_yanlis_sayisi(conn, current_user["id"])

    if baglanmamis_adet:
        st.warning(
            f"⚠️ {baglanmamis_adet} eski yanlış kaydı bir deneme başlığına"
            " bağlanamadığı için grafik ve alarm hesaplarına dahil edilmedi."
            " Kayıtlar silinmedi; koçunuzla birlikte kontrol edebilirsiniz."
        )

    hedef_ayt_turu = "YDT" if current_user["hedef_alan"] == "Dil" else "AYT"

    grafik_tab1, grafik_tab2, grafik_tab3 = st.tabs(
        [
            "📈 TYT Denemeleri",
            f"📈 {hedef_ayt_turu} Denemeleri",
            "🔍 Hata Nedenleri",
        ],
        key="kt_deneme_grafik_tabs",
        on_change="rerun",
    )

    def _deneme_grafigi(df_kaynak, df_ders, sinav_turu, selectbox_key):
        """Tek bir seriyi (genel toplam / ders bazlı / branş) kronolojik çizer."""
        secenekler = grafik_seri_secenekleri(df_kaynak, sinav_turu, df_ders)
        if not secenekler:
            st.info(f"Henüz {sinav_turu} denemesi kaydı bulunmuyor.")
            return
        etiket = st.selectbox(
            "İncelenecek Seri:",
            [s["etiket"] for s in secenekler],
            key=selectbox_key,
        )
        secenek = next(
            (s for s in secenekler if s["etiket"] == etiket), secenekler[0]
        )
        if secenek.get("kaynak") == "ders":
            seri = ders_net_serisi(
                df_ders, sinav_turu, secenek["ders"], secenek["kategori"]
            )
            net_kolonu = "net"
        else:
            seri = seri_filtrele(
                df_kaynak, secenek["kategori"], secenek["brans_dersi"]
            )
            net_kolonu = "net_bilgisi"
        if seri is None or seri.empty:
            st.info("Bu seride gösterilecek deneme bulunamadı.")
            return
        grafik_df = seri[["tarih", net_kolonu]].rename(
            columns={net_kolonu: secenek["etiket"]}
        )
        st.line_chart(grafik_df.set_index("tarih"))

        # FAZ 3: özet metrikler. Yetersiz veride ortalama/gelişim gösterilmez.
        ozet = net_ozeti(seri[net_kolonu].tolist())
        olcu1, olcu2, olcu3, olcu4 = st.columns(4)
        olcu1.metric("Deneme Sayısı", ozet["adet"])
        olcu2.metric(
            "Son Net", "—" if ozet["son"] is None else f"{ozet['son']:.2f}"
        )
        olcu3.metric(
            "En Yüksek Net",
            "—" if ozet["en_yuksek"] is None else f"{ozet['en_yuksek']:.2f}",
        )
        olcu4.metric(
            "Son 3 Ortalama",
            "—"
            if ozet["son_uc_ortalama"] is None
            else f"{ozet['son_uc_ortalama']:.2f}",
        )
        if ozet["adet"] < 3:
            st.caption(
                "ℹ️ Son 3 deneme ortalaması için en az 3 deneme gerekir"
                f" (şu an {ozet['adet']})."
            )
        elif ozet["gelisim"] is None:
            st.caption(
                "ℹ️ Gelişim yorumu için en az 6 deneme gerekir"
                f" (şu an {ozet['adet']})."
            )
        else:
            yon = "▲" if ozet["gelisim"] >= 0 else "▼"
            st.caption(
                f"Gelişim: son 3 ortalama, önceki 3 ortalamaya göre"
                f" {yon} {abs(ozet['gelisim']):.2f} net."
            )
        st.caption(
            f"{len(seri)} deneme • X ekseni deneme tarihi • aynı adlı"
            " denemeler ayrı nokta olarak gösterilir."
        )
        with st.expander("📋 Grafik Noktaları (Tarih • Deneme Adı • Net)"):
            id_kolonu = "deneme_id" if secenek.get("kaynak") == "ders" else "id"
            tablo = seri[[id_kolonu, "tarih", "deneme_adi", net_kolonu]].copy()
            tablo.columns = ["Deneme ID", "Tarih", "Deneme Adı", "Net"]
            if secenek.get("kaynak") == "ders":
                tablo.insert(3, "Ders", secenek["ders"])
            st.dataframe(tablo, width="stretch", hide_index=True)

    # FAZ 3: ders bazlı performans özeti (genel denemeler).
    if df_ders_sonuclari is not None and not df_ders_sonuclari.empty:
        with st.expander("📚 Ders Bazlı Performans Özeti", expanded=False):
            ozet_satirlari = []
            for ozet_tur in ("TYT", hedef_ayt_turu):
                for ozet_ders in ders_seri_listesi(df_ders_sonuclari, ozet_tur):
                    alt_seri = ders_net_serisi(df_ders_sonuclari, ozet_tur, ozet_ders)
                    alt_ozet = net_ozeti(alt_seri["net"].tolist())
                    ozet_satirlari.append({
                        "Sınav": ozet_tur,
                        "Ders": ozet_ders,
                        "Deneme": alt_ozet["adet"],
                        "Son Net": alt_ozet["son"],
                        "Son 3 Ort.": alt_ozet["son_uc_ortalama"],
                        "En Yüksek": alt_ozet["en_yuksek"],
                    })
            if ozet_satirlari:
                st.dataframe(
                    pd.DataFrame(ozet_satirlari),
                    width="stretch",
                    hide_index=True,
                )
                st.caption(
                    "Ortalama ve gelişim yalnızca yeterli deneme sayısına"
                    " ulaşıldığında gösterilir."
                )
            else:
                st.info(
                    "Genel denemelerde ders bazlı sonuç bulunmuyor. Yeni"
                    " denemeleri ders bazlı girerek burada gelişimi"
                    " izleyebilirsiniz."
                )

    with grafik_tab1:
        _deneme_grafigi(df_denemeler, df_ders_sonuclari, "TYT", "kt_tyt_seri")

    with grafik_tab2:
        _deneme_grafigi(
            df_denemeler, df_ders_sonuclari, hedef_ayt_turu, "kt_ayt_seri"
        )

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
# TAB 4: YANLIŞ SORU DEFTERİ (FAZ 6B)
# ==============================================================================
def _defter_konu_ciftleri(ders):
    """Seçilen dersin (makro, mikro) çiftleri (müfredat hiyerarşisinden)."""
    makro_dict = aktif_mufredat_hiyerarsisi.get(ders) or {}
    ciftler = []
    if isinstance(makro_dict, dict):
        for makro, mikrolar in makro_dict.items():
            for mikro in mikrolar or []:
                ciftler.append((makro, mikro))
    return ciftler


def _defter_durum_etiketi(kayit):
    """Listede gösterilen durum etiketi (tekrar zamanı vurgulanır)."""
    if kayit.get("durum") not in wrong_questions.AKTIF_DURUMLAR:
        return kayit.get("durum") or "-"
    if kayit.get("gecikmis"):
        return "⏰ Gecikmiş"
    if kayit.get("bugun"):
        return "🔔 Bugün"
    return kayit.get("durum") or "-"


def _defter_kayit_metni(kayit):
    """Kaydın ayrıntı satırları (boş alanlar yazılmaz)."""
    satirlar = []
    konu = " › ".join(
        parca
        for parca in (
            kayit.get("makro_konu"),
            kayit.get("mikro_konu"),
            kayit.get("alt_konu"),
        )
        if parca
    )
    satirlar.append("**Konu:** %s" % konu)
    satirlar.append(
        "**Hata türü:** %s • **Tekrar:** %d kez"
        % (kayit.get("hata_turu") or "-", kayit.get("tekrar_sayisi") or 0)
    )
    if kayit.get("sonraki_tekrar_tarihi"):
        satirlar.append(
            "**Sonraki tekrar:** %s" % kayit["sonraki_tekrar_tarihi"]
        )
    if kayit.get("kaynak") or kayit.get("soru_no"):
        satirlar.append(
            "**Kaynak:** %s %s"
            % (kayit.get("kaynak") or "-", kayit.get("soru_no") or "")
        )
    if kayit.get("deneme_id"):
        satirlar.append("**Deneme:** #%s" % kayit["deneme_id"])
    if kayit.get("soru_metni"):
        satirlar.append("**Soru:** %s" % kayit["soru_metni"])
    if kayit.get("notlar"):
        satirlar.append("**Not:** %s" % kayit["notlar"])
    return "\n\n".join(satirlar)


with tab4:
    st.header("📕 Yanlış Soru Defteri")
    st.caption(
        "Denemede yanlış yaptığınız soruları tek tek kaydedin. Tekrar zamanı"
        " gelen sorular haftalık programa görev olarak eklenir; görevi"
        " tamamladığınızda tekrar sayacı otomatik ilerler."
    )

    defter_ozet = wrong_questions.yanlis_soru_ozeti(current_user["id"])
    olcu_a, olcu_b, olcu_c, olcu_d, olcu_e = st.columns(5)
    olcu_a.metric("Toplam Kayıt", defter_ozet["toplam"])
    olcu_b.metric("Bekleyen", defter_ozet["bekleyen"])
    olcu_c.metric("Bugün Tekrar", defter_ozet["bugun"])
    olcu_d.metric("Gecikmiş", defter_ozet["gecikmis"])
    olcu_e.metric("Öğrenildi", defter_ozet["ogrenildi"])

    with st.expander(
        "➕ Deftere Yanlış Soru Ekle", expanded=defter_ozet["toplam"] == 0
    ):
        defter_ders_listesi = list(aktif_mufredat_hiyerarsisi.keys())
        if not defter_ders_listesi:
            defter_ders_listesi = ["Genel"]
        with st.form("defter_soru_ekle_formu", clear_on_submit=False):
            yeni_ders = st.selectbox(
                "Ders", defter_ders_listesi, key="defter_ekle_ders"
            )
            yeni_ciftler = _defter_konu_ciftleri(yeni_ders)
            if yeni_ciftler:
                yeni_etiketler = [
                    "%s › %s" % (makro, mikro) for makro, mikro in yeni_ciftler
                ]
                yeni_secim = st.selectbox(
                    "Konu (makro › mikro)", yeni_etiketler, key="defter_ekle_konu"
                )
                yeni_makro, yeni_mikro = yeni_ciftler[
                    yeni_etiketler.index(yeni_secim)
                ]
            else:
                yeni_makro = st.text_input(
                    "Makro konu (opsiyonel)", key="defter_ekle_makro"
                )
                yeni_mikro = st.text_input("Mikro konu", key="defter_ekle_mikro")
            yeni_alt_listesi = MIKRO_ALT_KONULAR.get(yeni_mikro) or []
            yeni_alt = st.selectbox(
                "Alt başlık (opsiyonel)",
                ["-"] + list(yeni_alt_listesi),
                key="defter_ekle_alt",
            )
            yeni_hata = st.selectbox(
                "Hata türü", wrong_questions.HATA_TURLERI, key="defter_ekle_hata"
            )
            yeni_soru = st.text_area(
                "Soru metni / kısa açıklama", key="defter_ekle_soru", height=90
            )
            yeni_kaynak = st.text_input(
                "Kaynak (deneme adı / kitap)", key="defter_ekle_kaynak"
            )
            yeni_soru_no = st.text_input("Soru numarası", key="defter_ekle_no")
            yeni_not = st.text_area(
                "Kendi notunuz", key="defter_ekle_not", height=70
            )
            if st.form_submit_button("📕 Deftere Kaydet", type="primary"):
                try:
                    yeni_kayit = wrong_questions.yanlis_soru_ekle(
                        current_user["id"],
                        yeni_ders,
                        yeni_mikro,
                        makro_konu=yeni_makro,
                        alt_konu=None if yeni_alt == "-" else yeni_alt,
                        hata_turu=yeni_hata,
                        soru_metni=yeni_soru,
                        kaynak=yeni_kaynak,
                        soru_no=yeni_soru_no,
                        notlar=yeni_not,
                    )
                except wrong_questions.YanlisSoruHatasi as defter_hatasi:
                    st.error(str(defter_hatasi))
                else:
                    log_islem(
                        current_user["id"],
                        "WRONG_QUESTION_ADD",
                        "#%d %s › %s" % (yeni_kayit["id"], yeni_ders, yeni_mikro),
                    )
                    set_flash_message(
                        "success",
                        "📕 Soru deftere eklendi (#%d)." % yeni_kayit["id"],
                    )
                    st.rerun()

    st.markdown("---")
    st.subheader("📋 Defter Kayıtları")
    defter_kayitlar = wrong_questions.yanlis_sorulari_getir(current_user["id"])
    if not defter_kayitlar:
        st.info(
            "Defter henüz boş. Deneme Analizi sekmesinden veya yukarıdaki"
            " formdan yanlış soru ekleyebilirsiniz."
        )
    else:
        filtre_a, filtre_b, filtre_c = st.columns([1, 1, 2])
        defter_dersleri = ["Tümü"] + sorted({k["ders"] for k in defter_kayitlar})
        ders_filtre = filtre_a.selectbox(
            "Ders", defter_dersleri, key="defter_filtre_ders"
        )
        durum_filtre = filtre_b.selectbox(
            "Durum",
            ["Aktif (bekleyen)", "Tümü"] + list(wrong_questions.DURUMLAR),
            key="defter_filtre_durum",
        )
        arama_filtre = filtre_c.text_input(
            "Ara (ders / konu / soru / not)", key="defter_filtre_arama"
        )

        gosterilen = 0
        for kayit in defter_kayitlar:
            if ders_filtre != "Tümü" and kayit["ders"] != ders_filtre:
                continue
            if durum_filtre == "Aktif (bekleyen)":
                if not kayit["bekliyor"]:
                    continue
            elif durum_filtre != "Tümü" and kayit["durum"] != durum_filtre:
                continue
            if arama_filtre.strip():
                havuz_metni = " ".join(
                    str(kayit.get(alan) or "")
                    for alan in (
                        "ders",
                        "makro_konu",
                        "mikro_konu",
                        "alt_konu",
                        "soru_metni",
                        "notlar",
                        "kaynak",
                    )
                ).lower()
                if arama_filtre.strip().lower() not in havuz_metni:
                    continue
            gosterilen += 1
            baslik = "#%d • %s › %s • %s" % (
                kayit["id"],
                kayit["ders"],
                kayit["mikro_konu"],
                _defter_durum_etiketi(kayit),
            )
            with st.expander(baslik):
                st.markdown(_defter_kayit_metni(kayit))
                but_a, but_b, but_c = st.columns(3)
                if kayit["durum"] in wrong_questions.AKTIF_DURUMLAR:
                    if but_a.button(
                        "✅ Çözdüm (öğrenildi)",
                        key="defter_coz_%d" % kayit["id"],
                    ):
                        wrong_questions.tekrar_sonucu_kaydet(
                            kayit["id"], True, ogrenci_id=current_user["id"]
                        )
                        log_islem(
                            current_user["id"],
                            "WRONG_QUESTION_SOLVED",
                            "#%d" % kayit["id"],
                        )
                        set_flash_message(
                            "success",
                            "✅ Soru öğrenildi olarak işaretlendi (#%d)."
                            % kayit["id"],
                        )
                        st.rerun()
                    if but_b.button(
                        "🔁 Yine yapamadım",
                        key="defter_yapamadi_%d" % kayit["id"],
                    ):
                        sonuc = wrong_questions.tekrar_sonucu_kaydet(
                            kayit["id"], False, ogrenci_id=current_user["id"]
                        )
                        set_flash_message(
                            "info",
                            "🔁 Soru yeniden havuza döndü; sonraki tekrar %s."
                            % (sonuc.get("sonraki_tekrar_tarihi") or "-"),
                        )
                        st.rerun()
                elif kayit["durum"] == wrong_questions.DURUM_OGRENILDI:
                    if but_a.button(
                        "↩️ Yeniden aç", key="defter_ac_%d" % kayit["id"]
                    ):
                        wrong_questions.yeniden_ac(
                            kayit["id"], ogrenci_id=current_user["id"]
                        )
                        set_flash_message(
                            "info", "Soru yeniden açıldı (#%d)." % kayit["id"]
                        )
                        st.rerun()
                else:
                    if but_a.button(
                        "📤 Arşivden çıkar", key="defter_cikar_%d" % kayit["id"]
                    ):
                        wrong_questions.arsivden_cikar(
                            kayit["id"], ogrenci_id=current_user["id"]
                        )
                        set_flash_message(
                            "info", "Soru arşivden çıkarıldı (#%d)." % kayit["id"]
                        )
                        st.rerun()
                if kayit["durum"] != wrong_questions.DURUM_ARSIV:
                    if but_c.button(
                        "🗄️ Arşivle", key="defter_arsiv_%d" % kayit["id"]
                    ):
                        wrong_questions.arsivle(
                            kayit["id"], ogrenci_id=current_user["id"]
                        )
                        log_islem(
                            current_user["id"],
                            "WRONG_QUESTION_ARCHIVE",
                            "#%d" % kayit["id"],
                        )
                        set_flash_message(
                            "info", "Soru arşivlendi (#%d)." % kayit["id"]
                        )
                        st.rerun()
                if kayit["durum"] != wrong_questions.DURUM_ARSIV:
                    with st.form("defter_not_formu_%d" % kayit["id"]):
                        guncel_not = st.text_area(
                            "Not",
                            value=kayit.get("notlar") or "",
                            key="defter_not_%d" % kayit["id"],
                        )
                        if st.form_submit_button("💾 Notu Kaydet"):
                            try:
                                wrong_questions.yanlis_soru_guncelle(
                                    kayit["id"],
                                    ogrenci_id=current_user["id"],
                                    notlar=guncel_not,
                                )
                            except wrong_questions.YanlisSoruHatasi as not_hatasi:
                                st.error(str(not_hatasi))
                            else:
                                set_flash_message(
                                    "success",
                                    "Not güncellendi (#%d)." % kayit["id"],
                                )
                                st.rerun()

        if gosterilen == 0:
            st.info("Filtrelere uyan defter kaydı bulunamadı.")

# ==============================================================================
# TAB 5: AKILLI ALARMLAR VE MONETIZATION CALL TO ACTION (CTA)
# ==============================================================================
with tab5:
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
# TAB 6: HAFTALIK ÇALIŞMA PROGRAMI (ÖN KOŞUL KİLİTLİ ALGORİTMA & MİKRO SÜRE HESABI)
# ==============================================================================
with tab6:
    st.header("📅 Haftalık Çalışma Programı Motoru (Ultra-Think)")
    col_p1, col_p2 = st.columns([1, 1])

    with col_p1:
        st.subheader("⚙️ Program Oluşturma Ayarları")
        # FAZ 5C: haftanın her günü için ayrı müsaitlik (0 = dinlenme günü).
        kayitli_musaitlik = planner.musaitlik_yukle(current_user["id"])
        musaitlik_saat = {}
        with st.expander("🗓️ Haftalık müsaitlik (saat)", expanded=True):
            st.caption(
                "Her gün için ayırabileceğin süreyi seç. **0 saat = dinlenme"
                " günü.** Bu tercihler kaydedilir ve yeni programlarda tekrar"
                " sorulmaz."
            )
            gun_kolonlari = st.columns(4)
            for gun_no, gun_adi in enumerate(GUN_ADLARI_LISTE, start=1):
                with gun_kolonlari[(gun_no - 1) % 4]:
                    musaitlik_saat[gun_no] = st.number_input(
                        gun_adi,
                        min_value=0,
                        max_value=12,
                        value=int(round(kayitli_musaitlik.get(gun_no, 360) / 60)),
                        step=1,
                        key=f"musaitlik_saat_{gun_no}",
                        help="%s günü kaç saat çalışabilirsin?" % gun_adi,
                    )
            if st.button("💾 Müsaitliği kaydet", key="musaitlik_kaydet_btn"):
                try:
                    planner.musaitlik_kaydet(
                        current_user["id"],
                        {gun: int(saat) * 60 for gun, saat in musaitlik_saat.items()},
                    )
                except planner.PlanHatasi as hata:
                    st.error("⚠️ %s" % hata)
                else:
                    set_flash_message("success", "🗓️ Haftalık müsaitlik kaydedildi.")
                    st.rerun()

        gunluk_saat = int(round(sum(musaitlik_saat.values()) / 7.0))
        gunluk_saat = max(1, min(12, gunluk_saat or 6))
        st.caption(
            "Haftalık ortalama: **%d saat/gün** · Toplam: **%d saat**"
            % (gunluk_saat, sum(musaitlik_saat.values()))
        )

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
                # FAZ 5A: eski program/görevler SİLİNMEZ. Yeni program ayrı bir
                # sürüm olarak eklenir; eskisi arşivlenir (tek transaction).
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

                gorevler, motor_adi, uyarilar = haftalik_program_gorevleri_uret(
                    current_user["id"],
                    aktif_mufredat_hiyerarsisi,
                    alarmlar_db,
                    ana_gorev_blok_sayisi,
                    blok_basi_soru_bütcesi,
                    günlük_paragraf_hedef,
                    gunler,
                    filtered_pekistirme,
                    filtered_ezber,
                    plan_baglami=planlama_baglami_olustur(
                        current_user["id"],
                        aktif_mufredat_hiyerarsisi,
                        alarmlar_db,
                        paragraf_soru=günlük_paragraf_hedef,
                    ),
                )

            # FAZ 5A: program TEK transaction'da yazılır ve hiçbir görev silinmez.
            # Motor hata verse bile eski program/görevler/oturumlar korunur.
            baslangic_tarih = get_tr_now().strftime("%Y-%m-%d")
            bitis_tarih = (get_tr_now() + timedelta(days=6)).strftime("%Y-%m-%d")
            try:
                yeni_program = program_service.program_olustur(
                    current_user["id"],
                    baslangic_tarih,
                    bitis_tarih,
                    gorevler,
                    gunluk_hedef_dakika=toplam_gunluk_dakika,
                    program_notu=motor_adi,
                )
            except program_service.ProgramHatasi as program_hata:
                set_flash_message(
                    "error",
                    "Program oluşturulamadı: %s Mevcut programınız, eski"
                    " görevleriniz ve çalışma kayıtlarınız korunuyor."
                    % program_hata,
                )
                st.rerun()
            else:
                plan_soru = sum(
                    int(g.get("hedef_soru") or 0)
                    for g in gorevler
                    if g.get("pedagoji_turu") != "Tekrar"
                )
                try:
                    with get_connection() as kayit_conn:
                        kayit_conn.execute(
                            "INSERT INTO ogrenci_hiz_gecmisi (ogrenci_id, tarih,"
                            " planlanan_gorev, planlanan_soru, kullanilan_katsayi)"
                            " VALUES (?, ?, ?, ?, ?)",
                            (
                                current_user["id"],
                                baslangic_tarih,
                                len(gorevler),
                                plan_soru,
                                hesapla_hiz_katsayisi(current_user["id"]),
                            ),
                        )
                        kayit_conn.commit()
                except Exception:
                    pass
                log_islem(
                    current_user["id"],
                    "CREATE_PROGRAM",
                    "Haftalık program oluşturuldu (#%s, %s, %s görev)."
                    % (yeni_program["id"], motor_adi, len(gorevler)),
                )
                uyari_metni = (" " + " ".join(uyarilar)) if uyarilar else ""
                set_flash_message(
                    "success",
                    "🎉 Haftalık programınız oluşturuldu (#%s). Toplam %s görev"
                    " planlandı.%s" % (yeni_program["id"], len(gorevler), uyari_metni),
                )
                if uyarilar:
                    set_flash_message("warning", uyari_metni.strip())
                st.rerun()

    with col_p2:
        st.subheader("🎯 YKS Puan ve Sıralama Simülatörü")
        st.info(
            "Simülatör kendi sekmesine taşındı: **🎯 YKS Simülatörü**.\n\n"
            "Orada son denemelerinizden veya manuel girişten netlerinizi\n"
            "kullanarak model puanınızı, hedef net karşılaştırmanızı ve\n"
            "(doğrulanmış veri varsa) sıralama tahmininizi görebilirsiniz."
        )
        st.caption(
            "Eski sürümdeki sabit sıralama tabloları kaldırıldı: kaynağı\n"
            "doğrulanmamış sıralama sayıları gösterilmiyor."
        )

    st.markdown("---")
    _onceki_programlar_bolumu(current_user["id"])
    st.subheader("📋 7 Günlük Genel Çalışma Çizelgesi")
    # FAZ 5A: çizelge yalnızca AKTİF programın görevlerini gösterir (aktif
    # program yoksa program bağlantısı olmayan eski kayıtlar gösterilir).
    df_program_full = pd.DataFrame(
        program_service.gorunur_gorevler(current_user["id"]),
        columns=[
            "id",
            "gun",
            "ders",
            "makro_konu",
            "mikro_konu",
            "gorev_tanimi",
            "hedef_soru",
            "tahmini_sure_dk",
            "pedagoji_turu",
            "durum",
            "tarih",
            "program_id",
        ],
    )

    if not df_program_full.empty:
        # FAZ 5B: tamamlanma alt adımlardan türetilir (soru adımları gerçek
        # çalışma kayıtlarından gelir).
        hafta_adimlari = {
            int(satir["id"]): _gorev_adimlari_senkron(int(satir["id"]), satir["durum"])
            for _, satir in df_program_full.iterrows()
        }
        biten_gorev = 0
        for _, satir in df_program_full.iterrows():
            adimlar = hafta_adimlari.get(int(satir["id"])) or []
            bitti = all(a["tamam"] for a in adimlar) if adimlar else bool(satir["durum"])
            biten_gorev += 1 if bitti else 0
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
        gun_tablari = st.tabs(
            gun_listesi,
            key="kt_program_gun_tabs",
            on_change="rerun",
        )

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
                            sure_dk = row.get("tahmini_sure_dk")
                            if pd.notna(sure_dk) and int(sure_dk or 0) > 0:
                                st.caption(
                                    "⏱️ " + task_steps.sure_metni(int(sure_dk))
                                )
                        with col_g2:
                            prog_adimlar = hafta_adimlari.get(int(row["id"])) or []
                            is_t = (
                                all(a["tamam"] for a in prog_adimlar)
                                if prog_adimlar
                                else bool(row["durum"])
                            )
                            if prog_adimlar:
                                # Soru adımları gerçek oturumlardan geldiği için
                                # bu görevler elle işaretlenmez.
                                ilerleme = task_steps.gorev_ilerleme(int(row["id"]))
                                st.caption(
                                    "✅ Tamamlandı"
                                    if is_t
                                    else "⏳ %d/%d adım"
                                    % (
                                        ilerleme["tamamlanan_adim"],
                                        ilerleme["adim_sayisi"],
                                    )
                                )
                            else:
                                prog_anahtar = f"prog_chk_{row['id']}"
                                # FAZ 4: iki sekme arasındaki checkbox değeri
                                # çakışmasını (sonsuz rerun) önler.
                                gorev_chk_durum_senkron(prog_anahtar, is_t)
                                chk_g = st.checkbox(
                                    "Tamamlandı",
                                    key=prog_anahtar,
                                )
                                if chk_g != is_t:
                                    with get_connection() as conn:
                                        # FAZ 4: planlanan soru ilerlemeye eklenmez.
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
# TAB 7: ÖZEL DERS & RAPORLAR
# ==============================================================================
with tab7:
    st.header("🤝 Özel Ders Talepleri & Çalışma Raporları")
    
    rep_tab1, rep_tab2 = st.tabs(
        [
            "🛒 Özel Ders Taleplerim",
            "📊 Detaylı Performans & İletişim Logları",
        ],
        key="kt_rapor_tabs",
        on_change="rerun",
    )
    
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


# ==============================================================================
# TAB 8: HAFTALIK PERFORMANS MERKEZİ (FAZ 7)
# ==============================================================================
# Rapor anlık görüntü (snapshot) ALMAZ; her açılışta canlı veriden üretilir.
# Hafta = Pazartesi–Pazar (TR). Devam eden hafta, geçen haftanın AYNI
# uzunluktaki dönemiyle karşılaştırılır (Pzt–Çar vs Pzt–Çar).
def _hafta_yuzde_metni(deger):
    """25.0 -> '%25', 33.33 -> '%33.3', None -> '—'."""
    if deger is None:
        return "—"
    try:
        metin = ("%.1f" % float(deger)).rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "—"
    return "%" + metin


def _hafta_deger_metni(alan, deger):
    """Karşılaştırma tablosu için okunur değer metni."""
    if deger is None:
        return "—"
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        return str(deger)
    if alan == "dk":
        return weekly_report.sure_metni(sayi)
    if alan == "deneme_net":
        return "%.2f" % sayi
    if alan == "uyum":
        return _hafta_yuzde_metni(sayi)
    if abs(sayi - round(sayi)) < 0.001:
        return "%d" % int(round(sayi))
    return "%.1f" % sayi


def _hafta_fark_metni(alan, fark, birim=""):
    """Sayısal değişimin işaretli metni ('+45 dk', '−2 soru')."""
    if fark is None:
        return "—"
    try:
        fark = float(fark)
    except (TypeError, ValueError):
        return "—"
    if abs(fark) < 0.005:
        return "değişim yok"
    isaret = "+" if fark > 0 else "−"
    mutlak = abs(fark)
    if alan == "dk":
        return isaret + weekly_report.sure_metni(mutlak)
    if alan == "deneme_net":
        return "%s%.2f net" % (isaret, mutlak)
    if abs(mutlak - round(mutlak)) < 0.001:
        return "%s%d %s" % (isaret, int(round(mutlak)), birim)
    return "%s%.1f %s" % (isaret, mutlak, birim)


with tab8:
    st.header("📈 Haftalık Performans Merkezi")
    st.caption(
        "Rapor her açılışta canlı veriden üretilir (ayrı kopya saklanmaz)."
        " Hafta Pazartesi–Pazar'dır. Devam eden hafta, geçen haftanın aynı"
        " uzunluktaki dönemiyle karşılaştırılır; gelecek haftalarda"
        " karşılaştırma yapılmaz."
    )

    hafta_secenekleri = weekly_report.hafta_secenekleri(12)
    hafta_etiketleri = [
        ("%s  ·  bu hafta" % s["etiket"]) if s["bu_hafta"] else s["etiket"]
        for s in hafta_secenekleri
    ]
    secilen_hafta_etiketi = st.selectbox(
        "Rapor haftası", hafta_etiketleri, key="hafta_perf_hafta_secimi"
    )
    secilen_hafta = hafta_secenekleri[
        hafta_etiketleri.index(secilen_hafta_etiketi)
    ]

    hafta_raporu = None
    try:
        hafta_raporu = weekly_report.rapor_uret(
            current_user["id"], secilen_hafta["baslangic"]
        )
    except weekly_report.HaftalikRaporHatasi as rapor_hatasi:
        st.error("Haftalık rapor üretilemedi: %s" % rapor_hatasi)

    if hafta_raporu is not None:
        hafta_bilgi = hafta_raporu["hafta"]
        hafta_ozet = hafta_raporu["ozet"]
        hafta_kars = hafta_raporu["karsilastirma"]
        fark_haritasi = {a["alan"]: a for a in hafta_kars["alanlar"]}

        def _metrik_delta(alan):
            kayit = fark_haritasi.get(alan)
            if not kayit:
                return None
            return _hafta_fark_metni(alan, kayit["fark"], kayit["birim"])

        st.subheader("🗓️ %s" % hafta_bilgi["etiket"])
        st.caption(
            "%s · Ölçülen gün: %d/%d · Karşılaştırma: %s"
            % (
                hafta_bilgi["durum_metni"],
                hafta_bilgi["olculen_gun"],
                hafta_bilgi["toplam_gun"],
                (
                    "geçen haftanın aynı dönemi"
                    if hafta_kars["donem"] == "esit_uzunluk"
                    else "geçen hafta"
                ),
            )
        )
        if hafta_bilgi["gelecek"]:
            st.info(
                "Bu hafta henüz başlamadı; performans sayıları hafta"
                " başlayınca oluşur. Aşağıdan hedeflerinizi önceden"
                " planlayabilirsiniz."
            )

        olcu_a, olcu_b, olcu_c, olcu_d, olcu_e = st.columns(5)
        olcu_a.metric(
            "Çalışma süresi",
            weekly_report.sure_metni(hafta_ozet["dk"]),
            delta=_metrik_delta("dk"),
        )
        olcu_b.metric(
            "Çözülen soru", hafta_ozet["soru"], delta=_metrik_delta("soru")
        )
        olcu_c.metric(
            "Aktif gün",
            "%d / 7" % hafta_ozet["aktif_gun"],
            delta=_metrik_delta("aktif_gun"),
        )
        olcu_d.metric(
            "Program uyumu",
            _hafta_deger_metni("uyum", hafta_ozet["uyum"]),
            delta=_metrik_delta("uyum"),
        )
        olcu_e.metric(
            "Deneme neti",
            _hafta_deger_metni("deneme_net", hafta_ozet["deneme_net"]),
            delta=_metrik_delta("deneme_net"),
        )

        olcu_f, olcu_g, olcu_h = st.columns(3)
        olcu_f.metric(
            "Tamamlanan görev",
            "%d / %d" % (
                hafta_ozet["tamamlanan_gorev"],
                hafta_ozet["planlanan_gorev"],
            ),
        )
        olcu_g.metric(
            "Tamamlanan tekrar",
            "%d / %d" % (
                hafta_ozet["tamamlanan_tekrar"],
                hafta_ozet["tekrar_planlanan"],
            ),
            delta=_metrik_delta("tamamlanan_tekrar"),
        )
        olcu_h.metric(
            "Defterde bekleyen yanlış",
            hafta_ozet["bekleyen_yanlis"],
            delta=_metrik_delta("bekleyen_yanlis"),
        )

        st.markdown("---")
        st.subheader("🔁 Önceki Dönemle Karşılaştırma")
        if not hafta_kars["kullanilabilir"]:
            if hafta_bilgi["gelecek"]:
                st.info("Gelecek haftalar için karşılaştırma yapılmaz.")
            elif not hafta_kars["onceki_veri_var"]:
                st.info(
                    "Önceki dönemde hiç kayıt bulunmadığı için karşılaştırma"
                    " üretilmedi: 'kayıt yok' ile 'kayıtlı sıfır' aynı şey"
                    " değildir."
                )
            else:
                st.info(
                    "Karşılaştırma için bu dönemde de en az bir kayıt"
                    " gerekiyor."
                )
        else:
            kars_df = pd.DataFrame(
                [
                    {
                        "Metrik": a["etiket"],
                        "Bu dönem": _hafta_deger_metni(
                            a["alan"], a["gercek"]
                        ),
                        "Önceki dönem": _hafta_deger_metni(
                            a["alan"], a["onceki"]
                        ),
                        "Fark": _hafta_fark_metni(
                            a["alan"], a["fark"], a["birim"]
                        ),
                        "Değişim %": (
                            "—" if a["yuzde"] is None
                            else "%+.1f%%" % a["yuzde"]
                        ),
                    }
                    for a in hafta_kars["alanlar"]
                ]
            )
            st.dataframe(kars_df, width="stretch", hide_index=True)

        # ------------------------------------------------------------------
        # HEDEFLER
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("🎯 Haftalık Hedefler")
        hedef_ozet = hafta_raporu["hedefler"]["ozet"]
        hedef_kartlari = hafta_raporu["hedefler"]["ilerleme"]
        if hedef_ozet["adet"]:
            st.caption(
                "Hedef: %d · Tamamlanan: %d · Yaklaşan: %d · Devam eden:"
                " %d · Veri bekleyen: %d · Ortalama gerçekleşme: %s"
                % (
                    hedef_ozet["adet"],
                    hedef_ozet["tamamlanan"],
                    hedef_ozet["yaklasan"],
                    hedef_ozet["devam"],
                    hedef_ozet["veri_bekleyen"],
                    _hafta_yuzde_metni(hedef_ozet["ortalama_oran"]),
                )
            )
            for kart in hedef_kartlari:
                hedef_sol, hedef_sag = st.columns([6, 1])
                with hedef_sol:
                    st.markdown(
                        "**%s** · %s" % (kart["etiket"], kart["durum"])
                    )
                    st.caption(
                        "Hedef: %s · Gerçekleşen: %s · Kalan: %s"
                        % (
                            kart["hedef_metin"],
                            kart["gercek_metin"],
                            kart["kalan_metin"],
                        )
                    )
                    if kart["oran"] is not None:
                        st.progress(
                            max(0.0, min(1.0, kart["oran"] / 100.0)),
                            text=_hafta_yuzde_metni(kart["oran_ham"]),
                        )
                    else:
                        st.caption("Bu hedef için henüz veri yok.")
                with hedef_sag:
                    if st.button(
                        "🗑️",
                        key="hafta_hedef_sil_%d" % kart["id"],
                        help="Hedefi sil",
                    ):
                        if weekly_report.hedef_sil(
                            kart["id"], current_user["id"]
                        ):
                            set_flash_message(
                                "success",
                                "'%s' hedefi silindi." % kart["etiket"],
                            )
                        st.rerun()
        else:
            st.info(
                "Bu hafta için henüz hedef tanımlanmadı. Aşağıdaki formdan"
                " ekleyebilir veya geçen haftanın hedeflerini"
                " kopyalayabilirsiniz."
            )


        hedef_ders_secenekleri = sorted(
            set(aktif_mufredat_hiyerarsisi.keys())
            | {
                d["ders"]
                for d in (hafta_raporu["dersler"] or [])
                if d.get("ders")
            }
        )
        if not hedef_ders_secenekleri:
            hedef_ders_secenekleri = ["Genel"]

        with st.expander(
            "➕ Hedef ekle / güncelle", expanded=not hedef_kartlari
        ):
            with st.form("hafta_hedef_formu"):
                hedef_tur_etiketleri = [
                    t["etiket"] for t in weekly_report.HEDEF_TURLERI.values()
                ]
                hedef_tur_kodlari = list(weekly_report.HEDEF_TURLERI.keys())
                secilen_tur_etiketi = st.selectbox(
                    "Hedef türü",
                    hedef_tur_etiketleri,
                    key="hafta_hedef_tur",
                )
                hedef_tur = hedef_tur_kodlari[
                    hedef_tur_etiketleri.index(secilen_tur_etiketi)
                ]
                hedef_tanimi = weekly_report.HEDEF_TURLERI[hedef_tur]
                hedef_ders = ""
                if hedef_tanimi["ders_gerekli"]:
                    hedef_ders = st.selectbox(
                        "Ders",
                        hedef_ders_secenekleri,
                        key="hafta_hedef_ders",
                    )
                # Süre hedefleri saat olarak girilir; servis dakika bekler.
                saat_cinsinden = hedef_tanimi["birim"] == "dk"
                birim_metni = (
                    "saat" if saat_cinsinden else hedef_tanimi["birim"]
                )
                maks_girdi = (
                    float(hedef_tanimi["maks"]) / 60.0
                    if saat_cinsinden
                    else float(hedef_tanimi["maks"])
                )
                hedef_deger_girdisi = st.number_input(
                    "Hedef değer (%s)" % birim_metni,
                    min_value=0.0,
                    max_value=maks_girdi,
                    value=1.0,
                    step=0.5 if saat_cinsinden else 1.0,
                    key="hafta_hedef_deger",
                )
                st.caption(
                    "Aynı hafta + hedef türü + ders için tek kayıt tutulur;"
                    " yeniden kaydetmek değeri günceller."
                )
                if st.form_submit_button(
                    "💾 Hedefi Kaydet", type="primary"
                ):
                    hedef_degeri = (
                        round(hedef_deger_girdisi * 60.0, 1)
                        if saat_cinsinden
                        else hedef_deger_girdisi
                    )
                    try:
                        weekly_report.hedef_kaydet(
                            current_user["id"],
                            secilen_hafta["baslangic"],
                            hedef_tur,
                            hedef_degeri,
                            ders=hedef_ders or None,
                        )
                    except weekly_report.HaftalikRaporHatasi as hedef_hatasi:
                        st.error(
                            "Hedef kaydedilemedi: %s" % hedef_hatasi
                        )
                    else:
                        log_islem(
                            current_user["id"],
                            "WEEKLY_GOAL_SAVE",
                            "%s = %s (%s)"
                            % (
                                secilen_tur_etiketi,
                                hedef_deger_girdisi,
                                birim_metni,
                            ),
                        )
                        set_flash_message(
                            "success",
                            "'%s' hedefi %s haftası için kaydedildi."
                            % (secilen_tur_etiketi, hafta_bilgi["kisa"]),
                        )
                        st.rerun()

        if st.button(
            "📋 Geçen haftanın hedeflerini bu haftaya kopyala",
            key="hafta_hedef_kopyala",
        ):
            try:
                kopya = weekly_report.hedefleri_kopyala(
                    current_user["id"],
                    weekly_report.onceki_hafta(
                        secilen_hafta["baslangic"]
                    ),
                    secilen_hafta["baslangic"],
                )
            except weekly_report.HaftalikRaporHatasi as kopya_hatasi:
                st.error("Hedefler kopyalanamadı: %s" % kopya_hatasi)
            else:
                if kopya["kopyalanan"]:
                    set_flash_message(
                        "success",
                        "%d hedef kopyalandı (kaynak hafta: %s)."
                        % (kopya["kopyalanan"], kopya["kaynak_hafta"]),
                    )
                else:
                    set_flash_message(
                        "info",
                        "Kopyalanacak yeni hedef yok; bu haftanın hedefleri"
                        " güncel.",
                    )
                st.rerun()


        # ------------------------------------------------------------------
        # DERS BAZLI DAĞILIM
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("📚 Ders Bazlı Dağılım")
        if not hafta_raporu["dersler"]:
            st.info("Bu hafta ders bazlı çalışma/deneme kaydı bulunmuyor.")
        else:
            ders_df = pd.DataFrame(
                [
                    {
                        "Ders": d["ders"],
                        "Süre (dk)": d["dk"],
                        "Soru": d["soru"],
                        "Soru/saat": d["soru_saat"],
                        "Oturum": d["oturum"],
                        "Doğru": d["dogru"],
                        "Yanlış": d["yanlis"],
                        "Başarı %": d["basari_orani"],
                        "Tamamlanan görev": d["gorev_tamam"],
                        "Mikro konu": d["mikro_sayisi"],
                        "Deneme neti": d["deneme_net_ort"],
                    }
                    for d in hafta_raporu["dersler"]
                ]
            )
            st.dataframe(ders_df, width="stretch", hide_index=True)
            sure_df = pd.DataFrame(
                [
                    {"Ders": d["ders"], "Süre (dk)": d["dk"]}
                    for d in hafta_raporu["dersler"]
                    if d["dk"]
                ]
            )
            if not sure_df.empty:
                st.bar_chart(sure_df.set_index("Ders")["Süre (dk)"])
            else:
                st.caption("Süre kaydı bulunmadığı için süre grafiği yok.")

        # ------------------------------------------------------------------
        # MİKRO KONU TAKİBİ
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("🔬 Mikro Konu Takibi")
        mikro_ozet = hafta_raporu["mikro"] or {}
        if not mikro_ozet.get("veri_var"):
            st.info("Bu hafta mikro konu bazlı kayıt bulunmuyor.")
        else:
            st.caption(
                "Çalışılan mikro konu: %d · Öğrenme adımları tamam: %d ·"
                " Soru hedefine ulaşan: %d · Uygulamada 'Biliyorum'"
                " beyanı: %d"
                % (
                    mikro_ozet["calisilan_mikro_sayisi"],
                    len(mikro_ozet["tamamlanan"]),
                    len(mikro_ozet["hedefe_ulasan"]),
                    mikro_ozet["beyan_ogrenildi"],
                )
            )
            st.caption(mikro_ozet["beyan_notu"])
            if mikro_ozet["calisilan"]:
                mikro_df = pd.DataFrame(
                    [
                        {
                            "Ders": k["ders"],
                            "Makro konu": k["makro_konu"],
                            "Mikro konu": k["mikro_konu"],
                            "Alt başlık": k["alt_konu"] or "",
                            "Süre (dk)": k["dk"],
                            "Soru": k["soru"],
                            "Gün": k["gun_sayisi"],
                            "Öğrenme": "✔" if k["ogrenme_tamam"] else "",
                            "Hedef soru": k["hedef_soru"],
                            "Çözülen soru": k["cozulen_soru"],
                        }
                        for k in mikro_ozet["calisilan"][:25]
                    ]
                )
                st.dataframe(mikro_df, width="stretch", hide_index=True)
                st.caption(
                    "Haftalık soru ile konunun TOPLAM çözülen sorusu ayrı"
                    " sütunlardadır; 'Soru' yalnızca bu haftanın sayısıdır."
                )
            else:
                st.info("Bu hafta çalışılmış mikro konu kaydı yok.")

            if mikro_ozet["bekleyen_konular"]:
                with st.expander("⏳ Soru hedefi tamamlanmayan konular"):
                    bekleyen_df = pd.DataFrame(
                        [
                            {
                                "Ders": k["ders"],
                                "Makro konu": k["makro_konu"],
                                "Mikro konu": k["mikro_konu"],
                                "Hedef soru": k["hedef_soru"],
                                "Çözülen soru": k["cozulen_soru"],
                                "Kalan": k["kalan"],
                                "Öğrenme": "✔" if k["ogrenme_tamam"] else "",
                            }
                            for k in mikro_ozet["bekleyen_konular"]
                        ]
                    )
                    st.dataframe(
                        bekleyen_df, width="stretch", hide_index=True
                    )
            if mikro_ozet["yanlis_biriken"]:
                with st.expander("📕 Defterde biriken yanlış sorular"):
                    biriken_df = pd.DataFrame(
                        [
                            {
                                "Ders": k["ders"],
                                "Mikro konu": k["mikro_konu"],
                                "Bekleyen soru": k["adet"],
                            }
                            for k in mikro_ozet["yanlis_biriken"]
                        ]
                    )
                    st.dataframe(
                        biriken_df, width="stretch", hide_index=True
                    )


        # ------------------------------------------------------------------
        # TEKRAR & YANLIŞ SORU DEFTERİ
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("🔁 Tekrar & Yanlış Soru Defteri")
        tekrar_ozet = hafta_raporu["tekrar"]
        defter_ozet = hafta_raporu["defter"]

        tekrar_a, tekrar_b, tekrar_c, tekrar_d = st.columns(4)
        tekrar_a.metric("Planlanan tekrar", tekrar_ozet["planlanan"])
        tekrar_b.metric(
            "Tamamlanan tekrar",
            tekrar_ozet["tamamlanan"],
            delta=(
                None
                if tekrar_ozet["tamamlama_orani"] is None
                else _hafta_yuzde_metni(tekrar_ozet["tamamlama_orani"])
            ),
        )
        tekrar_c.metric("Bekleyen tekrar", tekrar_ozet["bekleyen"])
        tekrar_d.metric(
            "Stokta bekleyen tekrar", tekrar_ozet["stok_bekleyen"]
        )
        if tekrar_ozet["gecikmis_bekleyen"] or tekrar_ozet["gecikmis_tamamlanan"]:
            st.caption(
                "Gecikmiş (bu hafta bekleyen): %d · Önceki haftadan"
                " tamamlanan: %d · İptal edilen: %d"
                % (
                    tekrar_ozet["gecikmis_bekleyen"],
                    tekrar_ozet["gecikmis_tamamlanan"],
                    tekrar_ozet["iptal"],
                )
            )
        if tekrar_ozet["kartlar"]:
            with st.expander("📇 Bu haftanın tekrar kartları"):
                tekrar_df = pd.DataFrame(
                    [
                        {
                            "Planlanan tarih": k["planlanan_tarih"],
                            "Ders": k["ders"],
                            "Makro konu": k["makro_konu"],
                            "Mikro konu": k["mikro_konu"],
                            "Alt başlık": k["alt_konu"] or "",
                            "Durum": k["durum"],
                            "Tamamlanma": k["tamam_gun"] or "",
                        }
                        for k in tekrar_ozet["kartlar"]
                    ]
                )
                st.dataframe(tekrar_df, width="stretch", hide_index=True)

        st.markdown("#### 📕 Yanlış Soru Defteri Akışı")
        defter_a, defter_b, defter_c, defter_d, defter_e = st.columns(5)
        defter_a.metric("Hafta başı bekleyen", defter_ozet["baslangic_bekleyen"])
        defter_b.metric(
            "Hafta sonu bekleyen",
            defter_ozet["bitis_bekleyen"],
            delta=_hafta_fark_metni(
                "bekleyen_yanlis", defter_ozet["degisim"], "soru"
            ),
        )
        defter_c.metric("Yeni eklenen", defter_ozet["eklenen"])
        defter_d.metric("Öğrenilen", defter_ozet["ogrenilen"])
        defter_e.metric("Yeniden çözülen", defter_ozet["yeniden_cozulen"])
        st.caption(
            "Arşivlenen: %d · Bugün defterde duran aktif kayıt: %d"
            % (defter_ozet["arsivlenen"], defter_ozet["aktif_toplam"])
        )
        st.caption(defter_ozet["not"])

        # ------------------------------------------------------------------
        # DENEMELER
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("📝 Haftanın Denemeleri")
        deneme_ozet = hafta_raporu["denemeler"]
        if not deneme_ozet["adet"]:
            st.info("Bu hafta deneme kaydı bulunmuyor.")
        else:
            deneme_df = pd.DataFrame(
                [
                    {
                        "Tarih": n["gun"],
                        "Deneme": n["ad"],
                        "Tür": n["tur"],
                        "Kategori": n["kategori"],
                        "Net": (
                            "—" if n["net"] is None
                            else ("%.2f" % float(n["net"]))
                        ),
                        "Doğru": n["dogru"],
                        "Yanlış": n["yanlis"],
                        "Boş": n["bos"],
                    }
                    for n in deneme_ozet["netler"]
                ]
            )
            st.dataframe(deneme_df, width="stretch", hide_index=True)
            st.caption(
                "Deneme sayısı: %d · Net ortalaması: %s"
                % (
                    deneme_ozet["adet"],
                    _hafta_deger_metni("deneme_net", deneme_ozet["net_ort"]),
                )
            )
            if deneme_ozet["turler"]:
                tur_df = pd.DataFrame(
                    [
                        {
                            "Tür": tur,
                            "Adet": kayit["adet"],
                            "Net ortalaması": kayit["net_ort"],
                        }
                        for tur, kayit in sorted(deneme_ozet["turler"].items())
                    ]
                )
                st.dataframe(tur_df, width="stretch", hide_index=True)
            if deneme_ozet["dersler"]:
                with st.expander("📊 Deneme ders kırılımı"):
                    ders_df = pd.DataFrame(
                        [
                            {
                                "Ders": d["ders"],
                                "Adet": d["adet"],
                                "Doğru": d["dogru"],
                                "Yanlış": d["yanlis"],
                                "Boş": d["bos"],
                                "Net ortalaması": d["net_ort"],
                            }
                            for d in deneme_ozet["dersler"]
                        ]
                    )
                    st.dataframe(ders_df, width="stretch", hide_index=True)


        # ------------------------------------------------------------------
        # HAFTALIK TREND (SON 8 HAFTA)
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("📈 Haftalık Trend")
        trend_serisi = weekly_report.haftalik_seri(
            current_user["id"], weekly_report.VARSAYILAN_SERI_HAFTA
        )
        if not weekly_report.trend_yeterli_mi(trend_serisi):
            st.info(
                "Trend grafiği için en az %d hafta veri gerekiyor."
                % weekly_report.GRAFIK_MIN_HAFTA
            )
        else:
            st.caption(
                "Son %d hafta. Ham haftalık değerle birlikte 4 haftalık"
                " ortalama gösterilir; ortalama tek haftalık dalgalanmayı"
                " yumuşatır."
                % len(trend_serisi)
            )
            trend_temel = pd.DataFrame(
                {
                    "Hafta": [s["kisa"] for s in trend_serisi],
                    "Süre (dk)": [s["dk"] for s in trend_serisi],
                    "Süre ortalaması": weekly_report.seri_ortalama_serisi(
                        trend_serisi, "dk", 4
                    ),
                    "Çözülen soru": [s["soru"] for s in trend_serisi],
                    "Soru ortalaması": weekly_report.seri_ortalama_serisi(
                        trend_serisi, "soru", 4
                    ),
                    "Program uyumu": [s["uyum"] for s in trend_serisi],
                }
            ).set_index("Hafta")
            st.line_chart(trend_temel[["Süre (dk)", "Süre ortalaması"]])
            st.line_chart(trend_temel[["Çözülen soru", "Soru ortalaması"]])
            if trend_temel["Program uyumu"].notna().any():
                st.line_chart(trend_temel[["Program uyumu"]])
            net_noktalari = [
                (s["kisa"], float(s["deneme_net"]))
                for s in trend_serisi
                if s["deneme_net"] is not None
            ]
            if len(net_noktalari) >= weekly_report.GRAFIK_MIN_DENEME:
                net_df = pd.DataFrame(
                    net_noktalari, columns=["Hafta", "Deneme neti"]
                ).set_index("Hafta")
                st.line_chart(net_df[["Deneme neti"]])
            else:
                st.caption(
                    "Deneme neti trendi için en az %d hafta deneme neti"
                    " gerekiyor."
                    % weekly_report.GRAFIK_MIN_DENEME
                )
            st.caption(
                "4 haftalık ortalamalar · Süre: %s · Soru: %s · Program"
                " uyumu: %s"
                % (
                    weekly_report.sure_metni(
                        weekly_report.seri_ortalamasi(trend_serisi, "dk", 4)
                        or 0
                    ),
                    _hafta_deger_metni(
                        "soru",
                        weekly_report.seri_ortalamasi(
                            trend_serisi, "soru", 4
                        ),
                    ),
                    _hafta_deger_metni(
                        "uyum",
                        weekly_report.seri_ortalamasi(
                            trend_serisi, "uyum", 4
                        ),
                    ),
                )
            )


        # ------------------------------------------------------------------
        # YORUMLAR (kural tabanlı, deterministik)
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("🗣️ Değerlendirme ve Öneriler")
        if not hafta_raporu["yorumlar"]:
            st.info(
                "Bu hafta için yorum üretilecek yeterli veri yok. Çalışma"
                " oturumu, görev, deneme veya tekrar kaydı girdikçe"
                " değerlendirme burada oluşur."
            )
        else:
            st.caption(
                "Her gözlem ölçülen bir sayıya dayanır; yapay zekâ"
                " kullanılmaz. Geçen hafta da verilen öneriler 🔁 ile"
                " işaretlenir ve listenin sonuna düşer."
            )
            for hafta_yorumu in hafta_raporu["yorumlar"]:
                yorum_metni = "**%s**\n\n%s" % (
                    hafta_yorumu["baslik"],
                    hafta_yorumu["gozlem"],
                )
                if hafta_yorumu["oneri"]:
                    yorum_metni += "\n\n👉 **Öneri:** %s" % (
                        hafta_yorumu["oneri"]
                    )
                if hafta_yorumu["tekrar"]:
                    yorum_metni = "🔁 *Geçen hafta da önerilmişti.*\n\n" + (
                        yorum_metni
                    )
                if hafta_yorumu["tur"] == "dikkat":
                    st.warning(yorum_metni)
                elif hafta_yorumu["tur"] == "olumlu":
                    st.success(yorum_metni)
                else:
                    st.info(yorum_metni)

        # ------------------------------------------------------------------
        # HAFTALIK ÖĞRENCİ DEĞERLENDİRMESİ (kalıcı notlar)
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("📝 Haftalık Öğrenci Değerlendirmesi")
        st.caption(
            "Bu notlar haftaya bağlı olarak saklanır ve yalnızca size"
            " gösterilir. Boş bırakılan alanlar kaydedilmez."
        )
        mevcut_degerlendirme = hafta_raporu["degerlendirme"] or {}
        with st.form("hafta_degerlendirme_formu"):
            degerlendirme_girdileri = {}
            for alan_kolonu, alan_sorusu in weekly_report.DEGERLENDIRME_ALANLARI:
                alan_anahtari = "hafta_deg_%s_%s" % (
                    secilen_hafta["baslangic"],
                    alan_kolonu,
                )
                if alan_anahtari not in st.session_state:
                    st.session_state[alan_anahtari] = (
                        mevcut_degerlendirme.get(alan_kolonu) or ""
                    )
                degerlendirme_girdileri[alan_kolonu] = st.text_area(
                    alan_sorusu, key=alan_anahtari, height=80
                )
            if st.form_submit_button(
                "💾 Değerlendirmeyi Kaydet", type="primary"
            ):
                try:
                    weekly_report.degerlendirme_kaydet(
                        current_user["id"],
                        secilen_hafta["baslangic"],
                        **degerlendirme_girdileri,
                    )
                except weekly_report.HaftalikRaporHatasi as deg_hatasi:
                    st.error(
                        "Değerlendirme kaydedilemedi: %s" % deg_hatasi
                    )
                else:
                    log_islem(
                        current_user["id"],
                        "WEEKLY_EVALUATION_SAVE",
                        hafta_bilgi["kisa"],
                    )
                    set_flash_message(
                        "success",
                        "Haftalık değerlendirme kaydedildi (%s)."
                        % hafta_bilgi["kisa"],
                    )
                    st.rerun()

        gecmis_degerlendirmeler = weekly_report.degerlendirmeleri_getir(
            current_user["id"], 8
        )
        dolu_gecmis = [k for k in gecmis_degerlendirmeler if k["dolu"]]
        if dolu_gecmis:
            with st.expander("📚 Geçmiş hafta notlarım"):
                for gecmis_kayit in dolu_gecmis:
                    st.markdown("**%s**" % gecmis_kayit["etiket"])
                    for alan_kolonu, alan_sorusu in (
                        weekly_report.DEGERLENDIRME_ALANLARI
                    ):
                        if gecmis_kayit[alan_kolonu]:
                            st.markdown(
                                "- *%s* %s"
                                % (alan_sorusu, gecmis_kayit[alan_kolonu])
                            )


# ==============================================================================
# FAZ 8: YKS PUAN VE SIRALAMA SİMÜLATÖRÜ (9. SEKME)
# ==============================================================================
# Hesaplama `services/ranking_engine.py`, yıl kuralı ve puan-sıra referans
# verisi `services/osym_verisi.py` içindedir. Bu bölüm yalnızca arayüzdür:
# hiçbir katsayı veya sıralama sayısı burada tanımlanmaz.
SIM_KAYNAK_OTO = "Son denemelerimden otomatik"
SIM_KAYNAK_MANUEL = "Manuel giriş"
SIM_KAYNAK_HEDEF = "Hedef netlerim"

SIM_DURUM_ETIKETLERI = {
    "hedefte": "✅ Hedefte",
    "hedefin_altinda": "⬇️ Hedefin altında",
    "hedef_yok": "— Hedef yok",
    "mevcut_yok": "— Deneme yok",
    "veri_yok": "— Veri yok",
}

SIM_SIRALAMA_NOTLARI = {
    "veri_yok": (
        "Sıralama tahmini üretilmedi: seçilen yıl ve puan türü için"
        " doğrulanmış puan–sıra referans verisi yok."
    ),
    "veri_yetersiz": (
        "Sıralama tahmini üretilmedi: referans noktası sayısı yetersiz."
    ),
    "aralik_disi": (
        "Sıralama tahmini üretilmedi: puan, girilen referans noktalarının"
        " puan aralığının dışında."
    ),
}


def sim_puan_turu_varsayilani(hedef_alan):
    """Öğrencinin hedef alanını puan türüne çevirir (geçersizse Sayısal)."""
    try:
        return osym_verisi.puan_turu_kontrol(hedef_alan)
    except osym_verisi.VeriHatasi:
        return "Sayısal"


def sim_sira_metni(sira):
    """18000 -> '~18.000' (okunur biçim)."""
    if sira is None:
        return "—"
    return "~{:,}".format(int(sira)).replace(",", ".")


def sim_noktalari_oku(metin):
    """'puan;sıra' satırlarını referans noktası listesine çevirir."""
    noktalar = []
    for satir_no, satir in enumerate(str(metin or "").splitlines(), start=1):
        temiz = satir.strip()
        if not temiz:
            continue
        parcalar = [p.strip() for p in temiz.replace("\t", ";").split(";")]
        if len(parcalar) != 2 or not parcalar[0] or not parcalar[1]:
            raise ValueError(
                "%d. satır 'puan;sıra' biçiminde olmalı (örn. 450;6000)."
                % satir_no
            )
        try:
            puan = float(parcalar[0].replace(",", "."))
            sira = int(float(parcalar[1].replace(".", "").replace(",", "")))
        except ValueError:
            raise ValueError(
                "%d. satırda puan/sıra sayı değil: %s" % (satir_no, temiz)
            ) from None
        noktalar.append({"puan": puan, "sira": sira})
    if not noktalar:
        raise ValueError("En az %d nokta girmelisiniz." % osym_verisi.MIN_NOKTA)
    return noktalar


with tab9:
    st.header("🎯 YKS Puan ve Sıralama Simülatörü")
    st.caption(
        "Netlerinizden **model puan** hesaplanır. Sıralama tahmini yalnızca"
        " doğrulanmış puan–sıra referans verisi varsa üretilir; bu ekran resmî"
        " ÖSYM sonucu göstermez."
    )

    sim_veri = ranking_engine.veri_durumu()
    sim_model = sim_veri["model"]
    sim_siralama_ozet = sim_veri["siralama"]

    with st.expander("ℹ️ Nasıl hesaplanıyor? Kaynak, yöntem ve sınırlar"):
        st.markdown(
            "**Puan (model):** 100 taban puan + her testin neti × test katsayısı"
            " + OBP katkısı. Net = doğru − yanlış / 4."
        )
        st.markdown(
            "**OBP:** OBP = diploma notu × 5, katkı = OBP × 0.12 (en fazla 60"
            " puan). OBP'yi puana ekleyip eklememek sizin seçiminizdir."
        )
        st.markdown(
            "**Sıralama:** yalnızca `data/osym_puan_sira.json` içindeki"
            " doğrulanmış puan–sıra noktaları kullanılır. Noktalar arasında"
            " doğrusal tahmin yapılır; aralık dışına tahmin üretilmez."
        )
        st.warning(sim_model["kaynak"]["sinirlilik"], icon="⚠️")
        st.caption(
            "Kural kaynağı: %s · %s"
            % (sim_model["kaynak"]["kurum"], sim_model["kaynak"]["belge"])
        )
        st.caption(
            "Desteklenen sınav yılları: %s – %s · Katsayı seti doğrulama durumu:"
            " **%s**"
            % (
                sim_model["yillar"][0],
                sim_model["yillar"][-1],
                sim_model["dogrulama_durumu"],
            )
        )

    sim_puan_turu_varsayilan = sim_puan_turu_varsayilani(
        current_user.get("hedef_alan")
    )
    sim_puan_turu_listesi = list(osym_verisi.PUAN_TURLERI)
    sim_kol_puan, sim_kol_yil, sim_kol_obp, sim_kol_obp_secim = st.columns(
        [1.2, 1, 1, 1]
    )
    with sim_kol_puan:
        sim_puan_turu = st.selectbox(
            "Puan türü",
            sim_puan_turu_listesi,
            index=sim_puan_turu_listesi.index(sim_puan_turu_varsayilan),
            key="sim_puan_turu",
        )
    with sim_kol_yil:
        sim_yil_listesi = list(reversed(osym_verisi.desteklenen_yillar()))
        sim_yil = st.selectbox(
            "Sınav yılı", sim_yil_listesi, index=0, key="sim_yil"
        )
    with sim_kol_obp:
        sim_diploma = st.number_input(
            "Diploma notu (OBP)",
            min_value=50.0,
            max_value=100.0,
            value=float(current_user.get("diploma_notu") or 85.0),
            step=0.1,
            key="sim_diploma",
        )
    with sim_kol_obp_secim:
        sim_obp_dahil = st.toggle(
            "OBP'yi puana ekle", value=True, key="sim_obp_dahil"
        )
    st.caption(
        "OBP %.0f → katkı +%.2f puan (diploma notunu değiştirmek için kenar"
        " çubuğundaki **Profili Güncelle** formunu kullanın)."
        % (
            osym_verisi.obp_puani(sim_diploma),
            osym_verisi.obp_katkisi(sim_diploma, sim_yil),
        )
    )

    sim_mevcut = ranking_engine.mevcut_netler(current_user["id"])
    sim_hedefler = ranking_engine.hedef_netleri_getir(
        current_user["id"], sim_puan_turu
    )

    sim_kaynak_listesi = [SIM_KAYNAK_OTO, SIM_KAYNAK_MANUEL]
    if sim_hedefler:
        sim_kaynak_listesi.append(SIM_KAYNAK_HEDEF)
    sim_varsayilan_kaynak = (
        SIM_KAYNAK_OTO if sim_mevcut["kayit_var"] else SIM_KAYNAK_MANUEL
    )
    sim_kaynak = st.radio(
        "Netler nereden gelsin?",
        sim_kaynak_listesi,
        index=sim_kaynak_listesi.index(sim_varsayilan_kaynak),
        horizontal=True,
        key="sim_kaynak_%s" % sanitize_key(sim_puan_turu),
    )

    if sim_kaynak == SIM_KAYNAK_OTO:
        if not sim_mevcut["kayit_var"]:
            st.info(
                "Ders bazlı net içeren genel denemeniz henüz yok. Netleri"
                " **Manuel giriş** ile girebilirsiniz; **Deneme Analizi**"
                " sekmesinde ders detayı girerseniz bu alan otomatik dolar.",
                icon="ℹ️",
            )
            sim_son_deneme = ranking_engine.VARSAYILAN_SON_DENEME
        else:
            sim_son_deneme = st.slider(
                "Kaç son genel denemenin ortalaması alınsın?",
                min_value=1,
                max_value=ranking_engine.MAKS_SON_DENEME,
                value=ranking_engine.VARSAYILAN_SON_DENEME,
                key="sim_son_deneme",
            )
            sim_mevcut = ranking_engine.mevcut_netler(
                current_user["id"], son_deneme=sim_son_deneme
            )
            sim_deneme_ozeti = ", ".join(
                "%s: %d" % (tur, adet)
                for tur, adet in sim_mevcut["deneme_sayisi"].items()
                if adet
            )
            st.caption(
                "%s · %s"
                % (
                    sim_mevcut["yontem"] or "Deneme verisi yok",
                    sim_deneme_ozeti or "—",
                )
            )
            for sim_uyari in sim_mevcut["uyarilar"]:
                st.caption("• %s" % sim_uyari)
    elif sim_kaynak == SIM_KAYNAK_HEDEF:
        st.caption(
            "Netler kaydettiğiniz hedef netlerden geliyor. Hedef netler ayrı"
            " saklanır ve mevcut deneme netlerinizin üzerine yazılmaz."
        )
    else:
        st.caption(
            "Netleri kendiniz girin. Girdiğiniz değerler otomatik olarak"
            " kaydedilmez; yalnızca bu ekrandaki tahmin için kullanılır."
        )

    sim_kaynak_kodu = {
        SIM_KAYNAK_OTO: "oto",
        SIM_KAYNAK_MANUEL: "manuel",
        SIM_KAYNAK_HEDEF: "hedef",
    }[sim_kaynak]
    sim_on_dolu = {}
    if sim_kaynak_kodu == "oto":
        sim_on_dolu.update(sim_mevcut["tyt"])
        sim_on_dolu.update(sim_mevcut["ayt"])
    elif sim_kaynak_kodu == "hedef":
        sim_on_dolu.update(sim_hedefler)

    sim_netler = {}
    with st.expander(
        "📊 Test netleri (düzenlenebilir)",
        expanded=(sim_kaynak_kodu == "manuel"),
    ):
        st.caption(
            "Net = doğru − yanlış / 4. Değerler 0 ile testin soru sayısı"
            " arasında olmalıdır."
        )
        sim_test_kolonlari = st.columns(2)
        for sim_indeks, sim_test in enumerate(
            ranking_engine.gereken_testler(sim_puan_turu)
        ):
            sim_soru_sayisi = osym_verisi.test_soru_sayisi(sim_test) or 40
            sim_net_anahtari = "sim_net_%s_%s" % (
                sim_kaynak_kodu,
                sanitize_key(sim_test),
            )
            if sim_net_anahtari not in st.session_state:
                st.session_state[sim_net_anahtari] = round(
                    float(sim_on_dolu.get(sim_test, 0.0)), 2
                )
            with sim_test_kolonlari[sim_indeks % 2]:
                sim_netler[sim_test] = st.number_input(
                    "%s (0–%d)" % (sim_test, sim_soru_sayisi),
                    min_value=0.0,
                    max_value=float(sim_soru_sayisi),
                    step=0.25,
                    key=sim_net_anahtari,
                )

    try:
        sim_paket = ranking_engine.simulasyon(
            sim_netler, sim_puan_turu, sim_yil, sim_diploma, sim_obp_dahil
        )
    except (osym_verisi.VeriHatasi, ranking_engine.SimulatorHatasi) as sim_hata:
        st.error("Simülasyon hesaplanamadı: %s" % sim_hata)
        sim_paket = None

    sim_puan = None
    sim_siralama = None
    if sim_paket is not None:
        sim_puan = sim_paket["puan"]
        sim_siralama = sim_paket["siralama"]
        if sim_puan["durum"] != ranking_engine.DURUM_OK:
            st.error(
                "Puan hesaplanamadı: %s"
                % "; ".join(sim_puan.get("uyarilar") or ["eksik veri"])
            )
            sim_puan = None

    if sim_puan is not None:
        sim_k1, sim_k2, sim_k3 = st.columns(3)
        with sim_k1:
            st.metric(
                "Model yerleştirme puanı",
                "%.2f" % sim_puan["puan"],
                help="Resmî ÖSYM puanı değildir; doğrusal model tahminidir.",
            )
            st.caption(
                "OBP hariç: %.2f · OBP katkısı: +%.2f"
                % (sim_puan["puan_obp_haric"], sim_puan["obp_katkisi"])
            )
        with sim_k2:
            st.metric("TYT neti", "%.2f" % sim_puan["tyt_net"])
            if sim_puan_turu == "TYT":
                st.caption("TYT puan türünde alan testi kullanılmaz.")
            else:
                st.caption("Alan neti: %.2f" % sim_puan["alan_net"])
        with sim_k3:
            st.metric(
                "Tahmini sıralama",
                sim_sira_metni(
                    sim_siralama.get("sira") if sim_siralama else None
                ),
            )
            st.caption(
                (
                    "Senaryo aralığı: %s – %s"
                    % (
                        sim_sira_metni(sim_siralama["aralik"][0]),
                        sim_sira_metni(sim_siralama["aralik"][1]),
                    )
                )
                if sim_siralama and sim_siralama.get("aralik")
                else "Sıralama aralığı bu veriyle hesaplanamıyor."
            )

        with st.expander("📐 Puan katkıları (test bazında)"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Test": sim_satir["test"],
                            "Net": "%.2f" % sim_satir["net"],
                            "Katsayı": "%.2f" % sim_satir["katsayi"],
                            "Puan katkısı": "%.2f" % sim_satir["katki"],
                        }
                        for sim_satir in sim_puan["test_katkilari"]
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            st.caption(
                "Taban puan %.0f + katkılar = %.2f (ham puan). OBP %s."
                % (
                    sim_puan["kural"]["taban_puan"],
                    sim_puan["ham_puan"],
                    ("eklendi (+%.2f)" % sim_puan["obp_katkisi"])
                    if sim_puan["obp_dahil"]
                    else "eklenmedi",
                )
            )

    st.divider()
    st.subheader("🏆 Başarı sıralaması tahmini")
    if sim_siralama is None:
        st.info("Puan hesaplanmadan sıralama tahmini yapılamaz.")
    elif sim_siralama["durum"] == ranking_engine.DURUM_OK:
        sim_sol, sim_sag = st.columns([1, 2])
        with sim_sol:
            st.metric("Tahmini sıra", sim_sira_metni(sim_siralama["sira"]))
            if sim_siralama.get("aralik"):
                st.caption(
                    "Senaryo aralığı: %s – %s"
                    % (
                        sim_sira_metni(sim_siralama["aralik"][0]),
                        sim_sira_metni(sim_siralama["aralik"][1]),
                    )
                )
        with sim_sag:
            for sim_not in sim_siralama.get("notlar") or []:
                st.caption("• %s" % sim_not)
            st.caption(
                "Referans verisi olan yıllar (%s): %s"
                % (
                    sim_puan_turu,
                    ", ".join(sim_siralama.get("kapsanan_yillar") or []) or "—",
                )
            )
            sim_veri_kaynagi = sim_siralama.get("kaynak") or {}
            if sim_veri_kaynagi:
                st.caption(
                    "Kaynak: %s · %s · Erişim: %s"
                    % (
                        sim_veri_kaynagi.get("kurum") or "—",
                        sim_veri_kaynagi.get("belge") or "—",
                        sim_veri_kaynagi.get("erisim_tarihi") or "belirtilmemiş",
                    )
                )
                if sim_veri_kaynagi.get("url"):
                    st.caption("Bağlantı: %s" % sim_veri_kaynagi["url"])
        if sim_siralama.get("yil_tahminleri"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Yıl": sim_yil_satiri["yil"],
                            "Tahmini sıra": sim_sira_metni(
                                sim_yil_satiri["sira"]
                            ),
                        }
                        for sim_yil_satiri in sim_siralama["yil_tahminleri"]
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
    else:
        st.info(
            SIM_SIRALAMA_NOTLARI.get(
                sim_siralama["durum"], SIM_SIRALAMA_NOTLARI["veri_yok"]
            ),
            icon="ℹ️",
        )
        for sim_eksik in sim_siralama.get("eksik_veri") or []:
            st.caption("• Eksik: %s" % sim_eksik)
        sim_kapsanan_yillar = sim_siralama.get("kapsanan_yillar") or []
        st.caption(
            "Bu puan türü için referans verisi olan yıllar: %s"
            % (", ".join(sim_kapsanan_yillar) if sim_kapsanan_yillar else "yok")
        )
        st.caption(
            "Referans verisi eklendiğinde (yönetici: bu sekmenin altındaki"
            " bölüm) sıralama tahmini otomatik görünür."
        )

    st.divider()
    st.subheader("🎯 Hedef netlerimle karşılaştırma")
    st.caption(
        "Hedef netler ayrı saklanır; mevcut deneme netlerinizin üzerine"
        " yazılmaz. Fark = mevcut − hedef (negatifse hedefin altındasınız)."
    )
    sim_hedef_satirlar = ranking_engine.hedef_karsilastirma(
        current_user["id"], sim_puan_turu, sim_mevcut
    )
    sim_hedef_var = [s for s in sim_hedef_satirlar if s["hedef"] is not None]
    sim_mevcut_var = [s for s in sim_hedef_satirlar if s["mevcut"] is not None]
    if not sim_hedef_var and not sim_mevcut_var:
        st.info(
            "Ne kayıtlı hedef netiniz ne de ders bazlı deneme netiniz var."
            " Aşağıdaki formdan hedef netlerinizi girebilirsiniz.",
            icon="ℹ️",
        )
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Test": sim_satir["test"],
                        "Mevcut net": (
                            "%.2f" % sim_satir["mevcut"]
                            if sim_satir["mevcut"] is not None
                            else "—"
                        ),
                        "Hedef net": (
                            "%.2f" % sim_satir["hedef"]
                            if sim_satir["hedef"] is not None
                            else "—"
                        ),
                        "Fark": (
                            "%+.2f" % sim_satir["fark"]
                            if sim_satir["fark"] is not None
                            else "—"
                        ),
                        "Durum": SIM_DURUM_ETIKETLERI.get(
                            sim_satir["durum"], sim_satir["durum"]
                        ),
                    }
                    for sim_satir in sim_hedef_satirlar
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    sim_gereken_testler = ranking_engine.gereken_testler(sim_puan_turu)
    sim_eksik_hedefler = [
        sim_test for sim_test in sim_gereken_testler if sim_test not in sim_hedefler
    ]
    if sim_hedef_var:
        if sim_eksik_hedefler:
            st.caption(
                "Hedef puan karşılığı için eksik hedef netler: %s"
                % ", ".join(sim_eksik_hedefler)
            )
        else:
            sim_hedef_puan = ranking_engine.puan_hesapla(
                sim_hedefler,
                sim_puan_turu,
                sim_yil,
                sim_diploma,
                sim_obp_dahil,
            )
            if sim_hedef_puan["durum"] == ranking_engine.DURUM_OK:
                sim_h1, sim_h2 = st.columns(2)
                with sim_h1:
                    st.metric(
                        "Hedef netlerin model puanı",
                        "%.2f" % sim_hedef_puan["puan"],
                    )
                with sim_h2:
                    if sim_puan is not None:
                        st.metric(
                            "Mevcuttan fark",
                            "%+.2f puan"
                            % (sim_hedef_puan["puan"] - sim_puan["puan"]),
                        )
                    else:
                        st.metric("Mevcuttan fark", "—")

    with st.form("sim_hedef_formu"):
        st.markdown("**Hedef netleri kaydet / güncelle**")
        st.caption(
            "Sıfır girilen testler hedef olarak saklanmaz. Hedef netler yalnızca"
            " karşılaştırma ve hedef puan hesabı için kullanılır."
        )
        sim_hedef_girdiler = {}
        sim_hedef_kolonlari = st.columns(2)
        for sim_indeks, sim_test in enumerate(sim_gereken_testler):
            sim_soru_sayisi = osym_verisi.test_soru_sayisi(sim_test) or 40
            sim_hedef_anahtari = "sim_hedef_%s_%s" % (
                sanitize_key(sim_puan_turu),
                sanitize_key(sim_test),
            )
            if sim_hedef_anahtari not in st.session_state:
                st.session_state[sim_hedef_anahtari] = float(
                    sim_hedefler.get(sim_test, 0.0)
                )
            with sim_hedef_kolonlari[sim_indeks % 2]:
                sim_hedef_girdiler[sim_test] = st.number_input(
                    "%s hedefi (0–%d)" % (sim_test, sim_soru_sayisi),
                    min_value=0.0,
                    max_value=float(sim_soru_sayisi),
                    step=0.25,
                    key=sim_hedef_anahtari,
                )
        if st.form_submit_button("💾 Hedef netleri kaydet"):
            sim_kayit_netler = {
                test: net
                for test, net in sim_hedef_girdiler.items()
                if net and net > 0
            }
            try:
                if sim_kayit_netler:
                    ranking_engine.hedef_netleri_kaydet(
                        current_user["id"], sim_puan_turu, sim_kayit_netler
                    )
                else:
                    ranking_engine.hedef_netleri_sil(
                        current_user["id"], sim_puan_turu
                    )
            except ranking_engine.SimulatorHatasi as sim_hedef_hata:
                st.error("Hedef netler kaydedilemedi: %s" % sim_hedef_hata)
            else:
                log_islem(
                    current_user["id"],
                    "SAVE_TARGET_NETS",
                    "%s: %d test" % (sim_puan_turu, len(sim_kayit_netler)),
                )
                set_flash_message(
                    "success",
                    "%s için hedef netler kaydedildi (%d test)."
                    % (sim_puan_turu, len(sim_kayit_netler)),
                )
                st.rerun()

    if sim_hedefler:
        if st.button("🗑️ Hedef netleri temizle", key="sim_hedef_temizle"):
            ranking_engine.hedef_netleri_sil(current_user["id"], sim_puan_turu)
            for sim_test in sim_gereken_testler:
                st.session_state.pop(
                    "sim_hedef_%s_%s"
                    % (sanitize_key(sim_puan_turu), sanitize_key(sim_test)),
                    None,
                )
            log_islem(
                current_user["id"], "CLEAR_TARGET_NETS", str(sim_puan_turu)
            )
            set_flash_message(
                "info", "%s hedef netleri temizlendi." % sim_puan_turu
            )
            st.rerun()

    st.divider()
    st.subheader("📅 Yıllara göre karşılaştırma")
    st.caption(
        "Aynı netlerle her yılın kural setine göre model puanı hesaplanır."
        " Sıralama yalnızca o yıl için doğrulanmış referans verisi varsa görünür."
    )
    sim_yil_satirlari = ranking_engine.yil_karsilastirmasi(
        sim_netler,
        sim_puan_turu,
        sim_diploma,
        sim_obp_dahil,
        yillar=list(reversed(osym_verisi.desteklenen_yillar())),
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Yıl": sim_satir["yil"],
                    "Model puanı": (
                        "%.2f" % sim_satir["puan"]
                        if sim_satir["puan"] is not None
                        else "—"
                    ),
                    "Tahmini sıra": (
                        sim_sira_metni(sim_satir["sira"])
                        if sim_satir["sira"] is not None
                        else "veri yok"
                    ),
                    "Senaryo aralığı": (
                        "%s – %s"
                        % (
                            sim_sira_metni(sim_satir["aralik"][0]),
                            sim_sira_metni(sim_satir["aralik"][1]),
                        )
                        if sim_satir["aralik"]
                        else "—"
                    ),
                }
                for sim_satir in sim_yil_satirlari
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Bu ekran bir ÖSYM sonucu açıklama sistemi değildir. Gerçek sıralama;"
        " sınavın zorluğu, adayların performansı ve ilgili yılın koşullarına"
        " göre değişebilir. Sıralama tahmini yalnızca girilen referans"
        " verisiyle sınırlıdır."
    )

    if current_user["rol"] == "admin":
        with st.expander("🛠️ Puan–sıra referans verisi (yönetici)"):
            st.caption(
                "Sıralama tahmini bu dosyadan beslenir: `%s`. Kaynaksız kayıt"
                " kabul edilmez; noktalar puan azalan / sıra artan olmalıdır."
                % sim_siralama_ozet.get("dosya", osym_verisi.veri_dosyasi())
            )
            if sim_siralama_ozet.get("hata"):
                st.error(sim_siralama_ozet["hata"])
            st.caption(
                "Kayıt: %d · Hatalı kayıt: %d · Son güncelleme: %s"
                % (
                    sim_siralama_ozet.get("kayit_sayisi") or 0,
                    sim_siralama_ozet.get("hatali_kayit_sayisi") or 0,
                    sim_siralama_ozet.get("guncelleme") or "—",
                )
            )
            sim_kaynak_tablosu = sim_siralama_ozet.get("kaynaklar") or []
            if sim_kaynak_tablosu:
                st.dataframe(
                    pd.DataFrame(sim_kaynak_tablosu),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info(
                    "Kayıtlı referans verisi yok. Aşağıdaki formdan resmî"
                    " kaynağa dayanan noktaları ekleyebilirsiniz."
                )

            with st.form("sim_veri_ekle_formu"):
                st.markdown("**Referans kaydı ekle / güncelle**")
                sim_veri_kol1, sim_veri_kol2 = st.columns(2)
                with sim_veri_kol1:
                    sim_veri_yil = st.selectbox(
                        "Sınav yılı",
                        list(reversed(osym_verisi.desteklenen_yillar())),
                        key="sim_veri_yil",
                    )
                    sim_veri_kurum = st.text_input(
                        "Kaynak kurum", value="", key="sim_veri_kurum"
                    )
                    sim_veri_url = st.text_input(
                        "Kaynak bağlantısı (URL)", value="", key="sim_veri_url"
                    )
                with sim_veri_kol2:
                    sim_veri_tur = st.selectbox(
                        "Puan türü",
                        list(osym_verisi.PUAN_TURLERI),
                        key="sim_veri_tur",
                    )
                    sim_veri_belge = st.text_input(
                        "Kaynak belge / tablo adı",
                        value="",
                        key="sim_veri_belge",
                    )
                    sim_veri_erisim = st.text_input(
                        "Erişim tarihi (YYYY-AA-GG)",
                        value="",
                        placeholder="2026-11-11",
                        key="sim_veri_erisim",
                    )
                sim_veri_noktalar = st.text_area(
                    "Noktalar (her satır: puan;sıra)",
                    value="",
                    height=120,
                    placeholder="500;500\n450;6000\n400;30000",
                    key="sim_veri_noktalar",
                )
                sim_veri_not = st.text_input(
                    "Not (kapsam / sınırlılık)", value="", key="sim_veri_not"
                )
                if st.form_submit_button("💾 Referans kaydını yaz"):
                    try:
                        osym_verisi.kayit_ekle(
                            sim_veri_yil,
                            sim_veri_tur,
                            sim_noktalari_oku(sim_veri_noktalar),
                            {
                                "kurum": sim_veri_kurum,
                                "belge": sim_veri_belge,
                                "url": sim_veri_url,
                                "erisim_tarihi": sim_veri_erisim or None,
                            },
                            not_metni=sim_veri_not,
                        )
                    except (ValueError, osym_verisi.VeriHatasi) as sim_veri_hata:
                        st.error("Kayıt yazılamadı: %s" % sim_veri_hata)
                    else:
                        log_islem(
                            current_user["id"],
                            "SAVE_RANK_DATA",
                            "%s / %s" % (sim_veri_yil, sim_veri_tur),
                        )
                        set_flash_message(
                            "success",
                            "Referans kaydı yazıldı (%s / %s)."
                            % (sim_veri_yil, sim_veri_tur),
                        )
                        st.rerun()

            if sim_kaynak_tablosu:
                with st.form("sim_veri_sil_formu"):
                    st.markdown("**Referans kaydı sil**")
                    sim_sil_secenekleri = [
                        "%s / %s" % (kayit["yil"], kayit["puan_turu"])
                        for kayit in sim_kaynak_tablosu
                    ]
                    sim_sil_secim = st.selectbox(
                        "Silinecek kayıt",
                        sim_sil_secenekleri,
                        key="sim_sil_secim",
                    )
                    if st.form_submit_button("🗑️ Seçili kaydı sil"):
                        sim_sil_yil, sim_sil_tur = sim_sil_secim.split(" / ")
                        osym_verisi.kayit_sil(sim_sil_yil, sim_sil_tur)
                        log_islem(
                            current_user["id"],
                            "DELETE_RANK_DATA",
                            sim_sil_secim,
                        )
                        set_flash_message(
                            "info",
                            "Referans kaydı silindi: %s" % sim_sil_secim,
                        )
                        st.rerun()










