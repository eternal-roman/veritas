"""Buyer-side counterparty diligence: grounds for refusing a seller.

`veritas/payer.py` records the gap this closes. Pinning payment parameters to
a validated 402 challenge does not authenticate the seller: the challenge is
itself content from an untrusted counterparty and is the sole source of
``payTo`` and ``amount``, so a hostile seller can name any recipient at any
price and only :class:`~veritas.payer.SpendPolicy` bounds the loss. A spend cap
means the buyer pays the wrong party, for the wrong thing, at the wrong price —
just not more than N per day. That is a budget, not a decision.

Meanwhile ``CONSTITUTION.md`` tells any buyer agent what it *should* do —
fetch the constitution, check that enforcement pointers exist, weigh
aspirational articles at zero — and until now nothing in this package did it.
Every surface here was seller-side, so a buyer adopting the pattern still
needed a human to go and read a test suite.

The discipline is the buyer-side form of the one this service sells. Where the
pipeline refuses to report `no_evidence` when it could not look, this module
refuses to report FAIL when it could not check: **UNVERIFIABLE is not FAIL.**
"I could not check this seller" and "this seller failed the check" are
different facts. Both refuse a payment, because the gate is fail-closed, but a
buyer answers them differently — FAIL means find another seller, UNVERIFIABLE
means fix your own fetch path and retry.

What these checks are evidence of, stated so it is not overread: cross-document
consistency and register integrity. **None of them proves the seller will
deliver.** A careful liar with a coherent set of documents passes every one.
This raises the cost of dishonesty and gives a buyer machine-checkable grounds
to refuse; it is not proof of honesty and must not be described as such.

No network I/O. :func:`assess` evaluates documents the caller already fetched,
which keeps it pure, adds no request surface to defend, and leaves the buyer
free to fetch however it likes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .payer import validate_accepts


class Verdict:
    """Outcomes, as plain strings because they travel in JSON.

    Deliberately not an ``enum.Enum``: these values are serialised into buyer
    logs and compared against decoded documents, where equality with a bare
    string is the useful behaviour.
    """

    PASS = "pass"
    FAIL = "fail"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True)
class CheckResult:
    """One named check, its verdict, and why — never just a boolean."""

    name: str
    verdict: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "verdict": self.verdict, "detail": self.detail}


@dataclass(frozen=True)
class DiligencePolicy:
    """What this buyer requires of a counterparty. Data, no behaviour.

    Every requirement can be waived, because a buyer's risk appetite is the
    buyer's business. Waiving them all is itself refused — see :func:`assess`.
    """

    require_challenge_matches_discovery: bool = True
    require_constitution: bool = True
    require_gap_register: bool = True
    require_trust_self_disclosure: bool = True
    #: A seller whose register enforces nothing has published prose, not norms.
    min_enforced_articles: int = 1


@dataclass(frozen=True)
class DiligenceReport:
    """The verdict, and every check that produced it."""

    verdict: str
    checks: tuple[CheckResult, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return self.verdict == Verdict.PASS

    @property
    def reasons(self) -> tuple[str, ...]:
        """Details of the checks that did not pass. Empty iff the report passed."""
        return tuple(c.detail for c in self.checks if c.verdict != Verdict.PASS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "checks": [c.to_dict() for c in self.checks],
            "reasons": list(self.reasons),
        }


def _mapping(value: object) -> dict | None:
    """A document we can read, or None. `bool` is not a mapping despite `int`."""
    return value if isinstance(value, dict) else None


def _first_accepts(document: object) -> object | None:
    """The first x402 `accepts` entry of a discovery or challenge document."""
    doc = _mapping(document)
    entries = doc.get("accepts") if doc is not None else (
        document if isinstance(document, list) else None
    )
    if not isinstance(entries, list) or not entries:
        return None
    return entries[0]


def _same(left: object, right: object) -> bool:
    """Case-insensitive equality: EVM addresses differing only in hex casing
    are the same address, and `validate_accepts` preserves caller casing
    rather than silently rewriting it."""
    return str(left).strip().lower() == str(right).strip().lower()


def check_challenge_matches_discovery(challenge: object, discovery: object) -> CheckResult:
    """The 402 must agree with what the seller advertises publicly.

    The strongest check available here, and the only one needing no trust at
    all: it asks two of the seller's own documents to agree. A seller that
    advertises one payout address and then bills another is compromised or
    hostile, and nothing else in the buyer path notices.

    Address, network and asset must match. The amount is compared one-sided —
    charging *less* than advertised is not fraud against the buyer, so only an
    amount exceeding the advertised price fails. Atomic units throughout; the
    human-readable price string is never compared.
    """
    name = "challenge_matches_discovery"
    raw_challenge = _first_accepts(challenge)
    raw_discovery = _first_accepts(discovery)
    if raw_challenge is None or raw_discovery is None:
        missing = "challenge" if raw_challenge is None else "discovery"
        return CheckResult(name, Verdict.UNVERIFIABLE,
                           f"no readable x402 accepts entry in the {missing} document")

    offered, offered_problems = validate_accepts(raw_challenge)
    advertised, advertised_problems = validate_accepts(raw_discovery)
    if offered is None:
        return CheckResult(name, Verdict.UNVERIFIABLE,
                           f"challenge did not validate: {'; '.join(offered_problems)}")
    if advertised is None:
        return CheckResult(name, Verdict.UNVERIFIABLE,
                           f"discovery did not validate: {'; '.join(advertised_problems)}")

    mismatches: list[str] = []
    if not _same(offered.pay_to, advertised.pay_to):
        mismatches.append(
            f"pay_to {offered.pay_to} is not the advertised {advertised.pay_to}")
    if not _same(offered.network, advertised.network):
        mismatches.append(
            f"network {offered.network} is not the advertised {advertised.network}")
    if not _same(offered.asset, advertised.asset):
        mismatches.append(
            f"asset {offered.asset} is not the advertised {advertised.asset}")
    if offered.amount_atomic > advertised.amount_atomic:
        mismatches.append(
            f"amount {offered.amount_atomic} exceeds the advertised "
            f"{advertised.amount_atomic}")

    if mismatches:
        return CheckResult(name, Verdict.FAIL,
                           "challenge contradicts discovery: " + "; ".join(mismatches))
    return CheckResult(name, Verdict.PASS,
                       "challenge agrees with advertised discovery on payee, "
                       "network and asset, and does not exceed the advertised price")


def check_register_integrity(constitution: object, minimum_enforced: int) -> CheckResult:
    """Re-run the seller's own meta-test instead of trusting that it passed.

    An article claiming L1 must name something that fails when the norm is
    broken; an article marked aspirational must not also claim enforcement.
    A register that enforces nothing is prose, not norms.
    """
    name = "register_integrity"
    doc = _mapping(constitution)
    if doc is None:
        return CheckResult(name, Verdict.UNVERIFIABLE, "no readable constitution document")
    articles = doc.get("articles")
    if not isinstance(articles, list) or not articles:
        return CheckResult(name, Verdict.UNVERIFIABLE,
                           "constitution document declares no articles")

    problems: list[str] = []
    enforced = 0
    for article in articles:
        entry = _mapping(article)
        if entry is None:
            problems.append("an article is not a mapping")
            continue
        article_id = entry.get("id") or "<unidentified>"
        level = str(entry.get("evidence_level") or "").upper()
        pointers = _enforcement_pointers(entry.get("enforcement"))
        if level == "L1":
            if not pointers:
                problems.append(f"{article_id} claims L1 but names no enforcement")
            else:
                enforced += 1
        elif level == "L0":
            if pointers:
                problems.append(
                    f"{article_id} is aspirational but also claims enforcement")
        else:
            problems.append(f"{article_id} declares no usable evidence level")

    if enforced < minimum_enforced:
        problems.append(
            f"only {enforced} enforced articles, below the required {minimum_enforced}")

    if problems:
        return CheckResult(name, Verdict.FAIL,
                           "register is not internally consistent: " + "; ".join(problems))
    return CheckResult(name, Verdict.PASS,
                       f"{enforced} articles carry enforcement pointers and no "
                       "aspirational article claims to be enforced")


def _enforcement_pointers(enforcement: object) -> list[str]:
    """Pointers named by an article, tolerating both shapes seen in the wild:
    a list of ``{kind, pointer}`` mappings, or a bare non-empty string."""
    if isinstance(enforcement, str):
        return [enforcement] if enforcement.strip() else []
    if not isinstance(enforcement, list):
        return []
    pointers = []
    for item in enforcement:
        if isinstance(item, str) and item.strip():
            pointers.append(item)
        elif isinstance(item, dict):
            pointer = item.get("pointer")
            if isinstance(pointer, str) and pointer.strip():
                pointers.append(pointer)
    return pointers


def check_gap_register_present(constitution: object) -> CheckResult:
    """A seller declaring no open gaps is claiming perfection.

    Deliberately inverted relative to intuition. In a venue where sellers
    describe themselves, an empty defect register is evidence of concealment,
    not of quality — every non-trivial service has open gaps, and the ones
    worth buying from say which.
    """
    name = "gap_register_present"
    doc = _mapping(constitution)
    if doc is None:
        return CheckResult(name, Verdict.UNVERIFIABLE, "no readable constitution document")
    gaps = doc.get("known_gaps")
    if not isinstance(gaps, list) or not gaps:
        return CheckResult(name, Verdict.FAIL,
                           "seller declares no known gaps, which claims perfection")

    open_gaps = [g for g in gaps if _mapping(g) and
                 str(g.get("status") or "").lower() == "open"]
    if not open_gaps:
        return CheckResult(name, Verdict.FAIL,
                           f"all {len(gaps)} declared gaps are closed and none is open, "
                           "which claims present perfection")
    return CheckResult(name, Verdict.PASS,
                       f"{len(open_gaps)} open gaps declared of {len(gaps)} registered")


def check_trust_self_disclosure(trust: object) -> CheckResult:
    """A self-reported score must say that it is self-reported.

    A seller publishing a bare number is *less* trustworthy than one
    publishing UNPROVEN: the second is telling the buyer what the number is
    worth. This checks the disclosure, never the value — a high score is not
    evidence of anything here.
    """
    name = "trust_self_disclosure"
    doc = _mapping(trust)
    if doc is None:
        return CheckResult(name, Verdict.UNVERIFIABLE, "no readable trust document")
    basis = _mapping(doc.get("basis"))
    if basis is None:
        return CheckResult(name, Verdict.FAIL,
                           "trust document publishes a score with no basis")

    disclosure = basis.get("self_reported")
    if not isinstance(disclosure, str) or not disclosure.strip():
        return CheckResult(name, Verdict.FAIL,
                           "trust document does not disclose that it is self-reported")
    if basis.get("min_samples") is None:
        return CheckResult(name, Verdict.FAIL,
                           "trust document names no sample floor, so the score "
                           "cannot be weighed")
    return CheckResult(name, Verdict.PASS,
                       "trust document discloses that it is self-reported and "
                       "names its sample floor")


def assess(
    *,
    challenge: object = None,
    discovery: object = None,
    constitution: object = None,
    trust: object = None,
    policy: DiligencePolicy | None = None,
) -> DiligenceReport:
    """Evaluate a counterparty from documents it publishes.

    Pure: no I/O, no clock, no global state, and it raises nothing — every
    failure is a result, matching the contract `veritas.payer` already keeps.

    The fold is deliberate. Any FAIL makes the report FAIL even if other
    checks could not run, because an observed defect outranks a missing
    observation. Only when nothing failed and something could not be checked
    is the report UNVERIFIABLE.
    """
    policy = policy or DiligencePolicy()
    checks: list[CheckResult] = []

    if policy.require_challenge_matches_discovery:
        checks.append(check_challenge_matches_discovery(challenge, discovery))
    if policy.require_constitution:
        checks.append(check_register_integrity(constitution, policy.min_enforced_articles))
    if policy.require_gap_register:
        checks.append(check_gap_register_present(constitution))
    if policy.require_trust_self_disclosure:
        checks.append(check_trust_self_disclosure(trust))

    if not checks:
        # A policy that requires nothing has checked nothing, and "I looked at
        # nothing" must never read as "this seller is fine".
        return DiligenceReport(Verdict.UNVERIFIABLE, (
            CheckResult("policy", Verdict.UNVERIFIABLE,
                        "policy requires no checks, so nothing was verified"),
        ))

    if any(c.verdict == Verdict.FAIL for c in checks):
        verdict = Verdict.FAIL
    elif any(c.verdict == Verdict.UNVERIFIABLE for c in checks):
        verdict = Verdict.UNVERIFIABLE
    else:
        verdict = Verdict.PASS
    return DiligenceReport(verdict, tuple(checks))
