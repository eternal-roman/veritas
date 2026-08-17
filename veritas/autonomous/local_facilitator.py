"""Local facilitator simulator for fully autonomous free-mode operation.

Records payment attempts and settlements without requiring a human-provisioned
facilitator or mainnet wallet. When real facilitator + pay_to are present,
the same interface can be switched to live verification.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from veritas.chain_reconcile import rpc_url_from_env
from veritas.eip3009 import (
    authorization_state_calldata,
    balance_of_calldata,
    decode_eth_bool,
    decode_eth_uint,
    verify_payment_signature,
)
from veritas.runtime import resolve_runtime_dir
from veritas.x402 import USDC_ASSETS, decode_payment_header, payment_authorization

# Explicit opt-in for on-chain nonce/balance views. Default unset/off: the
# simulator stays a G13-open local check (signature only). Accepted truthy
# values: 1, true, yes, on (case-insensitive). Any other value, including
# empty, leaves the default path unchanged and does not call RPC.
ENV_CHAIN_CHECKS = "VERITAS_FACILITATOR_CHAIN_CHECKS"

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _runtime() -> Path:
    return resolve_runtime_dir()


def _settlements() -> Path:
    return _runtime() / "settlements.jsonl"


def _attempts() -> Path:
    return _runtime() / "payment_attempts.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def record_attempt(request_id: str, headers: dict[str, str], amount: str = "$0.25") -> dict[str, Any]:
    runtime = _runtime()
    runtime.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": _now(),
        "request_id": request_id,
        "amount": amount,
        "has_signature": bool(headers.get("PAYMENT-SIGNATURE") or headers.get("X-PAYMENT")),
        "mode": "local_simulator",
    }
    with _attempts().open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def record_settlement(request_id: str, amount: str, status: str = "recorded", meta: dict | None = None) -> dict[str, Any]:
    runtime = _runtime()
    runtime.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": _now(),
        "request_id": request_id,
        "amount": amount,
        "status": status,
        "meta": meta or {},
        "mode": "local_simulator",
    }
    with _settlements().open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def chain_checks_opted_in() -> bool:
    """True only when ``VERITAS_FACILITATOR_CHAIN_CHECKS`` is an explicit opt-in.

    Unset (the default) keeps G13's default path: no RPC is consulted.
    """
    raw = (os.getenv(ENV_CHAIN_CHECKS) or "").strip().lower()
    return raw in _TRUTHY


def _rpc_transport(url: str, method: str, params: list[Any]) -> Any:
    # Reuse the G9 client: versioned User-Agent, env timeout, http(s) only.
    from veritas.chain_reconcile import _default_transport

    return _default_transport(url, method, params)


def _check_nonce_unused_and_balance(
    payload: dict[str, Any],
    *,
    transport: Any | None = None,
) -> bool:
    """On-chain nonce-unused + ``balanceOf(from) >= value``. Fail closed.

    Requires an explicit ``VERITAS_RPC_URL``. A missing URL, transport error,
    timeout, or unreadable result refuses the payment. Does not invent a
    second chain client: calls go through ``veritas.chain_reconcile``.
    """
    url = rpc_url_from_env()
    if not url:
        return False
    authorization = payment_authorization(payload)
    if authorization is None:
        return False
    network = payload.get("network")
    asset = USDC_ASSETS.get(network) if isinstance(network, str) else None
    if asset is None:
        return False
    from_addr = authorization.get("from")
    nonce = authorization.get("nonce")
    value = authorization.get("value")
    if not isinstance(from_addr, str) or not isinstance(nonce, str):
        return False
    try:
        needed = int(value) if not isinstance(value, bool) else -1
    except (TypeError, ValueError):
        return False
    if needed < 0:
        return False
    token = asset["address"]
    call = transport or _rpc_transport
    try:
        used_raw = call(
            url,
            "eth_call",
            [
                {
                    "to": token,
                    "data": authorization_state_calldata(from_addr, nonce),
                },
                "latest",
            ],
        )
        used = decode_eth_bool(used_raw)
        if used is None or used is True:
            return False
        balance_raw = call(
            url,
            "eth_call",
            [
                {
                    "to": token,
                    "data": balance_of_calldata(from_addr),
                },
                "latest",
            ],
        )
        balance = decode_eth_uint(balance_raw)
        if balance is None or balance < needed:
            return False
    except Exception:
        return False
    return True


def verify_payment(
    headers: dict[str, str],
    require: bool = False,
    *,
    transport: Any | None = None,
) -> bool:
    """Payment check for the local simulator.

    ``require=False`` is free mode: the request is allowed through and
    nothing is verified — that is stated, not disguised as verification.

    ``require=True`` decodes the header and recovers the EIP-712 signer of
    the EIP-3009 authorization (constitution G2, closed 2.9). A forged or
    expired signature is refused. This still does not prove the nonce is
    unused on chain or that the payer has balance (G13) **unless** the
    operator has opted in.

    Optional on-chain checks (USDC ``authorizationState(from, nonce)`` and
    ``balanceOf(from) >= value``) run only when **both** are set:

    * ``VERITAS_FACILITATOR_CHAIN_CHECKS`` is an explicit opt-in
      (``1`` / ``true`` / ``yes`` / ``on``; default unset/off)
    * ``VERITAS_RPC_URL`` is configured (env RPC wins; no silent public
      default is used for this path)

    When the opt-in is on, a missing RPC, transport error, timeout, or
    missing ``eth_account`` fails closed — a payment that could not be
    checked is refused. When the opt-in is off, no RPC is called. This
    does not close G13: the default path is unchanged. This module is not
    a paid network surface; no new HTTP is exposed.
    """
    if not require:
        return True
    raw = (
        headers.get("X-PAYMENT")
        or headers.get("PAYMENT-SIGNATURE")
        or headers.get("payment-signature")
        or ""
    )
    payload = decode_payment_header(raw)
    if payload is None:
        return False
    ok, _reason = verify_payment_signature(payload, now=int(time.time()))
    if not ok:
        return False
    if not chain_checks_opted_in():
        return True
    return _check_nonce_unused_and_balance(payload, transport=transport)
