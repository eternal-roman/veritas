"""Phase T: the claims the service makes must be true on the path it serves.

Three audited defects motivate this file, and each has a test here that failed
before the fix:

* P1 — the relevance gate lived only inside `StaticCorpusRetriever`, so in
  production any source with 40+ characters produced a billable `completed`
  response. The harness certified refusal on a code path production never used.
* P2 — the custody chain was never delivered. `custody_valid: true` was an
  unverifiable self-assertion, which made constitution article A12 false.
* P3/P4/P5 — the posterior could only increase, so the `low_confidence` refusal
  was unreachable; the number itself was uninterpretable (its hypothesis was the
  query string) and per-claim confidence was decided by list position.
"""

from __future__ import annotations

import pytest

from veritas.custody import verify_chain_records
from veritas.pipeline import run_research
from veritas.retrieval import RetrievalResult
from veritas.schema import validate_response

# Verbatim from the evaluation harness's UNSUPPORTED set. Before the fix this
# query returned `completed` with a confident claim about bananas.
ZEPHYRCORP = "What were the quarterly earnings of Zephyrcorp Industries in 1987?"

BANANA = (
    "A banana is an elongated, edible fruit produced by several kinds of large "
    "herbaceous flowering plants in the genus Musa."
)


class _Fixed:
    """Returns exactly the sources it was given, like a live provider would."""

    name = "fixed"

    def __init__(self, sources):
        self._sources = sources

    def retrieve(self, query, max_results=5):
        return RetrievalResult(
            sources=list(self._sources)[:max_results],
            errors=[],
            providers_attempted=[self.name],
            providers_succeeded=[self.name],
        )


def _source(text, url="https://example.org/a", provider="fixed", title="Doc"):
    return {
        "url": url,
        "title": title,
        "text": text,
        "provider": provider,
        "provenance": "live_fetch",
    }


def test_irrelevant_evidence_is_refused_on_the_production_path():
    """P1. The gate must live in the pipeline, not in one retriever."""
    r = run_research(ZEPHYRCORP, retriever=_Fixed([_source(BANANA)]))
    assert r["status"] == "refused"
    assert r["refusal_reason"] == "irrelevant_evidence"
    assert r["claims"] == []


def test_irrelevant_evidence_is_still_billable_but_asserts_nothing():
    """An honest refusal is a product; it must not smuggle out a claim."""
    r = run_research(ZEPHYRCORP, retriever=_Fixed([_source(BANANA)]))
    assert r["billable"] is True
    assert BANANA not in str(r["claims"])


def test_relevant_evidence_still_completes():
    query = "What is the x402 payment protocol?"
    text = (
        "The x402 payment protocol is an open standard for internet-native "
        "payments over HTTP, letting agents pay for APIs with stablecoins."
    )
    r = run_research(query, retriever=_Fixed([_source(text)]))
    assert r["status"] == "completed"
    assert r["claims"]


def test_min_relevance_is_enforced_by_the_pipeline_not_only_by_the_corpus():
    """The pipeline must apply the threshold even when the retriever does not."""
    from veritas.retrieval import MIN_RELEVANCE, relevance_score

    assert relevance_score(ZEPHYRCORP, BANANA) < MIN_RELEVANCE
    r = run_research(ZEPHYRCORP, retriever=_Fixed([_source(BANANA)]))
    assert r["status"] == "refused"


def test_response_delivers_the_custody_chain():
    """P2. The chain must be on the wire, not merely computed and discarded."""
    r = run_research("What is the x402 payment protocol?", allow_network=False)
    chain = r["custody_chain"]
    assert isinstance(chain, list) and chain, "custody chain not delivered"
    assert verify_chain_records(chain) is True


def test_delivered_chain_is_verifiable_without_the_seller():
    """The buyer re-runs chain validation client-side, on delivered data only."""
    r = run_research("What is the x402 payment protocol?", allow_network=False)
    assert verify_chain_records(r["custody_chain"]) is True
    assert r["custody_root"] == r["custody_chain"][-1]["event_hash"]


def test_tampering_with_a_delivered_chain_event_is_detected():
    r = run_research("What is the x402 payment protocol?", allow_network=False)
    chain = [dict(event) for event in r["custody_chain"]]
    chain[0]["payload"] = {"query": "something else"}
    assert verify_chain_records(chain) is False


def test_refused_and_unavailable_responses_also_deliver_a_chain():
    refused = run_research(ZEPHYRCORP, retriever=_Fixed([_source(BANANA)]))
    assert verify_chain_records(refused["custody_chain"]) is True

    class _Broken:
        name = "broken"

        def retrieve(self, query, max_results=5):
            raise ConnectionError("simulated outage")

    unavailable = run_research("anything", retriever=_Broken())
    assert unavailable["status"] == "unavailable"
    assert verify_chain_records(unavailable["custody_chain"]) is True


@pytest.mark.parametrize("query,retriever_sources", [
    ("What is the x402 payment protocol?", None),
    (ZEPHYRCORP, [BANANA]),
])
def test_no_posterior_or_confidence_appears_on_the_wire(query, retriever_sources):
    """P3/P4/P5. Unearnable numbers are removed rather than improved."""
    if retriever_sources is None:
        r = run_research(query, allow_network=False)
    else:
        r = run_research(query, retriever=_Fixed([_source(t) for t in retriever_sources]))
    assert "posterior" not in r
    for claim in r["claims"]:
        assert "confidence" not in claim


def test_support_report_replaces_the_posterior():
    """What ships instead is countable and recomputable from the evidence."""
    sources = [
        _source("The x402 payment protocol lets agents pay for APIs over HTTP.",
                url="https://first-publisher.org/x", provider="p1"),
        _source("The x402 payment protocol is an open standard for HTTP payments.",
                url="https://second-publisher.com/y", provider="p2"),
    ]
    r = run_research("What is the x402 payment protocol?", retriever=_Fixed(sources))
    support = r["support"]
    assert support["independent_domains"] == 2
    assert support["verdict"] == "corroborated"
    assert support["method"].startswith("veritas.support.")


def test_subdomains_of_one_site_are_one_publisher_not_two_witnesses():
    """Independence is counted per registrable domain: two pages on one site
    are one publisher, however many hostnames it uses."""
    sources = [
        _source("The x402 payment protocol lets agents pay for APIs over HTTP.",
                url="https://a.example.org/x", provider="p1"),
        _source("The x402 payment protocol is an open standard for HTTP payments.",
                url="https://b.example.org/y", provider="p2"),
    ]
    r = run_research("What is the x402 payment protocol?", retriever=_Fixed(sources))
    assert r["support"]["independent_domains"] == 1
    assert r["support"]["verdict"] == "single_source"


def test_single_domain_is_reported_as_single_source():
    sources = [
        _source("The x402 payment protocol lets agents pay for APIs over HTTP.",
                url="https://a.example.org/one", provider="p1"),
        _source("The x402 payment protocol is an open standard for HTTP payments.",
                url="https://a.example.org/two", provider="p1"),
    ]
    r = run_research("What is the x402 payment protocol?", retriever=_Fixed(sources))
    assert r["support"]["independent_domains"] == 1
    assert r["support"]["verdict"] == "single_source"


def test_responses_still_conform_to_the_wire_contract():
    for r in (
        run_research("What is the x402 payment protocol?", allow_network=False),
        run_research(ZEPHYRCORP, retriever=_Fixed([_source(BANANA)])),
    ):
        assert validate_response(r) == []


def test_price_is_validated_by_the_misconfiguration_guard(monkeypatch):
    """R9. `price` was the one live-mode field the guard never checked, so a
    typo produced mode=='live', a green /health, and a 500 on every request."""
    from veritas.payment_config import PaymentConfig

    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "1" * 40)
    monkeypatch.setenv("VERITAS_PRICE", "0.25 USD each")
    cfg = PaymentConfig.from_env()
    assert cfg.mode == "misconfigured"
    assert any("PRICE" in e or "price" in e for e in cfg.config_errors)


def test_default_price_is_the_market_facing_one(monkeypatch):
    """$0.25 was 25x comparable x402 endpoints for a worse deliverable."""
    from veritas.payment_config import PaymentConfig

    for var in ("VERITAS_PRICE", "VERITAS_REQUIRE_PAYMENT", "VERITAS_PAY_TO"):
        monkeypatch.delenv(var, raising=False)
    assert PaymentConfig.from_env().price == "$0.01"


def test_payment_validation_does_not_rely_on_assert(monkeypatch):
    """T8. `assert` in the payment path vanishes under `python -O`."""
    import inspect

    from veritas import payer

    source = inspect.getsource(payer.validate_accepts)
    assert "assert " not in source, "payment validation still relies on assert"
