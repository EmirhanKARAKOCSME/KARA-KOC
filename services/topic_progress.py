"""Konu takibi servisi: öğrenci müfredatı, mikro/alt konu ilerlemesi,
aylık hedef ve açılabilir konular.

Tablolar `init_alt_konu_db()` ile idempotent biçimde hazırlanır."""

import sqlite3
from typing import Dict, List, Set

import pandas as pd
import streamlit as st

from config.database import get_connection
from config.settings import get_tr_now
from data.curriculum import mufredat_klasik, mufredat_maarif_9
from data.prerequisites import ON_KOSULLAR
from data.subtopics import MIKRO_ALT_KONULAR
from data.weights_and_times import SINIF_SEVIYE_SKORU, SORU_AGIRLIKLARI
from services import task_steps


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


def konu_soru_kotasi(makro, mikro_sayisi, aktif_yanlis=0):
    """Konunun toplam soru kotası (5'in katı, 40-300 arası).

    TEK kaynak: planlama motoru (`program_motoru.konu_soru_hedefi_hesapla`) ve
    biten konu tespiti (`biten_konulari_yukle`) aynı formülü kullanır.
    """
    makro_kredi = SORU_AGIRLIKLARI.get(makro, 10.0)
    try:
        mikro_adet = max(1, int(mikro_sayisi or 1))
    except (TypeError, ValueError):
        mikro_adet = 1
    try:
        yanlis = max(0, int(aktif_yanlis or 0))
    except (TypeError, ValueError):
        yanlis = 0
    mikro_kredi = makro_kredi / mikro_adet
    zorluk = 1.0 + min(0.3, 0.05 * yanlis)
    hedef = int(round(mikro_kredi * 10.0 * zorluk))
    hedef = max(40, min(300, hedef))
    return int(round(hedef / 5.0) * 5)


def _mufredat_konu_indeksi(aktif_mufredat):
    """{(ders, mikro): (makro, mikro_sayisi)} indeksi (müfredat sırası korunur)."""
    indeks = {}
    for ders, gruplar in (aktif_mufredat or {}).items():
        if not isinstance(gruplar, dict):
            continue
        for makro, mikrolar in gruplar.items():
            if not isinstance(mikrolar, list):
                continue
            adet = len([m for m in mikrolar if m])
            for mikro in mikrolar:
                if mikro:
                    indeks.setdefault((ders, mikro), (makro, max(1, adet)))
    return indeks


def biten_konulari_yukle(ogrenci_id, aktif_mufredat=None, db_path=None):
    """%100 tamamlanmış (biten) konular: {(ders, mikro_konu)}.

    KURAL: biten konu rutin çalışma programına SONSUZA KADAR eklenmez. Konu
    yalnızca denemede yanlış çıkarsa sınırlı bir "Eksik Kapatma" görevi olarak
    plana girer ve o hedef tamamlanınca programdan düşer.

    Bir konu "biten" sayılır ancak ve ancak:
      1) öğrenme/tekrar adımları bitmiş ve gerçek soru hedefi dolmuş
         (`task_steps.mikro_konu_ilerleme.tamamlandi`), veya
      2) alt başlığı olmayan konularda konu 'Biliyorum' işaretlenmiş ve gerçek
         çözülen soru `konu_soru_kotasi` hedefini karşılamış.

    Alt başlığı olan bir konu, alt başlıklarının TAMAMI tamamlanmadan biten
    sayılmaz (eksik kalan mikro konu planlanmaya devam eder).

    Tablolar yoksa (eski veritabanı) boş küme döner; planlama bozulmaz.
    """
    try:
        oid = int(ogrenci_id)
    except (TypeError, ValueError):
        return set()
    try:
        tamamlanan = task_steps.mikro_tamamlananlar(oid)
    except Exception:  # noqa: BLE001 - tablo yoksa tespit kapalı
        tamamlanan = set()
    try:
        with get_connection(db_path) as c:
            bilinen = c.execute(
                "SELECT ders, makro_konu, mikro_konu FROM konu_durumlari_detay"
                " WHERE ogrenci_id = ? AND durum = 'Biliyorum'",
                (oid,),
            ).fetchall()
            gercek = {
                (satir[0], satir[1]): int(satir[2] or 0)
                for satir in c.execute(
                    "SELECT ders, mikro_konu, COALESCE(SUM(cozulen_soru), 0)"
                    " FROM calisma_oturumlari WHERE ogrenci_id = ? AND durum = ?"
                    " GROUP BY ders, mikro_konu",
                    (oid, "Tamamlandı"),
                ).fetchall()
            }
    except Exception:  # noqa: BLE001 - tablolar yoksa boş küme
        return set()

    indeks = _mufredat_konu_indeksi(aktif_mufredat)
    makro_haritasi = {
        (str(ders), str(mikro)): makro
        for ders, makro, mikro in bilinen
        if ders and mikro
    }
    adaylar = set(makro_haritasi)
    adaylar.update({(str(d), str(m)) for d, m, _alt in tamamlanan if d and m})

    sonuc = set()
    for ders, mikro in adaylar:
        alts = [a for a in (MIKRO_ALT_KONULAR.get(mikro) or []) if a]
        if alts:
            # Tüm alt başlıklar kapanmış olmalı.
            if not all((ders, mikro, alt) in tamamlanan for alt in alts):
                continue
        else:
            makro, adet = indeks.get(
                (ders, mikro), (makro_haritasi.get((ders, mikro)), 1)
            )
            if int(gercek.get((ders, mikro), 0) or 0) < konu_soru_kotasi(makro, adet):
                continue
        sonuc.add((ders, mikro))
    # KURAL 2 (v2.1): pekiştirme adımı bekleyen konu %100 (biten) sayılmaz;
    # ilerlemesi %50'de kilitlidir. Pekiştirme tamamlanınca normal akış döner.
    try:
        bekleyen = task_steps.pekistirme_bekleyenler(oid)
    except Exception:  # noqa: BLE001 - tablo yoksa kilit uygulanmaz
        bekleyen = set()
    if bekleyen and sonuc:
        sonuc = {k for k in sonuc if k not in bekleyen}
    return sonuc


def init_alt_konu_db(db_path=None):
    with get_connection(db_path) as conn:
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


def makro_unite_ilerleme_durumu(ogrenci_id, ders, makro_unite, mufredat):
    """Bir makro ünitenin tamamlanma yüzdesi (0-100, tam sayı).

    v2.3 (FAZ 1.4): görev tamamlanınca bildirimde "Ünite İlerlemesi:
    %33 ➔ %67" göstermek için kullanılır. Ünitedeki mikro konuların %100
    biten oranına dayanır; tablo yoksa 0 döner (planlama/arayüz bozulmaz).
    """
    try:
        mikrolar = ((mufredat or {}).get(ders) or {}).get(makro_unite) or []
    except Exception:  # noqa: BLE001
        mikrolar = []
    if not mikrolar:
        return 0
    try:
        biten = biten_konulari_yukle(ogrenci_id, mufredat)
    except Exception:  # noqa: BLE001
        biten = set()
    tamam = sum(1 for m in mikrolar if (ders, m) in biten)
    return int(round(tamam / float(len(mikrolar)) * 100))



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
