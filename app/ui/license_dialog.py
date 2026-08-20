from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.licensing.fingerprint import machine_id
from app.licensing.license_io import LicenseError, verify_license
from app.debuglog import debug_log
from app.ui.native_dialog import open_file_dialog
from app.paths import config_dir

LICENSE_PATH = config_dir() / "license.lic"


def license_summary(info: dict) -> str:
    expires = info.get("expires_at")
    if not expires:
        return "永久"
    exp_dt = datetime.fromisoformat(expires)
    if exp_dt.tzinfo is None:
        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
    remain = max(0, (exp_dt - datetime.now(exp_dt.tzinfo)).days + 1)
    return f"至 {exp_dt.date().isoformat()}（剩余 {remain} 天）"


def load_license_file(path: Path) -> dict | None:
    try:
        if not path.exists():
            return None
        info = verify_license(path.read_text(encoding="utf-8"))
        if info.get("machine_id") != machine_id():
            return None
        return info
    except (LicenseError, OSError, ValueError):
        return None


class LicenseDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("软件授权")
        self.setMinimumWidth(460)
        root = QVBoxLayout(self)
        tip = QLabel("本软件需要有效授权才能运行。请将授权文件（.lic）提供给管理员，"
                     "或用下方按钮导入。")
        tip.setWordWrap(True)
        root.addWidget(tip)
        form = QFormLayout()
        mid_row = QHBoxLayout()
        self.mid_edit = QLineEdit(machine_id())
        self.mid_edit.setReadOnly(True)
        self.mid_edit.setCursorPosition(0)
        copy_btn = QPushButton("复制")
        copy_btn.setObjectName("primary")
        copy_btn.clicked.connect(self._copy_machine_id)
        mid_row.addWidget(self.mid_edit, 1)
        mid_row.addWidget(copy_btn)
        form.addRow("本机机器码", mid_row)
        self.status_label = QLabel("尚未导入授权")
        form.addRow("状态", self.status_label)
        root.addLayout(form)
        btns = QHBoxLayout()
        import_btn = QPushButton("导入授权文件…")
        quit_btn = QPushButton("退出")
        import_btn.setObjectName("primary")
        import_btn.clicked.connect(self._import_file)
        quit_btn.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(import_btn)
        btns.addWidget(quit_btn)
        root.addLayout(btns)

    def _copy_machine_id(self, *args) -> None:
        QApplication.clipboard().setText(machine_id())
        self.status_label.setText("机器码已复制")

    def _import_file(self, *args) -> None:
        debug_log("license_dialog import enter")
        path = open_file_dialog(self, "选择授权文件", "", "授权文件 (*.lic);;所有文件 (*)")
        debug_log(f"license_dialog import exit: {path}")
        if not path:
            return
        try:
            info = verify_license(Path(path).read_text(encoding="utf-8"))
        except (LicenseError, OSError) as exc:
            QMessageBox.critical(self, "授权无效", str(exc))
            return
        if info.get("machine_id") != machine_id():
            QMessageBox.critical(self, "授权无效", "授权文件与本机机器码不匹配")
            return
        LICENSE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LICENSE_PATH.write_text(Path(path).read_text(encoding="utf-8"), encoding="utf-8")
        self.status_label.setText(
            f"授权有效：{info.get('allowed_groups')} 组 · {license_summary(info)}"
        )
        self.accept()


def ensure_license() -> int | None:
    info = load_license_file(LICENSE_PATH)
    if info is not None:
        return int(info.get("allowed_groups", 0))
    dlg = LicenseDialog()
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return int(load_license_file(LICENSE_PATH).get("allowed_groups", 0))
    return None
