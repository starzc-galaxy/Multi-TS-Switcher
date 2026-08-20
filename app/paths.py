from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def exe_dir() -> Path:
    """可写数据目录：冻结打包时取 exe 所在目录，源码运行时取项目根目录。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def base_dir() -> Path:
    """只读资源目录：冻结打包时取 PyInstaller 解包目录（_internal），源码运行时取项目根目录。"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def config_dir() -> Path:
    return exe_dir() / "config"


def log_dir() -> Path:
    return exe_dir() / "logs"


def assets_dir() -> Path:
    return base_dir() / "assets"
