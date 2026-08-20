from __future__ import annotations

from app.engine.ts.packets import Adaptation, PacketHeader

SPS_PATTERNS = (b"\x00\x00\x00\x01\x67", b"\x00\x00\x01\x67")
HEVC_RAP_PATTERNS = (b"\x00\x00\x01\x40\x01", b"\x00\x00\x00\x01\x40\x01")
MPEG_GOP_PATTERNS = (b"\x00\x00\x01\xB8",)


def payload_offset(pkt: bytes, afc: int, adaptation_length: int) -> int:
    return 4 + (1 + adaptation_length if afc in (2, 3) else 0)


def contains_nal_start(payload: bytes, patterns: tuple[bytes, ...]) -> bool:
    for pat in patterns:
        if pat in payload:
            return True
    return False


def is_rap(pkt: bytes, hdr: PacketHeader, adapt: Adaptation | None, video_pid: int | None) -> bool:
    if adapt is not None and adapt.random_access:
        return True
    if hdr.pid != video_pid or not hdr.pusi:
        return False
    if hdr.afc == 0 or hdr.afc == 2:
        return False
    alen = adapt.length if adapt is not None else 0
    off = payload_offset(pkt, hdr.afc, alen)
    payload = pkt[off:]
    return (
        contains_nal_start(payload, SPS_PATTERNS)
        or contains_nal_start(payload, HEVC_RAP_PATTERNS)
        or contains_nal_start(payload, MPEG_GOP_PATTERNS)
    )
