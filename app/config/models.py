from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class SourceConfig:
    id: int
    name: str
    address: str
    port: int
    multicast: bool = True
    enabled: bool = True
    note: str = ""


@dataclass
class OutputConfig:
    address: str
    port: int
    multicast: bool = True


@dataclass
class GroupConfig:
    id: int
    name: str
    note: str
    interval_seconds: float
    output: OutputConfig
    interface: str
    filler_path: str
    sources: list[SourceConfig] = field(default_factory=list)
    enabled: bool = True


@dataclass
class AppConfig:
    interface: str = ""
    data_timeout_seconds: float = 3.0
    buffer_ms: int = 300
    preview_enabled: bool = True
    preview_fps: int = 15
    log_retain_days: int = 7
    ts_packet_size: int = 188


def source_to_dict(s: SourceConfig) -> dict:
    return asdict(s)


def source_from_dict(d: dict) -> SourceConfig:
    keys = ("id", "name", "address", "port", "multicast", "enabled", "note")
    return SourceConfig(**{k: d[k] for k in keys if k in d})


def group_to_dict(g: GroupConfig) -> dict:
    return asdict(g)


def group_from_dict(d: dict) -> GroupConfig:
    return GroupConfig(
        id=int(d.get("id", 1)),
        name=d.get("name", ""),
        note=d.get("note", ""),
        interval_seconds=float(d.get("interval_seconds", 20.0)),
        output=OutputConfig(**d.get("output", {"address": "230.0.0.1", "port": 7000})),
        interface=d.get("interface", ""),
        filler_path=d.get("filler_path", ""),
        sources=[source_from_dict(x) for x in d.get("sources", [])],
        enabled=bool(d.get("enabled", True)),
    )
