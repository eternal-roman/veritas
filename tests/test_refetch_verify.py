"""P7 product: origin re-fetch verification via notary.observe (one engine)."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from veritas.hashing import compute_content_hash
from veritas.notary.fetch import FetchResult
from veritas.notary.refetch import refetch_verify


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
