"""Content-addressed excerpt store + HTTP surface.

PROPERTY: an excerpt persisted under its published hash is returned by
GET /v1/evidence/{hash}. A wrong hash, an unsafe path, or a miss is 404
not_found — never a guessed body.

EVIDENCE LEVEL: L1. NOT proven: multi-host durability without a shared URL.
"""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.testclient import TestClient

from veritas.evidence_store import EvidenceStore, is_safe_content_hash
from veritas.hashing import compute_content_hash
from veritas.pipeline import run_research
from veritas.retrieval import StaticCorpusRetriever


def test_hash_allowlist_rejects_path_traversal():
    assert is_safe_content_hash("sha256:" + "ab" * 32)
    assert not is_safe_content_hash("../secrets")
    assert not is_safe_content_hash("sha256:zzzz")
    assert not is_safe_content_hash("sha256:" + "ab" * 31)


def test_put_refuses_mismatched_hash(tmp_path):
    store = EvidenceStore(tmp_path)
    assert store.put("sha256:" + "ab" * 32, "hello") is False
    assert store.get("sha256:" + "ab" * 32) is None


def test_put_and_get_roundtrip(tmp_path):
    store = EvidenceStore(tmp_path)
    text = "x402 is an open standard for internet-native payments over HTTP."
    digest = compute_content_hash(text)
    assert store.put(digest, text, url="https://example/x402", title="x402")
    got = store.get(digest)
    assert got is not None
    assert got["excerpt"] == text
    assert got["url"] == "https://example/x402"


def test_get_refuses_tampered_excerpt(tmp_path):
    """A on-disk record whose excerpt no longer hashes to its key is a miss."""
    store = EvidenceStore(tmp_path)
    text = "canonical body that will be overwritten"
    digest = compute_content_hash(text)
    assert store.put(digest, text)
    path = store._file_path(digest)
    assert path is not None
    path.write_text(
        f'{{"content_hash":"{digest}","excerpt":"not the original","url":null,'
        '"title":null,"stored_at":"x"}',
        encoding="utf-8",
    )
    assert store.get(digest) is None


def test_pipeline_persists_excerpts_for_later_fetch(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    result = run_research(
        "What is the x402 protocol?",
        retriever=StaticCorpusRetriever(),
    )
    assert result["status"] == "completed"
    store = EvidenceStore(tmp_path)
    for ev in result["evidence"]:
        got = store.get(ev["content_hash"])
        assert got is not None
        assert got["excerpt"] == ev["excerpt"]


def test_http_surface_returns_stored_excerpt(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    import veritas.server as server
    importlib.reload(server)
    text = "stored excerpt body for the evidence endpoint test " + ("pad " * 10)
    digest = compute_content_hash(text)
    assert server.evidence_bodies.put(digest, text, url="https://ex/a")
    client = TestClient(server.app)
    body = client.get(f"/v1/evidence/{digest}").json()
    assert body["excerpt"] == text
    missing = client.get("/v1/evidence/sha256:" + "cd" * 32)
    assert missing.status_code == 404
    assert missing.json()["error"] == "not_found"
    traversal = client.get("/v1/evidence/../secrets")
    assert traversal.status_code == 404


def test_a_traversing_hash_never_reaches_the_filesystem(tmp_path, monkeypatch):
    """Rejection is by validation, not by the file happening to be absent.

    Same contract as custody O17: a wire value that is not a published
    digest must not open anything, including a canary one directory up.
    """
    store = EvidenceStore(tmp_path)
    (tmp_path / "canary.json").write_text('{"SECRET":"canary"}', encoding="utf-8")
    opened: list[str] = []
    real = Path.read_text

    def spy(self, *a, **kw):
        opened.append(str(self))
        return real(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", spy)
    for bad in (
        "../secrets",
        "sha256:zzzz",
        "sha256:" + "ab" * 31,
        "/etc/passwd",
        r"..\canary",
        "sha256:" + "../" + "ab" * 30,
    ):
        assert store.get(bad) is None, f"{bad!r} escaped the evidence directory"
        assert store._file_path(bad) is None
    assert opened == [], f"traversing hashes reached the filesystem: {opened}"
