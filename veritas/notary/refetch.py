"""Origin re-fetch verification for published content hashes (P7 product).

Binds a claimed ``content_hash`` to a live re-observation of a URL through the
same ``observe`` engine used by notarize — never a second scraper (N0-A).

When the origin cannot be re-observed (dead host, 404/410, timeout, SSRF-safe
refusal) and EvidenceStore still holds a body for that hash, the result is
``binding: stored_excerpt``. That is **not** an origin re-fetch and **not** a
fresh ``notary.observe``. The buyer learns: we still have the bytes we stored;
we could not re-observe the URL.

Honesty:

* A live match means: at re-fetch time, this service extracted a body whose
  content_hash equals the claimed hash. The origin may have changed since
  notarization; a mismatch is divergence, not proof of fraud.
* A stored-excerpt hit means only that the stored bytes still hash to the
  published digest. It does **not** prove the URL still serves them.
* Does **not** prove what the origin served to any other party.
* Does **not** settle on-chain (axis C remains unproven elsewhere).
"""

from __future__ import annotations

from typing import Any

from veritas.evidence_store import EvidenceStore
from veritas.hashing import verify_content_hash
from veritas.notary.observe import observe

REFETCH_NOTE = (
    "re-fetched origin at call time through notary.observe; "
    "page may have changed since notarization; "
    "not multi-party origin proof and not an on-chain anchor"
)

STORED_EXCERPT_BINDING = "stored_excerpt"
STORED_EXCERPT_NOTE = (
    "origin could not be re-observed; we still have the bytes stored "
    "under this content_hash; not a live origin observation and not "
    "an independent notary.observe"
)

#: HTTP statuses that mean the resource is gone, not a live body we can
#: compare. A completed observe of a 404 page is not an origin match.
_GONE_HTTP = frozenset({404, 410})


def _http_status(observation: dict[str, Any]) -> int | None:
    record = observation.get("evidence_record") or {}
    code = record.get("status_code")
    if isinstance(code, int):
        return code
    retrieval = observation.get("retrieval") or {}
    code = retrieval.get("status_code")
    return code if isinstance(code, int) else None


def _live_origin_observed(observation: dict[str, Any]) -> bool:
    """True only when observe completed against a still-present resource."""
    if observation.get("status") != "completed":
        return False
    code = _http_status(observation)
    if code is not None and code in _GONE_HTTP:
        return False
    return True


def _stored_excerpt_hit(
    url: str,
    expected_content_hash: str,
    evidence_store: EvidenceStore | None,
    *,
    origin_reason: str,
) -> dict[str, Any] | None:
    """Return a stored_excerpt result if the store still has matching bytes.

    Never invents a hit: missing, unsafe, or hash-mismatched records are
    a miss. Does not call observe and does not mint a new notary record.
    """
    store = evidence_store if evidence_store is not None else EvidenceStore()
    record = store.get(expected_content_hash)
    if record is None:
        return None
    excerpt = record.get("excerpt")
    if not isinstance(excerpt, str):
        return None
    ok, _ = verify_content_hash(excerpt, expected_content_hash)
    if not ok:
        return None
    stored_url = record.get("url")
    return {
        "valid": True,
        "binding": STORED_EXCERPT_BINDING,
        "match": True,
        # Distinct from "completed" so audit (live re-observation) stays
        # UNOBSERVED — stored bytes are not a fresh notary.observe.
        "status": STORED_EXCERPT_BINDING,
        "reason": STORED_EXCERPT_BINDING,
        "expected": expected_content_hash,
        "actual": expected_content_hash,
        "url": url,
        "stored_url": stored_url if isinstance(stored_url, str) else None,
        "stored_at": record.get("stored_at"),
        "origin_reason": origin_reason,
        "note": STORED_EXCERPT_NOTE,
    }


def refetch_verify(
    url: str,
    expected_content_hash: str,
    *,
    evidence_store: EvidenceStore | None = None,
    **observe_kwargs: Any,
) -> dict[str, Any]:
    """Re-observe ``url`` and compare the extracted body hash to ``expected``.

    Extra keyword arguments are forwarded to :func:`veritas.notary.observe.observe`
    (e.g. ``fetch_fn``, ``robots_body`` for offline tests). ``evidence_store``
    is this module's seam for the P13 stored-excerpt fallback; it is never
    forwarded to observe.
    """
    if not expected_content_hash or not str(expected_content_hash).startswith(
        "sha256:"
    ):
        return {
            "valid": False,
            "binding": "origin_refetch",
            "match": False,
            "status": "error",
            "reason": "malformed_hash",
            "expected": expected_content_hash,
            "actual": None,
            "url": url,
            "note": REFETCH_NOTE,
        }

    observation = observe(url, **observe_kwargs)
    status = observation.get("status")
    origin_reason = observation.get("refusal_reason") or status or "unavailable"

    if not _live_origin_observed(observation):
        stored = _stored_excerpt_hit(
            url,
            expected_content_hash,
            evidence_store,
            origin_reason=str(origin_reason),
        )
        if stored is not None:
            return stored

    if status != "completed":
        return {
            "valid": False,
            "binding": "origin_refetch",
            "match": False,
            "status": status,
            "reason": origin_reason,
            "expected": expected_content_hash,
            "actual": None,
            "url": url,
            "refetch_request_id": observation.get("request_id"),
            "note": REFETCH_NOTE,
        }

    record = observation.get("evidence_record") or {}
    actual = record.get("content_hash")
    match = actual == expected_content_hash
    return {
        "valid": bool(match),
        "binding": "origin_refetch",
        "match": bool(match),
        "status": "completed",
        "reason": "match" if match else "diverged",
        "expected": expected_content_hash,
        "actual": actual,
        "url": url,
        "refetch_request_id": observation.get("request_id"),
        "note": REFETCH_NOTE,
    }


__all__ = [
    "REFETCH_NOTE",
    "STORED_EXCERPT_BINDING",
    "STORED_EXCERPT_NOTE",
    "refetch_verify",
]
