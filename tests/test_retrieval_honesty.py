"""Provenance must be true, and the live path must not resell scraped results.

Two audited defects motivate this file:

* L1/L2 — `ddgs` is a *metasearch* library. On its default `auto` backend it
  shuffles across google, bing, yandex, brave, yahoo, startpage and mojeek, and
  the caller then stamped every result `provider: "duckduckgo"`. That is
  reselling scraped SERP snippets under a falsified provider label, inside a
  product whose entire pitch is verifiable provenance.
* L4 — the offline corpus publishes repo-authored text under real third-party
  URLs (`https://x402.org`) with a content hash, and it sat in the live
  retriever's fallback slot, so a paying caller could receive fabricated
  attribution.

The rule these tests enforce: **the provider named in a source is the provider
that was actually queried, and no source claims a URL we did not read it from.**
"""

from __future__ import annotations

import inspect

import pytest

from veritas import retrieval
from veritas.retrieval import StaticCorpusRetriever, default_retriever


def test_no_metasearch_backend_is_used():
    """L1. The scraper must be gone from the code path.

    Prose explaining *why* it was removed is deliberately still allowed — the
    repository keeps its defect history — so this asserts on imports and call
    sites rather than on any mention of the name.
    """
    from veritas.autonomous import zero_key_retrieval

    source = inspect.getsource(zero_key_retrieval)
    for forbidden in ("import ddgs", "from ddgs", "DDGS("):
        assert forbidden not in source, f"metasearch scraper still used: {forbidden}"
    assert not hasattr(zero_key_retrieval, "duckduckgo_search")


def test_ddgs_is_not_a_declared_dependency():
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    assert "ddgs" not in (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert "ddgs" not in (repo / "requirements.txt").read_text(encoding="utf-8")


def test_static_corpus_is_unreachable_from_the_live_retriever():
    """L4. Fabricated attribution must not be servable to a paying caller."""
    live = default_retriever(allow_network=True)
    assert getattr(live, "fallback", None) is None, (
        "the offline corpus is still reachable as a live fallback"
    )


def test_corpus_urls_are_not_third_party_attributions():
    """L4. Fixture text may not claim to have come from someone else's site."""
    for source in StaticCorpusRetriever().retrieve("x402", max_results=5).sources:
        url = source["url"]
        assert url.startswith("veritas://fixture/"), (
            f"corpus source claims a third-party URL: {url}"
        )
        assert source["provenance"] == "offline_corpus"


def test_offline_mode_still_serves_the_labelled_corpus():
    """Offline development keeps working; it is just honestly labelled."""
    result = StaticCorpusRetriever().retrieve("What is x402?", max_results=5)
    assert result.sources
    assert all(s["provider"] == "offline_corpus" for s in result.sources)


@pytest.mark.parametrize("provider_name", ["wikipedia", "duckduckgo_instant_answer"])
def test_zero_key_providers_name_the_engine_actually_queried(provider_name):
    """L2. Provider labels are the engine that served the bytes."""
    from veritas.autonomous import zero_key_retrieval

    source = inspect.getsource(zero_key_retrieval)
    assert f'"{provider_name}"' in source


def test_wikipedia_sources_carry_their_licence_and_attribution():
    """L3. CC BY-SA text must ship with its licence, not bare."""
    from veritas.autonomous.zero_key_retrieval import _wikipedia_source

    source = _wikipedia_source(
        title="Banana",
        extract="A banana is an elongated, edible fruit.",
        page_url="https://en.wikipedia.org/wiki/Banana",
    )
    assert source["license"]["id"] == "CC-BY-SA-4.0"
    assert source["license"]["url"].startswith("https://creativecommons.org/")
    assert source["attribution"]["required"] is True
    assert "Wikipedia" in source["attribution"]["text"]


def test_evidence_carries_licence_through_to_the_response():
    """A buyer must learn the licence of text they are about to reuse."""
    from veritas.pipeline import run_research
    from veritas.retrieval import RetrievalResult

    class _Licensed:
        name = "licensed"

        def retrieve(self, query, max_results=5):
            return RetrievalResult(
                sources=[{
                    "url": "https://en.wikipedia.org/wiki/X402",
                    "title": "x402",
                    "text": "The x402 payment protocol is an open standard for HTTP payments.",
                    "provider": "wikipedia",
                    "provenance": "live_fetch",
                    "license": {"id": "CC-BY-SA-4.0", "url": "https://creativecommons.org/licenses/by-sa/4.0/"},
                    "attribution": {"required": True, "text": "Wikipedia contributors"},
                }],
                providers_attempted=["wikipedia"], providers_succeeded=["wikipedia"],
            )

    r = run_research("What is the x402 payment protocol?", retriever=_Licensed())
    assert r["evidence"][0]["license"]["id"] == "CC-BY-SA-4.0"
    assert r["evidence"][0]["attribution"]["required"] is True


def test_unknown_licence_is_marked_unknown_not_assumed_permissive():
    assert retrieval.UNKNOWN_LICENSE["id"] == "unknown"
    assert retrieval.UNKNOWN_LICENSE.get("assumed_permissive") is not True
