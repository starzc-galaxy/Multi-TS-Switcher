"""授权生成器（图形界面，管理员用）。

用法：python tools/license_generator.py
或打包后的 LicenseGenerator.exe。
首次使用会生成密钥对 tools/dev_private_key.pem 并回填公钥到 app/licensing/keys.py。
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import (
    QApplication,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QComboBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.licensing.license_io import LicenseError, create_license, generate_keypair
from app.debuglog import debug_log
from app.ui.native_dialog import open_file_dialog
from app.ui.styles import QSS_LIGHT


def default_private_key_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "dev_private_key.pem"
    return Path(__file__).resolve().parent / "dev_private_key.pem"


def default_output_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "device.lic"
    return Path(__file__).resolve().parent.parent / "lic" / "device.lic"


class LicenseGeneratorWindow(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("授权生成器")
        self.setMinimumWidth(520)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        tip = QLabel(
            "为指定机器码生成离线授权文件。请严格使用客户端授权界面显示的机器码，"
            "组数 1–9。生成的 .lic 文件交给客户导入即可。"
        )
        tip.setWordWrap(True)
        root.addWidget(tip)
        form = QFormLayout()

        priv_row = QHBoxLayout()
        self.priv_edit = QLineEdit(str(default_private_key_path()))
        self.priv_browse_btn = QPushButton("浏览…")
        self.priv_browse_btn.clicked.connect(self._browse_priv)
        priv_row.addWidget(self.priv_edit, 1)
        priv_row.addWidget(self.priv_browse_btn)
        form.addRow("私钥文件", priv_row)

        self.mid_edit = QLineEdit()
        self.mid_edit.setPlaceholderText("粘贴客户端显示的机器码（64 位十六进制）")
        form.addRow("机器码", self.mid_edit)

        self.groups_spin = QSpinBox()
        self.groups_spin.setRange(1, 9)
        self.groups_spin.setValue(9)
        form.addRow("授权组数", self.groups_spin)

        valid_row = QHBoxLayout()
        self.valid_combo = QComboBox()
        self.valid_combo.addItem("永久")
        self.valid_combo.addItem("按天数")
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 3650)
        self.days_spin.setValue(30)
        self.days_spin.setVisible(False)
        self.days_spin.setSuffix(" 天")
        self.valid_combo.currentIndexChanged.connect(
            lambda idx: self.days_spin.setVisible(idx == 1)
        )
        valid_row.addWidget(self.valid_combo)
        valid_row.addWidget(self.days_spin)
        valid_row.addStretch(1)
        form.addRow("有效期", valid_row)

        out_row = QHBoxLayout()
        self.out_edit = QLineEdit(str(default_output_path()))
        self.out_browse_btn = QPushButton("浏览…")
        self.out_browse_btn.clicked.connect(self._browse_out)
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(self.out_browse_btn)
        form.addRow("输出文件", out_row)
        root.addLayout(form)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color:#2563eb;")
        root.addWidget(self.status_label)

        btns = QHBoxLayout()
        self.generate_btn = QPushButton("生成授权")
        self.generate_btn.setObjectName("primary")
        self.generate_btn.clicked.connect(self._generate)
        btns.addStretch(1)
        btns.addWidget(self.generate_btn)
        root.addLayout(btns)

    def _browse_priv(self, *args) -> None:
        debug_log("browse_priv enter")
        path = open_file_dialog(self, "选择私钥文件", "", "PEM 文件 (*.pem);;所有文件 (*)")
        debug_log(f"browse_priv exit: {path}")
        if path:
            self.priv_edit.setText(path)

    def _browse_out(self, *args) -> None:
        debug_log("browse_out enter")
        path = open_file_dialog(self, "选择输出文件", "", "授权文件 (*.lic);;所有文件 (*)", save=True)
        debug_log(f"browse_out exit: {path}")
        if path:
            self.out_edit.setText(path)

    def _ensure_key(self) -> Path | None:
        priv = Path(self.priv_edit.text().strip())
        if priv.exists():
            return priv
        self.status_label.setText("私钥不存在，正在生成密钥对…")
        QApplication.processEvents()
        try:
            priv_pem, pub_pem = generate_keypair()
            priv.parent.mkdir(parents=True, exist_ok=True)
            priv.write_bytes(priv_pem)
            keys_py = Path(__file__).resolve().parent.parent / "app" / "licensing" / "keys.py"
            if getattr(sys, "frozen", False):
                QMessageBox.warning(
                    self, "缺少私钥",
                    "未找到私钥文件。请把 tools/dev_private_key.pem 复制到本程序同目录后重试。",
                )
                return None
            keys_py.write_text(f"PUBLIC_KEY_PEM = {pub_pem!r}\n", encoding="utf-8")
            self.status_label.setText(f"已生成新密钥对：{priv}")
            return priv
        except OSError as exc:
            QMessageBox.critical(self, "错误", f"生成密钥失败：{exc}")
            return None

    def _generate(self, *args) -> None:
        mid = self.mid_edit.text().strip()
        if len(mid) != 64 or any(c not in "0123456789abcdefABCDEF" for c in mid):
            QMessageBox.warning(self, "机器码无效", "机器码应为 64 位十六进制字符，请检查。")
            return
        priv = self._ensure_key()
        if priv is None:
            return
        try:
            days = self.days_spin.value() if self.valid_combo.currentIndex() == 1 else None
            text = create_license(mid, self.groups_spin.value(), priv.read_bytes(), days=days)
            out = Path(self.out_edit.text().strip())
            if not out.name.lower().endswith(".lic"):
                out = out.with_suffix(".lic")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
        except (LicenseError, OSError) as exc:
            QMessageBox.critical(self, "生成失败", str(exc))
            return
        valid_text = "永久" if days is None else f"{days} 天"
        self.status_label.setText(f"已生成：{out}（{self.groups_spin.value()} 组 · {valid_text}）")
        QMessageBox.information(
            self, "生成成功",
            f"授权文件已生成：\n{out}\n授权组数：{self.groups_spin.value()}\n"
            f"有效期：{valid_text}\n\n请将此文件交给客户导入。",
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("LicenseGenerator")
    app.setStyleSheet(QSS_LIGHT)
    win = LicenseGeneratorWindow()
    win.show()
    if os.environ.get("MTS_TEST_DIALOG") == "1":
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(1500, win.priv_browse_btn.click)
        QTimer.singleShot(4500, app.quit)
    autoquit = os.environ.get("MTS_AUTOQUIT_MS")
    if autoquit:
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(int(autoquit), app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
