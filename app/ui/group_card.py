from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

from app.config.models import GroupConfig


class GroupCard(QFrame):
    """纯视频卡片：预览画面 + 右上角信息浮层（组信息/正常异常数/当前源）。"""

    def __init__(self, group: GroupConfig, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.group_id = group.id
        self.group_name = group.name
        self.output_text = f"{group.output.address}:{group.output.port}"
        self._source_ids = [s.id for s in group.sources]
        self._locked = False
        self._build_ui()

    def _build_ui(self) -> None:
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        self.preview = QLabel("无信号")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(200)
        self.preview.setStyleSheet(
            "background-color:#0b1220; color:#64748b; font-size:16px; border-radius:10px;"
        )
        grid.addWidget(self.preview, 0, 0)

        self.overlay = QFrame()
        self.overlay.setObjectName("videoOverlay")
        ol = QVBoxLayout(self.overlay)
        ol.setContentsMargins(10, 8, 10, 8)
        ol.setSpacing(2)
        self.title_label = QLabel(self.group_name or f"组 {self.group_id}")
        self.title_label.setObjectName("ovTitle")
        self.output_label = QLabel(self.output_text)
        self.output_label.setObjectName("ovDim")
        self.meta_label = QLabel("正常 0 · 异常 0")
        self.meta_label.setObjectName("ovMeta")
        self.current_label = QLabel("当前源：-")
        self.current_label.setObjectName("ovMeta")
        ol.addWidget(self.title_label)
        ol.addWidget(self.output_label)
        ol.addWidget(self.meta_label)
        ol.addWidget(self.current_label)
        for label in (self.title_label, self.output_label, self.meta_label, self.current_label):
            shadow = QGraphicsDropShadowEffect(self.overlay)
            shadow.setBlurRadius(6)
            shadow.setOffset(0, 0)
            shadow.setColor(QColor(0, 0, 0, 220))
            label.setGraphicsEffect(shadow)
        grid.addWidget(
            self.overlay, 0, 0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        if locked:
            self.meta_label.setText("未授权 · 仅监视")
            self.current_label.setText("当前源：-")

    def set_status(self, state: dict) -> None:
        if self._locked:
            return
        source_names = state.get("source_names", {})
        sources = state.get("sources", {})
        current = state.get("current")
        n = len(self._source_ids)
        ok = sum(1 for sid in self._source_ids if sources.get(sid, {}).get("healthy"))
        self.meta_label.setText(f"正常 {ok} · 异常 {n - ok}")
        name = source_names.get(current, f"源 {current}") if current is not None else "-"
        self.current_label.setText(f"当前源：{name}")

    def set_preview_pixmap(self, pm: QPixmap) -> None:
        if pm.isNull():
            return
        self.preview.setPixmap(
            pm.scaled(
                self.preview.width(), self.preview.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
