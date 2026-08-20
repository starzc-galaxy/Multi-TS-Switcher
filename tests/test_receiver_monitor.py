import socket
import threading
import time

from app.engine.monitor import StreamStats
from app.engine.receiver import UDPReceiver, parse_udp_datagram
from app.engine.ts.packets import TS_PKT_LEN


def test_parse_datagram_188():
    data = b"\x47" + b"\x00" * (TS_PKT_LEN - 1)
    pkts = parse_udp_datagram(data * 3 + b"\x47\x00", ts_size=188)
    assert len(pkts) == 3 and all(len(p) == 188 for p in pkts)


def test_parse_datagram_204():
    data = b"\x47" + b"\x00" * (TS_PKT_LEN - 1) + b"\xAA" * 16
    pkts = parse_udp_datagram(data * 2, ts_size=204)
    assert len(pkts) == 2 and all(len(p) == 188 for p in pkts)


def test_stats_health_and_bitrate():
    st = StreamStats()
    st.record(100, 18800, False)
    assert st.healthy(timeout=1.0) is True
    time.sleep(1.05)
    assert st.healthy(timeout=1.0) is False
    snap = st.snapshot(timeout=1.0)
    assert snap["pkt_count"] >= 100 and snap["bitrate"] >= 0


def test_udp_receiver_loopback():
    stop = threading.Event()
    got: list[list[bytes]] = []
    stats = StreamStats()
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    data = b"\x47" + b"\x00" * (TS_PKT_LEN - 1)
    rx = UDPReceiver(1, "127.0.0.1", port, False, "", 188, lambda pkts, metas: got.append(pkts), stop, stats)
    rx.start()
    time.sleep(0.1)
    for _ in range(5):
        sock.sendto(data, ("127.0.0.1", port))
    time.sleep(0.3)
    stop.set()
    rx.join(timeout=2)
    assert sum(len(b) for b in got) >= 5
