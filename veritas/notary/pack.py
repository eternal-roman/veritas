"""Portable EvidencePack for agent-to-agent handoff (N1.3).

A pack is a **self-contained JSON object** an agent can store, pass to another
agent, and re-check without re-calling the operator for arithmetic integrity:

* ``pack_hash`` binds the pack's own fields (canonical JSON, excl. pack_hash)
* Optional ``attestation`` reuses N1.1 EIP-191 over bound record fields
* Optional ``body`` is checked against ``content_hash`` when present

Honesty boundaries:

* This is **not** a Merkle inclusion proof against a public log (later N1.3+)
* This is **not** an on-chain anchor (settlements remain 0 elsewhere)
* ``pack_hash`` integrity means the pack bytes were not garbled in transit;
  it does not prove the origin served that body to any third party
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from veritas.hashing import compute_content_hash
from veritas.notary.sign import verify_attestation

PACK_VERSION = "veritas-evidence-pack-v1"

PACK_NOTE = (
    "portable evidence pack with pack_hash integrity; "
    "optional EIP-191 attestation; not a Merkle log inclusion proof "
    "and not an on-chain anchor"
)

_HASH_FIELDS = (
    "pack_version",
    "url",
    "content_hash",
    "observed_at",
    "extract_version",
    "request_id",
    "custody_root",
    "attestation",
)


class EvidencePackError(ValueError):
    """Pack construction or verification could not proceed."""


def _canonical_pack_payload(fields: Mapping[str, Any]) -> str:
    payload = {key: fields.get(key) for key in _HASH_FIELDS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_pack_hash(fields: Mapping[str, Any]) -> str:
    return compute_content_hash(_canonical_pack_payload(fields))


def build_evidence_pack(
    *,
    url: str,
    content_hash: str,
    observed_at: str,
    extract_version: str,
    request_id: str | None = None,
    custody_root: str | None = None,
    attestation: Mapping[str, Any] | None = None,
    body: str | None = None,
) -> dict[str, Any]:
    """Build a portable pack. Body is optional and never part of pack_hash."""
    if not content_hash or not str(content_hash).startswith("sha256:"):
        raise EvidencePackError("content_hash must be sha256:<hex>")
    if body is not None:
        actual = compute_content_hash(body)
        if actual != content_hash:
            raise EvidencePackError("body does not match content_hash")

    pack: dict[str, Any] = {
        "pack_version": PACK_VERSION,
        "url": url,
        "content_hash": content_hash,
        "observed_at": observed_at,
        "extract_version": extract_version,
        "request_id": request_id or "",
        "custody_root": custody_root,
        "attestation": dict(attestation) if attestation else None,
        "note": PACK_NOTE,
    }
    pack["pack_hash"] = compute_pack_hash(pack)
    if body is not None:
        pack["body"] = body
    return pack


def pack_from_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Build a pack from an observe/notarize envelope (completed only)."""
    if observation.get("status") != "completed":
        raise EvidencePackError("observation is not completed")
    record = observation.get("evidence_record") or {}
    try:
        return build_evidence_pack(
            url=str(record.get("url") or observation.get("url") or ""),
            content_hash=str(record["content_hash"]),
            observed_at=str(record["observed_at"]),
            extract_version=str(record["extract_version"]),
            request_id=record.get("request_id") or observation.get("request_id"),
            custody_root=observation.get("custody_root"),
            attestation=observation.get("attestation"),
        )
    except KeyError as exc:
        raise EvidencePackError(f"observation missing field: {exc}") from exc


def verify_evidence_pack(pack: Mapping[str, Any]) -> dict[str, Any]:
    """Check pack_hash (+ optional body and attestation). Stable reason codes."""
    if not pack:
        return {"valid": False, "reason": "pack_missing", "note": PACK_NOTE}
    if pack.get("pack_version") != PACK_VERSION:
        return {"valid": False, "reason": "version_mismatch", "note": PACK_NOTE}
    published = pack.get("pack_hash")
    if not isinstance(published, str) or not published.startswith("sha256:"):
        return {"valid": False, "reason": "pack_hash_missing", "note": PACK_NOTE}
    actual = compute_pack_hash(pack)
    if actual != published:
        return {
            "valid": False,
            "reason": "pack_hash_mismatch",
            "expected": published,
            "actual": actual,
            "note": PACK_NOTE,
        }

    content_hash = pack.get("content_hash")
    if not isinstance(content_hash, str) or not content_hash.startswith("sha256:"):
        return {"valid": False, "reason": "content_hash_malformed", "note": PACK_NOTE}

    body = pack.get("body")
    if body is not None:
        if not isinstance(body, str):
            return {"valid": False, "reason": "body_malformed", "note": PACK_NOTE}
        if compute_content_hash(body) != content_hash:
            return {"valid": False, "reason": "body_mismatch", "note": PACK_NOTE}

    attestation = pack.get("attestation")
    attestation_ok: bool | None = None
    attestation_reason: str | None = None
    if attestation is not None:
        if not isinstance(attestation, Mapping):
            return {"valid": False, "reason": "attestation_malformed", "note": PACK_NOTE}
        record = {
            "url": pack.get("url"),
            "content_hash": content_hash,
            "observed_at": pack.get("observed_at"),
            "extract_version": pack.get("extract_version"),
            "request_id": pack.get("request_id") or "",
        }
        ok, reason = verify_attestation(record, attestation)
        attestation_ok = ok
        attestation_reason = reason
        if not ok:
            return {
                "valid": False,
                "reason": "attestation_invalid",
                "attestation_reason": attestation_reason,
                "note": PACK_NOTE,
            }

    return {
        "valid": True,
        "reason": "ok",
        "pack_hash": published,
        "content_hash": content_hash,
        "attestation_ok": attestation_ok,
        "attestation_reason": attestation_reason,
        "note": PACK_NOTE,
    }


__all__ = [
    "PACK_NOTE",
    "PACK_VERSION",
    "EvidencePackError",
    "build_evidence_pack",
    "compute_pack_hash",
    "pack_from_observation",
    "verify_evidence_pack",
]
