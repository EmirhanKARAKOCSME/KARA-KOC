"""Konu uyarıları / alarm motoru.

Deneme yanlış serilerinden ivmelenme ve tekrar sinyalleri üretir;
arayüz yalnızca sonucu gösterir."""


import pandas as pd

from config.database import get_connection
from data.prerequisites import ON_KOSULLAR
from data.weights_and_times import SINIF_SEVIYE_SKORU
from services.exam_service import (
    ALARM_MIN_YANLIS,
    ALARM_SERI_PENCERESI,
    kohort_yanlis_serileri,
)
from services.topic_progress import (
    get_aylik_mufredat_hedevi,
    hesapla_tyt_ayt_tamamlanma,
)


def _alarm_penceresi(seri, boyut=ALARM_SERI_PENCERESI):
    """Serinin SON `boyut` FARKLI denemesini döndürür.

    "3 farklı deneme" koşulu seri uzunluğundan değil, buradan gelir: aynı
    `deneme_id` iki kez sayılmaz (mükerrer kayıt koruması) ve bağlantısız
    (deneme_id = 0) noktalar pencereye alınmaz.
    """
    pencere = []
    gorulen = set()
    for nokta in reversed(list(seri or [])):
        kimlik = int(nokta.get("deneme_id") or 0)
        if kimlik <= 0 or kimlik in gorulen:
            continue
        gorulen.add(kimlik)
        pencere.append(nokta)
        if len(pencere) >= boyut:
            break
    pencere.reverse()
    return pencere


def _alarm_ivmeleniyor(degerler):
    """Yanlış sayısı kesintisiz artıyor mu? (örn. 1 ➔ 2 ➔ 4)"""
    return (
        len(degerler) >= ALARM_SERI_PENCERESI
        and all(deger >= ALARM_MIN_YANLIS for deger in degerler)
        and all(
            onceki < sonraki for onceki, sonraki in zip(degerler, degerler[1:])
        )
    )


def _alarm_tekrar_ediyor(degerler):
    """Yanlış her denemede var ama azalmıyor / artmıyor mu? (örn. 2 ➔ 2 ➔ 1)"""
    return (
        len(degerler) >= ALARM_SERI_PENCERESI
        and all(deger >= ALARM_MIN_YANLIS for deger in degerler)
        and all(
            onceki >= sonraki for onceki, sonraki in zip(degerler, degerler[1:])
        )
    )


def hesapla_tum_alarmlar(ogrenci_id, mevcut_sinif, aktif_mufredat):
    alarmlar = {"siyah": [], "kirmizi": [], "mor": [], "turuncu": [], "mavi": []}
    ogrenci_skor = SINIF_SEVIYE_SKORU.get(mevcut_sinif, 4)

    with get_connection() as c:
        df_bilinen = pd.read_sql_query(
            "SELECT ders, makro_konu, mikro_konu FROM konu_durumlari_detay"
            " WHERE ogrenci_id = ? AND durum = 'Biliyorum'",
            c,
            params=(ogrenci_id,),
        )
        # FAZ 2: Alarm yalnızca deneme başlığına BAĞLI yanlış kayıtlarıyla
        # hesaplanır. deneme_id'si NULL olan eski kayıtlar sessizce yutulmaz;
        # arayüzde "bağlanmamış kayıt" uyarısıyla raporlanır.
        df_yanlislar = pd.read_sql_query(
            "SELECT y.id, y.deneme_id, y.deneme_adi, y.tarih, y.ders,"
            " y.makro_konu, y.konu_adi, y.yanlis_adedi, y.yanlis_nedeni,"
            " d.tarih AS deneme_tarih, d.deneme_turu AS deneme_turu,"
            " d.deneme_kategorisi AS deneme_kategorisi,"
            " d.brans_dersi AS brans_dersi,"
            " d.net_bilgisi AS deneme_net_bilgisi,"
            " d.dogru_adedi AS deneme_dogru_adedi,"
            " d.yanlis_adedi AS deneme_yanlis_adedi,"
            " d.bos_adedi AS deneme_bos_adedi,"
            " d.sure_dk AS deneme_sure_dk"
            " FROM deneme_konu_yanlislari y"
            " JOIN denemeler d ON d.id = y.deneme_id"
            " WHERE y.ogrenci_id = ? AND (y.durum IS NULL OR y.durum = 'Aktif')"
            " ORDER BY y.id ASC",
            c,
            params=(ogrenci_id,),
        )
        df_gorevler = pd.read_sql_query(
            "SELECT makro_konu, mikro_konu FROM calisma_programi_gorevler WHERE"
            " ogrenci_id = ?",
            c,
            params=(ogrenci_id,),
        )

    bilinen_pairs = set(zip(df_bilinen["ders"], df_bilinen["mikro_konu"]))
    bilinen_mikro_set = set(df_bilinen["mikro_konu"].tolist())
    bilinen_makro_set = set(df_bilinen["makro_konu"].tolist())
    bilinen_dersler_set = set(df_bilinen["ders"].tolist())

    yanlis_konular_set = (
        set(df_yanlislar["konu_adi"].tolist())
        if not df_yanlislar.empty
        else set()
    )
    aktif_gorevler_set = (
        set(df_gorevler["mikro_konu"].tolist()).union(
            set(df_gorevler["makro_konu"].tolist())
        )
        if not df_gorevler.empty
        else set()
    )

    if not df_yanlislar.empty:
        # FAZ 2: Sınav kohortu bazlı seri. Her nokta TEK bir deneme_id'dir;
        # sıralama deneme tarihine, eşitlik durumunda deneme_id'ye göredir.
        kohortler = kohort_yanlis_serileri(df_yanlislar)
        for (ders, konu, _tur, _kategori, _brans), seri in kohortler.items():
            yanlis_ids = [i for nokta in seri for i in nokta["ids"]]
            # Yalnızca GERÇEKTEN çözülmüş, BİRBİRİNDEN FARKLI son 3 deneme.
            pencere = _alarm_penceresi(seri)
            yanlis_listesi = [nokta["yanlis"] for nokta in pencere]
            son_yanlis = yanlis_listesi[-1] if yanlis_listesi else 0
            son_neden = pencere[-1]["neden"] if pencere else ""

            cta_text = (
                "Bu konudaki eksiğini haftalarca tek başına kapatmaya çalışmak yerine "
                "1-2 saatlik birebir özel ders seansıyla anında çözebilirsin."
            )

            # ⬛ Siyah Alarm: 3 FARKLI denemede yanlış sayısı sürekli artıyorsa (1 ➔ 2 ➔ 4)
            if _alarm_ivmeleniyor(yanlis_listesi):
                alarmlar["siyah"].append({
                    "id_list": yanlis_ids,
                    "ders": ders,
                    "konu": konu,
                    "detay": (
                        f"Son 3 farklı denemedir yanlış sayısı ivmelenerek artıyor! "
                        f"({yanlis_listesi[-3]} ➔ {yanlis_listesi[-2]} ➔ {yanlis_listesi[-1]})"
                    ),
                    "aksiyon": cta_text,
                    "neden": son_neden,
                })

            # 🟣 Mor Alarm: 3 FARKLI denemede her seferinde yanlış var ve sayı
            # artmıyorsa (örn. 2 ➔ 2 ➔ 1). Tek denemenin tekrarı veya sıfır
            # yanlışlı deneme bu alarmı ÜRETMEZ.
            elif _alarm_tekrar_ediyor(yanlis_listesi):
                alarmlar["mor"].append({
                    "id_list": yanlis_ids,
                    "ders": ders,
                    "konu": konu,
                    "detay": (
                        "Son 3 farklı denemedir bu konuda düzenli olarak yanlış"
                        f" yapılıyor ({yanlis_listesi[-3]} ➔ {yanlis_listesi[-2]}"
                        f" ➔ {yanlis_listesi[-1]})."
                    ),
                    "aksiyon": cta_text,
                    "neden": son_neden,
                })

            # 🔴 Kırmızı Alarm: "Biliyorum" olarak işaretlenen müfredat konusunda yanlış yapıldığında
            if (ders, konu) in bilinen_pairs:
                alarmlar["kirmizi"].append({
                    "id_list": yanlis_ids,
                    "ders": ders,
                    "konu": konu,
                    "detay": (
                        f"Tamamlandı ('Biliyorum') olarak işaretlenen konuda {son_yanlis} yanlış yapıldı!"
                    ),
                    "aksiyon": cta_text,
                    "neden": son_neden,
                })

    for hedef_konu, kural in ON_KOSULLAR.items():
        min_sinif = kural["min_sinif"]
        on_kosul_listesi = kural["on_kosul"]
        hedef_ders = kural.get("ders", "")

        if hedef_konu in bilinen_mikro_set or hedef_konu in bilinen_makro_set:
            continue

        if ogrenci_skor >= min_sinif:
            ders_aktif_mi = hedef_ders in bilinen_dersler_set or any(
                d == hedef_ders for d in df_yanlislar["ders"].tolist()
            )
            baglam_tetiklendi = ders_aktif_mi and (
                hedef_konu in yanlis_konular_set
                or hedef_konu in aktif_gorevler_set
                or len(bilinen_makro_set) >= 3
            )

            if baglam_tetiklendi:
                # Eksik ön koşullar TEK uyarıda toplanır; her ön koşul için
                # ayrı alarm/görev kartı üretilmez.
                eksikler = [
                    ok
                    for ok in on_kosul_listesi
                    if (
                        ok not in bilinen_mikro_set
                        and ok not in bilinen_makro_set
                    )
                ]
                if eksikler:
                    eksik_metni = ", ".join(eksikler)
                    alarmlar["turuncu"].append({
                        "ders": (
                            hedef_ders
                            if hedef_ders
                            else "İleri Seviye Odak Konusu"
                        ),
                        "konu": f"{hedef_konu} - Eksikler: {eksik_metni}",
                        "hedef_konu": hedef_konu,
                        "eksikler": eksikler,
                        "detay": (
                            f"'{hedef_konu}' konusunu iyi anlamak için önce"
                            f" **{eksik_metni}** konusunu tamamlamalısınız."
                        ),
                        "aksiyon": (
                            f"Önce '{eksik_metni}' konusunun temelini çalışın."
                        ),
                        "neden": "Ön Koşul Eksikliği",
                    })

    (
        tyt_o,
        ayt_o,
        gercek_tamamlanma_orani,
    ) = hesapla_tyt_ayt_tamamlanma(ogrenci_id, aktif_mufredat)
    ay_adi, hedef_yuzde = get_aylik_mufredat_hedevi(mevcut_sinif)
    delta_yuzde = round(gercek_tamamlanma_orani - hedef_yuzde, 1)

    if delta_yuzde < 0 and gercek_tamamlanma_orani < 100.0:
        alarmlar["mavi"].append({
            "ders": "Müfredat Takvimi",
            "konu": (
                f"{ay_adi} Ayı Hedefi (%{abs(delta_yuzde)} Geride)"
            ),
            "detay": (
                f"{ay_adi} ayı hedeflenen tamamlama oranının"
                f" **-%{abs(delta_yuzde)}** gerisindesiniz."
            ),
            "aksiyon": "Haftalık çalışma temanıza 1 ek çalışma bloğu ekleyin.",
            "neden": "Takvim Geriliği",
        })

    mufredat_cezasi = abs(delta_yuzde) * 1.5 if delta_yuzde < 0 else 0.0
    alarm_cezasi = (
        len(alarmlar["siyah"]) * 8.0
        + len(alarmlar["kirmizi"]) * 5.0
        + len(alarmlar["mor"]) * 3.0
        + len(alarmlar["turuncu"]) * 2.0
    )

    if (
        gercek_tamamlanma_orani >= 100.0
        and sum(len(v) for v in alarmlar.values()) == 0
    ):
        saglik_skoru = 100
    else:
        saglik_skoru = max(
            25, min(100, int(100.0 - mufredat_cezasi - alarm_cezasi))
        )

    return alarmlar, saglik_skoru, delta_yuzde, gercek_tamamlanma_orani, hedef_yuzde
