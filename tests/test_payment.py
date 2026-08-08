"""x402 payment: atomic amounts, spec-shaped challenges, and fail-closed gating."""


import socket
import urllib.error

import pytest

from veritas.facilitator import (
    INDETERMINATE_SETTLEMENT_REASONS,
    VERIFICATION_OUTAGE_PREFIXES,
    FacilitatorClient,
    SimulatedFacilitatorClient,
    _transport_reason,
)
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
    """A facilitator we cannot reach denies, and names the denial an outage.

    Which outage it is depends on the platform, not on us: a closed port is
    refused immediately on Linux (`facilitator_unreachable`) and swallowed
    until the timeout on Windows (`facilitator_timeout`). Both are correct.
    The invariant under test is that the caller fails closed and the reason is
    a registered outage — so buyers retry — rather than a payment rejection.
    The unreachable/timeout distinction itself is pinned deterministically in
    `test_transport_reasons_separate_never_left_from_never_heard_back`.
    """
    client = FacilitatorClient("http://127.0.0.1:1", timeout=1)
    result = client.verify({"scheme": "exact"}, {"scheme": "exact"})
    assert result.is_valid is False
    assert (result.invalid_reason or "").startswith(VERIFICATION_OUTAGE_PREFIXES)


def test_transport_reasons_separate_never_left_from_never_heard_back():
    """R7: "we never heard back" is not "it did not happen".

    A refused connection or failed DNS lookup proves the request never left,
    so nothing settled. A timeout proves nothing either way, and settlement
    must record it as indeterminate. Classified from the exception directly so
    the distinction is tested on every platform, not only where a closed port
    happens to refuse.
    """
    refused = urllib.error.URLError(ConnectionRefusedError("refused"))
    assert _transport_reason(refused) == "facilitator_unreachable"
    assert "facilitator_unreachable" not in INDETERMINATE_SETTLEMENT_REASONS

    for timed_out in (urllib.error.URLError(TimeoutError("timed out")), TimeoutError()):
        assert _transport_reason(timed_out) == "facilitator_timeout"
    assert "facilitator_timeout" in INDETERMINATE_SETTLEMENT_REASONS

    dns = urllib.error.URLError(socket.gaierror("name resolution failed"))
    assert _transport_reason(dns) == "facilitator_unreachable"

    http = urllib.error.HTTPError("http://f", 503, "boom", {}, None)
    assert _transport_reason(http) == "facilitator_http_503"

    # Every transport reason is a registered verification outage, so no
    # transport failure can ever reach a buyer as a payment rejection.
    for exc in (refused, urllib.error.URLError(TimeoutError()), dns, http):
        assert _transport_reason(exc).startswith(VERIFICATION_OUTAGE_PREFIXES)


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
