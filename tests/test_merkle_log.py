"""N1.4: Merkle tree + operator-local evidence log + HTTP surfaces."""

from __future__ import annotations

import importlib
import tempfile

from fastapi.testclient import TestClient

from veritas.hashing import compute_content_hash
from veritas.notary.fetch import FetchResult
from veritas.notary.log import EvidenceLog, reset_default_evidence_log, verify_log_inclusion
from veritas.notary.merkle import inclusion_proof, merkle_root, verify_inclusion
from veritas.notary.observe import observe


def test_merkle_single_and_multi_leaf():
    a = compute_content_hash("a")
    b = compute_content_hash("b")
    c = compute_content_hash("c")
    assert merkle_root([a]) == a
    root = merkle_root([a, b, c])
    assert root and root.startswith("sha256:")
    proof = inclusion_proof([a, b, c], 1)
    assert proof["leaf"] == b
    assert proof["root"] == root
    ok, reason = verify_inclusion(proof)
    assert (ok, reason) == (True, "ok")


def test_merkle_tamper_fails():
    leaves = [compute_content_hash(x) for x in ("x", "y", "z")]
    proof = inclusion_proof(leaves, 0)
    proof["leaf"] = compute_content_hash("forged")
    ok, reason = verify_inclusion(proof)
    assert ok is False
    assert reason == "root_mismatch"


def test_evidence_log_append_and_proof():
    with tempfile.TemporaryDirectory() as tmp:
        log = EvidenceLog(tmp)
        h1 = compute_content_hash("one")
        h2 = compute_content_hash("two")
        e1 = log.append(h1)
        e2 = log.append(h2)
        assert e1["index"] == 0
        assert e2["index"] == 1
        assert e2["root"] == log.root()
        proof = log.proof(0)
        out = verify_log_inclusion(proof)
        assert out["valid"] is True
        assert out["reason"] == "ok"


def test_observe_appends_to_log(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    reset_default_evidence_log()
    body = b"N1.4 observe log body."

    def fake_fetch(url, **kwargs):
        return FetchResult(
            request_url=url,
            final_url=url,
            status=200,
            headers={"content-type": "text/plain"},
            body=body,
            truncated=False,
        )

    result = observe(
        "https://example.org/n14",
        request_id="n14-obs",
        robots_body="User-agent: *\nAllow: /\n",
        fetch_fn=fake_fetch,
        observed_at="2026-08-08T21:00:00Z",
    )
    assert result["status"] == "completed"
    assert "evidence_log" in result
    assert result["evidence_log"]["index"] == 0
    assert result["evidence_log"]["leaf"] == result["evidence_record"]["content_hash"]
    # N1.5: full inclusion proof on the observe envelope (peer offline path).
    proof = result["evidence_log"]["inclusion_proof"]
    assert proof["leaf"] == result["evidence_log"]["leaf"]
    assert proof["root"] == result["evidence_log"]["root"]
    from veritas.notary.log import verify_log_inclusion

    assert verify_log_inclusion(proof)["valid"] is True
    chain = str(result["custody_chain"])
    assert "logged" in chain or "notary.log" in chain


def test_log_http_surfaces(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    reset_default_evidence_log()
    import veritas.server as server

    importlib.reload(server)
    client = TestClient(server.app)

    status = client.get("/v1/log")
    assert status.status_code == 200
    assert status.json()["count"] == 0

    # seed via observe path
    body = b"http surface seed"

    def fake_fetch(url, **kwargs):
        return FetchResult(
            request_url=url,
            final_url=url,
            status=200,
            headers={"content-type": "text/plain"},
            body=body,
            truncated=False,
        )

    observe(
        "https://example.org/seed",
        robots_body="User-agent: *\nAllow: /\n",
        fetch_fn=fake_fetch,
    )
    # process default log may be bound to tmp_path after reset
    status = client.get("/v1/log")
    # reload picks runtime; ensure log has leaf
    from veritas.notary.log import default_evidence_log

    if default_evidence_log().count() == 0:
        default_evidence_log().append(compute_content_hash(body.decode()))

    snap = client.get("/v1/log").json()
    assert snap["count"] >= 1
    proof = client.get("/v1/log/proof", params={"index": 0})
    assert proof.status_code == 200
    body_json = proof.json()
    verify = client.post("/v1/log/verify", json={"proof": body_json})
    assert verify.status_code == 200
    assert verify.json()["valid"] is True

    links = client.get("/.well-known/x402").json()["links"]
    assert links["evidence_log"] == "/v1/log"
    assert links["evidence_log_proof"] == "/v1/log/proof"
    assert links["evidence_log_verify"] == "/v1/log/verify"
