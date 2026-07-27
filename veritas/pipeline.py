"""Evidence-first research pipeline with grounded claims and Bayesian updates.

This is the single research engine for the whole system. Both the HTTP surface
(`app/main.py`) and the agent-native control plane (`autonomous/control_plane.py`)
call into it, so there is exactly one implementation of retrieval, hashing,
custody and belief updating to audit.

Outcome taxonomy — the distinction matters commercially and epistemically:

  completed   evidence was found and claims were grounded in it
  refused     sources were reachable and genuinely had nothing relevant
  unavailable retrieval itself failed; we did not observe an absence of
              evidence, so we must not claim one — and must not bill for it
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .bayesian import BayesianBelief, update_belief
from .custody import CustodyLedger
from .hashing import compute_content_hash, verify_content_hash
from .retrieval import Retriever, default_retriever, relevance_score

# Minimum usable evidence length; shorter excerpts cannot ground a claim.
MIN_EVIDENCE_CHARS = 40

# Posterior below which we decline to assert anything.
REFUSAL_THRESHOLD = 0.4

# Correlated-source damping. Two pages from the same provider are not two
# independent observations; treating them as such is how naive Bayes pipelines
# manufacture false confidence. Each repeat from a provider we have already
# counted has its evidential weight pulled toward 0.5 (uninformative).
CORRELATION_DAMPING = 0.55


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _likelihoods(source: Dict[str, Any], relevance: float, repeats: int) -> tuple[float, float]:
    """Map source quality onto (P(E|H), P(E|~H)).

    A highly relevant, independently fetched document is much more likely to
    exist if the hypothesis is true than if it is false. Offline-corpus text is
    fixture data, so its evidential weight is deliberately damped — it should
    never produce the same confidence as a live fetch.
    """
    p_true = 0.65 + 0.25 * relevance
    p_false = 0.35 - 0.15 * relevance

    if source.get("provenance") != "live_fetch":
        p_true = 0.5 + (p_true - 0.5) * 0.6
        p_false = 0.5 + (p_false - 0.5) * 0.6

    for _ in range(repeats):
        p_true = 0.5 + (p_true - 0.5) * CORRELATION_DAMPING
        p_false = 0.5 + (p_false - 0.5) * CORRELATION_DAMPING

    return p_true, p_false


def _envelope(
    request_id: str,
    query: str,
    status: str,
    posterior: float,
    claims: List[Dict[str, Any]],
    evidence: List[Dict[str, Any]],
    ledger: CustodyLedger,
    retrieval_meta: Dict[str, Any],
    billable: bool,
    refusal_reason: Optional[str] = None,
    evidence_hashes_valid: bool = True,
) -> Dict[str, Any]:
    return {
        "request_id": request_id,
        "status": status,
        "query": query,
        "posterior": round(posterior, 3),
        "claims": claims,
        "evidence": evidence,
        "custody_root": ledger.root_hash(),
        "custody_valid": ledger.verify_chain() and evidence_hashes_valid,
        "retrieval": retrieval_meta,
        "refusal_reason": refusal_reason,
        "billable": billable,
        "timestamp": _now(),
    }


def run_research(
    query: str,
    retriever: Optional[Retriever] = None,
    max_results: int = 5,
    allow_network: bool = True,
) -> Dict[str, Any]:
    """Run one research request end to end.

    `retriever` is injectable so tests and offline deployments can pin a
    deterministic source set without monkeypatching.
    """
    ledger = CustodyLedger()
    request_id = str(uuid.uuid4())
    ledger.append("created", "pipeline", {"query": query, "request_id": request_id})

    if retriever is None:
        retriever = default_retriever(allow_network=allow_network)

    result = retriever.retrieve(query, max_results=max_results)
    retrieval_meta = result.to_dict()

    for err in result.errors:
        ledger.append("retrieval_error", err.provider, err.to_dict())

    # Retrieval failed outright: report unavailability, never `no_evidence`,
    # and mark the request non-billable so a buying agent is not charged for
    # our inability to look.
    if result.unavailable:
        ledger.append("unavailable", "pipeline", {"reason": "retrieval_failed"})
        return _envelope(
            request_id, query, "unavailable", 0.0, [], [], ledger,
            retrieval_meta, billable=False, refusal_reason="retrieval_unavailable",
        )

    evidence: List[Dict[str, Any]] = []
    for src in result.sources:
        text = (src.get("text") or "").strip()
        if len(text) < MIN_EVIDENCE_CHARS:
            continue
        content_hash = compute_content_hash(text)
        ledger.append("evidence_created", src.get("provider", "retriever"), {
            "content_hash": content_hash,
            "url": src.get("url"),
            "title": src.get("title"),
            "provenance": src.get("provenance"),
        })
        evidence.append({
            "url": src.get("url"),
            "title": src.get("title"),
            "excerpt": text,
            "content_hash": content_hash,
            "provider": src.get("provider"),
            "provenance": src.get("provenance"),
            "relevance": src.get("relevance", round(relevance_score(query, text), 3)),
        })

    # Sources were reachable but nothing relevant came back: a genuine,
    # honestly-earned refusal.
    if not evidence:
        ledger.append("refused", "pipeline", {"reason": "no_evidence"})
        return _envelope(
            request_id, query, "refused", 0.08, [], [], ledger,
            retrieval_meta, billable=True, refusal_reason="no_evidence",
        )

    overall = BayesianBelief(hypothesis=query, prior=0.3)
    claims: List[Dict[str, Any]] = []
    provider_counts: Dict[str, int] = {}

    for i, ev in enumerate(evidence):
        provider = ev.get("provider") or "unknown"
        repeats = provider_counts.get(provider, 0)
        provider_counts[provider] = repeats + 1

        relevance = float(ev.get("relevance") or 0.0)
        p_true, p_false = _likelihoods(ev, relevance, repeats)

        claim_belief = BayesianBelief(hypothesis=ev["excerpt"][:120], prior=0.4)
        claim_belief = update_belief(claim_belief, p_true, p_false, ev["content_hash"])

        claims.append({
            "id": f"c{i + 1}",
            "statement": f"{ev['title'] or ev['url']}: {ev['excerpt'][:220]}",
            "confidence": round(claim_belief.posterior, 3),
            "evidence_hash": ev["content_hash"],
            "source_url": ev["url"],
            "provenance": ev["provenance"],
        })

        overall = update_belief(overall, p_true, p_false, ev["content_hash"])
        ledger.append("belief_updated", "pipeline", {
            "claim_id": f"c{i + 1}",
            "posterior": round(overall.posterior, 6),
            "p_e_given_h": round(p_true, 4),
            "p_e_given_not_h": round(p_false, 4),
        })

    # Every excerpt must still hash to the value we published.
    hashes_valid = all(
        verify_content_hash(ev["excerpt"], ev["content_hash"])[0] for ev in evidence
    )
    if not hashes_valid:
        ledger.append("integrity_failure", "pipeline", {"reason": "evidence_hash_mismatch"})

    if overall.posterior < REFUSAL_THRESHOLD:
        ledger.append("refused", "pipeline", {"reason": "low_confidence",
                                              "posterior": round(overall.posterior, 6)})
        return _envelope(
            request_id, query, "refused", overall.posterior, [], evidence, ledger,
            retrieval_meta, billable=True, refusal_reason="low_confidence",
            evidence_hashes_valid=hashes_valid,
        )

    ledger.append("completed", "pipeline", {"posterior": round(overall.posterior, 6),
                                            "n_claims": len(claims)})
    return _envelope(
        request_id, query, "completed", overall.posterior, claims, evidence, ledger,
        retrieval_meta, billable=True, evidence_hashes_valid=hashes_valid,
    )
