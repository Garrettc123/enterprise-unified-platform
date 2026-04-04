"""
Unit tests for keyless_utils.py
Run: python -m pytest utils/keyless_utils_test.py -v
"""
import os
import pytest

os.environ.setdefault("GITHUB_SHA", "abc123def456abc123def456abc123def456abc1")
os.environ.setdefault("GITHUB_REPOSITORY", "Garrettc123/enterprise-unified-platform")
os.environ.setdefault("GITHUB_ACTOR", "Garrettc123")

from keyless_utils import (
    KeylessContext,
    merkle_root,
    derive_ephemeral_key,
    hkdf_sha3_256,
)


def test_hkdf_deterministic():
    k1 = hkdf_sha3_256(b"ikm", b"salt", b"info")
    k2 = hkdf_sha3_256(b"ikm", b"salt", b"info")
    assert k1 == k2
    assert len(k1) == 32


def test_hkdf_different_info_produces_different_keys():
    k1 = hkdf_sha3_256(b"ikm", b"salt", b"info-a")
    k2 = hkdf_sha3_256(b"ikm", b"salt", b"info-b")
    assert k1 != k2


def test_merkle_root_deterministic():
    fields = {"a": "1", "b": "2", "c": "3"}
    assert merkle_root(fields) == merkle_root(fields)
    assert len(merkle_root(fields)) == 64


def test_merkle_root_order_independent():
    assert merkle_root({"a": "1", "b": "2"}) == merkle_root({"b": "2", "a": "1"})


def test_sign_and_verify():
    ctx = KeylessContext.from_env()
    signed = ctx.sign_payload({"action": "deploy", "target": "production"})
    assert ctx.verify(signed)
    assert signed.merkle
    assert len(signed.hkdf_fingerprint) == 16


def test_tamper_detection():
    ctx = KeylessContext.from_env()
    signed = ctx.sign_payload({"action": "deploy"})
    signed.payload["action"] = "TAMPERED"
    assert not ctx.verify(signed)


def test_two_contexts_isolated():
    ctx1 = KeylessContext("sha1" * 10, "repo/a", "actor1")
    ctx2 = KeylessContext("sha2" * 10, "repo/b", "actor2")
    assert ctx1.hkdf_fingerprint != ctx2.hkdf_fingerprint
    assert ctx1.public_key_hex != ctx2.public_key_hex


def test_signed_json_contains_no_secrets():
    ctx = KeylessContext.from_env()
    signed = ctx.sign_payload({"x": 42})
    j = signed.to_json()
    assert "merkle" in j
    assert "signature" in j
    assert "secret" not in j.lower()
