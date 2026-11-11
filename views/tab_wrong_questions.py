"""Sekme 4 - Yanlış Soru Defteri."""


import streamlit as st

from config.database import log_islem
from data.subtopics import MIKRO_ALT_KONULAR
from services import wrong_questions
from views.shared import set_flash_message


def _defter_konu_ciftleri(mufredat, ders):
    """Seçilen dersin (makro, mikro) çiftleri (müfredat hiyerarşisinden)."""
    makro_dict = mufredat.get(ders) or {}
    ciftler = []
    if isinstance(makro_dict, dict):
        for makro, mikrolar in makro_dict.items():
            for mikro in mikrolar or []:
                ciftler.append((makro, mikro))
    return ciftler


def _defter_durum_etiketi(kayit):
    """Listede gösterilen durum etiketi (tekrar zamanı vurgulanır)."""
    if kayit.get("durum") not in wrong_questions.AKTIF_DURUMLAR:
        return kayit.get("durum") or "-"
    if kayit.get("gecikmis"):
        return "⏰ Gecikmiş"
    if kayit.get("bugun"):
        return "🔔 Bugün"
    return kayit.get("durum") or "-"


def _defter_kayit_metni(kayit):
    """Kaydın ayrıntı satırları (boş alanlar yazılmaz)."""
    satirlar = []
    konu = " › ".join(
        parca
        for parca in (
            kayit.get("makro_konu"),
            kayit.get("mikro_konu"),
            kayit.get("alt_konu"),
        )
        if parca
    )
    satirlar.append("**Konu:** %s" % konu)
    satirlar.append(
        "**Hata türü:** %s • **Tekrar:** %d kez"
        % (kayit.get("hata_turu") or "-", kayit.get("tekrar_sayisi") or 0)
    )
    if kayit.get("sonraki_tekrar_tarihi"):
        satirlar.append(
            "**Sonraki tekrar:** %s" % kayit["sonraki_tekrar_tarihi"]
        )
    if kayit.get("kaynak") or kayit.get("soru_no"):
        satirlar.append(
            "**Kaynak:** %s %s"
            % (kayit.get("kaynak") or "-", kayit.get("soru_no") or "")
        )
    if kayit.get("deneme_id"):
        satirlar.append("**Deneme:** #%s" % kayit["deneme_id"])
    if kayit.get("soru_metni"):
        satirlar.append("**Soru:** %s" % kayit["soru_metni"])
    if kayit.get("notlar"):
        satirlar.append("**Not:** %s" % kayit["notlar"])
    return "\n\n".join(satirlar)


def render(ctx):
    st.header("📕 Yanlış Soru Defteri")
    st.caption(
        "Denemede yanlış yaptığınız soruları tek tek kaydedin. Tekrar zamanı"
        " gelen sorular haftalık programa görev olarak eklenir; görevi"
        " tamamladığınızda tekrar sayacı otomatik ilerler."
    )

    defter_ozet = wrong_questions.yanlis_soru_ozeti(ctx.user["id"])
    olcu_a, olcu_b, olcu_c, olcu_d, olcu_e = st.columns(5)
    olcu_a.metric("Toplam Kayıt", defter_ozet["toplam"])
    olcu_b.metric("Bekleyen", defter_ozet["bekleyen"])
    olcu_c.metric("Bugün Tekrar", defter_ozet["bugun"])
    olcu_d.metric("Gecikmiş", defter_ozet["gecikmis"])
    olcu_e.metric("Öğrenildi", defter_ozet["ogrenildi"])

    with st.expander(
        "➕ Deftere Yanlış Soru Ekle", expanded=defter_ozet["toplam"] == 0
    ):
        defter_ders_listesi = list(ctx.mufredat.keys())
        if not defter_ders_listesi:
            defter_ders_listesi = ["Genel"]
        with st.form("defter_soru_ekle_formu", clear_on_submit=False):
            yeni_ders = st.selectbox(
                "Ders", defter_ders_listesi, key="defter_ekle_ders"
            )
            yeni_ciftler = _defter_konu_ciftleri(ctx.mufredat, yeni_ders)
            if yeni_ciftler:
                yeni_etiketler = [
                    "%s › %s" % (makro, mikro) for makro, mikro in yeni_ciftler
                ]
                yeni_secim = st.selectbox(
                    "Konu (makro › mikro)", yeni_etiketler, key="defter_ekle_konu"
                )
                yeni_makro, yeni_mikro = yeni_ciftler[
                    yeni_etiketler.index(yeni_secim)
                ]
            else:
                yeni_makro = st.text_input(
                    "Makro konu (opsiyonel)", key="defter_ekle_makro"
                )
                yeni_mikro = st.text_input("Mikro konu", key="defter_ekle_mikro")
            yeni_alt_listesi = MIKRO_ALT_KONULAR.get(yeni_mikro) or []
            yeni_alt = st.selectbox(
                "Alt başlık (opsiyonel)",
                ["-"] + list(yeni_alt_listesi),
                key="defter_ekle_alt",
            )
            yeni_hata = st.selectbox(
                "Hata türü", wrong_questions.HATA_TURLERI, key="defter_ekle_hata"
            )
            yeni_soru = st.text_area(
                "Soru metni / kısa açıklama", key="defter_ekle_soru", height=90
            )
            yeni_kaynak = st.text_input(
                "Kaynak (deneme adı / kitap)", key="defter_ekle_kaynak"
            )
            yeni_soru_no = st.text_input("Soru numarası", key="defter_ekle_no")
            yeni_not = st.text_area(
                "Kendi notunuz", key="defter_ekle_not", height=70
            )
            if st.form_submit_button("📕 Deftere Kaydet", type="primary"):
                try:
                    yeni_kayit = wrong_questions.yanlis_soru_ekle(
                        ctx.user["id"],
                        yeni_ders,
                        yeni_mikro,
                        makro_konu=yeni_makro,
                        alt_konu=None if yeni_alt == "-" else yeni_alt,
                        hata_turu=yeni_hata,
                        soru_metni=yeni_soru,
                        kaynak=yeni_kaynak,
                        soru_no=yeni_soru_no,
                        notlar=yeni_not,
                    )
                except wrong_questions.YanlisSoruHatasi as defter_hatasi:
                    st.error(str(defter_hatasi))
                else:
                    log_islem(
                        ctx.user["id"],
                        "WRONG_QUESTION_ADD",
                        "#%d %s › %s" % (yeni_kayit["id"], yeni_ders, yeni_mikro),
                    )
                    set_flash_message(
                        "success",
                        "📕 Soru deftere eklendi (#%d)." % yeni_kayit["id"],
                    )
                    st.rerun()

    st.markdown("---")
    st.subheader("📋 Defter Kayıtları")
    defter_kayitlar = wrong_questions.yanlis_sorulari_getir(ctx.user["id"])
    if not defter_kayitlar:
        st.info(
            "Defter henüz boş. Deneme Analizi sekmesinden veya yukarıdaki"
            " formdan yanlış soru ekleyebilirsiniz."
        )
    else:
        filtre_a, filtre_b, filtre_c = st.columns([1, 1, 2])
        defter_dersleri = ["Tümü"] + sorted({k["ders"] for k in defter_kayitlar})
        ders_filtre = filtre_a.selectbox(
            "Ders", defter_dersleri, key="defter_filtre_ders"
        )
        durum_filtre = filtre_b.selectbox(
            "Durum",
            ["Aktif (bekleyen)", "Tümü"] + list(wrong_questions.DURUMLAR),
            key="defter_filtre_durum",
        )
        arama_filtre = filtre_c.text_input(
            "Ara (ders / konu / soru / not)", key="defter_filtre_arama"
        )

        gosterilen = 0
        for kayit in defter_kayitlar:
            if ders_filtre != "Tümü" and kayit["ders"] != ders_filtre:
                continue
            if durum_filtre == "Aktif (bekleyen)":
                if not kayit["bekliyor"]:
                    continue
            elif durum_filtre != "Tümü" and kayit["durum"] != durum_filtre:
                continue
            if arama_filtre.strip():
                havuz_metni = " ".join(
                    str(kayit.get(alan) or "")
                    for alan in (
                        "ders",
                        "makro_konu",
                        "mikro_konu",
                        "alt_konu",
                        "soru_metni",
                        "notlar",
                        "kaynak",
                    )
                ).lower()
                if arama_filtre.strip().lower() not in havuz_metni:
                    continue
            gosterilen += 1
            baslik = "#%d • %s › %s • %s" % (
                kayit["id"],
                kayit["ders"],
                kayit["mikro_konu"],
                _defter_durum_etiketi(kayit),
            )
            with st.expander(baslik):
                st.markdown(_defter_kayit_metni(kayit))
                but_a, but_b, but_c = st.columns(3)
                if kayit["durum"] in wrong_questions.AKTIF_DURUMLAR:
                    if but_a.button(
                        "✅ Çözdüm (öğrenildi)",
                        key="defter_coz_%d" % kayit["id"],
                    ):
                        wrong_questions.tekrar_sonucu_kaydet(
                            kayit["id"], True, ogrenci_id=ctx.user["id"]
                        )
                        log_islem(
                            ctx.user["id"],
                            "WRONG_QUESTION_SOLVED",
                            "#%d" % kayit["id"],
                        )
                        set_flash_message(
                            "success",
                            "✅ Soru öğrenildi olarak işaretlendi (#%d)."
                            % kayit["id"],
                        )
                        st.rerun()
                    if but_b.button(
                        "🔁 Yine yapamadım",
                        key="defter_yapamadi_%d" % kayit["id"],
                    ):
                        sonuc = wrong_questions.tekrar_sonucu_kaydet(
                            kayit["id"], False, ogrenci_id=ctx.user["id"]
                        )
                        set_flash_message(
                            "info",
                            "🔁 Soru yeniden havuza döndü; sonraki tekrar %s."
                            % (sonuc.get("sonraki_tekrar_tarihi") or "-"),
                        )
                        st.rerun()
                elif kayit["durum"] == wrong_questions.DURUM_OGRENILDI:
                    if but_a.button(
                        "↩️ Yeniden aç", key="defter_ac_%d" % kayit["id"]
                    ):
                        wrong_questions.yeniden_ac(
                            kayit["id"], ogrenci_id=ctx.user["id"]
                        )
                        set_flash_message(
                            "info", "Soru yeniden açıldı (#%d)." % kayit["id"]
                        )
                        st.rerun()
                else:
                    if but_a.button(
                        "📤 Arşivden çıkar", key="defter_cikar_%d" % kayit["id"]
                    ):
                        wrong_questions.arsivden_cikar(
                            kayit["id"], ogrenci_id=ctx.user["id"]
                        )
                        set_flash_message(
                            "info", "Soru arşivden çıkarıldı (#%d)." % kayit["id"]
                        )
                        st.rerun()
                if kayit["durum"] != wrong_questions.DURUM_ARSIV:
                    if but_c.button(
                        "🗄️ Arşivle", key="defter_arsiv_%d" % kayit["id"]
                    ):
                        wrong_questions.arsivle(
                            kayit["id"], ogrenci_id=ctx.user["id"]
                        )
                        log_islem(
                            ctx.user["id"],
                            "WRONG_QUESTION_ARCHIVE",
                            "#%d" % kayit["id"],
                        )
                        set_flash_message(
                            "info", "Soru arşivlendi (#%d)." % kayit["id"]
                        )
                        st.rerun()
                if kayit["durum"] != wrong_questions.DURUM_ARSIV:
                    with st.form("defter_not_formu_%d" % kayit["id"]):
                        guncel_not = st.text_area(
                            "Not",
                            value=kayit.get("notlar") or "",
                            key="defter_not_%d" % kayit["id"],
                        )
                        if st.form_submit_button("💾 Notu Kaydet"):
                            try:
                                wrong_questions.yanlis_soru_guncelle(
                                    kayit["id"],
                                    ogrenci_id=ctx.user["id"],
                                    notlar=guncel_not,
                                )
                            except wrong_questions.YanlisSoruHatasi as not_hatasi:
                                st.error(str(not_hatasi))
                            else:
                                set_flash_message(
                                    "success",
                                    "Not güncellendi (#%d)." % kayit["id"],
                                )
                                st.rerun()

        if gosterilen == 0:
            st.info("Filtrelere uyan defter kaydı bulunamadı.")
