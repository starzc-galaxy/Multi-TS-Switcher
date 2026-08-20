from app.ipc.protocol import CMD_FORCE, encode_message, make_command, make_status, parse_message


def test_command_roundtrip():
    raw = encode_message(make_command(CMD_FORCE, source_id=3))
    msg = parse_message(raw)
    assert msg["cmd"] == CMD_FORCE and msg["source_id"] == 3


def test_status_has_required_keys():
    st = make_status(2, {"current": 1, "countdown": 9.5})
    assert st["type"] == "status" and st["group_id"] == 2
