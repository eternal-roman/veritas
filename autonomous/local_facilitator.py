"""Local facilitator simulator for fully autonomous free-mode operation.

Records payment attempts and settlements without requiring a human-provisioned
facilitator or mainnet wallet. When real facilitator + pay_to are present,
the same interface can be switched to live verification.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

RUNTIME = Path(os.getenv("VERITAS_RUNTIME_DIR", ".veritas_runtime"))
SETTLEMENTS = RUNTIME / "settlements.jsonl"
ATTEMPTS = RUNTIME / "payment_attempts.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def record_attempt(request_id: str, headers: Dict[str, str], amount: str = "$0.25") -> Dict[str, Any]:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": _now(),
        "request_id": request_id,
        "amount": amount,
        "has_signature": bool(headers.get("PAYMENT-SIGNATURE") or headers.get("X-PAYMENT")),
        "mode": "local_simulator",
    }
    with ATTEMPTS.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def record_settlement(request_id: str, amount: str, status: str = "recorded", meta: Optional[Dict] = None) -> Dict[str, Any]:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": _now(),
        "request_id": request_id,
        "amount": amount,
        "status": status,
        "meta": meta or {},
        "mode": "local_simulator",
    }
    with SETTLEMENTS.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def verify_payment(headers: Dict[str, str], require: bool = False) -> bool:
    """In local mode: always allow if not required; otherwise accept any non-empty signature header.
    Live mode would call the real facilitator.
    """
    if not require:
        return True
    return bool(headers.get("PAYMENT-SIGNATURE") or headers.get("X-PAYMENT") or headers.get("payment-signature"))
