"""Survival records: counterparty standing as what survives independent audit.

The trust score in `veritas.trust` is computed by the graded party from its
own records — the constitution registers that as gap G10 and this repository
says it plainly wherever the score appears. This module is the buyer-side
mechanism that makes externally computable standing possible:

1. A seller's EIP-191 evidence attestation (N1.1) is a **staked claim**:
   "this URL served a body with this hash at this time", signed by a key.
2. Any third party holding the pack re-fetches the origin through the same
   notary engine (`veritas.notary.refetch` — one engine, never a second
   scraper) and records whether the claim survived: an **AuditRecord**,
   signed by the auditor's own key.
3. Anyone holding a set of audit records computes a **survival report** —
   counts, not a score, in the `veritas.support` tradition — without the
   audited party's cooperation or arithmetic.

Design rules inherited from the rest of the codebase (see
docs/program/FABLE_INSIGHTS.md for the full derivation):

* **Independence is counted per auditor key**, never per record volume —
  the same argument by which `support.py` counts registrable domains: two
  thousand records signed by one key are one witness.
* **`unobserved` is evidence of nothing.** A re-fetch that could not observe
  the origin is reported and never counted for or against a seller — the
  audit-layer analogue of `unavailable` ≠ `no_evidence`.
* **`diverged` is divergence, not fraud proof** (the P7 boundary): pages
  legitimately change between notarization and audit.
* **Self-audits are surfaced and excluded** from independence counts: a
  seller auditing its own attestation is a consistency check, not standing.
* **The aggregator is the buyer.** There is deliberately no seller-hosted
  audit surface here: a mailbox curated by the audited party is G10 with
  extra steps. `survival_report` is a pure function over records the caller
  holds, from wherever obtained.

Honesty boundaries:

* A survival report describes the records provided to it. Nothing forces an
  unfavourable record into the set — divergence counts are a floor, never a
  ceiling (constitution gap G11, witnessed).
* A `confirmed` verdict means one auditor's fetch matched the attested hash
  at one time; it does not prove what the origin serves to other parties.
* Distinct keys are not proven distinct parties. Sybil auditors cost only
  key generation; distinct-auditor counts raise the floor of collusion cost
  without establishing identity.
* Nothing here anchors to a chain or public log, and `/v1/trust` remains
  self-reported: this ships the mechanism for external standing, not the
  standing itself.

Signature domain separation: audit messages carry their own version prefix
(`veritas-audit-record-v1`), disjoint from the evidence-attestation prefix,
so a signature over one can never verify as the other. Signing reuses the
`veritas.notary.sign` primitives — the same secp256k1/EIP-191 family, never
a second crypto stack.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from veritas.notary.pack import verify_evidence_pack
from veritas.notary.refetch import refetch_verify
from veritas.notary.sign import (
    NotarySignError,
    OperatorSigner,
    recover_attestation_signer,
)

METHOD = "veritas.audit.v1"
AUDIT_VERSION = "veritas-audit-record-v1"

VERDICT_CONFIRMED = "confirmed"
VERDICT_DIVERGED = "diverged"
VERDICT_UNOBSERVED = "unobserved"
VALID_VERDICTS = frozenset({VERDICT_CONFIRMED, VERDICT_DIVERGED, VERDICT_UNOBSERVED})

AUDIT_NOTE = (
    "auditor re-fetched the origin through notary.observe and compared the "
    "attested content_hash; confirmed/diverged describe that one observation; "
    "unobserved is evidence of nothing and is never scored; "
    "not an on-chain anchor and not proof of what the origin serves others"
)

REPORT_NOTE = (
    "counts over the records provided; independence is per distinct auditor "
    "key, self-audits excluded; unobserved reported, never scored; records "
    "may have been withheld by whoever assembled the set (gap G11), so "
    "divergence counts are a floor, not a ceiling"
)

_ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
# RFC3339 UTC with Z suffix, seconds precision or better — the repo's `_now` shape.
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


class AuditError(ValueError):
    """Audit construction could not proceed. Stable message codes only."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_audit_message(record: Mapping[str, Any]) -> str:
    """The EIP-191 text an auditor signs. Binds the claim and the verdict.

    Bound fields only — enrichments (reason, refetch_request_id, note) stay
    outside the signature so wire additions do not invalidate old records,
    the same stability choice N1.1 made for evidence attestations.
    """
    try:
        pack_hash = record["pack_hash"]
        url = record["url"]
        content_hash = record["content_hash"]
        verdict = record["verdict"]
        audited_at = record["audited_at"]
    except KeyError as exc:
        raise AuditError(f"record missing field for signing: {exc}") from exc
    attested_signer = record.get("attested_signer") or ""
    return "\n".join(
        (
            AUDIT_VERSION,
            f"pack_hash: {pack_hash}",
            f"url: {url}",
            f"content_hash: {content_hash}",
            f"attested_signer: {attested_signer}",
            f"verdict: {verdict}",
            f"audited_at: {audited_at}",
        )
    )


def perform_audit(
    pack: Mapping[str, Any],
    *,
    signer: OperatorSigner | None = None,
    **observe_kwargs: Any,
) -> dict[str, Any]:
    """Audit an EvidencePack against a live re-observation of its origin.

    The pack's own integrity (pack_hash, optional body, optional seller
    attestation) is checked first; a pack that fails those checks is not
    auditable and raises :class:`AuditError` — an audit must never lend a
    verdict, favourable or not, to a claim that was never validly made.

    Keyword arguments are forwarded to ``notary.observe`` via
    :func:`veritas.notary.refetch.refetch_verify` (e.g. ``fetch_fn``,
    ``robots_body`` for offline tests). When ``signer`` is provided the
    record carries the auditor's EIP-191 signature; without one the record
    is unsigned and counts for nothing in a survival report.
    """
    verification = verify_evidence_pack(pack)
    if not verification.get("valid"):
        raise AuditError(f"pack_invalid:{verification.get('reason')}")

    attestation = pack.get("attestation") or {}
    attested_signer = str(attestation.get("signer") or "").lower()

    outcome = refetch_verify(
        str(pack["url"]), str(pack["content_hash"]), **observe_kwargs
    )
    if outcome["status"] == "completed":
        verdict = VERDICT_CONFIRMED if outcome["match"] else VERDICT_DIVERGED
    else:
        verdict = VERDICT_UNOBSERVED

    record: dict[str, Any] = {
        "audit_version": AUDIT_VERSION,
        "method": METHOD,
        "pack_hash": pack["pack_hash"],
        "url": pack["url"],
        "content_hash": pack["content_hash"],
        "attested_signer": attested_signer,
        "verdict": verdict,
        "reason": outcome.get("reason"),
        "refetch_request_id": outcome.get("refetch_request_id"),
        "audited_at": _now(),
        "note": AUDIT_NOTE,
    }
    if signer is not None:
        message = canonical_audit_message(record)
        record["auditor"] = {
            "scheme": "eip191",
            "signer": signer.address.lower(),
            "signature": signer.sign_text(message),
            "message": message,
        }
    return record


def verify_audit_record(record: Mapping[str, Any]) -> tuple[bool, str]:
    """Check one audit record. Returns ``(ok, reason)`` with stable codes.

    Valid means: well-formed, verdict in the taxonomy, timestamp in the
    repo's UTC shape, and the auditor signature recovers to the claimed
    signer over the canonically rebuilt message — a tampered ``message``
    field cannot pass, the same rule `notary.sign.verify_attestation`
    applies. Self-audit is a classification, not an invalidity: see
    :func:`is_self_audit`.
    """
    if not record:
        return False, "record_missing"
    if record.get("audit_version") != AUDIT_VERSION:
        return False, "version_mismatch"
    if record.get("verdict") not in VALID_VERDICTS:
        return False, "verdict_invalid"
    audited_at = record.get("audited_at")
    if not isinstance(audited_at, str) or not _TS_RE.match(audited_at):
        return False, "audited_at_malformed"
    content_hash = record.get("content_hash")
    if not isinstance(content_hash, str) or not content_hash.startswith("sha256:"):
        return False, "content_hash_malformed"
    pack_hash = record.get("pack_hash")
    if not isinstance(pack_hash, str) or not pack_hash.startswith("sha256:"):
        return False, "pack_hash_malformed"

    auditor = record.get("auditor")
    if not isinstance(auditor, Mapping):
        return False, "auditor_missing"
    if auditor.get("scheme") != "eip191":
        return False, "scheme_mismatch"
    signature = auditor.get("signature")
    if not isinstance(signature, str):
        return False, "signature_missing"
    try:
        message = canonical_audit_message(record)
    except AuditError:
        return False, "record_incomplete"
    published = auditor.get("message")
    if published is not None and published != message:
        return False, "message_mismatch"
    try:
        recovered = recover_attestation_signer(message, signature)
    except NotarySignError:
        return False, "signature_invalid"
    claimed = auditor.get("signer")
    if not isinstance(claimed, str) or claimed.lower() != recovered:
        return False, "signer_mismatch"
    return True, "ok"


def is_self_audit(record: Mapping[str, Any]) -> bool:
    """True when the auditor key is the key that made the attested claim."""
    auditor = record.get("auditor") or {}
    auditor_key = str(auditor.get("signer") or "").lower()
    attested = str(record.get("attested_signer") or "").lower()
    return bool(auditor_key) and auditor_key == attested


def survival_report(
    records: list[Mapping[str, Any]],
    *,
    seller: str | None = None,
) -> dict[str, Any]:
    """Summarise audit records as counts anyone can recompute.

    Pure function of the records provided — the audited party's cooperation
    and arithmetic are not involved. When ``seller`` is given, only records
    whose ``attested_signer`` matches it are counted; the rest are reported
    as ``foreign_excluded``.

    The independence unit is the distinct verified auditor key. Verdict
    counts (``confirmed_auditors`` / ``diverged_auditors``) count auditors,
    not records: an auditor who observed divergence even once appears in
    ``diverged_auditors`` — divergence is history, and history does not
    average away. ``unobserved`` records are reported and never scored.
    """
    want_seller = seller.lower() if seller else None

    invalid_excluded = 0
    foreign_excluded = 0
    unobserved_reported = 0
    self_audits_excluded = 0
    countable = 0
    packs: set[str] = set()
    auditors: set[str] = set()
    confirmed_auditors: set[str] = set()
    diverged_auditors: set[str] = set()

    for record in records:
        ok, _reason = verify_audit_record(record)
        if not ok:
            invalid_excluded += 1
            continue
        if want_seller is not None and (
            str(record.get("attested_signer") or "").lower() != want_seller
        ):
            foreign_excluded += 1
            continue
        verdict = record["verdict"]
        if verdict == VERDICT_UNOBSERVED:
            unobserved_reported += 1
            continue
        if is_self_audit(record):
            self_audits_excluded += 1
            continue
        countable += 1
        packs.add(str(record["pack_hash"]))
        key = str(record["auditor"]["signer"]).lower()
        auditors.add(key)
        if verdict == VERDICT_CONFIRMED:
            confirmed_auditors.add(key)
        else:
            diverged_auditors.add(key)

    if not countable:
        verdict = "unaudited"
    elif diverged_auditors:
        verdict = "contested"
    else:
        verdict = "surviving"

    return {
        "n_records": len(records),
        "invalid_excluded": invalid_excluded,
        "foreign_excluded": foreign_excluded,
        "unobserved_reported": unobserved_reported,
        "self_audits_excluded": self_audits_excluded,
        "countable_records": countable,
        "packs_audited": len(packs),
        "distinct_auditors": len(auditors),
        "confirmed_auditors": len(confirmed_auditors),
        "diverged_auditors": len(diverged_auditors),
        "verdict": verdict,
        "seller": want_seller,
        "method": METHOD,
        "note": REPORT_NOTE,
    }


__all__ = [
    "AUDIT_NOTE",
    "AUDIT_VERSION",
    "METHOD",
    "REPORT_NOTE",
    "VALID_VERDICTS",
    "VERDICT_CONFIRMED",
    "VERDICT_DIVERGED",
    "VERDICT_UNOBSERVED",
    "AuditError",
    "canonical_audit_message",
    "is_self_audit",
    "perform_audit",
    "survival_report",
    "verify_audit_record",
]
