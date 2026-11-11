"""Deneme (sınav) veri modeli ve analiz hesapları.

Deneme kategorileri, ders sonucu doğrulama, net hesapları, deneme
kaydetme/migrasyon ve kohort yanlış serileri buradadır. Arayüz kodu
içermez; bağlantı dışarıdan verilir veya
`config.database.get_connection()` kullanılır."""

from datetime import datetime
import re
import sqlite3

import pandas as pd

from config.settings import get_tr_now


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


DERS_SONUC_MIN_SORU = 1


DERS_SONUC_MAKS_SORU = 200


TYT_GENEL_DERS_SORU_SAYILARI = [
    ("TYT Türkçe", 40),
    ("TYT Matematik", 40),
    ("TYT Sosyal Bilimler", 20),
    ("TYT Fen Bilimleri", 20),
]


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


ALARM_SERI_PENCERESI = 3


ALARM_MIN_YANLIS = 1


_DENEME_KANIT_KOLONLARI = (
    "deneme_net_bilgisi",
    "deneme_dogru_adedi",
    "deneme_yanlis_adedi",
    "deneme_bos_adedi",
    "deneme_sure_dk",
)


def _deneme_tamamlanmis_mi(satirlar):
    """Deneme GERÇEKTEN çözülmüş mü (taslak başlık değil mi)?

    Yalnızca adı/tarihi girilmiş, net ve soru dağılımı boş bırakılmış bir
    deneme "çözülmüş sınav" değildir; Mor/Siyah alarm serilerine girmez.
    Alanlar tamamen yoksa (eski veri) engel konmaz.
    """
    for kolon in _DENEME_KANIT_KOLONLARI:
        if kolon not in satirlar:
            continue
        if pd.to_numeric(satirlar[kolon], errors="coerce").notna().any():
            return True
    return not any(k in satirlar for k in _DENEME_KANIT_KOLONLARI)


def kohort_yanlis_serileri(df_yanlislar):
    """Bağlı yanlış detaylarını (ders, konu, sınav kohortu) bazında serilere çevirir.

    Kohort = (ders, konu, sınav türü, deneme kategorisi, branş dersi). Böylece
    TYT genel denemesi ile TYT Matematik branş denemesi, TYT Türkçe ile TYT
    Matematik ve AYT Matematik ile TYT Matematik asla birleşmez.

    Alarm kuralları için üç güvence burada sağlanır:

    1. **Yalnızca gerçekten çözülmüş denemeler.** Net/doğru/yanlış/boş/süre
       alanlarının tamamı boş olan (taslak) deneme başlıkları seriye girmez.
       `deneme_id` bağlantısı olmayan eski detaylar da hesaba katılmaz.
    2. **Her deneme seride TEK noktadır.** Aynı denemeye ait birden fazla
       yanlış satırı `MAX(yanlis_adedi)` ile tekilleştirilir (eski çift kayıt
       şişirmesi engellenir).
    3. **Ayrı deneme kayıtları birleştirilmez.** Deneme kimliği
       `denemeler.id`'dir. Aynı gün, aynı adla girilmiş iki FARKLI deneme
       (örn. aynı gün çözülen iki ayrı "345 AYT Matematik" denemesi) tek sınav
       sayılmaz; ad + tarih benzerliği üzerinden yapılan birleştirme gerçek
       sınavları yutacağı için kullanılmaz.

    Dönüş: {(ders, konu, tur, kategori, brans): [{"deneme_id", "tarih",
            "yanlis", "ids", "neden", "deneme_sayisi"}, ...]}
            (tarih, sonra deneme_id sırasıyla)
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

    # 1) Başlığa bağlı olmayan detaylar seriye girmez.
    df = df[df["deneme_id"] > 0]
    if df.empty:
        return seriler

    for anahtar, grup in df.groupby(
        ["ders", "konu_adi", "deneme_turu", "deneme_kategorisi", "brans_dersi"],
        dropna=False,
    ):
        noktalar = []
        for _deneme_id, alt in grup.groupby("deneme_id", sort=False):
            # 1) Yalnızca gerçekten çözülmüş denemeler alarm üretebilir.
            if not _deneme_tamamlanmis_mi(alt):
                continue
            neden = (
                alt["yanlis_nedeni"].iloc[-1] if "yanlis_nedeni" in alt.columns else ""
            )
            noktalar.append({
                "deneme_id": int(alt["deneme_id"].max()),
                "tarih": str(alt["tarih"].iloc[0]),
                "yanlis": int(alt["yanlis_adedi"].max()),
                "ids": [int(i) for i in alt["id"].tolist()],
                "neden": neden,
                "deneme_sayisi": int(alt["deneme_id"].nunique()),
            })
        if not noktalar:
            continue
        noktalar.sort(key=lambda n: (n["tarih"], n["deneme_id"]))
        seriler[anahtar] = noktalar
    return seriler
