"""Sekmeler arasında paylaşılan arayüz yardımcıları ve görünüm bağlamı.

Burada **iş kuralı yoktur**: flash bildirimler, stil yükleme, oturum
zamanlayıcısı arayüzü ve görev adımı gösterimi gibi sunum yardımcıları
bulunur."""

from dataclasses import dataclass, field
from pathlib import Path
import re

import pandas as pd
import streamlit as st

from config.database import log_islem
from config.settings import CSS_YOLU
from services import programs as program_service
from services import study_sessions
from services import task_steps
from services.topic_progress import gorev_chk_durum_senkron


def set_flash_message(msg_type: str, message: str):
    st.session_state[f"flash_{msg_type}"] = message


def render_flash_messages():
    for mtype in ["success", "warning", "error", "info"]:
        key = f"flash_{mtype}"
        if key in st.session_state and st.session_state[key]:
            getattr(st, mtype)(st.session_state[key])
            st.session_state[key] = None


def sanitize_key(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(text))


CALISMA_BITIR_ANAHTARI = "calisma_bitir_oturum_id"


_CALISMA_SAYAC_CSS = """
<style>
.calisma-sayac{background:#eef2ff;border:1px solid #c7d2fe;border-radius:12px;
    padding:12px 16px;margin:6px 0 10px 0;}
.calisma-sayac .etiket{display:block;font-size:0.78rem;letter-spacing:0.06em;
    color:#4338ca;font-weight:700;}
.calisma-sayac .sure{display:block;font-size:2rem;font-weight:800;
    font-variant-numeric:tabular-nums;color:#1e1b4b;line-height:1.15;}
.calisma-sayac .konu{display:block;font-size:0.85rem;color:#475569;}
</style>
"""


def sure_bicimle(saniye):
    """Saniyeyi SS:DD:SS biçimine çevirir."""
    saniye = max(0, int(saniye or 0))
    return f"{saniye // 3600:02d}:{(saniye % 3600) // 60:02d}:{saniye % 60:02d}"


def dakika_bicimle(dakika):
    """Dakikayı '2 saat 35 dakika' biçiminde okunur hâle getirir."""
    dakika = max(0, int(dakika or 0))
    saat, kalan = divmod(dakika, 60)
    if saat and kalan:
        return f"{saat} saat {kalan} dakika"
    if saat:
        return f"{saat} saat"
    return f"{kalan} dakika"


def _calisma_hata_goster(hata):
    st.error(f"⚠️ {hata}")


def _oturum_sayac_icerigi(oturum_id):
    """Aktif oturumun geçen süresini çizer (yalnız bu parça yenilenir)."""
    oturum = study_sessions.oturum_getir(oturum_id)
    if not oturum or oturum["durum"] not in study_sessions.AKTIF_DURUMLAR:
        return
    mola_mi = oturum["durum"] == study_sessions.DURUM_MOLA
    konu = oturum.get("mikro_konu") or ""
    st.markdown(
        f'<div class="calisma-sayac">'
        f'<span class="etiket">'
        f'{"☕ MOLADASINIZ" if mola_mi else "⏱️ ÇALIŞMA SÜRÜYOR"}</span>'
        f'<span class="sure">{sure_bicimle(study_sessions.gecen_saniye(oturum))}</span>'
        f'<span class="konu">{oturum.get("ders") or ""}'
        f'{" • " + konu if konu else ""}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


if hasattr(st, "fragment"):
    _oturum_sayaci = st.fragment(run_every=1.0)(_oturum_sayac_icerigi)
else:
    _oturum_sayaci = _oturum_sayac_icerigi


def _aktif_oturum_paneli(oturum):
    """Aktif oturumun sayacı + Mola Ver / Devam Et / Bitir / İptal işlemleri."""
    oid = int(oturum["id"])
    st.markdown(_CALISMA_SAYAC_CSS, unsafe_allow_html=True)
    _oturum_sayaci(oid)

    mola_mi = oturum["durum"] == study_sessions.DURUM_MOLA
    col_a, col_b = st.columns(2)
    with col_a:
        if mola_mi:
            if st.button(
                "▶️ Çalışmaya Devam Et",
                key=f"calisma_devam_{oid}",
                type="primary",
            ):
                try:
                    study_sessions.oturum_devam_ettir(oid)
                except study_sessions.CalismaOturumHatasi as hata:
                    _calisma_hata_goster(hata)
                else:
                    st.rerun()
        else:
            if st.button("☕ Mola Ver", key=f"calisma_mola_{oid}"):
                try:
                    study_sessions.oturum_duraklat(oid)
                except study_sessions.CalismaOturumHatasi as hata:
                    _calisma_hata_goster(hata)
                else:
                    st.rerun()
    with col_b:
        if st.button(
            "⏹️ Çalışmayı Bitir",
            key=f"calisma_bitir_{oid}",
            type="secondary",
        ):
            try:
                # Süre dondurulur; kayıt ekranında öğrenci kontrol eder.
                study_sessions.oturum_duraklat(oid)
            except study_sessions.CalismaOturumHatasi as hata:
                _calisma_hata_goster(hata)
            else:
                st.session_state[CALISMA_BITIR_ANAHTARI] = oid
                st.rerun()

    with st.expander("⚙️ Bu çalışmayı iptal et"):
        st.caption(
            "Yanlışlıkla başlatıldıysa iptal edebilirsiniz. Kayıt silinmez,"
            " çalışma istatistiklerine katılmaz."
        )
        if st.button("🚫 Oturumu iptal et", key=f"calisma_iptal_{oid}"):
            try:
                study_sessions.oturum_iptal(oid)
            except study_sessions.CalismaOturumHatasi as hata:
                _calisma_hata_goster(hata)
            else:
                st.session_state.pop(CALISMA_BITIR_ANAHTARI, None)
                st.rerun()


def _oturum_bitirme_formu(oturum, planlanan_soru=0):
    """Çalışma bitirme ekranı: gerçek süre + gerçek çözülen soru sayısı."""
    oid = int(oturum["id"])
    olculen = study_sessions.gecen_saniye(oturum)
    max_dk = study_sessions.MAKS_GERCEK_SURE_DK
    olculen_dk = min(max_dk, int(round(olculen / 60.0)))
    konu = oturum.get("mikro_konu") or "-"

    st.markdown("#### 📝 Çalışma Kaydı")
    st.caption(f"{oturum.get('ders') or ''} • {konu}")
    st.markdown(f"**Zamanlayıcının ölçtüğü süre:** `{sure_bicimle(olculen)}`")
    st.caption(
        "Uygulama kapalıyken geçen süre ölçüme dâhil olmuş olabilir."
        " Gerçek odak süreniz farklıysa aşağıdan düzeltin."
    )

    with st.form(f"calisma_kayit_form_{oid}"):
        gercek_dk = st.number_input(
            "Gerçek çalışma süresi (dakika)",
            min_value=0,
            max_value=max_dk,
            value=olculen_dk,
            step=1,
            key=f"calisma_kayit_dk_{oid}",
        )
        cozulen = st.number_input(
            "Gerçek çözülen soru sayısı",
            min_value=0,
            max_value=study_sessions.MAKS_COZULEN_SORU,
            value=0,
            step=1,
            key=f"calisma_kayit_soru_{oid}",
            help="Bu çalışmada gerçekten üzerinden geçtiğiniz soru sayısı.",
        )
        if planlanan_soru:
            st.caption(
                f"Planlanan soru: **{planlanan_soru}** (plan verisi)."
                " Buraya planı değil gerçekte çözdüğünüz soru sayısını yazın."
            )
        kirilim_var = st.checkbox(
            "Soruları doğru / yanlış / boş olarak ayırdım",
            value=False,
            key=f"calisma_kayit_kirilim_{oid}",
            help="Takip etmiyorsanız işaretlemeyin; bu alanlar boş (NULL) kalır.",
        )
        dogru = yanlis = bos = None
        if kirilim_var:
            col_d, col_y, col_b = st.columns(3)
            with col_d:
                dogru = st.number_input(
                    "Doğru",
                    min_value=0,
                    max_value=study_sessions.MAKS_COZULEN_SORU,
                    value=0,
                    step=1,
                    key=f"calisma_kayit_dogru_{oid}",
                )
            with col_y:
                yanlis = st.number_input(
                    "Yanlış",
                    min_value=0,
                    max_value=study_sessions.MAKS_COZULEN_SORU,
                    value=0,
                    step=1,
                    key=f"calisma_kayit_yanlis_{oid}",
                )
            with col_b:
                bos = st.number_input(
                    "Boş",
                    min_value=0,
                    max_value=study_sessions.MAKS_COZULEN_SORU,
                    value=0,
                    step=1,
                    key=f"calisma_kayit_bos_{oid}",
                )
            st.caption(
                "Doğru + yanlış + boş toplamı çözülen soru sayısına eşit"
                " olmalıdır; eşleşmezse kayıt reddedilir."
            )
        notu = st.text_area(
            "Öğrenci notu (isteğe bağlı)",
            placeholder="Örn: Zor sorularda zorlandım, yarın buradan devam edeceğim.",
            max_chars=study_sessions.MAKS_NOT_UZUNLUK,
            key=f"calisma_kayit_not_{oid}",
        )
        col_kaydet, col_vazgec = st.columns(2)
        with col_kaydet:
            kaydet = st.form_submit_button("💾 Kaydet", type="primary")
        with col_vazgec:
            vazgec = st.form_submit_button("Vazgeç")

    if vazgec:
        st.session_state.pop(CALISMA_BITIR_ANAHTARI, None)
        st.rerun()
    if kaydet:
        try:
            kaydedilen = study_sessions.oturum_tamamla(
                oid,
                cozulen_soru=cozulen,
                gercek_sure_dk=gercek_dk,
                dogru=dogru,
                yanlis=yanlis,
                bos=bos,
                ogrenci_notu=notu,
            )
        except study_sessions.CalismaOturumHatasi as hata:
            _calisma_hata_goster(hata)
        else:
            # FAZ 5B: gerçek çalışma kaydı görevin alt adımlarını ilerletir;
            # tüm adımlar bittiyse görev otomatik tamamlanır.
            try:
                if kaydedilen and kaydedilen.get("gorev_id"):
                    task_steps.gorev_durum_guncelle(kaydedilen["gorev_id"])
            except Exception:
                pass
            st.session_state.pop(CALISMA_BITIR_ANAHTARI, None)
            set_flash_message("success", "✅ Çalışma kaydedildi.")
            st.rerun()


def _gercek_calisma_ozeti(ogrenci_id, aktif_oturum):
    """Bugün / bu hafta GERÇEK çalışma metrikleri + ders bazlı özet."""
    ozet = study_sessions.gunluk_haftalik_ozet(ogrenci_id)
    col_1, col_2, col_3 = st.columns(3)
    col_1.metric("⏱️ Bugün", dakika_bicimle(ozet["bugun_dk"]))
    col_2.metric("📅 Bu hafta", dakika_bicimle(ozet["hafta_dk"]))
    col_3.metric("✍️ Bu hafta çözülen soru", f"{ozet['hafta_soru']}")
    if aktif_oturum:
        devam_dk = int(study_sessions.gecen_saniye(aktif_oturum) // 60)
        st.caption(
            f"⏳ Devam eden çalışma: {dakika_bicimle(devam_dk)}"
            " (bitirince toplama eklenir)"
        )

    dersler = study_sessions.ders_bazli_ozet(ogrenci_id, gun_sayisi=7)
    with st.expander("📊 Derslere göre gerçek çalışma (son 7 gün)"):
        if dersler:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Ders": d["ders"],
                            "Süre": dakika_bicimle(d["dk"]),
                            "Çözülen soru": d["soru"],
                            "Oturum": d["oturum"],
                        }
                        for d in dersler
                    ]
                ),
                hide_index=True,
            )
        else:
            st.caption("Son 7 günde kaydedilmiş tamamlanmış çalışma yok.")
        gecmis = study_sessions.oturum_gecmisi(ogrenci_id, limit=5)
        if gecmis:
            st.markdown("**Son çalışmalar**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Tarih": (
                                o.get("bitis_zamani")
                                or o.get("baslangic_zamani")
                                or ""
                            )[:16],
                            "Ders": o.get("ders") or "-",
                            "Konu": o.get("mikro_konu") or "-",
                            "Süre": f"{int(o.get('gercek_sure_dk') or 0)} dk",
                            "Soru": int(o.get("cozulen_soru") or 0),
                            "Not": (o.get("ogrenci_notu") or "")[:40],
                        }
                        for o in gecmis
                    ]
                ),
                hide_index=True,
            )


def _gorev_gercek_soru_ozeti(gorev, ogrenci_id):
    """Planlanan / gerçekleşen / kalan soru özeti (görev kartının altı)."""
    g_id = int(gorev["id"])
    plan = int(gorev.get("hedef_soru") or 0)
    gercek = study_sessions.gorev_cozulen_soru(ogrenci_id, g_id)
    if plan <= 0 and not gercek["cozulen"] and not gercek["sure_dk"]:
        return
    parcalar = []
    if plan > 0:
        parcalar.append(f"Planlanan {plan} soru")
    parcalar.append(f"Gerçekleşen {gercek['cozulen']} soru")
    if plan > 0:
        parcalar.append(f"Kalan {max(0, plan - gercek['cozulen'])} soru")
    if gercek["sure_dk"]:
        parcalar.append(f"{dakika_bicimle(gercek['sure_dk'])} çalışma")
    st.caption("📊 " + " • ".join(parcalar))


def _gorev_adimlari_senkron(gorev_id, kayitli_durum):
    """Adımları okur; türetilen tamamlanma kayıtlı durumdan farklıysa eşitler.

    Görev tamamlanması alt adımlara bağlıdır: soru blokları gerçek çalışma
    oturumlarından dolduğunda görev kendiliğinden tamamlanır.
    """
    adimlar = task_steps.gorev_adimlari(gorev_id)
    if not adimlar:
        return []
    tamam = all(a["tamam"] for a in adimlar)
    if bool(kayitli_durum) != tamam:
        try:
            task_steps.gorev_durum_guncelle(gorev_id)
        except Exception:
            pass
    return adimlar


def _gorev_adim_listesi(adimlar):
    """FAZ 5B: mikro görev checklist'i.

    - Elle yapılan adımlar (video izle, not çıkar) checkbox olarak tutulur ve
      durumları veritabanına yazılır; sayfa yenilenince korunur.
    - Soru blokları salt okunurdur: tamamlanma durumları yalnızca GERÇEK
      çalışma oturumlarından türetilir. Kutuya tıklamak soru ilerlemesi
      üretmez (tek gerçek kaynak FAZ 4 oturumlarıdır).
    """
    if not adimlar:
        return
    st.markdown("**Yapılacaklar**")
    for adim in adimlar:
        if adim.get("adim_turu") == task_steps.ADIM_SORU:
            gercek = int(adim.get("gercek_soru") or 0)
            hedef = int(adim.get("hedef_soru") or 0)
            ikon = "✅" if adim.get("tamam") else "🔢"
            st.markdown(
                f"{ikon} **{adim['baslik']}** · gerçekleşen **{gercek}/{hedef}**"
            )
            if hedef > 0:
                st.progress(min(1.0, gercek / float(hedef)))
            continue
        anahtar = "adim_chk_%s" % adim["id"]
        gorev_chk_durum_senkron(anahtar, bool(adim.get("tamam")))
        secili = st.checkbox(adim["baslik"], key=anahtar)
        if secili != bool(adim.get("tamam")):
            try:
                task_steps.adim_durum_degistir(adim["id"], secili)
            except task_steps.AdimHatasi as hata:
                _calisma_hata_goster(hata)
            st.rerun()


def _calisma_basla_butonu(gorev, ogrenci_id):
    """Görev kartındaki 'Çalışmaya Başla' butonu."""
    g_id = int(gorev["id"])
    if st.button("▶️ Çalışmaya Başla", key=f"calisma_basla_{g_id}", type="primary"):
        try:
            study_sessions.oturum_baslat(
                ogrenci_id,
                gorev_id=g_id,
                ders=gorev.get("ders"),
                makro_konu=gorev.get("makro_konu"),
                mikro_konu=gorev.get("mikro_konu"),
                alt_konu=gorev.get("alt_konu"),
            )
        except study_sessions.CalismaOturumHatasi as hata:
            _calisma_hata_goster(hata)
        else:
            st.rerun()


def _oturum_paneli_veya_form(oturum, planlanan_soru=0):
    """Bitirme ekranı istenmişse formu, aksi hâlde sayacı gösterir."""
    if st.session_state.get(CALISMA_BITIR_ANAHTARI) == oturum["id"]:
        _oturum_bitirme_formu(oturum, planlanan_soru)
    else:
        _aktif_oturum_paneli(oturum)


def _onceki_programlar_bolumu(ogrenci_id):
    """Geçmiş program sürümlerinin sade özeti. Hiçbir kayıt silinmez/değişmez."""
    try:
        gecmis = program_service.gecmis_ozeti(ogrenci_id, limit=8)
    except Exception as hata:  # noqa: BLE001 - arayüz çökmemeli
        # Teknik ayrıntı öğrenciye gösterilmez; geliştirici kaydına yazılır.
        log_islem(ogrenci_id, "PROGRAM_HISTORY_ERROR", str(hata))
        st.caption(
            "Önceki programlar şu an görüntülenemiyor. Programınız ve"
            " görevleriniz etkilenmedi."
        )
        return

    kayitlar = list(gecmis.get("programlar") or [])
    eski = gecmis.get("eski_kayitlar")
    if eski:
        kayitlar.append(eski)
    if not kayitlar:
        return
    with st.expander("📚 Önceki Programlarım", expanded=False):
        st.caption(
            "Program yenilemek geçmişinizi silmez: tamamlanan görevler, yarım"
            " kalanlar ve gerçek çalışma süreleri burada saklı kalır."
        )
        for kayit in kayitlar:
            bas = kayit.get("baslangic_tarihi") or "-"
            bit = kayit.get("bitis_tarihi") or "-"
            oran = int(kayit.get("oran") or 0)
            st.markdown(
                f"**{bas} ➔ {bit}** · {kayit.get('durum') or '-'}  \n"
                f"✅ Tamamlanan: {kayit.get('tamamlanan', 0)} · "
                f"⏳ Yarım kalan: {kayit.get('yarim', 0)} · "
                f"%{oran} tamamlandı · "
                f"⏱️ {kayit.get('gercek_sure_dk', 0)} dk gerçek çalışma"
            )
            st.progress(max(0.0, min(1.0, oran / 100.0)))
        st.caption(
            "Geçmiş kayıtlar salt okunurdur; bu bölümden hiçbir görev"
            " değiştirilmez veya silinmez."
        )


@dataclass
class ViewContext:
    """Bir görünümün ihtiyaç duyduğu oturum verileri.

    Görünümler `main.py` dosyasından hiçbir global değişken okumaz; ihtiyaç
    duydukları her şey bu nesneyle taşınır.
    """

    user: dict
    mufredat: dict = field(default_factory=dict)
    alarmlar: dict = field(default_factory=dict)


def aktif_ogrenci_id():
    """Oturumdaki öğrencinin id'si (oturum yoksa None)."""
    return (st.session_state.get("active_user") or {}).get("id")


@st.cache_data(show_spinner=False)
def _css_metni(yol: str, _degisim: float) -> str:
    """CSS dosyasını okur; dosya değişmedikçe yeniden okunmaz."""
    return Path(yol).read_text(encoding="utf-8")


def load_css():
    """`assets/style.css` içeriğini sayfaya uygular.

    Yol çalışma dizinine bağımlı değildir (`config.settings.CSS_YOLU` proje
    kökünden türetilir). Dosya yoksa hata gizlenmez.
    """
    if not CSS_YOLU.exists():
        raise FileNotFoundError("CSS dosyası bulunamadı: %s" % CSS_YOLU)
    css = _css_metni(str(CSS_YOLU), CSS_YOLU.stat().st_mtime)
    st.markdown("<style>%s</style>" % css, unsafe_allow_html=True)
