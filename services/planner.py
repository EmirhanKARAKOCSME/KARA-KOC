"""FAZ 5C/5D - Gerçek ilerlemeye dayalı akıllı haftalık program motoru.

İlkeler:

- **Planlama birimi mikro konudur (FAZ 5D).** Ders → ana konu → mikro konu →
  checklist. Bir ana konunun alt başlıkları tek görevde BİRLEŞTİRİLMEZ; her
  mikro konu kendi görev kaydı, kendi tamamlanma durumu, kendi checklist'i,
  kendi soru hedefi ve kendi süresiyle planlanır.
- **Ana konu kotası korunur.** Ana konunun soru hedefi mikro konulara
  paylaştırılır; mikro hedeflerin toplamı ana hedefe eşittir. Aynı hedef her
  mikro konuya tekrar uygulanmaz.
- **Süre bölünmez, mikro konuya göre hesaplanır.** Ana konunun anlatım süresi
  mikro konu sayısına bölünmez; mikro konunun kendi süresi (varsa), yoksa ana
  konunun süresi makul varsayılan olarak kullanılır ve gerçek oturum medyanı
  ile kişiselleştirilir.
- **Gerçek soru kaynağı yalnızca FAZ 4 oturumlarıdır.** `konu_soru_ilerleme`
  (eski planlama sayacı) burada hiç okunmaz.
- **Kota arka planda kalır.** Kredi puanı, ana konu kotası, kalan soru
  matematiği ve öncelik puanları öğrenci arayüzünde gösterilmez.
- **Günlük kapasite aşılmaz.** Her gün için ayrı müsaitlik (dakika) tanımlıdır;
  0 dakika dinlenme günüdür. Görev süreleri `task_steps` ile aynı formülle
  hesaplandığı için planlanan süre gerçek tahminle tutarlıdır.
- **Haftaya sığmayan mikro konular devredilir.** Önceki programdan kalan soru
  miktarı yeni göreve `kaynak_gorev_id` ile bağlanır; tamamlanmış mikro konu
  yeniden üretilmez.
- **Ön koşul ağacı korunur.** Ön koşulu tamamlanmamış konuya geçilmez.

Bu modül Streamlit'e bağımlı değildir.
"""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

from services import task_steps

TR_TZ = timezone(timedelta(hours=3))

GUN_SAYISI = 7
VARSAYILAN_GUNLUK_DAKIKA = 360
MAKS_GUNLUK_DAKIKA = 1440
MIN_ANLAMLI_BLOK = 5
MAKS_YENI_MIKRO_GUN = 2
AGIR_DERSLER = ("AYT Matematik", "TYT Matematik", "AYT Geometri", "TYT Geometri")
PARAGRAF_DAKIKA = 30
TEKRAR_DAKIKA = 20
KREDI_MAKS = 100.0
SORU_CARPANI = 3.0  # toplam soru hedefi = 100 x 3 x normalize kredi
VARSAYILAN_DB_YOLU = "yks_veritabani.db"

GUN_ADLARI = (
    "Pazartesi",
    "Salı",
    "Çarşamba",
    "Perşembe",
    "Cuma",
    "Cumartesi",
    "Pazar",
)

_ZAMAN_KALIBI = "%Y-%m-%d %H:%M:%S"


class PlanHatasi(ValueError):
    """Geçersiz planlama girdisi."""


# ==============================================================================
# YAPILANDIRMA
# ==============================================================================
_db_yolu = VARSAYILAN_DB_YOLU
_baglanti_fabrikasi = None
_saat_fonksiyonu = None


def db_yolu_ayarla(yol):
    global _db_yolu
    _db_yolu = yol or VARSAYILAN_DB_YOLU


def baglanti_fabrikasi_ayarla(fabrika):
    global _baglanti_fabrikasi
    _baglanti_fabrikasi = fabrika


def saat_fonksiyonu_ayarla(fonksiyon):
    global _saat_fonksiyonu
    _saat_fonksiyonu = fonksiyon


def simdi():
    if _saat_fonksiyonu is not None:
        return _saat_fonksiyonu()
    return datetime.now(TR_TZ)


def _zaman_yaz(deger):
    return deger.strftime(_ZAMAN_KALIBI) if deger else None


@contextmanager
def _baglanti():
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


_SEMA = """
CREATE TABLE IF NOT EXISTS calisma_musaitlik (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ogrenci_id INTEGER NOT NULL,
    gun INTEGER NOT NULL,
    dakika INTEGER NOT NULL DEFAULT 0,
    guncelleme_zamani TEXT,
    UNIQUE(ogrenci_id, gun),
    FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
)
"""

_INDEKSLER = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_musaitlik_tek"
    " ON calisma_musaitlik(ogrenci_id, gun)",
)


def init_db():
    """Müsaitlik tablosunu idempotent kurar (veri silmez)."""
    with _baglanti() as conn:
        with _islem(conn):
            conn.execute(_SEMA)
            for sorgu in _INDEKSLER:
                conn.execute(sorgu)
    return True



# ==============================================================================
# GÜNLÜK MÜSAİTLİK
# ==============================================================================
def _gun_dogrula(gun):
    try:
        deger = int(gun)
    except (TypeError, ValueError):
        raise PlanHatasi("Gün 1-7 arasında olmalıdır (Pazartesi=1).") from None
    if deger < 1 or deger > 7:
        raise PlanHatasi("Gün 1-7 arasında olmalıdır (Pazartesi=1).")
    return deger


def _dakika_dogrula(dakika):
    if isinstance(dakika, bool):
        raise PlanHatasi("Müsaitlik süresi sayı olmalıdır.")
    try:
        deger = int(dakika)
    except (TypeError, ValueError):
        raise PlanHatasi("Müsaitlik süresi sayı olmalıdır.") from None
    if deger < 0 or deger > MAKS_GUNLUK_DAKIKA:
        raise PlanHatasi(
            "Müsaitlik 0 ile %d dakika arasında olmalıdır." % MAKS_GUNLUK_DAKIKA
        )
    return deger


def musaitlik_yukle(ogrenci_id):
    """Öğrencinin günlük müsaitliği: {1..7: dakika} (kayıt yoksa varsayılan)."""
    try:
        oid = int(ogrenci_id)
    except (TypeError, ValueError):
        raise PlanHatasi("Geçersiz öğrenci bilgisi.") from None
    sonuc = {gun: VARSAYILAN_GUNLUK_DAKIKA for gun in range(1, 8)}
    try:
        with _baglanti() as conn:
            satirlar = conn.execute(
                "SELECT gun, dakika FROM calisma_musaitlik WHERE ogrenci_id = ?",
                (oid,),
            ).fetchall()
    except sqlite3.Error:
        return sonuc
    for satir in satirlar:
        try:
            sonuc[int(satir["gun"])] = int(satir["dakika"])
        except (TypeError, ValueError):
            continue
    return sonuc


def musaitlik_kaydet(ogrenci_id, musaitlik, an=None):
    """Günlük müsaitliği kaydeder (0 dakika = dinlenme günü)."""
    try:
        oid = int(ogrenci_id)
    except (TypeError, ValueError):
        raise PlanHatasi("Geçersiz öğrenci bilgisi.") from None
    if not isinstance(musaitlik, dict) or not musaitlik:
        raise PlanHatasi("Müsaitlik bilgisi gün->dakika sözlüğü olmalıdır.")
    temiz = {}
    for gun, dakika in musaitlik.items():
        temiz[_gun_dogrula(gun)] = _dakika_dogrula(dakika)
    zaman = _zaman_yaz(an or simdi())
    with _baglanti() as conn:
        with _islem(conn):
            for gun, dakika in temiz.items():
                conn.execute(
                    "INSERT INTO calisma_musaitlik (ogrenci_id, gun, dakika,"
                    " guncelleme_zamani) VALUES (?, ?, ?, ?)"
                    " ON CONFLICT(ogrenci_id, gun) DO UPDATE SET"
                    " dakika = excluded.dakika,"
                    " guncelleme_zamani = excluded.guncelleme_zamani",
                    (oid, gun, dakika, zaman),
                )
    return musaitlik_yukle(oid)


def musaitlik_esitle(ogrenci_id, dakika, an=None):
    """Tek bir günlük süreyi haftanın yedi gününe uygular (varsayılan)."""
    dakika = _dakika_dogrula(dakika)
    return musaitlik_kaydet(ogrenci_id, {gun: dakika for gun in range(1, 8)}, an=an)


def gun_musaitligi(tarih, musaitlik=None):
    """Bir tarihin müsaitlik süresi (dakika)."""
    if isinstance(tarih, str):
        tarih = datetime.strptime(tarih[:10], "%Y-%m-%d").date()
    musaitlik = musaitlik if musaitlik is not None else {}
    return int(musaitlik.get(tarih.weekday() + 1, VARSAYILAN_GUNLUK_DAKIKA))


# ==============================================================================
# KREDİ PUANI -> SORU KOTASI (arka planda; arayüzde gösterilmez)
# ==============================================================================
def kredi_normalize(kredi):
    """SORU_AGIRLIKLARI değerini 0-1 aralığına indirger.

    Kaynaktaki değerler 1.5 - 99.5 aralığında; en yüksek değer (Paragraf 99.5)
    0-100 ölçeğinin üst sınırına denk gelir ve eski motor da `kredi x 10`
    formülüyle bu ölçeği kullanıyordu. Bu nedenle 100'e bölünerek normalize
    edilir. Değer zaten 0-1 aralığındaysa olduğu gibi korunur.
    """
    try:
        deger = float(kredi)
    except (TypeError, ValueError):
        deger = 10.0
    if deger <= 1.0:
        return max(0.0, min(1.0, deger))
    return max(0.0, min(1.0, deger / KREDI_MAKS))


def makro_soru_hedefi(kredi, carpan=SORU_CARPANI):
    """Makro konu toplam soru hedefi = 100 x 3 x normalize(kredi).

    Eski 40 soruluk yapay minimum kaldırıldı; alt sınır yoktur.
    """
    normalize = kredi_normalize(kredi)
    hedef = 100.0 * float(carpan) * normalize
    return max(0, int(round(hedef / 5.0) * 5))


def mikro_hedeflere_dagit(makro_hedef, mikrolar, konu_sureleri=None, zorluklar=None):
    """Makro konu hedefini mikro konulara ağırlıklı olarak paylaştırır.

    Ağırlık = konu süresi x zorluk çarpanı. Yuvarlama artıkları en büyük
    kalan yöntemiyle dağıtıldığı için mikro hedeflerin toplamı makro hedefe
    EŞİTTİR.
    """
    konu_sureleri = konu_sureleri or {}
    zorluklar = zorluklar or {}
    liste = [m for m in (mikrolar or []) if m]
    if not liste:
        return {}
    try:
        makro_hedef = max(0, int(makro_hedef or 0))
    except (TypeError, ValueError):
        makro_hedef = 0
    if makro_hedef == 0:
        return {m: 0 for m in liste}
    agirliklar = {}
    for mikro in liste:
        sure = konu_sureleri.get(mikro, task_steps.VARSAYILAN_KONU_SURESI_DK)
        try:
            sure = max(1.0, float(sure))
        except (TypeError, ValueError):
            sure = float(task_steps.VARSAYILAN_KONU_SURESI_DK)
        try:
            zorluk = max(0.5, float(zorluklar.get(mikro, 1.0)))
        except (TypeError, ValueError):
            zorluk = 1.0
        agirliklar[mikro] = sure * zorluk
    toplam_agirlik = sum(agirliklar.values())
    ham = {m: makro_hedef * agirliklar[m] / toplam_agirlik for m in liste}
    sonuc = {m: int(ham[m]) for m in liste}
    kalan = makro_hedef - sum(sonuc.values())
    if kalan:
        sirali = sorted(liste, key=lambda m: (ham[m] - sonuc[m]), reverse=True)
        for i in range(kalan):
            sonuc[sirali[i % len(sirali)]] += 1
    return sonuc


def mikro_soru_hedefi(makro_kredi, mikrolar, mikro, konu_sureleri=None,
                      zorluklar=None):
    """Tek mikro konunun soru hedefi (makro kotanın payı)."""
    dagilim = mikro_hedeflere_dagit(
        makro_soru_hedefi(makro_kredi), mikrolar, konu_sureleri, zorluklar
    )
    return dagilim.get(mikro, 0)

    return int(musaitlik.get(tarih.weekday() + 1, VARSAYILAN_GUNLUK_DAKIKA))



# ==============================================================================
# PLAN MOTORU
# ==============================================================================
MAKS_GOREV_SORU = 20


def _tarih_oku(deger):
    if isinstance(deger, datetime):
        return deger.date()
    if isinstance(deger, date):
        return deger
    return datetime.strptime(str(deger)[:10], "%Y-%m-%d").date()


def gorev_kalan_soru(gorev):
    """Önceki görevin devredilebilir kalan soru miktarı."""
    hedef = int(gorev.get("hedef_soru") or 0)
    gercek = int(gorev.get("gercek_soru") or 0)
    devredilen = int(gorev.get("devredilen_soru") or 0)
    return max(0, hedef - gercek - devredilen)


def _makro_bul(mufredat, ders, mikro):
    for makro, mikrolar in (mufredat.get(ders) or {}).items():
        if mikro in (mikrolar or []):
            return makro
    return "Genel Tekrar"


def _mikro_hedef(ders, makro, mikro, mufredat, soru_agirliklari, konu_sureleri):
    mikrolar = (mufredat.get(ders) or {}).get(makro) or []
    kredi = (soru_agirliklari or {}).get(makro, 10.0)
    if not mikrolar or mikro not in mikrolar:
        return makro_soru_hedefi(kredi)
    return mikro_soru_hedefi(kredi, mikrolar, mikro, konu_sureleri)


def _on_kosul_hazir(mikro, bilinen, kurallar, derinlik=0):
    """Ön koşulları tamamlanmamış konuya geçilmez."""
    kural = (kurallar or {}).get(mikro)
    if not kural or derinlik > 4:
        return True
    for ok in kural.get("on_kosul") or []:
        if ok not in bilinen:
            return False
    return True


def alt_listesi(mikro, mikro_alt):
    """Ana konunun mikro konuları (alt başlıkları); yoksa boş liste."""
    return [a for a in (mikro_alt or {}).get(mikro, []) or [] if a]


def mikro_soru_paylari(ana_hedef, mikrolar, agirliklar=None):
    """Ana konunun soru hedefini mikro konulara tam sayı olarak paylaştırır.

    FAZ 5D: aynı makro hedef her mikro konuya tekrar UYGULANMAZ; payların
    toplamı ana hedefe eşittir (yuvarlama artığı en büyük kalan yöntemiyle
    dağıtılır). Ağırlık verilmezse eşit bölünür.
    """
    liste = [m for m in (mikrolar or []) if m]
    if not liste:
        return {}
    agirliklar = agirliklar or {}
    return mikro_hedeflere_dagit(
        ana_hedef, liste, {m: agirliklar.get(m, 1.0) for m in liste}
    )


def _tek_alt(deger):
    """'A||B' biçimindeki alt başlık metninden tek mikro konu adı çıkarır."""
    parcalar = [p.strip() for p in str(deger or "").split("||") if p.strip()]
    return parcalar[0] if len(parcalar) == 1 else None


def _gorev_turu_tahmin(gorev):
    """Görev türünü mevcut alandan okur; yoksa tanımdan çıkarır."""
    tur = (gorev.get("gorev_turu") or "").strip()
    if tur:
        return tur
    tanim = str(gorev.get("gorev_tanimi") or "")
    if "🧩" in tanim:
        return "soru"
    if "anlatım" in tanim.lower() or "UYGULAMA" in tanim or "📌" in tanim:
        return "anlatim"
    return "anlatim"


def mikro_gorev_tanimi(ana_konu, mikro, soru, gorev_turu="anlatim"):
    """Tek mikro konuya ait görev metni (ana konu ➔ mikro konu)."""
    if gorev_turu == "anlatim":
        kuyruk = ", ardından %d soru çöz" % int(soru) if int(soru or 0) > 0 else ""
        return (
            "📌 %s ➔ %s: konu anlatımını izle ve kısa özet çıkar%s."
            % (ana_konu, mikro, kuyruk)
        )
    if gorev_turu == "tekrar":
        return "🔄 %s ➔ %s: özet notlarını oku." % (ana_konu, mikro)
    return "🧩 %s ➔ %s: %d soru çöz." % (ana_konu, mikro, int(soru or 0))


def mikro_gorevlere_ayir(
    gorevler_or_gorev,
    mikro_alt=None,
    konu_sureleri=None,
    tamamlanan_altlar=None,
    agirliklar=None,
):
    """Ana konu seviyesindeki görevleri MİKRO KONU başına ayrı görevlere böler.

    FAZ 5D: Her mikro konu kendi görev kaydı, kendi süresi ve kendi soru
    hedefiyle üretilir. Ana konunun soru hedefi mikro konulara paylaştırılır;
    toplam korunur. Tek mikro içeren görev olduğu gibi döner (idempotent).

    `gorevler_or_gorev` tek bir görev sözlüğü veya görev listesi olabilir.
    """
    tek = isinstance(gorevler_or_gorev, dict)
    kaynak = [gorevler_or_gorev] if tek else list(gorevler_or_gorev or [])
    sonuc = []
    for gorev in kaynak:
        sonuc.extend(
            _gorevi_mikrolara_ayir(
                gorev, mikro_alt, konu_sureleri, tamamlanan_altlar, agirliklar
            )
        )
    return sonuc


def _gorevi_mikrolara_ayir(gorev, mikro_alt, konu_sureleri, tamamlanan_altlar,
                           agirliklar):
    if not isinstance(gorev, dict):
        return []
    ders = gorev.get("ders")
    ana = (gorev.get("mikro_konu") or "").strip()
    if not ders or not ana:
        return [gorev]
    # Tekrar / deneme tekrarı görevleri ana konu düzeyinde kalır.
    if (gorev.get("pedagoji_turu") or "") == "Tekrar":
        return [gorev]
    if (gorev.get("makro_konu") or "") == "Deneme Tekrarı":
        return [gorev]

    mevcut = [p.strip() for p in str(gorev.get("alt_konu") or "").split("||") if p.strip()]
    if mevcut:
        alts = mevcut
    else:
        alts = [
            a for a in alt_listesi(ana, mikro_alt)
            if (ders, ana, a) not in (tamamlanan_altlar or set())
        ]
    if not alts:
        return [gorev]
    if len(alts) == 1:
        if mevcut:
            return [gorev]  # zaten tek mikro konu
        yeni = dict(gorev)
        yeni["alt_konu"] = alts[0]
        yeni["gorev_turu"] = _gorev_turu_tahmin(gorev)
        yeni["gorev_tanimi"] = mikro_gorev_tanimi(
            ana, alts[0], gorev.get("hedef_soru") or 0, yeni["gorev_turu"]
        )
        return [yeni]

    hedef = max(0, int(gorev.get("hedef_soru") or 0))
    paylar = mikro_soru_paylari(hedef, alts, agirliklar)
    ana_sure = gorev.get("konu_suresi_dk")
    if ana_sure in (None, "", 0):
        ana_sure = (konu_sureleri or {}).get(ana, task_steps.VARSAYILAN_KONU_SURESI_DK)
    sureler = task_steps.mikro_sure_paylari(ana_sure, alts, agirliklar)

    gorev_turu = _gorev_turu_tahmin(gorev)
    parcalar = []
    for alt in alts:
        yeni = dict(gorev)
        yeni["alt_konu"] = alt
        yeni["hedef_soru"] = int(paylar.get(alt, 0))
        yeni["gorev_turu"] = gorev_turu
        yeni["konu_suresi_dk"] = sureler.get(alt)
        yeni["gorev_tanimi"] = mikro_gorev_tanimi(
            ana, alt, yeni["hedef_soru"], gorev_turu
        )
        parcalar.append(yeni)
    return parcalar


def _gorev_uret(
    tur,
    ders,
    makro,
    mikro,
    tarih,
    soru,
    kaynak_gorev_id,
    ogrenci_id,
    konu_sureleri,
    alt_konu=None,
    pedagoji=None,
    alt_sayisi=None,
    sure_dk=None,
):
    """Görev sözlüğü + alt adımlar + planlanan süre.

    FAZ 5D: `alt_konu` tek bir MİKRO KONUdur; görev metni ana konu ➔ mikro
    konu biçiminde kurulur. `sure_dk` verilirse bu mikro konunun kendi
    anlatım süresi kullanılır (ana konu süresi mikro konulara paylaştırılmıştır).
    """
    etiket = "%s ➔ %s" % (mikro, alt_konu) if alt_konu else mikro
    if tur == "tekrar":
        tanim = "🔄 %s: özet notlarını oku, hatırlatma sorularını çöz." % etiket
        soru = min(5, max(0, int(soru or 5)))
        pedagoji = "Tekrar"
    elif tur == "devir":
        tanim = "➡️ %s: geçen programdan kalan %d soruyu çöz." % (etiket, soru)
    elif tur == "alarm":
        tanim = (
            "🔁 %s: denemede yanlış yaptığın soruları incele ve %d soru çöz."
            % (etiket, soru)
        )
    elif tur == "anlatim":
        tanim = (
            "📌 %s: konu anlatımını izle ve kısa özet çıkar, ardından %d soru çöz."
            % (etiket, soru)
        )
    else:
        tanim = "🧩 %s: %d soru çöz." % (etiket, soru)
    gorev = {
        "ders": ders,
        "makro_konu": makro,
        "mikro_konu": mikro,
        "alt_konu": alt_konu,
        "gorev_tanimi": tanim,
        "hedef_soru": int(soru or 0),
        "pedagoji_turu": pedagoji or "Pekiştirme",
        "gorev_turu": tur if tur in ("anlatim", "tekrar") else "soru",
        "tarih": tarih.isoformat(),
        "kaynak_gorev_id": kaynak_gorev_id,
    }
    if sure_dk not in (None, "", 0):
        gorev["konu_suresi_dk"] = int(sure_dk)
    if alt_sayisi is None:
        alt_sayisi = 1
        if alt_konu:
            alt_sayisi = max(
                1, len([p for p in str(alt_konu).split("||") if p.strip()])
            )
    return task_steps.gorev_zenginlestir(
        gorev,
        ogrenci_id=ogrenci_id,
        konu_sureleri=konu_sureleri,
        alt_sayisi=alt_sayisi,
    )




def plan_uret(baglam):
    """Haftalık görev planını üretir (yalnızca bellek; veritabanına yazmaz).

    FAZ 5D: Planlama birimi ANA KONU değil MİKRO KONUdur. Ana konunun soru
    hedefi ve işi mikro konularına paylaştırılır; her mikro konu kendi görev
    kaydı, kendi checklist'i, kendi soru hedefi ve kendi süresiyle planlanır.

    Öncelik sırası:
        1) Önceki programdan kalan gerçek eksikler (devir)
        2) Süresi geçmiş / bekleyen tekrar görevleri
        3) Deneme analizinden gelen kritik konular
        4) Ön koşulu tamamlanmış yeni ana konuların mikro konuları
        5) Pekiştirme gerektiren (öğrenilmiş) konuların mikro konuları
        6) Diğer düzenli çalışmalar (günlük paragraf)
    """
    if not isinstance(baglam, dict):
        raise PlanHatasi("Plan bağlamı sözlük olmalıdır.")
    ogrenci_id = baglam.get("ogrenci_id")
    bas = _tarih_oku(baglam.get("baslangic") or simdi().date())
    try:
        gun_sayisi = int(baglam.get("gun_sayisi") or GUN_SAYISI)
    except (TypeError, ValueError):
        gun_sayisi = GUN_SAYISI
    gun_sayisi = max(1, min(14, gun_sayisi))

    musaitlik = baglam.get("musaitlik") or {}
    konu_sureleri = baglam.get("konu_sureleri") or {}
    soru_agirliklari = baglam.get("soru_agirliklari") or {}
    mufredat = baglam.get("mufredat") or {}
    mikro_alt = baglam.get("mikro_alt") or {}
    tamamlanan_alt = set(baglam.get("tamamlanan_altlar") or [])
    gercek = dict(baglam.get("gercek_cozulen") or {})
    mikro_cozulen = {
        (str(anahtar[0]), str(anahtar[1]), str(anahtar[2])): int(deger or 0)
        for anahtar, deger in (baglam.get("mikro_cozulen") or {}).items()
        if isinstance(anahtar, (tuple, list)) and len(anahtar) >= 3
    }
    bilinen = set(baglam.get("bilinen_mikro") or [])
    kurallar = baglam.get("on_kosullar") or {}
    pedagoji_map = baglam.get("pedagoji") or {}
    try:
        paragraf_soru = max(0, int(baglam.get("paragraf_soru") or 20))
    except (TypeError, ValueError):
        paragraf_soru = 20
    onceki = list(baglam.get("onceki_gorevler") or [])
    uyarilar = []

    gunler = [bas + timedelta(days=i) for i in range(gun_sayisi)]
    kapasite = {gun: gun_musaitligi(gun, musaitlik) for gun in gunler}
    gun_dk = {gun: 0 for gun in gunler}
    gun_gorev = {gun: [] for gun in gunler}
    gun_yeni = {gun: 0 for gun in gunler}
    gun_yeni_ders = {gun: set() for gun in gunler}
    gun_mikro = {gun: set() for gun in gunler}
    planlanan = set()
    kuyruk = {}

    def _kuyruga_ekle(oge):
        anahtar = (oge["ders"], oge["ana"], oge["mikro"])
        mevcut_oge = kuyruk.get(anahtar)
        if mevcut_oge is None or oge["oncelik"] < mevcut_oge["oncelik"]:
            kuyruk[anahtar] = oge

    def _kalan_hedef(ders, makro, ana):
        hedef = _mikro_hedef(
            ders, makro, ana, mufredat, soru_agirliklari, konu_sureleri
        )
        return max(0, hedef - int(gercek.get((ders, ana), 0) or 0))

    def _mikro_sure(ana, alt):
        """Mikro konunun kendi anlatım süresi.

        FAZ 5D: ana konunun süresi mikro konu sayısına BÖLÜNMEZ (80 dk'lık
        konuyu 5'e bölüp 16 dk vermek gerçekçi değildir). Sıra:
          1) Mikro konunun kendi süresi (`konu_sureleri[alt]`),
          2) Ana konunun tanımlı süresi (makul varsayılan),
          3) Genel varsayılan süre.
        Gerçek oturum verisi varsa `task_steps` medyanı bunun üzerine uygular.
        """
        for anahtar in (alt, ana):
            if not anahtar:
                continue
            deger = konu_sureleri.get(anahtar)
            if deger in (None, "", 0):
                continue
            try:
                return float(deger)
            except (TypeError, ValueError):
                continue
        return float(task_steps.VARSAYILAN_KONU_SURESI_DK)

    def _mikro_dilimi(ders, makro, ana):
        """Ana konunun kalan işini MİKRO KONULARA paylaştırır.

        Dönen liste: [(mikro_konu, hedef_soru, anlatim_dk), ...]
        - Tamamlanmış mikro konu yeniden üretilmez.
        - Her mikro konu kendi soru hedefini ve kendi anlatım süresini alır;
          soru paylarının toplamı ana konunun hedefini aşmaz.
        - Mikro konusu olmayan ana konularda tek parça (mikro=None) döner.
        """
        butce = _kalan_hedef(ders, makro, ana)
        if butce <= 0:
            return []
        tum_alts = alt_listesi(ana, mikro_alt)
        if not tum_alts:
            return [(None, butce, None)]
        alts = [a for a in tum_alts if (ders, ana, a) not in tamamlanan_alt]
        if not alts:
            return []
        sureler = {alt: _mikro_sure(ana, alt) for alt in alts}
        cozulen_mikro = {
            anahtar[2]: int(deger or 0)
            for anahtar, deger in mikro_cozulen.items()
            if anahtar[0] == ders and anahtar[1] == ana
        }
        if cozulen_mikro:
            hedef_tam = _mikro_hedef(
                ders, makro, ana, mufredat, soru_agirliklari, konu_sureleri
            )
            paylar = mikro_soru_paylari(hedef_tam, tum_alts)
        else:
            paylar = mikro_soru_paylari(butce, alts)
        dilimler = []
        kalan_butce = butce
        for alt in alts:
            pay = int(paylar.get(alt, 0)) - int(cozulen_mikro.get(alt, 0))
            pay = max(0, min(pay, kalan_butce))
            if pay <= 0:
                continue
            kalan_butce -= pay
            dilimler.append((alt, pay, sureler.get(alt)))
        return dilimler

    # 1) Devir + 2) tekrar (devir kendi mikro konusuna bağlanır)
    for gorev in onceki:
        ders = gorev.get("ders")
        ana = gorev.get("mikro_konu")
        if not (ders and ana) or gorev.get("durum"):
            continue
        makro = gorev.get("makro_konu") or _makro_bul(mufredat, ders, ana)
        mikro = _tek_alt(gorev.get("alt_konu"))
        kalan = gorev_kalan_soru(gorev)
        if (gorev.get("pedagoji_turu") or "") == "Tekrar":
            _kuyruga_ekle({
                "oncelik": 2, "tur": "tekrar", "ders": ders, "makro": makro,
                "ana": ana, "mikro": mikro, "kalan": 5,
                "kaynak": gorev.get("id"), "pay_dk": None,
            })
            continue
        if kalan <= 0:
            continue
        tur = "devir" if ana in bilinen else "anlatim"
        _kuyruga_ekle({
            "oncelik": 1, "tur": tur, "ders": ders, "makro": makro,
            "ana": ana, "mikro": mikro, "kalan": kalan,
            "kaynak": gorev.get("id"), "pay_dk": None,
        })

    # 3) Alarm konuları
    for alarm in baglam.get("alarm_konular") or []:
        ders = alarm.get("ders")
        ana = alarm.get("konu") or alarm.get("mikro")
        if not (ders and ana):
            continue
        makro = _makro_bul(mufredat, ders, ana)
        dilimler = _mikro_dilimi(ders, makro, ana)
        if not dilimler:
            yedek = alt_listesi(ana, mikro_alt)[:1] or [None]
            dilimler = [(yedek[0], max(10, paragraf_soru), None)]
        for alt, pay, sure in dilimler:
            _kuyruga_ekle({
                "oncelik": 3,
                "tur": "alarm" if ana in bilinen else "anlatim",
                "ders": ders,
                "makro": makro,
                "ana": ana,
                "mikro": alt,
                "kalan": pay,
                "kaynak": None,
                "pay_dk": sure,
            })

    # 4) Yeni mikro konular (ön koşulu hazır)
    for ders, makro_dict in (mufredat or {}).items():
        if not isinstance(makro_dict, dict):
            continue
        for makro, mikrolar in makro_dict.items():
            if not isinstance(mikrolar, list):
                continue
            for ana in mikrolar:
                if ana in bilinen:
                    continue
                if not _on_kosul_hazir(ana, bilinen, kurallar):
                    continue
                for alt, pay, sure in _mikro_dilimi(ders, makro, ana):
                    if (ders, ana, alt) in planlanan:
                        continue
                    _kuyruga_ekle({
                        "oncelik": 4, "tur": "anlatim", "ders": ders,
                        "makro": makro, "ana": ana, "mikro": alt,
                        "kalan": pay, "kaynak": None, "pay_dk": sure,
                    })

    # 5) Pekiştirme (öğrenilmiş ama soru hedefi dolmamış)
    for (ders, ana), cozulen in list(gercek.items()):
        if ders is None or ana is None:
            continue
        makro = _makro_bul(mufredat, ders, ana)
        for alt, pay, sure in _mikro_dilimi(ders, makro, ana):
            _kuyruga_ekle({
                "oncelik": 5, "tur": "pes", "ders": ders, "makro": makro,
                "ana": ana, "mikro": alt, "kalan": pay, "kaynak": None,
                "pay_dk": None,
            })
    # ------------------------------------------------------------------
    # YERLEŞTİRME (günlük kapasite asla aşılmaz)
    # ------------------------------------------------------------------
    for tarih in gunler:
        kap = kapasite[tarih]
        if kap <= 0:
            continue  # dinlenme günü

        # 6) Günlük paragraf (tek oturuşluk, bölünmez)
        if paragraf_soru > 0:
            paragraf = task_steps.gorev_zenginlestir(
                {
                    "ders": "TYT Türkçe",
                    "makro_konu": "Paragraf",
                    "mikro_konu": "Günlük Paragraf",
                    "alt_konu": None,
                    "gorev_tanimi": "📖 Günlük paragraf: %d soru çöz." % paragraf_soru,
                    "hedef_soru": paragraf_soru,
                    "pedagoji_turu": "Ezber",
                    "gorev_turu": "soru",
                    "tarih": tarih.isoformat(),
                },
                ogrenci_id=ogrenci_id,
                konu_sureleri=konu_sureleri,
            )
            sure = int(paragraf.get("tahmini_sure_dk") or 0)
            if 0 < sure <= kap:
                gun_gorev[tarih].append(paragraf)
                gun_dk[tarih] += sure

        for _ in range(60):  # gün içi yerleştirme turu
            kalan_dk = kap - gun_dk[tarih]
            if kalan_dk < MIN_ANLAMLI_BLOK:
                break
            adaylar = sorted(
                kuyruk.items(),
                key=lambda cift: (cift[1]["oncelik"], -cift[1]["kalan"]),
            )
            yerlesti = False
            for oge_anahtar, oge in adaylar:
                if oge_anahtar in gun_mikro[tarih]:
                    continue  # aynı mikro konu aynı gün iki görev olmaz
                if oge["tur"] == "anlatim":
                    if gun_yeni[tarih] >= MAKS_YENI_MIKRO_GUN:
                        continue
                    if (
                        oge["ders"] in AGIR_DERSLER
                        and oge["ders"] in gun_yeni_ders[tarih]
                    ):
                        continue
                hedef_soru = oge["kalan"]
                if oge["tur"] == "anlatim":
                    hedef_soru = min(MAKS_GOREV_SORU, max(10, oge["kalan"] // 2), oge["kalan"])
                pedagoji = pedagoji_map.get(
                    (oge["ders"], oge["ana"]), "Pekiştirme"
                )
                gorev = _soru_sayisi_sigdir(
                    oge["tur"],
                    oge["ders"],
                    oge["makro"],
                    oge["ana"],
                    tarih,
                    int(hedef_soru or 0),
                    kalan_dk,
                    oge["kaynak"],
                    ogrenci_id,
                    konu_sureleri,
                    oge["mikro"],
                    pedagoji,
                    alt_sayisi=1,
                    sure_dk=oge.get("pay_dk"),
                )
                if gorev is None:
                    continue
                gun_gorev[tarih].append(gorev)
                gun_dk[tarih] += int(gorev.get("tahmini_sure_dk") or 0)
                gun_mikro[tarih].add(oge_anahtar)
                planlanan.add(oge_anahtar)
                oge["kalan"] = max(0, oge["kalan"] - int(gorev["hedef_soru"]))
                if oge["tur"] == "anlatim":
                    gun_yeni[tarih] += 1
                    gun_yeni_ders[tarih].add(oge["ders"])
                    # Devam görevi yalnızca soru içerir; anlatım tekrar edilmez.
                    oge["tur"] = "pes"
                    oge["pay_dk"] = None
                if oge["tur"] == "tekrar" or oge["kalan"] <= 0:
                    kuyruk.pop(oge_anahtar, None)
                yerlesti = True
                break
            if not yerlesti:
                break

    if kuyruk:
        uyarilar.append(
            "Bu haftanın kapasitesi tüm görevlere yetmedi; kalan işler bir"
            " sonraki programda devam edecek."
        )

    tum_gorevler = [g for tarih in gunler for g in gun_gorev[tarih]]
    gun_ozeti = [
        {
            "tarih": tarih.isoformat(),
            "gun": GUN_ADLARI[tarih.weekday()],
            "kapasite_dk": kapasite[tarih],
            "planlanan_dk": gun_dk[tarih],
            "gorev_sayisi": len(gun_gorev[tarih]),
            "dinlenme": kapasite[tarih] == 0,
        }
        for tarih in gunler
    ]
    return {
        "gorevler": tum_gorevler,
        "gun_ozeti": gun_ozeti,
        "uyarilar": uyarilar,
        "toplam_sure_dk": sum(gun_dk.values()),
        "toplam_soru": sum(int(g["hedef_soru"] or 0) for g in tum_gorevler),
    }



def _soru_sayisi_sigdir(
    tur, ders, makro, mikro, tarih, kalan_soru, kalan_dk,
    kaynak, ogrenci_id, konu_sureleri, alt_konu, pedagoji, alt_sayisi=1,
    sure_dk=None,
):
    """Kalan süreye sığan en büyük soru sayısıyla görevi üretir (yoksa None).

    FAZ 5D: mikro konunun hedefi 5'in altındaysa (ana konu kotası mikro
    konulara paylaştırıldığında oluşabilir) hedef küçültülmez; tek küçük blok
    olarak planlanır. Aksi hâlde bloklar 5-10 aralığında kalır.
    """
    adaylar = []
    for soru in (min(MAKS_GOREV_SORU, kalan_soru), 15, 10, 5):
        if soru < MIN_ANLAMLI_BLOK or soru > kalan_soru:
            continue
        if soru not in adaylar:
            adaylar.append(soru)
    if not adaylar and 0 < kalan_soru < MIN_ANLAMLI_BLOK:
        adaylar.append(int(kalan_soru))
    for soru in adaylar:
        gorev = _gorev_uret(
            tur, ders, makro, mikro, tarih, soru, kaynak, ogrenci_id,
            konu_sureleri, alt_konu=alt_konu, pedagoji=pedagoji,
            alt_sayisi=alt_sayisi, sure_dk=sure_dk,
        )
        if int(gorev.get("tahmini_sure_dk") or 0) <= kalan_dk:
            return gorev
    return None


def tum_gorevleri(baglam_sonuc):
    """Yardımcı: plan sonucundaki görev listesi."""
    return (baglam_sonuc or {}).get("gorevler") or []
