"""The venue constitution: every article is enforced or admits it is not.

These tests are the constitution's own enforcement mechanism. An article
claiming evidence level L1 must point at an artifact that exists (a test, a CI
gate string, or a schema invariant string); an L0 article must carry no
enforcement and is rendered as aspirational. Pointer resolution here is
string-level: it proves the named artifact exists, not that it fully covers
the article's meaning.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from veritas.constitution import (
    ARTICLES,
    CONSTITUTION_VERSION,
    KNOWN_GAPS,
    build_constitution,
    validate_constitution,
)

REPO = Path(__file__).resolve().parent.parent
CI_WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"
SCHEMA_SOURCE = REPO / "veritas" / "schema.py"


@pytest.fixture
def free_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    import importlib

    import veritas.server as main_module
    importlib.reload(main_module)
    return TestClient(main_module.app)


def _resolve_test_pointer(pointer: str) -> bool:
    path, _, name = pointer.partition("::")
    source_file = REPO / path
    if not source_file.is_file() or not name:
        return False
    return f"def {name}(" in source_file.read_text()


def test_constitution_validates():
    assert validate_constitution(build_constitution()) == []


def test_every_enforcement_pointer_resolves():
    ci_text = CI_WORKFLOW.read_text()
    schema_text = SCHEMA_SOURCE.read_text()
    for article in ARTICLES:
        for enforcement in article["enforcement"]:
            kind, pointer = enforcement["kind"], enforcement["pointer"]
            if kind == "test":
                assert _resolve_test_pointer(pointer), (
                    f"{article['id']}: test pointer does not resolve: {pointer}"
                )
            elif kind == "ci-gate":
                assert pointer in ci_text, (
                    f"{article['id']}: ci-gate string absent from ci.yml: {pointer}"
                )
            elif kind == "schema":
                assert pointer in schema_text, (
                    f"{article['id']}: schema string absent from schema.py: {pointer}"
                )
            else:
                raise AssertionError(f"{article['id']}: unknown enforcement kind {kind!r}")


def test_article_ids_unique_and_levels_consistent():
    ids = [a["id"] for a in ARTICLES]
    assert len(ids) == len(set(ids)), "duplicate article ids"
    for article in ARTICLES:
        assert re.fullmatch(r"A\d+", article["id"]), article["id"]
        assert article["scope"] in {"service", "venue"}, article["id"]
        if article["evidence_level"] == "L1":
            assert article["enforcement"], f"{article['id']} claims L1 without enforcement"
        elif article["evidence_level"] == "L0":
            assert not article["enforcement"], f"{article['id']} is L0 but lists enforcement"
            assert article.get("promoted_by"), (
                f"{article['id']} is aspirational but names no path to enforcement"
            )
        else:
            raise AssertionError(f"{article['id']}: articles are L0 or L1, nothing else")


def test_articles_do_not_contradict_wire_contract():
    """A3's schema enforcement is demonstrated, not just asserted: a payload
    that bills for an unavailable response must be flagged by the contract."""
    from veritas.schema import validate_response

    payload = {
        "request_id": "r1",
        "status": "unavailable",
        "query": "anything",
        "support": {"n_evidence": 0, "verdict": "unsupported"},
        "custody_chain": [],
        "claims": [],
        "evidence": [],
        "custody_root": None,
        "custody_valid": False,
        "retrieval": {},
        "refusal_reason": "retrieval_unavailable",
        "billable": True,
        "timestamp": "2026-01-01T00:00:00Z",
    }
    assert any("must not be billable" in p for p in validate_response(payload))


def test_constitution_hash_stable():
    """The identity document once hashed its own timestamp and could not
    detect tampering; the constitution must not repeat that."""
    assert build_constitution()["content_hash"] == build_constitution()["content_hash"]


def test_known_gaps_shape():
    article_ids = {a["id"] for a in ARTICLES}
    for gap in KNOWN_GAPS:
        assert gap["article"] in article_ids, f"{gap['id']} references unknown article"
        assert gap["status"] in {"open", "closed"}, gap["id"]
        if gap["status"] == "open":
            assert _resolve_test_pointer(gap["witness_test"]), (
                f"{gap['id']}: witness test does not resolve: {gap['witness_test']}"
            )


def test_constitution_endpoint(free_client):
    """/v1/constitution serves the same document this module builds, unpaid
    (discovery must be free to read, article A10)."""
    body = free_client.get("/v1/constitution").json()
    assert validate_constitution(body) == []
    assert body["constitution_version"] == CONSTITUTION_VERSION
    assert body["content_hash"] == build_constitution()["content_hash"]


def test_identity_references_constitution(free_client):
    """A buyer evaluating the service from its identity document alone must
    learn that a constitution exists and where to fetch it."""
    first = free_client.get("/v1/identity").json()
    second = free_client.get("/v1/identity").json()
    assert first["constitution"]["version"] == CONSTITUTION_VERSION
    assert first["endpoints"]["constitution"].endswith("/v1/constitution")
    assert first["content_hash"] == second["content_hash"]


def test_constitution_md_in_sync():
    """CONSTITUTION.md is a rendering of this module, not a second source of
    truth: every article id and verbatim statement must appear in it, and
    every aspirational article must be rendered as such. Rewording an article
    without updating both places breaks this test by design."""
    text = (REPO / "CONSTITUTION.md").read_text()
    assert f"version {CONSTITUTION_VERSION}" in text
    for article in ARTICLES:
        assert article["id"] in text, f"{article['id']} missing from CONSTITUTION.md"
        assert article["statement"] in text, (
            f"{article['id']} statement not rendered verbatim in CONSTITUTION.md"
        )
        if article["evidence_level"] == "L0":
            tail = text[text.index(article["statement"]):][:400].lower()
            assert "aspirational" in tail, (
                f"{article['id']} is L0 but not rendered as aspirational"
            )
    for gap in KNOWN_GAPS:
        assert gap["id"] in text, f"{gap['id']} missing from CONSTITUTION.md"


def test_new_docs_keep_the_register():
    """The repo's claim register bans success words that outrun evidence
    (skills/adversarial-code-truth.md). This checks the tokens that are
    unambiguous in prose; 'complete' is only checked as a bare claim phrase
    because 'completed' is a legitimate status value."""
    banned = re.compile(r"\b(live-ready|revenue-ready|production-ready|ZK)\b|\bis complete\b")
    for name in ("CONSTITUTION.md", "ECOSYSTEM.md"):
        text = (REPO / name).read_text()
        match = banned.search(text)
        assert match is None, f"{name} contains banned bare claim: {match.group(0)!r}"


def test_constitution_version_is_declared():
    doc = build_constitution()
    assert doc["constitution_version"] == CONSTITUTION_VERSION
    import veritas

    assert doc["veritas_version"] == veritas.__version__
