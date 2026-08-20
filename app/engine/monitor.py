from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class PacketMeta:
    pid: int
    pusi: int
    afc: int
    cc: int
    tei: int
    adapt_len: int
    pcr_base: int | None
    pcr_ext: int | None
    arrival: float


class StreamStats:
    def __init__(self, timeout: float = 3.0) -> None:
        self.timeout = timeout
        self._lock = threading.Lock()
        self.pkt_count = 0
        self.byte_count = 0
        self.cc_errors = 0
        self.last_packet_time = 0.0
        self._window: list[tuple[float, int]] = []
        self.last_pcr: int | None = None
        self.pcr_jumps = 0

    def record(self, pkt_count: int, byte_count: int, cc_error: bool) -> None:
        now = time.monotonic()
        with self._lock:
            self.pkt_count += pkt_count
            self.byte_count += byte_count
            if cc_error:
                self.cc_errors += 1
            self.last_packet_time = now
            self._window.append((now, byte_count))
            cutoff = now - 2.0
            while self._window and self._window[0][0] < cutoff:
                self._window.pop(0)

    def mark_pcr(self, base: int) -> None:
        with self._lock:
            if self.last_pcr is not None and abs(base - self.last_pcr) > 90000:
                self.pcr_jumps += 1
            self.last_pcr = base

    def healthy(self, timeout: float | None = None) -> bool:
        return (time.monotonic() - self.last_packet_time) <= (
            timeout if timeout is not None else self.timeout
        )

    def snapshot(self, timeout: float | None = None) -> dict:
        with self._lock:
            now = time.monotonic()
            win_bytes = sum(b for _, b in self._window)
            return {
                "pkt_count": self.pkt_count,
                "byte_count": self.byte_count,
                "cc_errors": self.cc_errors,
                "pcr_jumps": self.pcr_jumps,
                "bitrate": int(win_bytes * 8 / 2.0),
                "healthy": self.healthy(timeout),
                "age": round(now - self.last_packet_time, 2) if self.last_packet_time else -1.0,
            }
