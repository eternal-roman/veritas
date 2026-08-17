"""Catalog honesty gates — prices not verdicts; outage is not a miss.

Run: python -m veritas.evaluations.catalog
"""

from __future__ import annotations

from typing import Any
from urllib.error import URLError

from veritas.signals import (
    METHOD,
    SignalsError,
    SignalStore,
    pull,
    pull_kalshi,
    pull_polymarket,
)


def run_catalog_honesty() -> dict[str, Any]:
    failures: list[str] = []

    try:
        pull("   ")
        failures.append("empty query was accepted")
    except SignalsError as exc:
        if "query_empty" not in str(exc):
            failures.append(f"empty query error was {exc}")

    try:
        pull("fed", venues=["betfair"])
        failures.append("unknown venue was accepted")
    except SignalsError as exc:
        if "venue_unknown" not in str(exc):
            failures.append(f"unknown venue error was {exc}")

    class _Dead:
        def __call__(self, request, timeout=None):
            raise URLError("venue down")

    try:
        pull_polymarket("fed", opener=_Dead())
        failures.append("dead polymarket returned a catalog")
    except SignalsError:
        pass

    try:
        pull_kalshi("fed", opener=_Dead())
        failures.append("dead kalshi returned a catalog")
    except SignalsError:
        pass

    store = SignalStore()
    snap = {
        "venue": "polymarket",
        "market_id": "gate-m",
        "question": "Catalog honesty fixture",
        "outcomes": [{"name": "Yes", "price": 0.4}],
        "observed_at": "2026-08-17T00:00:00Z",
        "source_url": "https://gamma-api.polymarket.com/markets/gate-m",
        "method": METHOD,
        "note": "market-implied prices, not a verdict",
    }
    digest = store.put(snap)
    if not digest:
        failures.append("catalog persist failed")
    listed = store.list(q="honesty")
    if not listed:
        failures.append("catalog list missed a stored snapshot")
    elif "not a verdict" not in (listed[0].get("note") or ""):
        failures.append("catalog note is not honest")

    return {
        "schema": "veritas.catalog_honesty.v0",
        "ok": not failures,
        "failures": failures,
        "not_a_forecast": True,
    }


def main() -> int:
    import json

    report = run_catalog_honesty()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
