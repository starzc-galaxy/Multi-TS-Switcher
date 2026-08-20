"""生产测试工具：发送多路测试视频源 + 接收验证主程序输出的一路流。

注意：文件名不要以 test_ 开头，否则 PyCharm 会把它当成 pytest 测试文件。
"""

import os
import socket
import struct
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.engine.receiver import parse_udp_datagram
from app.engine.ts.packets import TS_PKT_LEN, SYNC, parse_adaptation, parse_header
from app.paths import exe_dir
from app.ui.styles import QSS_LIGHT

try:
    import ctypes

    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass


def test_sources_dir() -> Path:
    if getattr(sys, "frozen", False):
        local = exe_dir() / "test_sources"
        if local.exists() and any(local.glob("source_*.ts")):
            return local
        meipass = Path(getattr(sys, "_MEIPASS", str(exe_dir()))) / "test_sources"
        if meipass.exists() and any(meipass.glob("source_*.ts")):
            return meipass
        return local
    return exe_dir() / "test_sources"


def _wait_until(target: float) -> None:
    while True:
        now = time.monotonic()
        if now >= target:
            return
        delay = target - now
        time.sleep(min(0.002, max(0.0005, delay)))


class StreamSender(threading.Thread):
    def __init__(self, index: int, path: Path, host: str, port: int,
                 multicast: bool, stop: threading.Event, on_status=None) -> None:
        super().__init__(name=f"send-{index}", daemon=True)
        self.index = index
        self.path = path
        self.host = host
        self.port = port
        self.multicast = multicast
        self.stop = stop
        self.on_status = on_status
        self.sent = 0

    def run(self) -> None:
        data = self.path.read_bytes()
        pkts = parse_udp_datagram(data, 188)
        pcrs: list[int | None] = []
        for pkt in pkts:
            hdr = parse_header(pkt)
            adapt = parse_adaptation(pkt, hdr.afc) if hdr else None
            pcrs.append(adapt.pcr_base if adapt else None)
        first_pcr = next((p for p in pcrs if p is not None), 0)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self.multicast:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack("b", 8))
        try:
            while not self.stop.is_set():
                base = time.monotonic()
                for pkt, pcr in zip(pkts, pcrs):
                    if self.stop.is_set():
                        break
                    if pcr is not None:
                        _wait_until(base + (pcr - first_pcr) / 27_000_000)
                    sock.sendto(pkt, (self.host, self.port))
                    self.sent += 1
        finally:
            sock.close()


class SenderTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._threads: list[StreamSender] = []
        self._stop = threading.Event()
        form = QFormLayout(self)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 9)
        self.count_spin.setValue(2)
        self.base_edit = QLineEdit("229.1.1.1")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(7000)
        self.mcast_check = QCheckBox("组播")
        self.mcast_check.setChecked(True)
        form.addRow("路数", self.count_spin)
        form.addRow("起始地址", self.base_edit)
        form.addRow("端口", self.port_spin)
        form.addRow("", self.mcast_check)
        self.status_label = QLabel("未启动")
        self.status_label.setWordWrap(True)
        form.addRow(self.status_label)
        btns = QHBoxLayout()
        self.start_btn = QPushButton("开始发送")
        self.start_btn.setObjectName("primary")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop_sending)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.stop_btn)
        btns.addStretch(1)
        form.addRow(btns)

    def _start(self, *args) -> None:
        sources_dir = test_sources_dir()
        if not (sources_dir / "source_1.ts").exists():
            self.status_label.setText("正在生成测试源文件…")
            from tools.generate_test_sources import generate

            generate(sources_dir, on_progress=self._on_generate_progress)
        base = self.base_edit.text().strip()
        port = self.port_spin.value()
        n = self.count_spin.value()
        self._stop = threading.Event()
        self._threads = []
        for i in range(1, n + 1):
            addr = base if i == 1 else f"{base.rsplit('.', 1)[0]}.{int(base.rsplit('.', 1)[1]) + i - 1}"
            t = StreamSender(i, sources_dir / f"source_{i}.ts", addr, port,
                             self.mcast_check.isChecked(), self._stop)
            t.start()
            self._threads.append(t)
        self.status_label.setText(f"正在发送 {n} 路（{base}:{port} 起，端口相同）")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def _on_generate_progress(self, num: str, label: str, state: str) -> None:
        self.status_label.setText(f"测试源 {num}（{label}）：{state}")
        QApplication.processEvents()

    def _stop_sending(self, *args) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2)
        self._threads = []
        self.status_label.setText("已停止")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)


class DecodeThread(QThread):
    frame_ready = pyqtSignal(QImage)

    def __init__(self, pipe, parent=None) -> None:
        super().__init__(parent)
        self.pipe = pipe

    def run(self) -> None:
        import av

        try:
            while True:
                try:
                    container = av.open(self.pipe, mode="r")
                    video = next((s for s in container.streams if s.type == "video"), None)
                    if video is None:
                        time.sleep(0.5)
                        continue
                    video.thread_type = "AUTO"
                    for frame in container.decode(video):
                        try:
                            rgb = frame.reformat(width=480, height=270, format="rgb24")
                            arr = rgb.to_ndarray()
                            img = QImage(arr.tobytes(), 480, 270, 480 * 3, QImage.Format.Format_RGB888)
                            self.frame_ready.emit(img.copy())
                        except Exception:
                            continue
                except Exception:
                    time.sleep(0.2)
        except Exception:
            pass


class ReceiverTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running = False
        self._rx_thread: threading.Thread | None = None
        self._decode_thread: DecodeThread | None = None
        self._stop = threading.Event()
        from app.engine.preview import BytesPipe

        self.pipe = BytesPipe()
        form = QFormLayout(self)
        self.addr_edit = QLineEdit("230.1.1.1")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(7000)
        self.mcast_check = QCheckBox("组播")
        self.mcast_check.setChecked(True)
        form.addRow("接收地址", self.addr_edit)
        form.addRow("端口", self.port_spin)
        form.addRow("", self.mcast_check)
        self.preview = QLabel("等待接收…")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(270)
        self.preview.setStyleSheet("background-color:#0b1220; color:#64748b;")
        form.addRow(self.preview)
        self.stats_label = QLabel("收包 0 · 码率 0 kbps · CC错误 0")
        form.addRow(self.stats_label)
        btns = QHBoxLayout()
        self.start_btn = QPushButton("开始接收")
        self.start_btn.setObjectName("primary")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop_rx)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.stop_btn)
        btns.addStretch(1)
        form.addRow(btns)

    def _start(self, *args) -> None:
        self._stop = threading.Event()
        self.pipe = self.pipe.__class__()
        self._decode_thread = DecodeThread(self.pipe, self)
        self._decode_thread.frame_ready.connect(self._on_frame)
        self._decode_thread.start()
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()
        self._running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def _rx_loop(self) -> None:
        host = self.addr_edit.text().strip()
        port = self.port_spin.value()
        mcast = self.mcast_check.isChecked()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if mcast:
            try:
                sock.bind((host, port))
            except OSError:
                sock.bind(("0.0.0.0", port))
        else:
            sock.bind((host, port))
        if mcast:
            mreq = socket.inet_aton(host) + socket.inet_aton("0.0.0.0")
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(0.2)
        total = 0
        cc_errors = 0
        last_cc: dict[int, int] = {}
        window: list[tuple[float, int]] = []
        last_stats = 0.0
        try:
            while not self._stop.is_set():
                try:
                    data, _ = sock.recvfrom(65536)
                except socket.timeout:
                    continue
                pkts = parse_udp_datagram(data, 188)
                for pkt in pkts:
                    hdr = parse_header(pkt)
                    if hdr is None:
                        continue
                    if not hdr.tei:
                        exp = last_cc.get(hdr.pid)
                        if exp is not None and hdr.cc != exp:
                            cc_errors += 1
                        last_cc[hdr.pid] = (hdr.cc + 1) & 0x0F
                total += len(pkts)
                now = time.monotonic()
                window.append((now, len(data)))
                while window and window[0][0] < now - 2.0:
                    window.pop(0)
                self.pipe.write(data)
                if now - last_stats >= 1.0:
                    last_stats = now
                    bitrate = int(sum(b for _, b in window) * 8 / 2.0)
                    self.stats_label.setText(
                        f"收包 {total} · 码率 {bitrate // 1000} kbps · CC错误 {cc_errors}"
                    )
        finally:
            sock.close()

    def _on_frame(self, img: QImage) -> None:
        self.preview.setPixmap(QPixmap.fromImage(img))

    def _stop_rx(self, *args) -> None:
        self._stop.set()
        if self._rx_thread is not None:
            self._rx_thread.join(timeout=2)
        if self._decode_thread is not None:
            self.pipe.close()
            self._decode_thread.wait(2000)
        self._running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.preview.setText("已停止")


class TestToolWindow(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("生产测试工具")
        self.resize(640, 560)
        root = QVBoxLayout(self)
        tip = QLabel(
            "发送：生成 1–9 路彩色测试 TS 流（默认 229.1.1.x:7000），可给主程序当输入源；"
            "接收：监听一路 UDP-TS 并解码显示，用于验证主程序输出。"
        )
        tip.setWordWrap(True)
        root.addWidget(tip)
        tabs = QTabWidget()
        tabs.addTab(SenderTab(), "发送测试源")
        tabs.addTab(ReceiverTab(), "接收验证")
        root.addWidget(tabs, 1)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("TestTool")
    app.setStyleSheet(QSS_LIGHT)
    win = TestToolWindow()
    win.show()
    autoquit = os.environ.get("MTS_AUTOQUIT_MS")
    if autoquit:
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(int(autoquit), app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
