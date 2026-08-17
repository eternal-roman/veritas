"""The canonical Veritas response contract.

The contract is constants plus `validate_response`, which the test suite runs
against real pipeline output so the published shape cannot silently diverge
from the emitted one. An earlier revision also carried dataclasses mirroring
the wire shape; they were never instantiated and drifted from the real
contract twice — a contract nothing produces is where drift hides, so they
were removed rather than re-synced.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class Status(str, Enum):
    COMPLETED = "completed"
    REFUSED = "refused"
    UNAVAILABLE = "unavailable"


class RefusalReason(str, Enum):
    NO_EVIDENCE = "no_evidence"
    IRRELEVANT_EVIDENCE = "irrelevant_evidence"
    RETRIEVAL_UNAVAILABLE = "retrieval_unavailable"


class Provenance(str, Enum):
    LIVE_FETCH = "live_fetch"
    OFFLINE_CORPUS = "offline_corpus"
    # Stamped by the pipeline when a source was re-observed through the
    # notary engine (observe_urls=True) and carried no provenance of its own.
    NOTARY_OBSERVE = "notary.observe"


REQUIRED_FIELDS = (
    "request_id", "status", "query", "claims", "evidence",
    "custody_root", "custody_valid", "custody_chain", "support", "attests",
    "retrieval", "refusal_reason", "billable", "timestamp",
)

REQUIRED_CLAIM_FIELDS = ("id", "statement", "evidence_hash", "source_url")
REQUIRED_EVIDENCE_FIELDS = ("url", "excerpt", "content_hash")


def response_json_schema() -> dict[str, Any]:
    """A JSON-Schema rendering of the wire contract, for non-Python consumers.

    Derived from the same constants `validate_response` enforces, so the
    served schema cannot drift from the enforced one. Nullability mirrors the
    pipeline's actual output (refusal_reason is null on completed responses;
    custody_root is typed nullable only for an empty ledger, which the
    pipeline never produces).
    """
    evidence_properties = {
        "url": {"type": "string"},
        "title": {"type": ["string", "null"]},
        "excerpt": {"type": "string"},
        "content_hash": {"type": "string", "pattern": "^sha256:"},
        "provider": {"type": ["string", "null"]},
        "provenance": {"type": ["string", "null"], "enum": [p.value for p in Provenance] + [None]},
        "relevance": {"type": "number"},
        # Emitted on every evidence item: what the buyer may reuse, and the
        # attribution that reuse must carry. Unknown licences say "unknown".
        "license": {"type": ["string", "null"]},
        "attribution": {"type": ["string", "null"]},
        # Present (true) only when the source body was re-fetched through the
        # notary observation engine rather than taken from a search snippet.
        "observed": {"type": "boolean"},
    }
    claim_properties = {
        "id": {"type": "string"},
        "statement": {"type": "string"},
        "relevance": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "evidence_hash": {"type": "string", "pattern": "^sha256:"},
        "source_url": {"type": "string"},
        "provenance": {"type": ["string", "null"], "enum": [p.value for p in Provenance] + [None]},
        # Optional. Extractive claims are the default product; synthesized
        # claims are lexical-NLI gated and never required for a valid response.
        "kind": {"type": "string", "enum": ["extractive", "synthesized"]},
        "support_hashes": {
            "type": "array",
            "items": {"type": "string", "pattern": "^sha256:"},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "VeritasResponse",
        "type": "object",
        "required": list(REQUIRED_FIELDS),
        "properties": {
            "request_id": {"type": "string"},
            "status": {"type": "string", "enum": [s.value for s in Status]},
            "query": {"type": "string"},
            "support": {"type": "object"},
            "attests": {"type": "string"},
            "custody_chain": {"type": "array", "items": {"type": "object"}},
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": list(REQUIRED_CLAIM_FIELDS),
                    "properties": claim_properties,
                },
            },
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": list(REQUIRED_EVIDENCE_FIELDS),
                    "properties": evidence_properties,
                },
            },
            "custody_root": {"type": ["string", "null"]},
            "custody_valid": {"type": "boolean"},
            "retrieval": {"type": "object"},
            "refusal_reason": {
                "type": ["string", "null"],
                "enum": [r.value for r in RefusalReason] + [None],
            },
            "billable": {"type": "boolean"},
            "timestamp": {"type": "string"},
        },
    }


def validate_response(payload: dict[str, Any]) -> list[str]:
    """Return a list of contract violations; empty means conformant."""
    problems: list[str] = []

    for key in REQUIRED_FIELDS:
        if key not in payload:
            problems.append(f"missing field: {key}")
    if problems:
        return problems

    valid_statuses = {s.value for s in Status}
    if payload["status"] not in valid_statuses:
        problems.append(f"invalid status: {payload['status']!r}")

    reason = payload.get("refusal_reason")
    if reason is not None and reason not in {r.value for r in RefusalReason}:
        problems.append(f"invalid refusal_reason: {reason!r}")

    if not isinstance(payload.get("custody_chain"), list):
        problems.append("custody_chain must be a list of custody events")
    if not isinstance(payload.get("support"), dict):
        problems.append("support must be an object")

    # Core invariants of the product's promise.
    if payload["status"] == Status.COMPLETED.value and not payload["claims"]:
        problems.append("completed response must carry at least one claim")
    if payload["status"] == Status.REFUSED.value and payload["claims"]:
        problems.append("refused response must not carry claims")
    if payload["status"] == Status.UNAVAILABLE.value and payload["billable"]:
        problems.append("unavailable response must not be billable")

    evidence_hashes = set()
    for i, ev in enumerate(payload["evidence"]):
        for key in REQUIRED_EVIDENCE_FIELDS:
            if key not in ev:
                problems.append(f"evidence[{i}] missing {key}")
        if "content_hash" in ev:
            if not str(ev["content_hash"]).startswith("sha256:"):
                problems.append(f"evidence[{i}] hash not sha256-prefixed")
            evidence_hashes.add(ev["content_hash"])

    for i, claim in enumerate(payload["claims"]):
        for key in REQUIRED_CLAIM_FIELDS:
            if key not in claim:
                problems.append(f"claims[{i}] missing {key}")
        # Every claim must cite evidence actually present in the response.
        if claim.get("evidence_hash") not in evidence_hashes:
            problems.append(f"claims[{i}] cites evidence absent from response")
        kind = claim.get("kind")
        if kind is not None and kind not in {"extractive", "synthesized"}:
            problems.append(f"claims[{i}] has unknown kind {kind!r}")
        extra = claim.get("support_hashes")
        if extra is not None:
            if not isinstance(extra, list):
                problems.append(f"claims[{i}] support_hashes must be a list")
            else:
                for digest in extra:
                    if digest not in evidence_hashes:
                        problems.append(
                            f"claims[{i}] support_hashes cites evidence absent from response"
                        )

    return problems
