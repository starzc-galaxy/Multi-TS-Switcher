from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from app.config.models import (
    AppConfig,
    GroupConfig,
    OutputConfig,
    SourceConfig,
    group_from_dict,
    group_to_dict,
)

MAX_GROUPS = 9
MAX_SOURCES = 9


def _read_json(path: Path) -> dict | list:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json_atomic(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def default_app_config() -> AppConfig:
    return AppConfig()


def load_app_config(path: Path) -> AppConfig:
    data = _read_json(path)
    cfg = default_app_config()
    if isinstance(data, dict):
        for key in (
            "interface",
            "data_timeout_seconds",
            "buffer_ms",
            "preview_enabled",
            "preview_fps",
            "log_retain_days",
            "ts_packet_size",
        ):
            if key in data:
                setattr(cfg, key, data[key])
    return cfg


def save_app_config(path: Path, cfg: AppConfig) -> None:
    _write_json_atomic(path, cfg.__dict__)


def default_groups() -> list[GroupConfig]:
    return [
        GroupConfig(
            id=1,
            name="组 1",
            note="",
            interval_seconds=20.0,
            output=OutputConfig("230.1.1.1", 7000),
            interface="",
            filler_path="assets/filler.ts",
            sources=[
                SourceConfig(i, f"源 {i}", f"229.1.1.{i}", 7000, True)
                for i in range(1, 6)
            ],
        )
    ]


def load_groups(path: Path) -> list[GroupConfig]:
    data = _read_json(path)
    if not isinstance(data, list) or not data:
        return default_groups()
    return [group_from_dict(d) for d in data if isinstance(d, dict)]


def save_groups(path: Path, groups: list[GroupConfig]) -> None:
    _write_json_atomic(path, [group_to_dict(g) for g in groups])


def validate_groups(groups: list[GroupConfig]) -> list[str]:
    errs: list[str] = []
    if len(groups) > MAX_GROUPS:
        errs.append(f"组数超过上限 {MAX_GROUPS}")
    for g in groups:
        if len(g.sources) > MAX_SOURCES:
            errs.append(f"组 {g.name} 源数超过上限 {MAX_SOURCES}")
        if g.interval_seconds < 1.0:
            errs.append(f"组 {g.name} 轮询间隔需 >= 1 秒")
        if not (0 < g.output.port < 65536):
            errs.append(f"组 {g.name} 输出端口无效")
        for s in g.sources:
            if not (0 < s.port < 65536):
                errs.append(f"组 {g.name} 源 {s.name} 端口无效")
    return errs
