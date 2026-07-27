"""Buyer-side x402 exact-scheme payment helpers (Phase 0.1 / Phase 3.1).

Additive only. Does not change server payment gating.
Signing requires optional dependency ``eth_account``.
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any


class BuyerPaymentError(ValueError):
    """Raised when a payment payload cannot be constructed."""


def encode_x_payment(payment_payload: dict[str, Any]) -> str:
    """Base64-encode a JSON payment payload for the X-PAYMENT header."""
    raw = json.dumps(payment_payload, separators=(",", ":"), sort_keys=False).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def decode_x_payment(header_value: str) -> dict[str, Any]:
    """Decode an X-PAYMENT header back to a dict."""
    raw = base64.b64decode(header_value.encode("ascii"))
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise BuyerPaymentError("X-PAYMENT payload must be a JSON object")
    return data


def is_simulated_transaction(tx: str | None) -> bool:
    """True if a transaction id is a simulator marker, not on-chain."""
    if not tx:
        return False
    return str(tx).startswith("simulated")


def acceptance_met(http_status: int, transaction: str | None) -> bool:
    """Phase 0.1 acceptance: HTTP 200 and a non-simulated transaction id."""
    if http_status != 200:
        return False
    if not transaction:
        return False
    return not is_simulated_transaction(transaction)


def build_exact_payment_payload(
    requirements: dict[str, Any],
    private_key: str,
    *,
    now: int | None = None,
) -> dict[str, Any]:
    """Build and EIP-712-sign an exact-scheme payment payload.

    ``requirements`` is one entry from a 402 ``accepts[]`` list.
    """
    if not private_key:
        raise BuyerPaymentError("private_key is required")
    if not isinstance(requirements, dict):
        raise BuyerPaymentError("requirements must be a dict")
    for field in ("payTo", "asset", "network", "maxAmountRequired"):
        if field not in requirements:
            raise BuyerPaymentError(f"requirements missing {field}")

    try:
        from eth_account import Account
        from eth_account.messages import encode_typed_data
    except ImportError as exc:
        raise BuyerPaymentError(
            "eth_account is required for signing; pip install eth_account"
        ) from exc

    account = Account.from_key(private_key)
    network = requirements["network"]
    chain_id = int(str(network).split(":")[1]) if ":" in str(network) else 84532
    value = int(requirements["maxAmountRequired"])
    if value <= 0:
        raise BuyerPaymentError("maxAmountRequired must be positive")

    ts = int(time.time()) if now is None else int(now)
    valid_after = 0
    valid_before = ts + int(requirements.get("maxTimeoutSeconds") or 60)
    nonce = os.urandom(32)

    extra = requirements.get("extra") or {}
    typed: dict[str, Any] = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": extra.get("name") or "USDC",
            "version": extra.get("version") or "2",
            "chainId": chain_id,
            "verifyingContract": requirements["asset"],
        },
        "message": {
            "from": account.address,
            "to": requirements["payTo"],
            "value": value,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce,
        },
    }
    signable = encode_typed_data(full_message=typed)
    signed = account.sign_message(signable)

    return {
        "x402Version": 1,
        "scheme": requirements.get("scheme", "exact"),
        "network": network,
        "payload": {
            "signature": signed.signature.hex(),
            "authorization": {
                "from": account.address,
                "to": requirements["payTo"],
                "value": str(value),
                "validAfter": str(valid_after),
                "validBefore": str(valid_before),
                "nonce": "0x" + nonce.hex(),
            },
        },
        "payer": account.address,
    }


def extract_settlement_proof(response_body: dict[str, Any]) -> dict[str, Any]:
    """Normalize settlement fields from a research response body."""
    if not isinstance(response_body, dict):
        response_body = {}
    sett = response_body.get("settlement") or response_body.get("payment") or {}
    if not isinstance(sett, dict):
        sett = {}
    return {
        "request_id": response_body.get("request_id"),
        "status": response_body.get("status"),
        "billable": response_body.get("billable"),
        "custody_root": response_body.get("custody_root"),
        "settlement": sett,
        "transaction": sett.get("transaction") or sett.get("tx_hash"),
        "payer": sett.get("payer"),
        "network": sett.get("network"),
    }
