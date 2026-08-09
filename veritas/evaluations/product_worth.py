"""Product-worth baseline — measurable quality without inventing wins.

Phase-2-sized skeleton: report **prefer-again inputs** an agent buyer can use
(evidence length, claim density, honesty taxonomy, fidelity/refusal from the
existing harness). Does **not** claim commercial-grade retrieval or beat a
search API.

Run: ``python -m veritas.evaluations.product_worth``
"""

from __future__ import annotations

from statistics import median
from typing import Any

from veritas.evaluations.harness import (
    SUPPORTED_QUERIES,
    evaluate_fidelity,
    evaluate_refusal,
    evaluate_unavailability_honesty,
)
from veritas.pipeline import run_research
from veritas.retrieval import Retriever, StaticCorpusRetriever


def _excerpt_lens(resp: dict[str, Any]) -> list[int]:
    out: list[int] = []
    for e in resp.get("evidence") or []:
        excerpt = e.get("excerpt") or ""
        out.append(len(excerpt))
    return out


def measure_payload(
    queries: list[str] | None = None,
    retriever: Retriever | None = None,
) -> dict[str, Any]:
    """Structural payload metrics on supported offline queries."""
    queries = queries or SUPPORTED_QUERIES
    r = retriever or StaticCorpusRetriever()
    all_lens: list[int] = []
    claim_counts: list[int] = []
    completed = 0
    rows: list[dict[str, Any]] = []

    for q in queries:
        resp = run_research(q, retriever=r)
        lenses = _excerpt_lens(resp)
        all_lens.extend(lenses)
        n_claims = len(resp.get("claims") or [])
        claim_counts.append(n_claims)
        if resp.get("status") == "completed":
            completed += 1
        rows.append(
            {
                "query": q,
                "status": resp.get("status"),
                "billable": resp.get("billable"),
                "n_evidence": len(resp.get("evidence") or []),
                "n_claims": n_claims,
                "excerpt_chars_median": int(median(lenses)) if lenses else 0,
                "excerpt_chars_total": sum(lenses),
            }
        )

    return {
        "n_queries": len(queries),
        "completed_rate": round(completed / max(1, len(queries)), 3),
        "median_excerpt_chars": int(median(all_lens)) if all_lens else 0,
        "mean_claims_per_query": round(
            sum(claim_counts) / max(1, len(claim_counts)), 3
        ),
        "details": rows,
        "corpus": "offline_static",
        "not_commercial_grade": True,
    }


def run_product_worth_baseline(retriever: Retriever | None = None) -> dict[str, Any]:
    """Compose fidelity + refusal + unavailability + payload metrics.

    Prefer-again judgment is left to the buyer; this only publishes numbers.
    """
    r = retriever or StaticCorpusRetriever()
    fidelity = evaluate_fidelity(retriever=r)
    refusal = evaluate_refusal(retriever=r)
    unavail = evaluate_unavailability_honesty()
    payload = measure_payload(retriever=r)

    # Structural gates already expected green on offline corpus (CI harness).
    structural_ok = (
        fidelity.get("citation_fidelity", 0) >= 0.99
        and fidelity.get("all_custody_valid") is True
        and refusal.get("discrimination", -1) >= 0.99
        and unavail.get("correct") is True
    )

    return {
        "schema": "veritas.product_worth.v0",
        "fidelity": fidelity,
        "refusal": refusal,
        "unavailability_honesty": unavail,
        "payload": payload,
        "structural_ok": structural_ok,
        "compared_to_search_api": False,
        "commercial_grade": False,
        "notes": (
            "Baseline for prefer-again measurement. Snippet/offline corpus only. "
            "Does not claim retrieval worth paid price vs raw search."
        ),
    }


def main() -> None:
    import json

    print(json.dumps(run_product_worth_baseline(), indent=2))


if __name__ == "__main__":
    main()
