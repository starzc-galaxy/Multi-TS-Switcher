import json
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.licensing.fingerprint import machine_id
from app.licensing.license_io import LicenseError, create_license, verify_license


def test_machine_id_stable():
    a, b = machine_id(), machine_id()
    assert a == b and len(a) == 64


def test_license_roundtrip():
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
    text = create_license("abc123", 5, priv)
    info = verify_license(text, pub)
    assert info["allowed_groups"] == 5 and info["machine_id"] == "abc123"


def test_license_rejects_bad_signature():
    key = Ed25519PrivateKey.generate()
    other = Ed25519PrivateKey.generate()
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub_other = other.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    text = create_license("abc", 3, priv)
    with pytest.raises(LicenseError):
        verify_license(text, pub_other)


def test_license_expiry_rejected():
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
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    text = create_license("abc", 4, priv, issued=past, days=1)
    with pytest.raises(LicenseError):
        verify_license(text, pub)


def test_license_permanent_has_no_expiry():
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
    text = create_license("abc", 4, priv)
    info = verify_license(text, pub)
    assert "expires_at" not in info
