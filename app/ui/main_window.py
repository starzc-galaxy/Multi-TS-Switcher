from __future__ import annotations

import os
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence, QPixmap
from PyQt6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolBar,
    QWidget,
)

from app.config.loader import load_app_config, load_groups, save_app_config, save_groups
from app.config.models import AppConfig, group_to_dict
from app.debuglog import debug_log
from app.ui.native_dialog import open_file_dialog
from app.ui.config_panel import ConfigPanel
from app.ui.engine_supervisor import EngineSupervisor
from app.ui.icons import load_icon
from app.ui.log_viewer import LogViewer
from app.ui.monitor_wall import MonitorWall
from app.ui.preview import PreviewConsumer
from app.ui.settings_dialog import SettingsDialog
from app.paths import config_dir, log_dir


class MainWindow(QMainWindow):
    def __init__(self, allowed_groups: int, app_config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.allowed_groups = allowed_groups
        self.app_config = app_config
        self.config_dir = config_dir()
        self.log_dir = log_dir()
        self.groups_path = self.config_dir / "groups.json"
        self.app_path = self.config_dir / "app.json"
        self.groups = load_groups(self.groups_path)
        self._shms: dict[int, SharedMemory] = {}
        self._previews: dict[int, PreviewConsumer] = {}
        self._fullscreen = False

        self.setWindowTitle("Multi-TS Switcher")
        self.resize(1440, 860)
        self._build_ui()
        self.supervisor = EngineSupervisor(self)
        self.supervisor.start()
        self.supervisor.status_received.connect(self._on_status)
        self.supervisor.event_received.connect(self._on_event)
        self.supervisor.frame_received.connect(self._on_frame)
        self.supervisor.engine_exited.connect(self._on_engine_exited)
        self.config_panel.set_groups(self.groups)
        self.config_panel.set_allowed_groups(allowed_groups)
        self.monitor_wall.set_groups(self.groups)
        self._apply_locks()

    def _build_ui(self) -> None:
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.toggle_all_action = QAction(load_icon("play"), "启动全部", self)
        self.settings_action = QAction(load_icon("settings"), "设置", self)
        self.log_action = QAction(load_icon("file-text"), "日志", self)
        self.license_action = QAction(load_icon("shield-check"), "授权", self)
        self.fullscreen_action = QAction(load_icon("maximize"), "全屏", self)
        self.fullscreen_action.setShortcut(QKeySequence("F11"))
        toolbar.addAction(self.toggle_all_action)
        toolbar.addSeparator()
        toolbar.addAction(self.settings_action)
        toolbar.addAction(self.log_action)
        toolbar.addAction(self.license_action)
        toolbar.addSeparator()
        toolbar.addAction(self.fullscreen_action)
        self.status_info = QLabel("  就绪")
        toolbar.addWidget(self.status_info)

        self.toggle_all_action.triggered.connect(self._toggle_all)
        self.settings_action.triggered.connect(self._open_settings)
        self.log_action.triggered.connect(self._open_logs)
        self.license_action.triggered.connect(self._show_license)
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)

        self.monitor_wall = MonitorWall()
        self.config_panel = ConfigPanel()
        self.config_panel.config_saved.connect(self._on_config_saved)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.monitor_wall)
        self.splitter.addWidget(self.config_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([1000, 440])
        self.setCentralWidget(self.splitter)
        self.statusBar().showMessage("准备就绪")

    def _apply_locks(self) -> None:
        for g in self.groups:
            card = self.monitor_wall.card(g.id)
            if card is not None:
                card.set_locked(g.id > self.allowed_groups or not g.enabled)

    def _create_preview_shm(self, group_id: int) -> str | None:
        if not self.app_config.preview_enabled:
            return None
        w, h = 480, 270
        size = 2 * w * h * 3
        try:
            shm = SharedMemory(create=True, size=size)
            self._shms[group_id] = shm
            return shm.name
        except (OSError, ValueError):
            return None

    def _start_all(self, *args) -> None:
        for g in self.groups:
            if not g.enabled or g.id > self.allowed_groups:
                continue
            shm_name = self._create_preview_shm(g.id)
            self.supervisor.start_group(g.id, group_to_dict(g), self.log_dir, shm_name)
        self._update_toggle_state()
        self.statusBar().showMessage(f"已启动 {len(self.supervisor.running_group_ids())} 个引擎")

    def _stop_all(self, *args) -> None:
        self.supervisor.stop_all()
        for shm in self._shms.values():
            try:
                shm.close()
                shm.unlink()
            except (OSError, ValueError):
                pass
        self._shms.clear()
        for pv in self._previews.values():
            pv.detach()
        self._previews.clear()
        self._update_toggle_state()
        self.statusBar().showMessage("已全部停止")

    def _toggle_all(self, *args) -> None:
        if self.supervisor.running_group_ids():
            self._stop_all()
        else:
            self._start_all()

    def _update_toggle_state(self) -> None:
        running = bool(self.supervisor.running_group_ids())
        self.toggle_all_action.setText("停止全部" if running else "启动全部")
        self.toggle_all_action.setIcon(load_icon("power" if running else "play"))

    def _on_config_saved(self, groups: list) -> None:
        save_groups(self.groups_path, groups)
        self.groups = list(groups)
        self.config_panel.set_groups(self.groups)
        self.monitor_wall.set_groups(self.groups)
        self._apply_locks()
        for g in self.groups:
            if g.id in self.supervisor.running_group_ids():
                self.supervisor.update_config(g.id, group_to_dict(g))
        self.statusBar().showMessage("配置已保存并热生效")

    def _on_status(self, group_id: int, state: dict) -> None:
        card = self.monitor_wall.card(group_id)
        if card is None:
            return
        src_names = {s.id: s.name for g in self.groups if g.id == group_id for s in g.sources}
        src_notes = {s.id: s.note for g in self.groups if g.id == group_id for s in g.sources}
        interval = next((g.interval_seconds for g in self.groups if g.id == group_id), 20.0)
        state = dict(state)
        state["source_names"] = src_names
        state["source_notes"] = src_notes
        state["interval_seconds"] = interval
        card.set_status(state)
        self.config_panel.update_group_status(group_id, state)

    def _on_event(self, group_id: int, event: str, detail: dict) -> None:
        self.statusBar().showMessage(f"组 {group_id}: {event} {detail}", 5000)

    def _on_frame(self, group_id: int, idx: int, width: int, height: int) -> None:
        card = self.monitor_wall.card(group_id)
        if card is None:
            return
        pv = self._previews.get(group_id)
        if pv is None:
            shm = self._shms.get(group_id)
            if shm is None:
                return
            pv = PreviewConsumer(self)
            pv.attach(shm.name, width, height)
            pv.pixmap_ready.connect(card.set_preview_pixmap)
            self._previews[group_id] = pv
        pv.on_frame(idx, width, height)

    def _on_engine_exited(self, group_id: int, code: int) -> None:
        card = self.monitor_wall.card(group_id)
        if card is not None:
            card.state_badge.setProperty("state", "err")
            card.state_badge.setText(f"异常退出 {code}")
        self.statusBar().showMessage(f"组 {group_id} 引擎异常退出，代码 {code}，详见日志")
        self._update_toggle_state()

    def _open_settings(self, *args) -> None:
        dlg = SettingsDialog(self.app_config, self)
        if dlg.exec():
            self.app_config = dlg.config()
            save_app_config(self.app_path, self.app_config)
            self.statusBar().showMessage("设置已保存")

    def _open_logs(self, *args) -> None:
        LogViewer(self.log_dir, self).exec()

    def _show_license(self, *args) -> None:
        from app.ui.license_dialog import LICENSE_PATH, license_summary, load_license_file
        from app.licensing.license_io import LicenseError, verify_license
        from app.licensing.fingerprint import machine_id

        info = load_license_file(LICENSE_PATH)
        box = QMessageBox(self)
        box.setWindowTitle("授权")
        if info is None:
            box.setText("当前未授权或授权与本机不匹配")
        else:
            box.setText(
                f"机器码：{info.get('machine_id')}\n"
                f"授权组数：{info.get('allowed_groups')}\n"
                f"有效期：{license_summary(info)}"
            )
        import_btn = box.addButton("导入新授权…", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is import_btn:
            self._import_license()

    def _import_license(self, *args) -> None:
        from app.ui.license_dialog import LICENSE_PATH
        from app.licensing.license_io import LicenseError, verify_license
        from app.licensing.fingerprint import machine_id

        debug_log("main import_license enter")
        path = open_file_dialog(self, "选择授权文件", "", "授权文件 (*.lic);;所有文件 (*)")
        debug_log(f"main import_license exit: {path}")
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
        new_allowed = int(info.get("allowed_groups", 0))
        self.allowed_groups = new_allowed
        self.config_panel.set_allowed_groups(new_allowed)
        self._apply_locks()
        for gid in list(self.supervisor.running_group_ids()):
            if gid > new_allowed:
                self.supervisor.stop_group(gid)
        QMessageBox.information(
            self, "导入成功",
            f"授权已更新：{new_allowed} 组。超出组数的引擎已停止，新授权范围内的组可重新启动。",
        )

    def toggle_fullscreen(self, *args) -> None:
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self.config_panel.hide()
            self.showFullScreen()
            self.fullscreen_action.setIcon(load_icon("minimize"))
        else:
            self.config_panel.show()
            self.showNormal()
            self.fullscreen_action.setIcon(load_icon("maximize"))
        self.monitor_wall.relayout()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self._stop_all()
        self.supervisor.stop()
        event.accept()
