"""Pipeline behaviour: refusal discrimination, honesty under outage, contract."""

import pytest

from veritas.pipeline import run_research
from veritas.retrieval import (
    RetrievalError,
    RetrievalResult,
    StaticCorpusRetriever,
    relevance_score,
)
from veritas.schema import validate_response


class BrokenRetriever:
    """Every provider errors — simulates a network outage."""
    name = "broken"

    def retrieve(self, query, max_results=5):
        return RetrievalResult(
            sources=[],
            errors=[RetrievalError("broken", "network_unreachable", "simulated")],
            providers_attempted=["broken"],
            providers_succeeded=[],
        )


class EmptyRetriever:
    """Providers work fine but genuinely find nothing."""
    name = "empty"

    def retrieve(self, query, max_results=5):
        return RetrievalResult(
            sources=[], errors=[],
            providers_attempted=["empty"], providers_succeeded=["empty"],
        )


def test_relevant_query_completes():
    r = run_research("What is the x402 protocol?", retriever=StaticCorpusRetriever())
    assert r["status"] == "completed"
    assert r["claims"]
    assert r["support"]["n_evidence"] >= 1


def test_irrelevant_query_is_refused():
    """The old relevance filter matched on stopwords and then fell back
    unconditionally, so refusal was unreachable. It must now trigger."""
    r = run_research("zzqq flurbrigade 99999 nonexistent", retriever=StaticCorpusRetriever())
    assert r["status"] == "refused"
    assert r["refusal_reason"] == "no_evidence"
    assert r["claims"] == []


def test_outage_is_unavailable_not_no_evidence():
    """The central honesty invariant: never convert our own outage into a
    claim that no evidence exists."""
    r = run_research("What is x402?", retriever=BrokenRetriever())
    assert r["status"] == "unavailable"
    assert r["refusal_reason"] == "retrieval_unavailable"


def test_outage_is_not_billable():
    r = run_research("What is x402?", retriever=BrokenRetriever())
    assert r["billable"] is False


def test_genuine_emptiness_is_billable_refusal():
    """Working providers that find nothing is a real service outcome."""
    r = run_research("What is x402?", retriever=EmptyRetriever())
    assert r["status"] == "refused"
    assert r["refusal_reason"] == "no_evidence"
    assert r["billable"] is True


def test_claims_only_cite_present_evidence():
    r = run_research("What is the x402 protocol?", retriever=StaticCorpusRetriever())
    present = {e["content_hash"] for e in r["evidence"]}
    for claim in r["claims"]:
        assert claim["evidence_hash"] in present


def test_custody_chain_valid_and_rooted():
    r = run_research("What is the x402 protocol?", retriever=StaticCorpusRetriever())
    assert r["custody_valid"] is True
    assert r["custody_root"].startswith("sha256:")


@pytest.mark.parametrize("retriever", [StaticCorpusRetriever(), BrokenRetriever(), EmptyRetriever()])
def test_response_conforms_to_contract(retriever):
    r = run_research("What is the x402 protocol?", retriever=retriever)
    assert validate_response(r) == []


def test_correlated_sources_do_not_manufacture_certainty():
    """Three documents from one provider are not three independent
    observations; naive Bayes would push this past 0.95."""
    r = run_research("What is the x402 protocol?", retriever=StaticCorpusRetriever())
    assert len(r["evidence"]) >= 2
    assert r["support"]["independent_domains"] <= r["support"]["n_evidence"]


def test_relevance_ignores_stopwords():
    assert relevance_score("what is the a of and", "completely unrelated text") == 0.0


class OverproducingRetriever:
    """Ignores max_results, as a third-party retriever may."""
    name = "overproducer"

    def retrieve(self, query, max_results=5):
        return RetrievalResult(
            sources=[{"url": f"u{i}", "title": "t", "text": "lorem ipsum dolor " * 30,
                      "provenance": "live_fetch", "relevance": 0.9} for i in range(50)],
            providers_attempted=["overproducer"], providers_succeeded=["overproducer"],
        )


class ExplodingRetriever:
    name = "exploder"

    def retrieve(self, query, max_results=5):
        raise RuntimeError("provider blew up")


def test_max_results_is_enforced_against_the_retriever():
    """A retriever that ignores the cap must not drive unbounded work, an
    unbounded response, or inflated confidence from 50 correlated sources."""
    r = run_research("lorem ipsum", retriever=OverproducingRetriever(), max_results=5)
    assert len(r["evidence"]) == 5
    assert len(r["claims"]) <= 5


def test_raising_retriever_becomes_unavailable_not_a_crash():
    """A provider exception must convert to the unavailable outcome, not escape
    as a 500 that bypasses the non-billable path."""
    r = run_research("test", retriever=ExplodingRetriever())
    assert r["status"] == "unavailable"
    assert r["billable"] is False
    assert validate_response(r) == []
    assert r["retrieval"]["errors"][0]["error_type"] == "RuntimeError"
