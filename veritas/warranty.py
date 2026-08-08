"""Falsifiable commerce, W0: bonded warranties with deterministic challenges.

The methodology this implements is derived and bounded in
docs/program/FALSIFIABLE_COMMERCE.md (read it first; the mandate and the
prior-art differentiation live there). One sentence: a seller ships, inside
the signed deliverable, the executable experiment that would refute it —
a **falsification predicate** from the registry below — plus a bonded stake
and a challenge window, so that disputes terminate in re-execution any party
can perform, and checking other agents' work becomes a paid occupation
rather than a public good.

The Popperian inversion, mechanized: the seller does not certify it is
right; it authors the procedure by which it may be proven wrong, and prices
its own confidence by staking on that procedure. What cannot be given a
decidable refutation procedure is labeled class U — unwarrantable — and the
label, not a pretended warranty, is the honest product (the same move that
made `unavailable` ≠ `no_evidence` the product of the status layer).

Design rules inherited from this repository:

* **Predicates are registered, versioned, deterministic, and total.** Both
  parties (and any third party) compute the same verdict from the same
  bytes. No arbiter, no vote, no model call in D0.
* **A malformed deliverable fires.** The warranty binds the deliverable to
  be the warranted shape; a seller cannot escape into `undecidable` by
  shipping bytes the predicate cannot read. `undecidable` is reserved for
  defects of the *challenge context* (invalid warranty, wrong bytes,
  closed window) — the layer's "we could not decide", kept apart from both
  fired and not_fired, exactly as `unavailable` is kept apart from
  `no_evidence` and `unobserved` from `diverged`.
* **Origin divergence never forfeits.** Pages change (the P7 boundary), so
  no D0/D1 predicate may condition a bond on what an origin serves later.
* **No second crypto stack.** Signatures reuse `veritas.notary.sign`
  primitives with a domain-separated message prefix, so a warranty
  signature can never verify as an evidence attestation or an audit record.

Honesty boundaries:

* Bonds here are **signed commitments, not escrowed value** — no settlement
  has ever run from this codebase (constitution gap G12, witnessed). The
  forfeit indicated by a fired challenge is a claim the rails must later
  enforce (W1), not money that moved.
* Deterministic predicates cover a subset of quality: an answer can be
  worthless yet unfalsified. Bond size signals confidence *about the
  predicate*, nothing more.
* Sellers author their own predicates and will author weak ones; the
  counter-force is that the predicate set is visible metadata a competing
  seller can beat — a market force, asserted but not yet demonstrated.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from veritas.custody import verify_chain_records
from veritas.hashing import compute_content_hash
from veritas.notary.sign import (
    NotarySignError,
    OperatorSigner,
    recover_attestation_signer,
    verify_attestation,
)

METHOD = "veritas.warranty.v1"
WARRANTY_VERSION = "veritas-warranty-v1"

CLASS_D0 = "D0"
CLASS_D1 = "D1"
CLASS_D2 = "D2"
CLASS_U = "U"

OUTCOME_FIRED = "fired"
OUTCOME_NOT_FIRED = "not_fired"
OUTCOME_UNDECIDABLE = "undecidable"

WARRANTY_NOTE = (
    "seller-authored falsification predicates over the delivered bytes; "
    "bond is a signed commitment, not escrowed value (gap G12); "
    "origin divergence never forfeits (P7 boundary); "
    "unfalsified does not mean useful"
)

REPORT_NOTE = (
    "counts over the outcomes provided; every outcome is recomputable by "
    "anyone holding the warranty and the deliverable; forfeits become "
    "unomittable only once bonds are escrowed on payment rails (W1)"
)

UNWARRANTED_NOTE = (
    "no decidable refutation procedure exists for this content; sold "
    "unwarranted and labeled, never dressed in an undischargeable warranty"
)

_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
_ATOMIC_RE = re.compile(r"^[0-9]+$")


class WarrantyError(ValueError):
    """Warranty construction or evaluation could not proceed."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def canonical_response_hash(response: Mapping[str, Any]) -> str:
    """Hash binding a warranty to one deliverable's exact content."""
    payload = json.dumps(
        response, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return compute_content_hash(payload)


# --- D0 predicate registry ---------------------------------------------------
#
# Each predicate: deterministic, total, over the delivered response alone.
# Returns (fired, reason). A deliverable too malformed to read fires with
# reason "deliverable_malformed" — the warranted shape is part of the good.


def _predicate_custody_chain_invalid(response: Mapping[str, Any]) -> tuple[bool, str]:
    chain = response.get("custody_chain")
    if not isinstance(chain, list) or not chain:
        return True, "deliverable_malformed"
    try:
        ok = verify_chain_records(chain)
    except Exception:
        return True, "deliverable_malformed"
    if not ok:
        return True, "custody_chain_invalid"
    return False, "custody_chain_verifies"


def _predicate_citation_unbacked(response: Mapping[str, Any]) -> tuple[bool, str]:
    claims = response.get("claims")
    evidence = response.get("evidence")
    if not isinstance(claims, list) or not isinstance(evidence, list):
        return True, "deliverable_malformed"
    delivered = set()
    for item in evidence:
        if not isinstance(item, Mapping):
            return True, "deliverable_malformed"
        delivered.add(item.get("content_hash"))
    for claim in claims:
        if not isinstance(claim, Mapping):
            return True, "deliverable_malformed"
        if claim.get("evidence_hash") not in delivered:
            return True, "citation_unbacked"
    return False, "every_claim_cites_delivered_evidence"


def _predicate_status_incoherent(response: Mapping[str, Any]) -> tuple[bool, str]:
    status = response.get("status")
    claims = response.get("claims")
    if status not in ("completed", "refused", "unavailable") or not isinstance(
        claims, list
    ):
        return True, "deliverable_malformed"
    if status == "completed" and not claims:
        return True, "completed_without_claims"
    if status in ("refused", "unavailable") and claims:
        return True, "non_answer_carries_claims"
    if status == "unavailable" and response.get("billable") is not False:
        # Invariant 3, bonded: our own failure is never billable.
        return True, "billed_own_failure"
    return False, "status_coheres"


def _predicate_attestation_forged(response: Mapping[str, Any]) -> tuple[bool, str]:
    attestation = response.get("attestation")
    record = response.get("evidence_record")
    if attestation is None:
        return False, "no_attestation_warranted"
    if not isinstance(attestation, Mapping) or not isinstance(record, Mapping):
        return True, "deliverable_malformed"
    ok, _reason = verify_attestation(record, attestation)
    if not ok:
        return True, "attestation_forged"
    return False, "attestation_recovers"


PredicateFn = Callable[[Mapping[str, Any]], tuple[bool, str]]

PREDICATES: dict[str, dict[str, Any]] = {
    "custody_chain_invalid.v1": {
        "class": CLASS_D0,
        "fn": _predicate_custody_chain_invalid,
        "refutes": "the delivered custody chain fails hash-chain verification",
    },
    "citation_unbacked.v1": {
        "class": CLASS_D0,
        "fn": _predicate_citation_unbacked,
        "refutes": "a delivered claim cites a hash absent from delivered evidence",
    },
    "status_incoherent.v1": {
        "class": CLASS_D0,
        "fn": _predicate_status_incoherent,
        "refutes": "the status taxonomy is violated by the delivered body "
                   "(completed without claims, refusal carrying claims, or a "
                   "billable unavailable)",
    },
    "attestation_forged.v1": {
        "class": CLASS_D0,
        "fn": _predicate_attestation_forged,
        "refutes": "a delivered attestation does not recover to its claimed signer",
    },
}


def falsifiability_class(predicate_ids: list[str]) -> str:
    """The class of a warranty is the weakest class among its predicates."""
    if not predicate_ids:
        return CLASS_U
    order = {CLASS_D0: 0, CLASS_D1: 1, CLASS_D2: 2}
    worst = CLASS_D0
    for pid in predicate_ids:
        meta = PREDICATES.get(pid)
        if meta is None:
            raise WarrantyError(f"unknown_predicate:{pid}")
        if order[meta["class"]] > order[worst]:
            worst = meta["class"]
    return worst


def unwarranted_label() -> dict[str, Any]:
    """The honest alternative to a warranty that could not be discharged."""
    return {
        "falsifiability_class": CLASS_U,
        "warranted": False,
        "note": UNWARRANTED_NOTE,
    }


# --- warranty construction and verification ----------------------------------


def canonical_warranty_message(warranty: Mapping[str, Any]) -> str:
    """The EIP-191 text a seller signs. Domain-separated from evidence
    attestations and audit records by the version prefix."""
    try:
        response_hash = warranty["response_hash"]
        predicates = warranty["predicates"]
        bond = warranty["bond"]
        window = warranty["window_seconds"]
        issued_at = warranty["issued_at"]
    except KeyError as exc:
        raise WarrantyError(f"warranty missing field for signing: {exc}") from exc
    return "\n".join(
        (
            WARRANTY_VERSION,
            f"response_hash: {response_hash}",
            f"predicates: {','.join(predicates)}",
            f"bond: {bond['amount_atomic']} {bond['asset']} {bond['network']}",
            f"window_seconds: {window}",
            f"issued_at: {issued_at}",
        )
    )


def build_warranty(
    response: Mapping[str, Any],
    *,
    predicates: list[str],
    bond: Mapping[str, str],
    window_seconds: int,
    signer: OperatorSigner,
) -> dict[str, Any]:
    """Attach a bonded, signed falsification warranty to a deliverable.

    Refuses (loudly, never silently weakened) when: no predicates are named
    — class-U content must ship the :func:`unwarranted_label` instead of a
    vacuous warranty; a predicate is unregistered; the bond or window is
    malformed; or a named predicate already fires on the deliverable — a
    seller must not be able to sell a warranty it can see is already lost,
    because that converts the buyer's challenge stake into seller revenue.
    """
    if not predicates:
        raise WarrantyError("unwarrantable_use_unwarranted_label")
    fclass = falsifiability_class(predicates)  # raises on unknown ids
    for key in ("amount_atomic", "asset", "network"):
        if not isinstance(bond.get(key), str) or not bond[key]:
            raise WarrantyError(f"bond_malformed:{key}")
    if not _ATOMIC_RE.match(bond["amount_atomic"]) or int(bond["amount_atomic"]) <= 0:
        raise WarrantyError("bond_malformed:amount_atomic")
    if not isinstance(window_seconds, int) or window_seconds <= 0:
        raise WarrantyError("window_malformed")
    for pid in predicates:
        fired, reason = PREDICATES[pid]["fn"](response)
        if fired:
            raise WarrantyError(f"predicate_already_fires:{pid}:{reason}")

    warranty: dict[str, Any] = {
        "warranty_version": WARRANTY_VERSION,
        "method": METHOD,
        "response_hash": canonical_response_hash(response),
        "predicates": list(predicates),
        "falsifiability_class": fclass,
        "bond": {key: bond[key] for key in ("amount_atomic", "asset", "network")},
        "bond_binding": "signed_commitment_not_escrow",  # G12, stated on the wire
        "window_seconds": window_seconds,
        "issued_at": _iso(_now()),
        "note": WARRANTY_NOTE,
    }
    message = canonical_warranty_message(warranty)
    warranty["seller"] = {
        "scheme": "eip191",
        "signer": signer.address.lower(),
        "signature": signer.sign_text(message),
        "message": message,
    }
    return warranty


def verify_warranty(
    warranty: Mapping[str, Any], response: Mapping[str, Any] | None = None
) -> tuple[bool, str]:
    """Check a warranty's shape, signature, and (optionally) its binding to
    a deliverable. Stable reason codes, tampered `message` cannot pass."""
    if not warranty:
        return False, "warranty_missing"
    if warranty.get("warranty_version") != WARRANTY_VERSION:
        return False, "version_mismatch"
    predicates = warranty.get("predicates")
    if not isinstance(predicates, list) or not predicates:
        return False, "predicates_missing"
    for pid in predicates:
        if pid not in PREDICATES:
            return False, "predicate_unknown"
    issued_at = warranty.get("issued_at")
    if not isinstance(issued_at, str) or not _TS_RE.match(issued_at):
        return False, "issued_at_malformed"
    if not isinstance(warranty.get("window_seconds"), int):
        return False, "window_malformed"
    seller = warranty.get("seller")
    if not isinstance(seller, Mapping):
        return False, "seller_missing"
    if seller.get("scheme") != "eip191":
        return False, "scheme_mismatch"
    signature = seller.get("signature")
    if not isinstance(signature, str):
        return False, "signature_missing"
    try:
        message = canonical_warranty_message(warranty)
    except WarrantyError:
        return False, "warranty_incomplete"
    published = seller.get("message")
    if published is not None and published != message:
        return False, "message_mismatch"
    try:
        recovered = recover_attestation_signer(message, signature)
    except NotarySignError:
        return False, "signature_invalid"
    claimed = seller.get("signer")
    if not isinstance(claimed, str) or claimed.lower() != recovered:
        return False, "signer_mismatch"
    if response is not None and canonical_response_hash(response) != warranty.get(
        "response_hash"
    ):
        return False, "response_mismatch"
    return True, "ok"


# --- deterministic challenge evaluation --------------------------------------


def evaluate_challenge(
    warranty: Mapping[str, Any],
    response: Mapping[str, Any],
    *,
    challenged_at: str | None = None,
) -> dict[str, Any]:
    """Decide a challenge. Pure function: any party computes the same outcome.

    ``fired`` — a warranted predicate fires on the deliverable; the bond
    commitment is forfeit (enforceable only at W1; G12).
    ``not_fired`` — no warranted predicate fires; the challenger's stake
    goes to the seller under venue rules.
    ``undecidable`` — the challenge context is defective (invalid warranty,
    wrong bytes, closed window): neither side wins, and the reason says
    which defect. Kept apart from both verdicts, as every honest layer here
    keeps its could-not-decide apart from its yes and its no.
    """
    moment = challenged_at or _iso(_now())

    ok, reason = verify_warranty(warranty, response)
    if not ok:
        code = "response_mismatch" if reason == "response_mismatch" else "warranty_invalid"
        return _outcome(OUTCOME_UNDECIDABLE, f"{code}:{reason}", warranty, [], moment)

    if not isinstance(moment, str) or not _TS_RE.match(moment):
        return _outcome(OUTCOME_UNDECIDABLE, "challenged_at_malformed", warranty, [], moment)
    issued = _parse_iso(warranty["issued_at"])
    closes = issued + timedelta(seconds=int(warranty["window_seconds"]))
    when = _parse_iso(moment)
    if when < issued or when > closes:
        return _outcome(OUTCOME_UNDECIDABLE, "window_closed", warranty, [], moment)

    results = []
    fired_any = False
    for pid in warranty["predicates"]:
        fired, why = PREDICATES[pid]["fn"](response)
        fired_any = fired_any or fired
        results.append({"predicate": pid, "fired": fired, "reason": why})

    if fired_any:
        return _outcome(OUTCOME_FIRED, "predicate_fired", warranty, results, moment)
    return _outcome(OUTCOME_NOT_FIRED, "no_predicate_fired", warranty, results, moment)


def _outcome(
    outcome: str,
    reason: str,
    warranty: Mapping[str, Any],
    results: list[dict[str, Any]],
    challenged_at: str,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "method": METHOD,
        "outcome": outcome,
        "reason": reason,
        "predicate_results": results,
        "challenged_at": challenged_at,
        "warranty_hash": compute_content_hash(
            json.dumps(
                {k: warranty.get(k) for k in ("response_hash", "predicates", "bond",
                                              "window_seconds", "issued_at")},
                sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            )
        ),
        "note": WARRANTY_NOTE,
    }
    if outcome == OUTCOME_FIRED:
        record["forfeit"] = {
            **dict(warranty.get("bond") or {}),
            "binding": "signed_commitment_not_escrow",
        }
    return record


def warranty_report(outcomes: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Counts over challenge outcomes, in the support.py tradition.

    Every outcome is recomputable by any holder of the warranty and the
    deliverable, so this report needs no signatures to be checkable —
    what it cannot claim is completeness (outcomes may be withheld; the
    forfeit half of that asymmetry closes only at W1, when a forfeit is a
    settlement event rather than a document).
    """
    fired = sum(1 for o in outcomes if o.get("outcome") == OUTCOME_FIRED)
    not_fired = sum(1 for o in outcomes if o.get("outcome") == OUTCOME_NOT_FIRED)
    undecidable = sum(1 for o in outcomes if o.get("outcome") == OUTCOME_UNDECIDABLE)
    other = len(outcomes) - fired - not_fired - undecidable
    return {
        "n_outcomes": len(outcomes),
        "fired": fired,
        "not_fired": not_fired,
        "undecidable_reported": undecidable,
        "malformed_excluded": other,
        "method": METHOD,
        "note": REPORT_NOTE,
    }


__all__ = [
    "CLASS_D0",
    "CLASS_D1",
    "CLASS_D2",
    "CLASS_U",
    "METHOD",
    "OUTCOME_FIRED",
    "OUTCOME_NOT_FIRED",
    "OUTCOME_UNDECIDABLE",
    "PREDICATES",
    "REPORT_NOTE",
    "UNWARRANTED_NOTE",
    "WARRANTY_NOTE",
    "WARRANTY_VERSION",
    "WarrantyError",
    "build_warranty",
    "canonical_response_hash",
    "canonical_warranty_message",
    "evaluate_challenge",
    "falsifiability_class",
    "unwarranted_label",
    "verify_warranty",
    "warranty_report",
]
