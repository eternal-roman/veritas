"""Dogfood cycle 4 — operator economics, answered from the ledger alone.

The question this cycle asks is the one an operator actually has: *am I making
money, and how would I know?* The rule is that every answer must come out of
`veritas-ops`, not out of this script's own bookkeeping. If a number cannot be
obtained that way, that is the finding.

It runs a batch of real paid requests through the real server (local
facilitator stand-in, as in cycle 2), then answers five questions using only
the CLI's JSON:

    revenue      what was earned, in the units a settlement can be checked in
    cost         what serving it consumed, priced only where a price exists
    margin       revenue minus cost, or withheld with a reason
    owed         delivered work with no settlement
    attention    what an operator must chase

Then it reports the **break-even price** implied by the configured cost table
and the measured per-request consumption — a number an operator can act on,
and one that is explicitly a function of an input they supply.

What is measured here and what is not, stated once so no number in the output
is mistaken for something it is not:

* **Measured:** provider calls per request, evidence bytes, handler wall time,
  atomic amounts settled, and every ledger state transition.
* **Supplied by the operator:** the per-provider cost. Nothing in this
  repository can verify a provider's list price, so the default table is empty
  and this cycle passes an explicit, clearly-labelled figure in order to
  demonstrate the arithmetic.
* **Not production figures:** retrieval runs against the offline corpus, so
  the wall times here are a floor. A real provider call dominates them.

`python scripts/dogfood_cycle4.py [--out FILE] [--requests N]`.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.dogfood_cycle2 import Facilitator, _pay  # noqa: E402

QUERY = "What is the x402 payment protocol?"

#: A demonstrative cost, not a measurement. It is passed explicitly so the
#: arithmetic can be shown; the shipped default table is empty precisely
#: because no provider's list price is verifiable from here.
DEMO_COST_MICROS = "static_corpus=250"


def _ops(runtime: Path, *args: str) -> dict[str, Any]:
    """Run `veritas-ops` exactly as an operator would, and parse its JSON."""
    from veritas.ops_cli import main

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = main(["--runtime-dir", str(runtime), *args])
    if code != 0:
        return {"error": "veritas-ops exited nonzero", "exit_code": code}
    return json.loads(buffer.getvalue())


def _serve(runtime: Path, journals: Path, count: int) -> dict[str, Any]:
    """Put `count` real paid requests through the real server."""
    from fastapi.testclient import TestClient

    os.environ.update({
        "VERITAS_RUNTIME_DIR": str(runtime),
        "VERITAS_REQUIRE_PAYMENT": "true",
        "VERITAS_PUBLIC_URL": "https://veritas.example",
        "VERITAS_PAY_TO": "0x" + "22" * 20,
        "VERITAS_NETWORK": "eip155:84532",
        "VERITAS_FACILITATOR": "https://facilitator.invalid",
        "VERITAS_RATE_LIMIT_PER_MINUTE": "0",
        "VERITAS_MAX_PER_REQUEST": "1000000",
        "VERITAS_MAX_PER_DAY": "10000000",
        "VERITAS_PROVIDER_COST_MICROS": DEMO_COST_MICROS,
    })
    import veritas.server as server
    importlib.reload(server)
    server.get_facilitator = lambda *a, **k: Facilitator()

    from veritas.pipeline import run_research as real_run
    server.run_research = lambda query, **kw: real_run(query, allow_network=False, **kw)

    client = TestClient(server.app, raise_server_exceptions=False)
    statuses = []
    for i in range(count):
        challenge = client.post("/v1/research", json={"query": QUERY})
        header = _pay(challenge.json()["accepts"][0], journals / f"buyer-{i}")
        statuses.append(
            client.post("/v1/research", json={"query": QUERY},
                        headers={"X-PAYMENT": header}).status_code
        )
    # One more that is delivered and never settled, so "what am I owed?" has a
    # real answer rather than a trivially empty one.
    server.get_facilitator = lambda *a, **k: Facilitator("timeout")
    challenge = client.post("/v1/research", json={"query": QUERY})
    header = _pay(challenge.json()["accepts"][0], journals / "buyer-unsettled")
    statuses.append(
        client.post("/v1/research", json={"query": QUERY},
                    headers={"X-PAYMENT": header}).status_code
    )
    return {"statuses": statuses, "paid_requests": count}


def _answer(question: str, value: Any, source: str, measured: bool,
            note: str | None = None) -> dict[str, Any]:
    entry = {"question": question, "answer": value, "source": source,
             "measured": measured}
    if note:
        entry["note"] = note
    return entry


def run(count: int = 10) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        runtime, journals = tmp / "runtime", tmp / "journals"
        served = _serve(runtime, journals, count)

        economics = _ops(runtime, "revenue")
        usage = _ops(runtime, "usage")
        owed = _ops(runtime, "owed")
        reconcile = _ops(runtime, "reconcile")
        pricing = _ops(runtime, "pricing")

    revenue = economics.get("revenue_micros")
    cost = economics.get("cost_micros")
    margin = economics.get("margin_micros")
    requests = usage.get("requests") or 0

    per_request_cost = round(cost / requests, 2) if cost and requests else None
    price_micros = None
    if pricing.get("atomic_amount"):
        # USDC is 6 decimals, so one atomic unit is one micro-USD; the pricing
        # report carries the decimals so this is not an assumption.
        price_micros = int(pricing["atomic_amount"]) * 10 ** (6 - pricing["decimals"])

    answers = [
        _answer("What did I earn?", revenue, "veritas-ops revenue", True,
                "Micro-USD, converted from settled atomic units only where the "
                "asset's decimals are known and the conversion is exact."),
        _answer("What did serving it cost?", cost, "veritas-ops revenue", False,
                f"Provider calls are measured; the per-call price is operator "
                f"input ({DEMO_COST_MICROS}). With no cost table configured "
                f"this is null and margin is withheld, by design."),
        _answer("What is my margin?", margin, "veritas-ops revenue", False,
                "Only as trustworthy as the cost input above."),
        _answer("What am I owed?",
                {"count": owed.get("count"), "by_state": owed.get("by_state"),
                 "amount_at_risk": owed.get("amount_at_risk")},
                "veritas-ops owed", True,
                "First run of this cycle answered 0 here while `reconcile` "
                "flagged an unresolved settlement. Indeterminate settlements "
                "are now counted: delivered work is delivered whether the "
                "facilitator said no, said nothing, or was never asked."),
        _answer("What needs my attention?",
                [item["reason"] for item in reconcile.get("needs_attention", [])],
                "veritas-ops reconcile", True,
                reconcile.get("limitation")),
    ]

    unanswerable = [a["question"] for a in answers if a["answer"] is None]

    # An operator reading two commands must not get two stories. The first run
    # of this cycle did exactly that, which is how the defect above surfaced.
    flagged = {item["reason"] for item in reconcile.get("needs_attention", [])}
    consistent = bool(owed.get("count")) == bool(
        flagged & {"delivered_not_settled", "settlement_failed", "settlement_indeterminate"}
    )

    return {
        "cycle": 4,
        "title": "Operator economics, from the ledger alone",
        "served": served,
        "answers": answers,
        "unit_economics": {
            "price_micros_per_request": price_micros,
            "measured_cost_micros_per_request": per_request_cost,
            "gross_margin_micros_per_request": (
                price_micros - per_request_cost
                if price_micros is not None and per_request_cost is not None
                else None
            ),
            "break_even_price_micros": per_request_cost,
            "provider_calls": usage.get("provider_calls"),
            "mean_handler_ms": (
                round(usage["duration_ms_total"] / requests, 1) if requests else None
            ),
            "caveat": (
                "Retrieval ran against the offline corpus, so the wall times are "
                "a floor: a real provider call dominates them. The cost figure "
                "is arithmetic over an operator-supplied price, not a measured "
                "cost of goods."
            ),
        },
        "unanswerable": unanswerable,
        "owed_agrees_with_reconcile": consistent,
        "pass": not unanswerable and consistent,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", help="Write the JSON report here as well as stdout.")
    parser.add_argument("--requests", type=int, default=10)
    args = parser.parse_args(argv)

    report = run(args.requests)
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
