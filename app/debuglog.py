"""打包调试辅助：窗口版程序里 stderr 不可见，异常与关键路径写本地日志。"""

from __future__ import annotations

import sys
import threading
import traceback
from pathlib import Path


def log_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(".")


def debug_log(text: str) -> None:
    try:
        with (log_dir() / "dialog_debug.log").open("a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    except Exception:
        pass


def install_excepthook() -> None:
    def hook(exc_type, exc_value, exc_tb):
        try:
            with (log_dir() / "startup_error.log").open("a", encoding="utf-8") as fh:
                fh.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        except Exception:
            pass

    sys.excepthook = hook
    threading.excepthook = hook
