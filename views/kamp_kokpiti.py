"""v2.3 "KARAKOÇ YKS KAMP" uzay kokpiti (Streamlit görünümü).

İş mantığı `services/kamp_motoru.py` içindedir; bu modül yalnızca gösterim ve
oturum durumu yönetir. Kokpit; soğuk uzay arka planı, 5'li tema seçici, tek
görev kartı (makro ünite ilerleme çubuğu + canlı kronometre + +/- sayaçları)
ve yorgunluk merdivenini sunar.
"""
import time

import streamlit as st

from data import curriculum_meta as cm
from services import kamp_motoru
from views.shared import set_flash_message

PROTOKOL_METNI = (
    "Bildirimler kapalı. Eğlence, sosyal medya ve oyun yasak. Yalnızca ders ile "
    "uyku, yemek, hijyen ve zorunlu ihtiyaçlar serbest. Kurallar bozulursa kamp "
    "oturumu geçersiz sayılır."
)

_KAMP_DILIM_HEDEF = kamp_motoru.KAMP_MAKS_DILIM_SORU * 2  # mikro başına ~30 soru


def _tema_gradyan(tema):
    """Tema için (merkez, orta, kenar) renk üçlüsü (v2.4)."""
    gradyan = getattr(kamp_motoru, "TEMA_GRADYANLARI", {}).get(tema)
    if gradyan:
        return gradyan
    renk = kamp_motoru.TEMA_PALETLERI.get(tema, "#0A182E")
    return (renk, "#050B18", "#020306")


def _css(tema):
    """Kamp uzay kokpiti CSS'ini döndürür (güvenli; % biçimlendirme YOK).

    v2.4: CSS metni `.replace()` yer tutucularıyla doldurulur; böylece CSS
    içindeki `100%`, `50%` gibi yüzde değerleri Python `%` operatörüyle
    çakışmaz (eski `ValueError` çökmesi giderildi). Ayrıca saf CSS ile
    parıldayan mikro yıldız katmanı ve yavaş kozmik gradyan kayması eklenir.
    """
    merkez, orta, kenar = _tema_gradyan(tema)
    sablon = """
        <style>
        [data-testid="stSidebar"] {display:none !important;}
        .stApp {
            background: radial-gradient(circle at 50% 38%,
                __MERKEZ_RENK__ 0%, __ORTA_RENK__ 46%, __KENAR_RENK__ 100%) !important;
            background-size: 200% 200% !important;
            animation: kamp_kozmik_kayma 19s ease-in-out infinite !important;
            color: #E2E8F0;
        }
        /* v2.4: zarif, göz yormayan parıldayan mikro yıldız katmanı (saf CSS). */
        .stApp::before {
            content: "";
            position: fixed;
            top: 0; right: 0; bottom: 0; left: 0;
            pointer-events: none;
            z-index: 0;
            background-image:
                radial-gradient(1px 1px at 20% 30%, rgba(255,255,255,0.75), transparent 55%),
                radial-gradient(1px 1px at 72% 64%, rgba(255,255,255,0.55), transparent 55%),
                radial-gradient(1px 1px at 38% 82%, rgba(203,213,225,0.60), transparent 55%),
                radial-gradient(1.5px 1.5px at 88% 18%, rgba(255,255,255,0.50), transparent 55%),
                radial-gradient(1px 1px at 12% 68%, rgba(203,213,225,0.45), transparent 55%),
                radial-gradient(1px 1px at 56% 12%, rgba(255,255,255,0.60), transparent 55%);
            background-repeat: repeat;
            background-size: 260px 260px, 340px 340px, 300px 300px,
                             420px 420px, 380px 380px, 460px 460px;
            animation: kamp_yildiz_twinkle 5.5s ease-in-out infinite;
        }
        @keyframes kamp_kozmik_kayma {
            0% { background-position: 0% 46%; }
            50% { background-position: 100% 54%; }
            100% { background-position: 0% 46%; }
        }
        @keyframes kamp_yildiz_twinkle {
            0%, 100% { opacity: 0.32; }
            50% { opacity: 0.85; }
        }
        .kamp-baslik {display:flex; align-items:center; gap:16px; margin:4px 0 16px 0;}
        .kamp-baslik .marka {font-size:2.0rem; letter-spacing:0.38em;
            color:#E2E8F0; font-weight:600;}
        .kamp-baslik .rozet {font-size:0.8rem; letter-spacing:0.30em;
            color:#94A3B8; border:1px solid #475569; border-radius:8px;
            padding:6px 12px;}
        .kamp-kart {background: rgba(10,12,16,0.86); border:1px solid #b8975a;
            border-radius:16px; padding:20px 24px; margin-top:10px;
            box-shadow:0 0 22px rgba(0,0,0,0.6);}
        .kamp-sayac {font-size:2.6rem; font-variant-numeric:tabular-nums;
            color:#E2E8F0; line-height:1.1;}
        .kamp-mikro {font-size:0.95rem; color:#CBD5E1;}
        .kamp-dilim {color:#94A3B8; font-size:0.8rem; letter-spacing:0.06em;}
        </style>
        """
    return (
        sablon.replace("__MERKEZ_RENK__", merkez)
        .replace("__ORTA_RENK__", orta)
        .replace("__KENAR_RENK__", kenar)
    )


def _sayac(kayit_id):
    kayit = kamp_motoru._kayit_getir(kayit_id) if kayit_id else None
    if not kayit or not kayit.get("baslangic_ts"):
        return
    gecen = int(max(0, time.time() - float(kayit["baslangic_ts"])))
    st.markdown(
        f'<div class="kamp-sayac">{gecen // 60:02d}:{gecen % 60:02d}</div>',
        unsafe_allow_html=True,
    )


if hasattr(st, "fragment"):
    _sayac_akisi = st.fragment(run_every=1.0)(_sayac)
else:  # eski Streamlit: tek seferlik çizim
    _sayac_akisi = _sayac


def _veri_yukle(ctx):
    """(bilinen, biten) kümelerini güvenli biçimde yükler."""
    bilinen, biten = set(), set()
    try:
        from services.program_motoru import program_durumu_yukle

        durum = program_durumu_yukle(ctx.user["id"])
        bilinen = set(durum.get("bilinen_mikro") or ())
    except Exception:  # noqa: BLE001
        bilinen = set()
    try:
        from services.topic_progress import biten_konulari_yukle

        biten = set(biten_konulari_yukle(ctx.user["id"], ctx.mufredat))
    except Exception:  # noqa: BLE001
        biten = set()
    return bilinen, biten


def _ilerle():
    """Sonraki dilime, dilim bitince sonraki mikro konuya geç."""
    dilim_idx = int(st.session_state.get("kamp_dilim_idx", 0))
    toplam = int(st.session_state.get("kamp_toplam_dilim", 1))
    if dilim_idx + 1 < toplam:
        st.session_state["kamp_dilim_idx"] = dilim_idx + 1
    else:
        st.session_state["kamp_dilim_idx"] = 0
        st.session_state["kamp_mikro_idx"] = (
            int(st.session_state.get("kamp_mikro_idx", 0)) + 1
        )


def _protokol_karti():
    if st.session_state.get("kamp_protokol_onay"):
        return True
    st.markdown("### KAMP PROTOKOLÜ")
    st.markdown(
        f'<div class="kamp-kart kamp-mikro">{PROTOKOL_METNI}</div>',
        unsafe_allow_html=True,
    )
    if st.button("Anladım, Kampı Başlat", type="primary", key="kamp_protokol_btn"):
        st.session_state["kamp_protokol_onay"] = True
        st.rerun()
    return False


def _tema_secici():
    if "kamp_tema" not in st.session_state:
        st.session_state["kamp_tema"] = kamp_motoru.VARSAYILAN_TEMA
    temalar = list(kamp_motoru.TEMA_PALETLERI.keys())
    secili = st.selectbox(
        "Tema", temalar,
        index=temalar.index(st.session_state["kamp_tema"]),
        key="kamp_tema_sec",
    )
    if secili != st.session_state["kamp_tema"]:
        st.session_state["kamp_tema"] = secili
        # Kullanıcı talimatı: tema değişiminde arka plan ANINDA güncellensin.
        st.rerun()
    return st.session_state["kamp_tema"]


def render(ctx):
    # --- Oturum ---------------------------------------------------------
    if not st.session_state.get("kamp_oturum_id"):
        oturum = kamp_motoru.oturum_baslat(
            ctx.user["id"], tema=st.session_state.get("kamp_tema")
        )
        if oturum:
            st.session_state["kamp_oturum_id"] = oturum["id"]
    oturum_id = st.session_state.get("kamp_oturum_id")

    tema = st.session_state.get("kamp_tema") or kamp_motoru.VARSAYILAN_TEMA
    st.markdown(_css(tema), unsafe_allow_html=True)

    # --- Başlık + tema + çıkış -----------------------------------------
    ust1, ust2 = st.columns([5, 1])
    with ust1:
        st.markdown(
            '<div class="kamp-baslik"><span class="marka">KARAKOÇ</span>'
            '<span class="rozet">YKS KAMP</span></div>',
            unsafe_allow_html=True,
        )
    with ust2:
        tema = _tema_secici()
        if st.button("Çıkış", key="kamp_cikis"):
            st.session_state["kamp_aktif"] = False
            st.rerun()

    if not _protokol_karti():
        return

    # --- Branş seçici ---------------------------------------------------
    sinif = ctx.user.get("sinif_seviyesi")
    alan = ctx.user.get("hedef_alan")
    try:
        havuz = cm.havuz_suz(ctx.mufredat or {}, sinif, alan)
    except Exception:  # noqa: BLE001
        havuz = ctx.mufredat or {}
    dersler = [d for d, v in havuz.items() if isinstance(v, dict)]
    if not dersler:
        st.info("Kamp için uygun ders bulunamadı.")
        return
    if st.session_state.get("kamp_ders") not in dersler:
        st.session_state["kamp_ders"] = dersler[0]
    secilen_ders = st.selectbox(
        "Branş", dersler,
        index=dersler.index(st.session_state["kamp_ders"]),
        key="kamp_ders_sec",
    )
    if secilen_ders != st.session_state["kamp_ders"]:
        st.session_state["kamp_ders"] = secilen_ders
        st.session_state["kamp_mikro_idx"] = 0
        st.session_state["kamp_dilim_idx"] = 0
        st.session_state["kamp_kayit_id"] = None
        st.session_state["kamp_kayit_anahtar"] = None
        # Kullanıcı talimatı: branş değişiminde kart ANINDA güncellensin.
        st.rerun()

    bilinen, biten = _veri_yukle(ctx)
    try:
        kilit = kamp_motoru.aktif_makro_unite_hesapla(
            secilen_ders, ctx.mufredat or {}, bilinen, biten, sinif, alan
        )
    except Exception:  # noqa: BLE001
        kilit = None
    if not kilit:
        st.success("Bu dersin tüm makro üniteleri tamamlanmış. Başka bir branş seç.")
        return

    mikrolar = kilit.get("mikrolar") or []
    if not mikrolar:
        st.success("Bu ünite tamamlandı.")
        return
    mikro_idx = min(int(st.session_state.get("kamp_mikro_idx", 0)), len(mikrolar) - 1)
    st.session_state["kamp_mikro_idx"] = mikro_idx
    aktif_mikro = mikrolar[mikro_idx]

    # Makro ünite ilerleme yüzdesi
    try:
        from services.topic_progress import makro_unite_ilerleme_durumu

        ilerleme = makro_unite_ilerleme_durumu(
            ctx.user["id"], secilen_ders, kilit["makro_unite"], ctx.mufredat
        )
    except Exception:  # noqa: BLE001
        ilerleme = 0
    st.markdown(
        f'<div class="kamp-dilim">ÜNİTE İLERLEMESİ: %{int(ilerleme)} — {kilit["makro_unite"]}</div>',
        unsafe_allow_html=True,
    )
    st.progress(min(1.0, max(0.0, ilerleme / 100.0)))

    # --- Atomik dilim ---------------------------------------------------
    dilimler = kamp_motoru.mikro_dilimle(_KAMP_DILIM_HEDEF)
    dilim_idx = min(int(st.session_state.get("kamp_dilim_idx", 0)), len(dilimler) - 1)
    st.session_state["kamp_dilim_idx"] = dilim_idx
    st.session_state["kamp_toplam_dilim"] = len(dilimler)
    dilim = dilimler[dilim_idx]

    # --- Analiz kartı (başarı < %75) — sonraki konuya GEÇİLMEZ ----------
    analiz = st.session_state.get("kamp_analiz")
    if analiz:
        st.markdown("### 🔎 Yanlış / Boş Analizi ve Çözüm Kontrolü (5 dk)")
        _basari = float(analiz.get("basari_orani") or 0)
        st.markdown(
            f'<div class="kamp-kart">Başarı: <b>%{_basari:.1f}</b> (eşik %75). Önce '
            f'yanlış ve boş sorularını incele, çözümünü kontrol et; sonra devam et.</div>',
            unsafe_allow_html=True,
        )
        if st.button("Analizi Tamamla ve Devam Et", type="primary",
                     key="kamp_analiz_devam"):
            st.session_state.pop("kamp_analiz", None)
            _ilerle()
            st.rerun()
        return

    # --- Aktif görev kartı ---------------------------------------------
    anahtar = (secilen_ders, aktif_mikro, dilim["dilim_no"])
    if st.session_state.get("kamp_kayit_anahtar") != anahtar:
        kayit = kamp_motoru.mikro_gorev_baslat(
            oturum_id, ctx.user["id"], secilen_ders, kilit["makro_unite"],
            aktif_mikro, aktif_mikro, dilim["hedef_soru"],
            dilim_no=dilim["dilim_no"], toplam_dilim=dilim["toplam_dilim"],
        )
        st.session_state["kamp_kayit_id"] = kayit["id"] if kayit else None
        st.session_state["kamp_kayit_anahtar"] = anahtar
        st.session_state["kamp_yanlis"] = 0
        st.session_state["kamp_bos"] = 0

    kayit_id = st.session_state.get("kamp_kayit_id")
    st.markdown(
        f'<div class="kamp-kart"><div class="kamp-dilim">BÖLÜM '
        f'{dilim["dilim_no"]}/{dilim["toplam_dilim"]}</div>'
        f'<div class="kamp-mikro"><b>{kilit["makro_unite"]}</b> ➔ {aktif_mikro}</div></div>',
        unsafe_allow_html=True,
    )
    if kayit_id:
        _sayac_akisi(kayit_id)

    hedef = int(dilim["hedef_soru"])
    c1, c2 = st.columns(2)
    with c1:
        yanlis = st.number_input(
            "Yanlış", min_value=0, max_value=hedef,
            value=int(st.session_state.get("kamp_yanlis", 0)), step=1,
            key="kamp_yanlis_in",
        )
    with c2:
        bos = st.number_input(
            "Boş", min_value=0, max_value=hedef,
            value=int(st.session_state.get("kamp_bos", 0)), step=1,
            key="kamp_bos_in",
        )

    if st.button("Tamamla ve Sonrakine Geç", type="primary", key="kamp_tamamla"):
        try:
            sonuc = kamp_motoru.mikro_gorev_tamamla(kayit_id, yanlis, bos)
        except Exception as hata:  # noqa: BLE001
            set_flash_message("error", f"Kamp kaydı tamamlanamadı: {hata}")
            st.rerun()
        st.session_state["kamp_kayit_id"] = None
        st.session_state["kamp_kayit_anahtar"] = None
        st.session_state["kamp_yanlis"] = 0
        st.session_state["kamp_bos"] = 0
        if sonuc.get("analiz_gerekli"):
            st.session_state["kamp_analiz"] = sonuc
        else:
            _ilerle()
        # Kullanıcı talimatı: makro ünite barı ve arka plan ANINDA güncellensin.
        st.rerun()

    # --- Yorgunluk merdiveni -------------------------------------------
    with st.expander("😴 Yoruldum"):
        oneri = kamp_motoru.yorgunluk_onerisi(secilen_ders)
        st.markdown("**Öneri:** " + oneri["mesaj"])
        for kademe in kamp_motoru.yorgunluk_kademeleri():
            st.markdown(
                f'- **{kademe["kademe"]}. {kademe["baslik"]}** — {kademe["mesaj"]}'
            )
        if oneri.get("tur") == "sozel" and oneri.get("oneri") in dersler:
            if st.button(f'Sözel derse geç ({oneri["oneri"]})', key="kamp_sozel_gec"):
                st.session_state["kamp_ders"] = oneri["oneri"]
                st.session_state["kamp_mikro_idx"] = 0
                st.session_state["kamp_dilim_idx"] = 0
                st.session_state["kamp_kayit_id"] = None
                st.session_state["kamp_kayit_anahtar"] = None
                st.rerun()
        if st.button("Kampı Kesinlikle Bitir", key="kamp_bitir"):
            ozet = kamp_motoru.oturum_bitir(oturum_id, kamp_motoru.DURUM_BOZUK)
            st.session_state["kamp_ozet"] = ozet
            st.session_state["kamp_aktif"] = False
            st.session_state["kamp_oturum_id"] = None
            st.rerun()

    # --- Çıkışta özet fişi (varsa) -------------------------------------
    ozet = st.session_state.get("kamp_ozet")
    if ozet:
        st.markdown("### Kamp Özeti Fişi")
        _ts = int(ozet.get("toplam_soru") or 0)
        _td = int(ozet.get("toplam_dogru") or 0)
        _ty = int(ozet.get("toplam_yanlis") or 0)
        _tb = int(ozet.get("toplam_bos") or 0)
        st.markdown(
            f'<div class="kamp-kart">Toplam soru: <b>{_ts}</b> • Doğru: <b>{_td}</b> • '
            f'Yanlış: <b>{_ty}</b> • Boş: <b>{_tb}</b></div>',
            unsafe_allow_html=True,
        )

