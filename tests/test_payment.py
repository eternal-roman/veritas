"""x402 payment: atomic amounts, spec-shaped challenges, and fail-closed gating."""


import pytest

from veritas.facilitator import FacilitatorClient, SimulatedFacilitatorClient
from veritas.x402 import PriceError, build_402_challenge, parse_price, to_atomic_amount


def test_price_converts_to_atomic_units():
    """The old challenge advertised '$0.25' as maxAmountRequired, which no
    conforming x402 client can parse as an amount."""
    assert to_atomic_amount("$0.25", "eip155:8453") == "250000"
    assert to_atomic_amount("1", "eip155:8453") == "1000000"
    assert to_atomic_amount("0.000001", "eip155:8453") == "1"


def test_price_parsing_variants():
    assert parse_price("$0.25") == parse_price("0.25") == parse_price("USD 0.25")


@pytest.mark.parametrize("bad", ["", "free", "$0", "-1", "abc"])
def test_bad_prices_rejected(bad):
    with pytest.raises(PriceError):
        to_atomic_amount(bad, "eip155:8453")


def test_price_rounding_to_zero_is_rejected():
    with pytest.raises(PriceError):
        to_atomic_amount("0.0000001", "eip155:8453")


def test_unknown_network_has_no_settlement_asset():
    with pytest.raises(PriceError):
        build_402_challenge("0xabc", "eip155:99999999", "$0.25", "/v1/research")


def test_challenge_is_spec_shaped():
    body = build_402_challenge("0xabc", "eip155:8453", "$0.25", "/v1/research")
    assert body["x402Version"] == 1
    accepts = body["accepts"][0]
    assert accepts["scheme"] == "exact"
    assert accepts["maxAmountRequired"] == "250000"
    assert accepts["asset"].startswith("0x")
    assert accepts["resource"] == "/v1/research"
    assert accepts["payTo"] == "0xabc"


def test_facilitator_fails_closed_when_unconfigured():
    """A verifier that cannot be reached must deny, never grant."""
    client = FacilitatorClient("")
    result = client.verify({"scheme": "exact"}, {"scheme": "exact"})
    assert result.is_valid is False
    assert result.invalid_reason == "no_facilitator_configured"


def test_facilitator_fails_closed_on_unreachable_host():
    client = FacilitatorClient("http://127.0.0.1:1", timeout=1)
    result = client.verify({"scheme": "exact"}, {"scheme": "exact"})
    assert result.is_valid is False
    assert "unreachable" in (result.invalid_reason or "")


def test_simulated_facilitator_labels_itself():
    sim = SimulatedFacilitatorClient()
    settlement = sim.settle({"payer": "0xabc"}, {"network": "eip155:8453"})
    assert settlement.success is True
    # A simulated settlement must never look like an on-chain one.
    assert "simulated" in settlement.transaction


def test_simulated_facilitator_rejects_malformed_payload():
    sim = SimulatedFacilitatorClient()
    assert sim.verify({}, {}).is_valid is False
    assert sim.verify({"scheme": "wrong"}, {"scheme": "exact"}).is_valid is False
