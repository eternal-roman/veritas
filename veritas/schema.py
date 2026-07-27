"""The canonical Veritas response contract.

These dataclasses previously described a response shape that nothing produced:
the pipeline built ad-hoc dicts with different field names, so the "contract"
and the wire format were free to drift apart, and a consuming agent had no
authoritative definition to code against.

This module now defines the shape the pipeline actually emits and provides
`validate_response`, which the test suite runs against real pipeline output so
the contract cannot silently diverge again.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Status(str, Enum):
    COMPLETED = "completed"
    REFUSED = "refused"
    UNAVAILABLE = "unavailable"


class RefusalReason(str, Enum):
    NO_EVIDENCE = "no_evidence"
    LOW_CONFIDENCE = "low_confidence"
    RETRIEVAL_UNAVAILABLE = "retrieval_unavailable"


class Provenance(str, Enum):
    LIVE_FETCH = "live_fetch"
    OFFLINE_CORPUS = "offline_corpus"


@dataclass
class Evidence:
    url: str
    title: Optional[str]
    excerpt: str
    content_hash: str
    provider: Optional[str] = None
    provenance: Optional[str] = None
    relevance: float = 0.0


@dataclass
class Claim:
    id: str
    statement: str
    confidence: float
    evidence_hash: str
    source_url: str
    provenance: Optional[str] = None


@dataclass
class VeritasResponse:
    request_id: str
    status: Status
    query: str
    posterior: float
    claims: List[Claim] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    custody_root: Optional[str] = None
    custody_valid: bool = False
    retrieval: Dict[str, Any] = field(default_factory=dict)
    refusal_reason: Optional[str] = None
    billable: bool = True
    timestamp: str = ""


REQUIRED_FIELDS = (
    "request_id", "status", "query", "posterior", "claims", "evidence",
    "custody_root", "custody_valid", "retrieval", "refusal_reason",
    "billable", "timestamp",
)

REQUIRED_CLAIM_FIELDS = ("id", "statement", "confidence", "evidence_hash", "source_url")
REQUIRED_EVIDENCE_FIELDS = ("url", "excerpt", "content_hash")


def validate_response(payload: Dict[str, Any]) -> List[str]:
    """Return a list of contract violations; empty means conformant."""
    problems: List[str] = []

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

    if not isinstance(payload["posterior"], (int, float)) or not 0.0 <= payload["posterior"] <= 1.0:
        problems.append(f"posterior out of range: {payload['posterior']!r}")

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

    return problems
