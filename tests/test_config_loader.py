from pathlib import Path

from app.config.loader import load_groups, save_groups, validate_groups
from app.config.models import GroupConfig, OutputConfig, SourceConfig


def test_save_load_roundtrip(tmp_path: Path):
    groups = [
        GroupConfig(
            id=1,
            name="G1",
            note="主频道",
            interval_seconds=20.0,
            output=OutputConfig("230.1.1.1", 7000),
            interface="",
            filler_path="assets/filler.ts",
            sources=[SourceConfig(1, "源A", "229.1.1.1", 7000, True, note="摄像A")],
            enabled=True,
        )
    ]
    p = tmp_path / "groups.json"
    save_groups(p, groups)
    loaded = load_groups(p)
    assert loaded[0].name == "G1" and loaded[0].sources[0].note == "摄像A"


def test_validate_max_9():
    groups = [
        GroupConfig(
            id=i,
            name=str(i),
            note="",
            interval_seconds=20.0,
            output=OutputConfig("1.1.1.1", 7000),
            interface="",
            filler_path="",
            sources=[],
            enabled=True,
        )
        for i in range(1, 11)
    ]
    errs = validate_groups(groups)
    assert any("9" in e for e in errs)
