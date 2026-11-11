"""Sekme 8 - Haftalık Performans Merkezi."""


import pandas as pd
import streamlit as st

from config.database import log_islem
from services import weekly_report
from views.shared import set_flash_message


def _hafta_yuzde_metni(deger):
    """25.0 -> '%25', 33.33 -> '%33.3', None -> '—'."""
    if deger is None:
        return "—"
    try:
        metin = ("%.1f" % float(deger)).rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "—"
    return "%" + metin


def _hafta_deger_metni(alan, deger):
    """Karşılaştırma tablosu için okunur değer metni."""
    if deger is None:
        return "—"
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        return str(deger)
    if alan == "dk":
        return weekly_report.sure_metni(sayi)
    if alan == "deneme_net":
        return "%.2f" % sayi
    if alan == "uyum":
        return _hafta_yuzde_metni(sayi)
    if abs(sayi - round(sayi)) < 0.001:
        return "%d" % int(round(sayi))
    return "%.1f" % sayi


def _hafta_fark_metni(alan, fark, birim=""):
    """Sayısal değişimin işaretli metni ('+45 dk', '−2 soru')."""
    if fark is None:
        return "—"
    try:
        fark = float(fark)
    except (TypeError, ValueError):
        return "—"
    if abs(fark) < 0.005:
        return "değişim yok"
    isaret = "+" if fark > 0 else "−"
    mutlak = abs(fark)
    if alan == "dk":
        return isaret + weekly_report.sure_metni(mutlak)
    if alan == "deneme_net":
        return "%s%.2f net" % (isaret, mutlak)
    if abs(mutlak - round(mutlak)) < 0.001:
        return "%s%d %s" % (isaret, int(round(mutlak)), birim)
    return "%s%.1f %s" % (isaret, mutlak, birim)


def render(ctx):
    st.header("📈 Haftalık Performans Merkezi")
    st.caption(
        "Rapor her açılışta canlı veriden üretilir (ayrı kopya saklanmaz)."
        " Hafta Pazartesi–Pazar'dır. Devam eden hafta, geçen haftanın aynı"
        " uzunluktaki dönemiyle karşılaştırılır; gelecek haftalarda"
        " karşılaştırma yapılmaz."
    )

    hafta_secenekleri = weekly_report.hafta_secenekleri(12)
    hafta_etiketleri = [
        ("%s  ·  bu hafta" % s["etiket"]) if s["bu_hafta"] else s["etiket"]
        for s in hafta_secenekleri
    ]
    secilen_hafta_etiketi = st.selectbox(
        "Rapor haftası", hafta_etiketleri, key="hafta_perf_hafta_secimi"
    )
    secilen_hafta = hafta_secenekleri[
        hafta_etiketleri.index(secilen_hafta_etiketi)
    ]

    hafta_raporu = None
    try:
        hafta_raporu = weekly_report.rapor_uret(
            ctx.user["id"], secilen_hafta["baslangic"]
        )
    except weekly_report.HaftalikRaporHatasi as rapor_hatasi:
        st.error("Haftalık rapor üretilemedi: %s" % rapor_hatasi)

    if hafta_raporu is not None:
        hafta_bilgi = hafta_raporu["hafta"]
        hafta_ozet = hafta_raporu["ozet"]
        hafta_kars = hafta_raporu["karsilastirma"]
        fark_haritasi = {a["alan"]: a for a in hafta_kars["alanlar"]}

        def _metrik_delta(alan):
            kayit = fark_haritasi.get(alan)
            if not kayit:
                return None
            return _hafta_fark_metni(alan, kayit["fark"], kayit["birim"])

        st.subheader("🗓️ %s" % hafta_bilgi["etiket"])
        st.caption(
            "%s · Ölçülen gün: %d/%d · Karşılaştırma: %s"
            % (
                hafta_bilgi["durum_metni"],
                hafta_bilgi["olculen_gun"],
                hafta_bilgi["toplam_gun"],
                (
                    "geçen haftanın aynı dönemi"
                    if hafta_kars["donem"] == "esit_uzunluk"
                    else "geçen hafta"
                ),
            )
        )
        if hafta_bilgi["gelecek"]:
            st.info(
                "Bu hafta henüz başlamadı; performans sayıları hafta"
                " başlayınca oluşur. Aşağıdan hedeflerinizi önceden"
                " planlayabilirsiniz."
            )

        olcu_a, olcu_b, olcu_c, olcu_d, olcu_e = st.columns(5)
        olcu_a.metric(
            "Çalışma süresi",
            weekly_report.sure_metni(hafta_ozet["dk"]),
            delta=_metrik_delta("dk"),
        )
        olcu_b.metric(
            "Çözülen soru", hafta_ozet["soru"], delta=_metrik_delta("soru")
        )
        olcu_c.metric(
            "Aktif gün",
            "%d / 7" % hafta_ozet["aktif_gun"],
            delta=_metrik_delta("aktif_gun"),
        )
        olcu_d.metric(
            "Program uyumu",
            _hafta_deger_metni("uyum", hafta_ozet["uyum"]),
            delta=_metrik_delta("uyum"),
        )
        olcu_e.metric(
            "Deneme neti",
            _hafta_deger_metni("deneme_net", hafta_ozet["deneme_net"]),
            delta=_metrik_delta("deneme_net"),
        )

        olcu_f, olcu_g, olcu_h = st.columns(3)
        olcu_f.metric(
            "Tamamlanan görev",
            "%d / %d" % (
                hafta_ozet["tamamlanan_gorev"],
                hafta_ozet["planlanan_gorev"],
            ),
        )
        olcu_g.metric(
            "Tamamlanan tekrar",
            "%d / %d" % (
                hafta_ozet["tamamlanan_tekrar"],
                hafta_ozet["tekrar_planlanan"],
            ),
            delta=_metrik_delta("tamamlanan_tekrar"),
        )
        olcu_h.metric(
            "Defterde bekleyen yanlış",
            hafta_ozet["bekleyen_yanlis"],
            delta=_metrik_delta("bekleyen_yanlis"),
        )

        st.markdown("---")
        st.subheader("🔁 Önceki Dönemle Karşılaştırma")
        if not hafta_kars["kullanilabilir"]:
            if hafta_bilgi["gelecek"]:
                st.info("Gelecek haftalar için karşılaştırma yapılmaz.")
            elif not hafta_kars["onceki_veri_var"]:
                st.info(
                    "Önceki dönemde hiç kayıt bulunmadığı için karşılaştırma"
                    " üretilmedi: 'kayıt yok' ile 'kayıtlı sıfır' aynı şey"
                    " değildir."
                )
            else:
                st.info(
                    "Karşılaştırma için bu dönemde de en az bir kayıt"
                    " gerekiyor."
                )
        else:
            kars_df = pd.DataFrame(
                [
                    {
                        "Metrik": a["etiket"],
                        "Bu dönem": _hafta_deger_metni(
                            a["alan"], a["gercek"]
                        ),
                        "Önceki dönem": _hafta_deger_metni(
                            a["alan"], a["onceki"]
                        ),
                        "Fark": _hafta_fark_metni(
                            a["alan"], a["fark"], a["birim"]
                        ),
                        "Değişim %": (
                            "—" if a["yuzde"] is None
                            else "%+.1f%%" % a["yuzde"]
                        ),
                    }
                    for a in hafta_kars["alanlar"]
                ]
            )
            st.dataframe(kars_df, width="stretch", hide_index=True)

        # ------------------------------------------------------------------
        # HEDEFLER
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("🎯 Haftalık Hedefler")
        hedef_ozet = hafta_raporu["hedefler"]["ozet"]
        hedef_kartlari = hafta_raporu["hedefler"]["ilerleme"]
        if hedef_ozet["adet"]:
            st.caption(
                "Hedef: %d · Tamamlanan: %d · Yaklaşan: %d · Devam eden:"
                " %d · Veri bekleyen: %d · Ortalama gerçekleşme: %s"
                % (
                    hedef_ozet["adet"],
                    hedef_ozet["tamamlanan"],
                    hedef_ozet["yaklasan"],
                    hedef_ozet["devam"],
                    hedef_ozet["veri_bekleyen"],
                    _hafta_yuzde_metni(hedef_ozet["ortalama_oran"]),
                )
            )
            for kart in hedef_kartlari:
                hedef_sol, hedef_sag = st.columns([6, 1])
                with hedef_sol:
                    st.markdown(
                        "**%s** · %s" % (kart["etiket"], kart["durum"])
                    )
                    st.caption(
                        "Hedef: %s · Gerçekleşen: %s · Kalan: %s"
                        % (
                            kart["hedef_metin"],
                            kart["gercek_metin"],
                            kart["kalan_metin"],
                        )
                    )
                    if kart["oran"] is not None:
                        st.progress(
                            max(0.0, min(1.0, kart["oran"] / 100.0)),
                            text=_hafta_yuzde_metni(kart["oran_ham"]),
                        )
                    else:
                        st.caption("Bu hedef için henüz veri yok.")
                with hedef_sag:
                    if st.button(
                        "🗑️",
                        key="hafta_hedef_sil_%d" % kart["id"],
                        help="Hedefi sil",
                    ):
                        if weekly_report.hedef_sil(
                            kart["id"], ctx.user["id"]
                        ):
                            set_flash_message(
                                "success",
                                "'%s' hedefi silindi." % kart["etiket"],
                            )
                        st.rerun()
        else:
            st.info(
                "Bu hafta için henüz hedef tanımlanmadı. Aşağıdaki formdan"
                " ekleyebilir veya geçen haftanın hedeflerini"
                " kopyalayabilirsiniz."
            )


        hedef_ders_secenekleri = sorted(
            set(ctx.mufredat.keys())
            | {
                d["ders"]
                for d in (hafta_raporu["dersler"] or [])
                if d.get("ders")
            }
        )
        if not hedef_ders_secenekleri:
            hedef_ders_secenekleri = ["Genel"]

        with st.expander(
            "➕ Hedef ekle / güncelle", expanded=not hedef_kartlari
        ):
            with st.form("hafta_hedef_formu"):
                hedef_tur_etiketleri = [
                    t["etiket"] for t in weekly_report.HEDEF_TURLERI.values()
                ]
                hedef_tur_kodlari = list(weekly_report.HEDEF_TURLERI.keys())
                secilen_tur_etiketi = st.selectbox(
                    "Hedef türü",
                    hedef_tur_etiketleri,
                    key="hafta_hedef_tur",
                )
                hedef_tur = hedef_tur_kodlari[
                    hedef_tur_etiketleri.index(secilen_tur_etiketi)
                ]
                hedef_tanimi = weekly_report.HEDEF_TURLERI[hedef_tur]
                hedef_ders = ""
                if hedef_tanimi["ders_gerekli"]:
                    hedef_ders = st.selectbox(
                        "Ders",
                        hedef_ders_secenekleri,
                        key="hafta_hedef_ders",
                    )
                # Süre hedefleri saat olarak girilir; servis dakika bekler.
                saat_cinsinden = hedef_tanimi["birim"] == "dk"
                birim_metni = (
                    "saat" if saat_cinsinden else hedef_tanimi["birim"]
                )
                maks_girdi = (
                    float(hedef_tanimi["maks"]) / 60.0
                    if saat_cinsinden
                    else float(hedef_tanimi["maks"])
                )
                # Widget anahtarı hedef türüne (ve haftaya) göre ayrılır: tür
                # değişince önceki değer taşınmaz (dk/soru/% karışması olmaz).
                hedef_deger_anahtari = "hafta_hedef_deger_%s_%s" % (
                    secilen_hafta["baslangic"],
                    hedef_tur,
                )
                if hedef_deger_anahtari not in st.session_state:
                    st.session_state[hedef_deger_anahtari] = 1.0
                hedef_deger_girdisi = st.number_input(
                    "Hedef değer (%s)" % birim_metni,
                    min_value=0.0,
                    max_value=maks_girdi,
                    step=0.5 if saat_cinsinden else 1.0,
                    key=hedef_deger_anahtari,
                )

                st.caption(
                    "Aynı hafta + hedef türü + ders için tek kayıt tutulur;"
                    " yeniden kaydetmek değeri günceller."
                )
                if st.form_submit_button(
                    "💾 Hedefi Kaydet", type="primary"
                ):
                    hedef_degeri = (
                        round(hedef_deger_girdisi * 60.0, 1)
                        if saat_cinsinden
                        else hedef_deger_girdisi
                    )
                    try:
                        weekly_report.hedef_kaydet(
                            ctx.user["id"],
                            secilen_hafta["baslangic"],
                            hedef_tur,
                            hedef_degeri,
                            ders=hedef_ders or None,
                        )
                    except weekly_report.HaftalikRaporHatasi as hedef_hatasi:
                        st.error(
                            "Hedef kaydedilemedi: %s" % hedef_hatasi
                        )
                    else:
                        log_islem(
                            ctx.user["id"],
                            "WEEKLY_GOAL_SAVE",
                            "%s = %s (%s)"
                            % (
                                secilen_tur_etiketi,
                                hedef_deger_girdisi,
                                birim_metni,
                            ),
                        )
                        set_flash_message(
                            "success",
                            "'%s' hedefi %s haftası için kaydedildi."
                            % (secilen_tur_etiketi, hafta_bilgi["kisa"]),
                        )
                        st.rerun()

        if st.button(
            "📋 Geçen haftanın hedeflerini bu haftaya kopyala",
            key="hafta_hedef_kopyala",
        ):
            try:
                kopya = weekly_report.hedefleri_kopyala(
                    ctx.user["id"],
                    weekly_report.onceki_hafta(
                        secilen_hafta["baslangic"]
                    ),
                    secilen_hafta["baslangic"],
                )
            except weekly_report.HaftalikRaporHatasi as kopya_hatasi:
                st.error("Hedefler kopyalanamadı: %s" % kopya_hatasi)
            else:
                if kopya["kopyalanan"]:
                    set_flash_message(
                        "success",
                        "%d hedef kopyalandı (kaynak hafta: %s)."
                        % (kopya["kopyalanan"], kopya["kaynak_hafta"]),
                    )
                else:
                    set_flash_message(
                        "info",
                        "Kopyalanacak yeni hedef yok; bu haftanın hedefleri"
                        " güncel.",
                    )
                st.rerun()


        # ------------------------------------------------------------------
        # DERS BAZLI DAĞILIM
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("📚 Ders Bazlı Dağılım")
        if not hafta_raporu["dersler"]:
            st.info("Bu hafta ders bazlı çalışma/deneme kaydı bulunmuyor.")
        else:
            ders_df = pd.DataFrame(
                [
                    {
                        "Ders": d["ders"],
                        "Süre (dk)": d["dk"],
                        "Soru": d["soru"],
                        "Soru/saat": d["soru_saat"],
                        "Oturum": d["oturum"],
                        "Doğru": d["dogru"],
                        "Yanlış": d["yanlis"],
                        "Başarı %": d["basari_orani"],
                        "Tamamlanan görev": d["gorev_tamam"],
                        "Mikro konu": d["mikro_sayisi"],
                        "Deneme neti": d["deneme_net_ort"],
                    }
                    for d in hafta_raporu["dersler"]
                ]
            )
            st.dataframe(ders_df, width="stretch", hide_index=True)
            sure_df = pd.DataFrame(
                [
                    {"Ders": d["ders"], "Süre (dk)": d["dk"]}
                    for d in hafta_raporu["dersler"]
                    if d["dk"]
                ]
            )
            if not sure_df.empty:
                st.bar_chart(sure_df.set_index("Ders")["Süre (dk)"])
            else:
                st.caption("Süre kaydı bulunmadığı için süre grafiği yok.")

        # ------------------------------------------------------------------
        # MİKRO KONU TAKİBİ
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("🔬 Mikro Konu Takibi")
        mikro_ozet = hafta_raporu["mikro"] or {}
        if not mikro_ozet.get("veri_var"):
            st.info("Bu hafta mikro konu bazlı kayıt bulunmuyor.")
        else:
            st.caption(
                "Çalışılan mikro konu: %d · Öğrenme adımları tamam: %d ·"
                " Soru hedefine ulaşan: %d · Uygulamada 'Biliyorum'"
                " beyanı: %d"
                % (
                    mikro_ozet["calisilan_mikro_sayisi"],
                    len(mikro_ozet["tamamlanan"]),
                    len(mikro_ozet["hedefe_ulasan"]),
                    mikro_ozet["beyan_ogrenildi"],
                )
            )
            st.caption(mikro_ozet["beyan_notu"])
            if mikro_ozet["calisilan"]:
                mikro_df = pd.DataFrame(
                    [
                        {
                            "Ders": k["ders"],
                            "Makro konu": k["makro_konu"],
                            "Mikro konu": k["mikro_konu"],
                            "Alt başlık": k["alt_konu"] or "",
                            "Süre (dk)": k["dk"],
                            "Soru": k["soru"],
                            "Gün": k["gun_sayisi"],
                            "Öğrenme": "✔" if k["ogrenme_tamam"] else "",
                            "Hedef soru": k["hedef_soru"],
                            "Çözülen soru": k["cozulen_soru"],
                        }
                        for k in mikro_ozet["calisilan"][:25]
                    ]
                )
                st.dataframe(mikro_df, width="stretch", hide_index=True)
                st.caption(
                    "Haftalık soru ile konunun TOPLAM çözülen sorusu ayrı"
                    " sütunlardadır; 'Soru' yalnızca bu haftanın sayısıdır."
                )
            else:
                st.info("Bu hafta çalışılmış mikro konu kaydı yok.")

            if mikro_ozet["bekleyen_konular"]:
                with st.expander("⏳ Soru hedefi tamamlanmayan konular"):
                    bekleyen_df = pd.DataFrame(
                        [
                            {
                                "Ders": k["ders"],
                                "Makro konu": k["makro_konu"],
                                "Mikro konu": k["mikro_konu"],
                                "Hedef soru": k["hedef_soru"],
                                "Çözülen soru": k["cozulen_soru"],
                                "Kalan": k["kalan"],
                                "Öğrenme": "✔" if k["ogrenme_tamam"] else "",
                            }
                            for k in mikro_ozet["bekleyen_konular"]
                        ]
                    )
                    st.dataframe(
                        bekleyen_df, width="stretch", hide_index=True
                    )
            if mikro_ozet["yanlis_biriken"]:
                with st.expander("📕 Defterde biriken yanlış sorular"):
                    biriken_df = pd.DataFrame(
                        [
                            {
                                "Ders": k["ders"],
                                "Mikro konu": k["mikro_konu"],
                                "Bekleyen soru": k["adet"],
                            }
                            for k in mikro_ozet["yanlis_biriken"]
                        ]
                    )
                    st.dataframe(
                        biriken_df, width="stretch", hide_index=True
                    )


        # ------------------------------------------------------------------
        # TEKRAR & YANLIŞ SORU DEFTERİ
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("🔁 Tekrar & Yanlış Soru Defteri")
        tekrar_ozet = hafta_raporu["tekrar"]
        defter_ozet = hafta_raporu["defter"]

        tekrar_a, tekrar_b, tekrar_c, tekrar_d = st.columns(4)
        tekrar_a.metric("Planlanan tekrar", tekrar_ozet["planlanan"])
        tekrar_b.metric(
            "Tamamlanan tekrar",
            tekrar_ozet["tamamlanan"],
            delta=(
                None
                if tekrar_ozet["tamamlama_orani"] is None
                else _hafta_yuzde_metni(tekrar_ozet["tamamlama_orani"])
            ),
        )
        tekrar_c.metric("Bekleyen tekrar", tekrar_ozet["bekleyen"])
        tekrar_d.metric(
            "Stokta bekleyen tekrar", tekrar_ozet["stok_bekleyen"]
        )
        if tekrar_ozet["gecikmis_bekleyen"] or tekrar_ozet["gecikmis_tamamlanan"]:
            st.caption(
                "Gecikmiş (bu hafta bekleyen): %d · Önceki haftadan"
                " tamamlanan: %d · İptal edilen: %d"
                % (
                    tekrar_ozet["gecikmis_bekleyen"],
                    tekrar_ozet["gecikmis_tamamlanan"],
                    tekrar_ozet["iptal"],
                )
            )
        if tekrar_ozet["kartlar"]:
            with st.expander("📇 Bu haftanın tekrar kartları"):
                tekrar_df = pd.DataFrame(
                    [
                        {
                            "Planlanan tarih": k["planlanan_tarih"],
                            "Ders": k["ders"],
                            "Makro konu": k["makro_konu"],
                            "Mikro konu": k["mikro_konu"],
                            "Alt başlık": k["alt_konu"] or "",
                            "Durum": k["durum"],
                            "Tamamlanma": k["tamam_gun"] or "",
                        }
                        for k in tekrar_ozet["kartlar"]
                    ]
                )
                st.dataframe(tekrar_df, width="stretch", hide_index=True)

        st.markdown("#### 📕 Yanlış Soru Defteri Akışı")
        defter_a, defter_b, defter_c, defter_d, defter_e = st.columns(5)
        defter_a.metric("Hafta başı bekleyen", defter_ozet["baslangic_bekleyen"])
        defter_b.metric(
            "Hafta sonu bekleyen",
            defter_ozet["bitis_bekleyen"],
            delta=_hafta_fark_metni(
                "bekleyen_yanlis", defter_ozet["degisim"], "soru"
            ),
        )
        defter_c.metric("Yeni eklenen", defter_ozet["eklenen"])
        defter_d.metric("Öğrenilen", defter_ozet["ogrenilen"])
        defter_e.metric("Yeniden çözülen", defter_ozet["yeniden_cozulen"])
        st.caption(
            "Arşivlenen: %d · Bugün defterde duran aktif kayıt: %d"
            % (defter_ozet["arsivlenen"], defter_ozet["aktif_toplam"])
        )
        st.caption(defter_ozet["not"])

        # ------------------------------------------------------------------
        # DENEMELER
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("📝 Haftanın Denemeleri")
        deneme_ozet = hafta_raporu["denemeler"]
        if not deneme_ozet["adet"]:
            st.info("Bu hafta deneme kaydı bulunmuyor.")
        else:
            deneme_df = pd.DataFrame(
                [
                    {
                        "Tarih": n["gun"],
                        "Deneme": n["ad"],
                        "Tür": n["tur"],
                        "Kategori": n["kategori"],
                        "Net": (
                            "—" if n["net"] is None
                            else ("%.2f" % float(n["net"]))
                        ),
                        "Doğru": n["dogru"],
                        "Yanlış": n["yanlis"],
                        "Boş": n["bos"],
                    }
                    for n in deneme_ozet["netler"]
                ]
            )
            st.dataframe(deneme_df, width="stretch", hide_index=True)
            st.caption(
                "Deneme sayısı: %d · Net ortalaması: %s"
                % (
                    deneme_ozet["adet"],
                    _hafta_deger_metni("deneme_net", deneme_ozet["net_ort"]),
                )
            )
            if deneme_ozet["turler"]:
                tur_df = pd.DataFrame(
                    [
                        {
                            "Tür": tur,
                            "Adet": kayit["adet"],
                            "Net ortalaması": kayit["net_ort"],
                        }
                        for tur, kayit in sorted(deneme_ozet["turler"].items())
                    ]
                )
                st.dataframe(tur_df, width="stretch", hide_index=True)
            if deneme_ozet["dersler"]:
                with st.expander("📊 Deneme ders kırılımı"):
                    ders_df = pd.DataFrame(
                        [
                            {
                                "Ders": d["ders"],
                                "Adet": d["adet"],
                                "Doğru": d["dogru"],
                                "Yanlış": d["yanlis"],
                                "Boş": d["bos"],
                                "Net ortalaması": d["net_ort"],
                            }
                            for d in deneme_ozet["dersler"]
                        ]
                    )
                    st.dataframe(ders_df, width="stretch", hide_index=True)


        # ------------------------------------------------------------------
        # HAFTALIK TREND (SON 8 HAFTA)
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("📈 Haftalık Trend")
        trend_serisi = weekly_report.haftalik_seri(
            ctx.user["id"], weekly_report.VARSAYILAN_SERI_HAFTA
        )
        if not weekly_report.trend_yeterli_mi(trend_serisi):
            st.info(
                "Trend grafiği için en az %d hafta veri gerekiyor."
                % weekly_report.GRAFIK_MIN_HAFTA
            )
        else:
            st.caption(
                "Son %d hafta. Ham haftalık değerle birlikte 4 haftalık"
                " ortalama gösterilir; ortalama tek haftalık dalgalanmayı"
                " yumuşatır."
                % len(trend_serisi)
            )
            trend_temel = pd.DataFrame(
                {
                    "Hafta": [s["kisa"] for s in trend_serisi],
                    "Süre (dk)": [s["dk"] for s in trend_serisi],
                    "Süre ortalaması": weekly_report.seri_ortalama_serisi(
                        trend_serisi, "dk", 4
                    ),
                    "Çözülen soru": [s["soru"] for s in trend_serisi],
                    "Soru ortalaması": weekly_report.seri_ortalama_serisi(
                        trend_serisi, "soru", 4
                    ),
                    "Program uyumu": [s["uyum"] for s in trend_serisi],
                }
            ).set_index("Hafta")
            st.line_chart(trend_temel[["Süre (dk)", "Süre ortalaması"]])
            st.line_chart(trend_temel[["Çözülen soru", "Soru ortalaması"]])
            if trend_temel["Program uyumu"].notna().any():
                st.line_chart(trend_temel[["Program uyumu"]])
            net_noktalari = [
                (s["kisa"], float(s["deneme_net"]))
                for s in trend_serisi
                if s["deneme_net"] is not None
            ]
            if len(net_noktalari) >= weekly_report.GRAFIK_MIN_DENEME:
                net_df = pd.DataFrame(
                    net_noktalari, columns=["Hafta", "Deneme neti"]
                ).set_index("Hafta")
                st.line_chart(net_df[["Deneme neti"]])
            else:
                st.caption(
                    "Deneme neti trendi için en az %d hafta deneme neti"
                    " gerekiyor."
                    % weekly_report.GRAFIK_MIN_DENEME
                )
            st.caption(
                "4 haftalık ortalamalar · Süre: %s · Soru: %s · Program"
                " uyumu: %s"
                % (
                    weekly_report.sure_metni(
                        weekly_report.seri_ortalamasi(trend_serisi, "dk", 4)
                        or 0
                    ),
                    _hafta_deger_metni(
                        "soru",
                        weekly_report.seri_ortalamasi(
                            trend_serisi, "soru", 4
                        ),
                    ),
                    _hafta_deger_metni(
                        "uyum",
                        weekly_report.seri_ortalamasi(
                            trend_serisi, "uyum", 4
                        ),
                    ),
                )
            )


        # ------------------------------------------------------------------
        # YORUMLAR (kural tabanlı, deterministik)
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("🗣️ Değerlendirme ve Öneriler")
        if not hafta_raporu["yorumlar"]:
            st.info(
                "Bu hafta için yorum üretilecek yeterli veri yok. Çalışma"
                " oturumu, görev, deneme veya tekrar kaydı girdikçe"
                " değerlendirme burada oluşur."
            )
        else:
            st.caption(
                "Her gözlem ölçülen bir sayıya dayanır; yapay zekâ"
                " kullanılmaz. Geçen hafta da verilen öneriler 🔁 ile"
                " işaretlenir ve listenin sonuna düşer."
            )
            for hafta_yorumu in hafta_raporu["yorumlar"]:
                yorum_metni = "**%s**\n\n%s" % (
                    hafta_yorumu["baslik"],
                    hafta_yorumu["gozlem"],
                )
                if hafta_yorumu["oneri"]:
                    yorum_metni += "\n\n👉 **Öneri:** %s" % (
                        hafta_yorumu["oneri"]
                    )
                if hafta_yorumu["tekrar"]:
                    yorum_metni = "🔁 *Geçen hafta da önerilmişti.*\n\n" + (
                        yorum_metni
                    )
                if hafta_yorumu["tur"] == "dikkat":
                    st.warning(yorum_metni)
                elif hafta_yorumu["tur"] == "olumlu":
                    st.success(yorum_metni)
                else:
                    st.info(yorum_metni)

        # ------------------------------------------------------------------
        # HAFTALIK ÖĞRENCİ DEĞERLENDİRMESİ (kalıcı notlar)
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("📝 Haftalık Öğrenci Değerlendirmesi")
        st.caption(
            "Bu notlar haftaya bağlı olarak saklanır ve yalnızca size"
            " gösterilir. Boş bırakılan alanlar kaydedilmez."
        )
        mevcut_degerlendirme = hafta_raporu["degerlendirme"] or {}
        with st.form("hafta_degerlendirme_formu"):
            degerlendirme_girdileri = {}
            for alan_kolonu, alan_sorusu in weekly_report.DEGERLENDIRME_ALANLARI:
                alan_anahtari = "hafta_deg_%s_%s" % (
                    secilen_hafta["baslangic"],
                    alan_kolonu,
                )
                if alan_anahtari not in st.session_state:
                    st.session_state[alan_anahtari] = (
                        mevcut_degerlendirme.get(alan_kolonu) or ""
                    )
                degerlendirme_girdileri[alan_kolonu] = st.text_area(
                    alan_sorusu, key=alan_anahtari, height=80
                )
            if st.form_submit_button(
                "💾 Değerlendirmeyi Kaydet", type="primary"
            ):
                try:
                    weekly_report.degerlendirme_kaydet(
                        ctx.user["id"],
                        secilen_hafta["baslangic"],
                        **degerlendirme_girdileri,
                    )
                except weekly_report.HaftalikRaporHatasi as deg_hatasi:
                    st.error(
                        "Değerlendirme kaydedilemedi: %s" % deg_hatasi
                    )
                else:
                    log_islem(
                        ctx.user["id"],
                        "WEEKLY_EVALUATION_SAVE",
                        hafta_bilgi["kisa"],
                    )
                    set_flash_message(
                        "success",
                        "Haftalık değerlendirme kaydedildi (%s)."
                        % hafta_bilgi["kisa"],
                    )
                    st.rerun()

        gecmis_degerlendirmeler = weekly_report.degerlendirmeleri_getir(
            ctx.user["id"], 8
        )
        dolu_gecmis = [k for k in gecmis_degerlendirmeler if k["dolu"]]
        if dolu_gecmis:
            with st.expander("📚 Geçmiş hafta notlarım"):
                for gecmis_kayit in dolu_gecmis:
                    st.markdown("**%s**" % gecmis_kayit["etiket"])
                    for alan_kolonu, alan_sorusu in (
                        weekly_report.DEGERLENDIRME_ALANLARI
                    ):
                        if gecmis_kayit[alan_kolonu]:
                            st.markdown(
                                "- *%s* %s"
                                % (alan_sorusu, gecmis_kayit[alan_kolonu])
                            )
