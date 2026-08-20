from __future__ import annotations

from multiprocessing.shared_memory import SharedMemory

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap


class PreviewConsumer(QObject):
    pixmap_ready = pyqtSignal(QPixmap)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._shm: SharedMemory | None = None
        self._width = 0
        self._height = 0
        self._frame_bytes = 0

    def attach(self, shm_name: str, width: int, height: int) -> None:
        self.detach()
        self._shm = SharedMemory(name=shm_name)
        self._width, self._height = width, height
        self._frame_bytes = width * height * 3

    def detach(self) -> None:
        if self._shm is not None:
            self._shm.close()
            self._shm = None

    def on_frame(self, idx: int, width: int, height: int) -> QPixmap | None:
        if self._shm is None or self._frame_bytes <= 0:
            return None
        off = idx * self._frame_bytes
        data = bytes(self._shm.buf[off : off + self._frame_bytes])
        img = QImage(data, width, height, width * 3, QImage.Format.Format_RGB888)
        pm = QPixmap.fromImage(img)
        self.pixmap_ready.emit(pm)
        return pm
