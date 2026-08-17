"""Composed standing: one counts document over the whole evidence hierarchy.

Survival records (`veritas.audit`) and warranty challenge outcomes
(`veritas.warranty`) each produce checkable counts. This module composes
them — with the self-reported trust document as the explicit floor — into
the single standing view a buyer's spend policy can consume, ordered by
evidential strength (docs/program/FALSIFIABLE_COMMERCE.md §3.4):

1. ``forfeited_bond`` — a fired challenge on a seller-signed warranty;
   settlement-grade once the bond was an EIP-3009 lock that
   ``settle_forfeit`` submitted (W1). Commitment-only warranties stay
   labeled ``signed_commitment_not_escrow``.
2. ``survived_challenge`` — an adversary staked to refute and failed
3. ``audit`` — survival records, per distinct auditor key (A26 rules)
4. ``expired_unchallenged`` — silence; the weakest positive there is
5. ``self_reported`` — the floor (G10); included only as what it is

Independence discipline carries through every level: challenge outcomes
count per distinct warranty, audits per distinct auditor key, never per
record volume. The composed verdict is dominated by the strongest evidence
present: any forfeit → ``forfeited``; else observed divergence →
``contested``; else survived challenges upgrade ``surviving`` to
``surviving_challenged``; else the audit verdict stands.

Honesty boundaries: every input set may be curated by whoever assembled it
(G11 closed only for published auditor sets); a forfeited escrowed bond is
a settlement event once ``settle_forfeit`` succeeds; this module never
fetches anything — it is a pure function over records the caller holds,
per A26.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from veritas.audit import survival_report
from veritas.warranty import (
    OUTCOME_FIRED,
    OUTCOME_NOT_FIRED,
    OUTCOME_UNDECIDABLE,
)

METHOD = "veritas.standing.v1"

EVIDENCE_HIERARCHY = (
    "forfeited_bond",
    "survived_challenge",
    "audit",
    "expired_unchallenged",
    "self_reported",
)

STANDING_NOTE = (
    "composed from records the holder provided; surviving audits require "
    "an auditor publication (withheld published records → curated); "
    "forfeit_binding is eip3009_authorization when any fired outcome "
    "carried an escrowed lock, else signed_commitment_not_escrow"
)

VERDICT_FORFEITED = "forfeited"
VERDICT_CONTESTED = "contested"
VERDICT_SURVIVING_CHALLENGED = "surviving_challenged"


def standing_report(
    *,
    audit_records: list[Mapping[str, Any]] | None = None,
    audit_publication: list[Mapping[str, Any]] | None = None,
    challenge_outcomes: list[Mapping[str, Any]] | None = None,
    expired_unchallenged_warranties: int = 0,
    self_reported: Mapping[str, Any] | None = None,
    seller: str | None = None,
) -> dict[str, Any]:
    """Compose the full evidence hierarchy into counts anyone can recompute.

    ``challenge_outcomes`` are deduplicated by ``warranty_hash`` — many
    evaluations of one warranty are one fact about the seller, the same
    one-key-one-witness rule the audit layer applies to auditors. A
    warranty that appears with both a ``fired`` and a ``not_fired`` outcome
    counts as fired: outcomes are deterministic over the same bytes, so a
    conflict means differing inputs, and the seller-signed refuted variant
    is the one that cannot be explained away.
    """
    audits = survival_report(
        list(audit_records or []),
        seller=seller,
        publication=audit_publication,
    )

    fired_warranties: set[str] = set()
    survived_warranties: set[str] = set()
    undecidable_reported = 0
    malformed_excluded = 0
    bindings: set[str] = set()
    for outcome in challenge_outcomes or []:
        kind = outcome.get("outcome")
        wid = outcome.get("warranty_hash")
        if kind == OUTCOME_UNDECIDABLE:
            undecidable_reported += 1
            continue
        if kind not in (OUTCOME_FIRED, OUTCOME_NOT_FIRED) or not isinstance(wid, str):
            malformed_excluded += 1
            continue
        if kind == OUTCOME_FIRED:
            fired_warranties.add(wid)
            binding = (outcome.get("forfeit") or {}).get("binding")
            if isinstance(binding, str) and binding:
                bindings.add(binding)
        else:
            survived_warranties.add(wid)
    survived_warranties -= fired_warranties  # fired dominates per warranty

    if fired_warranties:
        verdict = VERDICT_FORFEITED
    elif audits["verdict"] == "contested":
        verdict = VERDICT_CONTESTED
    elif survived_warranties:
        verdict = VERDICT_SURVIVING_CHALLENGED
    else:
        verdict = audits["verdict"]  # surviving | unaudited

    if "eip3009_authorization" in bindings:
        forfeit_binding = "eip3009_authorization"
    else:
        forfeit_binding = "signed_commitment_not_escrow"

    return {
        "hierarchy": list(EVIDENCE_HIERARCHY),
        "forfeited_bonds": len(fired_warranties),
        "forfeit_binding": forfeit_binding,
        "survived_challenges": len(survived_warranties),
        "undecidable_challenges_reported": undecidable_reported,
        "challenge_records_excluded": malformed_excluded,
        "audits": audits,
        "expired_unchallenged": expired_unchallenged_warranties,
        "self_reported": {
            "included": self_reported is not None,
            "recommendation": (self_reported or {}).get("recommendation"),
            "role": "operator counters only; not the independent score",
        },
        "verdict": verdict,
        "seller": seller.lower() if seller else None,
        "method": METHOD,
        "note": STANDING_NOTE,
    }


__all__ = [
    "EVIDENCE_HIERARCHY",
    "METHOD",
    "STANDING_NOTE",
    "VERDICT_CONTESTED",
    "VERDICT_FORFEITED",
    "VERDICT_SURVIVING_CHALLENGED",
    "standing_report",
]
