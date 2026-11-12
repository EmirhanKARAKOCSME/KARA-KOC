"""Haftalık program motoru (eski + v2) ve planlama yardımcıları.

Akış: planlama bağlamı -> `haftalik_program_gorevleri_uret()` ->
`services/programs` üzerinden sürümlü görev kaydı. Eski motor
`eski_program_motoru_gorevleri()` yalnızca v2 motoru görev
üretemediğinde yedek (fallback) olarak çalışır; bu davranış korunur."""

from datetime import datetime, timedelta

import pandas as pd

from config.database import get_connection, log_islem
from config.settings import GUN_ADLARI_LISTE, get_tr_now
from data.pedagogy import get_konu_pedagoji_turu
from data.prerequisites import ON_KOSULLAR
from data.subtopics import MIKRO_ALT_KONULAR
from data.weights_and_times import KONU_SURELERI_DK, SORU_AGIRLIKLARI
from services import planner
from services import programs as program_service
from services import task_steps
from services import topic_progress
from services.topic_progress import alt_durumlari_yukle


def init_program_motoru_db(db_path=None):
    with get_connection(db_path) as conn:
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


def konu_soru_hedefi_hesapla(makro, mikro_sayisi, aktif_yanlis=0):
    """Konunun kredi puanından türeyen toplam soru kotası (5'in katı, 40-300 arası).

    Formülün TEK kaynağı `topic_progress.konu_soru_kotasi`'dır; biten konu
    tespiti de aynı hedefi kullanır.
    """
    return topic_progress.konu_soru_kotasi(makro, mikro_sayisi, aktif_yanlis)


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
        # v2.2 (FAZ 3/4.5.4): öğrenilmiş (konu anlatımı bitmiş) konular. Bu
        # konular %0 sayılmaz; sonraki planda soru çözümü aşamasına geçer.
        ogrenilmis = set()
        try:
            df_o = pd.read_sql_query(
                "SELECT ders, mikro_konu FROM mikro_konu_ilerleme"
                " WHERE ogrenci_id = ? AND ogrenme_tamam = 1",
                c, params=(ogrenci_id,),
            )
            ogrenilmis |= {
                (r["ders"], r["mikro_konu"]) for _, r in df_o.iterrows()
            }
        except Exception:  # noqa: BLE001 - tablo yoksa boş
            pass
        try:
            df_ka = pd.read_sql_query(
                "SELECT ders, mikro_konu FROM calisma_programi_gorevler"
                " WHERE ogrenci_id = ? AND gorev_tipi = 'konu_anlatimi'"
                " AND durum = 1",
                c, params=(ogrenci_id,),
            )
            ogrenilmis |= {
                (r["ders"], r["mikro_konu"]) for _, r in df_ka.iterrows()
            }
        except Exception:  # noqa: BLE001 - kolon/tablo yoksa boş
            pass
    return {
        "bilinen_mikro": set(df_b["mikro_konu"].tolist()),
        "ogrenilmis_konular": ogrenilmis,
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
    kurallar = ON_KOSULLAR

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
                    "📌 Konu Anlatımı (Video/Kaynak) ➔ "
                    f"{mi}: izle / oku ve kısa özet çıkar, "
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
    kurallar = ON_KOSULLAR

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
                        f"📌 Konu Anlatımı (Video/Kaynak) ➔ {mi} ➔ mikro konu: "
                        f"{liste_str}. İzle / oku ve 3-4 satır not çıkar; "
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
                    bas = (
                        "📌 Konu Anlatımı (Video/Kaynak) ➔ "
                        f"{mi}: izle / oku ve kısa özet çıkar, "
                    )
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


def _gorevleri_zenginlestir(gorevler, ogrenci_id, biten_konular=None):
    """FAZ 5B/5D: görevleri MİKRO KONU bazında böler; checklist + süre ekler.

    FAZ 5D: Fallback motorları (alt başlık / soru kotalı / temel) ana konu
    seviyesinde görev üretse bile buradan geçen her görev tek mikro konuya
    ayrılır. Böylece hangi motor çalışırsa çalışsın hiyerarşi aynıdır:
    ders → ana konu → mikro konu → checklist. Bölme idempotenttir; zaten tek
    mikro konu içeren görev olduğu gibi kalır.

    `biten_konular`: (ders, mikro konu) çiftleri. %100 biten konuların RUTİN
    kartları (KURAL 1) ve günlük farklı ders sayısı sınırı (KURAL 4) yedek
    motorlarda da uygulanır; deneme yanlışından doğan "Eksik Kapatma" kartları
    korunur.
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
    # KURAL 1: biten konuların rutin kartları programa dönmez (telafi kartları
    # korunur). Biten kümesi verilmezse deneme/pekiştirme kartları olduğu gibi
    # kalır (geriye dönük uyum).
    if biten_konular:
        sonuc = planner.biten_konu_suzgeci(sonuc, biten_konular)
        # Aynı konu için daha önce açılmış telafi kartı varsa (tamamlanmış ya
        # da devirde) yeniden üretilmez.
        kapsanan = planner.telafi_kapsanan_konular(
            _planlama_onceki_gorevler(ogrenci_id)
        )
        if kapsanan:
            sonuc = [
                gorev
                for gorev in sonuc
                if not (
                    planner.telafi_gorevi_mi(gorev)
                    and (str(gorev.get("ders")), str(gorev.get("mikro_konu")))
                    in kapsanan
                )
            ]
    # KURAL 4: aynı güne müsaitliğe göre sınırlı sayıda farklı ders atanır.
    try:
        musaitlik = planner.musaitlik_yukle(ogrenci_id)
    except Exception:  # noqa: BLE001 - müsaitlik okunamazsa varsayılan
        musaitlik = {}
    # KURAL 4: günlük farklı ders limiti + tek ders 150 dk / 90 soru tavanı.
    sonuc = planner.gunluk_ders_doldur(sonuc, musaitlik)
    # Tekilleştirme: aynı gün + aynı ders + aynı mikro konu/görev tek kez.
    # Rutin görevler (Günlük Paragraf) gün başına max_daily_limit slot alır.
    # Ana konu bazlı kısıt burada KAPALI: fallback motoru ana konuyu mikro
    # konulara bölerek aynı güne birden çok meşru kart yazabilir (FAZ 5D).
    return planner.gunluk_tekillestir(sonuc, ana_konu_tekillestir=False)


def _gercek_cozulen_haritasi(ogrenci_id):
    """Ders+mikro bazında GERÇEK çözülen soru (yalnızca tamamlanmış oturumlar)."""
    sonuc = {}
    try:
        with get_connection(db_path) as conn:
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
        with get_connection(db_path) as conn:
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
    """Alarm konularını öncelik sırasıyla düz listeye çevirir.

    "Temel Eksik" uyarılarında `hedef_konu` ve `eksikler` de taşınır; böylece
    planlayıcı eksik ön koşulları TEK görev kartında birleştirir.
    """
    sonuc = []
    for kat in ("siyah", "kirmizi", "mor", "turuncu"):
        for alarm in (alarmlar_db or {}).get(kat, []) or []:
            ders = alarm.get("ders")
            konu = alarm.get("konu")
            if ders and konu:
                sonuc.append({
                    "ders": ders,
                    "konu": konu,
                    "seviye": kat,
                    "hedef_konu": alarm.get("hedef_konu"),
                    "eksikler": list(alarm.get("eksikler") or []),
                })
    return sonuc


def _deneme_yanlislari_haritasi(ogrenci_id):
    """KURAL 1 (v2.1): biten konu telafisi için deneme yanlışları (okuma).

    Her kayıt: `{'ders', 'konu', 'deneme_id', 'yanlis_adedi'}`. `deneme_id`'si
    olmayan eski kayıtlar alınmaz; telafi yalnızca GERÇEK bir denemeye bağlanır.
    """
    sonuc = []
    try:
        with get_connection(db_path) as conn:
            satirlar = conn.execute(
                "SELECT COALESCE(ders, '') AS ders,"
                " COALESCE(konu_adi, '') AS konu, deneme_id,"
                " COALESCE(yanlis_adedi, 0) AS yanlis"
                " FROM deneme_konu_yanlislari"
                " WHERE ogrenci_id = ? AND deneme_id IS NOT NULL"
                " AND (durum IS NULL OR durum = 'Aktif')",
                (ogrenci_id,),
            ).fetchall()
    except Exception:  # noqa: BLE001 - tablo yoksa boş harita (eski DB)
        return sonuc
    for satir in satirlar:
        ders, konu = satir[0], satir[1]
        if not (ders and konu):
            continue
        try:
            deneme_id = int(satir[2] or 0)
            yanlis = int(satir[3] or 0)
        except (TypeError, ValueError):
            continue
        if deneme_id <= 0:
            continue
        sonuc.append({
            "ders": ders,
            "konu": konu,
            "deneme_id": deneme_id,
            "yanlis_adedi": yanlis,
        })
    return sonuc


def _pekistirme_bekleyen(ogrenci_id):
    """KURAL 2 (v2.1): pekiştirme adımı planlanması gereken konular (okuma)."""
    try:
        return task_steps.pekistirme_ihtiyaci(ogrenci_id)
    except Exception:  # noqa: BLE001 - tablo yoksa pekiştirme planlanmaz
        return set()


def _ogrenci_sinif_alan(ogrenci_id):
    """Öğrencinin (sinif_seviyesi, hedef_alan) bilgisini okur (yoksa None)."""
    try:
        with get_connection(db_path) as conn:
            satir = conn.execute(
                "SELECT sinif_seviyesi, hedef_alan FROM ogrenciler WHERE id = ?",
                (ogrenci_id,),
            ).fetchone()
    except Exception:  # noqa: BLE001 - tablo yoksa kısıtlama uygulanmaz
        return None, None
    if not satir:
        return None, None
    return satir[0], satir[1]


def planlama_baglami_olustur(ogrenci_id, aktif_mufredat, alarmlar_db,
                             paragraf_soru=None, referans_tarihi=None):
    """FAZ 5C: akıllı plan motorunun girdilerini hazırlar (yalnızca okuma).

    v2.2: `referans_tarihi` verilirse motor `1 Mayıs` çift motor geçişini bu
    tarihe göre değerlendirir (simülatör/test desteği). Ayrıca öğrencinin
    sınıf seviyesi ve alanı havuza eklenir (FAZ 1 havuz kilidi).
    """
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
    try:
        # KURAL 1: %100 biten konular planlayıcıya açıkça bildirilir.
        biten_konular = topic_progress.biten_konulari_yukle(
            ogrenci_id, aktif_mufredat
        )
    except Exception:  # noqa: BLE001 - tespit yapılamazsa planlama sürer
        biten_konular = set()
    # v2.2 (FAZ 1): sınıf seviyesi + alan havuz kilidi ve referans tarihi.
    sinif_seviyesi, hedef_alan = _ogrenci_sinif_alan(ogrenci_id)
    return {
        "ogrenci_id": ogrenci_id,
        "baslangic": get_tr_now().date(),
        "gun_sayisi": 7,
        "sinif_seviyesi": sinif_seviyesi,
        "alan": hedef_alan,
        "referans_tarihi": referans_tarihi,
        "musaitlik": planner.musaitlik_yukle(ogrenci_id),
        "mufredat": aktif_mufredat,
        "konu_sureleri": KONU_SURELERI_DK,
        "soru_agirliklari": SORU_AGIRLIKLARI,
        "on_kosullar": ON_KOSULLAR,
        "mikro_alt": MIKRO_ALT_KONULAR,
        "bilinen_mikro": set(durum["bilinen_mikro"]),
        # v2.2 (FAZ 3/4.5.4): konu anlatımı bitmiş (öğrenilmiş) konular.
        "ogrenilmis_konular": set(durum.get("ogrenilmis_konular") or ()),
        "gercek_cozulen": _gercek_cozulen_haritasi(ogrenci_id),
        "mikro_cozulen": _gercek_mikro_cozulen_haritasi(ogrenci_id),
        "onceki_gorevler": _planlama_onceki_gorevler(ogrenci_id),
        "paragraf_soru": max(10, int(paragraf_soru or 20)),
        "pedagoji": pedagoji,
        "tamamlanan_altlar": tamamlanan_altlar,
        "alarm_konular": _alarm_konulari(alarmlar_db),
        "biten_konular": biten_konular,
        # KURAL 1 (v2.1): biten konularda YENİ deneme yanlışı tespiti için.
        "deneme_yanlislari": _deneme_yanlislari_haritasi(ogrenci_id),
        # KURAL 2 (v2.1): ilk günü tamamlanmış %0 konular için 24-48 saat
        # sonrasına pekiştirme planlanır.
        "pekistirme_bekleyen": _pekistirme_bekleyen(ogrenci_id),
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
    referans_tarihi=None,
):
    """Motor zinciri: akıllı plan (5C) → alt başlık → soru kotalı → temel.

    Hiçbir aşamada veritabanına yazılmaz veya silinmez; yalnızca görev listesi
    döner. Yazmayı `program_service.program_olustur` tek transaction'da yapar;
    hata olursa hiçbir şey değişmez (eski program aktif kalır).

    v2.2: `referans_tarihi` verilirse `1 Mayıs` çift motor geçişi bu tarihe
    göre değerlendirilir (simülatör/test desteği).
    """
    uyarilar = []
    # v2.2: referans tarihi bağlama iletilir (bağlamda yoksa).
    if plan_baglami is not None and referans_tarihi is not None:
        plan_baglami.setdefault("referans_tarihi", referans_tarihi)
    # KURAL 1: biten (%100) konular yedek motorlarda da rutin plana dönmez.
    biten_konular = set((plan_baglami or {}).get("biten_konular") or ())

    # FAZ 5C: kredi puanı + gerçek ilerleme + günlük kapasiteye dayalı motor
    if plan_baglami:
        try:
            sonuc = planner.plan_uret(plan_baglami)
            if sonuc.get("gorevler"):
                uyarilar.extend(sonuc.get("uyarilar") or [])
                return sonuc["gorevler"], "Akıllı plan", uyarilar
            uyarilar.append("Akıllı plan boş döndü.")
        except Exception as hata:  # noqa: BLE001
            log_islem(ogrenci_id, "PLANNER_FALLBACK", "Akıllı plan: %s" % hata)
            uyarilar.append(
                "Akıllı plan motoru bu hafta kullanılamadı; yedek motorla"
                " plan oluşturuldu."
            )


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
            return (
                _gorevleri_zenginlestir(gorevler, ogrenci_id, biten_konular),
                "Alt başlık motoru",
                uyarilar,
            )
        uyarilar.append("Alt başlık motoru boş plan üretti.")
    except Exception as hata:  # noqa: BLE001 - motor çökse de program korunur
        log_islem(ogrenci_id, "PLANNER_FALLBACK", "Alt başlık motoru: %s" % hata)
        uyarilar.append(
            "Alt başlık motoru bu hafta kullanılamadı; yedek motorla plan"
            " oluşturuldu."
        )


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
                _gorevleri_zenginlestir(gorevler, ogrenci_id, biten_konular),
                "Soru kotalı motor",
                uyarilar,
            )
        uyarilar.append("Soru kotalı motor boş plan üretti.")
    except Exception as hata:  # noqa: BLE001
        log_islem(ogrenci_id, "PLANNER_FALLBACK", "Soru kotalı motor: %s" % hata)
        uyarilar.append(
            "Soru kotalı motor bu hafta kullanılamadı; yedek motorla plan"
            " oluşturuldu."
        )


    gorevler = eski_program_motoru_gorevleri(
        gunler,
        paragraf_hedef,
        blok_soru_butcesi,
        ana_gorev_blok_sayisi,
        filtered_pekistirme,
        filtered_ezber,
    )
    uyarilar.append("Temel program motoru kullanıldı.")
    return (
        _gorevleri_zenginlestir(gorevler, ogrenci_id, biten_konular),
        "Temel motor",
        uyarilar,
    )
