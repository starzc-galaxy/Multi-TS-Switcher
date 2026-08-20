from __future__ import annotations

import threading
import time
from pathlib import Path

from app.engine.receiver import parse_udp_datagram
from app.paths import assets_dir


class FillerReader(threading.Thread):
    def __init__(self, path: str, on_packets, stop: threading.Event, ts_size: int = 188) -> None:
        super().__init__(name="filler", daemon=True)
        self.path = Path(path)
        self.on_packets = on_packets
        self.stop = stop
        self.ts_size = ts_size
        self.healthy = self.path.exists()

    def run(self) -> None:
        path = self._resolve_path()
        if not path.exists():
            self.healthy = False
            return
        while not self.stop.is_set():
            try:
                with path.open("rb") as fh:
                    while not self.stop.is_set():
                        chunk = fh.read(self.ts_size * 512)
                        if not chunk:
                            break
                        pkts = parse_udp_datagram(chunk, self.ts_size)
                        if pkts:
                            self.on_packets(pkts)
                        time.sleep(0.002)
            except OSError:
                time.sleep(1.0)

    def _resolve_path(self) -> Path:
        p = Path(self.path)
        if p.is_absolute() or p.exists():
            return p
        cand = assets_dir() / p
        if cand.exists():
            return cand
        return p
