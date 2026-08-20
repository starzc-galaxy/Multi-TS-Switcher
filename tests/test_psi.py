from app.engine.ts.psi import PSITracker
from app.engine.ts.packets import TS_PKT_LEN


def section_bytes(table_id: int, payload_data: bytes, section_number=0, last_section=0) -> bytes:
    section_length = len(payload_data) + 9
    return b"\x00" + (
        bytes([table_id])
        + bytes([(section_length >> 8) & 0xFF, section_length & 0xFF])
        + bytes([0x00, 0x01, 0xC1, section_number, last_section])
        + payload_data
        + b"\x00\x00\x00\x00"
    )


def pat_payload(pmt_pid: int) -> bytes:
    return bytes([0x00, 0x01]) + bytes([(pmt_pid >> 8) & 0x1F, pmt_pid & 0xFF])


def pmt_payload(pcr_pid: int, video_pid: int) -> bytes:
    out = bytearray()
    out += bytes([0xE1, pcr_pid & 0xFF])
    out += bytes([0xF0, 0x00])
    out += bytes([0x1B, 0xE1, video_pid & 0xFF, 0xF0, 0x00])
    return bytes(out)


def ts_pkt(pid: int, pusi: int, payload: bytes) -> bytes:
    pkt = bytearray(TS_PKT_LEN)
    pkt[0] = 0x47
    pkt[1] = ((pid >> 8) & 0x1F) | (pusi << 6)
    pkt[2] = pid & 0xFF
    pkt[3] = 0x10 | 0x00
    pkt[4 : 4 + len(payload)] = payload
    return bytes(pkt)


def test_psi_tracker_finds_video_pid():
    tracker = PSITracker()
    pat = section_bytes(0x00, pat_payload(0x10))
    info = tracker.feed(ts_pkt(0, 1, pat), pusi=1, pid=0, payload=pat)
    assert info is None  # PAT 不直接返回
    pmt = section_bytes(0x02, pmt_payload(0x100, 0x101))
    info = tracker.feed(ts_pkt(0x10, 1, pmt), pusi=1, pid=0x10, payload=pmt)
    assert info is not None
    assert info.video_pid == 0x101 and info.pcr_pid == 0x100
