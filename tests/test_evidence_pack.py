"""N1.3: portable EvidencePack build + verify (agent-to-agent handoff)."""

from __future__ import annotations

import importlib

import pytest
from eth_account import Account
from fastapi.testclient import TestClient

from veritas.hashing import compute_content_hash
from veritas.notary.pack import (
    PACK_VERSION,
    build_evidence_pack,
    pack_from_observation,
    verify_evidence_pack,
)
from veritas.notary.sign import OperatorSigner, sign_evidence_record

pytest.importorskip("eth_account")


def _fields(**overrides):
    body = "Portable pack body for N1.3."
    base = {
        "url": "https://example.org/pack",
        "content_hash": compute_content_hash(body),
        "observed_at": "2026-08-08T18:00:00Z",
        "extract_version": "extract.v1",
        "request_id": "req-n13-1",
        "custody_root": "sha256:" + "ab" * 32,
        "body": body,
    }
    base.update(overrides)
    return base


@pytest.fixture
def free_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    import veritas.server as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_build_and_verify_round_trip():
    f = _fields()
    pack = build_evidence_pack(
        url=f["url"],
        content_hash=f["content_hash"],
        observed_at=f["observed_at"],
        extract_version=f["extract_version"],
        request_id=f["request_id"],
        custody_root=f["custody_root"],
        body=f["body"],
    )
    assert pack["pack_version"] == PACK_VERSION
    assert pack["pack_hash"].startswith("sha256:")
    out = verify_evidence_pack(pack)
    assert out["valid"] is True
    assert out["reason"] == "ok"


def test_tampered_pack_hash_fails():
    f = _fields()
    pack = build_evidence_pack(
        url=f["url"],
        content_hash=f["content_hash"],
        observed_at=f["observed_at"],
        extract_version=f["extract_version"],
        request_id=f["request_id"],
    )
    pack["url"] = "https://evil.example/forged"
    out = verify_evidence_pack(pack)
    assert out["valid"] is False
    assert out["reason"] == "pack_hash_mismatch"


def test_pack_with_attestation():
    account = Account.create()
    signer = OperatorSigner("0x" + bytes(account.key).hex())
    f = _fields()
    record = {
        "url": f["url"],
        "content_hash": f["content_hash"],
        "observed_at": f["observed_at"],
        "extract_version": f["extract_version"],
        "request_id": f["request_id"],
    }
    attestation = sign_evidence_record(record, signer)
    pack = build_evidence_pack(
        url=f["url"],
        content_hash=f["content_hash"],
        observed_at=f["observed_at"],
        extract_version=f["extract_version"],
        request_id=f["request_id"],
        attestation=attestation,
    )
    out = verify_evidence_pack(pack)
    assert out["valid"] is True
    assert out["attestation_ok"] is True
    assert bytes(account.key).hex() not in str(pack)


def test_pack_from_observation_completed():
    body = "From observe envelope."
    h = compute_content_hash(body)
    observation = {
        "status": "completed",
        "request_id": "obs-1",
        "url": "https://example.org/o",
        "custody_root": "sha256:" + "cd" * 32,
        "evidence_record": {
            "url": "https://example.org/o",
            "content_hash": h,
            "observed_at": "2026-08-08T19:00:00Z",
            "extract_version": "extract.v1",
            "request_id": "obs-1",
            "body": body,
        },
    }
    pack = pack_from_observation(observation)
    assert verify_evidence_pack(pack)["valid"] is True


def test_verify_pack_endpoint(free_client):
    f = _fields()
    pack = build_evidence_pack(
        url=f["url"],
        content_hash=f["content_hash"],
        observed_at=f["observed_at"],
        extract_version=f["extract_version"],
        request_id=f["request_id"],
        body=f["body"],
    )
    r = free_client.post("/v1/packs/verify", json={"pack": pack})
    assert r.status_code == 200
    assert r.json()["valid"] is True
    assert r.json()["reason"] == "ok"


def test_discovery_advertises_packs_verify(free_client):
    links = free_client.get("/.well-known/x402").json()["links"]
    assert links["packs_verify"] == "/v1/packs/verify"
    assert free_client.get("/v1/packs/verify").status_code != 404


def test_identity_lists_pack_capability(free_client):
    body = free_client.get("/v1/identity").json()
    assert "portable-evidence-pack" in body["capabilities"]
    assert body["endpoints"]["packs_verify"].endswith("/v1/packs/verify")


def test_mcp_tool_verify_pack():
    from veritas.mcp_server import tool_verify_pack

    f = _fields()
    pack = build_evidence_pack(
        url=f["url"],
        content_hash=f["content_hash"],
        observed_at=f["observed_at"],
        extract_version=f["extract_version"],
        request_id=f["request_id"],
    )
    assert tool_verify_pack(pack)["valid"] is True
