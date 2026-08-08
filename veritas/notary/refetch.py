"""Origin re-fetch verification for published content hashes (P7 product).

Binds a claimed ``content_hash`` to a live re-observation of a URL through the
same ``observe`` engine used by notarize — never a second scraper (N0-A).

Honesty:

* A match means: at re-fetch time, this service extracted a body whose
  content_hash equals the claimed hash. The origin may have changed since
  notarization; a mismatch is divergence, not proof of fraud.
* Does **not** prove what the origin served to any other party.
* Does **not** settle on-chain (axis C remains unproven elsewhere).
"""

from __future__ import annotations

from typing import Any

from veritas.notary.observe import observe

REFETCH_NOTE = (
    "re-fetched origin at call time through notary.observe; "
    "page may have changed since notarization; "
    "not multi-party origin proof and not an on-chain anchor"
)


def refetch_verify(
    url: str,
    expected_content_hash: str,
    **observe_kwargs: Any,
) -> dict[str, Any]:
    """Re-observe ``url`` and compare the extracted body hash to ``expected``.

    Extra keyword arguments are forwarded to :func:`veritas.notary.observe.observe`
    (e.g. ``fetch_fn``, ``robots_body`` for offline tests).
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
    if status != "completed":
        return {
            "valid": False,
            "binding": "origin_refetch",
            "match": False,
            "status": status,
            "reason": observation.get("refusal_reason") or status or "unavailable",
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


__all__ = ["REFETCH_NOTE", "refetch_verify"]
