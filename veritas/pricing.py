"""Versioned pricing, recorded per request.

Repricing is inevitable — the default here has already moved once, from $0.25
to $0.01, after the earlier figure turned out to be roughly twenty-five times
what comparable x402 data endpoints charge for a better deliverable. Without a
version stamped on each authorization, a revenue report over any period
spanning a reprice cannot be explained: the same request count yields
different revenue and nothing in the record says why.

So `PRICE_TABLE_VERSION` travels with every ledger entry
(`veritas.ledger.Authorization.price_version`), and `current_price_point`
renders the configured price into the units the 402 challenge actually quotes.
A report that only knows "$0.01" cannot be checked against a settlement; one
that knows "10000 atomic units of USDC on eip155:84532" can.

Deliberately absent: an effective-from date table. The ledger's own
`claimed_at` timestamps are the record of when a price applied, and they are
measured rather than asserted.
"""

from __future__ import annotations

from typing import Any

from .x402 import USDC_ASSETS, PriceError, to_atomic_amount

#: Bumped whenever the *meaning* of the default price changes, so entries
#: written under different pricing regimes stay distinguishable in the ledger.
#: v1 quoted $0.25; v2 is the current $0.01 default.
PRICE_TABLE_VERSION = "veritas.pricing.v2"

PRICE_TABLE_NOTE = (
    "v1 quoted $0.25 per research request. v2 quotes $0.01, the level at which "
    "comparable x402 data endpoints sell. The version is stamped on every "
    "payment authorization, so revenue across a reprice stays explainable."
)


def current_price_point(price: str, network: str) -> dict[str, Any]:
    """Render the configured price into the units a settlement can be checked in.

    Never guesses. A price that cannot be converted reports `atomic_amount:
    null` with the reason, rather than a plausible number.
    """
    asset = USDC_ASSETS.get(network)
    point: dict[str, Any] = {
        "version": PRICE_TABLE_VERSION,
        "price": price,
        "network": network,
        "asset": asset["address"] if asset else None,
        "decimals": asset["decimals"] if asset else None,
        "atomic_amount": None,
        "note": PRICE_TABLE_NOTE,
        "error": None,
    }
    if asset is None:
        point["error"] = f"no settlement asset configured for network {network!r}"
        return point
    try:
        point["atomic_amount"] = to_atomic_amount(price, network)
    except PriceError as exc:
        # The message describes operator configuration, not buyer input, and
        # this document is served publicly — so state the category only.
        point["error"] = f"configured price is not convertible to atomic units ({type(exc).__name__})"
    return point
