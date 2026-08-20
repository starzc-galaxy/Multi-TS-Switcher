from app.engine.ts.packets import parse_adaptation, parse_header, TS_PKT_LEN
from app.engine.ts.raps import SPS_PATTERNS, contains_nal_start, is_rap


def pkt_with_payload(pid, pusi, payload, afc=1):
    pkt = bytearray(TS_PKT_LEN)
    pkt[0] = 0x47
    pkt[1] = ((pid >> 8) & 0x1F) | (pusi << 6)
    pkt[2] = pid & 0xFF
    pkt[3] = (afc << 4) | 0
    off = 4
    if afc in (2, 3):
        pkt[4] = 1
        pkt[5] = 0x40  # random_access_indicator
        off = 6
    pkt[off : off + len(payload)] = payload
    return bytes(pkt)


def test_rap_via_adaptation_flag():
    pkt = pkt_with_payload(0x101, 1, b"AAAA", afc=3)
    hdr = parse_header(pkt)
    adapt = parse_adaptation(pkt, hdr.afc)
    assert is_rap(pkt, hdr, adapt, video_pid=0x101) is True


def test_rap_via_sps_fallback():
    pes = b"\x00\x00\x01\xE0" + b"\x00\x00" + b"\x80\x80\x05" + b"\x21\x00" + b"\x00\x00\x01\x67\x42\x00\x1E"
    pkt = pkt_with_payload(0x101, 1, pes)
    hdr = parse_header(pkt)
    assert is_rap(pkt, hdr, None, video_pid=0x101) is True
    assert contains_nal_start(pes, SPS_PATTERNS) is True


def test_non_video_pid_not_rap():
    pkt = pkt_with_payload(0x102, 1, b"xxxx")
    hdr = parse_header(pkt)
    assert is_rap(pkt, hdr, None, video_pid=0x101) is False


def test_rap_via_mpeg2_gop_header():
    # MPEG2 视频 PES 载荷含 GOP 头 00 00 01 B8
    pes = b"\x00\x00\x01\xE0" + b"\x00\x00" + b"\x80\x80\x05" + b"\x00" * 3 + b"\x00\x00\x01\xB8\x00\x08"
    pkt = pkt_with_payload(0x101, 1, pes)
    hdr = parse_header(pkt)
    assert is_rap(pkt, hdr, None, video_pid=0x101) is True
