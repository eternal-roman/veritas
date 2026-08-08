"""How well the delivered evidence supports the query — as counts, not a score.

This replaces a Bayesian `posterior` that could not survive scrutiny. That number
took the raw query string as its hypothesis (`P("What is x402?" | evidence)` has
no truth value), derived its likelihoods from hand-typed constants, could only
ever increase — so the `low_confidence` refusal it gated was unreachable — and
rose to 0.806 on two flatly contradictory sources. Per-claim confidence was
decided by list position: the same text scored 0.75 first and 0.589 second.

Everything here is a count the buyer can recompute from the records they were
given. There are no free parameters and nothing to calibrate. When we have
labelled outcomes we can add a scored layer on top; until then, publishing
counts is strictly more informative than publishing an unearnable probability.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

METHOD = "veritas.support.v1"

# Suffixes where the label below is the registrable unit, so that
# `a.example.co.uk` and `b.example.co.uk` count as one domain, not two.
_MULTI_LABEL_SUFFIXES = frozenset({
    "co.uk", "org.uk", "ac.uk", "gov.uk", "co.jp", "com.au", "com.br",
    "co.nz", "co.za", "com.cn", "co.in", "com.mx",
})


def registrable_domain(url: str | None) -> str | None:
    """The registrable domain of a URL, or None when it has no host.

    Independence is counted per registrable domain rather than per URL, because
    two pages on one site are one publisher, not two witnesses.
    """
    if not url:
        return None
    host = (urlsplit(url).hostname or "").lower().strip(".")
    if not host:
        return None
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    last_two = ".".join(labels[-2:])
    if last_two in _MULTI_LABEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return last_two


def support_report(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise the delivered evidence. Pure function of what the buyer holds."""
    domains: list[str] = []
    providers: list[str] = []
    for item in evidence:
        domain = registrable_domain(item.get("url"))
        if domain and domain not in domains:
            domains.append(domain)
        provider = item.get("provider")
        if provider and provider not in providers:
            providers.append(provider)

    n_domains = len(domains)
    if not evidence:
        verdict = "unsupported"
    elif n_domains >= 2:
        verdict = "corroborated"
    else:
        verdict = "single_source"

    return {
        "n_evidence": len(evidence),
        "independent_domains": n_domains,
        "domains": domains,
        "distinct_providers": len(providers),
        "verdict": verdict,
        # Agreement between sources is not measured. Saying so is the honest
        # alternative to inferring it from token overlap, which is what the
        # previous posterior did under a statistical costume.
        "agreement": "not_assessed",
        "method": METHOD,
    }
