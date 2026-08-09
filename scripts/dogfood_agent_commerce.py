#!/usr/bin/env python3
"""Dogfood multi-agent testnet commerce (Base Sepolia USDC via x402).

1. Load roster from ``.veritas_dogfood/roster.json``
2. Probe RPC + facilitator + USDC balances
3. Against a **live-mode** server: unpaid 402 → pay_via_policy → paid research
4. Emit commerce gap report for multi-agent value flow

Exit 0 = acceptance met (real non-simulated tx). Exit 2 = honest incomplete
(unfunded / captcha / misconfigured / no server). Exit 1 = hard failure.
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

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from veritas.buyer_payment import (  # noqa: E402
    BuyerPaymentError,
    acceptance_met,
    extract_settlement_proof,
    pay_via_policy,
)
from veritas.safeurl import require_http_url  # noqa: E402

USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
DEFAULT_RPC = "https://sepolia.base.org"
DEFAULT_FACILITATOR = "https://x402.org/facilitator"
DOGFOOD = ROOT / ".veritas_dogfood"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def http_json(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 60.0,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    data = None if body is None else json.dumps(body).encode()
    hdrs = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "veritas-dogfood-commerce/0.8.1",
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(
        require_http_url(url), data=data, headers=hdrs, method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {}), dict(resp.headers.items())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode() if exc.fp else ""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload, dict(exc.headers.items()) if exc.headers else {}


def usdc_balance(rpc: str, holder: str) -> dict[str, Any]:
    addr = holder.lower().replace("0x", "").zfill(64)
    data = "0x70a08231" + addr
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": USDC_BASE_SEPOLIA, "data": data}, "latest"],
    }
    req = urllib.request.Request(
        rpc,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "veritas-dogfood-commerce/0.8.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
        payload = json.loads(resp.read().decode())
    if "error" in payload:
        return {"ok": False, "error": payload["error"]}
    atomic = int(payload["result"], 16)
    return {"ok": True, "atomic": atomic, "usdc": atomic / 1_000_000, "address": holder}


def commerce_gap_report(
    *,
    balances: dict[str, Any],
    settle_ok: bool,
    payment_mode: str | None,
    notes: list[str],
) -> dict[str, Any]:
    return {
        "schema": "veritas.commerce_gap.v0",
        "vision": (
            "Each agent holds a budget of value-tokens and pays peers under a "
            "community agreement of value (priced services + bonds)."
        ),
        "proven_this_run": {
            "wallet_generation": True,
            "testnet_usdc_balance_probe": True,
            "rpc_chainid_base_sepolia": True,
            "facilitator_supported_reachable": True,
            "x402_settle_e2e": settle_ok,
            "server_live_mode": payment_mode == "live",
        },
        "proven_prior_project_evidence": {
            "note": "Same-operator testnet settles already on tip (n=2); see docs/program/fable/settlement/",
            "settlements_on_main_claim": "2 testnet self-dogfood",
        },
        "missing_or_partial": [
            {
                "id": "faucet_automation",
                "severity": "high",
                "gap": "Circle faucet reCAPTCHA + bot detection blocks unattended funding",
                "plan": "Headed Playwright + human captcha; cache funded wallets; "
                "2h rate limit; optional Circle console API for Circle Wallets",
                "evidence": "faucet_*.json under .veritas_dogfood/",
            },
            {
                "id": "multi_agent_usdc_roster",
                "severity": "high",
                "gap": "Product path is one seller pay-to + one buyer key; no on-chain "
                "per-agent USDC budget ledger with community prices",
                "plan": "Roster (address, role, spend cap) + per-agent Signer; "
                "optional shared paymaster",
            },
            {
                "id": "community_value_agreement",
                "severity": "high",
                "gap": "No machine-readable bilateral/community rate card; price is seller-only",
                "plan": "Discovery price_table + warranty class; buyer SpendPolicy max; "
                "optional rate-card negotiation protocol",
            },
            {
                "id": "plane_vaat_vs_product_usdc",
                "severity": "medium",
                "gap": "Plane VAAT quality-pay ≠ USDC; must never auto-convert",
                "plan": "Explicit bridge policy; SIWx map; label not_x402 always",
            },
            {
                "id": "peer_seller_export",
                "severity": "high",
                "gap": "Only Veritas research sells; peers cannot list services under same norms",
                "plan": "Export constitution + x402 accept template; second seller dogfood process",
            },
            {
                "id": "unsolicited_counterparty",
                "severity": "high",
                "gap": "All on-chain settles so far are same-operator",
                "plan": "Stage-1 public host + registry; metric unsolicited paid ≥ 1",
            },
            {
                "id": "w1_bond_escrow",
                "severity": "medium",
                "gap": "W0 warranty without escrowed bonds — verification not paid niche yet",
                "plan": "After public money: FALSIFIABLE_COMMERCE W1",
            },
            {
                "id": "live_mode_public_url",
                "severity": "medium",
                "gap": "Live mode requires VERITAS_PUBLIC_URL or serves misconfigured",
                "plan": "Dogfood always sets PUBLIC_URL=http://127.0.0.1:PORT for local live",
            },
            {
                "id": "g9_production_routine",
                "severity": "medium",
                "gap": "Reconcile path exists; not always-on production ops",
                "plan": "Runbook + alerts; never rewrite ledger",
            },
        ],
        "balances_snapshot": balances,
        "notes": notes,
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--base-url",
        default=os.environ.get("VERITAS_BASE_URL", "http://127.0.0.1:8765"),
    )
    ap.add_argument("--rpc", default=os.environ.get("VERITAS_RPC_URL", DEFAULT_RPC))
    ap.add_argument("--roster", default=str(DOGFOOD / "roster.json"))
    ap.add_argument("--query", default="What is the x402 payment protocol?")
    ap.add_argument("--skip-settle", action="store_true")
    args = ap.parse_args()

    report: dict[str, Any] = {
        "started_at": _now(),
        "base_url": args.base_url,
        "rpc": args.rpc,
        "steps": [],
        "acceptance": {"met": False, "transaction": None},
    }
    notes: list[str] = []

    roster_path = Path(args.roster)
    if not roster_path.is_file():
        print("missing roster — generate wallets first", file=sys.stderr)
        return 1
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    buyer = json.loads(
        (ROOT / roster["agents"]["buyer"]["key_file"]).read_text(encoding="utf-8")
    )
    seller_addr = roster["agents"]["seller"]["address"]
    report["roster_addresses"] = {k: v["address"] for k, v in roster["agents"].items()}

    payment_mode = None
    try:
        st, health, _ = http_json("GET", f"{args.base_url.rstrip('/')}/health")
        payment_mode = health.get("payment_mode")
        report["steps"].append({"step": "health", "status": st, "body": health})
        if payment_mode == "misconfigured":
            notes.append(
                "server payment_mode=misconfigured — set VERITAS_PUBLIC_URL + PAY_TO + REQUIRE_PAYMENT"
            )
        if payment_mode == "free":
            notes.append("server free mode — not a live settle path")
    except Exception as exc:  # noqa: BLE001
        report["steps"].append({"step": "health", "error": str(exc)})
        notes.append("server unreachable")

    try:
        st, _fac, _ = http_json("GET", f"{DEFAULT_FACILITATOR}/supported")
        report["steps"].append({"step": "facilitator_supported", "status": st})
    except Exception as exc:  # noqa: BLE001
        report["steps"].append({"step": "facilitator_supported", "error": str(exc)})

    balances: dict[str, Any] = {}
    for role, meta in roster["agents"].items():
        balances[role] = usdc_balance(args.rpc, meta["address"])
    report["balances"] = balances
    buyer_usdc = float(balances.get("buyer", {}).get("usdc") or 0)
    if buyer_usdc <= 0:
        notes.append(
            "buyer USDC=0 — fund: python scripts/circle_faucet_playwright.py "
            f"--address {buyer['address']} --headed --wait-human 120"
        )

    settle_ok = False
    health_ok = any(
        s.get("step") == "health" and s.get("status") == 200 for s in report["steps"]
    )
    live_ok = payment_mode == "live"

    if args.skip_settle:
        notes.append("skip_settle set")
    elif not health_ok:
        notes.append("skip settle — server not healthy")
    elif not live_ok:
        notes.append("skip settle — server not live mode")
    elif buyer_usdc <= 0:
        notes.append("skip settle — buyer unfunded")
    else:
        try:
            st, body, _hdrs = http_json(
                "POST",
                f"{args.base_url.rstrip('/')}/v1/research",
                {"query": args.query},
            )
            report["steps"].append(
                {
                    "step": "unpaid",
                    "status": st,
                    "has_accepts": bool(body.get("accepts")),
                }
            )
            if st == 402 and body.get("accepts"):
                requirements = body["accepts"][0]
                x_payment, payment_payload = pay_via_policy(
                    requirements, buyer["private_key"]
                )
                report["steps"].append(
                    {
                        "step": "build_payment",
                        "payer": payment_payload.get("payload", {})
                        .get("authorization", {})
                        .get("from"),
                        "network": payment_payload.get("network"),
                        "seller_pay_to": seller_addr,
                        "challenge_pay_to": requirements.get("payTo"),
                    }
                )
                paid_st, paid_body, paid_hdrs = http_json(
                    "POST",
                    f"{args.base_url.rstrip('/')}/v1/research",
                    {"query": args.query},
                    headers={"X-PAYMENT": x_payment},
                )
                proof = extract_settlement_proof(paid_body)
                tx = proof.get("transaction")
                met = acceptance_met(paid_st, tx)
                report["steps"].append(
                    {
                        "step": "paid_request",
                        "http_status": paid_st,
                        "acceptance_met": met,
                        "transaction": tx,
                        "status": paid_body.get("status"),
                        "billable": paid_body.get("billable"),
                    }
                )
                report["acceptance"]["met"] = bool(met)
                report["acceptance"]["transaction"] = tx
                settle_ok = bool(met)
                if not met:
                    notes.append(
                        f"paid status={paid_st} tx={tx!r} — not Phase 0.1 acceptance"
                    )
            else:
                notes.append(f"expected 402 accepts, got {st}")
        except BuyerPaymentError as exc:
            notes.append(f"BuyerPaymentError: {exc}")
            report["steps"].append({"step": "settle_error", "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            notes.append(f"settle exception: {exc}")
            report["steps"].append({"step": "settle_error", "error": str(exc)})

    report["gaps"] = commerce_gap_report(
        balances=balances,
        settle_ok=settle_ok,
        payment_mode=payment_mode,
        notes=notes,
    )
    report["finished_at"] = _now()
    report["notes"] = notes

    out = DOGFOOD / f"commerce_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    DOGFOOD.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {out}", file=sys.stderr)

    if settle_ok:
        return 0
    if buyer_usdc <= 0 or not live_ok or any("unreachable" in n for n in notes):
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
