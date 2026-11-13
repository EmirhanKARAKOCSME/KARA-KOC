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
        .kamp-sayac {font-size:clamp(2.8rem, 9vw, 5.4rem);
            font-variant-numeric:tabular-nums; color:#F1F5F9; line-height:1.0;
            text-align:center; font-weight:700; letter-spacing:0.05em;
            text-shadow:0 0 30px rgba(148,163,184,0.35);}
        .kamp-yatay-ipucu {display:none;}
        /* Portre mobilde küçük ve zarif yönlendirme; yatay/masaüstünde gizli. */
        @media (orientation: portrait) and (max-width: 768px) {
            .kamp-yatay-ipucu {display:block; text-align:center; color:#94A3B8;
                font-size:0.76rem; letter-spacing:0.04em; margin:2px 0 8px 0;}
        }
        /* Yatay telefon: dikey boşluğu azalt, metni küçült, butonu koru. */
        @media (orientation: landscape) and (max-height: 520px) {
            .block-container {padding-top:0.5rem !important;
                padding-bottom:0.5rem !important;}
            .kamp-baslik {margin:0 0 6px 0; gap:10px;}
            .kamp-baslik .marka {font-size:1.3rem; letter-spacing:0.22em;}
            .kamp-baslik .rozet {font-size:0.64rem; padding:3px 8px;}
            .kamp-kart {padding:10px 14px; margin-top:4px; border-radius:12px;}
            .kamp-merkez {padding:6px 4px 4px 4px;}
            .kamp-sayac {font-size:clamp(2.2rem, 6.5vw, 3.4rem);}
            .kamp-sayac-etiket {font-size:0.66rem; margin-bottom:2px;}
            .kamp-adim {font-size:0.8rem; margin:2px 0;}
            .kamp-dilim {font-size:0.72rem;}
            .stButton > button, .stDownloadButton > button {min-height:42px;}
            .stTabs [data-baseweb="tab-list"] {flex-wrap:nowrap;
                overflow-x:auto; -webkit-overflow-scrolling:touch;}
            h4 {font-size:0.95rem; margin:2px 0 4px 0;}
        }
        .kamp-sayac-etiket {text-align:center; color:#94A3B8; font-size:0.78rem;
            letter-spacing:0.26em; margin-bottom:8px;}
        .kamp-merkez {display:flex; flex-direction:column; align-items:center;
            justify-content:center; padding:26px 8px 14px 8px;}
        .kamp-mikro {font-size:0.98rem; color:#CBD5E1;}
        .kamp-dilim {color:#94A3B8; font-size:0.8rem; letter-spacing:0.06em;}
        .kamp-gorev-tur {display:inline-block; margin-top:8px; padding:3px 12px;
            border-radius:999px; border:1px solid #b8975a; color:#E7C98B;
            font-size:0.74rem; letter-spacing:0.09em; text-transform:uppercase;}
        .kamp-adim {color:#CBD5E1; font-size:0.92rem; margin:5px 0;
            padding-left:14px; border-left:2px solid rgba(184,151,90,0.55);}
        /* Tema ile bütünleşik giriş alanları (beyaz kutular azaltıldı). */
        .stSelectbox div[data-baseweb="select"] > div,
        .stNumberInput input {
            background-color:#0E1520 !important; color:#E2E8F0 !important;
            border-color:#334155 !important;
        }
        .stSelectbox label, .stNumberInput label {color:#CBD5E1 !important;}
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
        '<div class="kamp-merkez">'
        '<div class="kamp-sayac-etiket">ÇALIŞMA SÜRESİ</div>'
        f'<div class="kamp-sayac">{gecen // 60:02d}:{gecen % 60:02d}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _temizle_gorev_durumu():
    """Aktif görev oturum durumunu sıfırlar (yeni kart için)."""
    st.session_state["kamp_kayit_id"] = None
    st.session_state["kamp_kayit_anahtar"] = None
    st.session_state["kamp_sonuc_bekliyor"] = False
    st.session_state["kamp_yanlis"] = 0
    st.session_state["kamp_bos"] = 0


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

    # --- Kamp havuzu / branş listesi (ayarlar panelinde kullanılır) -----
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

    # --- Üst bölüm: sade başlık + sağ üstte AYARLAR paneli -------------
    # Tema, branş, çıkış, kampı bitir ve "Yoruldum" artık ana ekranı
    # kaplamaz; yalnızca ayarlar panelinden erişilir.
    ust1, ust2 = st.columns([6, 1])
    with ust1:
        st.markdown(
            '<div class="kamp-baslik"><span class="marka">KARA KOÇ</span>'
            '<span class="rozet">YKS KAMP</span></div>',
            unsafe_allow_html=True,
        )
    with ust2:
        with st.popover("⚙️", help="Kamp ayarları"):
            _tema_secici()
            _sec = st.selectbox(
                "Branş", dersler,
                index=dersler.index(st.session_state["kamp_ders"]),
                key="kamp_ders_sec",
            )
            if _sec != st.session_state["kamp_ders"]:
                st.session_state["kamp_ders"] = _sec
                st.session_state["kamp_mikro_idx"] = 0
                st.session_state["kamp_dilim_idx"] = 0
                _temizle_gorev_durumu()
                st.rerun()
            st.markdown("---")
            if st.button("😴 Yoruldum", key="kamp_yoruldum_panel"):
                st.session_state["kamp_yoruldum_goster"] = True
                st.rerun()
            if st.button("Çıkış", key="kamp_cikis"):
                st.session_state["kamp_aktif"] = False
                st.rerun()
            if st.button("Kampı Bitir", key="kamp_bitir_panel"):
                if oturum_id:
                    st.session_state["kamp_ozet"] = kamp_motoru.oturum_bitir(
                        oturum_id, kamp_motoru.DURUM_BOZUK
                    )
                st.session_state["kamp_aktif"] = False
                st.session_state["kamp_oturum_id"] = None
                st.rerun()

    secilen_ders = st.session_state["kamp_ders"]

    # Yatay kullanım önerisi (yalnızca portre mobilde görünür; yön zorlanmaz).
    st.markdown(
        '<div class="kamp-yatay-ipucu">📱 En iyi deneyim için telefonunu '
        "yatay kullan.</div>",
        unsafe_allow_html=True,
    )

    if not _protokol_karti():
        return

    # --- 24 saatlik telafi (varsa) — yeni konudan ÖNCE ------------------
    # Aralıklı tekrar mantığı bozulmaz: telafi bir TEKRAR görevidir, soru
    # sonucu istenmez; yalnızca özet not okuma adımı sunulur.
    if not st.session_state.get("kamp_telafi_tamam"):
        try:
            _telafiler = kamp_motoru.son_24s_telafi(ctx.user["id"], secilen_ders)
        except Exception:  # noqa: BLE001
            _telafiler = []
        if _telafiler:
            _t = _telafiler[0]
            st.markdown(
                f'<div class="kamp-kart"><div class="kamp-dilim">TELAFİ</div>'
                f'<div class="kamp-mikro">{_t.get("ders") or secilen_ders} ➔ '
                f'{_t.get("mikro_konu") or ""}</div>'
                '<div class="kamp-gorev-tur">TEKRAR GÖREVİ</div></div>',
                unsafe_allow_html=True,
            )
            st.caption(
                "Bu tekrar görevinde soru sonucu istenmez; özet notlarını "
                "gözden geçir ve devam et."
            )
            if st.button(
                "Tekrarı Tamamla", type="primary", key="kamp_telafi_tamamla"
            ):
                _plan_t = kamp_motoru.tekrar_gorev_plani(
                    _t.get("ders") or secilen_ders,
                    _t.get("makro_unite") or "",
                    _t.get("mikro_konu") or "",
                )
                _kayit_t = kamp_motoru.mikro_gorev_baslat(
                    oturum_id, ctx.user["id"], _t.get("ders") or secilen_ders,
                    _t.get("makro_unite") or "", _t.get("mikro_konu") or "",
                    _t.get("mikro_konu") or "", 1,
                    pedagoji_turu=_plan_t["pedagoji_turu"],
                    gorev_turu=_plan_t["gorev_turu"],
                    adimlar=_plan_t["adimlar"], soru_gerekli=0,
                )
                if _kayit_t:
                    kamp_motoru.mikro_gorev_tamamla(_kayit_t["id"])
                st.session_state["kamp_telafi_tamam"] = True
                st.rerun()
            return

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

    # --- Pedagojik görev planı (tür + çalışma adımları) ----------------
    plan = kamp_motoru.gorev_plani_uret(
        secilen_ders, kilit["makro_unite"], aktif_mikro, dilim["hedef_soru"]
    )
    anahtar = (secilen_ders, aktif_mikro, dilim["dilim_no"])
    if st.session_state.get("kamp_kayit_anahtar") != anahtar:
        kayit = kamp_motoru.mikro_gorev_baslat(
            oturum_id, ctx.user["id"], secilen_ders, kilit["makro_unite"],
            aktif_mikro, aktif_mikro, dilim["hedef_soru"],
            dilim_no=dilim["dilim_no"], toplam_dilim=dilim["toplam_dilim"],
            pedagoji_turu=plan["pedagoji_turu"], gorev_turu=plan["gorev_turu"],
            adimlar=plan["adimlar"], soru_gerekli=plan["soru_gerekli"],
        )
        st.session_state["kamp_kayit_id"] = kayit["id"] if kayit else None
        st.session_state["kamp_kayit_anahtar"] = anahtar
        st.session_state["kamp_sonuc_bekliyor"] = False

    kayit_id = st.session_state.get("kamp_kayit_id")

    # --- Görev kartı (ders / makro / mikro / tür / bölüm / hedef) ------
    gorev_etiketi = (
        "KONU ÖĞRENME + PEKİŞTİRME"
        if plan["pedagoji_turu"] != "Ezber"
        else "KONU ÖĞRENME + EZBER"
    )
    soru_satiri = (
        f'<div class="kamp-dilim">{int(dilim["hedef_soru"])} SORU</div>'
        if plan["soru_gerekli"] else ""
    )
    st.markdown(
        '<div class="kamp-dilim" style="margin-top:8px;">BÖLÜM '
        f'{dilim["dilim_no"]} / {dilim["toplam_dilim"]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="kamp-kart"><div class="kamp-dilim">{secilen_ders.upper()}</div>'
        f'<div class="kamp-mikro"><b>{kilit["makro_unite"]}</b> ➔ {aktif_mikro}</div>'
        f'<div class="kamp-gorev-tur">GÖREV: {gorev_etiketi}</div>'
        f'{soru_satiri}</div>',
        unsafe_allow_html=True,
    )

    # --- Bu görevde ne yapılacak? (çalışma adımları) -------------------
    st.markdown("#### 📋 Bu görevde ne yapacaksın?")
    for _adim in plan["adimlar"]:
        _hedef = int(_adim.get("hedef_soru") or 0)
        _ek = (" — %d soru" % _hedef) if _hedef else ""
        st.markdown(
            f'<div class="kamp-adim">{_adim.get("baslik", "")}{_ek}</div>',
            unsafe_allow_html=True,
        )

    # --- Merkezî büyük kronometre --------------------------------------
    if kayit_id:
        _sayac_akisi(kayit_id)

    # --- Tamamla / sonuç akışı -----------------------------------------
    hedef = int(dilim["hedef_soru"])
    soru_gerekli = bool(plan["soru_gerekli"])

    if not soru_gerekli:
        # Soru gerektirmeyen görev: sonuç formu AÇILMAZ.
        if st.button("Tamamla ve Sonrakine Geç", type="primary", key="kamp_tamamla"):
            try:
                kamp_motoru.mikro_gorev_tamamla(kayit_id)
            except Exception as hata:  # noqa: BLE001
                set_flash_message("error", f"Kamp kaydı tamamlanamadı: {hata}")
                st.rerun()
            _temizle_gorev_durumu()
            _ilerle()
            st.rerun()
    elif not st.session_state.get("kamp_sonuc_bekliyor"):
        # Aktif çalışma ekranında yanlış/boş alanları GÖSTERİLMEZ.
        if st.button("Tamamla ve Sonrakine Geç", type="primary", key="kamp_tamamla"):
            st.session_state["kamp_sonuc_bekliyor"] = True
            st.rerun()
    else:
        st.markdown("### ✅ Sonuç Girişi")
        c1, c2 = st.columns(2)
        with c1:
            yanlis = st.number_input(
                "Yanlış", min_value=0, max_value=hedef, value=0, step=1,
                key="kamp_yanlis_in",
            )
        with c2:
            bos = st.number_input(
                "Boş", min_value=0, max_value=hedef, value=0, step=1,
                key="kamp_bos_in",
            )
        if int(yanlis) + int(bos) > hedef:
            st.error(
                "Yanlış + boş toplamı hedef soru sayısını (%d) aşamaz." % hedef
            )
        else:
            dogru = max(0, hedef - int(yanlis) - int(bos))
            oran = (dogru / float(hedef) * 100.0) if hedef else 0.0
            st.caption(
                "Doğru: %d · Başarı: %%%.1f · Eşik: %%75" % (dogru, oran)
            )
            if st.button(
                "Sonucu Kaydet ve Devam Et", type="primary", key="kamp_sonuc_kaydet"
            ):
                try:
                    sonuc = kamp_motoru.mikro_gorev_tamamla(
                        kayit_id, int(yanlis), int(bos)
                    )
                except Exception as hata:  # noqa: BLE001
                    set_flash_message("error", f"Kamp kaydı tamamlanamadı: {hata}")
                    st.rerun()
                _temizle_gorev_durumu()
                if sonuc.get("analiz_gerekli"):
                    st.session_state["kamp_analiz"] = sonuc
                else:
                    _ilerle()
                st.rerun()

    # --- Yorgunluk merdiveni (yalnızca ayarlar panelinden açılır) ------
    if st.session_state.get("kamp_yoruldum_goster"):
        with st.expander("😴 Yoruldum — öneri", expanded=True):
            oneri = kamp_motoru.yorgunluk_onerisi(secilen_ders)
            st.markdown("**Öneri:** " + oneri["mesaj"])
            for kademe in kamp_motoru.yorgunluk_kademeleri():
                st.markdown(
                    f'- **{kademe["kademe"]}. {kademe["baslik"]}** — {kademe["mesaj"]}'
                )
            if oneri.get("tur") == "sozel" and oneri.get("oneri") in dersler:
                if st.button(
                    f'Sözel derse geç ({oneri["oneri"]})', key="kamp_sozel_gec"
                ):
                    st.session_state["kamp_ders"] = oneri["oneri"]
                    st.session_state["kamp_mikro_idx"] = 0
                    st.session_state["kamp_dilim_idx"] = 0
                    _temizle_gorev_durumu()
                    st.rerun()
            if st.button("Kapat", key="kamp_yoruldum_kapat"):
                st.session_state["kamp_yoruldum_goster"] = False
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

