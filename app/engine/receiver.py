from __future__ import annotations

import socket
import threading
import time

from app.engine.monitor import PacketMeta, StreamStats
from app.engine.ts.packets import SYNC, TS_PKT_LEN, parse_adaptation, parse_header
from app.engine.ts.psi import PSITracker


def parse_udp_datagram(data: bytes, ts_size: int = 188) -> list[bytes]:
    if ts_size not in (188, 204):
        ts_size = 188
    out: list[bytes] = []
    i = 0
    n = len(data)
    while i + ts_size <= n:
        if data[i] != SYNC:
            i += 1
            continue
        out.append(data[i : i + 188])
        i += ts_size
    return out


class UDPReceiver(threading.Thread):
    def __init__(self, source_id: int, host: str, port: int, multicast: bool,
                 interface: str, ts_size: int, on_packets, stop: threading.Event,
                 stats: StreamStats) -> None:
        super().__init__(name=f"rx-{source_id}", daemon=True)
        self.source_id = source_id
        self.host = host
        self.port = port
        self.multicast = multicast
        self.interface = interface
        self.ts_size = ts_size
        self.on_packets = on_packets
        self.stop = stop
        self.stats = stats
        self.tracker = PSITracker()
        self._sock: socket.socket | None = None

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        if self.multicast:
            # Windows 上绑定组地址可让多个同端口 socket 互不抢包；失败则回退 0.0.0.0
            try:
                sock.bind((self.host, self.port))
            except OSError:
                sock.bind(("0.0.0.0", self.port))
        else:
            sock.bind((self.host, self.port))
        if self.multicast:
            iface = socket.inet_aton(self.interface) if self.interface else socket.inet_aton("0.0.0.0")
            mreq = socket.inet_aton(self.host) + iface
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(0.2)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
        self._sock = sock
        try:
            while not self.stop.is_set():
                try:
                    data, _addr = sock.recvfrom(65536)
                except socket.timeout:
                    continue
                pkts = parse_udp_datagram(data, self.ts_size)
                if not pkts:
                    continue
                metas: list[PacketMeta] = []
                for pkt in pkts:
                    hdr = parse_header(pkt)
                    if hdr is None:
                        continue
                    adapt = parse_adaptation(pkt, hdr.afc)
                    if adapt is not None and adapt.pcr_base is not None:
                        self.stats.mark_pcr(adapt.pcr_base)
                    self.tracker.feed(pkt, hdr.pusi, hdr.pid, pkt[4:])
                    metas.append(
                        PacketMeta(
                            pid=hdr.pid,
                            pusi=hdr.pusi,
                            afc=hdr.afc,
                            cc=hdr.cc,
                            tei=hdr.tei,
                            adapt_len=adapt.length if adapt else 0,
                            pcr_base=adapt.pcr_base if adapt else None,
                            pcr_ext=adapt.pcr_ext if adapt else None,
                            arrival=time.monotonic(),
                        )
                    )
                self.stats.record(len(metas), len(data), cc_error=False)
                self.on_packets(pkts, metas)
        finally:
            try:
                sock.close()
            except OSError:
                pass
