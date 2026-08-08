"""N1.2: free POST /v1/attestations/verify for EIP-191 EvidenceRecord checks."""

from __future__ import annotations

import importlib

import pytest
from eth_account import Account
from fastapi.testclient import TestClient

from veritas.hashing import compute_content_hash
from veritas.notary.sign import OperatorSigner, sign_evidence_record

pytest.importorskip("eth_account")


def _record(**overrides):
    body = "Body for attestation verify API tests."
    base = {
        "url": "https://example.org/attested",
        "observed_at": "2026-08-08T16:00:00Z",
        "content_hash": compute_content_hash(body),
        "body": body,
        "extract_version": "extract.v1",
        "media_kind": "text",
        "retention_class": "standard",
        "request_id": "req-n12-api",
    }
    base.update(overrides)
    return base


@pytest.fixture
def account():
    return Account.create()


@pytest.fixture
def signer(account):
    return OperatorSigner("0x" + bytes(account.key).hex())


@pytest.fixture
def free_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.delenv("VERITAS_PUBLIC_URL", raising=False)
    import veritas.server as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_verify_attestation_valid_round_trip(free_client, signer, account):
    record = _record()
    attestation = sign_evidence_record(record, signer)
    r = free_client.post(
        "/v1/attestations/verify",
        json={
            "evidence_record": record,
            "attestation": attestation,
            "expected_signer": account.address,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["reason"] == "ok"
    assert body["scheme"] == "eip191"
    assert "on-chain" in body["note"].lower() or "not an on-chain" in body["note"]
    assert bytes(account.key).hex() not in r.text


def test_verify_attestation_rejects_tamper(free_client, signer):
    record = _record()
    attestation = sign_evidence_record(record, signer)
    tampered = dict(record, content_hash="sha256:" + "00" * 32)
    r = free_client.post(
        "/v1/attestations/verify",
        json={"evidence_record": tampered, "attestation": attestation},
    )
    assert r.status_code == 200
    assert r.json()["valid"] is False
    assert r.json()["reason"] != "ok"


def test_verify_attestation_wrong_expected_signer(free_client, signer):
    record = _record()
    attestation = sign_evidence_record(record, signer)
    r = free_client.post(
        "/v1/attestations/verify",
        json={
            "evidence_record": record,
            "attestation": attestation,
            "expected_signer": "0x" + "11" * 20,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert body["reason"] == "unexpected_signer"


def test_verify_attestation_is_free_even_in_live_mode(tmp_path, monkeypatch, signer, account):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "ab" * 20)
    monkeypatch.setenv("VERITAS_NETWORK", "eip155:84532")
    monkeypatch.setenv("VERITAS_PRICE", "$0.01")
    monkeypatch.setenv("VERITAS_FACILITATOR_URL", "https://facilitator.example")
    import veritas.server as main_module

    importlib.reload(main_module)
    client = TestClient(main_module.app)
    record = _record()
    attestation = sign_evidence_record(record, signer)
    r = client.post(
        "/v1/attestations/verify",
        json={
            "evidence_record": record,
            "attestation": attestation,
            "expected_signer": account.address,
        },
    )
    assert r.status_code == 200
    assert r.json()["valid"] is True


def test_discovery_advertises_attestations_verify(free_client):
    links = free_client.get("/.well-known/x402").json()["links"]
    assert links["attestations_verify"] == "/v1/attestations/verify"
    # POST-only: GET may be 405; must not be 404.
    assert free_client.get("/v1/attestations/verify").status_code != 404


def test_identity_lists_attestation_capability(free_client):
    body = free_client.get("/v1/identity").json()
    assert "evidence-record-attestation-verify" in body["capabilities"]
    assert body["endpoints"]["attestations_verify"].endswith(
        "/v1/attestations/verify"
    )


def test_mcp_tool_verify_attestation(signer, account):
    from veritas.mcp_server import tool_verify_attestation

    record = _record()
    attestation = sign_evidence_record(record, signer)
    out = tool_verify_attestation(
        record, attestation, expected_signer=account.address
    )
    assert out["valid"] is True
    assert out["reason"] == "ok"
