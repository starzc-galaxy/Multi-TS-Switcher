"""生成 9 路彩色测试 TS 源（160x90 MPEG2，带移动竖条，5 秒循环）。"""

import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import av

COLORS = [
    ("1", (76, 84, 255), "红"),
    ("2", (150, 44, 21), "绿"),
    ("3", (29, 255, 107), "蓝"),
    ("4", (226, 150, 16), "黄"),
    ("5", (170, 255, 79), "青"),
    ("6", (106, 202, 222), "品红"),
    ("7", (235, 128, 128), "白"),
    ("8", (128, 128, 128), "灰"),
    ("9", (16, 128, 128), "黑"),
]


def _solid_frame(w: int, h: int, yuv: tuple[int, int, int], bar_x: int) -> av.VideoFrame:
    y, u, v = yuv
    yarr = bytearray([y] * (w * h))
    for row in range(h):
        off = row * w + bar_x
        yarr[off : off + 8] = b"\xeb" * 8
    uarr = bytes([u] * ((w // 2) * (h // 2)))
    varr = bytes([v] * ((w // 2) * (h // 2)))
    frame = av.VideoFrame(w, h, "yuv420p")
    frame.planes[0].update(bytes(yarr))
    frame.planes[1].update(uarr)
    frame.planes[2].update(varr)
    return frame


def generate(out_dir: Path, seconds: int = 5, width: int = 160, height: int = 90,
             on_progress=None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for num, yuv, label in COLORS:
        path = out_dir / f"source_{num}.ts"
        if path.exists() and path.stat().st_size > 1000:
            written.append(path)
            if on_progress:
                on_progress(num, label, "已存在")
            continue
        out = av.open(str(path), "w", format="mpegts")
        v = out.add_stream("mpeg2video", rate=25)
        v.width, v.height, v.pix_fmt = width, height, "yuv420p"
        v.bit_rate = 500_000
        v.gop_size = 12
        v.time_base = Fraction(1, 25)
        for i in range(25 * seconds):
            bar_x = (i * 6) % max(1, width - 12)
            frame = _solid_frame(width, height, yuv, bar_x)
            frame.pts = i
            for packet in v.encode(frame):
                out.mux(packet)
        for packet in v.encode():
            out.mux(packet)
        out.close()
        written.append(path)
        print(f"source_{num} ({label}) -> {path} ({path.stat().st_size} bytes)")
        if on_progress:
            on_progress(num, label, "已生成")
    return written


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("test_sources")
    generate(target)
