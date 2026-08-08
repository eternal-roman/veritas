"""N0 observe: fetch → extract → record(+policy); research routes through it."""

from __future__ import annotations

from veritas.hashing import compute_content_hash, verify_content_hash
from veritas.notary.extract import EXTRACT_VERSION
from veritas.notary.fetch import FetchError, FetchResult
from veritas.notary.observe import observe
from veritas.notary.record import RETENTION_CLASS_STANDARD
from veritas.notary.robots import FetchClass
from veritas.pipeline import run_research
from veritas.retrieval import RetrievalResult
from veritas.safeurl import UnsafeUrlError


def _ok_fetch(url: str, **_kwargs) -> FetchResult:
    return FetchResult(
        request_url=url,
        final_url=url,
        status=200,
        headers={"content-type": "text/plain; charset=utf-8"},
        body=b"Full observed body from origin for notary tests.",
        truncated=False,
    )


def test_observe_composes_fetch_extract_record_and_stores_full_body():
    url = "https://example.org/article"
    result = observe(
        url,
        fetch_fn=_ok_fetch,
        robots_body="",  # empty robots → allow-all
        declared_license="CC0-1.0",
        request_id="obs-1",
        observed_at="2026-08-08T12:00:00Z",
    )
    assert result["status"] == "completed"
    assert result["billable"] is True
    assert result["request_id"] == "obs-1"
    record = result["evidence_record"]
    assert record["body"] == "Full observed body from origin for notary tests."
    assert record["content_hash"] == compute_content_hash(record["body"])
    assert record["extract_version"] == EXTRACT_VERSION
    assert record["retention_class"] == RETENTION_CLASS_STANDARD
    ok, _ = verify_content_hash(record["body"], record["content_hash"])
    assert ok
    assert result["policy"]["license"]["id"] == "CC0-1.0"
    assert result["policy"]["robots"]["allowance"] == FetchClass.ALLOWED
    assert result["custody_valid"] is True
    assert result["custody_chain"]
    assert result["evidence"][0]["content_hash"] == record["content_hash"]
    # Anti-theater: evidence excerpt is the stored body, not a truncated hash-only stub.
    assert result["evidence"][0]["excerpt"] == record["body"]


def test_observe_unavailable_on_fetch_error_is_not_billable():
    def boom(url: str, **_kwargs):
        raise FetchError("connection reset", url=url)

    result = observe(
        "https://example.org/down",
        fetch_fn=boom,
        robots_body="",
    )
    assert result["status"] == "unavailable"
    assert result["billable"] is False
    assert result["refusal_reason"] == "fetch_unavailable"
    assert result["evidence_record"] is None


def test_observe_unavailable_on_ssrf_refusal_is_not_billable():
    def refuse(url: str, **_kwargs):
        raise UnsafeUrlError("refusing private destination")

    result = observe(
        "https://evil.example/private",
        fetch_fn=refuse,
        robots_body="",
    )
    assert result["status"] == "unavailable"
    assert result["billable"] is False


def test_robots_deny_is_not_silently_ignored():
    result = observe(
        "https://example.org/private",
        fetch_fn=_ok_fetch,
        robots_body="User-agent: *\nDisallow: /\n",
    )
    assert result["status"] == "refused"
    assert result["refusal_reason"] == "robots_denied"
    assert result["policy"]["robots"]["allowance"] == FetchClass.DENIED
    assert result["policy"]["robots"]["may_fetch"] is False
    # No body was observed under an un-overridden deny.
    assert result["evidence_record"] is None
    assert result["billable"] is True  # we delivered a policy refusal, not an outage


def test_robots_override_allows_fetch_and_records_underlying_deny():
    result = observe(
        "https://example.org/private",
        fetch_fn=_ok_fetch,
        robots_body="User-agent: *\nDisallow: /\n",
        robots_override="operator_policy:notarize_despite_robots",
        declared_license={"id": "unknown"},
    )
    assert result["status"] == "completed"
    assert result["policy"]["robots"]["allowance"] == FetchClass.OVERRIDE
    assert result["policy"]["robots"]["underlying"] == FetchClass.DENIED
    assert result["evidence_record"]["body"]


def test_missing_robots_is_unknown_fail_closed():
    result = observe(
        "https://example.org/page",
        fetch_fn=_ok_fetch,
        robots_body=None,
    )
    assert result["status"] == "refused"
    assert result["refusal_reason"] == "robots_unknown"
    assert result["policy"]["robots"]["allowance"] == FetchClass.UNKNOWN
    assert result["billable"] is True


def test_unknown_license_stays_explicit_on_completed_record():
    result = observe(
        "https://example.org/page",
        fetch_fn=_ok_fetch,
        robots_body="",
        declared_license=None,
    )
    assert result["status"] == "completed"
    lic = result["policy"]["license"]
    assert lic["reuse"] == "unknown"
    assert lic["assumed_permissive"] is False
    assert lic["may_reuse"] is False


def test_custom_retention_class_is_stamped():
    result = observe(
        "https://example.org/e",
        fetch_fn=_ok_fetch,
        robots_body="",
        retention_class="ephemeral",
    )
    assert result["evidence_record"]["retention_class"] == "ephemeral"


def test_pipeline_routes_url_observation_through_observe():
    """A1: research remains the sole engine; URL observation uses notary.observe."""
    calls: list[str] = []

    def fake_observe(url: str, **kwargs):
        calls.append(url)
        # Keep query-relevant tokens so the pipeline relevance gate still passes.
        body = f"observed full page about the x402 protocol payment at {url}"
        return {
            "status": "completed",
            "billable": True,
            "evidence_record": {
                "url": url,
                "body": body,
                "content_hash": compute_content_hash(body),
                "title": "Observed",
                "extract_version": EXTRACT_VERSION,
                "retention_class": RETENTION_CLASS_STANDARD,
                "media_kind": "text",
            },
            "policy": {
                "license": {"id": "unknown", "reuse": "unknown"},
                "robots": {"allowance": "allowed", "may_fetch": True},
            },
        }

    class UrlOnlyRetriever:
        name = "url_only"

        def retrieve(self, query, max_results=5):
            return RetrievalResult(
                sources=[{
                    "url": "https://example.org/src",
                    "title": "Snippet title",
                    "text": "x402 protocol payment evidence tokens enough to pass gate",
                    "provider": "url_only",
                    "provenance": "test",
                    "license": {"id": "unknown"},
                }],
                providers_attempted=["url_only"],
                providers_succeeded=["url_only"],
            )

    result = run_research(
        "What is the x402 protocol payment?",
        retriever=UrlOnlyRetriever(),
        observe_urls=True,
        observer=fake_observe,
    )
    assert calls == ["https://example.org/src"]
    assert result["status"] == "completed"
    # Body came from observe, not the original snippet alone.
    assert any(
        (e.get("excerpt") or "").startswith("observed full page") for e in result["evidence"]
    )
    assert any(e.get("observed") is True for e in result["evidence"])


def test_pipeline_does_not_call_observer_when_observe_urls_false():
    def boom(*_a, **_k):
        raise AssertionError("observer must not run unless observe_urls is set")

    class LocalRetriever:
        name = "local"

        def retrieve(self, query, max_results=5):
            return RetrievalResult(
                sources=[{
                    "url": "https://example.org/x",
                    "title": "T",
                    "text": "x402 protocol payment evidence tokens enough to pass gate",
                    "provider": "local",
                    "provenance": "test",
                }],
                providers_attempted=["local"],
                providers_succeeded=["local"],
            )

    result = run_research(
        "What is the x402 protocol payment?",
        retriever=LocalRetriever(),
        observe_urls=False,
        observer=boom,
    )
    assert result["status"] == "completed"


def test_default_observer_is_notary_observe(monkeypatch):
    """When observe_urls is on and no observer is injected, use notary.observe."""
    seen: list[str] = []

    def stub(url: str, **kwargs):
        seen.append(url)
        body = "from-default-observe covering x402 protocol payment evidence"
        return {
            "status": "completed",
            "billable": True,
            "evidence_record": {
                "url": url,
                "body": body,
                "content_hash": compute_content_hash(body),
                "title": None,
                "extract_version": EXTRACT_VERSION,
                "retention_class": RETENTION_CLASS_STANDARD,
                "media_kind": "text",
            },
            "policy": {"license": {}, "robots": {"may_fetch": True}},
        }

    monkeypatch.setattr("veritas.notary.observe.observe", stub)

    class R:
        name = "r"

        def retrieve(self, query, max_results=5):
            return RetrievalResult(
                sources=[{
                    "url": "https://example.org/y",
                    "title": "Y",
                    "text": "x402 protocol payment evidence tokens enough to pass gate",
                    "provider": "r",
                    "provenance": "test",
                }],
                providers_attempted=["r"],
                providers_succeeded=["r"],
            )

    result = run_research(
        "What is the x402 protocol payment?",
        retriever=R(),
        observe_urls=True,
    )
    assert seen == ["https://example.org/y"]
    assert result["status"] == "completed"
