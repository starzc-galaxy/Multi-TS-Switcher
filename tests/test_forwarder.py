import time

from app.engine.forwarder import Forwarder
from app.engine.monitor import PacketMeta
from app.engine.ts.generator import SyntheticTS
from app.engine.ts.packets import parse_adaptation, parse_header


def meta_of(pkt, arrival=None):
    h = parse_header(pkt)
    a = parse_adaptation(pkt, h.afc)
    return PacketMeta(
        pid=h.pid, pusi=h.pusi, afc=h.afc, cc=h.cc, tei=h.tei,
        adapt_len=a.length if a else 0, pcr_base=a.pcr_base if a else None,
        pcr_ext=a.pcr_ext if a else None, arrival=arrival or time.monotonic(),
    )


def run_forwarder(gen, n_packets=400):
    out = []
    fw = Forwarder("127.0.0.1", 7001, False, "", buffer_ms=50, now_fn=time.monotonic, send_fn=out.append)
    fw.start()
    fw.start_io()
    fw.set_video_pid_fn(lambda: gen.video_pid)
    fw.request_switch(1, lambda: gen.video_pid, "normal")
    for i, pkt in enumerate(gen.take(n_packets)):
        fw.feed(1, pkt, meta_of(pkt, arrival=i / gen.pps))
        time.sleep(0.0005)
    fw.stop_event.set()
    fw.join(timeout=3)
    return out, fw


def test_forwarder_sends_and_switches():
    gen1 = SyntheticTS(video_pid=0x101, pcr_pid=0x101)
    out, fw = run_forwarder(gen1)
    assert len(out) > 0
    assert all(p[0] == 0x47 for p in out)
    assert fw.stats()["packets_sent"] == len(out)


def test_forwarder_output_pcr_monotonic_across_reset():
    out = []
    fw = Forwarder("127.0.0.1", 7002, False, "", buffer_ms=50,
                   now_fn=time.monotonic, send_fn=out.append)
    fw.start()
    fw.start_io()
    fw.set_video_pid_fn(lambda: 0x101)
    fw.request_switch(1, lambda: 0x101, "emergency")
    seq = list(range(0, 100_000, 1000)) + [0, 1000, 2000]  # 模拟测试源文件循环回跳(>1s)
    for pcr in seq:
        pkt = bytearray(188)
        pkt[0] = 0x47
        pkt[1] = 0x11
        pkt[2] = 0x01
        pkt[3] = 0x20
        pkt[4] = 7
        pkt[5] = 0x10
        b = bytearray(6)
        b[0] = (pcr >> 25) & 0xFF
        b[1] = (pcr >> 17) & 0xFF
        b[2] = (pcr >> 9) & 0xFF
        b[3] = (pcr >> 1) & 0xFF
        b[4] = (pcr & 1) << 7
        b[5] = 0
        pkt[6:12] = b
        meta = PacketMeta(pid=0x101, pusi=0, afc=2, cc=0, tei=0, adapt_len=7,
                          pcr_base=pcr, pcr_ext=0, arrival=time.monotonic())
        fw.feed(1, bytes(pkt), meta)
        time.sleep(0.0005)
    deadline = time.time() + 3
    while fw.packets_sent < len(seq) and time.time() < deadline:
        time.sleep(0.02)
    fw.stop_event.set()
    fw.join(timeout=3)
    pcrs = []
    for p in out:
        h = parse_header(p)
        if h is None:
            continue
        a = parse_adaptation(p, h.afc)
        if a is not None and a.pcr_base is not None:
            pcrs.append(a.pcr_base)
    assert len(pcrs) > 5
    drops = sum(1 for i in range(1, len(pcrs)) if pcrs[i] < pcrs[i - 1] - 1000)
    assert drops == 0
