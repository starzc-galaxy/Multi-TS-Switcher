from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
)

from app.config.models import AppConfig
from app.netinfo import interface_choices


class SettingsDialog(QDialog):
    def __init__(self, cfg: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(360)
        form = QFormLayout(self)
        self.interface_combo = QComboBox()
        for label, val in interface_choices():
            self.interface_combo.addItem(label, val)
        if cfg.interface:
            idx = self.interface_combo.findData(cfg.interface)
            if idx >= 0:
                self.interface_combo.setCurrentIndex(idx)
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(0.5, 60.0)
        self.timeout_spin.setValue(cfg.data_timeout_seconds)
        self.timeout_spin.setSuffix(" 秒")
        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(50, 2000)
        self.buffer_spin.setValue(cfg.buffer_ms)
        self.buffer_spin.setSuffix(" ms")
        self.preview_check = QCheckBox("启用预览")
        self.preview_check.setChecked(cfg.preview_enabled)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 30)
        self.fps_spin.setValue(cfg.preview_fps)
        self.retain_spin = QSpinBox()
        self.retain_spin.setRange(1, 90)
        self.retain_spin.setValue(cfg.log_retain_days)
        self.retain_spin.setSuffix(" 天")
        form.addRow("默认网卡", self.interface_combo)
        form.addRow("无数据超时", self.timeout_spin)
        form.addRow("输出缓冲", self.buffer_spin)
        form.addRow("", self.preview_check)
        form.addRow("预览帧率", self.fps_spin)
        form.addRow("日志保留", self.retain_spin)

    def config(self) -> AppConfig:
        return AppConfig(
            interface=self.interface_combo.currentData() or "",
            data_timeout_seconds=self.timeout_spin.value(),
            buffer_ms=self.buffer_spin.value(),
            preview_enabled=self.preview_check.isChecked(),
            preview_fps=self.fps_spin.value(),
            log_retain_days=self.retain_spin.value(),
        )
