"""Local facilitator simulator for fully autonomous free-mode operation.

Records payment attempts and settlements without requiring a human-provisioned
facilitator or mainnet wallet. When real facilitator + pay_to are present,
the same interface can be switched to live verification.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from veritas.eip3009 import verify_payment_signature
from veritas.runtime import resolve_runtime_dir
from veritas.x402 import decode_payment_header


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


def verify_payment(headers: dict[str, str], require: bool = False) -> bool:
    """Payment check for the local simulator.

    ``require=False`` is free mode: the request is allowed through and
    nothing is verified — that is stated, not disguised as verification.

    ``require=True`` decodes the header and recovers the EIP-712 signer of
    the EIP-3009 authorization (constitution G2, closed 2.9). A forged or
    expired signature is refused. This still does not prove the nonce is
    unused on chain or that the payer has balance (G13).
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
    return ok
