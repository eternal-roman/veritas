"""Keyed provider behaviour: Serper parsing, fail-soft degradation, ordering,
and — most importantly — that the API key never leaks out of the module."""

import io
import json
import urllib.error

from veritas.pipeline import run_research
from veritas.providers import SerperRetriever, serper_api_key
from veritas.retrieval import CompositeRetriever, StaticCorpusRetriever, default_retriever

KEY = "sk-serper-test-secret-000"

SERPER_FIXTURE = {
    "organic": [
        {
            "title": "x402 Protocol",
            "link": "https://x402.org",
            "snippet": "x402 is an open standard for internet-native payments over HTTP.",
        },
        {
            "title": "x402 on the Linux Foundation",
            "link": "https://linuxfoundation.org/x402",
            "snippet": "The x402 payment protocol moved to the Linux Foundation.",
        },
        {"title": "no snippet, must be skipped", "link": "https://example.com/empty"},
    ]
}


class _FakeResponse:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch_urlopen(monkeypatch, handler):
    monkeypatch.setattr("urllib.request.urlopen", handler)


def test_serper_parses_organic_and_sends_key_as_header(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["headers"] = dict(req.header_items())
        captured["payload"] = json.loads(req.data.decode())
        captured["url"] = req.full_url
        return _FakeResponse(SERPER_FIXTURE)

    _patch_urlopen(monkeypatch, fake_urlopen)
    result = SerperRetriever(api_key=KEY).retrieve("What is x402?", max_results=2)

    assert captured["headers"].get("X-api-key") == KEY
    assert KEY not in captured["url"], "key must never appear in the URL"
    assert captured["payload"] == {"q": "What is x402?", "num": 2}

    assert result.providers_succeeded == ["serper"]
    assert not result.errors
    assert [s["url"] for s in result.sources] == ["https://x402.org",
                                                  "https://linuxfoundation.org/x402"]
    assert all(s["provenance"] == "search_snippet" and s["provider"] == "serper"
               for s in result.sources)


def test_serper_http_error_fails_soft(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "unauthorized", {}, io.BytesIO(b""))

    _patch_urlopen(monkeypatch, fake_urlopen)
    result = SerperRetriever(api_key=KEY).retrieve("anything")

    assert result.sources == []
    assert result.providers_succeeded == []
    assert result.errors and result.errors[0].error_type == "http_error"
    assert result.unavailable


def test_key_never_leaks_into_errors_or_serialisation(monkeypatch):
    """Even a provider that echoes the key back must not get it into our
    error channel, and no serialised result may contain it."""

    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError(f"denied for key {KEY}")

    _patch_urlopen(monkeypatch, fake_urlopen)
    result = SerperRetriever(api_key=KEY).retrieve("anything")

    serialised = json.dumps(result.to_dict())
    assert KEY not in serialised
    assert "[redacted]" in result.errors[0].detail


def test_serper_without_key_reports_not_configured(monkeypatch):
    monkeypatch.delenv("VERITAS_SERPER_API_KEY", raising=False)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    result = SerperRetriever().retrieve("anything")
    assert result.errors[0].error_type == "not_configured"
    assert result.unavailable


def test_serper_malformed_response_is_an_error(monkeypatch):
    _patch_urlopen(monkeypatch, lambda req, timeout=None: _FakeResponse({"unexpected": True}))
    result = SerperRetriever(api_key=KEY).retrieve("anything")
    assert result.errors[0].error_type == "malformed_response"
    assert result.providers_succeeded == []


def test_default_retriever_registers_serper_first_when_key_set(monkeypatch):
    monkeypatch.setenv("VERITAS_SERPER_API_KEY", KEY)
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    r = default_retriever(allow_network=True)
    assert isinstance(r, CompositeRetriever)
    assert [type(x).__name__ for x in r.retrievers] == ["SerperRetriever", "ZeroKeyRetriever"]


def test_default_retriever_skips_serper_in_free_mode_even_with_key(monkeypatch):
    """R10: unpaid traffic must not burn a paid provider."""
    monkeypatch.setenv("VERITAS_SERPER_API_KEY", KEY)
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.delenv("VERITAS_SERPER_IN_FREE_MODE", raising=False)
    r = default_retriever(allow_network=True)
    assert [type(x).__name__ for x in r.retrievers] == ["ZeroKeyRetriever"]


def test_default_retriever_serper_opt_in_free_mode(monkeypatch):
    monkeypatch.setenv("VERITAS_SERPER_API_KEY", KEY)
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.setenv("VERITAS_SERPER_IN_FREE_MODE", "true")
    r = default_retriever(allow_network=True)
    assert [type(x).__name__ for x in r.retrievers] == ["SerperRetriever", "ZeroKeyRetriever"]


def test_default_retriever_skips_serper_without_key(monkeypatch):
    monkeypatch.delenv("VERITAS_SERPER_API_KEY", raising=False)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    assert serper_api_key() == ""
    r = default_retriever(allow_network=True)
    assert [type(x).__name__ for x in r.retrievers] == ["ZeroKeyRetriever"]


def test_serper_outage_degrades_to_next_tier():
    """Roadmap 1.2 acceptance: a provider outage degrades to the next tier
    and is reported, with no pipeline change."""

    class DownSerper(SerperRetriever):
        def _search(self, query, max_results):
            raise urllib.error.URLError("provider down")

    composite = CompositeRetriever([DownSerper(api_key=KEY), StaticCorpusRetriever()])
    r = run_research("What is the x402 protocol?", retriever=composite)

    assert r["status"] == "completed"                      # next tier answered
    assert r["retrieval"]["degraded"] is True              # and the outage is reported
    assert any(e["provider"] == "serper" for e in r["retrieval"]["errors"])


def test_pipeline_never_bills_when_only_serper_and_it_fails(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("provider down")

    _patch_urlopen(monkeypatch, fake_urlopen)
    r = run_research("What is x402?", retriever=SerperRetriever(api_key=KEY))
    assert r["status"] == "unavailable"
    assert r["billable"] is False
