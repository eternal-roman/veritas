"""Bounded exhaustive model check of the real payer machinery.

This drives the REAL ``SpendPolicy`` and ``PaymentClient`` (with a keyless
stub signer defined below) through the FULL enumeration of a small bounded
request space — every trace of up to ``MAX_TRACE_LEN`` requests over the
request alphabet, each in its own temp dir, plus a restart variant per
multi-step trace where the policy is re-instantiated from disk mid-trace —
and asserts the semantic invariants I1–I7 over every executed trace.

Evidence level, stated per the repository's locked gate: this is L2 — the
invariants hold for the stated bounds, and for nothing beyond them. It is
not a proof of the product; larger amounts, longer traces, concurrent
processes, and real signers are all outside the checked space.

Invariants:
  I1 signed => validation passed and the model's own cap semantics allowed it
     (the stub signer counts calls; no call happens without a prior ok).
  I2 signed value == the quoted maxAmountRequired, exactly.
  I3 all nonces are unique across every signed authorization in the run.
  I4 signed amounts within a day stay <= the daily cap and <= the
     per-counterparty cap, in every trace including restart variants.
  I5 a denial means zero signer calls for that request (signer-fault
     requests excepted: there the one attempt is the injected failure).
  I6 invalid entries (unknown network / wrong asset / malformed payTo /
     zero amount) never yield a ValidatedAccepts, so never reach pay().
  I7 signer failures fail closed and the budget stays untouched: a
     signer-fault request is never paid, reports check == "signer_error",
     and every later request the model allows is still signed —
     equivalently, no denial the model does not predict. This is what makes
     the validate → policy → sign → record ordering observable: charging
     the budget before (or despite) a failed signature flips a later
     model-allowed request into a denial.
"""

from __future__ import annotations

import itertools
import json
import sys
import tempfile
from pathlib import Path

from veritas.payer import PaymentClient, SpendPolicy, validate_accepts
from veritas.x402 import USDC_ASSETS

# Bounds of the checked space — stated in the report, never implicit.
AMOUNTS = (1, 2, 3)
PER_REQUEST_CAP = 2
PER_DAY_CAP = 4
PER_COUNTERPARTY_CAP = 3
VALID_NETWORK = "eip155:8453"
UNKNOWN_NETWORK = "eip155:999999"
COUNTERPARTY_A = "0x" + "aa" * 20
COUNTERPARTY_B = "0x" + "bb" * 20
# Same on-chain address as A in a different hex casing: the per-counterparty
# cap must treat every spelling of one address as one budget.
COUNTERPARTY_A_MIXED = "0x" + "aA" * 20
INVALID_KINDS = ("unknown_network", "wrong_asset", "malformed_pay_to", "zero_amount")
# Structurally valid requests whose signer call raises: the signer boundary
# is untrusted, and without these symbols the ordering of policy.record()
# relative to the signer call is invisible to the model.
SIGNER_FAULT_SYMBOLS = (
    ("signer_fault", 1, COUNTERPARTY_A),
    ("signer_fault", 2, COUNTERPARTY_B),
)
MAX_TRACE_LEN = 3
NOW = 1_753_600_000
# The policy day is pinned so a UTC-midnight rollover mid-run cannot reset the
# implementation's counters while the model's stay put (a spurious, fail-safe
# I1 violation — but a time-flaky CI gate is a bug regardless of direction).
FIXED_UTC_DATE = "2026-07-27"

BOUNDS = {
    "amounts": list(AMOUNTS),
    "max_per_request": PER_REQUEST_CAP,
    "max_per_day": PER_DAY_CAP,
    "max_per_day_per_counterparty": PER_COUNTERPARTY_CAP,
    "counterparties": [COUNTERPARTY_A, COUNTERPARTY_B, COUNTERPARTY_A_MIXED],
    "casing_note": "COUNTERPARTY_A_MIXED is the same address as A in a different hex casing",
    "networks": [VALID_NETWORK, UNKNOWN_NETWORK],
    "invalid_variants": list(INVALID_KINDS),
    "signer_fault_variants": [
        f"signer raises on a valid request for {amount} to {counterparty}"
        for _, amount, counterparty in SIGNER_FAULT_SYMBOLS
    ],
    "max_trace_len": MAX_TRACE_LEN,
    "restart_variant": "policy re-instantiated from disk before request index 1",
    "fixed_utc_date": FIXED_UTC_DATE,
}

INVARIANT_NAMES = ("I1", "I2", "I3", "I4", "I5", "I6", "I7")


class _SignerFault(RuntimeError):
    """The injected out-of-process signer failure."""


class _StubSigner:
    """Keyless test double: records payloads, returns deterministic markers.

    Holds no key bytes and performs no cryptography — the model checks the
    machinery around the signer, not signatures themselves. When ``fail_next``
    is armed the next call raises instead of signing, modelling the untrusted
    signer boundary failing; ``attempts`` counts every entry including faults,
    ``calls`` records successful signatures only.
    """

    address = "0x" + "cc" * 20

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.attempts = 0
        self.fail_next = False

    def sign_typed_data(self, payload: dict) -> str:
        self.attempts += 1
        if self.fail_next:
            self.fail_next = False
            raise _SignerFault("injected signer failure")
        self.calls.append(payload)
        return f"0xstub{len(self.calls):04d}"


def _symbols() -> list[tuple[str, int, str]]:
    """The request alphabet: every (kind, amount, counterparty) the model uses."""
    syms = [
        ("valid", amount, counterparty)
        for amount in AMOUNTS
        for counterparty in (COUNTERPARTY_A, COUNTERPARTY_B, COUNTERPARTY_A_MIXED)
    ]
    syms.extend((kind, 1, COUNTERPARTY_A) for kind in INVALID_KINDS)
    syms.extend(SIGNER_FAULT_SYMBOLS)
    return syms


def _entry(kind: str, amount: int, counterparty: str) -> dict:
    entry = {
        "scheme": "exact",
        "network": VALID_NETWORK,
        "maxAmountRequired": str(amount),
        "payTo": counterparty,
        "asset": USDC_ASSETS[VALID_NETWORK]["address"],
        "extra": {"name": "USDC", "version": "2"},
    }
    if kind == "unknown_network":
        entry["network"] = UNKNOWN_NETWORK
    elif kind == "wrong_asset":
        entry["asset"] = "0x" + "11" * 20
    elif kind == "malformed_pay_to":
        entry["payTo"] = "not-an-address"
    elif kind == "zero_amount":
        entry["maxAmountRequired"] = "0"
    return entry


def _model_allows(amount: int, counterparty: str, spent: int, per_cp: dict[str, int]) -> bool:
    """The semantic model of the caps, independent of the implementation."""
    if amount > PER_REQUEST_CAP:
        return False
    if spent + amount > PER_DAY_CAP:
        return False
    if per_cp.get(counterparty.lower(), 0) + amount > PER_COUNTERPARTY_CAP:
        return False
    return True


def _violate(violations: dict[str, str], name: str, detail: str) -> None:
    violations.setdefault(name, f"VIOLATED: {detail}")


def _run_trace(
    trace: tuple[tuple[str, int, str], ...],
    restart_at: int | None,
    violations: dict[str, str],
    seen_nonces: set[str],
    counters: dict[str, int],
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        def _fresh_policy() -> SpendPolicy:
            return SpendPolicy(
                max_per_request=PER_REQUEST_CAP,
                max_per_day=PER_DAY_CAP,
                max_per_day_per_counterparty=PER_COUNTERPARTY_CAP,
                allowed_networks=None,
                base_dir=base,
            )

        signer = _StubSigner()
        client = PaymentClient(signer, _fresh_policy())
        spent = 0
        per_cp: dict[str, int] = {}

        for index, (kind, amount, counterparty) in enumerate(trace):
            if restart_at is not None and index == restart_at:
                # Restart variant: the policy is rebuilt from its disk state
                # mid-trace, modelling a buyer process crash + restart.
                client = PaymentClient(signer, _fresh_policy())

            validated, problems = validate_accepts(_entry(kind, amount, counterparty))

            if kind in INVALID_KINDS:
                if validated is not None or not problems:
                    _violate(violations, "I6", f"invalid entry kind {kind!r} validated")
                continue  # invalid entries never reach pay()
            if validated is None:
                # A valid entry failing validation means the checker itself is
                # driving the wrong space — that is a harness bug, not I1–I7.
                raise RuntimeError(f"model bug: valid entry rejected: {problems}")

            calls_before = len(signer.calls)
            attempts_before = signer.attempts
            model_ok = _model_allows(amount, counterparty, spent, per_cp)
            if kind == "signer_fault":
                signer.fail_next = True
            result = client.pay(validated, now=NOW, now_utc_date=FIXED_UTC_DATE)
            signer.fail_next = False  # disarm if the policy denied pre-signer
            delta = len(signer.calls) - calls_before
            attempt_delta = signer.attempts - attempts_before

            if kind == "signer_fault":
                # I7: the failure must fail closed — never paid, reported as
                # signer_error when the caps allowed the attempt, and the
                # budget untouched (the semantic model does not charge, so any
                # implementation that did charge is caught by the
                # denied-although-model-allows check on a later request).
                counters["signer_faults"] += 1
                counters["denied"] += 1
                if result.paid:
                    _violate(violations, "I7", f"paid despite signer fault in {trace}")
                elif model_ok and (
                    result.check != "signer_error" or attempt_delta != 1 or delta != 0
                ):
                    _violate(
                        violations,
                        "I7",
                        f"signer fault not failed closed: check={result.check!r}, "
                        f"attempts={attempt_delta}, signed={delta} in {trace}",
                    )
                elif not model_ok and attempt_delta != 0:
                    _violate(
                        violations,
                        "I5",
                        f"policy denial reached the signer ({attempt_delta} attempts) "
                        f"in {trace}",
                    )
                continue

            if result.paid:
                counters["signed"] += 1
                if delta != 1:
                    _violate(violations, "I1", f"paid with {delta} signer calls in {trace}")
                if not model_ok:
                    _violate(
                        violations,
                        "I1",
                        f"signed although model denies: {trace} at index {index}",
                    )
                payload = signer.calls[-1]
                if payload["message"]["value"] != str(amount):
                    _violate(
                        violations,
                        "I2",
                        f"signed value {payload['message']['value']!r} != quoted {amount}",
                    )
                if result.nonce in seen_nonces:
                    _violate(violations, "I3", f"nonce reused across run: {result.nonce}")
                seen_nonces.add(result.nonce)
                spent += amount
                cp_key = counterparty.lower()
                per_cp[cp_key] = per_cp.get(cp_key, 0) + amount
                if spent > PER_DAY_CAP:
                    _violate(violations, "I4", f"daily spend {spent} > {PER_DAY_CAP} in {trace}")
                if per_cp[cp_key] > PER_COUNTERPARTY_CAP:
                    _violate(
                        violations,
                        "I4",
                        f"counterparty spend {per_cp[cp_key]} > "
                        f"{PER_COUNTERPARTY_CAP} in {trace}",
                    )
            else:
                counters["denied"] += 1
                if attempt_delta != 0:
                    _violate(
                        violations,
                        "I5",
                        f"denial ({result.denial}) with {attempt_delta} signer "
                        f"attempts in {trace}",
                    )
                if model_ok:
                    _violate(
                        violations,
                        "I7",
                        f"denied ({result.denial}) although the model allows — "
                        f"budget charged without a signature? {trace} at index {index}",
                    )


def run_model_check() -> dict:
    """Enumerate the full bounded space and return the invariant report."""
    symbols = _symbols()
    violations: dict[str, str] = {}
    seen_nonces: set[str] = set()
    counters = {"signed": 0, "denied": 0, "signer_faults": 0}
    traces_checked = 0

    for length in range(1, MAX_TRACE_LEN + 1):
        for trace in itertools.product(symbols, repeat=length):
            _run_trace(trace, None, violations, seen_nonces, counters)
            traces_checked += 1
            if length >= 2:
                _run_trace(trace, 1, violations, seen_nonces, counters)
                traces_checked += 1

    return {
        "bounds": BOUNDS,
        "traces_checked": traces_checked,
        "signed_total": counters["signed"],
        "denied_total": counters["denied"],
        "signer_fault_total": counters["signer_faults"],
        "invariants": {name: violations.get(name, "holds") for name in INVARIANT_NAMES},
    }


def main() -> int:
    report = run_model_check()
    print(json.dumps(report, indent=2))
    all_hold = all(verdict == "holds" for verdict in report["invariants"].values())
    return 0 if all_hold and report["traces_checked"] > 200 else 1


if __name__ == "__main__":
    sys.exit(main())
