import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from app.config.models import AppConfig
from app.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_main_window_opens(app):
    win = MainWindow(allowed_groups=9, app_config=AppConfig())
    win.show()
    assert win.windowTitle().startswith("Multi-TS Switcher")
    win.close()
