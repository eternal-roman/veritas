"""Buyer-side x402 exact-scheme payment helpers (Phase 0.1 / Phase 3.1).

Additive only. Does not change server payment gating.
Signing requires optional dependency ``eth_account``.

**Custody scope — read before using this in anything but a test.** This is the
only module in the package that takes a private key in-process, and it exists
for the Phase 0.1 testnet settlement proof, where an operator deliberately
runs a throwaway funded key on a testnet. It is NOT the production custody
model: ROADMAP 3.2 commits to the key never entering the agent process, with
the payload travelling out to an external signer and only a signature coming
back. That boundary is :class:`veritas.payer.Signer`.

There is one payment path, not two. :func:`pay_via_policy` routes this
module's signing through :mod:`veritas.payer`, so a testnet run gets the same
challenge validation, spend caps, and pre-sign attempt journal as any other
buyer. :class:`LocalAccountSigner` is the adapter that puts an in-process key
behind the ``Signer`` protocol; swapping in a remote signer later changes that
one class and nothing else. The lower-level :func:`build_exact_payment_payload`
remains for tests and for reconstructing a payload for audit — it applies no
caps and writes no journal, so prefer :func:`pay_via_policy`.
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

from veritas.payer import (
    PaymentClient,
    SpendPolicy,
    build_authorization,  # noqa: F401 - re-exported for audit-time reconstruction
    validate_accepts,
)


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


# ---------------------------------------------------------------------------
# The gated path: in-process signing behind veritas.payer's Signer seam, so a
# testnet run inherits validation, spend caps, and the attempt journal.
# ---------------------------------------------------------------------------

# Default caps for an unattended testnet run, in atomic USDC units (6 dp).
# A harness with no caps at all is how a loop drains a funded key overnight.
DEFAULT_MAX_PER_REQUEST = 1_000_000   # 1.00 USDC
DEFAULT_MAX_PER_DAY = 5_000_000       # 5.00 USDC


def _typed_data_for_signing(payload: dict[str, Any]) -> dict[str, Any]:
    """Coerce a wire-shaped EIP-712 payload into the types eth_account expects.

    ``veritas.payer.build_authorization`` emits JSON wire types — uint256 as
    decimal strings, bytes32 as a 0x hex string — because that is what goes
    into the ``X-PAYMENT`` header. The encoder wants Python ints and bytes.
    Converting here (rather than changing the wire shape) keeps the header
    exactly as the x402 spec describes it.
    """
    message = dict(payload["message"])
    for field in ("value", "validAfter", "validBefore"):
        message[field] = int(message[field])
    nonce = message["nonce"]
    if isinstance(nonce, str):
        message["nonce"] = bytes.fromhex(nonce[2:] if nonce.startswith("0x") else nonce)
    domain = dict(payload["domain"])
    domain["chainId"] = int(domain["chainId"])
    return {
        "types": payload["types"],
        "primaryType": payload["primaryType"],
        "domain": domain,
        "message": message,
    }


class LocalAccountSigner:
    """``Signer`` backed by an in-process eth_account key. TESTNET/DEV ONLY.

    This is the one place a private key is held in this process, and it is
    deliberately a thin adapter: it implements exactly the two members of
    :class:`veritas.payer.Signer` (``address`` and ``sign_typed_data``), so a
    remote or hardware signer can replace it without touching any caller.
    The key is never logged, never returned, and never serialised.
    """

    def __init__(self, private_key: str) -> None:
        if not private_key:
            raise BuyerPaymentError("private_key is required")
        try:
            from eth_account import Account
        except ImportError as exc:  # pragma: no cover - dependency-gated
            raise BuyerPaymentError(
                "eth_account is required for signing; pip install eth_account"
            ) from exc
        self._account = Account.from_key(private_key)

    @property
    def address(self) -> str:
        return self._account.address

    def sign_typed_data(self, payload: dict[str, Any]) -> str:
        try:
            from eth_account.messages import encode_typed_data
        except ImportError as exc:  # pragma: no cover - dependency-gated
            raise BuyerPaymentError("eth_account is required for signing") from exc
        signable = encode_typed_data(full_message=_typed_data_for_signing(payload))
        signature = self._account.sign_message(signable).signature
        return "0x" + signature.hex().removeprefix("0x")


def default_spend_policy(base_dir: str | None = None) -> SpendPolicy:
    """Caps for an unattended run, overridable by environment."""
    return SpendPolicy(
        max_per_request=int(os.getenv("VERITAS_MAX_PER_REQUEST", DEFAULT_MAX_PER_REQUEST)),
        max_per_day=int(os.getenv("VERITAS_MAX_PER_DAY", DEFAULT_MAX_PER_DAY)),
        max_per_day_per_counterparty=(
            int(os.environ["VERITAS_MAX_PER_COUNTERPARTY"])
            if os.getenv("VERITAS_MAX_PER_COUNTERPARTY")
            else None
        ),
        base_dir=base_dir,
    )


def pay_via_policy(
    requirements: dict[str, Any],
    private_key: str,
    *,
    policy: SpendPolicy | None = None,
    now: int | None = None,
    validity_seconds: int = 60,
) -> tuple[str, dict[str, Any]]:
    """Validate a 402 entry, apply spend caps, journal, sign, and encode.

    Returns ``(x_payment_header, decoded_payload)`` where the payload is
    exactly what the header decodes to — the envelope stays spec-shaped, with
    no vendor fields added after signing. The payer address is
    ``payload["payload"]["authorization"]["from"]``.

    Raises :class:`BuyerPaymentError` naming the failed check when the
    challenge is rejected or the policy refuses — a refusal is never a silent
    no-op, and a refused payment never reaches the signer.
    """
    validated, problems = validate_accepts(requirements)
    if validated is None:
        raise BuyerPaymentError(f"402 accepts entry rejected: {problems}")

    signer = LocalAccountSigner(private_key)
    client = PaymentClient(signer, policy or default_spend_policy())
    result = client.pay(
        validated,
        now=int(time.time()) if now is None else int(now),
        validity_seconds=validity_seconds,
    )
    if not result.paid:
        raise BuyerPaymentError(f"payment refused [{result.check}]: {result.denial}")

    return result.header, decode_x_payment(result.header)
