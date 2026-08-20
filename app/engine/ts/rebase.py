from __future__ import annotations

from app.engine.ts.packets import TS_PKT_LEN, parse_adaptation, parse_header

PCR_MASK = (1 << 33) - 1


def pcr_add(pcr: int, offset: int) -> int:
    return (pcr + offset) & PCR_MASK


def _read_ts_field(payload: bytes, start: int) -> int | None:
    if start + 5 > len(payload):
        return None
    b = payload[start : start + 5]
    if b[0] & 0x01 != 0x01:
        return None
    return ((b[0] >> 1) & 0x07) << 30 | b[1] << 22 | ((b[2] >> 1) & 0x7F) << 15 | b[3] << 7 | (b[4] >> 1)


def _write_ts_field(payload: bytearray, start: int, value: int, prefix: int) -> None:
    b = memoryview(payload)[start : start + 5]
    b[0] = (b[0] & 0xF1) | (prefix << 4) | 0x01 | (((value >> 30) & 0x07) << 1)
    b[1] = (value >> 22) & 0xFF
    b[2] = (b[2] & 0x01) | (((value >> 15) & 0x7F) << 1)
    b[3] = (value >> 7) & 0xFF
    b[4] = (b[4] & 0x01) | ((value & 0x7F) << 1)


def read_pts(pes_payload: bytes) -> tuple[int | None, int | None]:
    if len(pes_payload) < 9 or pes_payload[:3] != b"\x00\x00\x01":
        return None, None
    flags = pes_payload[6]
    pts = dts = None
    off = 8 + pes_payload[7]
    if flags & 0x20 and off + 5 <= len(pes_payload):
        pts = _read_ts_field(pes_payload, off)
    if flags & 0x10 and off + 10 <= len(pes_payload):
        dts = _read_ts_field(pes_payload, off + 5)
    return pts, dts


def write_pts(pes_payload: bytearray, pts: int | None, dts: int | None) -> None:
    if len(pes_payload) < 9 or pes_payload[:3] != b"\x00\x00\x01":
        return
    flags = pes_payload[6]
    off = 8 + pes_payload[7]
    if flags & 0x20 and pts is not None and off + 5 <= len(pes_payload):
        _write_ts_field(pes_payload, off, pts & PCR_MASK, 0x2)
    if flags & 0x10 and dts is not None and off + 10 <= len(pes_payload):
        _write_ts_field(pes_payload, off + 5, dts & PCR_MASK, 0x1)


def rebase_ts_packet(pkt: bytes, offset: int, video_pid: int | None) -> bytes:
    out = bytearray(pkt)
    hdr = parse_header(pkt)
    if hdr is None:
        return pkt
    adapt = parse_adaptation(pkt, hdr.afc)
    if adapt is not None and adapt.pcr_base is not None:
        pos = 6
        b = bytes(out[pos : pos + 6])
        val = pcr_add(adapt.pcr_base, offset)
        new6 = bytearray(6)
        new6[0] = (val >> 25) & 0xFF
        new6[1] = (val >> 17) & 0xFF
        new6[2] = (val >> 9) & 0xFF
        new6[3] = (val >> 1) & 0xFF
        new6[4] = (b[4] & 0x01) | ((val & 1) << 7)
        new6[5] = b[5]
        out[pos : pos + 6] = bytes(new6)
    if offset and hdr.pid == video_pid and hdr.pusi and hdr.afc in (1, 3):
        alen = adapt.length if adapt is not None else 0
        off = 4 + (1 + alen if hdr.afc in (2, 3) else 0)
        if off + 9 <= TS_PKT_LEN:
            payload = bytearray(out[off:])
            pts, dts = read_pts(bytes(payload))
            if pts is not None or dts is not None:
                write_pts(
                    payload,
                    pcr_add(pts, offset) if pts is not None else None,
                    pcr_add(dts, offset) if dts is not None else None,
                )
                out[off:] = payload
    return bytes(out)


def make_discontinuity_marker(pid: int, cc: int) -> bytes:
    pkt = bytearray(TS_PKT_LEN)
    pkt[0] = 0x47
    pkt[1] = (pid >> 8) & 0x1F
    pkt[2] = pid & 0xFF
    pkt[3] = 0x20 | (cc & 0x0F)
    pkt[4] = 1
    pkt[5] = 0x80
    for i in range(6, TS_PKT_LEN):
        pkt[i] = 0xFF
    return bytes(pkt)


class OutputCC:
    def __init__(self) -> None:
        self._expected: dict[int, int] = {}
        self._last: dict[int, int] = {}

    def feed(self, pid: int, cc: int) -> None:
        self._last[pid] = cc
        self._expected[pid] = (cc + 1) & 0x0F

    def next_cc(self, pid: int) -> int:
        cc = self._expected.get(pid)
        if cc is None:
            return 0
        self._expected[pid] = (cc + 1) & 0x0F
        return cc

    def reset(self) -> None:
        self._expected.clear()
