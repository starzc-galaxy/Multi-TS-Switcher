"""生成垫片 TS：5 秒黑场 + 静音，输出到 assets/filler.ts（依赖 PyAV）。"""

import sys
from fractions import Fraction
from pathlib import Path

import av


def generate(out_path: Path, seconds: int = 5) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out = av.open(str(out_path), "w", format="mpegts")
    v = out.add_stream("mpeg2video", rate=25)
    v.width, v.height, v.pix_fmt = 320, 180, "yuv420p"
    v.bit_rate = 800_000
    v.gop_size = 12
    v.time_base = Fraction(1, 25)
    a = out.add_stream("mp2", rate=48000)
    a.layout = "mono"
    a.bit_rate = 64_000
    a.time_base = Fraction(1, 48000)
    for i in range(25 * seconds):
        frame = av.VideoFrame(320, 180, "yuv420p")
        for p in frame.planes:
            p.update(b"\x00" * p.buffer_size)
        frame.pts = i
        for packet in v.encode(frame):
            out.mux(packet)
        audio = av.AudioFrame(format="s16", layout="mono", samples=960)
        audio.sample_rate = 48000
        audio.pts = i * 960
        for p in audio.planes:
            p.update(b"\x00" * p.buffer_size)
        for packet in a.encode(audio):
            out.mux(packet)
    for packet in v.encode():
        out.mux(packet)
    for packet in a.encode():
        out.mux(packet)
    out.close()
    print(f"filler written: {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    generate(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("assets/filler.ts"))
