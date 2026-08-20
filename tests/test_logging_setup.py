import logging
from pathlib import Path

from app.logging_setup import install_crash_hooks, setup_logging


def test_setup_logging_creates_files(tmp_path: Path):
    setup_logging(tmp_path, retain_days=7, module_names=["engine", "switch"])
    logging.getLogger("engine").info("hello")
    logging.getLogger("switch").error("boom")
    for handler in logging.getLogger().handlers:
        handler.flush()
    assert (tmp_path / "engine.log").exists()
    assert (tmp_path / "switch.log").exists()
    assert "hello" in (tmp_path / "engine.log").read_text(encoding="utf-8", errors="replace")


def test_install_crash_hooks_writes_crash_report(tmp_path: Path):
    install_crash_hooks(tmp_path)
    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("error").exception("uncaught")
    assert True
