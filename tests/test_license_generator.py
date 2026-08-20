import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QMessageBox

from tools.license_generator import LicenseGeneratorWindow


def test_generator_window_builds():
    app = QApplication.instance() or QApplication([])
    win = LicenseGeneratorWindow()
    assert "生成授权" in win.generate_btn.text()
    win.close()


def test_generator_writes_license(tmp_path: Path):
    from app.licensing.license_io import verify_license

    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    priv = Path(__file__).resolve().parent.parent / "tools" / "dev_private_key.pem"
    if not priv.exists():
        return
    win = LicenseGeneratorWindow()
    win.priv_edit.setText(str(priv))
    win.mid_edit.setText("a" * 64)
    win.groups_spin.setValue(3)
    out = tmp_path / "x.lic"
    win.out_edit.setText(str(out))
    win._generate()
    assert out.exists()
    info = verify_license(out.read_text(encoding="utf-8"))
    assert info["allowed_groups"] == 3 and info["machine_id"] == "a" * 64
    win.close()
