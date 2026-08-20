import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PyQt6.QtWidgets import QApplication

from app.ui.license_dialog import LicenseDialog, license_summary, load_license_file


def test_load_license_file_missing(tmp_path: Path):
    assert load_license_file(tmp_path / "none.lic") is None


def test_load_license_file_invalid(tmp_path: Path):
    p = tmp_path / "bad.lic"
    p.write_text("{not json", encoding="utf-8")
    assert load_license_file(p) is None


def test_license_dialog_has_copy_button():
    app = QApplication.instance() or QApplication([])
    dlg = LicenseDialog()
    from PyQt6.QtWidgets import QPushButton

    texts = [btn.text() for btn in dlg.findChildren(QPushButton)]
    assert "复制" in texts
    dlg.close()


def test_license_summary_permanent_and_expiry():
    assert license_summary({"allowed_groups": 9}) == "永久"
    assert "剩余" in license_summary({"expires_at": "2099-01-01T00:00:00+00:00"})
