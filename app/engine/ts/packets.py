from __future__ import annotations

from dataclasses import dataclass

TS_PKT_LEN = 188
SYNC = 0x47


@dataclass
class PacketHeader:
    tei: int
    pusi: int
    pid: int
    scrambling: int
    afc: int
    cc: int


@dataclass
class Adaptation:
    length: int
    random_access: bool
    discontinuity: bool
    pcr_base: int | None
    pcr_ext: int | None


def parse_header(pkt: bytes) -> PacketHeader | None:
    if len(pkt) < 4 or pkt[0] != SYNC:
        return None
    return PacketHeader(
        tei=pkt[1] >> 7,
        pusi=(pkt[1] >> 6) & 1,
        pid=((pkt[1] & 0x1F) << 8) | pkt[2],
        scrambling=(pkt[3] >> 6) & 3,
        afc=(pkt[3] >> 4) & 3,
        cc=pkt[3] & 0x0F,
    )


def parse_adaptation(pkt: bytes, afc: int) -> Adaptation | None:
    if afc not in (2, 3) or len(pkt) < 5:
        return None
    pos = 4
    length = pkt[pos]
    pos += 1
    if length == 0 or pos + length > TS_PKT_LEN:
        return None
    flags = pkt[pos]
    random_access = bool(flags & 0x40)
    discontinuity = bool(flags & 0x80)
    pcr_base = pcr_ext = None
    if flags & 0x10 and length >= 7 and pos + 7 <= TS_PKT_LEN:
        b = pkt[pos + 1 : pos + 7]
        pcr_base = (b[0] << 25) | (b[1] << 17) | (b[2] << 9) | (b[3] << 1) | (b[4] >> 7)
        pcr_ext = ((b[4] & 0x01) << 8) | b[5]
    return Adaptation(
        length=length,
        random_access=random_access,
        discontinuity=discontinuity,
        pcr_base=pcr_base,
        pcr_ext=pcr_ext,
    )


class CCWatcher:
    def __init__(self) -> None:
        self._expected: dict[int, int] = {}
        self._errors: dict[int, int] = {}

    def feed(self, pid: int, cc: int, tei: int) -> bool:
        if tei:
            return False
        exp = self._expected.get(pid)
        if exp is None:
            self._expected[pid] = (cc + 1) & 0x0F
            return False
        if cc != exp:
            self._errors[pid] = self._errors.get(pid, 0) + 1
        self._expected[pid] = (cc + 1) & 0x0F
        return cc != exp

    def errors(self) -> dict[int, int]:
        return dict(self._errors)

    def reset_all(self) -> None:
        self._expected.clear()

    def reset_pid(self, pid: int) -> None:
        self._expected.pop(pid, None)
