import multiprocessing as mp
import socket
import threading
import time
from pathlib import Path

from app.config.models import GroupConfig, OutputConfig, SourceConfig, group_to_dict
from app.engine.group_engine import spawn_engine
from app.engine.ts.generator import SyntheticTS


def test_engine_end_to_end(tmp_path: Path):
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probe.bind(("127.0.0.1", 0))
    src_port = probe.getsockname()[1]
    probe.close()
    src_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    src_sock.bind(("127.0.0.1", 0))
    stop = threading.Event()

    def src_loop():
        g = SyntheticTS()
        while not stop.is_set():
            for i, pkt in enumerate(g.take(300)):
                if stop.is_set():
                    break
                src_sock.sendto(pkt, ("127.0.0.1", src_port))
                if i % 50 == 0:
                    time.sleep(0.001)

    threading.Thread(target=src_loop, daemon=True).start()

    out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    out_sock.bind(("127.0.0.1", 0))
    out_port = out_sock.getsockname()[1]
    out_sock.settimeout(0.5)

    cfg = GroupConfig(
        id=1, name="T", note="", interval_seconds=2.0,
        output=OutputConfig("127.0.0.1", out_port, multicast=False),
        interface="", filler_path="",
        sources=[SourceConfig(1, "S", "127.0.0.1", src_port, False)],
    )
    ctx = mp.get_context("spawn")
    handle = spawn_engine(1, group_to_dict(cfg), ctx, tmp_path)
    collected = 0
    deadline = time.time() + 8
    try:
        while time.time() < deadline and collected < 60:
            try:
                data, _ = out_sock.recvfrom(65536)
                if data and data[0] == 0x47:
                    collected += 1
            except socket.timeout:
                pass
    finally:
        stop.set()
        handle.process.terminate()
        handle.process.join(timeout=3)
        out_sock.close()
        src_sock.close()
    assert collected >= 10
