"""Bounded exhaustive model check of the real payer machinery.

The checker in veritas.evaluations.payment_model drives the REAL SpendPolicy
and PaymentClient (with a keyless stub signer) through the full enumeration of
a small bounded space and asserts semantic invariants I1-I6. Evidence level is
L2: the invariants hold for the stated bounds, nothing more — this is not a
proof of the product.
"""

import json
import subprocess
import sys

import pytest

from veritas.evaluations import payment_model
from veritas.evaluations.payment_model import run_model_check
from veritas.payer import PaymentClient

INVARIANT_NAMES = {"I1", "I2", "I3", "I4", "I5", "I6", "I7"}


@pytest.fixture(scope="module")
def report():
    """One checker run shared across tests — the enumeration is the slow part."""
    return run_model_check()


def test_model_report_shape(report):
    assert set(report["invariants"]) == INVARIANT_NAMES
    assert isinstance(report["bounds"], dict)
    assert report["bounds"], "bounds must be stated in the report, not implicit"


def test_model_explores_more_than_200_traces(report):
    assert report["traces_checked"] > 200


def test_model_exercises_both_outcomes(report):
    """A checker that only ever signs (or only ever denies) is not exploring
    the space it claims to."""
    assert report["signed_total"] > 0
    assert report["denied_total"] > 0


def test_model_all_invariants_hold(report):
    violated = {
        name: verdict
        for name, verdict in report["invariants"].items()
        if verdict != "holds"
    }
    assert violated == {}


def test_model_checked_space_contains_signer_failures(report):
    """Regression: the checked space must contain signer failures. Without
    them the ordering of policy.record() relative to the signer call is
    unobservable, and a client that charges the buyer for unsigned work
    passes the checker (this happened: a record-before-sign mutant survived
    with all invariants 'holds')."""
    assert report["signer_fault_total"] > 0
    assert "signer_fault_variants" in report["bounds"]


def test_model_catches_charge_on_signer_failure(monkeypatch):
    """Regression: a client that charges the budget when the signer fails —
    observationally the record-before-sign bug class — must be reported as
    an I7 violation, not pass the checker."""

    class _ChargesOnSignerFailure(PaymentClient):
        def pay(self, validated, now, validity_seconds=60, now_utc_date=None):
            result = super().pay(validated, now, validity_seconds, now_utc_date=now_utc_date)
            if not result.paid and result.check == "signer_error":
                # The bug under test: buyer charged for unsigned work.
                self._policy.record(validated.amount_atomic, validated.pay_to)
            return result

    monkeypatch.setattr(payment_model, "PaymentClient", _ChargesOnSignerFailure)
    mutant_report = run_model_check()
    assert mutant_report["invariants"]["I7"] != "holds"


def test_model_runs_as_module_and_exits_zero():
    """Roadmap acceptance: python -m veritas.evaluations.payment_model prints a
    JSON report and exits 0 iff every invariant holds."""
    proc = subprocess.run(
        [sys.executable, "-m", "veritas.evaluations.payment_model"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    printed = json.loads(proc.stdout)
    assert set(printed["invariants"]) == INVARIANT_NAMES
    assert printed["traces_checked"] > 200
