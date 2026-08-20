import atexit
import faulthandler
import logging
import os
import sys
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR: Path | None = None


def _log_dir(log_dir: Path) -> Path:
    global LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    LOG_DIR = log_dir
    return log_dir


def setup_logging(log_dir: Path, retain_days: int = 7, module_names: list[str] | None = None) -> None:
    log_dir = _log_dir(log_dir)
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s")
    for name in (module_names or ["app", "engine", "switch", "error", "ui"]):
        logger = logging.getLogger(name)
        if logger.handlers:
            continue
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(
            log_dir / f"{name}.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=max(1, retain_days),
            encoding="utf-8",
            delay=True,
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.propagate = False


def install_crash_hooks(log_dir: Path | None = None) -> None:
    if log_dir is not None:
        _log_dir(log_dir)
    if LOG_DIR is None:
        return
    crash_file = LOG_DIR / "error.log"

    def _write_crash(text: str) -> None:
        try:
            with crash_file.open("a", encoding="utf-8") as fh:
                fh.write(f"\n===== CRASH {datetime.now().isoformat()} =====\n{text}\n")
        except Exception:
            pass

    def _hook(exc_type, exc_value, exc_tb):
        import traceback

        _write_crash("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))

    def _thread_hook(args):
        import traceback

        _write_crash(
            "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        )

    sys.excepthook = _hook
    threading.excepthook = _thread_hook
    try:
        faulthandler.enable(crash_file.open("a", encoding="utf-8"))
    except Exception:
        pass

    def _atexit():
        logging.getLogger("app").info("process exiting normally")

    atexit.register(_atexit)


def pid_suffix_log_dir(base: Path, name: str) -> Path:
    return base / f"logs_{name}_{os.getpid()}"
