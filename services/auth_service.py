"""Kimlik doğrulama ve sunucu taraflı yetkilendirme servisi.

Parola hash'i:
- Yeni kayıtlar **scrypt** (bellek-zorlu KDF; Argon2id'ye denk güvenli) ile
  `scrypt$tuz$hash` biçiminde saklanır.
- Eski PBKDF2-HMAC-SHA256 kayıtları (`tuz:hash`) geriye dönük doğrulanmaya
  devam eder; böylece mevcut öğrenci hesapları bozulmaz.
- Düz metin parola hiçbir zaman saklanmaz veya loglanmaz.

Yetkilendirme:
- `rol` değeri **sunucu tarafındaki veritabanından** okunur; `st.session_state`
  içindeki rol tek başına yetki kanıtı kabul edilmez.
- Yetkisiz admin işlem girişimleri `sistem_loglari`'na yazılır (parola yok).

Bu modül Streamlit'e bağımlı değildir."""

from datetime import datetime
import hashlib
import hmac
import os

from config.database import get_connection, log_islem
from config.settings import get_tr_now

# scrypt parametreleri (bellek-zorlu; makul pilot sunucu maliyeti).
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32


def hash_password(password: str) -> str:
    """Parolayı güvenli biçimde hash'ler (scrypt + rastgele tuz)."""
    salt = os.urandom(16)
    turetilen = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    return "scrypt$%s$%s" % (salt.hex(), turetilen.hex())


def _pbkdf2_dogrula(stored_password_hash: str, provided_password: str) -> bool:
    """Eski PBKDF2 (`tuz:hash`) kayıtlarını doğrular (geriye dönük uyum)."""
    if ":" not in stored_password_hash:
        return False
    try:
        salt_hex, hash_hex = stored_password_hash.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        stored_pwd_hash = bytes.fromhex(hash_hex)
        new_pwd_hash = hashlib.pbkdf2_hmac(
            "sha256", provided_password.encode("utf-8"), salt, 100000
        )
        return hmac.compare_digest(stored_pwd_hash, new_pwd_hash)
    except Exception:  # noqa: BLE001
        return False


def verify_password(stored_password_hash: str, provided_password: str) -> bool:
    """Kayıtlı hash ile verilen parolayı sabit zamanlı karşılaştırır."""
    if not stored_password_hash or provided_password is None:
        return False
    if stored_password_hash.startswith("scrypt$"):
        try:
            _, salt_hex, hash_hex = stored_password_hash.split("$", 2)
            salt = bytes.fromhex(salt_hex)
            beklenen = bytes.fromhex(hash_hex)
            yeni = hashlib.scrypt(
                provided_password.encode("utf-8"),
                salt=salt,
                n=_SCRYPT_N,
                r=_SCRYPT_R,
                p=_SCRYPT_P,
                dklen=_SCRYPT_DKLEN,
            )
            return hmac.compare_digest(beklenen, yeni)
        except Exception:  # noqa: BLE001
            return False
    return _pbkdf2_dogrula(stored_password_hash, provided_password)


# ==============================================================================
# SUNUCU TARAFLI YETKİLENDİRME
# ==============================================================================
def kullanici_rolu(ogrenci_id):
    """Kullanıcının rolünü VERİTABANINDAN okur.

    Hesap yoksa veya `hesap_durumu` 'Aktif' değilse `None` döner. Böylece
    oturumda tutulan (ve arayüzden etkilenebilecek) rol değeri tek başına
    yetki kanıtı sayılmaz.
    """
    try:
        oid = int(ogrenci_id)
    except (TypeError, ValueError):
        return None
    if oid <= 0:
        return None
    with get_connection() as conn:
        satir = conn.execute(
            "SELECT rol, hesap_durumu FROM ogrenciler WHERE id = ?", (oid,)
        ).fetchone()
    if not satir:
        return None
    rol, durum = satir[0], satir[1]
    if (durum or "").strip() != "Aktif":
        return None
    return (rol or "").strip() or None


def admin_mi(ogrenci_id) -> bool:
    """Kullanıcı gerçekten (DB'de) yönetici mi?"""
    return kullanici_rolu(ogrenci_id) == "admin"


def yetki_dogrula(ogrenci_id, islem="yonetici islemi") -> bool:
    """Hassas admin işlemleri için sunucu taraflı yetki kontrolü.

    Yetkisiz girişim reddedilir ve `sistem_loglari`'na yazılır. Log'a parola
    veya gizli bilgi YAZILMAZ; yalnızca işlem adı ve kullanıcı kimliği.
    """
    if admin_mi(ogrenci_id):
        return True
    try:
        log_islem(ogrenci_id, "YETKISIZ_ERISIM", "Reddedildi: %s" % str(islem)[:120])
    except Exception:  # noqa: BLE001 - log yazımı akışı durdurmaz
        pass
    return False


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
