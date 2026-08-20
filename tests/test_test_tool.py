import os
import socket
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PyQt6.QtWidgets import QApplication

from tools.stream_tester import DecodeThread, ReceiverTab, SenderTab, StreamSender


def test_tool_tabs_build():
    app = QApplication.instance() or QApplication([])
    sender = SenderTab()
    receiver = ReceiverTab()
    assert sender.start_btn.text() == "开始发送"
    assert receiver.start_btn.text() == "开始接收"
    sender.close()
    receiver.close()


def test_stream_sender_loopback(tmp_path: Path):
    filler = Path(__file__).resolve().parent.parent / "assets" / "filler.ts"
    if not filler.exists():
        return
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx.bind(("127.0.0.1", port))
    rx.settimeout(0.5)
    stop = threading.Event()
    sender = StreamSender(1, filler, "127.0.0.1", port, False, stop)
    sender.start()
    got = 0
    deadline = time.time() + 5
    try:
        while time.time() < deadline and got < 30:
            try:
                data, _ = rx.recvfrom(65536)
                if data and data[0] == 0x47:
                    got += 1
            except socket.timeout:
                pass
    finally:
        stop.set()
        sender.join(timeout=2)
        rx.close()
    assert got >= 20


def test_decode_thread_emits_frames(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    filler = Path(__file__).resolve().parent.parent / "assets" / "filler.ts"
    if not filler.exists():
        return
    from app.engine.preview import BytesPipe

    pipe = BytesPipe()
    decoder = DecodeThread(pipe)
    frames = []
    decoder.frame_ready.connect(lambda img: frames.append(img))
    decoder.start()
    data = filler.read_bytes()
    for _ in range(3):
        for i in range(0, len(data), 8192):
            pipe.write(data[i : i + 8192])
            time.sleep(0.02)
    deadline = time.time() + 5
    while time.time() < deadline and not frames:
        app.processEvents()
        time.sleep(0.05)
    pipe.close()
    decoder.wait(3000)
    assert frames
