"""Binary Merkle tree helpers for the local evidence log (N1.4).

Leaves are already-hashed values (``sha256:<hex>`` content or pack hashes).
Internal nodes hash the concatenation of child digests (raw 32-byte values).

Honesty:

* A valid inclusion proof shows a leaf was in the tree that produced ``root``
  at some operator-local log state — not a public transparency log and not
  on-chain.
* Empty tree has no root; single-leaf root is the leaf digest itself.
"""

from __future__ import annotations

import hashlib
from typing import Any

from veritas.hashing import compute_content_hash


def _raw_digest(value: str) -> bytes:
    """Turn ``sha256:<hex>`` (or bare 64-hex) into 32 raw bytes."""
    text = (value or "").strip()
    if text.startswith("sha256:"):
        text = text[7:]
    if len(text) != 64:
        raise ValueError("digest must be sha256 32-byte hex")
    return bytes.fromhex(text)


def _pair_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(left + right).digest()


def _to_sha256_hex(raw: bytes) -> str:
    return "sha256:" + raw.hex()


def merkle_root(leaves: list[str]) -> str | None:
    """Compute Merkle root over leaf hash strings. None if empty."""
    if not leaves:
        return None
    level = [_raw_digest(leaf) for leaf in leaves]
    while len(level) > 1:
        nxt: list[bytes] = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left  # promote odd
            nxt.append(_pair_hash(left, right))
        level = nxt
    return _to_sha256_hex(level[0])


def inclusion_proof(leaves: list[str], index: int) -> dict[str, Any]:
    """Build an inclusion proof for ``leaves[index]``.

    Path entries: ``{"sibling": "sha256:…", "side": "left"|"right"}`` where
    ``side`` is the side the *sibling* sits on when hashing with the running
    node (sibling left → hash(sibling || node)).
    """
    if not leaves:
        raise ValueError("empty leaves")
    if index < 0 or index >= len(leaves):
        raise ValueError("index out of range")
    level = [_raw_digest(leaf) for leaf in leaves]
    path: list[dict[str, str]] = []
    idx = index
    while len(level) > 1:
        if idx % 2 == 0:
            sib_i = idx + 1 if idx + 1 < len(level) else idx
            side = "right"
        else:
            sib_i = idx - 1
            side = "left"
        path.append({"sibling": _to_sha256_hex(level[sib_i]), "side": side})
        nxt: list[bytes] = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left
            nxt.append(_pair_hash(left, right))
        level = nxt
        idx //= 2
    return {
        "leaf": leaves[index],
        "index": index,
        "root": _to_sha256_hex(level[0]),
        "path": path,
        "leaf_count": len(leaves),
    }


def verify_inclusion(proof: dict[str, Any]) -> tuple[bool, str]:
    """Verify an inclusion proof. Returns ``(ok, reason)`` with stable codes."""
    try:
        leaf = proof["leaf"]
        root = proof["root"]
        path = proof["path"]
    except KeyError:
        return False, "proof_incomplete"
    if not isinstance(path, list):
        return False, "path_malformed"
    try:
        node = _raw_digest(leaf)
        for step in path:
            if not isinstance(step, dict):
                return False, "path_malformed"
            sibling = _raw_digest(str(step.get("sibling") or ""))
            side = step.get("side")
            if side == "left":
                node = _pair_hash(sibling, node)
            elif side == "right":
                node = _pair_hash(node, sibling)
            else:
                return False, "path_side_invalid"
        actual = _to_sha256_hex(node)
    except (ValueError, TypeError):
        return False, "digest_malformed"
    if actual != root:
        return False, "root_mismatch"
    return True, "ok"


def leaf_from_content(content: str) -> str:
    """Hash arbitrary content into a leaf (same as content_hash)."""
    return compute_content_hash(content)


__all__ = [
    "inclusion_proof",
    "leaf_from_content",
    "merkle_root",
    "verify_inclusion",
]
