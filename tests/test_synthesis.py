"""Lexical NLI synthesis: entailed only, extractive fallback stays.

PROPERTY: a synthesized claim's content tokens are a subset of the cited
excerpts. An unentailed hypothesis is dropped. Extractive claims still
ground every completed response. The contract still validates.

EVIDENCE LEVEL: L1. NOT a language model. NOT commercial-grade research.
"""

from __future__ import annotations

from veritas.hashing import compute_content_hash
from veritas.pipeline import run_research
from veritas.retrieval import RetrievalResult, StaticCorpusRetriever
from veritas.schema import validate_response
from veritas.synthesis import (
    CLAIM_KIND_EXTRACTIVE,
    CLAIM_KIND_SYNTHESIZED,
    lexical_entails,
    synthesize_claims,
)


def test_entailed_hypothesis_passes():
    premise = (
        "x402 is an open standard for internet-native payments over HTTP. "
        "It enables AI agents to pay for APIs using stablecoins."
    )
    assert lexical_entails(premise, "x402 is an open standard for payments")


def test_unentailed_hypothesis_is_dropped():
    assert lexical_entails("cats sit on mats", "dogs fly to mars") is False
    assert lexical_entails("cats sit on mats", "") is False


def test_synthesize_emits_only_entailed_cross_source_claims():
    shared = (
        "x402 is an open standard for internet native payments over HTTP "
        "and enables agents to pay using stablecoins"
    )
    evidence = [
        {
            "excerpt": shared + " under the Linux Foundation.",
            "content_hash": compute_content_hash("a"),
            "url": "https://a.example/x402",
            "title": "A",
            "provenance": "live_fetch",
            "relevance": 0.8,
        },
        {
            "excerpt": shared + " via HTTP 402 Payment Required.",
            "content_hash": compute_content_hash("b"),
            "url": "https://b.example/x402",
            "title": "B",
            "provenance": "live_fetch",
            "relevance": 0.7,
        },
    ]
    # Repair hashes to match excerpts so a later store put would accept them.
    for ev in evidence:
        ev["content_hash"] = compute_content_hash(ev["excerpt"])

    claims = synthesize_claims("What is the x402 protocol?", evidence)
    assert claims, "overlapping excerpts should produce at least one claim"
    for claim in claims:
        assert claim["kind"] == CLAIM_KIND_SYNTHESIZED
        assert claim["evidence_hash"] in {e["content_hash"] for e in evidence}
        for digest in claim["support_hashes"]:
            assert digest in {e["content_hash"] for e in evidence}
        premise = " ".join(e["excerpt"] for e in evidence)
        assert lexical_entails(premise, claim["statement"])


def test_single_source_does_not_synthesize():
    evidence = [{
        "excerpt": "x402 is an open standard for internet-native payments over HTTP.",
        "content_hash": compute_content_hash("solo"),
        "url": "https://a.example",
        "title": "A",
        "provenance": "live_fetch",
        "relevance": 0.9,
    }]
    evidence[0]["content_hash"] = compute_content_hash(evidence[0]["excerpt"])
    assert synthesize_claims("x402", evidence) == []


def test_pipeline_keeps_extractive_and_may_add_synthesized():
    result = run_research(
        "What is the x402 protocol?",
        retriever=StaticCorpusRetriever(),
    )
    assert result["status"] == "completed"
    assert validate_response(result) == []
    kinds = {c.get("kind") for c in result["claims"]}
    assert CLAIM_KIND_EXTRACTIVE in kinds
    extractive = [c for c in result["claims"] if c.get("kind") == CLAIM_KIND_EXTRACTIVE]
    assert extractive, "extractive fallback must remain"


class _TwoSourceRetriever:
    name = "pair"

    def retrieve(self, query, max_results=5):
        shared = (
            "x402 is an open standard for internet native payments over HTTP "
            "used by agents paying with stablecoins"
        )
        return RetrievalResult(
            sources=[
                {
                    "url": "https://one.example/x402",
                    "title": "One",
                    "text": shared + " under a foundation umbrella. " + ("padding " * 8),
                    "provider": "pair",
                    "provenance": "live_fetch",
                    "relevance": 0.9,
                },
                {
                    "url": "https://two.example/x402",
                    "title": "Two",
                    "text": shared + " returning HTTP 402 Payment Required. " + ("padding " * 8),
                    "provider": "pair",
                    "provenance": "live_fetch",
                    "relevance": 0.85,
                },
            ],
            providers_attempted=["pair"],
            providers_succeeded=["pair"],
        )


def test_pipeline_synthesized_claims_are_entailed_and_contract_valid():
    result = run_research("What is the x402 protocol?", retriever=_TwoSourceRetriever())
    assert result["status"] == "completed"
    assert validate_response(result) == []
    synthesized = [c for c in result["claims"] if c.get("kind") == CLAIM_KIND_SYNTHESIZED]
    present = {e["content_hash"] for e in result["evidence"]}
    premise = " ".join(e["excerpt"] for e in result["evidence"])
    for claim in synthesized:
        assert claim["evidence_hash"] in present
        assert lexical_entails(premise, claim["statement"])
