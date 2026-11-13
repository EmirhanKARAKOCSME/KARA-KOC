"""Kontrollü ilerleme denetimi ve bakım işlemleri.

Bu modül v2.6'da eklenen **tek seferlik / isteğe bağlı** bakım aracıdır:

- `ilerleme_denetimi`: veritabanını SALT OKUNUR açar; negatif, aralık dışı
  veya mantıksal olarak bozuk ilerleme kayıtlarını raporlar.
- `ilerleme_onarimi`: varsayılan olarak **dry-run** çalışır. Yalnızca açıkça
  `uygula=True` verilirse ve önce zaman damgalı yedek alınırsa yazar.
  Onarım yalnızca bariz bozulmaları (negatif sayı, 0/1 dışı bayrak) düzeltir;
  pozitif/geçerli değerleri DEĞİŞTİRMEZ, kayıt SİLMEZ, toplu sıfırlama YAPMAZ.

Komut satırı (varsayılan: rapor):

    python -m services.maintenance --db yks_veritabani.db
    python -m services.maintenance --db yks_veritabani.db --uygula
"""
import argparse
import sqlite3
import sys

from config.database import db_yolu, zaman_damgali_yedek


def _tablo_var_mi(conn, tablo):
    try:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (tablo,),
        ).fetchone() is not None
    except sqlite3.Error:
        return False


def _kolonlar(conn, tablo):
    try:
        return {satir[1] for satir in conn.execute("PRAGMA table_info(%s)" % tablo)}
    except sqlite3.Error:
        return set()


def _satirlar(conn, sorgu, params=()):
    try:
        return [tuple(s) for s in conn.execute(sorgu, params).fetchall()]
    except sqlite3.Error:
        return []


def ilerleme_denetimi(db_path=None) -> dict:
    """Bozuk ilerleme kayıtlarını SALT OKUNUR biçimde raporlar.

    Canlı veriye yazmaz. Dönen sözlükte her bulgu ayrı listelenir; düzeltme
    kararı kullanıcıya aittir.
    """
    yol = db_yolu(db_path)
    rapor = {
        "veritabani": yol,
        "negatif_hedef": [],
        "negatif_cozulen": [],
        "gecersiz_bayrak": [],
        "aralik_disi_oran": [],
        "negatif_program_hedefi": [],
        "negatif_konu_soru": [],
        "mukerrer_mikro_kayit": [],
        "toplam_sorun": 0,
    }
    conn = sqlite3.connect("file:%s?mode=ro" % yol, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if _tablo_var_mi(conn, "mikro_konu_ilerleme"):
            rapor["negatif_hedef"] = _satirlar(
                conn,
                "SELECT id, ogrenci_id, ders, mikro_konu, alt_konu, hedef_soru"
                " FROM mikro_konu_ilerleme WHERE hedef_soru < 0",
            )
            rapor["negatif_cozulen"] = _satirlar(
                conn,
                "SELECT id, ogrenci_id, ders, mikro_konu, alt_konu,"
                " cozulen_soru, guncelleme_zamani FROM mikro_konu_ilerleme"
                " WHERE cozulen_soru < 0",
            )
            rapor["gecersiz_bayrak"] = _satirlar(
                conn,
                "SELECT id, ogrenci_id, ders, mikro_konu, alt_konu,"
                " ogrenme_tamam, tamamlandi FROM mikro_konu_ilerleme"
                " WHERE ogrenme_tamam NOT IN (0, 1) OR tamamlandi NOT IN (0, 1)",
            )
            rapor["mukerrer_mikro_kayit"] = _satirlar(
                conn,
                "SELECT ogrenci_id, ders, mikro_konu, COALESCE(alt_konu,''),"
                " COUNT(*) AS adet FROM mikro_konu_ilerleme"
                " GROUP BY 1, 2, 3, 4 HAVING adet > 1",
            )
        if _tablo_var_mi(conn, "calisma_programi_gorevler"):
            rapor["negatif_program_hedefi"] = _satirlar(
                conn,
                "SELECT id, ogrenci_id, ders, mikro_konu, hedef_soru"
                " FROM calisma_programi_gorevler WHERE hedef_soru < 0",
            )
        if _tablo_var_mi(conn, "konu_soru_ilerleme"):
            kolonlar = _kolonlar(conn, "konu_soru_ilerleme")
            if "cozulen_soru" in kolonlar:
                rapor["negatif_konu_soru"] = _satirlar(
                    conn,
                    "SELECT id, ogrenci_id, ders, mikro_konu, cozulen_soru"
                    " FROM konu_soru_ilerleme WHERE cozulen_soru < 0",
                )
        if _tablo_var_mi(conn, "kamp_mikro_kayitlari"):
            rapor["aralik_disi_oran"] = _satirlar(
                conn,
                "SELECT id, ogrenci_id, ders, mikro_konu, basari_orani"
                " FROM kamp_mikro_kayitlari"
                " WHERE basari_orani < 0 OR basari_orani > 100",
            )
    finally:
        conn.close()


    rapor["toplam_sorun"] = sum(
        len(deger) for deger in rapor.values() if isinstance(deger, list)
    )
    return rapor


def ilerleme_onarimi(db_path=None, uygula=False) -> dict:
    """Bariz bozulmaları düzeltir (varsayılan: yalnızca plan/dry-run).

    Kurallar:
      - Yalnızca `uygula=True` iken yazar; önce zaman damgalı yedek alınır.
      - Negatif `hedef_soru` / `cozulen_soru` ➔ 0.
      - `ogrenme_tamam` / `tamamlandi` yalnızca 0/1'e sıkıştırılır.
      - `basari_orani` yalnızca 0–100 aralığına sıkıştırılır.
      - Pozitif değerler, geçerli kayıtlar ve mükerrerler DEĞİŞTİRİLMEZ.
    """
    rapor = ilerleme_denetimi(db_path)
    plan = {
        "negatif_hedef": len(rapor["negatif_hedef"]),
        "negatif_cozulen": len(rapor["negatif_cozulen"]),
        "gecersiz_bayrak": len(rapor["gecersiz_bayrak"]),
        "aralik_disi_oran": len(rapor["aralik_disi_oran"]),
        "negatif_program_hedefi": len(rapor["negatif_program_hedefi"]),
        "negatif_konu_soru": len(rapor["negatif_konu_soru"]),
        "mukerrer_mikro_kayit": len(rapor["mukerrer_mikro_kayit"]),
    }
    sonuc = {
        "dry_run": not uygula,
        "plan": plan,
        "veritabani": rapor["veritabani"],
        "yedek": None,
        "degisen_satir": 0,
    }
    if not uygula:
        return sonuc

    yedek = zaman_damgali_yedek(db_path=db_path)
    sonuc["yedek"] = yedek.get("yol")
    conn = sqlite3.connect(db_yolu(db_path), timeout=20)
    try:
        with conn:
            toplam = 0
            if rapor["negatif_hedef"]:
                cur = conn.execute(
                    "UPDATE mikro_konu_ilerleme SET hedef_soru = 0"
                    " WHERE hedef_soru < 0"
                )
                toplam += cur.rowcount or 0
            if rapor["negatif_cozulen"]:
                cur = conn.execute(
                    "UPDATE mikro_konu_ilerleme SET cozulen_soru = 0"
                    " WHERE cozulen_soru < 0"
                )
                toplam += cur.rowcount or 0
            if rapor["gecersiz_bayrak"]:
                cur = conn.execute(
                    "UPDATE mikro_konu_ilerleme SET"
                    " ogrenme_tamam = CASE WHEN ogrenme_tamam = 1 THEN 1 ELSE 0 END,"
                    " tamamlandi = CASE WHEN tamamlandi = 1 THEN 1 ELSE 0 END"
                    " WHERE ogrenme_tamam NOT IN (0, 1)"
                    " OR tamamlandi NOT IN (0, 1)"
                )
                toplam += cur.rowcount or 0
            if rapor["aralik_disi_oran"]:
                cur = conn.execute(
                    "UPDATE kamp_mikro_kayitlari SET basari_orani ="
                    " MAX(0, MIN(100, basari_orani))"
                    " WHERE basari_orani < 0 OR basari_orani > 100"
                )
                toplam += cur.rowcount or 0
            if rapor["negatif_program_hedefi"]:
                cur = conn.execute(
                    "UPDATE calisma_programi_gorevler SET hedef_soru = 0"
                    " WHERE hedef_soru < 0"
                )
                toplam += cur.rowcount or 0
            if rapor["negatif_konu_soru"]:
                cur = conn.execute(
                    "UPDATE konu_soru_ilerleme SET cozulen_soru = 0"
                    " WHERE cozulen_soru < 0"
                )
                toplam += cur.rowcount or 0
        sonuc["degisen_satir"] = toplam
    finally:
        conn.close()
    return sonuc


def _yazdir(rapor):
    print("Veritabanı: %s" % rapor["veritabani"])
    basliklar = {
        "negatif_hedef": "Negatif hedef_soru",
        "negatif_cozulen": "Negatif cozulen_soru",
        "gecersiz_bayrak": "0/1 dışı bayrak",
        "aralik_disi_oran": "0–100 dışı başarı oranı",
        "negatif_program_hedefi": "Negatif program hedefi",
        "negatif_konu_soru": "Negatif konu soru ilerlemesi",
        "mukerrer_mikro_kayit": "Mükerrer mikro kayıt (yalnızca rapor)",
    }
    for anahtar, etiket in basliklar.items():
        kayitlar = rapor.get(anahtar) or []
        print("- %s: %d" % (etiket, len(kayitlar)))
        for satir in kayitlar[:20]:
            print("    %s" % (satir,))
    print("TOPLAM BULGU: %d" % rapor["toplam_sorun"])


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="KARA KOÇ ilerleme denetimi (varsayılan salt okunur)"
    )
    parser.add_argument("--db", default=None, help="Veritabanı yolu")
    parser.add_argument(
        "--uygula", action="store_true",
        help="Bariz bozulmaları düzelt (önce otomatik yedek alınır)",
    )
    args = parser.parse_args(argv)
    if args.uygula:
        sonuc = ilerleme_onarimi(args.db, uygula=True)
        print("Yedek: %s" % sonuc["yedek"])
        print("Değişen satır: %s" % sonuc["degisen_satir"])
        print("Plan: %s" % sonuc["plan"])
    rapor = ilerleme_denetimi(args.db)
    _yazdir(rapor)
    return 0 if rapor["toplam_sorun"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
