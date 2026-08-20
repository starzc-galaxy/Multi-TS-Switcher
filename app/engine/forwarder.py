from __future__ import annotations

import queue
import socket
import struct
import threading
import time

from app.engine.monitor import PacketMeta
from app.engine.ts.packets import parse_adaptation, parse_header
from app.engine.ts.rebase import (
    OutputCC,
    PCR_MASK,
    make_discontinuity_marker,
    pcr_add,
    rebase_ts_packet,
)
from app.engine.ts.raps import is_rap

class Forwarder(threading.Thread):
    def __init__(self, output_host: str, output_port: int, multicast: bool, interface: str,
                 buffer_ms: int = 300, now_fn=time.monotonic, send_fn=None) -> None:
        super().__init__(name="forwarder", daemon=True)
        self.output_host = output_host
        self.output_port = output_port
        self.multicast = multicast
        self.interface = interface
        self.buffer_ms = max(50, buffer_ms)
        self.now_fn = now_fn
        self.send_fn = send_fn
        self.stop_event = threading.Event()
        self._queues: dict[int, queue.Queue] = {}
        self._lock = threading.Lock()
        self._pending: tuple[int, str] | None = None
        self._video_pid_fn = lambda: None
        self._current: int | None = None
        self._sock: socket.socket | None = None
        self._out_cc = OutputCC()
        self._out_pcr64: int | None = None
        self._out_time: float | None = None
        self._first_pcr64: int | None = None
        self._start_epoch: float | None = None
        self._steady_offset = 0
        self.packets_sent = 0
        self.switch_count = 0

    def start_io(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self.multicast:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack("b", 8))
            if self.interface:
                sock.setsockopt(
                    socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.interface)
                )
        self._sock = sock
        self._start_epoch = self.now_fn()

    def set_video_pid_fn(self, fn) -> None:
        self._video_pid_fn = fn

    def register_source(self, source_id: int) -> None:
        self._queues.setdefault(source_id, queue.Queue(maxsize=4096))

    def current_source(self) -> int | None:
        return self._current

    def feed(self, source_id: int, pkt: bytes, meta: PacketMeta | None) -> None:
        q = self._queues.get(source_id)
        if q is None:
            return
        try:
            q.put_nowait((pkt, meta))
        except queue.Full:
            pass

    def request_switch(self, source_id: int, video_pid_fn, mode: str = "normal") -> None:
        self.register_source(source_id)
        with self._lock:
            self._video_pid_fn = video_pid_fn
            self._pending = (source_id, mode)

    def update_output(self, host: str, port: int, multicast: bool) -> None:
        with self._lock:
            self.output_host, self.output_port, self.multicast = host, port, multicast

    def _send(self, pkt: bytes) -> None:
        if self.send_fn is not None:
            self.send_fn(pkt)
        elif self._sock is not None:
            self._sock.sendto(pkt, (self.output_host, self.output_port))
        self.packets_sent += 1

    def _expected_pcr64(self) -> int:
        if self._out_pcr64 is None or self._out_time is None:
            return 0
        delta = int((self.now_fn() - self._out_time) * 27_000_000)
        return self._out_pcr64 + delta

    def _pcr64(self, meta: PacketMeta | None) -> int | None:
        if meta is None or meta.pcr_base is None:
            return None
        return meta.pcr_base * 300 + (meta.pcr_ext or 0)

    def _maybe_send_packet(self, pkt: bytes, meta: PacketMeta | None) -> bool:
        pcr64 = self._pcr64(meta)
        if pcr64 is not None and self._out_pcr64 is not None:
            if pcr64 < self._out_pcr64 - 27_000_000:
                # 源 PCR 回跳（如测试源循环/编码器重置）：重新对齐保持输出连续
                self._steady_offset = (
                    (self._out_pcr64 // 300) - (pcr64 // 300)
                ) & PCR_MASK
                self._out_cc.reset()
                marker = make_discontinuity_marker(meta.pid, 0)
                self._send(marker)
        if pcr64 is not None and self._steady_offset:
            pkt = rebase_ts_packet(pkt, self._steady_offset, self._video_pid_fn())
            pcr64 = ((pcr64 // 300) + self._steady_offset) * 300 + (pcr64 % 300)
        if self._first_pcr64 is None and pcr64 is not None:
            self._first_pcr64 = pcr64
            self._start_epoch = self.now_fn()
        if pcr64 is not None and self._first_pcr64 is not None and self._start_epoch is not None:
            target = self._start_epoch + (pcr64 - self._first_pcr64) / 27_000_000
            delay = target - self.now_fn()
            if delay > 0 and self.send_fn is None:
                time.sleep(min(delay, 0.1))
        self._send(pkt)
        if pcr64 is not None:
            self._out_pcr64 = pcr64
            self._out_time = self.now_fn()
        return True

    def run(self) -> None:
        while not self.stop_event.is_set():
            with self._lock:
                pending = self._pending
                self._pending = None
            if pending is not None:
                target, mode = pending
                self._handle_switch_request(target, mode)
                continue
            if self._current is None:
                time.sleep(0.01)
                continue
            q = self._queues.get(self._current)
            if q is None:
                time.sleep(0.01)
                continue
            try:
                pkt, meta = q.get_nowait()
            except queue.Empty:
                time.sleep(0.005)
                continue
            if meta is not None:
                self._out_cc.feed(meta.pid, meta.cc)
            self._maybe_send_packet(pkt, meta)

    def _handle_switch_request(self, target: int, mode: str) -> None:
        q = self._queues.get(target)
        if q is None:
            return
        video_pid = self._video_pid_fn()
        if mode == "normal":
            deadline = self.now_fn() + 30.0
            while not self.stop_event.is_set() and self.now_fn() < deadline:
                if self._current is not None:
                    cq = self._queues.get(self._current)
                    if cq is not None:
                        try:
                            pkt, meta = cq.get_nowait()
                            if meta is not None:
                                self._out_cc.feed(meta.pid, meta.cc)
                            self._maybe_send_packet(pkt, meta)
                        except queue.Empty:
                            pass
                try:
                    pkt, meta = q.get_nowait()
                except queue.Empty:
                    time.sleep(0.005)
                    continue
                if meta is None:
                    continue
                hdr = parse_header(pkt)
                adapt = parse_adaptation(pkt, hdr.afc)
                if is_rap(pkt, hdr, adapt, video_pid):
                    self._perform_switch(target, pkt, meta)
                    return
        else:
            try:
                pkt, meta = q.get_nowait()
            except queue.Empty:
                time.sleep(0.005)
                return
            self._perform_switch(target, pkt, meta)

    def _perform_switch(self, target: int, first_pkt: bytes, first_meta: PacketMeta) -> None:
        expected = self._expected_pcr64()
        src_pcr = self._pcr64(first_meta)
        self._steady_offset = (
            (expected // 300) - (src_pcr // 300)
        ) & PCR_MASK if src_pcr is not None else 0
        self._out_cc.reset()
        marker = make_discontinuity_marker(first_meta.pid, 0)
        self._maybe_send_packet(
            marker,
            PacketMeta(pid=first_meta.pid, pusi=0, afc=2, cc=0, tei=0,
                       adapt_len=1, pcr_base=None, pcr_ext=None, arrival=self.now_fn()),
        )
        self._out_cc.feed(first_meta.pid, first_meta.cc)
        self._maybe_send_packet(first_pkt, first_meta)
        self._current = target
        self.switch_count += 1

    def stats(self) -> dict:
        return {"packets_sent": self.packets_sent, "switches": self.switch_count}
