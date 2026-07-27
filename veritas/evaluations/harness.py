"""Evaluation harness: fidelity, refusal discrimination, and calibration input.

Runs against a pinned offline corpus by default so results are deterministic
and do not depend on network reachability — a harness whose numbers change
with the weather cannot support a quality claim.
"""

from __future__ import annotations

from typing import Any

from veritas.hashing import verify_content_hash
from veritas.pipeline import run_research
from veritas.retrieval import Retriever, StaticCorpusRetriever

# Queries the offline corpus genuinely supports.
SUPPORTED_QUERIES = [
    "What is the x402 protocol?",
    "How does the CDP Bazaar help agents?",
    "What is the Model Context Protocol?",
]

# Queries nothing in the corpus supports. A correct service refuses these.
UNSUPPORTED_QUERIES = [
    "What were the quarterly earnings of Zephyrcorp Industries in 1987?",
    "zzqq flurbrigade nonexistent topic 99999",
    "Who won the Martian Grand Prix last season?",
]


def _retriever(retriever: Retriever | None) -> Retriever:
    return retriever or StaticCorpusRetriever()


def evaluate_fidelity(
    queries: list[str] | None = None,
    retriever: Retriever | None = None,
) -> dict[str, Any]:
    """Every published claim must hash-match the evidence it cites."""
    queries = queries or SUPPORTED_QUERIES
    r = _retriever(retriever)

    total_claims = 0
    hash_valid = 0
    details = []

    for q in queries:
        resp = run_research(q, retriever=r)
        evidence_by_hash = {e["content_hash"]: e for e in resp.get("evidence", [])}
        claims = resp.get("claims", [])
        total_claims += len(claims)

        valid_here = 0
        for claim in claims:
            ev = evidence_by_hash.get(claim.get("evidence_hash"))
            if ev and verify_content_hash(ev["excerpt"], ev["content_hash"])[0]:
                valid_here += 1
                hash_valid += 1

        details.append({
            "query": q,
            "status": resp["status"],
            "claims": len(claims),
            "hash_valid": valid_here,
            "custody_valid": resp["custody_valid"],
        })

    return {
        "citation_fidelity": round(hash_valid / max(1, total_claims), 3),
        "total_claims": total_claims,
        "all_custody_valid": all(d["custody_valid"] for d in details),
        "details": details,
    }


def evaluate_refusal(retriever: Retriever | None = None) -> dict[str, Any]:
    """Measure discrimination: answer the supported, refuse the unsupported.

    Refusal rate alone is not a quality signal — a service that refuses
    everything scores perfectly on it. What matters is the gap between the two
    populations, so both are measured together.
    """
    r = _retriever(retriever)

    refused_unsupported = 0
    for q in UNSUPPORTED_QUERIES:
        if run_research(q, retriever=r)["status"] == "refused":
            refused_unsupported += 1

    answered_supported = 0
    for q in SUPPORTED_QUERIES:
        if run_research(q, retriever=r)["status"] == "completed":
            answered_supported += 1

    correct_refusal = refused_unsupported / len(UNSUPPORTED_QUERIES)
    correct_answer = answered_supported / len(SUPPORTED_QUERIES)

    return {
        "correct_refusal_rate": round(correct_refusal, 3),
        "correct_answer_rate": round(correct_answer, 3),
        "discrimination": round(correct_refusal + correct_answer - 1.0, 3),
        "n_unsupported": len(UNSUPPORTED_QUERIES),
        "n_supported": len(SUPPORTED_QUERIES),
    }


def evaluate_unavailability_honesty() -> dict[str, Any]:
    """A failing retriever must yield `unavailable`, never `no_evidence`.

    This guards the property that separates Veritas from a guesser: it must
    never convert its own outage into a claim about the world.
    """
    from veritas.retrieval import RetrievalError, RetrievalResult

    class BrokenRetriever:
        name = "broken"

        def retrieve(self, query: str, max_results: int = 5) -> RetrievalResult:
            return RetrievalResult(
                sources=[],
                errors=[RetrievalError("broken", "network_unreachable", "simulated outage")],
                providers_attempted=["broken"],
                providers_succeeded=[],
            )

    resp = run_research("What is x402?", retriever=BrokenRetriever())
    return {
        "status": resp["status"],
        "refusal_reason": resp["refusal_reason"],
        "billable": resp["billable"],
        "correct": resp["status"] == "unavailable" and resp["billable"] is False,
    }


def run_full_harness() -> dict[str, Any]:
    return {
        "fidelity": evaluate_fidelity(),
        "refusal": evaluate_refusal(),
        "unavailability_honesty": evaluate_unavailability_honesty(),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_full_harness(), indent=2))
