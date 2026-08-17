"""What a request cost to serve — counted, and priced only where a price exists.

The operator's first question is "am I making money", and before this module
the service could not answer either half of it. It could quote a price but had
no idea what a request cost to produce.

The rule that shapes this module: **count everything, invent nothing.**

Provider calls, evidence bytes and wall time are countable facts, and they are
recorded on every request — including free ones, because a retrieval pass costs
the same whether or not anyone paid for it. Turning those counts into dollars
needs a per-provider price. This repository cannot verify any *paid* API's
list price, so those stay unpriced until an operator sets
`VERITAS_PROVIDER_COST_MICROS`. Providers that are known-free inside this
tree (Wikipedia, DuckDuckGo Instant Answer, the offline corpus, the
zero-key tier, the composite wrapper) default to zero — that is a fact
about the code, not an invented invoice.

An assumed-zero cost for a *paid* provider nobody configured produces a
margin report that is confidently wrong, which is worse than no report.
A rejected env override (`wikipedia=oops`) drops that provider's default
rather than silently keeping zero: a typo must not look like a price.

Operators supply real numbers through `VERITAS_PROVIDER_COST_MICROS`, e.g.

    VERITAS_PROVIDER_COST_MICROS="serper=1000,wikipedia=0,duckduckgo_instant_answer=0"

in micro-USD per provider call (1000 = $0.001), keyed by the provider name as
it appears in `retrieval.providers_attempted` — an entry for a name no request
ever reports prices nothing. Attempted calls are counted, not just successful
ones: a search API bills the request, not the result.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

#: Reported in place of a number when a cost or margin cannot be computed
#: without inventing a price. It is None so reports serialise as JSON; the
#: reason always travels alongside it in `unpriced_providers`.
UNPRICED = None

COST_ENV_VAR = "VERITAS_PROVIDER_COST_MICROS"

#: Providers whose retrieval path in this repository does not call a paid
#: API. Zero is a fact about the code, not a guessed invoice. Paid
#: providers (serper, anything an operator adds) stay unpriced until set.
FREE_PROVIDER_COSTS: dict[str, int] = {
    "wikipedia": 0,
    "duckduckgo_instant_answer": 0,
    "static_corpus": 0,
    "zero_key": 0,
    "composite": 0,
}

#: One US dollar in the micro-USD unit every money figure in reports uses.
MICROS_PER_USD = 1_000_000


@dataclass(frozen=True)
class Usage:
    """What one request consumed. Counted facts only — no money here."""

    request_id: str
    status: str
    billable: bool
    paid: bool
    provider_calls: dict[str, int]
    evidence_bytes: int
    duration_ms: int


@dataclass(frozen=True)
class CostTable:
    """Operator-supplied cost per provider call, in micro-USD.

    `rejected` keeps malformed configuration entries visible instead of
    swallowing them: a typo in one entry must not silently price every
    provider at zero.
    """

    micros: dict[str, int]
    rejected: list[str] = field(default_factory=list)

    def micros_per_call(self, provider: str) -> int | None:
        """Cost of one call, or None when nobody has priced this provider."""
        return self.micros.get(provider)

    @classmethod
    def from_env(cls) -> CostTable:
        raw = os.getenv(COST_ENV_VAR, "")
        micros: dict[str, int] = dict(FREE_PROVIDER_COSTS)
        rejected: list[str] = []
        for chunk in raw.split(","):
            entry = chunk.strip()
            if not entry:
                continue
            provider, sep, value = entry.partition("=")
            name = provider.strip()
            try:
                if not sep:
                    raise ValueError("missing '='")
                micros[name] = int(value.strip())
            except ValueError:
                rejected.append(entry)
                # A malformed override of a defaulted name must not leave
                # the default looking like a configured price.
                micros.pop(name, None)
        return cls(micros, rejected)


def cost_of(provider_calls: dict[str, int], costs: CostTable) -> tuple[int | None, list[str]]:
    """Total micro-USD for these calls, plus the providers nobody has priced.

    Returns `(UNPRICED, [...])` when any provider is unpriced. Charging on
    behalf of the priced subset would understate cost while looking complete.
    """
    unpriced = sorted(p for p in provider_calls if costs.micros_per_call(p) is None)
    if unpriced:
        return UNPRICED, unpriced
    total = sum(costs.micros_per_call(p) * n for p, n in provider_calls.items())
    return total, []
