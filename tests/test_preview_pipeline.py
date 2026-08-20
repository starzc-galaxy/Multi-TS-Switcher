import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from multiprocessing.shared_memory import SharedMemory
import threading
import time

from PyQt6.QtWidgets import QApplication

from app.engine.preview import BytesPipe
from app.ui.preview import PreviewConsumer


def test_shared_memory_frame_to_pixmap():
    app = QApplication.instance() or QApplication([])
    w, h = 48, 27
    shm = SharedMemory(create=True, size=w * h * 3)
    try:
        data = bytes(range(256)) * (w * h * 3 // 256 + 1)
        shm.buf[: w * h * 3] = data[: w * h * 3]
        consumer = PreviewConsumer()
        consumer.attach(shm.name, w, h)
        pm = consumer.on_frame(0, w, h)
        assert pm is not None and not pm.isNull()
        consumer.detach()
    finally:
        shm.close()
        shm.unlink()


def test_bytes_pipe_blocks_and_closes():
    pipe = BytesPipe()
    pipe.write(b"hello")
    assert pipe.read(5) == b"hello"
    result = []
    t = threading.Thread(target=lambda: result.append(pipe.read(1)), daemon=True)
    t.start()
    time.sleep(0.1)
    assert not result  # 空队列时阻塞，不返回 EOF
    pipe.close()
    t.join(2)
    assert result == [b""]
