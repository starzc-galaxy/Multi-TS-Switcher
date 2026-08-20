from __future__ import annotations

from app.engine.ts.packets import TS_PKT_LEN


def _ts_field(value: int) -> bytes:
    b = bytearray(5)
    b[0] = 0x21 | (((value >> 30) & 0x07) << 1)
    b[1] = (value >> 22) & 0xFF
    b[2] = (((value >> 15) & 0x7F) << 1) | 0x01
    b[3] = (value >> 7) & 0xFF
    b[4] = ((value & 0x7F) << 1) | 0x01
    return bytes(b)


class SyntheticTS:
    """生成可解析的合成 TS（供测试与回环集成）。不保证可解码，只保证语法有效。"""

    def __init__(self, video_pid: int = 0x101, pcr_pid: int = 0x101, packets_per_sec: int = 1500) -> None:
        self.video_pid = video_pid
        self.pcr_pid = pcr_pid
        self.pps = packets_per_sec
        self._cc: dict[int, int] = {}
        self._seq = 0

    def packet(self, pid: int, pusi: bool = False, payload: bytes | None = None,
               afc: int = 1, adapt_flags: int = 0, pcr_base: int | None = None,
               pcr_ext: int = 0) -> bytes:
        pkt = bytearray(TS_PKT_LEN)
        pkt[0] = 0x47
        pkt[1] = ((pid >> 8) & 0x1F) | ((1 if pusi else 0) << 6)
        pkt[2] = pid & 0xFF
        cc = self._cc.get(pid, 0)
        self._cc[pid] = (cc + 1) & 0x0F
        pkt[3] = (afc << 4) | cc
        off = 4
        if afc in (2, 3):
            if pcr_base is not None:
                pkt[4] = 7
                pkt[5] = 0x10 | adapt_flags
                b = bytearray(6)
                b[0] = (pcr_base >> 25) & 0xFF
                b[1] = (pcr_base >> 17) & 0xFF
                b[2] = (pcr_base >> 9) & 0xFF
                b[3] = (pcr_base >> 1) & 0xFF
                b[4] = ((pcr_base & 1) << 7) | ((pcr_ext >> 8) & 1)
                b[5] = pcr_ext & 0xFF
                pkt[6:12] = b
                off = 12
            else:
                pkt[4] = 0
                off = 5
        if payload and afc in (1, 3):
            if off + len(payload) > TS_PKT_LEN:
                payload = payload[: TS_PKT_LEN - off]
            pkt[off : off + len(payload)] = payload
        return bytes(pkt)

    def make_psi(self) -> list[bytes]:
        pmt_payload = bytearray()
        pmt_payload += bytes([0xE1, self.pcr_pid & 0xFF])
        pmt_payload += bytes([0xF0, 0x00])
        pmt_payload += bytes([0x1B, 0xE1, self.video_pid & 0xFF, 0xF0, 0x00])
        pmt_sec = (
            bytes([0x02, 0xB0, len(pmt_payload) + 9])
            + bytes([0x00, 0x01, 0xC1, 0x00, 0x00])
            + bytes(pmt_payload)
        )
        pat_payload = bytes([0x00, 0x01, 0xE0, 0x10])
        pat_sec = (
            bytes([0x00, 0xB0, len(pat_payload) + 9])
            + bytes([0x00, 0x01, 0xC1, 0x00, 0x00])
            + bytes(pat_payload)
        )
        return [
            self.packet(0, pusi=True, payload=b"\x00" + pat_sec),
            self.packet(0x10, pusi=True, payload=b"\x00" + pmt_sec),
        ]

    def take(self, n: int) -> list[bytes]:
        out = self.make_psi()
        fps = 25
        pkt_per_frame = max(1, self.pps // fps)
        for _ in range(n):
            if self._seq % pkt_per_frame == 0:
                pcr = (self._seq // pkt_per_frame) * 90000
                pts = pcr
                pes = b"\x00\x00\x01\xE0" + b"\x00\x00" + b"\xA0\x05" + _ts_field(pts)
                pes += b"\x00\x00\x01\x67\x42\x00\x1E" + b"\x00" * 60
                out.append(self.packet(self.video_pid, pusi=True, payload=pes, afc=3, pcr_base=pcr))
            else:
                out.append(self.packet(self.video_pid, afc=3, pcr_base=self._seq * 900))
            self._seq += 1
        return out
