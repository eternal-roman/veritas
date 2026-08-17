"""EIP-3009 ``transferWithAuthorization`` signature recovery.

The local facilitator used to accept any structurally valid x402 payload
(constitution G2). The USDC contract does not: it recovers the EIP-712
signer and requires it equals ``from`` (EIP-3009
``transferWithAuthorization``). Coinbase's x402 facilitator and Circle's
signing docs do the same check before they will submit.

This module is that check, in-process:

1. Reconstruct the typed-data payload from the authorization + the pinned
   USDC domain for the named network (``veritas.x402.EIP712_DOMAINS``).
2. Recover the signer with ``eth_account``.
3. Refuse unless the recovered address equals ``authorization.from``.
4. Refuse an authorization outside its ``validAfter`` / ``validBefore``
   window.

This does **not** prove the nonce is unused on chain or that the payer
has balance. Those stay on-chain (constitution G13). Calldata helpers for
the USDC ``authorizationState`` and ERC-20 ``balanceOf`` views live here
so an operator-opted-in checker can encode them; the signature check
itself never calls RPC. Missing ``eth_account`` fails closed.
"""

from __future__ import annotations

import re
from typing import Any

from veritas.x402 import (
    USDC_ASSETS,
    eip712_domain,
    payment_authorization,
)

TRANSFER_WITH_AUTHORIZATION_TYPES = {
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
}

_SIG_RE = re.compile(r"\A0x[0-9a-fA-F]{130}\Z")
_NONCE_RE = re.compile(r"\A0x[0-9a-fA-F]{64}\Z")
_UINT_RE = re.compile(r"\A[0-9]+\Z")
_ADDR = re.compile(r"\A0x[0-9a-fA-F]{40}\Z")

# keccak256("authorizationState(address,bytes32)")[:4]
AUTHORIZATION_STATE_SELECTOR = "0xe94a0102"
# keccak256("balanceOf(address)")[:4]
BALANCE_OF_SELECTOR = "0x70a08231"


def payment_signature(payload: dict[str, Any]) -> str | None:
    """The hex signature on an x402 exact payload, or None."""
    inner = payload.get("payload")
    if isinstance(inner, dict):
        sig = inner.get("signature")
        if isinstance(sig, str) and _SIG_RE.fullmatch(sig):
            return sig
    sig = payload.get("signature")
    if isinstance(sig, str) and _SIG_RE.fullmatch(sig):
        return sig
    return None


def _as_uint(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and _UINT_RE.fullmatch(value):
        return int(value)
    return None


def _as_nonce(value: Any) -> bytes | None:
    if isinstance(value, (bytes, bytearray)) and len(value) == 32:
        return bytes(value)
    if isinstance(value, str) and _NONCE_RE.fullmatch(value):
        return bytes.fromhex(value[2:])
    return None


def _as_address(value: Any) -> str | None:
    if isinstance(value, str) and _ADDR.fullmatch(value):
        return value
    return None


def _pad_address_word(address: str) -> str:
    """Left-pad a 0x-address to a 32-byte ABI word (no 0x prefix)."""
    return address[2:].lower().zfill(64)


def authorization_state_calldata(authorizer: str, nonce: str) -> str:
    """``eth_call`` data for USDC ``authorizationState(from, nonce)``.

    The view returns ``true`` when that nonce has already been used.
    Raises ``ValueError`` if the arguments are not an address + bytes32.
    """
    addr = _as_address(authorizer)
    nonce_bytes = _as_nonce(nonce)
    if addr is None or nonce_bytes is None:
        raise ValueError("authorization_state_args_invalid")
    return AUTHORIZATION_STATE_SELECTOR + _pad_address_word(addr) + nonce_bytes.hex()


def balance_of_calldata(holder: str) -> str:
    """``eth_call`` data for ERC-20 ``balanceOf(holder)``.

    Raises ``ValueError`` if ``holder`` is not an address.
    """
    addr = _as_address(holder)
    if addr is None:
        raise ValueError("balance_of_args_invalid")
    return BALANCE_OF_SELECTOR + _pad_address_word(addr)


def decode_eth_bool(raw: Any) -> bool | None:
    """Decode an ``eth_call`` bool word. ``None`` if the value is unreadable."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int) and not isinstance(raw, bool):
        if raw == 0:
            return False
        if raw == 1:
            return True
        return None
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        value = int(text, 16) if text[:2].lower() == "0x" else int(text)
    except ValueError:
        return None
    if value == 0:
        return False
    if value == 1:
        return True
    return None


def decode_eth_uint(raw: Any) -> int | None:
    """Decode an ``eth_call`` uint256 word. ``None`` if the value is unreadable."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw >= 0 else None
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        value = int(text, 16) if text[:2].lower() == "0x" else int(text)
    except ValueError:
        return None
    return value if value >= 0 else None


def typed_data_for_authorization(
    authorization: dict[str, Any],
    *,
    network: str,
    asset: str | None = None,
) -> dict[str, Any]:
    """Rebuild the EIP-712 payload the buyer signed.

    Domain name/version come from the pinned table, never from the payload:
    a hostile buyer must not pick a domain whose signature we would accept
    but USDC would not.
    """
    domain = eip712_domain(network)
    known = USDC_ASSETS.get(network)
    if known is None:
        raise ValueError(f"no settlement asset for {network!r}")
    contract = asset or known["address"]
    if not isinstance(contract, str) or not _ADDR.fullmatch(contract):
        raise ValueError("verifyingContract is not an address")
    chain_id = int(network.split(":", 1)[1])
    from_addr = _as_address(authorization.get("from"))
    to_addr = _as_address(authorization.get("to"))
    value = _as_uint(authorization.get("value"))
    valid_after = _as_uint(authorization.get("validAfter") or 0)
    valid_before = _as_uint(authorization.get("validBefore"))
    nonce = _as_nonce(authorization.get("nonce"))
    if None in (from_addr, to_addr, value, valid_after, valid_before, nonce):
        raise ValueError("authorization incomplete")
    return {
        "types": TRANSFER_WITH_AUTHORIZATION_TYPES,
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": domain.name,
            "version": domain.version,
            "chainId": chain_id,
            "verifyingContract": contract,
        },
        "message": {
            "from": from_addr,
            "to": to_addr,
            "value": value,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce,
        },
    }


def recover_authorization_signer(
    authorization: dict[str, Any],
    signature: str,
    *,
    network: str,
    asset: str | None = None,
) -> str:
    """Recover the EOA that signed this authorization. Raises on failure."""
    try:
        from eth_account import Account
        from eth_account.messages import encode_typed_data
    except ImportError as exc:
        raise RuntimeError("eth_account_missing") from exc
    typed = typed_data_for_authorization(
        authorization, network=network, asset=asset
    )
    signable = encode_typed_data(full_message=typed)
    recovered = Account.recover_message(signable, signature=signature)
    return recovered.lower()


def verify_payment_signature(
    payload: dict[str, Any],
    *,
    now: int | None = None,
) -> tuple[bool, str]:
    """Return ``(ok, reason)``. ``ok`` is True only for a live, matching signature.

    Reasons are type names, never exception text.
    """
    if not isinstance(payload, dict):
        return False, "payload_missing"
    authorization = payment_authorization(payload)
    if authorization is None:
        return False, "authorization_missing"
    signature = payment_signature(payload)
    if signature is None:
        return False, "signature_missing"
    network = payload.get("network")
    if not isinstance(network, str) or network not in USDC_ASSETS:
        return False, "network_unknown"
    try:
        typed = typed_data_for_authorization(authorization, network=network)
    except ValueError:
        return False, "authorization_incomplete"
    except Exception:
        return False, "authorization_incomplete"
    message = typed["message"]
    if now is not None:
        if now <= int(message["validAfter"]):
            return False, "authorization_not_yet_valid"
        if now >= int(message["validBefore"]):
            return False, "authorization_expired"
    try:
        recovered = recover_authorization_signer(
            authorization, signature, network=network
        )
    except RuntimeError:
        return False, "eth_account_missing"
    except Exception:
        return False, "signature_invalid"
    claimed = str(authorization.get("from") or "").lower()
    if recovered != claimed:
        return False, "signer_mismatch"
    return True, "ok"
