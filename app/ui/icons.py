from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QIcon

from app.paths import base_dir

_CANDIDATES = [
    Path(__file__).resolve().parent.parent.parent / "assets" / "icons",
    Path("assets") / "icons",
    base_dir() / "assets" / "icons",
]


def icon_path(name: str) -> Path:
    for base in _CANDIDATES:
        p = base / f"{name}.svg"
        if p.exists():
            return p
    return _CANDIDATES[0] / f"{name}.svg"


def load_icon(name: str) -> QIcon:
    p = icon_path(name)
    return QIcon(str(p)) if p.exists() else QIcon()
