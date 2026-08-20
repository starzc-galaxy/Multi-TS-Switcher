from app.engine.ts.packets import parse_adaptation, parse_header
from app.engine.ts.rebase import (
    make_discontinuity_marker,
    pcr_add,
    read_pts,
    rebase_ts_packet,
    write_pts,
)


def test_pcr_add_wraps():
    assert pcr_add((1 << 33) - 10, 20) == 10


def test_pts_roundtrip():
    pts = 0x123456789
    dts = pts - 3000
    pes = bytearray(b"\x00\x00\x01\xE0\x00\x00\xB0\x0A" + b"\x00" * 100)
    write_pts(pes, pts, dts)
    r_pts, r_dts = read_pts(pes)
    assert (r_pts, r_dts) == (pts, dts)


def test_rebase_pcr_and_pts():
    pcr = 90000
    pkt1 = bytearray(188)
    pkt1[0] = 0x47
    pkt1[1] = 0x11
    pkt1[2] = 0x01
    pkt1[3] = 0x20
    pkt1[4] = 7
    pkt1[5] = 0x10
    b = bytearray(6)
    b[0] = (pcr >> 25) & 0xFF
    b[1] = (pcr >> 17) & 0xFF
    b[2] = (pcr >> 9) & 0xFF
    b[3] = (pcr >> 1) & 0xFF
    b[4] = (pcr & 1) << 7
    b[5] = 0
    pkt1[6:12] = b
    out = rebase_ts_packet(bytes(pkt1), 3000, video_pid=None)
    h = parse_header(out)
    a = parse_adaptation(out, h.afc)
    assert a.pcr_base == pcr + 3000


def test_discontinuity_marker():
    pkt = make_discontinuity_marker(0x101, 3)
    h = parse_header(pkt)
    a = parse_adaptation(pkt, h.afc)
    assert h.afc == 2 and a.discontinuity and h.cc == 3
