from __future__ import annotations

from dataclasses import dataclass, field

VIDEO_STREAM_TYPES = {0x02, 0x10, 0x1B, 0x24}
PAT_PID = 0


def _section(payload: bytes) -> bytes:
    return payload[1:] if payload and payload[0] == 0 else payload


@dataclass
class StreamInfo:
    stream_type: int
    pid: int


@dataclass
class PSIInfo:
    video_pid: int | None = None
    pcr_pid: int | None = None
    streams: list[StreamInfo] = field(default_factory=list)


def parse_pat(payload: bytes) -> dict[int, int]:
    payload = _section(payload)
    if len(payload) < 4 or payload[0] != 0x00:
        return {}
    data = payload[8:]  # 跳过 table_id+length 与 tsid/version/section_number/last_section
    i, n = 0, len(data)
    out: dict[int, int] = {}
    while i + 4 <= n:
        program = (data[i] << 8) | data[i + 1]
        pmt_pid = ((data[i + 2] & 0x1F) << 8) | data[i + 3]
        if program != 0:
            out[program] = pmt_pid
        i += 4
    return out


def parse_pmt(payload: bytes) -> PSIInfo:
    info = PSIInfo()
    payload = _section(payload)
    if len(payload) < 12 or payload[0] != 0x02:
        return info
    data = payload
    pcr_pid = ((data[8] & 0x1F) << 8) | data[9]
    info.pcr_pid = pcr_pid if pcr_pid != 0x1FFF else None
    prog_info_len = ((data[10] & 0x0F) << 8) | data[11]
    i = 12 + prog_info_len
    while i + 5 <= len(data):
        stream_type = data[i]
        pid = ((data[i + 1] & 0x1F) << 8) | data[i + 2]
        es_info_len = ((data[i + 3] & 0x0F) << 8) | data[i + 4]
        info.streams.append(StreamInfo(stream_type=stream_type, pid=pid))
        if stream_type in VIDEO_STREAM_TYPES and info.video_pid is None:
            info.video_pid = pid
        i += 5 + es_info_len
    return info


class PSITracker:
    def __init__(self) -> None:
        self._pat: dict[int, int] = {}
        self._pmt_pid: int | None = None
        self._psi_info: PSIInfo | None = None
        self._buffer: dict[int, bytearray] = {}

    def feed(self, pkt: bytes, pusi: int, pid: int, payload: bytes) -> PSIInfo | None:
        if pid == PAT_PID and pusi:
            self._pat = parse_pat(payload)
            self._pmt_pid = next(iter(self._pat.values()), None)
            return None
        if pid != self._pmt_pid or not pusi:
            return None
        section = _section(payload)
        if len(section) >= 3:
            section_length = ((section[1] & 0x0F) << 8) | section[2]
            self._buffer[pid] = bytearray(section[: min(len(section), section_length + 3)])
        buf = bytes(self._buffer.get(pid, b""))
        if len(buf) >= 3 and ((buf[1] & 0x0F) << 8 | buf[2]) + 3 <= len(buf):
            self._psi_info = parse_pmt(buf)
            self._buffer[pid] = bytearray()
            return self._psi_info
        return None
