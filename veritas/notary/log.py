"""Append-only local evidence leaf log with Merkle roots (N1.4).

Stores leaf hashes (typically EvidencePack ``pack_hash`` or record
``content_hash``) under the runtime directory. Each append recomputes the
Merkle root over the full leaf list (sufficient for L1 product; not a
certificate transparency scale log).

Honesty:

* Operator-local only — not a public transparency log
* Not an on-chain anchor (settlements remain 0 elsewhere)
* Inclusion proves membership in *this instance's* log at a given root
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from veritas.notary.merkle import inclusion_proof, merkle_root, verify_inclusion

ENV_RUNTIME = "VERITAS_RUNTIME_DIR"
LOG_NOTE = (
    "operator-local Merkle evidence log; inclusion proves membership in this "
    "instance's leaf list at the stated root — not a public transparency log "
    "and not an on-chain anchor"
)


class EvidenceLogError(ValueError):
    """Evidence log operation could not proceed."""


class EvidenceLog:
    """Thread-safe append-only leaf log with Merkle proofs."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        runtime = Path(
            base_dir
            or os.getenv(ENV_RUNTIME)
            or ".veritas_runtime"
        )
        self.path = runtime / "evidence_log" / "leaves.json"
        self._lock = threading.Lock()

    def _read_leaves(self) -> list[str]:
        if not self.path.is_file():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        leaves = data.get("leaves") if isinstance(data, dict) else None
        if not isinstance(leaves, list):
            return []
        return [str(x) for x in leaves]

    def _write_leaves(self, leaves: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        payload = {
            "leaves": leaves,
            "root": merkle_root(leaves),
            "count": len(leaves),
            "note": LOG_NOTE,
        }
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def count(self) -> int:
        with self._lock:
            return len(self._read_leaves())

    def root(self) -> str | None:
        with self._lock:
            return merkle_root(self._read_leaves())

    def append(self, leaf: str) -> dict[str, Any]:
        """Append a leaf hash. Returns index, root, count."""
        if not isinstance(leaf, str) or not leaf.startswith("sha256:"):
            raise EvidenceLogError("leaf must be sha256:<hex>")
        with self._lock:
            leaves = self._read_leaves()
            leaves.append(leaf)
            self._write_leaves(leaves)
            root = merkle_root(leaves)
            return {
                "index": len(leaves) - 1,
                "leaf": leaf,
                "root": root,
                "count": len(leaves),
                "note": LOG_NOTE,
            }

    def proof(self, index: int) -> dict[str, Any]:
        with self._lock:
            leaves = self._read_leaves()
            if not leaves:
                raise EvidenceLogError("log_empty")
            try:
                proof = inclusion_proof(leaves, index)
            except ValueError as exc:
                raise EvidenceLogError(str(exc)) from exc
            proof["note"] = LOG_NOTE
            return proof

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            leaves = self._read_leaves()
            return {
                "count": len(leaves),
                "root": merkle_root(leaves),
                "note": LOG_NOTE,
            }


def verify_log_inclusion(proof: dict[str, Any]) -> dict[str, Any]:
    """Public verify helper with stable reason codes."""
    ok, reason = verify_inclusion(proof)
    return {
        "valid": ok,
        "reason": reason,
        "root": proof.get("root"),
        "leaf": proof.get("leaf"),
        "note": LOG_NOTE,
    }


# Process-default log (server uses runtime dir).
_default_log: EvidenceLog | None = None
_default_lock = threading.Lock()


def default_evidence_log() -> EvidenceLog:
    global _default_log
    with _default_lock:
        if _default_log is None:
            _default_log = EvidenceLog()
        return _default_log


def reset_default_evidence_log() -> None:
    """Test helper: drop process default so a new runtime dir is picked up."""
    global _default_log
    with _default_lock:
        _default_log = None


__all__ = [
    "ENV_RUNTIME",
    "LOG_NOTE",
    "EvidenceLog",
    "EvidenceLogError",
    "default_evidence_log",
    "reset_default_evidence_log",
    "verify_log_inclusion",
]
