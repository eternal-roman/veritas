#!/usr/bin/env python3
"""Phase 0.1 — Testnet settlement proof harness for Veritas.

Acceptance: Base Sepolia USDC transfer buyer → VERITAS_PAY_TO from unattended request.

Uses veritas.buyer_payment for payload construction (additive package API).
Does not claim Phase 0.1 success without a non-simulated on-chain tx hash.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from veritas.buyer_payment import (
    BuyerPaymentError,
    acceptance_met,
    build_exact_payment_payload,
    encode_x_payment,
    extract_settlement_proof,
)

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

    status, body, hdrs = http_json("POST", f"{BASE_URL}/v1/research", {"query": QUERY})
    challenge: dict[str, Any] = {
        "step": "unpaid_challenge",
        "http_status": status,
        "body": body,
        "payment_required_header": hdrs.get("Payment-Required") or hdrs.get("PAYMENT-REQUIRED"),
    }
    if status != 402 or not (body.get("accepts") or []):
        challenge["error"] = f"expected 402 with accepts[], got {status}"
    report["steps"].append(challenge)
    if challenge.get("error"):
        report["acceptance"]["notes"].append(challenge["error"])
        out_path.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 1

    requirements = body["accepts"][0]
    report["requirements"] = requirements

    try:
        payment_payload = build_exact_payment_payload(requirements, BUYER_KEY)
    except BuyerPaymentError as exc:
        report["steps"].append({"step": "build_payment", "error": str(exc)})
        report["acceptance"]["notes"].append(str(exc))
        out_path.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 1

    report["steps"].append({
        "step": "build_payment",
        "payer": payment_payload.get("payer"),
        "network": payment_payload.get("network"),
    })

    x_payment = encode_x_payment(payment_payload)
    paid_status, paid_body, paid_hdrs = http_json(
        "POST",
        f"{BASE_URL}/v1/research",
        {"query": QUERY},
        headers={"X-PAYMENT": x_payment},
    )
    paid = {
        "step": "paid_request",
        "http_status": paid_status,
        "body": paid_body,
        "payment_response_header": paid_hdrs.get("X-Payment-Response")
        or paid_hdrs.get("X-PAYMENT-RESPONSE"),
    }
    report["steps"].append(paid)
    proof = extract_settlement_proof(paid_body)
    report["proof"] = proof

    tx = proof.get("transaction")
    if acceptance_met(paid_status, tx):
        report["acceptance"]["met"] = True
        report["acceptance"]["transaction"] = tx
        report["acceptance"]["notes"].append("on-chain transaction field present")
    elif paid_status == 200 and tx and str(tx).startswith("simulated"):
        report["acceptance"]["notes"].append("simulated settlement — not Phase 0.1 proof")
    else:
        report["acceptance"]["notes"].append(f"paid status={paid_status}; no real tx")

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
