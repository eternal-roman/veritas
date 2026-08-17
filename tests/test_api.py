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
    assert body["store_mode"] in {"unset", "sqlite", "postgres", "unavailable"}


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
    ok = free_client.post("/v1/verify", json={"content": text, "content_hash": h}).json()
    assert ok["valid"]
    assert ok.get("binding") == "caller_supplied"
    bad = free_client.post(
        "/v1/verify", json={"content": text + "!", "content_hash": h}
    ).json()
    assert not bad["valid"]


def test_missing_payment_returns_spec_shaped_402(paid_client):
    r = paid_client.post("/v1/signals", json={"query": "What is x402?"})
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
        "/v1/signals", json={"query": "What is x402?"}, headers={"X-PAYMENT": "hello"}
    )
    assert r.status_code == 402
    assert r.json()["accepts"]


def test_unreachable_facilitator_fails_closed(paid_client):
    """A well-formed payload must still be denied when the verifier is down.

    It carries a real nonce because structurally inadmissible payloads are now
    refused before the facilitator is called at all (dogfood cycle 3), and the
    behaviour under test here is the outage path, not that one.
    """
    payload = base64.b64encode(json.dumps({
        "scheme": "exact", "network": "eip155:8453", "payer": "0xabc",
        "payload": {"signature": "0x" + "cd" * 65,
                    "authorization": {"nonce": "0x" + "ab" * 32}},
    }).encode()).decode()
    r = paid_client.post(
        "/v1/signals", json={"query": "What is x402?"}, headers={"X-PAYMENT": payload}
    )
    assert r.status_code == 503
    assert r.json()["error"] == "payment_verification_unavailable"


def test_query_validation_rejects_empty(free_client):
    assert free_client.post("/v1/signals", json={"query": ""}).status_code == 422


def test_receipt_missing_returns_404(free_client):
    r = free_client.get("/v1/receipts/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"] == "receipt_not_found"


def test_public_receipt_does_not_serve_a_research_question(free_client):
    """L6: GET /v1/receipts is unauthenticated. A free-text question stays off
    the wire; a hash still binds the receipt to what was asked."""
    import veritas.server as main_module
    from veritas.hashing import compute_content_hash

    question = "buyer-only research question about a merger"
    record = main_module.store.save({
        "request_id": "req-l6-question",
        "query": question,
        "status": "completed",
        "custody_root": "sha256:x",
        "custody_valid": True,
        "evidence": [],
    })
    assert record["persisted"] is True
    assert "query" not in record
    assert record["query_hash"] == compute_content_hash(question)

    body = free_client.get("/v1/receipts/req-l6-question").json()
    assert question not in json.dumps(body)
    assert "query" not in body
    assert body["query_hash"] == compute_content_hash(question)
    assert body.get("query_redacted") is not True

    # Legacy on-disk receipts that still carry a question are redacted on GET.
    main_module.store.save({
        "request_id": "req-l6-legacy",
        "query": question,
        "status": "completed",
        "custody_root": "sha256:x",
        "custody_valid": True,
        "evidence": [],
    })
    path = main_module.store.base_dir / "req-l6-legacy.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["query"] = question
    path.write_text(json.dumps(raw), encoding="utf-8")
    leaked = free_client.get("/v1/receipts/req-l6-legacy").json()
    assert "query" not in leaked
    assert leaked["query_redacted"] is True
    assert question not in json.dumps(leaked)


def test_public_receipt_keeps_an_origin_url_for_refetch(free_client):
    import veritas.server as main_module

    url = "https://example.com/observed"
    record = main_module.store.save({
        "request_id": "req-l6-url",
        "query": url,
        "status": "completed",
        "custody_root": "sha256:x",
        "custody_valid": True,
        "evidence": [],
    })
    assert record["query"] == url
    body = free_client.get("/v1/receipts/req-l6-url").json()
    assert body["query"] == url


def test_receipt_pruned_returns_410_gone_not_404(free_client, tmp_path):
    """O.6: known-but-pruned is 410 receipt_gone; never-seen stays 404.

    Distinct envelopes so a buyer can trust the receipt endpoint after
    retention has run — collapsing both to 404 makes audit impossible.
    """
    import json
    from datetime import datetime, timezone

    import veritas.server as main_module

    store = main_module.store
    record = store.save({
        "request_id": "req-kept-then-pruned",
        "query": "q",
        "status": "completed",
        "custody_root": "sha256:x",
        "custody_valid": True,
        "evidence": [],
    })
    assert record["persisted"] is True
    assert free_client.get("/v1/receipts/req-kept-then-pruned").status_code == 200

    path = store.base_dir / "req-kept-then-pruned.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    body["stored_at"] = "2020-01-01T00:00:00Z"
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    store.prune(datetime(2024, 1, 1, tzinfo=timezone.utc))

    gone = free_client.get("/v1/receipts/req-kept-then-pruned")
    assert gone.status_code == 410
    assert gone.json()["error"] == "receipt_gone"
    assert gone.json()["request_id"] == "req-kept-then-pruned"

    missing = free_client.get("/v1/receipts/never-existed-at-all")
    assert missing.status_code == 404
    assert missing.json()["error"] == "receipt_not_found"
    # Envelopes must stay distinct — same status family is not enough.
    assert gone.json()["error"] != missing.json()["error"]


def test_schema_endpoint_describes_catalog_and_errors(free_client):
    """/v1/schema is the catalog + error contract, not a research body."""
    body = free_client.get("/v1/schema").json()
    catalog = body.get("catalog") or body.get("response")
    assert "signals" in str(catalog).lower() or "properties" in catalog
    envelope = body["error_envelope"]
    assert envelope["required"] == ["error"]
