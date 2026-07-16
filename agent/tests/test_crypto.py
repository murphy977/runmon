import pytest

from runmon.crypto import decrypt, encrypt, generate_key, key_from_b64, key_to_b64


def test_roundtrip():
    key = generate_key()
    obj = {"runs": [{"id": "abc", "name": "训练", "progress": 42.5}], "n": None}
    env = encrypt(obj, key)
    assert set(env) == {"n", "c"}
    assert decrypt(env, key) == obj


def test_key_b64_roundtrip():
    key = generate_key()
    assert len(key) == 32
    assert key_from_b64(key_to_b64(key)) == key


def test_bad_key_length():
    with pytest.raises(ValueError):
        key_from_b64("c2hvcnQ=")  # "short"


def test_tamper_fails():
    key = generate_key()
    env = encrypt({"a": 1}, key)
    bad = dict(env)
    bad["c"] = ("A" + env["c"][1:]) if env["c"][0] != "A" else ("B" + env["c"][1:])
    with pytest.raises(Exception):
        decrypt(bad, key)


def test_wrong_key_fails():
    env = encrypt({"a": 1}, generate_key())
    with pytest.raises(Exception):
        decrypt(env, generate_key())
