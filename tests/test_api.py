"""HTTP surface: discovery, payment gating, verification, receipts."""

import base64
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def free_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    import importlib

    import veritas.server as main_module
    importlib.reload(main_module)
    return TestClient(main_module.app)


@pytest.fixture
def paid_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://veritas.test")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "1" * 40)
    # Unroutable facilitator so verification cannot succeed.
    monkeypatch.setenv("VERITAS_FACILITATOR", "http://127.0.0.1:1")
    import importlib

    import veritas.server as main_module
    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_health(free_client):
    body = free_client.get("/health").json()
    assert body["status"] == "ok"
    assert body["payment_mode"] == "free"


def test_trust_is_unproven_without_data(free_client):
    """A self-graded score is worse than none; the old endpoint always
    returned 90/RECOMMENDED regardless of behaviour."""
    body = free_client.get("/v1/trust").json()
    assert body["recommendation"] == "UNPROVEN"
    assert body["overall"] is None


def test_identity_hash_is_stable(free_client):
    """The old identity hashed a timestamp into its own body, so the hash
    changed every call and could not detect tampering."""
    first = free_client.get("/v1/identity").json()
    second = free_client.get("/v1/identity").json()
    assert first["content_hash"] == second["content_hash"]


def test_verify_endpoint_checks_hashes(free_client):
    from veritas.hashing import compute_content_hash

    text = "some evidence text"
    h = compute_content_hash(text)
    assert free_client.post("/v1/verify", json={"content": text, "content_hash": h}).json()["valid"]
    assert not free_client.post(
        "/v1/verify", json={"content": text + "!", "content_hash": h}
    ).json()["valid"]


def test_missing_payment_returns_spec_shaped_402(paid_client):
    r = paid_client.post("/v1/research", json={"query": "What is x402?"})
    assert r.status_code == 402
    body = r.json()
    assert body["x402Version"] == 1
    accepts = body["accepts"][0]
    # $0.01 at USDC's 6 decimals. The default was $0.25 (25x comparable
    # x402 endpoints) until the repricing in Phase T.
    assert accepts["maxAmountRequired"] == "10000"
    assert accepts["scheme"] == "exact"


def test_junk_payment_header_is_rejected(paid_client):
    """Previously any non-empty X-PAYMENT value bought full access."""
    r = paid_client.post(
        "/v1/research", json={"query": "What is x402?"}, headers={"X-PAYMENT": "hello"}
    )
    assert r.status_code == 402
    assert r.json()["accepts"]


def test_unreachable_facilitator_fails_closed(paid_client):
    """A well-formed payload must still be denied when the verifier is down."""
    payload = base64.b64encode(
        json.dumps({"scheme": "exact", "network": "eip155:8453", "payer": "0xabc"}).encode()
    ).decode()
    r = paid_client.post(
        "/v1/research", json={"query": "What is x402?"}, headers={"X-PAYMENT": payload}
    )
    assert r.status_code == 503
    assert r.json()["error"] == "payment_verification_unavailable"


def test_query_validation_rejects_empty(free_client):
    assert free_client.post("/v1/research", json={"query": "x"}).status_code == 422


def test_receipt_missing_returns_404(free_client):
    assert free_client.get("/v1/receipts/does-not-exist").status_code == 404


def test_schema_endpoint_matches_real_pipeline_output(free_client):
    """/v1/schema is generated from the same constants validate_response
    enforces, so a non-Python agent gets the contract without reading source
    — and it must describe what the pipeline actually emits."""
    from veritas.pipeline import run_research
    from veritas.schema import REQUIRED_FIELDS, RefusalReason, Status

    body = free_client.get("/v1/schema").json()
    response_schema = body["response"]
    assert set(response_schema["required"]) == set(REQUIRED_FIELDS)
    assert set(response_schema["properties"]["status"]["enum"]) == {s.value for s in Status}
    reasons = set(response_schema["properties"]["refusal_reason"]["enum"])
    assert {r.value for r in RefusalReason} <= reasons

    result = run_research("What is x402?", allow_network=False)
    for key in response_schema["required"]:
        assert key in result, f"schema requires {key} but pipeline does not emit it"

    envelope = body["error_envelope"]
    assert envelope["required"] == ["error"]
