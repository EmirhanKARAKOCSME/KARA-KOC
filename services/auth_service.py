"""Kimlik doğrulama servisi (FAZ F).

PBKDF2-HMAC-SHA256 + salt yaklaşımı **değiştirilmedi**; yalnızca
`main.py` içindeki tanımlar buraya taşındı. Bu modül Streamlit'e
bağımlı değildir."""

from datetime import datetime
import hashlib
import os

from config.database import get_connection
from config.settings import get_tr_now


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
