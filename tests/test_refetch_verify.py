"""P7 product: origin re-fetch verification via notary.observe (one engine)."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from veritas.evidence_store import EvidenceStore
from veritas.hashing import compute_content_hash
from veritas.notary.fetch import FetchError, FetchResult
from veritas.notary.refetch import (
    STORED_EXCERPT_BINDING,
    refetch_verify,
)
from veritas.safeurl import UnsafeUrlError


def _fetch(body: bytes):
    def fake_fetch(request_url, **kwargs):
        return FetchResult(
            request_url=request_url,
            final_url=request_url,
            status=200,
            headers={"content-type": "text/plain"},
            body=body,
            truncated=False,
        )

    return fake_fetch


def _dead_fetch(request_url, **kwargs):
    raise FetchError("origin gone", url=request_url)


def _ssrf_fetch(request_url, **kwargs):
    raise UnsafeUrlError("refusing private destination")


def _status_fetch(body: bytes, status: int):
    def fake_fetch(request_url, **kwargs):
        return FetchResult(
            request_url=request_url,
            final_url=request_url,
            status=status,
            headers={"content-type": "text/plain"},
            body=body,
            truncated=False,
        )

    return fake_fetch


ROBOTS_ALLOW = "User-agent: *\nAllow: /\n"


@pytest.fixture
def free_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    import veritas.server as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_refetch_verify_match():
    body = b"Stable notarized page body for P7."
    expected = compute_content_hash(body.decode("utf-8"))
    out = refetch_verify(
        "https://example.org/page",
        expected,
        robots_body="User-agent: *\nAllow: /\n",
        fetch_fn=_fetch(body),
    )
    assert out["valid"] is True
    assert out["match"] is True
    assert out["binding"] == "origin_refetch"
    assert out["actual"] == expected
    assert out["reason"] == "match"


def test_refetch_verify_diverged():
    body = b"Current origin body."
    expected = compute_content_hash("something else entirely")
    out = refetch_verify(
        "https://example.org/page",
        expected,
        robots_body="User-agent: *\nAllow: /\n",
        fetch_fn=_fetch(body),
    )
    assert out["valid"] is False
    assert out["match"] is False
    assert out["reason"] == "diverged"
    assert out["actual"] == compute_content_hash(body.decode("utf-8"))
    assert out["binding"] == "origin_refetch"


def test_refetch_falls_back_to_stored_excerpt_when_origin_is_gone(tmp_path):
    """P13 remainder: dead origin + stored bytes → stored_excerpt, not origin."""
    text = "bytes we stored before the origin vanished"
    digest = compute_content_hash(text)
    store = EvidenceStore(tmp_path)
    assert store.put(digest, text, url="https://example.org/page")

    out = refetch_verify(
        "https://example.org/page",
        digest,
        evidence_store=store,
        robots_body=ROBOTS_ALLOW,
        fetch_fn=_dead_fetch,
    )
    assert out["binding"] == STORED_EXCERPT_BINDING
    assert out["status"] == STORED_EXCERPT_BINDING
    assert out["reason"] == STORED_EXCERPT_BINDING
    assert out["valid"] is True
    assert out["match"] is True
    assert out["actual"] == digest
    assert out["expected"] == digest
    assert out["stored_url"] == "https://example.org/page"
    assert "origin" not in out["binding"]
    assert "independent" not in out["note"].lower() or "not" in out["note"]
    assert "not a live origin" in out["note"]


def test_refetch_ssrf_refusal_uses_stored_excerpt_not_origin(tmp_path):
    text = "previously observed public origin body"
    digest = compute_content_hash(text)
    store = EvidenceStore(tmp_path)
    assert store.put(digest, text, url="https://example.org/once-public")

    out = refetch_verify(
        "https://example.org/once-public",
        digest,
        evidence_store=store,
        robots_body=ROBOTS_ALLOW,
        fetch_fn=_ssrf_fetch,
    )
    assert out["binding"] == STORED_EXCERPT_BINDING
    assert out["valid"] is True
    assert out["match"] is True
    assert out["status"] != "completed"


def test_refetch_404_uses_stored_excerpt_when_present(tmp_path):
    text = "the page that later 404ed"
    digest = compute_content_hash(text)
    store = EvidenceStore(tmp_path)
    assert store.put(digest, text, url="https://example.org/gone")

    out = refetch_verify(
        "https://example.org/gone",
        digest,
        evidence_store=store,
        robots_body=ROBOTS_ALLOW,
        fetch_fn=_status_fetch(b"Not Found", 404),
    )
    assert out["binding"] == STORED_EXCERPT_BINDING
    assert out["valid"] is True
    assert out["actual"] == digest
    assert out["binding"] != "origin_refetch"


def test_refetch_no_stored_excerpt_keeps_origin_failure(tmp_path):
    """Empty store + dead origin → existing failure, not a false stored hit."""
    digest = compute_content_hash("never stored this body")
    store = EvidenceStore(tmp_path)

    out = refetch_verify(
        "https://example.org/missing",
        digest,
        evidence_store=store,
        robots_body=ROBOTS_ALLOW,
        fetch_fn=_dead_fetch,
    )
    assert out["valid"] is False
    assert out["match"] is False
    assert out["binding"] == "origin_refetch"
    assert out["status"] == "unavailable"
    assert out["actual"] is None
    assert out["reason"] != STORED_EXCERPT_BINDING


def test_refetch_404_without_store_stays_diverged(tmp_path):
    """No stored excerpt: a 404 body is still a completed (diverged) observe."""
    expected = compute_content_hash("the original page")
    store = EvidenceStore(tmp_path)
    out = refetch_verify(
        "https://example.org/gone",
        expected,
        evidence_store=store,
        robots_body=ROBOTS_ALLOW,
        fetch_fn=_status_fetch(b"Not Found", 404),
    )
    assert out["binding"] == "origin_refetch"
    assert out["valid"] is False
    assert out["reason"] == "diverged"
    assert out["status"] == "completed"


def test_refetch_live_origin_unchanged_even_when_store_has_bytes(tmp_path):
    """Live success stays origin_refetch; stored bytes are not a substitute."""
    text = "Stable notarized page body for P7."
    digest = compute_content_hash(text)
    store = EvidenceStore(tmp_path)
    assert store.put(digest, text, url="https://example.org/page")

    out = refetch_verify(
        "https://example.org/page",
        digest,
        evidence_store=store,
        robots_body=ROBOTS_ALLOW,
        fetch_fn=_fetch(text.encode("utf-8")),
    )
    assert out["valid"] is True
    assert out["match"] is True
    assert out["binding"] == "origin_refetch"
    assert out["reason"] == "match"
    assert out["status"] == "completed"


def test_refetch_live_divergence_not_hidden_by_stored_excerpt(tmp_path):
    """Origin is live and changed: report diverged, do not serve old bytes."""
    old = "yesterday's body"
    new = "today's different body"
    digest = compute_content_hash(old)
    store = EvidenceStore(tmp_path)
    assert store.put(digest, old, url="https://example.org/page")

    out = refetch_verify(
        "https://example.org/page",
        digest,
        evidence_store=store,
        robots_body=ROBOTS_ALLOW,
        fetch_fn=_fetch(new.encode("utf-8")),
    )
    assert out["binding"] == "origin_refetch"
    assert out["valid"] is False
    assert out["reason"] == "diverged"
    assert out["actual"] == compute_content_hash(new)


def test_refetch_corrupt_store_is_not_a_stored_hit(tmp_path):
    """A file whose excerpt no longer hashes to its key is a miss."""
    text = "canonical stored body"
    digest = compute_content_hash(text)
    store = EvidenceStore(tmp_path)
    assert store.put(digest, text)
    path = store._file_path(digest)
    assert path is not None
    path.write_text(
        f'{{"content_hash":"{digest}","excerpt":"tampered","url":null,'
        '"title":null,"stored_at":"x"}',
        encoding="utf-8",
    )
    assert store.get(digest) is None

    out = refetch_verify(
        "https://example.org/page",
        digest,
        evidence_store=store,
        robots_body=ROBOTS_ALLOW,
        fetch_fn=_dead_fetch,
    )
    assert out["binding"] == "origin_refetch"
    assert out["valid"] is False
    assert out["reason"] != STORED_EXCERPT_BINDING


def test_verify_endpoint_url_refetch(free_client, monkeypatch):
    expected = compute_content_hash("Wire-level re-fetch body.")

    import veritas.notary.refetch as refetch_mod

    def fake_refetch(url, content_hash, **kwargs):
        assert url == "https://example.org/wire"
        assert content_hash == expected
        return {
            "valid": True,
            "binding": "origin_refetch",
            "match": True,
            "status": "completed",
            "reason": "match",
            "expected": expected,
            "actual": expected,
            "url": url,
            "note": "test",
        }

    monkeypatch.setattr(refetch_mod, "refetch_verify", fake_refetch)
    r = free_client.post(
        "/v1/verify",
        json={"url": "https://example.org/wire", "content_hash": expected},
    )
    assert r.status_code == 200
    assert r.json()["valid"] is True
    assert r.json()["binding"] == "origin_refetch"


def test_verify_endpoint_legacy_caller_supplied_labeled(free_client):
    text = "legacy arithmetic only"
    h = compute_content_hash(text)
    r = free_client.post("/v1/verify", json={"content": text, "content_hash": h})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["binding"] == "caller_supplied"
    assert "not an origin re-fetch" in body["note"]


def test_verify_endpoint_request_id_refetch(free_client, monkeypatch):
    import veritas.server as main_module

    rid = "req-p7-receipt-1"
    published = compute_content_hash("published body")
    main_module.store.save(
        {
            "request_id": rid,
            "query": "https://example.org/from-receipt",
            "status": "completed",
            "custody_root": "sha256:" + "ab" * 32,
            "custody_valid": True,
            "evidence": [{"content_hash": published}],
        }
    )

    import veritas.notary.refetch as refetch_mod

    def fake_refetch(url, content_hash, **kwargs):
        assert url == "https://example.org/from-receipt"
        assert content_hash == published
        return {
            "valid": True,
            "binding": "origin_refetch",
            "match": True,
            "status": "completed",
            "reason": "match",
            "expected": published,
            "actual": published,
            "url": url,
            "note": "test",
        }

    monkeypatch.setattr(refetch_mod, "refetch_verify", fake_refetch)
    r = free_client.post("/v1/verify", json={"request_id": rid})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["binding"] == "receipt_refetch"
    assert body["request_id"] == rid


def test_verify_endpoint_uses_stored_excerpt_when_origin_dead(free_client, tmp_path, monkeypatch):
    """HTTP: stored bytes + failed observe → stored_excerpt, not origin."""
    text = "http-level stored excerpt body for a vanished origin"
    digest = compute_content_hash(text)
    assert EvidenceStore(tmp_path).put(digest, text, url="https://example.org/http-gone")

    import veritas.notary.refetch as refetch_mod

    def fail_observe(url, **kwargs):
        return {
            "status": "unavailable",
            "refusal_reason": "fetch_unavailable",
            "request_id": "obs-dead",
        }

    monkeypatch.setattr(refetch_mod, "observe", fail_observe)
    r = free_client.post(
        "/v1/verify",
        json={"url": "https://example.org/http-gone", "content_hash": digest},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["binding"] == STORED_EXCERPT_BINDING
    assert body["valid"] is True
    assert body["match"] is True
    assert body["actual"] == digest
    assert body["binding"] != "origin_refetch"
    assert "not a live origin" in body["note"]


def test_verify_endpoint_no_store_keeps_failure_class(free_client, monkeypatch):
    digest = compute_content_hash("never written to the evidence store")

    import veritas.notary.refetch as refetch_mod

    def fail_observe(url, **kwargs):
        return {
            "status": "unavailable",
            "refusal_reason": "fetch_unavailable",
            "request_id": "obs-dead",
        }

    monkeypatch.setattr(refetch_mod, "observe", fail_observe)
    r = free_client.post(
        "/v1/verify",
        json={"url": "https://example.org/no-store", "content_hash": digest},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["binding"] == "origin_refetch"
    assert body["valid"] is False
    assert body["reason"] == "fetch_unavailable"
    assert body["status"] == "unavailable"


def test_receipt_verify_preserves_stored_excerpt_binding(free_client, tmp_path, monkeypatch):
    """Receipt path must not relabel stored_excerpt as receipt_refetch."""
    import veritas.server as main_module

    text = "receipt-bound body kept after origin died"
    published = compute_content_hash(text)
    assert EvidenceStore(tmp_path).put(
        published, text, url="https://example.org/from-receipt"
    )
    rid = "req-p13-stored-1"
    main_module.store.save(
        {
            "request_id": rid,
            "query": "https://example.org/from-receipt",
            "status": "completed",
            "custody_root": "sha256:" + "ab" * 32,
            "custody_valid": True,
            "evidence": [{"content_hash": published}],
        }
    )

    import veritas.notary.refetch as refetch_mod

    def fail_observe(url, **kwargs):
        return {
            "status": "unavailable",
            "refusal_reason": "fetch_unavailable",
            "request_id": "obs-dead",
        }

    monkeypatch.setattr(refetch_mod, "observe", fail_observe)
    r = free_client.post("/v1/verify", json={"request_id": rid})
    assert r.status_code == 200
    body = r.json()
    assert body["binding"] == STORED_EXCERPT_BINDING
    assert body["valid"] is True
    assert body["request_id"] == rid
    assert body["binding"] != "receipt_refetch"
    """Found live 2026-08-09: a research receipt stores the buyer's QUESTION
    in `query`, and receipt re-fetch tried to fetch the question as a URL —
    the refusal surfaced as `robots_unknown`, a claim about an origin's
    robots policy for something that was never an origin. Could-not-check
    must not impersonate a specific failure, and no slot/fetch is owed."""
    import veritas.server as main_module

    rid = "req-research-receipt-1"
    main_module.store.save(
        {
            "request_id": rid,
            "query": "What is the x402 payment protocol?",
            "status": "completed",
            "custody_root": "sha256:" + "cd" * 32,
            "custody_valid": True,
            "evidence": [{"content_hash": compute_content_hash("evidence body")}],
        }
    )

    import veritas.notary.refetch as refetch_mod

    def must_not_fetch(url, content_hash, **kwargs):
        raise AssertionError(f"refetch attempted for non-URL query: {url!r}")

    monkeypatch.setattr(refetch_mod, "refetch_verify", must_not_fetch)
    r = free_client.post("/v1/verify", json={"request_id": rid})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert body["binding"] == "receipt_refetch"
    assert body["reason"] == "receipt_not_refetchable"
    assert "robots" not in json.dumps(body)
    assert "url+content_hash" in body["note"]


def test_verify_endpoint_requires_a_mode(free_client):
    r = free_client.post("/v1/verify", json={})
    assert r.status_code == 422


def test_verify_source_binds_store_or_refetch():
    """P7 close witness: independent path is present on /v1/verify."""
    from veritas import server as server_module

    source = Path(server_module.__file__).read_text(encoding="utf-8")
    verify_body = source.split('@app.post("/v1/verify")')[1].split("@app.")[0]
    assert "store.load" in verify_body
    assert "refetch_verify" in verify_body
    # P7-C: re-fetch modes share research_slots with research/notarize.
    assert "research_slots.acquire" in verify_body


def test_verify_refetch_sheds_when_research_slots_full(free_client, monkeypatch):
    """P7-C: free origin re-fetch must not bypass the research semaphore."""
    import veritas.server as main_module

    expected = compute_content_hash("should not run re-fetch")
    held = []
    try:
        while main_module.research_slots.acquire(blocking=False):
            held.append(1)
        assert held, "expected at least one research slot to hold"

        r = free_client.post(
            "/v1/verify",
            json={"url": "https://example.org/shed", "content_hash": expected},
        )
        assert r.status_code == 503
        body = r.json()
        assert body["error"] == "service_overloaded"
        assert r.headers.get("Retry-After") == main_module.OVERLOAD_RETRY_AFTER
    finally:
        for _ in held:
            main_module.research_slots.release()


def test_verify_legacy_caller_supplied_skips_research_slots(free_client, monkeypatch):
    """Caller-supplied arithmetic is free CPU — must not take research_slots."""
    import veritas.server as main_module

    text = "no outbound work"
    h = compute_content_hash(text)
    held = []
    try:
        while main_module.research_slots.acquire(blocking=False):
            held.append(1)
        r = free_client.post("/v1/verify", json={"content": text, "content_hash": h})
        assert r.status_code == 200
        assert r.json()["binding"] == "caller_supplied"
    finally:
        for _ in held:
            main_module.research_slots.release()
