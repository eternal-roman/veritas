"""The unified buyer path: in-process signing behind veritas.payer's Signer
seam, so a testnet run inherits challenge validation, spend caps, and the
pre-sign attempt journal.

The load-bearing test here is the signature round-trip: it proves the payload
`veritas.payer` emits is genuinely EIP-712 encodable and that the recovered
signer is the payer we claimed. Everything else in the payment stack is
shape-checking; this is the one place real cryptography runs.
"""

import json

import pytest

from veritas.buyer_payment import (
    BuyerPaymentError,
    LocalAccountSigner,
    _typed_data_for_signing,
    decode_x_payment,
    pay_via_policy,
)
from veritas.payer import SpendPolicy, build_authorization, validate_accepts
from veritas.x402 import USDC_ASSETS

eth_account = pytest.importorskip("eth_account")

NETWORK = "eip155:8453"
ASSET = USDC_ASSETS[NETWORK]["address"]
PAY_TO = "0x" + "ab" * 20
# Test-only key: a well-known throwaway used across eth tooling examples.
TEST_KEY = "0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318"
NOW = 1_753_600_000


def _requirements(amount="250000", **overrides):
    entry = {
        "scheme": "exact",
        "network": NETWORK,
        "maxAmountRequired": amount,
        "payTo": PAY_TO,
        "asset": ASSET,
        "extra": {"name": "USDC", "version": "2"},
    }
    entry.update(overrides)
    return entry


def _policy(tmp_path, per_request=500_000, per_day=1_000_000, per_counterparty=None):
    return SpendPolicy(
        max_per_request=per_request,
        max_per_day=per_day,
        max_per_day_per_counterparty=per_counterparty,
        base_dir=tmp_path,
    )


def test_signature_recovers_to_the_payer_address():
    """The whole point of the seam: payer.py builds it, the signer signs it,
    and the recovered address is the account that signed."""
    from eth_account import Account
    from eth_account.messages import encode_typed_data

    signer = LocalAccountSigner(TEST_KEY)
    validated, problems = validate_accepts(_requirements())
    assert problems == []

    payload = build_authorization(validated, signer.address, now=NOW)
    signature = signer.sign_typed_data(payload)

    signable = encode_typed_data(full_message=_typed_data_for_signing(payload))
    recovered = Account.recover_message(signable, signature=bytes.fromhex(signature[2:]))
    assert recovered == signer.address


def test_typed_data_coercion_matches_eip712_types():
    """Wire shape is JSON strings; the encoder needs ints and bytes32."""
    validated, _ = validate_accepts(_requirements())
    payload = build_authorization(validated, "0x" + "cd" * 20, now=NOW)
    typed = _typed_data_for_signing(payload)

    assert isinstance(typed["message"]["value"], int)
    assert isinstance(typed["message"]["validAfter"], int)
    assert isinstance(typed["message"]["validBefore"], int)
    assert isinstance(typed["message"]["nonce"], bytes)
    assert len(typed["message"]["nonce"]) == 32
    assert isinstance(typed["domain"]["chainId"], int)
    # The wire payload itself must be untouched — it is what goes in the header.
    assert isinstance(payload["message"]["value"], str)


def test_gated_payment_produces_a_decodable_header(tmp_path):
    header, payload = pay_via_policy(
        _requirements(), TEST_KEY, policy=_policy(tmp_path), now=NOW
    )
    assert decode_x_payment(header) == payload
    assert payload["x402Version"] == 1
    assert payload["scheme"] == "exact"
    assert payload["network"] == NETWORK
    assert payload["payload"]["signature"].startswith("0x")
    authorization = payload["payload"]["authorization"]
    assert authorization["to"] == PAY_TO
    assert authorization["value"] == "250000"
    # The envelope carries no vendor fields: header and payload agree exactly,
    # and the payer is read from the signed authorization itself.
    assert authorization["from"] == LocalAccountSigner(TEST_KEY).address


def test_gated_payment_enforces_spend_caps(tmp_path):
    """The reason the gated path exists: an unattended harness must not be
    able to spend without limit."""
    policy = _policy(tmp_path, per_request=100_000)
    with pytest.raises(BuyerPaymentError) as excinfo:
        pay_via_policy(_requirements("250000"), TEST_KEY, policy=policy, now=NOW)
    assert "per_request_cap" in str(excinfo.value)


def test_gated_payment_exhausts_the_daily_budget(tmp_path):
    policy = _policy(tmp_path, per_request=250_000, per_day=250_000)
    pay_via_policy(_requirements(), TEST_KEY, policy=policy, now=NOW)
    with pytest.raises(BuyerPaymentError) as excinfo:
        pay_via_policy(_requirements(), TEST_KEY, policy=policy, now=NOW)
    assert "per_day_cap" in str(excinfo.value)


def test_gated_payment_rejects_a_hostile_challenge(tmp_path):
    """A challenge naming an asset that is not the network's USDC must never
    reach the signer."""
    hostile = _requirements(asset="0x" + "ee" * 20)
    with pytest.raises(BuyerPaymentError) as excinfo:
        pay_via_policy(hostile, TEST_KEY, policy=_policy(tmp_path), now=NOW)
    assert "rejected" in str(excinfo.value)


def test_gated_payment_writes_the_attempt_journal(tmp_path):
    pay_via_policy(_requirements(), TEST_KEY, policy=_policy(tmp_path), now=NOW)
    lines = [json.loads(x) for x in
             (tmp_path / "authorization_attempts.jsonl").read_text().splitlines()]
    assert [x["stage"] for x in lines] == ["pre_sign", "signed"]


def test_every_gated_payment_uses_a_fresh_nonce(tmp_path):
    policy = _policy(tmp_path, per_request=250_000, per_day=1_000_000)
    nonces = set()
    for _ in range(3):
        _, payload = pay_via_policy(_requirements(), TEST_KEY, policy=policy, now=NOW)
        nonces.add(payload["payload"]["authorization"]["nonce"])
    assert len(nonces) == 3


def test_signer_requires_a_key():
    with pytest.raises(BuyerPaymentError):
        LocalAccountSigner("")


def test_signer_never_exposes_key_material():
    signer = LocalAccountSigner(TEST_KEY)
    rendered = f"{signer!r} {vars(signer)}"
    assert TEST_KEY not in rendered
    assert TEST_KEY[2:] not in rendered
