"""veritas-ops: the operator's questions, answered from the ledger.

An operator running this service has four questions, and before this command
there was no way to ask any of them:

    veritas-ops revenue                  how much did I earn, and what did it cost?
    veritas-ops owed                     what did I deliver and never get paid for?
    veritas-ops reconcile                what needs my attention?
    veritas-ops reconcile-chain          G9 design: check settled tx hashes via RPC
    veritas-ops existence                Stage-1 landmass + human residues (evidence dir)
    veritas-ops usage                    what did serving actually consume?
    veritas-ops authorization <nonce>    one payment, end to end
    veritas-ops pricing                  what price are new entries stamped with?
    veritas-ops prune                    drop expired receipts and ledger rows

Every command prints JSON to stdout, because the first consumer of an
operations CLI for an agent-native service is another agent.

**What `reconcile` does not do.** It compares this instance's own records
against each other. It does not contact any chain, so a `settled` entry means
"the facilitator told us it settled", not "the transfer is confirmed on
Base". That limit is printed in the report itself and is registered as
constitution gap G9 — closing it needs an RPC endpoint. A reconcile report
that implied on-chain confirmation it had not performed would be the most
damaging untruth this codebase could ship, so it says so every time.

**`reconcile-chain` (G9 design).** Classifies facilitator-reported transaction
hashes via ``eth_getTransactionReceipt``. ``VERITAS_RPC_URL`` wins when set;
unset, settlements on a known public **testnet** are checked against that
network's pinned default (``chain_reconcile.DEFAULT_PUBLIC_RPC_URLS``, source
stamped per row) and every other network stays ``rpc_not_configured`` —
mainnet always requires the explicit variable. Never rewrites the ledger or
invents revenue. G9 stays open until reconciliation runs routinely in
production.

**What `prune` does not do.** It ages local custody receipts and settled or
abandoned ledger rows against a shared cutoff. It does not invent settlement
outcomes, does not touch open-exposure states, and does not contact any chain.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from typing import Any

from veritas.custody import CustodyStore
from veritas.ledger import Ledger, NonceState
from veritas.metering import CostTable
from veritas.payment_config import get_payment_config
from veritas.pricing import current_price_point
from veritas.retention import RetentionConfigError, retention_cutoff, retention_days_from_env

CHAIN_LIMITATION = (
    "Records are compared only against each other. Nothing here has been "
    "checked against on-chain state: a 'settled' entry means the facilitator "
    "reported success, not that the transfer is confirmed. See constitution "
    "gap G9."
)


def _reconcile(ledger: Ledger) -> dict[str, Any]:
    """Internal consistency of the ledger, and what an operator must chase."""
    needs_attention: list[dict[str, Any]] = []

    for auth in ledger.awaiting_settlement():
        if auth.state == NonceState.INDETERMINATE:
            # Reported below instead, with the facilitator's own reason —
            # listing it twice under two labels tells the operator there are
            # two problems when there is one.
            continue
        needs_attention.append({
            "reason": (
                "delivered_not_settled" if auth.state == NonceState.DELIVERED
                else "settlement_failed"
            ),
            "request_id": auth.request_id,
            "nonce": auth.nonce,
            "amount": auth.amount,
            "asset": auth.asset,
            "state": auth.state,
            "claimed_at": auth.claimed_at,
            "action": (
                "The buyer holds work we were not paid for. Resubmitting their "
                "authorization returns the stored deliverable and retries "
                "settlement; nothing here re-runs the retrieval."
            ),
        })

    summary = ledger.summary()
    for record in ledger.indeterminate():
        needs_attention.append({
            "reason": "settlement_indeterminate",
            "request_id": record["request_id"],
            "nonce": record["nonce"],
            "amount": record["amount"],
            "asset": record["asset"],
            "facilitator_reason": record["reason"],
            "action": (
                "The facilitator never answered, so the funds may or may not "
                "have moved. Check the payer's authorization nonce on chain "
                "before treating this as revenue or as a loss."
            ),
        })

    for record in ledger.settled_without_transaction():
        needs_attention.append({
            "reason": "settled_without_transaction",
            "request_id": record["request_id"],
            "nonce": record["nonce"],
            "action": (
                "The facilitator reported success with no transaction "
                "reference, so this entry proves nothing. Do not count it as "
                "revenue until a transaction is identified."
            ),
        })

    return {
        "clean": not needs_attention,
        "needs_attention": needs_attention,
        "chain_checked": False,
        "limitation": CHAIN_LIMITATION,
        "summary": summary,
    }


def _owed(ledger: Ledger) -> dict[str, Any]:
    """Delivered work with nothing proving it was paid for.

    Broken out by state because the three are owed in different senses and an
    operator acts differently on each: `delivered` was never settled at all,
    `settlement_failed` was refused, and `indeterminate` may already have paid
    us. Totalled per asset in atomic units — the same units the challenge
    quotes — so the figure can be checked against a settlement.
    """
    entries = [asdict(a) for a in ledger.awaiting_settlement()]
    by_state: dict[str, int] = {}
    at_risk: dict[str, int] = {}
    for entry in entries:
        by_state[entry["state"]] = by_state.get(entry["state"], 0) + 1
        try:
            amount = int(entry["amount"])
        except (TypeError, ValueError):
            continue
        key = f"{entry['network']}/{entry['asset']}"
        at_risk[key] = at_risk.get(key, 0) + amount
    return {
        "count": len(entries),
        "by_state": by_state,
        "amount_at_risk": {k: str(v) for k, v in sorted(at_risk.items())},
        "awaiting_settlement": entries,
        "note": (
            "`indeterminate` entries may already have been paid: the "
            "facilitator never answered. They are counted here because "
            "delivered work is delivered either way, and an operator told "
            "'you are owed nothing' while holding one has been told the "
            "wrong thing."
        ),
    }


def _authorization(ledger: Ledger, nonce: str) -> dict[str, Any] | None:
    auth = ledger.authorization(nonce)
    if auth is None:
        return None
    return {
        "authorization": asdict(auth),
        "settlements": ledger.settlements(auth.request_id),
        "chain_checked": False,
        "limitation": CHAIN_LIMITATION,
    }


def _prune(runtime_dir: str | None, days: int | None) -> dict[str, Any]:
    """Age custody receipts and terminal ledger rows against one cutoff."""
    try:
        window = days if days is not None else retention_days_from_env()
        cutoff = retention_cutoff(days=window)
    except RetentionConfigError as exc:
        return {
            "error": "retention_misconfigured",
            "detail": str(exc),
            "chain_checked": False,
            "limitation": CHAIN_LIMITATION,
        }
    custody = CustodyStore(runtime_dir)
    ledger = Ledger(runtime_dir)
    custody_report = custody.prune(cutoff)
    ledger_report = ledger.prune(cutoff)
    return {
        "retention_days": window,
        "cutoff": cutoff.isoformat().replace("+00:00", "Z"),
        "custody": custody_report,
        "ledger": ledger_report,
        "chain_checked": False,
        "limitation": CHAIN_LIMITATION,
        "note": (
            "Pruned receipt bodies leave durable tombstones so GET "
            "/v1/receipts/{id} returns 410 Gone, not 404. Open-exposure "
            "ledger states (delivered, indeterminate, settlement_failed, "
            "claimed) are never deleted. Settlement outcomes are never "
            "rewritten."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veritas-ops",
        description="Operator reports drawn from the Veritas ledger. JSON on stdout.",
    )
    parser.add_argument(
        "--runtime-dir",
        help="Runtime directory holding the ledger (default: $VERITAS_RUNTIME_DIR).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("revenue", help="Revenue, cost and margin in micro-USD.")
    sub.add_parser("owed", help="Delivered work with no terminal settlement.")
    sub.add_parser("reconcile", help="What needs an operator's attention.")
    sub.add_parser(
        "reconcile-chain",
        help=(
            "G9 design: classify settled tx hashes via VERITAS_RPC_URL, or a "
            "pinned public default for known testnets (mainnet needs the env)."
        ),
    )
    existence = sub.add_parser(
        "existence",
        help=(
            "Stage-1 existence scorecard: confirmed testnet settlements from "
            "on-disk evidence, unsolicited/mainnet never invented, human residues. "
            "Optional --probe measures PyPI + public /health."
        ),
    )
    existence.add_argument(
        "--evidence-dir",
        default=None,
        help="Settlement transcript directory (default: docs/program/fable/settlement).",
    )
    existence.add_argument(
        "--probe",
        action="store_true",
        help=(
            "Contact PyPI JSON API and optional VERITAS_PUBLIC_URL/health "
            "(Stage-1 vision prep; never invents publish)."
        ),
    )
    sub.add_parser("usage", help="What serving consumed, priced where possible.")
    sub.add_parser("pricing", help="The price new ledger entries are stamped with.")
    one = sub.add_parser("authorization", help="One payment authorization, end to end.")
    one.add_argument("nonce", help="The 0x-prefixed 32-byte authorization nonce.")
    prune = sub.add_parser(
        "prune",
        help="Delete expired receipts and settled/abandoned ledger rows (local only).",
    )
    prune.add_argument(
        "--days",
        type=int,
        default=None,
        help="Retention window in days (default: VERITAS_RETENTION_DAYS or 30).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.runtime_dir:
        # Set it rather than only passing it, so any collaborator that reads
        # the environment sees the same runtime as the ledger we open.
        os.environ["VERITAS_RUNTIME_DIR"] = args.runtime_dir
    ledger = Ledger(args.runtime_dir)
    costs = CostTable.from_env()

    if args.command == "revenue":
        payload: dict[str, Any] = ledger.economics(costs)
    elif args.command == "owed":
        payload = _owed(ledger)
    elif args.command == "reconcile":
        payload = _reconcile(ledger)
    elif args.command == "reconcile-chain":
        from veritas.chain_reconcile import reconcile_settlements_auto

        candidates = ledger.settled_with_transaction()
        missing = ledger.settled_without_transaction()
        payload = reconcile_settlements_auto(candidates)
        payload["candidates"] = len(candidates)
        payload["settled_without_transaction"] = len(missing)
        payload["chain_checked"] = bool(payload.get("chain_checked"))
    elif args.command == "existence":
        from pathlib import Path

        from veritas.existence import build_existence_report

        evidence = Path(args.evidence_dir) if args.evidence_dir else None
        payload = build_existence_report(
            evidence_dir=evidence,
            probe=bool(getattr(args, "probe", False)),
        )
    elif args.command == "usage":
        payload = ledger.usage_summary(costs)
    elif args.command == "pricing":
        cfg = get_payment_config()
        payload = current_price_point(cfg.price, cfg.network)
    elif args.command == "prune":
        payload = _prune(args.runtime_dir, args.days)
        if payload.get("error"):
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 1
    else:  # authorization
        found = _authorization(ledger, args.nonce)
        if found is None:
            print(json.dumps({"error": "authorization_not_found", "nonce": args.nonce}))
            return 1
        payload = found

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - console entry point
    raise SystemExit(main())
