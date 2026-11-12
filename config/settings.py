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
DB_BOOTSTRAP_SURUMU = "4"


def varsayilan_db_yolu() -> str:
    """Uygulamanın kullanacağı veritabanı dosyasının mutlak yolu."""
    ortam = os.environ.get(ORTAM_DB_DEGISKENI)
    if ortam:
        return str(Path(ortam).expanduser().resolve())
    return str(PROJE_KOKU / DB_DOSYA_ADI)


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
