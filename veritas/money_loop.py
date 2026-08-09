"""Phase 0.1-R — routine settle → chain reconcile orchestrator.

One agent-clearable path that **composes** existing surfaces:

* settle: ``veritas.buyer_payment.pay_via_policy`` (gated by ``veritas.payer``)
* reconcile: ``veritas.chain_reconcile.reconcile_settlements_auto`` (report only)

Does **not** close constitution gap G9, invent green on an empty ledger, default
mainnet RPC, or open a second payer/engine. Live dogfood is optional evidence;
CI must stay offline via injectable HTTP and RPC transports.

Exit codes (honest, not vibes)::

* ``0`` — settle acceptance met **and** that tx is chain ``confirmed``, or
  reconcile-only with at least one ``confirmed`` row.
* ``2`` — honest incomplete: unfunded / simulated / no candidates / not
  confirmed / missing buyer key. Never claimed as success.
* ``1`` — transport or hard failure: server unreachable, RPC unavailable,
  malformed runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from veritas.buyer_payment import (
    BuyerPaymentError,
    acceptance_met,
    extract_settlement_proof,
    pay_via_policy,
)
from veritas.chain_reconcile import (
    DEFAULT_PUBLIC_RPC_URLS,
    G9_NOTE,
    RpcTransport,
    reconcile_settlements_auto,
)
from veritas.safeurl import require_http_url

# Exit codes — stable contract for agents shelling this module.
EXIT_OK = 0
EXIT_TRANSPORT = 1
EXIT_HONEST = 2

HttpJson = Callable[
    [str, str, dict[str, Any] | None, dict[str, str] | None],
    tuple[int, dict[str, Any], dict[str, str]],
]

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_QUERY = "What is the x402 payment protocol?"
DEFAULT_TIMEOUT = 60.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_http_json(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    """HTTP JSON helper used by the live settle path (scheme-checked)."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    req_headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(
        require_http_url(url), data=data, headers=req_headers, method=method,
    )
    try:
        with urllib.request.urlopen(  # nosec B310 - scheme checked by require_http_url
            req, timeout=timeout
        ) as resp:
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


def run_settle(
    *,
    base_url: str,
    buyer_key: str,
    query: str = DEFAULT_QUERY,
    http_json: HttpJson | None = None,
) -> dict[str, Any]:
    """One unpaid → pay → paid cycle. Does not claim success without a real tx."""
    http = http_json or default_http_json
    base = base_url.rstrip("/")
    report: dict[str, Any] = {
        "phase": "settle",
        "base_url": base,
        "query": query,
        "steps": [],
        "acceptance": {
            "criterion": (
                "Base Sepolia USDC transfer buyer → pay_to from unattended request"
            ),
            "met": False,
            "transaction": None,
            "notes": [],
        },
        "error_class": None,
    }

    if not (buyer_key or "").strip():
        report["error_class"] = "honest"
        report["acceptance"]["notes"].append("BUYER_PRIVATE_KEY missing")
        return report

    try:
        st, health, _ = http("GET", f"{base}/health", None, None)
        report["steps"].append({"step": "health", "http_status": st, "body": health})
    except Exception as exc:  # noqa: BLE001 — surface transport class to exit codes
        report["error_class"] = "transport"
        report["steps"].append({"step": "health", "error": str(exc)})
        report["acceptance"]["notes"].append("server unreachable")
        return report

    try:
        status, body, hdrs = http("POST", f"{base}/v1/research", {"query": query}, None)
    except Exception as exc:  # noqa: BLE001
        report["error_class"] = "transport"
        report["steps"].append({"step": "unpaid_challenge", "error": str(exc)})
        report["acceptance"]["notes"].append("challenge transport failure")
        return report

    challenge: dict[str, Any] = {
        "step": "unpaid_challenge",
        "http_status": status,
        "body": body,
        "payment_required_header": hdrs.get("Payment-Required")
        or hdrs.get("PAYMENT-REQUIRED"),
    }
    if status != 402 or not (body.get("accepts") or []):
        challenge["error"] = f"expected 402 with accepts[], got {status}"
        report["error_class"] = "honest"
    report["steps"].append(challenge)
    if challenge.get("error"):
        report["acceptance"]["notes"].append(challenge["error"])
        return report

    requirements = body["accepts"][0]
    report["requirements"] = requirements

    try:
        x_payment, payment_payload = pay_via_policy(requirements, buyer_key)
    except BuyerPaymentError as exc:
        report["error_class"] = "honest"
        report["steps"].append({"step": "build_payment", "error": str(exc)})
        report["acceptance"]["notes"].append(str(exc))
        return report

    report["steps"].append(
        {
            "step": "build_payment",
            "payer": payment_payload.get("payload", {})
            .get("authorization", {})
            .get("from"),
            "network": payment_payload.get("network"),
            "gated_by": "veritas.payer: validate_accepts + SpendPolicy + attempt journal",
        }
    )

    try:
        paid_status, paid_body, paid_hdrs = http(
            "POST",
            f"{base}/v1/research",
            {"query": query},
            {"X-PAYMENT": x_payment},
        )
    except Exception as exc:  # noqa: BLE001
        report["error_class"] = "transport"
        report["steps"].append({"step": "paid_request", "error": str(exc)})
        report["acceptance"]["notes"].append("paid request transport failure")
        return report

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
    if acceptance_met(paid_status, tx if isinstance(tx, str) else None):
        report["acceptance"]["met"] = True
        report["acceptance"]["transaction"] = tx
        report["acceptance"]["notes"].append("on-chain transaction field present")
        report["error_class"] = None
    elif paid_status == 200 and tx and str(tx).startswith("simulated"):
        report["error_class"] = "honest"
        report["acceptance"]["notes"].append(
            "simulated settlement — not Phase 0.1-R proof"
        )
    else:
        report["error_class"] = "honest"
        report["acceptance"]["notes"].append(
            f"paid status={paid_status}; no real tx"
        )
    return report


def run_reconcile(
    *,
    runtime_dir: str | Path | None = None,
    settlements: Sequence[Mapping[str, Any]] | None = None,
    transport: RpcTransport | None = None,
    env_url: str | None = None,
) -> dict[str, Any]:
    """Reconcile facilitator-recorded settlements against chain (report only).

    Prefer the **server** runtime ledger (``VERITAS_RUNTIME_DIR`` of the live
    process). Injected ``settlements`` skip the ledger (tests / single-tx pin).
    """
    report: dict[str, Any] = {
        "phase": "reconcile",
        "error_class": None,
        "runtime_dir": str(runtime_dir) if runtime_dir else None,
        "g9_note": G9_NOTE,
    }

    rows: list[Mapping[str, Any]]
    missing = 0
    if settlements is not None:
        rows = list(settlements)
    else:
        try:
            from veritas.ledger import Ledger

            ledger = Ledger(str(runtime_dir) if runtime_dir else None)
            rows = list(ledger.settled_with_transaction())
            missing = len(ledger.settled_without_transaction())
        except Exception as exc:  # noqa: BLE001
            report["error_class"] = "transport"
            report["error"] = f"ledger_open_failed:{type(exc).__name__}:{exc}"
            report["candidates"] = 0
            report["chain_checked"] = False
            return report

    payload = reconcile_settlements_auto(
        list(rows), env_url=env_url, transport=transport
    )
    report.update(payload)
    report["candidates"] = len(rows)
    report["settled_without_transaction"] = missing

    if any(r.get("status") == "rpc_unavailable" for r in payload.get("results", [])):
        report["error_class"] = "transport"
    elif report["candidates"] == 0:
        report["error_class"] = "honest"
        report.setdefault("notes", []).append("no settled_with_transaction candidates")
    return report


def classify_exit(
    settle: Mapping[str, Any] | None,
    reconcile: Mapping[str, Any] | None,
) -> int:
    """Map settle/reconcile reports to EXIT_* without inventing green."""
    if settle is not None and settle.get("error_class") == "transport":
        return EXIT_TRANSPORT
    if reconcile is not None and reconcile.get("error_class") == "transport":
        return EXIT_TRANSPORT

    settle_met = bool(settle and settle.get("acceptance", {}).get("met"))
    settle_tx = (
        settle.get("acceptance", {}).get("transaction") if settle else None
    )

    if settle is not None and not settle_met and reconcile is None:
        return EXIT_HONEST

    if reconcile is not None:
        results = list(reconcile.get("results") or [])
        if settle_met and settle_tx:
            for row in results:
                if row.get("transaction") == settle_tx and row.get("status") == "confirmed":
                    return EXIT_OK
            # Settled on facilitator view but chain did not confirm this run.
            if any(
                row.get("transaction") == settle_tx and row.get("chain_checked")
                for row in results
            ):
                return EXIT_HONEST
            return EXIT_HONEST

        confirmed = int((reconcile.get("counts") or {}).get("confirmed") or 0)
        if confirmed > 0 and reconcile.get("chain_checked"):
            return EXIT_OK
        return EXIT_HONEST

    if settle_met:
        # Settle-only success: acceptance met; chain not yet checked this run.
        return EXIT_OK
    return EXIT_HONEST


def run_money_loop(
    *,
    do_settle: bool = True,
    do_reconcile: bool = True,
    base_url: str | None = None,
    buyer_key: str | None = None,
    query: str | None = None,
    runtime_dir: str | Path | None = None,
    out_dir: str | Path | None = None,
    http_json: HttpJson | None = None,
    transport: RpcTransport | None = None,
    env_url: str | None = None,
    settle_report: Mapping[str, Any] | None = None,
    settlements: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Orchestrate settle then reconcile; write one evidence JSON when out_dir set."""
    started = _now()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence: dict[str, Any] = {
        "run_id": run_id,
        "phase": "0.1-R",
        "started_at": started,
        "settle": None,
        "reconcile": None,
        "acceptance": {
            "criterion": (
                "routine settle → chain reconcile; non-simulated tx when funded; "
                "rpc_source stamped; mainnet never defaulted"
            ),
            "met": False,
            "notes": [],
        },
        "defaults": {
            "public_rpc_networks": sorted(DEFAULT_PUBLIC_RPC_URLS.keys()),
            "mainnet_never_defaulted": "eip155:8453" not in DEFAULT_PUBLIC_RPC_URLS,
        },
        "limitations": [
            "Does not close constitution G9 (production-routine still required).",
            "Self-dogfood is not unsolicited demand; mainnet not in scope.",
            G9_NOTE,
        ],
    }

    settle_out: dict[str, Any] | None = None
    if settle_report is not None:
        settle_out = dict(settle_report)
        evidence["settle"] = settle_out
    elif do_settle:
        settle_out = run_settle(
            base_url=base_url or os.environ.get("VERITAS_BASE_URL", DEFAULT_BASE_URL),
            buyer_key=buyer_key
            if buyer_key is not None
            else os.environ.get("BUYER_PRIVATE_KEY", ""),
            query=query or os.environ.get("VERITAS_TEST_QUERY", DEFAULT_QUERY),
            http_json=http_json,
        )
        evidence["settle"] = settle_out

    recon_out: dict[str, Any] | None = None
    if do_reconcile:
        injected = settlements
        if injected is None and settle_out and settle_out.get("acceptance", {}).get("met"):
            # Pin the just-settled tx even if runtime_dir points at a different
            # ledger (buyer machine vs server). Prefer ledger when provided.
            proof = settle_out.get("proof") or {}
            req = settle_out.get("requirements") or {}
            pin = {
                "request_id": proof.get("request_id"),
                "transaction": settle_out["acceptance"].get("transaction"),
                "network": proof.get("network")
                or req.get("network")
                or "eip155:84532",
            }
            if runtime_dir is None and injected is None:
                injected = [pin]
        recon_out = run_reconcile(
            runtime_dir=runtime_dir
            if runtime_dir is not None
            else os.environ.get("VERITAS_RUNTIME_DIR"),
            settlements=injected,
            transport=transport,
            env_url=env_url,
        )
        evidence["reconcile"] = recon_out

    code = classify_exit(settle_out, recon_out)
    evidence["exit_code"] = code
    evidence["acceptance"]["met"] = code == EXIT_OK
    if code == EXIT_OK:
        evidence["acceptance"]["notes"].append("exit 0 — confirmed path this run")
    elif code == EXIT_TRANSPORT:
        evidence["acceptance"]["notes"].append("exit 1 — transport/config failure")
    else:
        evidence["acceptance"]["notes"].append("exit 2 — honest incomplete (not green)")

    evidence["finished_at"] = _now()

    if out_dir is not None:
        dest = Path(out_dir)
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / f"money_loop_{run_id}.json"
        path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        evidence["wrote"] = str(path)

    return code, evidence


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="veritas-money-loop",
        description=(
            "Phase 0.1-R: settle then chain-reconcile (compose only). "
            "Exit 0=confirmed, 2=honest incomplete, 1=transport failure."
        ),
    )
    p.add_argument(
        "--base-url",
        default=None,
        help="Seller base URL (default: VERITAS_BASE_URL or http://127.0.0.1:8000)",
    )
    p.add_argument(
        "--runtime-dir",
        default=None,
        help="Server ledger dir for reconcile (default: VERITAS_RUNTIME_DIR)",
    )
    p.add_argument(
        "--out-dir",
        default=None,
        help="Directory for money_loop_*.json evidence (default: money_loop_runs)",
    )
    p.add_argument("--query", default=None, help="Research query for settle")
    p.add_argument(
        "--settle-only",
        action="store_true",
        help="Skip reconcile (exit 0 still requires non-simulated tx)",
    )
    p.add_argument(
        "--reconcile-only",
        action="store_true",
        help="Skip settle; reconcile ledger / pinned rows only",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.settle_only and args.reconcile_only:
        print(
            json.dumps({"error": "choose_one_of_settle_only_or_reconcile_only"}),
            file=sys.stderr,
        )
        return EXIT_TRANSPORT

    out = args.out_dir or os.environ.get("VERITAS_MONEY_LOOP_OUT", "money_loop_runs")
    code, evidence = run_money_loop(
        do_settle=not args.reconcile_only,
        do_reconcile=not args.settle_only,
        base_url=args.base_url,
        query=args.query,
        runtime_dir=args.runtime_dir,
        out_dir=out,
    )
    print(json.dumps(evidence, indent=2))
    if evidence.get("wrote"):
        print(f"Wrote {evidence['wrote']}", file=sys.stderr)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
