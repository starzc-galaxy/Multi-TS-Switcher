from __future__ import annotations

import logging
import multiprocessing as mp
import threading
import time
from pathlib import Path

from app.config.models import group_from_dict, group_to_dict
from app.engine.filler import FillerReader
from app.engine.forwarder import Forwarder
from app.engine.monitor import PacketMeta, StreamStats
from app.engine.receiver import UDPReceiver
from app.engine.scheduler import FILLER_ID, RotationScheduler
from app.ipc.protocol import (
    CMD_FORCE,
    CMD_NEXT,
    CMD_PAUSE,
    CMD_PREV,
    CMD_QUERY,
    CMD_RESUME,
    CMD_SET_PREVIEW,
    CMD_START,
    CMD_STOP,
    CMD_UPDATE_CONFIG,
    encode_message,
    make_command,
    make_event,
    make_frame_ready,
    make_status,
    parse_message,
)
from app.engine.ts.packets import parse_adaptation, parse_header
from app.engine.ts.psi import PSITracker


class EngineHandle:
    def __init__(self, process, conn, status_queue, shm):
        self.process = process
        self.conn = conn
        self.status_queue = status_queue
        self.shm = shm


def spawn_engine(group_id: int, config_dict: dict, ctx: mp.context.BaseContext,
                 log_dir: Path, preview_shm_name: str | None = None,
                 preview_size: tuple[int, int] = (480, 270)) -> EngineHandle:
    parent_conn, child_conn = ctx.Pipe(duplex=True)
    status_queue = ctx.Queue(maxsize=512)
    proc = ctx.Process(
        target=engine_main,
        args=(group_id, config_dict, child_conn, status_queue, preview_shm_name,
              preview_size, str(log_dir)),
        name=f"engine-{group_id}",
    )
    proc.daemon = True
    proc.start()
    handle = EngineHandle(proc, parent_conn, status_queue, None)
    handle.conn.send(encode_message(make_command(CMD_START)))
    return handle


def engine_main(group_id: int, config_dict: dict, conn, status_queue,
                preview_shm_name: str | None, preview_size: tuple[int, int],
                log_dir: str) -> None:
    from app.logging_setup import install_crash_hooks, setup_logging

    setup_logging(Path(log_dir), module_names=["app", "engine", "switch", "error"])
    install_crash_hooks(Path(log_dir))
    log = logging.getLogger("engine")
    cfg = group_from_dict(config_dict)
    log.info("engine %s starting: %s sources", group_id, len(cfg.sources))

    stop = threading.Event()
    stats: dict[int, StreamStats] = {}
    receivers: dict[int, UDPReceiver] = {}
    video_pids: dict[int, int] = {}
    filler_reader: FillerReader | None = None

    fw = Forwarder(cfg.output.address, cfg.output.port, cfg.output.multicast,
                   cfg.interface, buffer_ms=300)
    fw.start()
    fw.start_io()
    for sid in [s.id for s in cfg.sources] + [FILLER_ID]:
        fw.register_source(sid)
    fw.set_video_pid_fn(lambda: _target_video_pid())

    def _target_video_pid() -> int | None:
        sid = fw.current_source() or (scheduler.current() if scheduler else None)
        return video_pids.get(sid) if sid is not None else None

    scheduler: RotationScheduler | None = None
    preview: PreviewThreadHolder | None = None

    class PreviewThreadHolder:
        def __init__(self) -> None:
            self._start()

        def feed(self, data: bytes) -> None:
            self.pipe.write(data)

        def restart(self) -> None:
            self.thread.stop()
            self.thread.join(timeout=2)
            self._start()

        def _start(self) -> None:
            from app.engine.preview import BytesPipe, PreviewThread

            self.pipe = BytesPipe()
            self.thread = PreviewThread(
                self.pipe, preview_shm_name, preview_size, 15,
                lambda idx, w, h: status_queue.put(make_frame_ready(idx, w, h)),
            )
            self.thread.start()

        def stop(self) -> None:
            self.thread.stop()

    def make_meta(pkt: bytes) -> PacketMeta | None:
        hdr = parse_header(pkt)
        if hdr is None:
            return None
        adapt = parse_adaptation(pkt, hdr.afc)
        return PacketMeta(
            pid=hdr.pid, pusi=hdr.pusi, afc=hdr.afc, cc=hdr.cc, tei=hdr.tei,
            adapt_len=adapt.length if adapt else 0,
            pcr_base=adapt.pcr_base if adapt else None,
            pcr_ext=adapt.pcr_ext if adapt else None,
            arrival=time.monotonic(),
        )

    def on_packets(source_id: int, pkts: list[bytes], metas: list[PacketMeta]) -> None:
        if source_id not in stats:
            return
        for pkt in pkts:
            hdr = parse_header(pkt)
            if hdr is None:
                continue
            tracker = receivers[source_id].tracker if source_id in receivers else None
            if tracker is not None:
                info = tracker.feed(pkt, hdr.pusi, hdr.pid, pkt[4:])
                if info is not None and info.video_pid is not None:
                    video_pids[source_id] = info.video_pid
        if preview is not None and scheduler is not None and source_id == scheduler.current():
            preview.feed(b"".join(pkts))
        for pkt, m in zip(pkts, metas):
            fw.feed(source_id, pkt, m)

    def start_io() -> None:
        nonlocal filler_reader
        for s in cfg.sources:
            if s.id in receivers:
                continue
            st = StreamStats(timeout=3.0)
            stats[s.id] = st
            rx = UDPReceiver(
                s.id, s.address, s.port, s.multicast, cfg.interface, 188,
                lambda pkts, metas, sid=s.id: on_packets(sid, pkts, metas),
                stop, st,
            )
            receivers[s.id] = rx
            rx.start()
        if cfg.filler_path and filler_reader is None:
            def filler_cb(pkts: list[bytes]) -> None:
                for pkt in pkts:
                    m = make_meta(pkt)
                    if m is None:
                        continue
                    fw.feed(FILLER_ID, pkt, m)

            filler_reader = FillerReader(cfg.filler_path, filler_cb, stop)
            filler_reader.start()

    def stop_io() -> None:
        for sid, rx in list(receivers.items()):
            rx.stop.set()
            rx.join(timeout=2)
        receivers.clear()
        stats.clear()

    def apply_decision(d) -> None:
        if d.mode == "hold":
            return
        target_pid = lambda sid=d.target: video_pids.get(sid)  # noqa: E731
        fw.request_switch(d.target, target_pid, d.mode)
        if preview is not None:
            preview.restart()
        status_queue.put(make_event(group_id, "switch", {"target": d.target, "mode": d.mode}))
        publish_status()

    def publish_status() -> None:
        if scheduler is None:
            return
        snap = {sid: st.snapshot() for sid, st in stats.items()}
        status_queue.put(
            make_status(
                group_id,
                {
                    "current": scheduler.current(),
                    "countdown": round(scheduler.seconds_until_next(), 1),
                    "paused": scheduler.paused,
                    "sources": snap,
                    "fw": fw.stats(),
                },
            )
        )

    def handle_command(msg: dict) -> None:
        nonlocal cfg, preview
        cmd = msg.get("cmd")
        if cmd == CMD_START:
            start_io()
            if scheduler is None:
                rebuild_scheduler()
            if preview_shm_name and preview is None:
                preview = PreviewThreadHolder()
            fw.request_switch(scheduler.current() or FILLER_ID,
                              lambda: _target_video_pid(), "emergency")
            publish_status()
        elif cmd == CMD_STOP:
            stop.set()
        elif cmd == CMD_PAUSE:
            scheduler.pause()
        elif cmd == CMD_RESUME:
            scheduler.resume()
        elif cmd == CMD_NEXT:
            apply_decision(scheduler.next_manual())
        elif cmd == CMD_PREV:
            apply_decision(scheduler.prev_manual())
        elif cmd == CMD_FORCE:
            apply_decision(scheduler.force(int(msg.get("source_id", -1))))
        elif cmd == CMD_SET_PREVIEW:
            if msg.get("on"):
                if preview is None and preview_shm_name:
                    preview = PreviewThreadHolder()
            else:
                if preview is not None:
                    preview.stop()
                    preview = None
        elif cmd == CMD_UPDATE_CONFIG:
            stop_io()
            cfg = group_from_dict(msg["config"])
            fw.update_output(cfg.output.address, cfg.output.port, cfg.output.multicast)
            rebuild_scheduler()
            start_io()
            fw.request_switch(scheduler.current() or FILLER_ID,
                              lambda: _target_video_pid(), "emergency")
            log.info("engine %s config updated", group_id)
        elif cmd == CMD_QUERY:
            publish_status()

    def rebuild_scheduler() -> None:
        nonlocal scheduler
        scheduler = RotationScheduler([s.id for s in cfg.sources], cfg.interval_seconds)
        for sid, st in stats.items():
            scheduler.set_health(sid, st.healthy())
        scheduler.set_health(FILLER_ID, True)

    last_status = 0.0
    initial_switch_done = False
    try:
        while not stop.is_set():
            if conn.poll(0.1):
                try:
                    raw = conn.recv()
                except (EOFError, OSError):
                    break
                handle_command(parse_message(raw))
            if scheduler is not None:
                for sid, st in stats.items():
                    scheduler.set_health(sid, st.healthy())
                if not initial_switch_done:
                    if fw.current_source() is None:
                        fw.request_switch(scheduler.current() or FILLER_ID,
                                          lambda: _target_video_pid(), "emergency")
                        time.sleep(0.3)
                    else:
                        initial_switch_done = True
                if not scheduler.paused:
                    apply_decision(scheduler.tick())
            now = time.monotonic()
            if now - last_status >= 1.0:
                last_status = now
                publish_status()
    finally:
        stop.set()
        fw.stop_event.set()
        if preview is not None:
            preview.stop()
        log.info("engine %s exiting", group_id)
