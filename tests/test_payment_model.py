"""The payment-model checker runs as a dedicated CI job.

Pytest keeps only the mutant that CI's module run does not replace: a
client that charges the budget when the signer fails must not report I7
as holding.
"""

from veritas.evaluations import payment_model
from veritas.evaluations.payment_model import run_model_check
from veritas.payer import PaymentClient


def test_model_catches_charge_on_signer_failure(monkeypatch):
    """A client that charges the budget when the signer fails —
    observationally the record-before-sign bug class — must be reported as
    an I7 violation, not pass the checker."""

    class _ChargesOnSignerFailure(PaymentClient):
        def pay(self, validated, now, validity_seconds=60, now_utc_date=None):
            result = super().pay(validated, now, validity_seconds, now_utc_date=now_utc_date)
            if not result.paid and result.check == "signer_error":
                self._policy.record(validated.amount_atomic, validated.pay_to)
            return result

    monkeypatch.setattr(payment_model, "PaymentClient", _ChargesOnSignerFailure)
    mutant_report = run_model_check()
    assert mutant_report["invariants"]["I7"] != "holds"
