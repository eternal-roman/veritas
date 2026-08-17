"""G2: local recovery of an EIP-3009 transferWithAuthorization signature."""

from __future__ import annotations

import secrets
import time

import pytest

from veritas.eip3009 import (
    recover_authorization_signer,
    typed_data_for_authorization,
    verify_payment_signature,
)
from veritas.x402 import USDC_ASSETS

pytest.importorskip("eth_account")

NETWORK = "eip155:84532"


def _sign_authorization(*, now: int | None = None, valid_for: int = 600):
    from eth_account import Account
    from eth_account.messages import encode_typed_data

    account = Account.create()
    ts = now if now is not None else int(time.time())
    nonce = "0x" + secrets.token_bytes(32).hex()
    authorization = {
        "from": account.address,
        "to": "0x" + "2" * 40,
        "value": "10000",
        "validAfter": str(ts - 1),
        "validBefore": str(ts + valid_for),
        "nonce": nonce,
    }
    typed = typed_data_for_authorization(authorization, network=NETWORK)
    signature = "0x" + account.sign_message(
        encode_typed_data(full_message=typed)
    ).signature.hex()
    payload = {
        "x402Version": 1,
        "scheme": "exact",
        "network": NETWORK,
        "payload": {"signature": signature, "authorization": authorization},
        "payer": account.address,
    }
    return payload, account.address.lower()


def test_typed_data_uses_pinned_usdc_domain():
    payload, _ = _sign_authorization()
    typed = typed_data_for_authorization(
        payload["payload"]["authorization"], network=NETWORK
    )
    assert typed["domain"]["name"] == "USDC"
    assert typed["domain"]["version"] == "2"
    assert typed["domain"]["verifyingContract"] == USDC_ASSETS[NETWORK]["address"]
    assert typed["primaryType"] == "TransferWithAuthorization"


def test_recovered_signer_matches_from():
    payload, address = _sign_authorization()
    recovered = recover_authorization_signer(
        payload["payload"]["authorization"],
        payload["payload"]["signature"],
        network=NETWORK,
    )
    assert recovered == address


def test_forged_signature_is_refused():
    payload, _ = _sign_authorization()
    payload["payload"]["signature"] = "0x" + "00" * 65
    ok, reason = verify_payment_signature(payload, now=int(time.time()))
    assert ok is False
    assert reason in {"signature_invalid", "signer_mismatch"}


def test_expired_authorization_is_refused():
    now = int(time.time())
    payload, _ = _sign_authorization(now=now - 10_000, valid_for=60)
    ok, reason = verify_payment_signature(payload, now=now)
    assert ok is False
    assert reason == "authorization_expired"


def test_valid_authorization_passes():
    payload, _ = _sign_authorization()
    ok, reason = verify_payment_signature(payload, now=int(time.time()))
    assert ok is True
    assert reason == "ok"


def test_wrong_from_is_signer_mismatch():
    payload, _ = _sign_authorization()
    payload["payload"]["authorization"]["from"] = "0x" + "3" * 40
    ok, reason = verify_payment_signature(payload, now=int(time.time()))
    assert ok is False
    assert reason == "signer_mismatch"
