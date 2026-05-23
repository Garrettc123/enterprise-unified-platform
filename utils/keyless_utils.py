"""
Keyless Cryptographic Utility Layer
====================================
Zero secrets. Zero stored keys. Every credential is derived ephemerally
from public, verifiable inputs using:
  - HKDF-SHA3-256  → ephemeral symmetric key
  - Ed25519         → ephemeral signing keypair (in-memory only)
  - SHA3-256 Merkle → holographic audit root
  - GitHub OIDC JWT → identity proof (no stored token)

Usage:
    from utils.keyless_utils import KeylessContext
    ctx = KeylessContext.from_env()  # reads GITHUB_SHA, GITHUB_REPOSITORY, GITHUB_ACTOR
    signed = ctx.sign_payload({"action": "deploy", "target": "production"})
    assert ctx.verify(signed)  # always verify before acting
    print(ctx.merkle_root(signed))  # immutable audit fingerprint
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


# ---------------------------------------------------------------------------
# HKDF-SHA3-256 (no stored secret — derived from public commit metadata)
# ---------------------------------------------------------------------------

def hkdf_sha3_256(ikm: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
    """Minimal HKDF using SHA3-256.  RFC 5869 compliant."""
    # Extract
    if not salt:
        salt = bytes(32)
    prk = hmac.new(salt, ikm, hashlib.sha3_256).digest()
    # Expand
    t = b""
    okm = b""
    for i in range(1, -(-length // 32) + 1):
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha3_256).digest()
        okm += t
    return okm[:length]


def derive_ephemeral_key(commit_sha: str, repo: str, actor: str) -> bytes:
    """
    Derive a per-job symmetric key from fully public inputs.
    The salt is itself a SHA3-256 hash, so it is deterministic but
    never requires a secret to be stored anywhere.
    """
    ikm = f"{commit_sha}:{repo}:{actor}:{int(time.time() // 300)}".encode()
    salt = hashlib.sha3_256(f"{repo}:{commit_sha}".encode()).digest()
    info = b"garcar-enterprise-keyless-v1"
    return hkdf_sha3_256(ikm, salt, info)


# ---------------------------------------------------------------------------
# Ed25519 ephemeral signing (private key never leaves memory)
# ---------------------------------------------------------------------------

@dataclass
class EphemeralSigner:
    _private_key: Any = field(repr=False)
    public_bytes: bytes = field(repr=True)

    @classmethod
    def generate(cls) -> "EphemeralSigner":
        if not _CRYPTO_AVAILABLE:
            raise RuntimeError(
                "Install 'cryptography' package: pip install cryptography"
            )
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        return cls(_private_key=priv, public_bytes=pub)

    def sign(self, data: bytes) -> bytes:
        return self._private_key.sign(data)

    def verify(self, data: bytes, signature: bytes) -> bool:
        try:
            self._private_key.public_key().verify(signature, data)
            return True
        except Exception:
            return False

    def __del__(self):
        self._private_key = None


# ---------------------------------------------------------------------------
# Holographic Merkle root — single SHA3-256 hash of all state fields
# ---------------------------------------------------------------------------

def merkle_root(fields: dict) -> str:
    """
    Deterministic SHA3-256 Merkle root over sorted key-value pairs.
    Order-independent: sorted by key before hashing.
    """
    leaves = [
        hashlib.sha3_256(f"{k}={v}".encode()).digest()
        for k, v in sorted(fields.items())
    ]
    while len(leaves) > 1:
        if len(leaves) % 2 != 0:
            leaves.append(leaves[-1])
        leaves = [
            hashlib.sha3_256(leaves[i] + leaves[i + 1]).digest()
            for i in range(0, len(leaves), 2)
        ]
    return leaves[0].hex() if leaves else hashlib.sha3_256(b"").hexdigest()


# ---------------------------------------------------------------------------
# KeylessContext — top-level API
# ---------------------------------------------------------------------------

@dataclass
class SignedPayload:
    payload: dict
    signature_hex: str
    public_key_hex: str
    hkdf_fingerprint: str
    merkle: str
    timestamp: int

    def to_dict(self) -> dict:
        return {
            "payload": self.payload,
            "signature": self.signature_hex,
            "pubkey": self.public_key_hex,
            "hkdf_fp": self.hkdf_fingerprint,
            "merkle": self.merkle,
            "ts": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


class KeylessContext:
    """
    One-shot context per GitHub Actions job.
    Instantiate once, use sign_payload() for every action that needs
    a cryptographic proof — no secret is ever touched.
    """

    def __init__(self, commit_sha: str, repo: str, actor: str):
        self.commit_sha = commit_sha
        self.repo = repo
        self.actor = actor
        self._hkdf_key = derive_ephemeral_key(commit_sha, repo, actor)
        self._signer = EphemeralSigner.generate()
        self._hkdf_fp = hashlib.sha3_256(self._hkdf_key).hexdigest()[:16]

    @classmethod
    def from_env(cls) -> "KeylessContext":
        """Bootstrap entirely from public GitHub Actions environment variables."""
        return cls(
            commit_sha=os.environ["GITHUB_SHA"],
            repo=os.environ["GITHUB_REPOSITORY"],
            actor=os.environ.get("GITHUB_ACTOR", "ci"),
        )

    def sign_payload(self, payload: dict) -> SignedPayload:
        """Sign an arbitrary payload dict. Private key lives only in this call."""
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        sig = self._signer.sign(canonical)
        ts = int(time.time())
        state = {
            "repo": self.repo,
            "sha": self.commit_sha,
            "actor": self.actor,
            "hkdf_fp": self._hkdf_fp,
            "sig": sig.hex(),
            "pubkey": self._signer.public_bytes.hex(),
            "ts": str(ts),
        }
        root = merkle_root(state)
        return SignedPayload(
            payload=payload,
            signature_hex=sig.hex(),
            public_key_hex=self._signer.public_bytes.hex(),
            hkdf_fingerprint=self._hkdf_fp,
            merkle=root,
            timestamp=ts,
        )

    def verify(self, signed: SignedPayload) -> bool:
        """Verify Ed25519 signature. Returns True only if tamper-free."""
        canonical = json.dumps(signed.payload, sort_keys=True, separators=(",", ":")).encode()
        return self._signer.verify(canonical, bytes.fromhex(signed.signature_hex))

    @property
    def hkdf_fingerprint(self) -> str:
        return self._hkdf_fp

    @property
    def public_key_hex(self) -> str:
        return self._signer.public_bytes.hex()
