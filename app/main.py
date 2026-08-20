import multiprocessing
import os
import shutil
import sys


def main() -> None:
    multiprocessing.freeze_support()
    verbose = os.environ.get("MTS_VERBOSE") == "1"
    if verbose:
        print("mts: starting", flush=True)
    from PyQt6.QtWidgets import QApplication

    from app.config.loader import load_app_config
    from app.debuglog import install_excepthook
    from app.logging_setup import install_crash_hooks, setup_logging
    from app.paths import base_dir, config_dir, is_frozen, log_dir
    from app.ui.license_dialog import ensure_license
    from app.ui.main_window import MainWindow
    from app.ui.styles import QSS_LIGHT
    from app.ui.icons import load_icon

    setup_logging(log_dir(), module_names=["app", "engine", "switch", "error", "ui"])
    install_crash_hooks(log_dir())
    install_excepthook()
    if verbose:
        print("mts: logging ok", flush=True)

    cfg_dir = config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    if is_frozen() and not (cfg_dir / "groups.json").exists():
        bundled_cfg = base_dir() / "config"
        for fname in ("app.json", "groups.json"):
            src = bundled_cfg / fname
            if src.exists():
                shutil.copy2(src, cfg_dir / fname)

    app = QApplication(sys.argv)
    app.setApplicationName("Multi-TS Switcher")
    app.setWindowIcon(load_icon("radio"))
    app.setStyleSheet(QSS_LIGHT)
    if verbose:
        print("mts: QApplication ok", flush=True)

    allowed = ensure_license()
    if allowed is None:
        return 1
    if verbose:
        print(f"mts: license ok ({allowed} groups)", flush=True)

    app_config = load_app_config(config_dir() / "app.json")
    if verbose:
        print("mts: app config ok", flush=True)
    win = MainWindow(allowed, app_config)
    win.show()
    if verbose:
        print("mts: window shown", flush=True)
    if os.environ.get("MTS_AUTOSTART") == "1":
        if verbose:
            print("mts: autostart engines", flush=True)
        win._start_all()
        if verbose:
            print(f"mts: engines running: {win.supervisor.running_group_ids()}", flush=True)
    if os.environ.get("MTS_TEST_LICENSE") == "1":
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(2000, win.license_action.trigger)
    autoquit = os.environ.get("MTS_AUTOQUIT_MS")
    if autoquit:
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(int(autoquit), app.quit)
    if verbose:
        print("mts: entering event loop", flush=True)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
