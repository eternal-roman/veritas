#!/usr/bin/env python3
"""Phase 0.1 — Testnet settlement proof harness for Veritas.

Acceptance: Base Sepolia USDC transfer buyer → VERITAS_PAY_TO from unattended request.

Usage:
  # Server (testnet live mode)
  export VERITAS_PAY_TO=0xYourReceiver
  export VERITAS_FACILITATOR=https://x402.org/facilitator
  export VERITAS_REQUIRE_PAYMENT=true
  export VERITAS_NETWORK=eip155:84532
  export VERITAS_PRICE=0.01
  veritas-server

  # Client
  export VERITAS_BASE_URL=http://127.0.0.1:8000
  export BUYER_PRIVATE_KEY=0x...   # testnet key funded with Sepolia USDC
  python scripts/testnet_settlement.py

Does not claim Phase 0.1 success without a non-simulated on-chain tx hash.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_URL = os.environ.get("VERITAS_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
BUYER_KEY = os.environ.get("BUYER_PRIVATE_KEY", "")
QUERY = os.environ.get("VERITAS_TEST_QUERY", "What is the x402 payment protocol?")
OUT_DIR = Path(os.environ.get("VERITAS_SETTLEMENT_OUT", "settlement_runs"))
TIMEOUT = 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def http_json(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req_headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode()
            payload = json.loads(raw) if raw else {}
            return resp.status, payload, {k: v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode() if exc.fp else ""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload, {k: v for k, v in (exc.headers.items() if exc.headers else [])}


def step_unpaid_challenge() -> dict[str, Any]:
    status, body, hdrs = http_json("POST", f"{BASE_URL}/v1/research", {"query": QUERY})
    result: dict[str, Any] = {
        "step": "unpaid_challenge",
        "http_status": status,
        "body": body,
        "payment_required_header": hdrs.get("Payment-Required") or hdrs.get("PAYMENT-REQUIRED"),
    }
    if status != 402:
        result["error"] = f"expected 402, got {status}"
    if not (body.get("accepts") or []):
        result["error"] = result.get("error") or "402 body missing accepts[]"
    return result


def build_payment_payload(requirements: dict[str, Any]) -> dict[str, Any]:
    if not BUYER_KEY:
        return {
            "error": "BUYER_PRIVATE_KEY not set",
            "hint": "Export a Base Sepolia test key funded with test USDC",
        }
    try:
        from eth_account import Account
        from eth_account.messages import encode_typed_data
    except ImportError:
        return {"error": "eth_account not installed", "hint": "pip install eth_account"}

    account = Account.from_key(BUYER_KEY)
    pay_to = requirements["payTo"]
    asset = requirements["asset"]
    network = requirements["network"]
    value = requirements["maxAmountRequired"]
    chain_id = int(network.split(":")[1]) if ":" in network else 84532

    now = int(time.time())
    valid_after = 0
    valid_before = now + int(requirements.get("maxTimeoutSeconds") or 60)
    nonce = os.urandom(32)

    typed = {
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
            "name": (requirements.get("extra") or {}).get("name") or "USDC",
            "version": (requirements.get("extra") or {}).get("version") or "2",
            "chainId": chain_id,
            "verifyingContract": asset,
        },
        "message": {
            "from": account.address,
            "to": pay_to,
            "value": int(value),
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
                "to": pay_to,
                "value": str(value),
                "validAfter": str(valid_after),
                "validBefore": str(valid_before),
                "nonce": "0x" + nonce.hex(),
            },
        },
        "payer": account.address,
    }


def encode_x_payment(payment_payload: dict[str, Any]) -> str:
    raw = json.dumps(payment_payload, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def step_paid_request(x_payment: str) -> dict[str, Any]:
    status, body, hdrs = http_json(
        "POST",
        f"{BASE_URL}/v1/research",
        {"query": QUERY},
        headers={"X-PAYMENT": x_payment},
    )
    return {
        "step": "paid_request",
        "http_status": status,
        "body": body,
        "payment_response_header": hdrs.get("X-Payment-Response") or hdrs.get("X-PAYMENT-RESPONSE"),
    }


def extract_settlement_proof(paid: dict[str, Any]) -> dict[str, Any]:
    body = paid.get("body") or {}
    sett = body.get("settlement") or body.get("payment") or {}
    if not isinstance(sett, dict):
        sett = {}
    return {
        "request_id": body.get("request_id"),
        "status": body.get("status"),
        "billable": body.get("billable"),
        "custody_root": body.get("custody_root"),
        "settlement": sett,
        "transaction": sett.get("transaction") or sett.get("tx_hash"),
        "payer": sett.get("payer"),
        "network": sett.get("network"),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT_DIR / f"settlement_{run_id}.json"
    report: dict[str, Any] = {
        "run_id": run_id,
        "started_at": _now(),
        "base_url": BASE_URL,
        "query": QUERY,
        "steps": [],
        "acceptance": {
            "criterion": "Base Sepolia USDC transfer buyer → VERITAS_PAY_TO from unattended request",
            "met": False,
            "transaction": None,
            "notes": [],
        },
    }

    try:
        st, health, _ = http_json("GET", f"{BASE_URL}/health")
        report["steps"].append({"step": "health", "http_status": st, "body": health})
    except Exception as exc:
        report["steps"].append({"step": "health", "error": str(exc)})
        report["acceptance"]["notes"].append("server unreachable")
        out_path.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 1

    challenge = step_unpaid_challenge()
    report["steps"].append(challenge)
    if challenge.get("error"):
        report["acceptance"]["notes"].append(challenge["error"])
        out_path.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 1

    requirements = (challenge["body"].get("accepts") or [None])[0]
    report["requirements"] = requirements

    payment_payload = build_payment_payload(requirements)
    report["steps"].append({
        "step": "build_payment",
        "has_error": "error" in payment_payload,
        "payer": payment_payload.get("payer"),
        "error": payment_payload.get("error"),
    })
    if "error" in payment_payload:
        report["acceptance"]["notes"].append(payment_payload["error"])
        if payment_payload.get("hint"):
            report["acceptance"]["notes"].append(payment_payload["hint"])
        out_path.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 1

    x_payment = encode_x_payment(payment_payload)
    paid = step_paid_request(x_payment)
    report["steps"].append(paid)
    proof = extract_settlement_proof(paid)
    report["proof"] = proof

    tx = proof.get("transaction")
    if paid.get("http_status") == 200 and tx and not str(tx).startswith("simulated"):
        report["acceptance"]["met"] = True
        report["acceptance"]["transaction"] = tx
        report["acceptance"]["notes"].append("on-chain transaction field present")
    elif paid.get("http_status") == 200 and str(tx or "").startswith("simulated"):
        report["acceptance"]["notes"].append("simulated settlement — not Phase 0.1 proof")
    else:
        report["acceptance"]["notes"].append(
            f"paid status={paid.get('http_status')}; no real tx"
        )

    report["finished_at"] = _now()
    out_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"Wrote {out_path}", file=sys.stderr)

    rid = proof.get("request_id")
    if rid:
        st, receipt, _ = http_json("GET", f"{BASE_URL}/v1/receipts/{rid}")
        (OUT_DIR / f"receipt_{rid}.json").write_text(
            json.dumps({"http_status": st, "receipt": receipt}, indent=2)
        )
    return 0 if report["acceptance"]["met"] else 2


if __name__ == "__main__":
    sys.exit(main())
