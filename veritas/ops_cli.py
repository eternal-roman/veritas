"""veritas-ops: the operator's questions, answered from the ledger.

An operator running this service has four questions, and before this command
there was no way to ask any of them:

    veritas-ops revenue                  how much did I earn, and what did it cost?
    veritas-ops owed                     what did I deliver and never get paid for?
    veritas-ops reconcile                what needs my attention?
    veritas-ops usage                    what did serving actually consume?
    veritas-ops authorization <nonce>    one payment, end to end
    veritas-ops pricing                  what price are new entries stamped with?

Every command prints JSON to stdout, because the first consumer of an
operations CLI for an agent-native service is another agent.

**What `reconcile` does not do.** It compares this instance's own records
against each other. It does not contact any chain, so a `settled` entry means
"the facilitator told us it settled", not "the transfer is confirmed on
Base". That limit is printed in the report itself and is registered as
constitution gap G9 — closing it needs an RPC endpoint. A reconcile report
that implied on-chain confirmation it had not performed would be the most
damaging untruth this codebase could ship, so it says so every time.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from typing import Any

from veritas.ledger import Ledger, NonceState
from veritas.metering import CostTable
from veritas.payment_config import get_payment_config
from veritas.pricing import current_price_point

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
    sub.add_parser("usage", help="What serving consumed, priced where possible.")
    sub.add_parser("pricing", help="The price new ledger entries are stamped with.")
    one = sub.add_parser("authorization", help="One payment authorization, end to end.")
    one.add_argument("nonce", help="The 0x-prefixed 32-byte authorization nonce.")
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
        owed = [asdict(a) for a in ledger.awaiting_settlement()]
        payload = {"count": len(owed), "awaiting_settlement": owed}
    elif args.command == "reconcile":
        payload = _reconcile(ledger)
    elif args.command == "usage":
        payload = ledger.usage_summary(costs)
    elif args.command == "pricing":
        cfg = get_payment_config()
        payload = current_price_point(cfg.price, cfg.network)
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
