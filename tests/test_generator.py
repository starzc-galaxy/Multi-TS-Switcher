from app.engine.ts.generator import SyntheticTS
from app.engine.ts.packets import parse_header
from app.engine.ts.psi import PSITracker


def test_synthetic_ts_parses_and_has_video():
    gen = SyntheticTS(video_pid=0x101, pcr_pid=0x101)
    tracker = PSITracker()
    psi = None
    for pkt in gen.take(300):
        h = parse_header(pkt)
        off = 4
        if h.afc in (2, 3):
            off += 1 + pkt[4]
        payload = pkt[off:]
        info = tracker.feed(pkt, h.pusi, h.pid, payload)
        if info is not None:
            psi = info
    assert psi is not None and psi.video_pid == 0x101


def test_synthetic_ts_contains_sps():
    gen = SyntheticTS(video_pid=0x101, pcr_pid=0x101)
    blob = b"".join(gen.take(300))
    assert b"\x00\x00\x01\x67" in blob
