from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config.loader import validate_groups
from app.config.models import GroupConfig, OutputConfig, SourceConfig
from app.debuglog import debug_log
from app.ui.native_dialog import open_file_dialog
from app.netinfo import interface_choices


class ConfigPanel(QWidget):
    config_saved = pyqtSignal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._groups: list[GroupConfig] = []
        self._allowed_groups = 9
        self._current_index = -1
        self._build_ui()

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(splitter)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self.group_list = QListWidget()
        self.group_list.currentRowChanged.connect(self._on_select_group)
        lv.addWidget(self.group_list)
        add_group_btn = QPushButton("新增组")
        del_group_btn = QPushButton("删除组")
        add_group_btn.clicked.connect(self._add_group)
        del_group_btn.clicked.connect(self._del_group)
        lv.addWidget(add_group_btn)
        lv.addWidget(del_group_btn)
        splitter.addWidget(left)

        right = QScrollArea()
        right.setWidgetResizable(True)
        form_host = QWidget()
        self.form = QFormLayout(form_host)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.name_edit = QLineEdit()
        self.note_edit = QPlainTextEdit()
        self.note_edit.setFixedHeight(56)
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(1.0, 3600.0)
        self.interval_spin.setSuffix(" 秒")
        self.out_addr = QLineEdit()
        self.out_port = QSpinBox()
        self.out_port.setRange(1, 65535)
        self.out_mcast = QCheckBox("组播输出")
        self.interface_combo = QComboBox()
        filler_row = QHBoxLayout()
        self.filler_edit = QLineEdit()
        self.filler_edit.setPlaceholderText("assets/filler.ts")
        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._browse_filler)
        filler_row.addWidget(self.filler_edit, 1)
        filler_row.addWidget(browse_btn)
        self.enabled_check = QCheckBox("启用本组")
        self.lock_label = QLabel("")
        self.lock_label.setStyleSheet("color:#b91c1c; font-weight:600;")

        self.form.addRow("组名", self.name_edit)
        self.form.addRow("组备注", self.note_edit)
        self.form.addRow("轮询间隔", self.interval_spin)
        self.form.addRow("输出地址", self.out_addr)
        self.form.addRow("输出端口", self.out_port)
        self.form.addRow("", self.out_mcast)
        self.form.addRow("绑定网卡", self.interface_combo)
        self.form.addRow("垫片文件", filler_row)
        self.form.addRow("", self.enabled_check)
        self.form.addRow("", self.lock_label)

        self.form.addRow(QLabel("输入源 · 实时状态 (最多 9 路)"))
        self.source_table = QTableWidget(0, 9)
        self.source_table.setHorizontalHeaderLabels(
            ["状态", "名称", "地址", "端口", "备注", "码率", "收包", "CC错误", "断流"]
        )
        self.source_table.horizontalHeader().setStretchLastSection(True)
        self.source_table.verticalHeader().setVisible(False)
        self.form.addRow(self.source_table)

        src_btns = QHBoxLayout()
        add_src = QPushButton("新增源")
        del_src = QPushButton("删除源")
        up_src = QPushButton("上移")
        down_src = QPushButton("下移")
        add_src.clicked.connect(self._add_source)
        del_src.clicked.connect(self._del_source)
        up_src.clicked.connect(lambda *a: self._move_source(-1))
        down_src.clicked.connect(lambda *a: self._move_source(1))
        src_btns.addWidget(add_src)
        src_btns.addWidget(del_src)
        src_btns.addWidget(up_src)
        src_btns.addWidget(down_src)
        src_btns.addStretch(1)
        self.form.addRow(src_btns)

        self.save_btn = QPushButton("保存配置")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        self.form.addRow(self.save_btn)
        right.setWidget(form_host)
        splitter.addWidget(right)
        splitter.setSizes([180, 480])

    def set_groups(self, groups: list[GroupConfig]) -> None:
        self._groups = [g for g in groups]
        self.group_list.blockSignals(True)
        self.group_list.clear()
        for g in self._groups:
            QListWidgetItem(g.name or f"组 {g.id}", self.group_list)
        self.group_list.blockSignals(False)
        if self._groups:
            self.group_list.setCurrentRow(0)

    def set_allowed_groups(self, n: int) -> None:
        self._allowed_groups = n

    def count_groups(self) -> int:
        return len(self._groups)

    def _on_select_group(self, row: int) -> None:
        self._current_index = row
        if not (0 <= row < len(self._groups)):
            return
        g = self._groups[row]
        locked = g.id > self._allowed_groups
        self.name_edit.setText(g.name)
        self.note_edit.setPlainText(g.note)
        self.interval_spin.setValue(g.interval_seconds)
        self.out_addr.setText(g.output.address)
        self.out_port.setValue(g.output.port)
        self.out_mcast.setChecked(g.output.multicast)
        self._fill_interface_combo(g.interface)
        self.filler_edit.setText(g.filler_path)
        self.enabled_check.setChecked(g.enabled)
        self.lock_label.setText("授权组数不足，本组不可用" if locked else "")
        self.source_table.setRowCount(len(g.sources))
        for i, s in enumerate(g.sources):
            self._set_source_row(i, s)
        for w in (
            self.name_edit, self.note_edit, self.interval_spin, self.out_addr,
            self.out_port, self.out_mcast, self.interface_combo, self.filler_edit,
            self.enabled_check, self.source_table, self.save_btn,
        ):
            w.setEnabled(not locked)

    def _set_source_row(self, row: int, s: SourceConfig, snap: dict | None = None,
                        live_only: bool = False) -> None:
        live = snap or {}
        healthy = live.get("healthy", False)
        if live_only:
            items = {
                0: "●" if healthy else "○",
                5: f"{live.get('bitrate', 0) // 1000} kbps",
                6: str(live.get("pkt_count", 0)),
                7: str(live.get("cc_errors", 0)),
                8: str(live.get("pcr_jumps", 0)),
            }
            for col, text in items.items():
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setForeground(QColor("#15803d") if healthy else QColor("#dc2626"))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.source_table.setItem(row, col, item)
            return
        items = [
            "●" if healthy else "○",
            s.name,
            s.address,
            str(s.port),
            s.note,
            f"{live.get('bitrate', 0) // 1000} kbps",
            str(live.get("pkt_count", 0)),
            str(live.get("cc_errors", 0)),
            str(live.get("pcr_jumps", 0)),
        ]
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            if col == 0:
                item.setForeground(QColor("#15803d") if healthy else QColor("#dc2626"))
            if col in (0, 5, 6, 7, 8):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter if col != 1 else Qt.AlignmentFlag.AlignLeft
            )
            self.source_table.setItem(row, col, item)

    def update_group_status(self, group_id: int, state: dict) -> None:
        g = self._current_group()
        if g is None or g.id != group_id:
            return
        sources = state.get("sources", {})
        for row, s in enumerate(g.sources):
            snap = sources.get(s.id, {})
            self._set_source_row(row, s, snap, live_only=True)

    def _current_group(self) -> GroupConfig | None:
        if 0 <= self._current_index < len(self._groups):
            return self._groups[self._current_index]
        return None

    def _read_form_into_group(self) -> None:
        g = self._current_group()
        if g is None:
            return
        g.name = self.name_edit.text().strip() or f"组 {g.id}"
        g.note = self.note_edit.toPlainText().strip()
        g.interval_seconds = self.interval_spin.value()
        g.output = OutputConfig(
            self.out_addr.text().strip(), self.out_port.value(), self.out_mcast.isChecked()
        )
        g.interface = self.interface_combo.currentData() or ""
        g.filler_path = self.filler_edit.text().strip()
        g.enabled = self.enabled_check.isChecked()
        g.sources = []
        for row in range(self.source_table.rowCount()):
            def cell(r, c):
                item = self.source_table.item(r, c)
                return item.text() if item else ""

            try:
                sid = row + 1
                g.sources.append(
                    SourceConfig(
                        id=sid,
                        name=cell(row, 1).strip() or f"源 {sid}",
                        address=cell(row, 2).strip(),
                        port=int(cell(row, 3) or 0),
                        multicast=True,
                        enabled=True,
                        note=cell(row, 4).strip(),
                    )
                )
            except ValueError:
                continue
        self.group_list.item(self._current_index).setText(g.name)

    def _save(self, *args) -> None:
        self._read_form_into_group()
        errs = validate_groups(self._groups)
        if errs:
            QMessageBox.warning(self, "配置无效", "\n".join(errs))
            return
        self.config_saved.emit([g for g in self._groups])

    def _add_group(self, *args) -> None:
        nid = max((g.id for g in self._groups), default=0) + 1
        self._groups.append(
            GroupConfig(
                id=nid, name=f"组 {nid}", note="", interval_seconds=20.0,
                output=OutputConfig("230.1.1.1", 7000), interface="",
                filler_path="assets/filler.ts",
                sources=[SourceConfig(1, "源 1", "229.1.1.1", 7000, True)],
            )
        )
        self.group_list.addItem(f"组 {nid}")
        self.group_list.setCurrentRow(len(self._groups) - 1)

    def _del_group(self, *args) -> None:
        if self._current_index < 0:
            return
        self._groups.pop(self._current_index)
        self.group_list.takeItem(self._current_index)
        self.group_list.setCurrentRow(max(0, min(self._current_index, len(self._groups) - 1)))

    def _add_source(self, *args) -> None:
        g = self._current_group()
        if g is None:
            return
        if len(g.sources) >= 9:
            QMessageBox.information(self, "提示", "每组最多 9 个输入源")
            return
        sid = max((s.id for s in g.sources), default=0) + 1
        g.sources.append(SourceConfig(sid, f"源 {sid}", "229.1.1.1", 7000, True))
        self._render_source_table()

    def _del_source(self, *args) -> None:
        g = self._current_group()
        if g is None:
            return
        row = self.source_table.currentRow()
        if 0 <= row < len(g.sources):
            g.sources.pop(row)
            self._render_source_table()

    def _move_source(self, direction: int, *args) -> None:
        g = self._current_group()
        if g is None:
            return
        row = self.source_table.currentRow()
        target = row + direction
        if 0 <= row < len(g.sources) and 0 <= target < len(g.sources):
            g.sources[row], g.sources[target] = g.sources[target], g.sources[row]
            self._render_source_table()
            self.source_table.setCurrentCell(target, 0)

    def _render_source_table(self) -> None:
        g = self._current_group()
        if g is None:
            return
        self.source_table.setRowCount(len(g.sources))
        for i, s in enumerate(g.sources):
            self._set_source_row(i, s)

    def _browse_filler(self, *args) -> None:
        debug_log("browse_filler enter")
        path = open_file_dialog(self, "选择垫片 TS 文件", "", "TS 文件 (*.ts);;所有文件 (*)")
        debug_log(f"browse_filler exit: {path}")
        if path:
            self.filler_edit.setText(path)

    def _fill_interface_combo(self, value: str) -> None:
        self.interface_combo.blockSignals(True)
        self.interface_combo.clear()
        for label, val in interface_choices():
            self.interface_combo.addItem(label, val)
        if value:
            idx = self.interface_combo.findData(value)
            if idx >= 0:
                self.interface_combo.setCurrentIndex(idx)
        self.interface_combo.blockSignals(False)
