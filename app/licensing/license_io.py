from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


class LicenseError(Exception):
    pass


def generate_keypair() -> tuple[bytes, bytes]:
    key = Ed25519PrivateKey.generate()
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv, pub


def _canonical_payload(info: dict) -> bytes:
    core = {
        k: info[k]
        for k in ("product", "machine_id", "allowed_groups", "issued", "valid_days", "expires_at")
        if k in info
    }
    return json.dumps(core, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def create_license(machine_id: str, allowed_groups: int, private_key_pem: bytes,
                   issued: str | None = None, days: int | None = None) -> str:
    key = serialization.load_pem_private_key(private_key_pem, password=None)
    assert isinstance(key, Ed25519PrivateKey)
    issued_str = issued or datetime.now(timezone.utc).isoformat()
    info = {
        "product": "multi-ts-switcher",
        "machine_id": machine_id,
        "allowed_groups": int(allowed_groups),
        "issued": issued_str,
    }
    if days:
        issued_dt = datetime.fromisoformat(issued_str)
        if issued_dt.tzinfo is None:
            issued_dt = issued_dt.replace(tzinfo=timezone.utc)
        info["valid_days"] = int(days)
        info["expires_at"] = (issued_dt + timedelta(days=int(days))).isoformat()
    sig = key.sign(_canonical_payload(info))
    info["signature"] = sig.hex()
    return json.dumps(info, ensure_ascii=False, indent=2)


def verify_license(text: str, public_key_pem: bytes | None = None) -> dict:
    if public_key_pem is None:
        from app.licensing.keys import PUBLIC_KEY_PEM

        public_key_pem = PUBLIC_KEY_PEM
    try:
        info = json.loads(text)
        sig = bytes.fromhex(info.pop("signature"))
        key = serialization.load_pem_public_key(public_key_pem)
        assert isinstance(key, Ed25519PublicKey)
        key.verify(sig, _canonical_payload(info))
        expires = info.get("expires_at")
        if expires:
            exp_dt = datetime.fromisoformat(expires)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp_dt:
                raise LicenseError("授权已过期")
        return info
    except (KeyError, ValueError, json.JSONDecodeError, InvalidSignature, TypeError, AssertionError) as exc:
        raise LicenseError(f"授权文件无效: {exc}") from exc
