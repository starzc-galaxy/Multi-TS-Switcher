"""把应用 SVG 图标渲染成多尺寸 .ico（PyQt6 QtSvg + Pillow）。"""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QByteArray, QBuffer, QIODevice
from PyQt6.QtGui import QImage, QGuiApplication, QPainter
from PyQt6.QtSvg import QSvgRenderer

APPS = [
    ("app_multits", "app_multits.ico"),
    ("app_testtool", "app_testtool.ico"),
    ("app_license", "app_license.ico"),
]
SIZES = [16, 24, 32, 48, 64, 128, 256]


def svg_to_png_bytes(svg_path: Path, size: int) -> bytes:
    renderer = QSvgRenderer(str(svg_path))
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba.data())


def build_ico(svg_path: Path, out_path: Path) -> None:
    blobs = [svg_to_png_bytes(svg_path, s) for s in SIZES]
    count = len(SIZES)
    offset = 6 + 16 * count
    entries = []
    for s, png in zip(SIZES, blobs):
        dim = 0 if s == 256 else s
        entries.append(struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset))
        offset += len(png)
    header = struct.pack("<HHH", 0, 1, count)
    out_path.write_bytes(header + b"".join(entries) + b"".join(blobs))
    print(f"{out_path.name}: {out_path.stat().st_size} bytes, sizes={SIZES}")


def main() -> int:
    app = QGuiApplication(sys.argv)
    icons_dir = Path(__file__).resolve().parent.parent / "assets" / "icons"
    for stem, out_name in APPS:
        build_ico(icons_dir / f"{stem}.svg", icons_dir / out_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
