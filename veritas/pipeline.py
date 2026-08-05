"""Evidence-first research pipeline with grounded claims and a delivered custody chain.

This is the single research engine for the whole system. Both the HTTP surface
(`veritas/server.py`) and the agent-native control plane (`veritas/autonomous/control_plane.py`)
call into it, so there is exactly one implementation of retrieval, hashing and
custody to audit.

Outcome taxonomy — the distinction matters commercially and epistemically:

  completed          evidence was found, was relevant, and claims were grounded in it
  refused            sources were reachable but returned nothing (`no_evidence`) or
                     nothing on topic (`irrelevant_evidence`)
  unavailable        retrieval itself failed; we did not observe an absence of
                     evidence, so we must not claim one — and must not bill for it

Two audited defects shaped this module's current form. The relevance gate lived
only inside one retriever, so in production any source of 40+ characters became a
billable `completed` answer however unrelated — the evaluation harness certified a
filter the served path never applied. And the custody chain was computed and then
discarded, leaving `custody_valid` as our own unverifiable word. Both are fixed
here: the gate runs on every source, and the chain ships with the response.

The Bayesian posterior this module used to publish has been removed rather than
repaired — see `veritas/support.py` for why, and for the counts that replace it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .custody import CustodyLedger
from .hashing import compute_content_hash, verify_content_hash
from .retrieval import (
    MIN_RELEVANCE,
    UNKNOWN_LICENSE,
    RetrievalError,
    RetrievalResult,
    Retriever,
    default_retriever,
    relevance_score,
)
from .support import support_report

# Minimum usable evidence length; shorter excerpts cannot ground a claim.
MIN_EVIDENCE_CHARS = 40

# What a response is and is not evidence of. Without something like TLSNotary or
# a trusted execution environment we can attest only to what we received; we
# cannot prove what the origin served to anyone else. Publishing that limit is
# constitution article A22.
ATTESTS = (
    "what this service received from these sources at this time; "
    "not what those sources served to any other party"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _envelope(
    request_id: str,
    query: str,
    status: str,
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    ledger: CustodyLedger,
    retrieval_meta: dict[str, Any],
    billable: bool,
    refusal_reason: str | None = None,
    evidence_hashes_valid: bool = True,
) -> dict[str, Any]:
    # The custody chain ships with the response. Previously only the root hash
    # and a self-asserted `custody_valid` were published while the events
    # themselves were discarded, so a buyer had nothing to check and had to take
    # our word — the opposite of what the ledger exists for.
    return {
        "request_id": request_id,
        "status": status,
        "query": query,
        "claims": claims,
        "evidence": evidence,
        "support": support_report(evidence),
        "custody_root": ledger.root_hash(),
        "custody_valid": ledger.verify_chain() and evidence_hashes_valid,
        "custody_chain": ledger.to_list(),
        "attests": ATTESTS,
        "retrieval": retrieval_meta,
        "refusal_reason": refusal_reason,
        "billable": billable,
        "timestamp": _now(),
    }


def run_research(
    query: str,
    retriever: Retriever | None = None,
    max_results: int = 5,
    allow_network: bool = True,
) -> dict[str, Any]:
    """Run one research request end to end.

    `retriever` is injectable so tests and offline deployments can pin a
    deterministic source set without monkeypatching.
    """
    ledger = CustodyLedger()
    request_id = str(uuid.uuid4())
    ledger.append("created", "pipeline", {"query": query, "request_id": request_id})

    if retriever is None:
        retriever = default_retriever(allow_network=allow_network)

    # A retriever is an untrusted collaborator: it may raise, and it may ignore
    # max_results. Neither may escape as a 500 or as unbounded work, so the
    # exception becomes an `unavailable` outcome and the cap is re-applied here
    # rather than trusted.
    try:
        result = retriever.retrieve(query, max_results=max_results)
    except Exception as exc:  # noqa: BLE001 - converted to an unavailable outcome
        provider = getattr(retriever, "name", "unknown")
        result = RetrievalResult(
            errors=[RetrievalError(provider, type(exc).__name__, str(exc)[:200])],
            providers_attempted=[provider],
        )

    if len(result.sources) > max_results:
        result.sources = result.sources[:max_results]

    retrieval_meta = result.to_dict()

    for err in result.errors:
        ledger.append("retrieval_error", err.provider, err.to_dict())

    # Retrieval failed outright: report unavailability, never `no_evidence`,
    # and mark the request non-billable so a buying agent is not charged for
    # our inability to look.
    if result.unavailable:
        ledger.append("unavailable", "pipeline", {"reason": "retrieval_failed"})
        return _envelope(
            request_id, query, "unavailable", [], [], ledger,
            retrieval_meta, billable=False, refusal_reason="retrieval_unavailable",
        )

    evidence: list[dict[str, Any]] = []
    discarded_irrelevant = 0
    for src in result.sources:
        text = (src.get("text") or "").strip()
        if len(text) < MIN_EVIDENCE_CHARS:
            continue
        # The relevance gate belongs here, not inside one retriever. It used to
        # live only in StaticCorpusRetriever, so the evaluation harness measured
        # a filter that production never applied: any source of 40+ characters
        # became a billable `completed` answer, however unrelated.
        score = src.get("relevance")
        score = relevance_score(query, text) if score is None else float(score)
        if score < MIN_RELEVANCE:
            discarded_irrelevant += 1
            ledger.append("evidence_discarded", src.get("provider", "retriever"), {
                "reason": "below_min_relevance",
                "relevance": round(score, 3),
                "threshold": MIN_RELEVANCE,
                "url": src.get("url"),
            })
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
            "relevance": round(score, 3),
            # A buyer reusing an excerpt needs to know what licence attaches to
            # it. Unknown is stated as unknown rather than left blank.
            "license": src.get("license") or dict(UNKNOWN_LICENSE),
            "attribution": src.get("attribution") or {"required": False, "text": None},
        })

    # Sources were reachable but nothing usable came back. Two different honest
    # refusals: nothing was returned at all, or everything returned was off-topic.
    # Distinguishing them tells the buyer whether to rephrase or to stop asking.
    if not evidence:
        reason = "irrelevant_evidence" if discarded_irrelevant else "no_evidence"
        ledger.append("refused", "pipeline", {
            "reason": reason, "discarded_irrelevant": discarded_irrelevant,
        })
        return _envelope(
            request_id, query, "refused", [], [], ledger,
            retrieval_meta, billable=True, refusal_reason=reason,
        )

    claims: list[dict[str, Any]] = []
    for i, ev in enumerate(evidence):
        # A claim is a grounded excerpt, and is published as exactly that. It
        # carries no confidence score: the previous one was decided by list
        # position, which is noise wearing a probability's clothes.
        claims.append({
            "id": f"c{i + 1}",
            "statement": f"{ev['title'] or ev['url']}: {ev['excerpt'][:220]}",
            "evidence_hash": ev["content_hash"],
            "source_url": ev["url"],
            "provenance": ev["provenance"],
            "relevance": ev["relevance"],
        })
        ledger.append("claim_created", "pipeline", {
            "claim_id": f"c{i + 1}",
            "evidence_hash": ev["content_hash"],
            "relevance": ev["relevance"],
        })

    # Every excerpt must still hash to the value we published.
    hashes_valid = all(
        verify_content_hash(ev["excerpt"], ev["content_hash"])[0] for ev in evidence
    )
    if not hashes_valid:
        ledger.append("integrity_failure", "pipeline", {"reason": "evidence_hash_mismatch"})

    ledger.append("completed", "pipeline", {"n_claims": len(claims)})
    return _envelope(
        request_id, query, "completed", claims, evidence, ledger,
        retrieval_meta, billable=True, evidence_hashes_valid=hashes_valid,
    )
