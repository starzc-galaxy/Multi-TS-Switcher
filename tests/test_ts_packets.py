from app.engine.ts.packets import CCWatcher, TS_PKT_LEN, parse_adaptation, parse_header


def make_pkt(pid=0x100, pusi=0, afc=1, cc=0, payload=None):
    pkt = bytearray(TS_PKT_LEN)
    pkt[0] = 0x47
    pkt[1] = ((pid >> 8) & 0x1F) | (pusi << 6)
    pkt[2] = pid & 0xFF
    pkt[3] = (afc << 4) | (cc & 0x0F)
    if afc in (2, 3):
        pkt[4] = 183 if afc == 2 else 0
        pkt[5] = 0x00
    if payload:
        off = 4
        if afc == 3:
            off = 5 + pkt[4]
        pkt[off : off + len(payload)] = payload
    return bytes(pkt)


def test_parse_header_basic():
    h = parse_header(make_pkt(pid=0x100, pusi=1, afc=1, cc=5))
    assert h is not None and (h.pid, h.pusi, h.afc, h.cc) == (0x100, 1, 1, 5)


def test_parse_header_bad_sync():
    assert parse_header(b"\x00" + b"\x00" * (TS_PKT_LEN - 1)) is None


def test_parse_adaptation_pcr():
    pkt = bytearray(TS_PKT_LEN)
    pkt[0] = 0x47
    pkt[1] = 0x10
    pkt[2] = 0x00
    pkt[3] = 0x20  # afc=2
    pkt[4] = 7
    pkt[5] = 0x10  # PCR flag
    pcr_base = 0x1234567
    pcr_ext = 135
    b = bytearray(6)
    b[0] = (pcr_base >> 25) & 0xFF
    b[1] = (pcr_base >> 17) & 0xFF
    b[2] = (pcr_base >> 9) & 0xFF
    b[3] = (pcr_base >> 1) & 0xFF
    b[4] = ((pcr_base & 1) << 7) | ((pcr_ext >> 8) & 0x01)
    b[5] = pcr_ext & 0xFF
    pkt[6:12] = b
    a = parse_adaptation(bytes(pkt), 2)
    assert a is not None and a.pcr_base == pcr_base and a.pcr_ext == pcr_ext


def test_cc_watcher_counts_errors():
    w = CCWatcher()
    assert w.feed(0x100, 0, 0) is False
    assert w.feed(0x100, 1, 0) is False
    assert w.feed(0x100, 3, 0) is True  # 期待 2，收到 3
    assert w.errors()[0x100] == 1
