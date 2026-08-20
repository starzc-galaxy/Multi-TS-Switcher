import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from app.ui.config_panel import ConfigPanel
from app.netinfo import interface_choices


def test_config_panel_builds():
    app = QApplication.instance() or QApplication([])
    panel = ConfigPanel()
    panel.set_groups([])
    assert panel.count_groups() == 0


def test_config_panel_add_group():
    app = QApplication.instance() or QApplication([])
    panel = ConfigPanel()
    panel.set_groups([])
    panel._add_group()
    assert panel.count_groups() == 1


def test_interface_combo_has_auto_option():
    app = QApplication.instance() or QApplication([])
    panel = ConfigPanel()
    choices = interface_choices()
    assert choices[0] == ("自动（默认）", "")
    panel.set_groups([])
    panel._add_group()
    assert panel.interface_combo.itemData(0) == ""
