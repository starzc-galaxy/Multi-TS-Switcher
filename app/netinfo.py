from __future__ import annotations

import socket


def list_network_interfaces() -> list[dict]:
    """返回本机网卡列表：[{name, ipv4: [ip,...]}, ...]，仅含带 IPv4 的网卡。"""
    import psutil

    out: list[dict] = []
    for name, addrs in psutil.net_if_addrs().items():
        ipv4 = [a.address for a in addrs if a.family == socket.AF_INET]
        if ipv4:
            out.append({"name": name, "ipv4": ipv4})
    return out


def interface_choices() -> list[tuple[str, str]]:
    """返回下拉选项 [(显示文本, 值)]，值用于 engine 绑定（IPv4 地址，空串=自动）。"""
    choices: list[tuple[str, str]] = [("自动（默认）", "")]
    for it in list_network_interfaces():
        ip = it["ipv4"][0]
        choices.append((f"{it['name']} ({ip})", ip))
    return choices
