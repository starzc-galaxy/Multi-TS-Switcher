from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QComboBox, QDialog, QPlainTextEdit, QVBoxLayout


class LogViewer(QDialog):
    def __init__(self, log_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("日志查看")
        self.resize(760, 520)
        self.log_dir = log_dir
        layout = QVBoxLayout(self)
        self.module_combo = QComboBox()
        layout.addWidget(self.module_combo)
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(2000)
        layout.addWidget(self.view)
        self._refresh_modules()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.module_combo.currentTextChanged.connect(lambda _: self.refresh())
        self.refresh()

    def _refresh_modules(self) -> None:
        names = ["ui", "engine", "switch", "error"]
        for f in sorted(self.log_dir.glob("engine_*.log")):
            names.append(f.name.removesuffix(".log"))
        self.module_combo.clear()
        for n in names:
            self.module_combo.addItem(n)

    def refresh(self) -> None:
        name = self.module_combo.currentText()
        path = self.log_dir / f"{name}.log"
        if not path.exists():
            self.view.setPlainText("(无日志)")
            return
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]
        self.view.setPlainText("\n".join(lines))
