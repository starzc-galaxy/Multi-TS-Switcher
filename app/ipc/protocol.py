from __future__ import annotations

import json

CMD_START = "start"
CMD_STOP = "stop"
CMD_PAUSE = "pause"
CMD_RESUME = "resume"
CMD_NEXT = "next"
CMD_PREV = "prev"
CMD_FORCE = "force"
CMD_UPDATE_CONFIG = "update_config"
CMD_SET_PREVIEW = "set_preview"
CMD_QUERY = "query"


def make_command(cmd: str, **kw) -> dict:
    return {"type": "cmd", "cmd": cmd, **kw}


def make_status(group_id: int, state: dict) -> dict:
    return {"type": "status", "group_id": group_id, "state": state}


def make_event(group_id: int, event: str, detail: dict | None = None) -> dict:
    return {"type": "event", "group_id": group_id, "event": event, "detail": detail or {}}


def make_frame_ready(idx: int, width: int, height: int) -> dict:
    return {"type": "frame", "idx": idx, "width": width, "height": height}


def encode_message(msg: dict) -> bytes:
    return json.dumps(msg, ensure_ascii=False).encode("utf-8")


def parse_message(raw: bytes) -> dict:
    return json.loads(raw.decode("utf-8"))
