"""Modül import hijyeni testleri (FAZ G kabul kriterleri).

Doğrulananlar:
01 Data/config/servis/view modüllerinin tamamı hatasız import edilir.
02 Import sırasında veritabanı oluşmaz/yazılmaz (yan etki yok).
03 Hiçbir view modülü `main.py` dosyasını import etmez (dairesel bağımlılık).
04 Bütün sekmeler tek imzalı `render(ctx)` fonksiyonu sunar.
05 Veri modülleri servis/arayüz katmanını import etmez.

Çalıştırma:
    python tests/test_import_smoke.py
    python -m unittest discover -s tests -v
"""
import ast
import importlib
import inspect
import os
import subprocess
import sys
import tempfile
import unittest

TEST_KOK = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(TEST_KOK)
if KOK not in sys.path:
    sys.path.insert(0, KOK)

VERI_MODULLERI = (
    "data.curriculum",
    "data.subtopics",
    "data.prerequisites",
    "data.weights_and_times",
    "data.pedagogy",
)

YAPILANDIRMA_MODULLERI = ("config.settings", "config.database")

SERVIS_MODULLERI = (
    "services.auth_service",
    "services.exam_service",
    "services.topic_progress",
    "services.program_motoru",
    "services.alarm_service",
    "services.core_schema",
)

VIEW_MODULLERI = (
    "views.shared",
    "views.login",
    "views.dashboard",
    "views.admin_panel",
    "views.tab_today",
    "views.tab_curriculum",
    "views.tab_exam_analysis",
    "views.tab_wrong_questions",
    "views.tab_alarms",
    "views.tab_weekly_planner",
    "views.tab_private_lessons",
    "views.tab_performance",
    "views.tab_simulator",
)

SEKME_VIEW_MODULLERI = VIEW_MODULLERI[4:]


class ImportHijyeniTestleri(unittest.TestCase):
    def test_01_tum_moduller_import_edilir(self):
        for ad in VERI_MODULLERI + YAPILANDIRMA_MODULLERI + SERVIS_MODULLERI:
            with self.subTest(modul=ad):
                self.assertIsNotNone(importlib.import_module(ad))
        for ad in VIEW_MODULLERI:
            with self.subTest(modul=ad):
                self.assertIsNotNone(importlib.import_module(ad))

    def test_02_veri_importu_veritabani_olusturmaz(self):
        """Veri modülleri import edilirken migration/DB yazımı başlamamalı."""
        gecici = tempfile.mkdtemp(prefix="karakoc_import_")
        hedef_db = os.path.join(gecici, "olmamali.db")
        kod = (
            "import sys; sys.path.insert(0, %r)\n"
            "import data.curriculum, data.subtopics, data.prerequisites\n"
            "import data.weights_and_times, data.pedagogy\n"
            "import config.settings\n"
            "print('TAMAM')\n" % KOK
        )
        ortam = dict(os.environ)
        ortam["KARAKOC_DB_PATH"] = hedef_db
        sonuc = subprocess.run(
            [sys.executable, "-c", kod],
            cwd=KOK,
            env=ortam,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(sonuc.returncode, 0, sonuc.stderr)
        self.assertIn("TAMAM", sonuc.stdout)
        self.assertFalse(
            os.path.exists(hedef_db), "Import sırasında veritabanı oluşturulmamalı"
        )

    def test_03_view_modulleri_main_import_etmez(self):
        for ad in VIEW_MODULLERI:
            yol = os.path.join(KOK, *ad.split(".")) + ".py"
            with open(yol, encoding="utf-8") as dosya:
                agac = ast.parse(dosya.read(), yol)
            for dugum in ast.walk(agac):
                if isinstance(dugum, ast.ImportFrom) and dugum.module:
                    self.assertNotEqual(
                        dugum.module.split(".")[0],
                        "main",
                        "%s main.py import ediyor" % ad,
                    )
                elif isinstance(dugum, ast.Import):
                    for takma in dugum.names:
                        self.assertNotEqual(
                            takma.name.split(".")[0],
                            "main",
                            "%s main.py import ediyor" % ad,
                        )

    def test_04_sekme_viewleri_render_ctx_sunuyor(self):
        for ad in SEKME_VIEW_MODULLERI:
            modul = importlib.import_module(ad)
            self.assertTrue(hasattr(modul, "render"), "%s render yok" % ad)
            parametreler = list(inspect.signature(modul.render).parameters)
            self.assertEqual(
                parametreler[:1], ["ctx"], "%s imzası render(ctx) olmalı" % ad
            )

    def test_05_veri_modulleri_ust_katmani_import_etmez(self):
        for ad in VERI_MODULLERI:
            yol = os.path.join(KOK, *ad.split(".")) + ".py"
            with open(yol, encoding="utf-8") as dosya:
                agac = ast.parse(dosya.read(), yol)
            for dugum in ast.walk(agac):
                if isinstance(dugum, ast.ImportFrom) and dugum.module:
                    kok = dugum.module.split(".")[0]
                    self.assertNotIn(kok, ("services", "views", "config"), ad)
                    self.assertNotEqual(kok, "main", ad)
                elif isinstance(dugum, ast.Import):
                    for takma in dugum.names:
                        kok = takma.name.split(".")[0]
                        self.assertNotIn(kok, ("services", "views", "config"), ad)
                        self.assertNotEqual(kok, "main", ad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
