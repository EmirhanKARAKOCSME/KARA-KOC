"""KARAKOÇ YKS Akıllı Koçluk Sistemi - uygulama giriş noktası.

Bu dosya yalnızca uygulama akışını kurar:
sayfa ayarları -> stil -> veritabanı başlangıcı -> oturum/giriş ->
kokpit -> sekme tanımları -> ilgili görünümün render edilmesi.

Katmanlar:
- `config/`   : ayarlar ve veritabanı bootstrap/migration yönetimi
- `data/`     : müfredat, alt konu, ön koşul, ağırlık ve süre verileri
- `services/` : iş mantığı (veritabanı + hesaplama), Streamlit'ten bağımsız
- `views/`    : Streamlit arayüz modülleri (her sekme ayrı dosya)
"""
import streamlit as st

from config.database import bootstrap_database
from services import auth_service, study_sessions
from services.alarm_service import hesapla_tum_alarmlar
from services.topic_progress import (
    build_student_curriculum,
    hesapla_tyt_ayt_tamamlanma,
)
from views import (
    admin_panel,
    dashboard,
    kamp_kokpiti,
    login,
    shared,
    tab_alarms,
    tab_curriculum,
    tab_exam_analysis,
    tab_performance,
    tab_private_lessons,
    tab_simulator,
    tab_today,
    tab_weekly_planner,
    tab_wrong_questions,
)
from views.shared import ViewContext

# ==============================================================================
# 1) SAYFA YAPILANDIRMASI (Streamlit'in ilk komutu olmalıdır)
# ==============================================================================
st.set_page_config(
    page_title="KARAKOÇ YKS Akıllı Koçluk Sistemi",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="auto",
)

# ==============================================================================
# 2) BEKLEYEN BİLDİRİMLER VE STİL (assets/style.css)
# ==============================================================================
shared.render_flash_messages()
shared.load_css()

# ==============================================================================
# 3) VERİTABANI BAŞLANGICI (tek çağrı noktası)
# ==============================================================================
# Tüm servis `init_db()`/migration adımları `config/database.py` içinde
# sırayla çalışır. Cache anahtarı (mutlak DB yolu, şema sürümü) çiftidir ve
# SQLite bağlantısı cache'lenmez; rerun'larda migration tekrarlanmaz.
bootstrap_database()

# ==============================================================================
# 4) OTURUM DURUMU VE GİRİŞ EKRANI
# ==============================================================================
if "active_user" not in st.session_state:
    st.session_state.active_user = None

if not st.session_state.active_user:
    # Giriş ekranı kendi içinde st.stop() çağırır.
    login.render()

current_user = st.session_state.active_user

# FAZ 4: Çalışma serisi artık GİRİŞ tarihine değil GERÇEK ÇALIŞMAYA bağlı.
# `update_user_streak()` giriş günlerini sayıyordu; bu gerçek çalışma serisi
# değildir. Seri, tamamlanmış çalışma oturumlarından hesaplanır (bir günde
# toplam en az 15 dk tamamlanmış çalışma o günü saydırır). Eski giriş bazlı
# değer veritabanında korunur (silinmez), yalnızca ekranda gerçek seri
# gösterilir. Profil tasarımı değiştirilmez.
try:
    current_user["streak_count"] = study_sessions.gercek_calisma_serisi(
        current_user["id"]
    )
except Exception:
    current_user["streak_count"] = current_user.get("streak_count", 0)

# ==============================================================================
# 4b) SUNUCU TARAFLI ROL DOĞRULAMA
# ==============================================================================
# `st.session_state` içindeki `rol` tek başına yetki kanıtı DEĞİLDİR.
# Rol, her istekte veritabanından okunur. Hesap silinmiş/pasifse oturum kapanır.
db_rol = auth_service.kullanici_rolu(current_user["id"])
if db_rol is None:
    st.session_state.active_user = None
    st.error(
        "Oturumunuz geçersiz veya hesabınız pasif durumda. Lütfen tekrar"
        " giriş yapın."
    )
    st.stop()
current_user["rol"] = db_rol  # oturum ipucu DB ile eşitlenir

# ==============================================================================
# 5) ÖĞRENCİ MÜFREDATI VE GÖRÜNÜM BAĞLAMI
# ==============================================================================
aktif_mufredat_hiyerarsisi = build_student_curriculum(
    current_user["sinif_seviyesi"], current_user["hedef_alan"]
)

# Görünümler `main.py` globali okumaz; ihtiyaç duydukları veri bu nesnededir.
ctx = ViewContext(user=current_user, mufredat=aktif_mufredat_hiyerarsisi)

# ==============================================================================
# 5b) KAMP MODU (v2.3) — aktifse normal sekmeleri atla, uzay kokpitini aç
# ==============================================================================
if current_user.get("rol") != "admin" and st.session_state.get("kamp_aktif"):
    kamp_kokpiti.render(ctx)
    st.stop()

# ==============================================================================
# 6) YÖNETİCİ PANELİ (panel sonunda st.stop() ile öğrenci kokpitime geçilmez)
# ==============================================================================
# Karar DB'den gelen `db_rol` ile verilir; session_state rolüne güvenilmez.
if db_rol == "admin":
    admin_panel.render(ctx)

# ==============================================================================
# 7) ALARM / MÜFREDAT METRİKLERİ VE KOKPİT
# ==============================================================================
(
    alarmlar_db,
    saglik_skoru,
    delta_yuzde,
    gercek_orand,
    hedef_yuzd,
) = hesapla_tum_alarmlar(
    current_user["id"], current_user["sinif_seviyesi"], aktif_mufredat_hiyerarsisi
)
tyt_orani, ayt_orani, genel_tamamlanma_orani = hesapla_tyt_ayt_tamamlanma(
    current_user["id"], aktif_mufredat_hiyerarsisi
)

ctx.alarmlar = alarmlar_db

dashboard.render(
    ctx,
    saglik_skoru,
    delta_yuzde,
    gercek_orand,
    tyt_orani,
    ayt_orani,
    hedef_yuzd,
)

# ==============================================================================
# 8) SEKMELER (sıra, ad ve sayı değişmedi)
# ==============================================================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(
    [
        "🎯 Bugünün Görevleri",
        "📚 Konu Takip & İlerleme",
        "📝 Deneme Analizi",
        "📕 Yanlış Soru Defteri",
        "🚨 Konu Uyarıları & Alarmlar",
        "📅 Haftalık Çalışma Programı",
        "🤝 Özel Ders & Talepler",
        "📈 Haftalık Performans",
        "🎯 YKS Simülatörü",
    ],
    key="kt_main_tabs",
    on_change="rerun",
)

with tab1:
    tab_today.render(ctx)

with tab2:
    tab_curriculum.render(ctx)

with tab3:
    tab_exam_analysis.render(ctx)

with tab4:
    tab_wrong_questions.render(ctx)

with tab5:
    tab_alarms.render(ctx)

with tab6:
    tab_weekly_planner.render(ctx)

with tab7:
    tab_private_lessons.render(ctx)

with tab8:
    tab_performance.render(ctx)

with tab9:
    tab_simulator.render(ctx)
