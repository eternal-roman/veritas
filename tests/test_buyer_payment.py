"""Tests for veritas.buyer_payment — additive Phase 0.1 helpers."""

from __future__ import annotations

import base64

import pytest

from veritas.buyer_payment import (
    BuyerPaymentError,
    acceptance_met,
    build_exact_payment_payload,
    decode_x_payment,
    encode_x_payment,
    extract_settlement_proof,
    is_simulated_transaction,
)
from veritas.x402 import build_402_challenge


def test_encode_decode_roundtrip():
    payload = {"x402Version": 1, "scheme": "exact", "payer": "0xabc"}
    header = encode_x_payment(payload)
    assert decode_x_payment(header) == payload


def test_decode_rejects_non_object():
    bad = base64.b64encode(b"[1,2,3]").decode("ascii")
    with pytest.raises(BuyerPaymentError):
        decode_x_payment(bad)


def test_simulated_transaction_detection():
    assert is_simulated_transaction("simulated:no-onchain-settlement") is True
    assert is_simulated_transaction("0xdeadbeef") is False
    assert is_simulated_transaction(None) is False
    assert is_simulated_transaction("") is False


def test_acceptance_met_requires_200_and_real_tx():
    assert acceptance_met(200, "0xabc") is True
    assert acceptance_met(200, "simulated:x") is False
    assert acceptance_met(200, None) is False
    assert acceptance_met(402, "0xabc") is False
    assert acceptance_met(500, "0xabc") is False


def test_extract_settlement_proof_from_body():
    body = {
        "request_id": "r1",
        "status": "completed",
        "billable": True,
        "custody_root": "sha256:ab",
        "settlement": {
            "transaction": "0xtx",
            "payer": "0xp",
            "network": "eip155:84532",
        },
    }
    proof = extract_settlement_proof(body)
    assert proof["transaction"] == "0xtx"
    assert proof["request_id"] == "r1"
    assert proof["payer"] == "0xp"


def test_extract_settlement_proof_tx_hash_alias():
    proof = extract_settlement_proof({"settlement": {"tx_hash": "0xhash"}})
    assert proof["transaction"] == "0xhash"


def test_extract_settlement_proof_empty():
    proof = extract_settlement_proof({})
    assert proof["transaction"] is None
    assert proof["request_id"] is None


def test_build_payload_requires_key():
    req = build_402_challenge(
        "0x1111111111111111111111111111111111111111",
        "eip155:84532",
        "0.01",
        "/v1/research",
    )["accepts"][0]
    with pytest.raises(BuyerPaymentError, match="private_key"):
        build_exact_payment_payload(req, "")


def test_build_payload_requires_fields():
    with pytest.raises(BuyerPaymentError, match="missing"):
        build_exact_payment_payload({"payTo": "0x1"}, "0x" + "11" * 32)


def test_build_payload_signs_with_eth_account():
    eth_account = pytest.importorskip("eth_account")
    acct = eth_account.Account.create()
    req = build_402_challenge(
        "0x2222222222222222222222222222222222222222",
        "eip155:84532",
        "0.01",
        "/v1/research",
    )["accepts"][0]
    payload = build_exact_payment_payload(req, acct.key.hex(), now=1_700_000_000)
    assert payload["scheme"] == "exact"
    assert payload["network"] == "eip155:84532"
    assert payload["payer"].lower() == acct.address.lower()
    assert payload["payload"]["authorization"]["to"] == req["payTo"]
    assert payload["payload"]["authorization"]["value"] == req["maxAmountRequired"]
    assert payload["payload"]["signature"]
    header = encode_x_payment(payload)
    decoded = decode_x_payment(header)
    assert decoded["payer"].lower() == acct.address.lower()


def test_build_payload_rejects_zero_amount():
    eth_account = pytest.importorskip("eth_account")
    acct = eth_account.Account.create()
    req = {
        "payTo": "0x1111111111111111111111111111111111111111",
        "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        "network": "eip155:84532",
        "maxAmountRequired": "0",
        "scheme": "exact",
    }
    with pytest.raises(BuyerPaymentError, match="positive"):
        build_exact_payment_payload(req, acct.key.hex())


def test_challenge_accepts_compatible_with_buyer_payload():
    eth_account = pytest.importorskip("eth_account")
    acct = eth_account.Account.create()
    body = build_402_challenge(
        "0x3333333333333333333333333333333333333333",
        "eip155:84532",
        "$0.01",
        "/v1/research",
    )
    req = body["accepts"][0]
    assert req["maxAmountRequired"] == "10000"
    payload = build_exact_payment_payload(req, acct.key.hex())
    assert payload["payload"]["authorization"]["value"] == "10000"
