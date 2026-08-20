from __future__ import annotations

import hashlib
import platform
import uuid


def machine_id() -> str:
    raw = "|".join(
        [
            f"mac={uuid.getnode():012x}",
            f"machine={platform.machine()}",
            f"processor={platform.processor()}",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
