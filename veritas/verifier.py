"""Standalone verification of a Veritas response. Zero dependencies.

Constitution article A12 says a buyer "can verify every published hash and
receipt without the seller's cooperation". That was true only in a narrow
sense. The check lived in ``veritas.custody``, and reaching it meant
``pip install veritas-research`` — which drags in FastAPI, uvicorn and
pydantic. Asking a buyer to install a seller's *web server* in order to audit
the seller's *receipt* is not independence, and a buyer running the seller's
own verification code would validate the seller's forgeries with it.

**This file is the answer, and it is deliberately a single file.** It imports
nothing from ``veritas`` and nothing off the standard library. Copy it out of
the repository, vendor it, read all of it in one sitting, and run it::

    python verifier.py receipt.json
    python -c "import verifier, json; print(verifier.verify_response(json.load(open('r.json'))).valid)"

It re-implements the hash chain rather than importing it. That duplication is
the point: two independent implementations that agree is a stronger statement
than one implementation asserting it is right. ``tests/test_verifier.py``
pins the agreement differentially against ``veritas.custody`` on real pipeline
output and on tampered variants, so the copy cannot silently drift.

**What agreement here is and is not evidence of.** A valid result means the
records are internally consistent: nothing was altered after the chain was
built, every excerpt still hashes to its published hash, and every claim cites
evidence that was actually delivered. It does **not** mean the seller ever
contacted the URLs it names, that the excerpts appear at those URLs, or that
the content is true. A seller that fabricated evidence and then hashed its own
fabrication produces a chain that verifies perfectly. Tamper-evidence is not
attestation — the response's own ``attests`` field says the same thing.

Both authors of the two implementations are the same party, so this raises the
cost of a silent bug, not the cost of a deliberate one.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field

__all__ = [
    "CheckOutcome",
    "VerificationReport",
    "compute_content_hash",
    "main",
    "normalize_content",
    "verify_chain",
    "verify_response",
]

VERIFIER_VERSION = "1"

EXIT_VALID = 0
EXIT_INVALID = 1
#: The input could not be read. Not a statement about the seller.
EXIT_UNREADABLE = 2


@dataclass(frozen=True)
class CheckOutcome:
    """One named check and why it landed where it did."""

    name: str
    valid: bool
    detail: str

    def to_dict(self) -> dict:
        return {"name": self.name, "valid": self.valid, "detail": self.detail}


@dataclass(frozen=True)
class VerificationReport:
    checks: tuple[CheckOutcome, ...] = field(default_factory=tuple)

    @property
    def valid(self) -> bool:
        return bool(self.checks) and all(c.valid for c in self.checks)

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(c.detail for c in self.checks if not c.valid)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "verifier_version": VERIFIER_VERSION,
            "checks": [c.to_dict() for c in self.checks],
            "failures": list(self.failures),
            "attests": (
                "these records are internally consistent; not that the seller "
                "contacted the URLs it names, nor that the content is true"
            ),
        }


# -- the two primitives, re-implemented ------------------------------------


def normalize_content(text: str) -> str:
    """Deterministic normalisation applied before hashing evidence.

    Must match ``veritas.hashing.normalize_content`` exactly; a differential
    test asserts it does. Any divergence makes every hash disagree.
    """
    if not text:
        return ""
    text = str(text)
    text = text.encode("utf-8", errors="replace").decode("utf-8")
    text = unicodedata.normalize("NFC", text)
    text = text.lstrip("﻿")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def compute_content_hash(content: str) -> str:
    digest = hashlib.sha256(normalize_content(content).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _event_hash(record: dict) -> str:
    """Recompute one custody event's hash from its own fields.

    Field order and JSON separators are load-bearing: the seller hashes a
    canonical form, so this must serialise identically or nothing verifies.
    """
    data = {
        "event_type": record.get("event_type", ""),
        "actor": record.get("actor", ""),
        "timestamp": record.get("timestamp", ""),
        "prev_hash": record.get("prev_hash"),
        "payload": record.get("payload", {}),
    }
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_chain(events: object) -> CheckOutcome:
    """Every event hashes to its recorded value and links to its predecessor."""
    name = "custody_chain"
    if events is None:
        return CheckOutcome(name, False, "response carries no custody_chain")
    if not isinstance(events, list):
        return CheckOutcome(name, False, "custody_chain is not a list")
    if not events:
        # An empty chain is vacuously consistent but attests to nothing, and a
        # response claiming custody while carrying none should not read valid.
        return CheckOutcome(name, False, "custody_chain is empty")

    prev = None
    for index, record in enumerate(events):
        if not isinstance(record, dict):
            return CheckOutcome(name, False, f"event {index} is not an object")
        if _event_hash(record) != record.get("event_hash"):
            return CheckOutcome(
                name, False,
                f"event {index} ({record.get('event_type')!r}) does not hash to "
                "its recorded event_hash: it was altered after it was written")
        if record.get("prev_hash") != prev:
            return CheckOutcome(
                name, False,
                f"event {index} does not link to its predecessor: the chain was "
                "reordered, spliced or truncated")
        prev = record.get("event_hash")
    return CheckOutcome(name, True, f"{len(events)} events hash and link correctly")


# -- response-level checks -------------------------------------------------


def verify_root(response: dict, events: object) -> CheckOutcome:
    """The advertised custody_root must be the chain's last event hash."""
    name = "custody_root"
    claimed = response.get("custody_root")
    if not isinstance(events, list) or not events or not isinstance(events[-1], dict):
        return CheckOutcome(name, False, "no chain to take a root from")
    actual = events[-1].get("event_hash")
    if claimed != actual:
        return CheckOutcome(
            name, False,
            f"published custody_root {claimed!r} is not the chain's last event "
            f"hash {actual!r}")
    return CheckOutcome(name, True, "custody_root matches the chain's last event")


def verify_evidence_hashes(response: dict) -> CheckOutcome:
    """Every delivered excerpt must still hash to its published hash."""
    name = "evidence_hashes"
    evidence = response.get("evidence")
    if not isinstance(evidence, list):
        return CheckOutcome(name, False, "evidence is missing or not a list")
    if not evidence:
        # Refusals and outages legitimately carry none; there is nothing to check.
        return CheckOutcome(name, True, "no evidence delivered, nothing to check")

    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            return CheckOutcome(name, False, f"evidence {index} is not an object")
        published = item.get("content_hash")
        recomputed = compute_content_hash(item.get("excerpt") or "")
        if published != recomputed:
            return CheckOutcome(
                name, False,
                f"evidence {index} ({item.get('url')!r}) does not hash to its "
                f"published content_hash: expected {published!r}, got {recomputed!r}")
    return CheckOutcome(name, True, f"{len(evidence)} excerpts hash to their published values")


def verify_claims_are_grounded(response: dict) -> CheckOutcome:
    """Every claim must cite evidence that was actually delivered.

    A claim citing a hash absent from the response is ungrounded: the buyer
    cannot check it, which is the failure mode the whole product exists to
    prevent.
    """
    name = "claims_grounded"
    claims = response.get("claims")
    evidence = response.get("evidence")
    if not isinstance(claims, list):
        return CheckOutcome(name, False, "claims is missing or not a list")
    if not claims:
        return CheckOutcome(name, True, "no claims made, nothing to ground")

    delivered = {
        item.get("content_hash")
        for item in (evidence if isinstance(evidence, list) else [])
        if isinstance(item, dict)
    }
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            return CheckOutcome(name, False, f"claim {index} is not an object")
        cited = claim.get("evidence_hash")
        if cited not in delivered:
            return CheckOutcome(
                name, False,
                f"claim {claim.get('id', index)!r} cites evidence_hash {cited!r}, "
                "which was not delivered in this response")
    return CheckOutcome(name, True, f"{len(claims)} claims cite delivered evidence")


def verify_billing_honesty(response: dict) -> CheckOutcome:
    """An unavailable response must not be billable.

    The seller's core commercial promise, checkable by the buyer holding the
    response rather than taken on trust.
    """
    name = "billing_honesty"
    status = response.get("status")
    billable = response.get("billable")
    if status == "unavailable" and billable:
        return CheckOutcome(
            name, False,
            "response is 'unavailable' but marked billable: the seller is "
            "charging for its own failure to retrieve")
    return CheckOutcome(name, True, f"status {status!r} with billable {billable!r} is consistent")


def verify_response(response: object) -> VerificationReport:
    """Verify one Veritas response or stored receipt. Never raises."""
    if not isinstance(response, dict):
        return VerificationReport((
            CheckOutcome("input", False, "input is not a JSON object"),
        ))

    # A stored receipt may wrap the response; accept either shape.
    body = response.get("response") if isinstance(response.get("response"), dict) else response
    events = body.get("custody_chain")

    return VerificationReport((
        verify_chain(events),
        verify_root(body, events),
        verify_evidence_hashes(body),
        verify_claims_are_grounded(body),
        verify_billing_honesty(body),
    ))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return EXIT_UNREADABLE if not argv else EXIT_VALID

    path = argv[0]
    try:
        if path == "-":
            document = json.load(sys.stdin)
        else:
            with open(path, encoding="utf-8") as handle:
                document = json.load(handle)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": "unreadable_input",
                          "detail": f"{type(exc).__name__}: {path}"}, indent=2))
        return EXIT_UNREADABLE

    report = verify_response(document)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return EXIT_VALID if report.valid else EXIT_INVALID


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
