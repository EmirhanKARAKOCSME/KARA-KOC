"""FAZ 8 - YKS puan ve başarı sıralaması simülatörü (HESAP MOTORU).

Tasarım ilkesi: **puan hesaplamak ile sıralama tahmin etmek ayrı işlerdir.**

- `puan_hesapla(...)`: netlerden doğrusal model puanı üretir (taban 100 +
  test katsayısı x net + OBP katkısı). Sonuç **tahmindir**; resmî ÖSYM
  standart puanı değildir ve öyle sunulmaz.
- `siralama_tahmini(...)`: yalnızca `services/osym_verisi.py` içindeki
  **doğrulanmış** puan-sıra referans noktaları varsa tahmin üretir. Veri yoksa
  `durum="veri_yok"` döner; uydurma tablo kullanılmaz.

Faz 7 entegrasyonu (bozmadan kullanılır):
- Mevcut performans: son N **genel denemenin** ders bazlı net ortalaması
  (`denemeler` + `deneme_ders_sonuclari`). Haftalık rapor hesaplarına dokunmaz.
- Hedef performans: `ogrenci_hedef_netleri` tablosu. Hedef netler mevcut
  netlerin üzerine yazılmaz; iki veri ayrı kaynaklardır.

Bağlantı deseni diğer servislerle aynıdır: testler `db_yolu_ayarla` ile geçici
veritabanına yönlendirir, gerçek `yks_veritabani.db` dosyasına dokunulmaz.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from services import osym_verisi as ov

TR_TZ = timezone(timedelta(hours=3))
VARSAYILAN_DB_YOLU = "yks_veritabani.db"
_ZAMAN_KALIBI = "%Y-%m-%d %H:%M:%S"

GENEL_DENEME = "Genel Deneme"
DENEME_TURLERI = ("TYT", "AYT", "YDT")
VARSAYILAN_SON_DENEME = 3
MAKS_SON_DENEME = 10
MAKS_NET = 200.0

# Puan türü -> hesapta kullanılan alan testleri (TYT testleri her zaman gerekir).
PUAN_TURLERI = ov.PUAN_TURLERI

# Sıralama tahmininin durum kodları.
DURUM_OK = "ok"
DURUM_VERI_YOK = "veri_yok"
DURUM_VERI_YETERSIZ = "veri_yetersiz"
DURUM_ARALIK_DISI = "aralik_disi"
DURUM_EKSIK_NET = "eksik_veri"


class SimulatorHatasi(ValueError):
    """Geçersiz net, puan türü, yıl veya hedef net işlemi."""


# ==============================================================================
# YAPILANDIRMA (testler için enjekte edilebilir)
# ==============================================================================
_db_yolu = VARSAYILAN_DB_YOLU
_baglanti_fabrikasi = None
_saat_fonksiyonu = None


def db_yolu_ayarla(yol):
    """Testlerin geçici kopya DB kullanabilmesi için yol değiştirir."""
    global _db_yolu
    _db_yolu = yol or VARSAYILAN_DB_YOLU


def baglanti_fabrikasi_ayarla(fabrika):
    """Testlerin hazır bir bağlantı vermesini sağlar (None = varsayılan)."""
    global _baglanti_fabrikasi
    _baglanti_fabrikasi = fabrika


def saat_fonksiyonu_ayarla(fonksiyon):
    """Testlerde zamanı sabitlemek için kullanılır (None = gerçek saat)."""
    global _saat_fonksiyonu
    _saat_fonksiyonu = fonksiyon


def simdi():
    """Türkiye yerel saatiyle şu an (test enjeksiyonuna duyarlı)."""
    if _saat_fonksiyonu is not None:
        return _saat_fonksiyonu()
    return datetime.now(TR_TZ)


@contextmanager
def _baglanti():
    """Kendi açtığı bağlantıyı kapatır; enjekte edilen bağlantıya dokunmaz."""
    if _baglanti_fabrikasi is not None:
        conn = _baglanti_fabrikasi()
        kendi = False
    else:
        conn = sqlite3.connect(_db_yolu, timeout=20, check_same_thread=False)
        kendi = True
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        if kendi:
            conn.close()


@contextmanager
def _islem(conn):
    """Atomik yazma işlemi (BEGIN IMMEDIATE ile yarış koşulu kapatılır)."""
    if conn.in_transaction:
        yield
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _tablo_var_mi(conn, tablo):
    satir = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (tablo,),
    ).fetchone()
    return satir is not None


def _ogrenci_dogrula(ogrenci_id):
    try:
        oid = int(ogrenci_id)
    except (TypeError, ValueError):
        raise SimulatorHatasi("Geçersiz öğrenci numarası.") from None
    if oid <= 0:
        raise SimulatorHatasi("Geçersiz öğrenci numarası.")
    return oid


def _zaman_yaz(deger):
    if not deger:
        return None
    return deger.strftime(_ZAMAN_KALIBI)


# ==============================================================================
# NET HESABI
# ==============================================================================
def net_hesapla(dogru, yanlis=0, bos=0, soru_sayisi=None):
    """Net = Doğru - (Yanlış / 4). Uygulamanın mevcut kuralıyla aynıdır.

    Doğru/yanlış/boş negatif olamaz; verilirse toplam soru sayısını aşamaz.
    """
    degerler = {}
    for etiket, deger in (("Doğru", dogru), ("Yanlış", yanlis), ("Boş", bos)):
        try:
            sayi = float(0 if deger in (None, "") else deger)
        except (TypeError, ValueError):
            raise SimulatorHatasi("%s sayısı sayısal olmalıdır." % etiket) from None
        if sayi < 0:
            raise SimulatorHatasi("%s sayısı negatif olamaz." % etiket)
        degerler[etiket] = sayi
    if soru_sayisi is not None:
        try:
            toplam = float(soru_sayisi)
        except (TypeError, ValueError):
            raise SimulatorHatasi("Soru sayısı sayısal olmalıdır.") from None
        if toplam <= 0:
            raise SimulatorHatasi("Soru sayısı pozitif olmalıdır.")
        if sum(degerler.values()) > toplam:
            raise SimulatorHatasi(
                "Doğru + yanlış + boş toplamı soru sayısını aşamaz (%.0f > %.0f)."
                % (sum(degerler.values()), toplam)
            )
    return round(degerler["Doğru"] - (degerler["Yanlış"] / 4.0), 2)


def _net_degeri(test, deger):
    """Tek bir net değerini doğrular (0..test soru sayısı aralığında)."""
    if deger is None or deger == "":
        raise SimulatorHatasi("%s için net değeri gerekli." % test)
    try:
        net = float(deger)
    except (TypeError, ValueError):
        raise SimulatorHatasi("%s neti sayısal olmalıdır." % test) from None
    if net != net:  # NaN
        raise SimulatorHatasi("%s neti sayısal olmalıdır." % test)
    soru = ov.test_soru_sayisi(test)
    ust = float(soru) if soru else MAKS_NET
    if net > ust:
        raise SimulatorHatasi(
            "%s neti en fazla %.0f olabilir (girilen: %.2f)." % (test, ust, net)
        )
    if net < -MAKS_NET:
        raise SimulatorHatasi("%s neti çok küçük: %.2f." % (test, net))
    return round(net, 2)


def testleri_getir(puan_turu):
    """Puan türünün test listesi: [(test, katsayı)] (TYT + alan testleri)."""
    return ov.testleri_getir(puan_turu)


def gereken_testler(puan_turu):
    """Puan türü için neti girilmesi gereken testler."""
    return [test for test, _ in testleri_getir(puan_turu)]


# ==============================================================================
# PUAN HESABI (MODEL)
# ==============================================================================
def puan_hesapla(
    netler,
    puan_turu="Sayısal",
    yil=None,
    diploma_notu=None,
    obp_dahil=True,
):
    """Doğrusal model puanını hesaplar.

    Dönüş: durum / puan / puan_obp_haric / ham_puan / obp_puani / obp_katkisi /
    test_katkilari / eksik_testler / uyarilar / kural / resmi_mi=False.

    Resmî ÖSYM puanı ÜRETİLMEZ: standart puan dönüşümü için yıl bazlı test
    ortalama/standart sapma gerekir ve bu veri üründe yoktur.
    """
    tur = ov.puan_turu_kontrol(puan_turu)
    kural = ov.kural_seti(yil)
    if not isinstance(netler, dict):
        raise SimulatorHatasi("Netler bir sözlük olmalıdır (test -> net).")

    testler = testleri_getir(tur)
    eksik = [test for test, _ in testler if test not in netler]
    if eksik:
        return {
            "durum": DURUM_EKSIK_NET,
            "puan_turu": tur,
            "yil": kural["yil"],
            "puan": None,
            "puan_obp_haric": None,
            "ham_puan": None,
            "obp_puani": None,
            "obp_katkisi": None,
            "obp_dahil": bool(obp_dahil),
            "test_katkilari": [],
            "eksik_testler": eksik,
            "uyarilar": ["Eksik test netleri: %s" % ", ".join(eksik)],
            "kural": kural,
            "resmi_mi": False,
        }

    katkilar = []
    ham = kural["taban_puan"]
    tyt_net = 0.0
    alan_net = 0.0
    uyarilar = []
    for test, katsayi in testler:
        net = _net_degeri(test, netler[test])
        if net < 0:
            uyarilar.append("%s neti negatif (%.2f)." % (test, net))
        katki = net * katsayi
        ham += katki
        if test.startswith("TYT"):
            tyt_net += net
        else:
            alan_net += net
        katkilar.append(
            {
                "test": test,
                "net": net,
                "katsayi": katsayi,
                "katki": round(katki, 2),
            }
        )

    ham = round(ham, 2)
    if ham > kural["maks_ham_puan"]:  # pragma: no cover - netler sınırlı
        ham = kural["maks_ham_puan"]
        uyarilar.append("Ham puan üst sınırı uygulandı (%.0f)." % ham)

    obp_p = None
    obp_k = 0.0
    if diploma_notu is not None:
        obp_p = ov.obp_puani(diploma_notu)
        obp_k = round(obp_p * kural["obp_katsayisi"], 2)
    puan = ham + (obp_k if obp_dahil else 0.0)
    if puan > kural["maks_yerlestirme_puani"]:
        puan = kural["maks_yerlestirme_puani"]
        uyarilar.append(
            "Yerleştirme puanı üst sınırı uygulandı (%.0f)."
            % kural["maks_yerlestirme_puani"]
        )

    uyarilar.append(
        "Bu puan bir model tahminidir; resmî ÖSYM standart puanı değildir."
    )
    return {
        "durum": DURUM_OK,
        "puan_turu": tur,
        "yil": kural["yil"],
        "puan": round(puan, 2),
        "puan_obp_haric": ham,
        "ham_puan": ham,
        "obp_puani": obp_p,
        "obp_katkisi": obp_k,
        "obp_dahil": bool(obp_dahil),
        "tyt_net": round(tyt_net, 2),
        "alan_net": round(alan_net, 2),
        "test_katkilari": katkilar,
        "eksik_testler": [],
        "uyarilar": uyarilar,
        "kural": kural,
        "resmi_mi": False,
    }


# ==============================================================================
# SIRALAMA TAHMİNİ (yalnızca doğrulanmış referans verisiyle)
# ==============================================================================
def _arada_tahmin(noktalar, puan):
    """Noktalar arasında doğrusal interpolasyon; aralık dışında None (ekstrapolasyon yok)."""
    if not noktalar or puan is None:
        return None
    if puan > noktalar[0]["puan"] or puan < noktalar[-1]["puan"]:
        return None
    for indeks in range(len(noktalar) - 1):
        ust = noktalar[indeks]
        alt = noktalar[indeks + 1]
        if alt["puan"] <= puan <= ust["puan"]:
            fark = ust["puan"] - alt["puan"]
            if fark <= 0:
                return int(round(alt["sira"]))
            oran = (ust["puan"] - puan) / fark
            tahmin = ust["sira"] + oran * (alt["sira"] - ust["sira"])
            return max(1, int(round(tahmin)))
    return None


def siralama_tahmini(puan, puan_turu, yil=None, veri=None):
    """Puanı, referans verisindeki puan-sıra noktalarıyla eşleştirir.

    Dönüş: durum / sira / aralik / kapsanan_yillar / kaynak / notlar.
    - Veri yoksa: durum="veri_yok", sira=None (uydurma tablo yok).
    - Tek yıl varsa: aralik=None ("tek yıl verisi").
    - Birden çok yıl varsa: aralik=(en_iyi, en_kotu) ve tur="senaryo_araligi".
    Bu aralık istatistiksel güven aralığı değildir.
    """
    tur = ov.puan_turu_kontrol(puan_turu)
    yil_kodu = ov.yil_normalize(yil)
    kapsanan = ov.kapsanan_yillar(tur, veri=veri)
    cevap = {
        "durum": DURUM_VERI_YOK,
        "puan": puan,
        "puan_turu": tur,
        "yil": yil_kodu,
        "sira": None,
        "aralik": None,
        "aralik_turu": None,
        "kapsanan_yillar": kapsanan,
        "secilen_yil_verisi_var": yil_kodu in kapsanan,
        "kaynak": None,
        "notlar": [],
    }

    if puan is None:
        cevap["notlar"].append("Puan hesaplanmadan sıralama tahmini yapılamaz.")
        return cevap

    kayit = ov.kayit_getir(yil_kodu, tur, veri=veri)
    if not kayit:
        cevap["eksik_veri"] = [
            "%s %s puan-sıra referans verisi yok." % (yil_kodu, tur)
        ]
        cevap["notlar"].append(
            "Seçilen yıl için doğrulanmış puan-sıra verisi bulunmadığından"
            " sıralama tahmini üretilmedi."
        )
        return cevap

    noktalar = kayit["noktalar"]
    if len(noktalar) < ov.MIN_NOKTA:
        cevap["durum"] = DURUM_VERI_YETERSIZ
        cevap["eksik_veri"] = [
            "%s %s için en az %d referans noktası gerekir."
            % (yil_kodu, tur, ov.MIN_NOKTA)
        ]
        return cevap

    sira = _arada_tahmin(noktalar, float(puan))
    cevap["kaynak"] = kayit["kaynak"]
    if sira is None:
        cevap["durum"] = DURUM_ARALIK_DISI
        cevap["notlar"].append(
            "Puan, girilen referans noktalarının aralığı dışında"
            " (%.0f – %.0f). Aralık dışına doğru tahmin üretilmedi."
            % (noktalar[-1]["puan"], noktalar[0]["puan"])
        )
        return cevap

    cevap["durum"] = DURUM_OK
    cevap["sira"] = sira

    yil_tahminleri = []
    for diger_yil in kapsanan:
        diger_kayit = ov.kayit_getir(diger_yil, tur, veri=veri)
        if not diger_kayit:
            continue
        diger_sira = _arada_tahmin(diger_kayit["noktalar"], float(puan))
        if diger_sira is not None:
            yil_tahminleri.append({"yil": diger_yil, "sira": diger_sira})
    cevap["yil_tahminleri"] = yil_tahminleri
    if len(yil_tahminleri) >= 2:
        degerler = [t["sira"] for t in yil_tahminleri]
        cevap["aralik"] = (min(degerler), max(degerler))
        cevap["aralik_turu"] = "senaryo_araligi"
        cevap["notlar"].append(
            "%d yılın verisiyle hesaplanan senaryo aralığı; istatistiksel güven"
            " aralığı değildir." % len(yil_tahminleri)
        )
    elif len(kapsanan) < 2:
        cevap["notlar"].append(
            "Tek yıl verisi olduğu için aralık üretilmedi."
        )
    else:
        cevap["notlar"].append(
            "Bu puan yalnızca bir yılın referans aralığına düştüğü için"
            " aralık üretilmedi."
        )
    return cevap


# ==============================================================================
# MEVCUT PERFORMANS (son genel denemeler) - Faz 7 verisini bozmadan okur
# ==============================================================================
def _deneme_net_ortalamalari(conn, deneme_idleri):
    """Verilen denemelerde test başına net ortalaması (yalnızca veri olan testler)."""
    if not deneme_idleri:
        return {}
    yer_tutucu = ",".join("?" for _ in deneme_idleri)
    satirlar = conn.execute(
        "SELECT deneme_id, ders, net FROM deneme_ders_sonuclari"
        " WHERE deneme_id IN (%s)" % yer_tutucu,
        tuple(deneme_idleri),
    ).fetchall()
    toplam = {}
    for satir in satirlar:
        ders = str(satir["ders"] or "").strip()
        if not ders or ov.test_soru_sayisi(ders) is None:
            continue
        try:
            net = float(satir["net"])
        except (TypeError, ValueError):
            continue
        kayit = toplam.setdefault(ders, [])
        kayit.append(net)
    return {
        ders: round(sum(degerler) / len(degerler), 2)
        for ders, degerler in toplam.items()
        if degerler
    }


def mevcut_netler(ogrenci_id, son_deneme=VARSAYILAN_SON_DENEME):
    """Son N genel denemeden test bazlı net ortalaması.

    Yöntem kullanıcıya açıkça bildirilir (`yontem`). Deneme yoksa boş sözlük
    döner; hiçbir varsayılan net üretilmez.
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    try:
        adet = int(son_deneme)
    except (TypeError, ValueError):
        raise SimulatorHatasi("Deneme sayısı sayısal olmalıdır.") from None
    adet = max(1, min(MAKS_SON_DENEME, adet))

    cevap = {
        "tyt": {},
        "ayt": {},
        "yontem": None,
        "deneme_sayisi": {"TYT": 0, "AYT": 0, "YDT": 0},
        "kullanilan_denemeler": {"TYT": [], "AYT": [], "YDT": []},
        "son_tarihler": {"TYT": None, "AYT": None, "YDT": None},
        "kayit_var": False,
        "uyarilar": [],
    }

    with _baglanti() as conn:
        if not _tablo_var_mi(conn, "denemeler"):
            cevap["uyarilar"].append("Deneme tablosu bulunamadı.")
            return cevap
        satirlar = conn.execute(
            "SELECT id, substr(tarih, 1, 10) AS gun, deneme_adi, deneme_turu"
            " FROM denemeler"
            " WHERE ogrenci_id = ? AND deneme_kategorisi = ?"
            " ORDER BY COALESCE(substr(tarih, 1, 10), '') DESC, id DESC",
            (oid, GENEL_DENEME),
        ).fetchall()
        if not satirlar:
            return cevap
        if not _tablo_var_mi(conn, "deneme_ders_sonuclari"):
            cevap["uyarilar"].append(
                "Ders bazlı deneme sonuçları tablosu bulunamadı."
            )
            return cevap

        turler = {}
        for satir in satirlar:
            tur = str(satir["deneme_turu"] or "").strip().upper()
            if tur not in DENEME_TURLERI:
                continue
            kova = turler.setdefault(tur, [])
            if len(kova) < adet:
                kova.append(satir)

        for tur, kayitlar in turler.items():
            idler = [int(k["id"]) for k in kayitlar]
            netler = _deneme_net_ortalamalari(conn, idler)
            if not netler:
                cevap["uyarilar"].append(
                    "%s denemelerinde ders bazlı net kaydı yok." % tur
                )
                continue
            hedef = cevap["tyt"] if tur == "TYT" else cevap["ayt"]
            hedef.update(netler)
            cevap["deneme_sayisi"][tur] = len(idler)
            cevap["kullanilan_denemeler"][tur] = idler
            cevap["son_tarihler"][tur] = kayitlar[0]["gun"] or None

    toplam_deneme = sum(cevap["deneme_sayisi"].values())
    if toplam_deneme:
        cevap["kayit_var"] = True
        cevap["yontem"] = (
            "Son genel denemenin test bazlı netleri"
            if toplam_deneme == 1
            else "Son %d genel denemenin test bazlı net ortalaması" % adet
        )
    return cevap


# ==============================================================================
# HEDEF NETLER (Faz 7 hedeflerinden AYRI; mevcut netlerin üzerine yazılmaz)
# ==============================================================================
_HEDEF_SEMA = """
CREATE TABLE IF NOT EXISTS ogrenci_hedef_netleri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    puan_turu TEXT NOT NULL,
    test TEXT NOT NULL,
    hedef_net REAL NOT NULL DEFAULT 0,
    guncelleme_zamani TEXT,
    FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
)
"""

_HEDEF_INDEKS = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_hedef_net_tekil
ON ogrenci_hedef_netleri(ogrenci_id, puan_turu, test)
"""


def init_db():
    """Hedef net tablosunu idempotent kurar (veri silmez)."""
    with _baglanti() as conn:
        with _islem(conn):
            conn.execute(_HEDEF_SEMA)
            conn.execute(_HEDEF_INDEKS)


def hedef_netleri_getir(ogrenci_id, puan_turu):
    """Öğrencinin bir puan türü için kayıtlı hedef netleri (test -> net)."""
    oid = _ogrenci_dogrula(ogrenci_id)
    tur = ov.puan_turu_kontrol(puan_turu)
    with _baglanti() as conn:
        if not _tablo_var_mi(conn, "ogrenci_hedef_netleri"):
            return {}
        satirlar = conn.execute(
            "SELECT test, hedef_net FROM ogrenci_hedef_netleri"
            " WHERE ogrenci_id = ? AND puan_turu = ?",
            (oid, tur),
        ).fetchall()
    return {
        str(satir["test"]): round(float(satir["hedef_net"] or 0.0), 2)
        for satir in satirlar
    }


def hedef_netleri_kaydet(ogrenci_id, puan_turu, netler):
    """Hedef netleri yazar/günceller (aynı test için tek kayıt).

    Yalnızca verilen testler yazılır; diğer kayıtlar korunur. Doğrulama:
    test, puan türünün testlerinden olmalı; 0 <= hedef net <= soru sayısı.
    """
    oid = _ogrenci_dogrula(ogrenci_id)
    tur = ov.puan_turu_kontrol(puan_turu)
    if not isinstance(netler, dict) or not netler:
        raise SimulatorHatasi("Kaydedilecek hedef net bulunamadı.")
    izinli = set(gereken_testler(tur))
    temiz = {}
    for test, deger in netler.items():
        ad = str(test or "").strip()
        if ad not in izinli:
            raise SimulatorHatasi(
                "%s testi %s puan türünde kullanılmıyor." % (ad, tur)
            )
        net = _net_degeri(ad, deger)
        if net < 0:
            raise SimulatorHatasi("Hedef net negatif olamaz: %s" % ad)
        temiz[ad] = net

    zaman = _zaman_yaz(simdi())
    with _baglanti() as conn:
        if not _tablo_var_mi(conn, "ogrenci_hedef_netleri"):
            raise SimulatorHatasi(
                "Hedef net tablosu bulunamadı; veritabanı hazır değil."
            )
        with _islem(conn):
            for test, net in temiz.items():
                conn.execute(
                    "INSERT INTO ogrenci_hedef_netleri"
                    " (ogrenci_id, puan_turu, test, hedef_net, guncelleme_zamani)"
                    " VALUES (?, ?, ?, ?, ?)"
                    " ON CONFLICT(ogrenci_id, puan_turu, test)"
                    " DO UPDATE SET hedef_net = excluded.hedef_net,"
                    " guncelleme_zamani = excluded.guncelleme_zamani",
                    (oid, tur, test, net, zaman),
                )
    return hedef_netleri_getir(oid, tur)


def hedef_netleri_sil(ogrenci_id, puan_turu):
    """Bir puan türünün hedef netlerini siler; silinen kayıt sayısı."""
    oid = _ogrenci_dogrula(ogrenci_id)
    tur = ov.puan_turu_kontrol(puan_turu)
    with _baglanti() as conn:
        if not _tablo_var_mi(conn, "ogrenci_hedef_netleri"):
            return 0
        with _islem(conn):
            imlec = conn.execute(
                "DELETE FROM ogrenci_hedef_netleri"
                " WHERE ogrenci_id = ? AND puan_turu = ?",
                (oid, tur),
            )
            return imlec.rowcount or 0


def hedef_karsilastirma(ogrenci_id, puan_turu, mevcut=None):
    """Mevcut net ile hedef neti test bazında yan yana getirir.

    Mevcut netler hedefin üzerine yazılmaz; iki değer ayrı alanlarda döner.
    """
    tur = ov.puan_turu_kontrol(puan_turu)
    hedefler = hedef_netleri_getir(ogrenci_id, tur)
    if mevcut is None:
        mevcut = mevcut_netler(ogrenci_id)
    mevcut_tyt = (mevcut or {}).get("tyt") or {}
    mevcut_ayt = (mevcut or {}).get("ayt") or {}

    satirlar = []
    for test in gereken_testler(tur):
        simdi_net = mevcut_tyt.get(test)
        if simdi_net is None:
            simdi_net = mevcut_ayt.get(test)
        hedef_net = hedefler.get(test)
        if simdi_net is None and hedef_net is None:
            durum = "veri_yok"
        elif hedef_net is None:
            durum = "hedef_yok"
        elif simdi_net is None:
            durum = "mevcut_yok"
        elif round(float(simdi_net), 2) >= hedef_net:
            durum = "hedefte"
        else:
            durum = "hedefin_altinda"
        satirlar.append(
            {
                "test": test,
                "mevcut": None if simdi_net is None else round(float(simdi_net), 2),
                "hedef": hedef_net,
                "fark": (
                    None
                    if simdi_net is None or hedef_net is None
                    else round(float(simdi_net) - hedef_net, 2)
                ),
                "durum": durum,
            }
        )
    return satirlar


# ==============================================================================
# BİRLEŞİK ÇIKTILAR (arayüz için)
# ==============================================================================
def simulasyon(netler, puan_turu="Sayısal", yil=None, diploma_notu=None,
               obp_dahil=True, veri=None):
    """Puan + sıralama sonucunu tek pakette döndürür (arayüz kullanır)."""
    puan = puan_hesapla(
        netler,
        puan_turu=puan_turu,
        yil=yil,
        diploma_notu=diploma_notu,
        obp_dahil=obp_dahil,
    )
    if puan["durum"] != DURUM_OK:
        siralama = {
            "durum": DURUM_EKSIK_NET,
            "sira": None,
            "aralik": None,
            "kapsanan_yillar": ov.kapsanan_yillar(puan_turu, veri=veri),
            "notlar": ["Puan hesaplanamadığı için sıralama tahmini yok."],
        }
    else:
        siralama = siralama_tahmini(
            puan["puan"], puan_turu, yil=puan["yil"], veri=veri
        )
    return {"puan": puan, "siralama": siralama}


def yil_karsilastirmasi(netler, puan_turu="Sayısal", diploma_notu=None,
                        obp_dahil=True, yillar=None, veri=None):
    """Aynı netlerle yıllara göre model puanı + (varsa) sıralama tahmini."""
    tur = ov.puan_turu_kontrol(puan_turu)
    hedefler = list(yillar) if yillar else ov.desteklenen_yillar()
    satirlar = []
    for yil in hedefler:
        puan = puan_hesapla(
            netler,
            puan_turu=tur,
            yil=yil,
            diploma_notu=diploma_notu,
            obp_dahil=obp_dahil,
        )
        if puan["durum"] != DURUM_OK:
            satirlar.append(
                {"yil": puan["yil"], "puan": None, "sira": None,
                 "aralik": None, "durum": puan["durum"]}
            )
            continue
        siralama = siralama_tahmini(
            puan["puan"], tur, yil=puan["yil"], veri=veri
        )
        satirlar.append(
            {
                "yil": puan["yil"],
                "puan": puan["puan"],
                "sira": siralama.get("sira"),
                "aralik": siralama.get("aralik"),
                "durum": siralama.get("durum"),
            }
        )
    return satirlar


def veri_durumu():
    """Arayüzde gösterilecek veri/kaynak durumu (bozuk dosyayı da bildirir)."""
    kaynak = dict(ov.KAYNAKLAR["MODEL_YKS_DOGRUSAL"])
    try:
        siralama_ozeti = ov.veri_ozeti()
    except ov.VeriHatasi as hata:
        siralama_ozeti = {"hata": str(hata), "kayit_sayisi": 0, "yillar": [],
                          "kapsanan": {tur: [] for tur in ov.PUAN_TURLERI}}
    return {
        "model": {
            "kod": "yks_dogrusal",
            "kaynak": kaynak,
            "dogrulama_durumu": kaynak.get("dogrulama_durumu"),
            "yillar": ov.desteklenen_yillar(),
            "resmi_mi": False,
        },
        "siralama": siralama_ozeti,
        "kaynaklar": ov.KAYNAKLAR,
    }






