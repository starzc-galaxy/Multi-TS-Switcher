from __future__ import annotations

import multiprocessing as mp
import queue
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.engine.group_engine import EngineHandle, spawn_engine
from app.ipc.protocol import (
    CMD_STOP,
    CMD_UPDATE_CONFIG,
    encode_message,
    make_command,
)


class _Poller(QThread):
    def __init__(self, supervisor: "EngineSupervisor") -> None:
        super().__init__()
        self.supervisor = supervisor
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            for group_id, handle in list(self.supervisor._handles.items()):
                while True:
                    try:
                        msg = handle.status_queue.get_nowait()
                    except queue.Empty:
                        break
                    mtype = msg.get("type")
                    if mtype == "status":
                        self.supervisor.status_received.emit(group_id, msg.get("state", {}))
                    elif mtype == "event":
                        self.supervisor.event_received.emit(
                            group_id, msg.get("event", ""), msg.get("detail", {})
                        )
                    elif mtype == "frame":
                        self.supervisor.frame_received.emit(
                            group_id,
                            int(msg.get("idx", 0)),
                            int(msg.get("width", 0)),
                            int(msg.get("height", 0)),
                        )
                if not handle.process.is_alive():
                    code = handle.process.exitcode
                    if code is not None and group_id not in self.supervisor._reported_exits:
                        self.supervisor._reported_exits.add(group_id)
                        self.supervisor.engine_exited.emit(group_id, code)
            self.msleep(40)

    def stop(self) -> None:
        self._stop.set()


class EngineSupervisor(QObject):
    status_received = pyqtSignal(int, dict)
    event_received = pyqtSignal(int, str, dict)
    frame_received = pyqtSignal(int, int, int, int)
    engine_exited = pyqtSignal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ctx = mp.get_context("spawn")
        self._handles: dict[int, EngineHandle] = {}
        self._poller = _Poller(self)
        self._reported_exits: set[int] = set()

    def start(self) -> None:
        self._poller.start()

    def stop(self) -> None:
        self._poller.stop()
        self._poller.wait(3000)

    def start_group(self, group_id: int, config_dict: dict, log_dir: Path,
                    preview_shm_name: str | None = None) -> None:
        handle = spawn_engine(
            group_id, config_dict, self._ctx, log_dir,
            preview_shm_name=preview_shm_name,
        )
        self._handles[group_id] = handle

    def stop_group(self, group_id: int) -> None:
        handle = self._handles.get(group_id)
        if handle is None:
            return
        try:
            handle.conn.send(encode_message(make_command(CMD_STOP)))
        except (OSError, ValueError):
            pass
        handle.process.join(timeout=2)
        if handle.process.is_alive():
            handle.process.terminate()
            handle.process.join(timeout=2)
        self._handles.pop(group_id, None)

    def stop_all(self) -> None:
        for group_id in list(self._handles):
            self.stop_group(group_id)

    def command(self, group_id: int, cmd: str, **kw) -> None:
        handle = self._handles.get(group_id)
        if handle is None:
            return
        try:
            handle.conn.send(encode_message(make_command(cmd, **kw)))
        except (OSError, ValueError):
            pass

    def update_config(self, group_id: int, config_dict: dict) -> None:
        self.command(group_id, CMD_UPDATE_CONFIG, config=config_dict)

    def running_group_ids(self) -> list[int]:
        return list(self._handles)
