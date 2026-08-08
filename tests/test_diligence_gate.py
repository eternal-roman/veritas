"""The diligence verdict must bind money, not advise about it.

Constitution article A20 already draws the line that a refused payment never
reaches the signer. A counterparty refused on diligence grounds must hold that
same line: the loss a hostile seller can inflict is bounded by the decision,
not merely by the daily budget.
"""

from __future__ import annotations

import pytest

from veritas.diligence import Verdict, assess
from veritas.payer import PaymentClient, SpendPolicy, validate_accepts

PAY_TO = "0x" + "11" * 20
OTHER_PAY_TO = "0x" + "22" * 20
ASSET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
NOW = 1_760_000_000


class ExplodingSigner:
    """Fails the test if it is ever reached."""

    address = "0x" + "99" * 20

    def sign_typed_data(self, payload):
        raise AssertionError("signer reached despite a refused counterparty")


class RecordingSigner:
    address = "0x" + "99" * 20

    def __init__(self):
        self.reached = False

    def sign_typed_data(self, payload):
        self.reached = True
        return "0x" + "ab" * 65


def _accepts(pay_to=PAY_TO, amount="10000"):
    return {
        "scheme": "exact", "network": "eip155:8453", "asset": ASSET,
        "payTo": pay_to, "maxAmountRequired": amount,
        "resource": "https://seller.test/v1/research",
        "extra": {"name": "USD Coin", "version": "2"},
    }


def _validated(pay_to=PAY_TO, amount="10000"):
    validated, problems = validate_accepts(_accepts(pay_to, amount))
    assert not problems, problems
    return validated


def _policy(tmp_path):
    return SpendPolicy(
        max_per_request=1_000_000, max_per_day=1_000_000,
        max_per_day_per_counterparty=1_000_000, base_dir=tmp_path,
    )


@pytest.fixture
def strict_client(tmp_path):
    """A buyer that will not pay a counterparty it has not cleared."""
    return PaymentClient(ExplodingSigner(), _policy(tmp_path),
                         base_dir=tmp_path, require_diligence=True)


def test_a_refused_counterparty_never_reaches_the_signer(strict_client):
    report = assess(
        challenge={"accepts": [_accepts(pay_to=OTHER_PAY_TO)]},
        discovery={"accepts": [_accepts(pay_to=PAY_TO)]},
    )
    assert report.verdict == Verdict.FAIL

    result = strict_client.pay(_validated(pay_to=OTHER_PAY_TO), now=NOW,
                               diligence=report)
    assert result.paid is False
    assert result.check == "diligence"
    assert result.header is None
    assert result.nonce is None


def test_absent_diligence_is_refused_when_required(strict_client):
    """Fail-closed: required but not supplied must refuse, not proceed."""
    result = strict_client.pay(_validated(), now=NOW, diligence=None)
    assert result.paid is False
    assert result.check == "diligence"


def test_unverifiable_is_refused_but_named_distinctly(strict_client):
    """Both refuse, but the buyer must be able to tell them apart: one means
    find another seller, the other means fix your own fetch path."""
    report = assess(challenge={"accepts": [_accepts()]}, discovery=None)
    assert report.verdict == Verdict.UNVERIFIABLE

    result = strict_client.pay(_validated(), now=NOW, diligence=report)
    assert result.paid is False
    assert result.check == "diligence"
    assert Verdict.UNVERIFIABLE in result.denial


def test_a_cleared_counterparty_is_paid(tmp_path):
    signer = RecordingSigner()
    client = PaymentClient(signer, _policy(tmp_path), base_dir=tmp_path,
                           require_diligence=True)
    report = assess(
        challenge={"accepts": [_accepts()]},
        discovery={"accepts": [_accepts()]},
        policy=_pass_policy(),
    )
    assert report.verdict == Verdict.PASS

    result = client.pay(_validated(), now=NOW, diligence=report)
    assert result.paid is True, result.denial
    assert signer.reached is True


def _pass_policy():
    from veritas.diligence import DiligencePolicy

    return DiligencePolicy(require_constitution=False, require_gap_register=False,
                           require_trust_self_disclosure=False)


def test_diligence_is_opt_in_and_off_by_default(tmp_path):
    """Additive: an existing caller that passes no diligence keeps working, and
    turning the gate on stays the buyer's decision."""
    signer = RecordingSigner()
    client = PaymentClient(signer, _policy(tmp_path), base_dir=tmp_path)

    result = client.pay(_validated(), now=NOW)
    assert result.paid is True, result.denial
    assert signer.reached is True


def test_a_refused_counterparty_consumes_no_budget(tmp_path):
    """The gate sits before the spend policy, so refusing costs the buyer
    nothing: a hostile seller must not be able to burn a daily budget by
    presenting challenges that will be refused."""
    policy = _policy(tmp_path)
    client = PaymentClient(ExplodingSigner(), policy, base_dir=tmp_path,
                           require_diligence=True)
    report = assess(
        challenge={"accepts": [_accepts(pay_to=OTHER_PAY_TO)]},
        discovery={"accepts": [_accepts(pay_to=PAY_TO)]},
    )

    for _ in range(5):
        assert client.pay(_validated(pay_to=OTHER_PAY_TO), now=NOW,
                          diligence=report).paid is False

    decision = policy.authorize(10000, "eip155:8453", PAY_TO)
    assert decision.allowed, "refused counterparties consumed budget"


def test_a_refused_counterparty_is_never_journalled(tmp_path):
    """The attempt journal exists to find authorizations that may exist
    on-chain. A payment refused before the signer created none, so writing one
    would put a phantom into reconciliation."""
    client = PaymentClient(ExplodingSigner(), _policy(tmp_path),
                           base_dir=tmp_path, require_diligence=True)
    report = assess(
        challenge={"accepts": [_accepts(pay_to=OTHER_PAY_TO)]},
        discovery={"accepts": [_accepts(pay_to=PAY_TO)]},
    )

    client.pay(_validated(pay_to=OTHER_PAY_TO), now=NOW, diligence=report)

    journal = tmp_path / "authorization_attempts.jsonl"
    assert not journal.exists() or journal.read_text(encoding="utf-8").strip() == ""
