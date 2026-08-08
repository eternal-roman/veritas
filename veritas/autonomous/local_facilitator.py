"""Local facilitator simulator for fully autonomous free-mode operation.

Records payment attempts and settlements without requiring a human-provisioned
facilitator or mainnet wallet. When real facilitator + pay_to are present,
the same interface can be switched to live verification.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from veritas.x402 import decode_payment_header, payment_authorization

RUNTIME = Path(os.getenv("VERITAS_RUNTIME_DIR", ".veritas_runtime"))
SETTLEMENTS = RUNTIME / "settlements.jsonl"
ATTEMPTS = RUNTIME / "payment_attempts.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def record_attempt(request_id: str, headers: dict[str, str], amount: str = "$0.25") -> dict[str, Any]:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": _now(),
        "request_id": request_id,
        "amount": amount,
        "has_signature": bool(headers.get("PAYMENT-SIGNATURE") or headers.get("X-PAYMENT")),
        "mode": "local_simulator",
    }
    with ATTEMPTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def record_settlement(request_id: str, amount: str, status: str = "recorded", meta: dict | None = None) -> dict[str, Any]:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": _now(),
        "request_id": request_id,
        "amount": amount,
        "status": status,
        "meta": meta or {},
        "mode": "local_simulator",
    }
    with SETTLEMENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def verify_payment(headers: dict[str, str], require: bool = False) -> bool:
    """Structural payment check for the local simulator.

    `require=False` is free mode: the request is allowed through and nothing
    is verified — that is stated, not disguised as verification.

    `require=True` decodes the header with the same logic the HTTP surface
    uses (`veritas.x402.decode_payment_header`) and demands the x402
    structural minimum: a payload carrying an authorization object. This
    closed gap G1 (any non-empty string previously bought access). What it
    still does not do is verify signatures — that is gap G2 in the
    constitution's register, and it is why this module must never be exposed
    as a paid network surface; the server's facilitator verification is the
    strong gate.
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
    return payment_authorization(payload) is not None
