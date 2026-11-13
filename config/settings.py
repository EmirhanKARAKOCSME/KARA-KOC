"""Uygulama geneli yapılandırma (yol, saat dilimi, takvim sabitleri).

Bu modül **yan etkisizdir**: import edilmesi veritabanına yazmaz, arayüz
çalıştırmaz. Yalnızca diğer katmanların paylaştığı ayarları tanımlar.
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Proje kökü: dosya konumundan türetilir (çalışma dizinine bağımlı değildir).
PROJE_KOKU = Path(__file__).resolve().parent.parent

# --- Veritabanı -------------------------------------------------------------
DB_DOSYA_ADI = "yks_veritabani.db"

# Testlerin / yönetici araçlarının gerçek dosyaya dokunmadan çalışabilmesi
# için ortam değişkeniyle geçici bir veritabanına yönlendirilebilir.
ORTAM_DB_DEGISKENI = "KARAKOC_DB_PATH"

# Şema/migration kodu değiştiğinde bu sürüm artırılır; bootstrap cache anahtarı
# bu değeri içerir (bkz. config/database.py).
DB_BOOTSTRAP_SURUMU = "5"


def streamlit_secret_oku(anahtar):
    """Streamlit `secrets` içinden bir değer okur (yoksa/ortam yoksa None).

    Bu fonksiyon yan etkisizdir: Streamlit çalışma zamanı yoksa veya
    `secrets.toml` tanımlı değilse sessizce `None` döner. Böylece testler ve
    yerel geliştirme Streamlit kurulumu olmadan da çalışır.
    """
    try:
        import streamlit as st

        # Streamlit çalışma zamanı dışında `st.secrets` erişimi hata verir.
        if not st.runtime.exists():
            return None
        return st.secrets.get(anahtar)
    except Exception:  # noqa: BLE001 - secrets yoksa varsayılana düşülür
        return None


# --- Yönetici kimlik bilgisi -------------------------------------------------
# Parola/anahtar KODA YAZILMAZ. Bu değerler ortam değişkeninden veya
# Streamlit secrets'tan okunur; yoksa güvenli varsayılan davranış uygulanır.
ADMIN_KULLANICI_DEGISKENI = "KARAKOC_ADMIN_USERNAME"
ADMIN_PAROLA_DEGISKENI = "KARAKOC_ADMIN_PASSWORD"
ADMIN_VARSAYILAN_KULLANICI = "admin"


def _secrets_dosyasi_oku(anahtar):
    """Yerel `.streamlit/secrets.toml` dosyasından değer okur (bare mod).

    Streamlit çalışma zamanı dışında `st.secrets` erişilemez; yerel geliştirme
    ve bootstrap betikleri aynı dosyadan okur. Bu dosya Git'e eklenmez.
    """
    yol = PROJE_KOKU / ".streamlit" / "secrets.toml"
    if not yol.exists():
        return None
    try:
        import tomllib

        with open(yol, "rb") as dosya:
            veri = tomllib.load(dosya)
        return veri.get(anahtar)
    except Exception:  # noqa: BLE001 - eksik/bozuk secrets uygulamayı durdurmaz
        return None


def _ayar_oku(anahtar):
    """Ortam değişkeni → Streamlit secrets → yerel secrets dosyası."""
    ortam = os.environ.get(anahtar)
    if ortam:
        return ortam
    return streamlit_secret_oku(anahtar) or _secrets_dosyasi_oku(anahtar)


def admin_kimlik_bilgisi() -> dict:
    """Yönetici hesabının yapılandırmasını döndürür (parola koda gömülmez).

    `parola` None ise uygulama bilinen bir varsayılan parola OLUŞTURMAZ;
    yönetici hesabı pasif bırakılır veya mevcut güvenli parola korunur.
    """
    kullanici = _ayar_oku(ADMIN_KULLANICI_DEGISKENI)
    parola = _ayar_oku(ADMIN_PAROLA_DEGISKENI)
    return {
        "kullanici_adi": str(kullanici).strip() or ADMIN_VARSAYILAN_KULLANICI,
        "parola": str(parola) if parola else None,
        "parola_tanimli": bool(parola),
    }


def db_yolu_kaynagi() -> str:
    """Aktif DB yolunun nereden geldiğini döndürür: 'env' | 'secrets' | 'varsayilan'."""
    if os.environ.get(ORTAM_DB_DEGISKENI):
        return "env"
    if streamlit_secret_oku(ORTAM_DB_DEGISKENI):
        return "secrets"
    return "varsayilan"


def varsayilan_db_yolu() -> str:
    """Uygulamanın kullanacağı veritabanı dosyasının mutlak yolu.

    Öncelik sırası:
    1. `KARAKOC_DB_PATH` ortam değişkeni (yerel geliştirme / testler).
    2. Streamlit `secrets` içindeki `KARAKOC_DB_PATH` (bulut yayını).
    3. Proje kökündeki varsayılan `yks_veritabani.db` dosyası.

    Kalıcı disk sunucusunda (Örn. VPS / Streamlit Community Cloud'a bağlı
    kalıcı volume) 1. veya 2. seçenek kalıcı bir yola işaret etmelidir.
    Streamlit Community Cloud'un geçici dosya alanı kalıcı DEĞİLDİR.
    """
    ortam = os.environ.get(ORTAM_DB_DEGISKENI)
    if ortam:
        return str(Path(ortam).expanduser().resolve())
    secret = streamlit_secret_oku(ORTAM_DB_DEGISKENI)
    if secret:
        return str(Path(str(secret)).expanduser().resolve())
    return str(PROJE_KOKU / DB_DOSYA_ADI)


# Geçici dosya alanı olduğu bilinen yol parçaları (bulut konteynerleri).
_GECICI_YOL_ISARETLERI = (
    "/tmp",
    "/var/tmp",
    "\\temp\\",
    "\\appdata\\local\\temp",
    "/var/folders",  # macOS geçici dizinleri
)


def veritabani_kalicilik_durumu(db_yolu=None) -> dict:
    """Aktif veritabanının kalıcılık riskini raporlar (yan etkisiz).

    Dönen sözlük arayüz/admin panelinde uyarı göstermek içindir. Bir yolun
    "geçici" olması kesin kanıt değildir; yalnızca bilinen geçici dizin
    kalıplarına göre ihtimal bildirir. Yayın güvenliği için DB yolu mutlaka
    kalıcı bir diske işaret etmelidir.
    """
    from pathlib import Path

    yol = Path(db_yolu or varsayilan_db_yolu())
    metin = str(yol)
    kucuk = metin.lower()
    gecici = any(isaret in kucuk for isaret in _GECICI_YOL_ISARETLERI)
    return {
        "yol": metin,
        "kaynak": db_yolu_kaynagi(),
        "gecici_olabilir": gecici,
        "kalici_gorunuyor": not gecici,
        "uyari": (
            "Veritabanı geçici bir dizinde görünüyor; sunucu yeniden "
            "başlarsa öğrenci verisi kaybolabilir."
            if gecici
            else ""
        ),
    }


# --- Varlıklar --------------------------------------------------------------
ASSETS_KLASORU = PROJE_KOKU / "assets"
CSS_YOLU = ASSETS_KLASORU / "style.css"

# --- Zaman dilimi (UTC+3 Türkiye saati) -------------------------------------
TR_TZ = timezone(timedelta(hours=3))


def get_tr_now():
    """Türkiye saatiyle şu anki zaman."""
    return datetime.now(TR_TZ)


# --- Takvim ----------------------------------------------------------------
# Hafta Pazartesi başlar; planlayıcı ve arayüz aynı sırayı kullanır.
GUN_ADLARI_LISTE = [
    "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"
]
