"""Compose fetch → extract → record(+policy) into one observation.

This is the sole URL-observation entry for the notary product surface and for
research when it needs an observed page (``pipeline.run_research`` routes
through here rather than growing a parallel scraper — N0-A / A1).

Unavailable / transport failure is non-billable. Robots deny and unknown are
explicit refusals, never silent allow. Licence unknown stays unknown.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from veritas.custody import CustodyLedger
from veritas.hashing import verify_content_hash
from veritas.notary.extract import extract_body
from veritas.notary.fetch import USER_AGENT, FetchError, FetchResult, fetch
from veritas.notary.license import classify_license
from veritas.notary.record import (
    RETENTION_CLASS_STANDARD,
    EvidenceRecord,
    build_evidence_record,
)
from veritas.notary.robots import FetchClass, evaluate_robots
from veritas.notary.sign import maybe_attest_record
from veritas.safeurl import UnsafeUrlError
from veritas.support import support_report

ATTESTS = (
    "what this service received from this origin at this time; "
    "not what the origin served to any other party"
)

FetchFn = Callable[..., FetchResult]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _robots_url_for(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def _envelope(
    *,
    request_id: str,
    url: str,
    status: str,
    billable: bool,
    ledger: CustodyLedger,
    policy: dict[str, Any],
    evidence_record: dict[str, Any] | None,
    evidence: list[dict[str, Any]],
    refusal_reason: str | None,
    retrieval_meta: dict[str, Any],
    evidence_hashes_valid: bool = True,
    attestation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "request_id": request_id,
        "status": status,
        "url": url,
        # Money-path / ledger binding reuses the research `query` field name so
        # resubmitted authorizations compare like-for-like without a second store.
        "query": url,
        "claims": [],
        "evidence": evidence,
        "evidence_record": evidence_record,
        "policy": policy,
        "support": support_report(evidence),
        "custody_root": ledger.root_hash(),
        "custody_valid": ledger.verify_chain() and evidence_hashes_valid,
        "custody_chain": ledger.to_list(),
        "attests": ATTESTS,
        "retrieval": retrieval_meta,
        "refusal_reason": refusal_reason,
        "billable": billable,
        "timestamp": _now(),
    }
    # N1.1: omit rather than invent when no operator key is configured.
    if attestation is not None:
        body["attestation"] = attestation
    return body


def _fetch_robots_body(
    url: str,
    *,
    fetch_fn: FetchFn,
    fetch_kwargs: dict[str, Any],
) -> str | None:
    """Best-effort robots.txt. Failure → None (unknown, fail-closed)."""
    robots_url = _robots_url_for(url)
    try:
        result = fetch_fn(robots_url, **fetch_kwargs)
    except (FetchError, UnsafeUrlError, OSError, ValueError, TypeError):
        return None
    if result.status >= 400:
        return None
    try:
        return result.body.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - treat undecodable robots as missing
        return None


def observe(
    url: str,
    *,
    request_id: str | None = None,
    retention_class: str = RETENTION_CLASS_STANDARD,
    declared_license: str | Mapping[str, Any] | None = None,
    robots_body: str | None | object = ...,
    robots_override: str | None = None,
    observed_at: str | None = None,
    fetch_fn: FetchFn | None = None,
    resolver: Any = None,
    open_url: Any = None,
    ssl_context: Any = None,
    timeout: float | None = None,
    user_agent: str = USER_AGENT,
) -> dict[str, Any]:
    """Observe ``url``: policy → fetch → extract → EvidenceRecord + custody.

    ``robots_body``:
      * omitted (default ``...``) — attempt to fetch ``/robots.txt``
      * ``None`` — treat as not obtained (unknown, fail-closed)
      * ``str`` — classify this body (tests and operators pin it)

    Fetch injection (``fetch_fn`` / resolver / open_url / ssl_context) is for
    offline tests and local TLS fixtures. Production has no private bypass.
    """
    request_id = request_id or str(uuid.uuid4())
    ledger = CustodyLedger()
    ledger.append("created", "notary.observe", {"url": url, "request_id": request_id})

    fetch_impl: FetchFn = fetch_fn or fetch
    fetch_kwargs: dict[str, Any] = {}
    if resolver is not None:
        fetch_kwargs["resolver"] = resolver
    if open_url is not None:
        fetch_kwargs["open_url"] = open_url
    if ssl_context is not None:
        fetch_kwargs["ssl_context"] = ssl_context
    if timeout is not None:
        fetch_kwargs["timeout"] = timeout

    # --- robots policy (before content fetch) --------------------------------
    if robots_body is ...:
        resolved_robots: str | None = _fetch_robots_body(
            url, fetch_fn=fetch_impl, fetch_kwargs=fetch_kwargs,
        )
    else:
        resolved_robots = robots_body  # type: ignore[assignment]

    robots_decision = evaluate_robots(
        resolved_robots,
        url,
        user_agent,
        override=robots_override,
    )
    license_label = classify_license(declared_license)
    policy = {
        "license": license_label.to_dict(),
        "robots": robots_decision.to_dict(),
    }
    ledger.append("policy_classified", "notary.observe", {
        "robots": robots_decision.allowance,
        "license": license_label.id,
        "license_reuse": license_label.reuse,
    })

    empty_retrieval = {
        "providers_attempted": ["notary"],
        "providers_succeeded": [],
        "errors": [],
        "degraded": False,
        "unavailable": False,
    }

    if not robots_decision.may_fetch:
        reason = (
            "robots_denied"
            if robots_decision.allowance == FetchClass.DENIED
            else "robots_unknown"
        )
        ledger.append("refused", "notary.observe", {
            "reason": reason,
            "robots": robots_decision.to_dict(),
        })
        return _envelope(
            request_id=request_id,
            url=url,
            status="refused",
            billable=True,
            ledger=ledger,
            policy=policy,
            evidence_record=None,
            evidence=[],
            refusal_reason=reason,
            retrieval_meta=empty_retrieval,
        )

    # --- fetch ---------------------------------------------------------------
    def _fetch_unavailable(reason: str, exc: BaseException) -> dict[str, Any]:
        # Type name only — no exception text on the wire (CodeQL / 4f2321c).
        err_type = type(exc).__name__
        ledger.append("unavailable", "notary.observe", {
            "reason": reason,
            "detail": err_type,
        })
        meta = {
            **empty_retrieval,
            "errors": [{
                "provider": "notary",
                "error_type": err_type,
                "detail": err_type,
            }],
            "degraded": True,
            "unavailable": True,
        }
        return _envelope(
            request_id=request_id,
            url=url,
            status="unavailable",
            billable=False,
            ledger=ledger,
            policy=policy,
            evidence_record=None,
            evidence=[],
            refusal_reason="fetch_unavailable",
            retrieval_meta=meta,
        )

    try:
        fetched = fetch_impl(url, **fetch_kwargs)
    except UnsafeUrlError as exc:
        return _fetch_unavailable("url_refused", exc)
    except FetchError as exc:
        return _fetch_unavailable("fetch_failed", exc)
    except Exception as exc:  # noqa: BLE001 - converted to unavailable
        return _fetch_unavailable("fetch_failed", exc)

    content_type = fetched.headers.get("content-type")
    extracted = extract_body(fetched.body, content_type=content_type)
    record: EvidenceRecord = build_evidence_record(
        url=fetched.final_url or url,
        extracted=extracted,
        observed_at=observed_at,
        retention_class=retention_class,
        content_type=content_type,
        status_code=fetched.status,
        request_id=request_id,
    )
    record_dict = record.to_dict()
    # Stamp policy onto the durable record view without mutating the frozen dataclass.
    record_dict["policy"] = policy
    if fetched.truncated:
        record_dict["truncated"] = True

    content_hash = record.content_hash
    ledger.append("evidence_created", "notary.observe", {
        "content_hash": content_hash,
        "url": record.url,
        "extract_version": record.extract_version,
        "retention_class": record.retention_class,
        "status_code": record.status_code,
    })

    evidence_item = {
        "url": record.url,
        "title": record.title,
        "excerpt": record.body,
        "content_hash": content_hash,
        "provider": "notary",
        "provenance": "notary.observe",
        "license": license_label.to_dict(),
        "attribution": {
            "required": license_label.attribution_required,
            "text": None,
        },
        "observed": True,
        "retention_class": record.retention_class,
        "extract_version": record.extract_version,
    }
    hashes_valid = verify_content_hash(record.body, content_hash)[0]
    if not hashes_valid:
        ledger.append("integrity_failure", "notary.observe", {
            "reason": "evidence_hash_mismatch",
        })

    ledger.append("completed", "notary.observe", {
        "content_hash": content_hash,
        "n_bytes": len(record.body.encode("utf-8")),
    })

    retrieval_meta = {
        "providers_attempted": ["notary"],
        "providers_succeeded": ["notary"],
        "errors": [],
        "degraded": False,
        "unavailable": False,
        "final_url": fetched.final_url,
        "status_code": fetched.status,
        "truncated": fetched.truncated,
    }
    # N1.1 EIP-191: sign bound fields when VERITAS_SIGNING_KEY / agent wallet
    # is present. Refusal/unavailable paths never invent a signature.
    attestation = maybe_attest_record(record_dict)
    if attestation is not None:
        ledger.append("attested", "notary.sign", {
            "scheme": attestation.get("scheme"),
            "signer": attestation.get("signer"),
            "content_hash": content_hash,
        })
    # N1.4/N1.5: append content_hash + embed inclusion proof. Fail closed —
    # content_hash is always sha256: on this path; soft-omit was multi-worker residue.
    from veritas.notary.log import default_evidence_log

    log = default_evidence_log()
    log_entry = log.append(content_hash)
    proof = log.proof(int(log_entry["index"]))
    evidence_log_meta = {
        "index": log_entry["index"],
        "root": log_entry["root"],
        "leaf": log_entry["leaf"],
        "note": log_entry["note"],
        "inclusion_proof": proof,
    }
    ledger.append("logged", "notary.log", {
        "index": log_entry["index"],
        "root": log_entry["root"],
        "leaf": log_entry["leaf"],
    })
    envelope = _envelope(
        request_id=request_id,
        url=url,
        status="completed",
        billable=True,
        ledger=ledger,
        policy=policy,
        evidence_record=record_dict,
        evidence=[evidence_item],
        refusal_reason=None,
        retrieval_meta=retrieval_meta,
        evidence_hashes_valid=hashes_valid,
        attestation=attestation,
    )
    # N1.3: completed observations always carry a pack. Fail closed.
    from veritas.notary.pack import pack_from_observation

    envelope["evidence_pack"] = pack_from_observation(envelope)
    envelope["evidence_log"] = evidence_log_meta
    return envelope


__all__ = ["observe", "ATTESTS"]
