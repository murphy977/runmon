"""E2EE:所有经 relay 的业务负载用 ChaCha20-Poly1305 加密,密钥只在 agent 与 App 两端。"""
from __future__ import annotations

import base64
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305


def generate_key() -> bytes:
    return os.urandom(32)


def key_to_b64(key: bytes) -> str:
    return base64.urlsafe_b64encode(key).decode()


def key_from_b64(s: str) -> bytes:
    key = base64.urlsafe_b64decode(s.encode())
    if len(key) != 32:
        raise ValueError("E2EE key must be 32 bytes")
    return key


def encrypt(obj: Any, key: bytes) -> dict:
    nonce = os.urandom(12)
    data = json.dumps(obj, ensure_ascii=False).encode()
    ct = ChaCha20Poly1305(key).encrypt(nonce, data, None)
    return {"n": base64.b64encode(nonce).decode(), "c": base64.b64encode(ct).decode()}


def decrypt(env: dict, key: bytes) -> Any:
    nonce = base64.b64decode(env["n"])
    ct = base64.b64decode(env["c"])
    return json.loads(ChaCha20Poly1305(key).decrypt(nonce, ct, None).decode())
