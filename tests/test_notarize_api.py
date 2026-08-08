"""POST /v1/notarize: same money path as research; billable false on unavailable."""

from __future__ import annotations

import base64
import importlib
import json

import pytest
from fastapi.testclient import TestClient

from veritas.facilitator import SettlementResult, VerificationResult
from veritas.hashing import compute_content_hash
from veritas.notary.extract import EXTRACT_VERSION
from veritas.notary.record import RETENTION_CLASS_STANDARD

NONCE = "0x" + "ab" * 32


def _header(nonce: str = NONCE) -> str:
    return base64.b64encode(json.dumps({
        "x402Version": 1,
        "scheme": "exact",
        "network": "eip155:84532",
        "payload": {
            "signature": "0x" + "cd" * 65,
            "authorization": {
                "from": "0x" + "1" * 40,
                "to": "0x" + "2" * 40,
                "value": "10000",
                "nonce": nonce,
            },
        },
    }).encode()).decode()


def _completed_observation(url: str, request_id: str | None = None) -> dict:
    body = "Stored evidence text for notarize API tests."
    content_hash = compute_content_hash(body)
    return {
        "request_id": request_id or "n0-req",
        "status": "completed",
        "url": url,
        "query": url,
        "claims": [],
        "evidence": [{
            "url": url,
            "title": None,
            "excerpt": body,
            "content_hash": content_hash,
            "provider": "notary",
            "provenance": "notary.observe",
            "observed": True,
        }],
        "evidence_record": {
            "url": url,
            "body": body,
            "content_hash": content_hash,
            "extract_version": EXTRACT_VERSION,
            "retention_class": RETENTION_CLASS_STANDARD,
            "media_kind": "text",
            "observed_at": "2026-08-08T00:00:00Z",
            "status_code": 200,
            "request_id": request_id,
        },
        "policy": {
            "license": {
                "id": "unknown",
                "reuse": "unknown",
                "assumed_permissive": False,
                "may_reuse": False,
            },
            "robots": {"allowance": "allowed", "may_fetch": True},
        },
        "support": {
            "n_evidence": 1,
            "independent_domains": 1,
            "domains": ["example.org"],
            "distinct_providers": 1,
            "verdict": "single_source",
            "agreement": "not_assessed",
            "method": "veritas.support.v1",
        },
        "custody_root": "sha256:" + "aa" * 32,
        "custody_valid": True,
        "custody_chain": [],
        "attests": "what this service received",
        "retrieval": {
            "providers_attempted": ["notary"],
            "providers_succeeded": ["notary"],
            "errors": [],
            "degraded": False,
            "unavailable": False,
        },
        "refusal_reason": None,
        "billable": True,
        "timestamp": "2026-08-08T00:00:00Z",
    }


def _unavailable_observation(url: str, request_id: str | None = None) -> dict:
    body = _completed_observation(url, request_id)
    body.update({
        "status": "unavailable",
        "billable": False,
        "refusal_reason": "fetch_unavailable",
        "evidence": [],
        "evidence_record": None,
        "support": {
            "n_evidence": 0,
            "independent_domains": 0,
            "domains": [],
            "distinct_providers": 0,
            "verdict": "unsupported",
            "agreement": "not_assessed",
            "method": "veritas.support.v1",
        },
        "retrieval": {
            "providers_attempted": ["notary"],
            "providers_succeeded": [],
            "errors": [{"provider": "notary", "error_type": "FetchError", "detail": "down"}],
            "degraded": True,
            "unavailable": True,
        },
    })
    return body


class _Control:
    def __init__(self):
        self.settle_result = SettlementResult(
            True, transaction="0xdeadbeef", network="eip155:84532", payer="0xbuyer",
        )
        self.work_calls = 0
        self.ledger = None
        self.owed_at_settle_time: list[str] = []

    def verify(self, payload, requirements):
        return VerificationResult(True, payer="0xbuyer")

    def settle(self, payload, requirements):
        self.owed_at_settle_time = [
            a.request_id for a in self.ledger.awaiting_settlement()
        ]
        return self.settle_result


@pytest.fixture
def free_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.delenv("VERITAS_PUBLIC_URL", raising=False)

    import veritas.server as server
    importlib.reload(server)

    def fake_observe(url, **kwargs):
        return _completed_observation(url, kwargs.get("request_id"))

    monkeypatch.setattr(server, "observe", fake_observe)
    return server, TestClient(server.app)


@pytest.fixture
def money_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://veritas.test")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "11" * 20)
    monkeypatch.setenv("VERITAS_NETWORK", "eip155:84532")
    monkeypatch.setenv("VERITAS_FACILITATOR", "https://facilitator.test")

    import veritas.server as server
    importlib.reload(server)

    control = _Control()
    control.ledger = server.ledger
    monkeypatch.setattr(server, "get_facilitator", lambda *a, **k: control)

    def counting_observe(url, **kwargs):
        control.work_calls += 1
        return _completed_observation(url, kwargs.get("request_id"))

    monkeypatch.setattr(server, "observe", counting_observe)
    return server, TestClient(server.app), control


def test_notarize_route_exists_and_returns_stored_body(free_client):
    _server, client = free_client
    r = client.post("/v1/notarize", json={"url": "https://example.org/page"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["billable"] is True
    record = body["evidence_record"]
    assert record["body"]
    assert record["retention_class"] == RETENTION_CLASS_STANDARD
    assert record["content_hash"] == compute_content_hash(record["body"])


def test_notarize_url_validation(free_client):
    _server, client = free_client
    assert client.post("/v1/notarize", json={"url": "x"}).status_code == 422
    assert client.post("/v1/notarize", json={}).status_code == 422


def test_live_mode_requires_payment_for_notarize(money_client):
    _server, client, control = money_client
    r = client.post("/v1/notarize", json={"url": "https://example.org/p"})
    assert r.status_code == 402
    assert control.work_calls == 0
    challenge = r.json()
    assert challenge.get("accepts") or "x402Version" in challenge


def test_paid_notarize_verify_claim_work_fsync_settle(money_client):
    server, client, control = money_client
    r = client.post(
        "/v1/notarize",
        json={"url": "https://example.org/paid"},
        headers={"X-PAYMENT": _header()},
    )
    assert r.status_code == 200
    assert control.work_calls == 1
    body = r.json()
    assert body["payment"]["settled"] is True
    assert body["evidence_record"]["body"]
    # Delivery must already be durable when settle runs (same money-path order).
    assert control.owed_at_settle_time, "settle saw no awaiting delivery"
    assert server.ledger.deliverable(body["request_id"]) is not None


def test_unavailable_notarize_is_not_settled(money_client, monkeypatch):
    server, client, control = money_client

    def fail_observe(url, **kwargs):
        control.work_calls += 1
        return _unavailable_observation(url, kwargs.get("request_id"))

    monkeypatch.setattr(server, "observe", fail_observe)
    r = client.post(
        "/v1/notarize",
        json={"url": "https://example.org/down"},
        headers={"X-PAYMENT": _header()},
    )
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "unavailable"
    assert body["billable"] is False
    assert body["payment"]["settled"] is False
    assert control.settle_result.success  # facilitator ready, but we must not call it
    # No settlement attempts for non-billable work.
    settlements = server.ledger.settlements(body["request_id"])
    assert settlements == [] or all(s.get("outcome") != "settled" for s in settlements)


def test_discovery_advertises_notarize_only_because_route_exists(free_client):
    _server, client = free_client
    # Route is real (not 404).
    assert client.post("/v1/notarize", json={"url": "https://example.org/x"}).status_code != 404

    well = client.get("/.well-known/x402").json()
    assert well["links"]["notarize"] == "/v1/notarize"
    # Self-traversing: GET on POST-only yields 405, never 404.
    assert client.get(well["links"]["notarize"]).status_code != 404

    llms = client.get("/llms.txt").text
    assert "/v1/notarize" in llms
    # Existing honesty: every listed path exists.
    paths = [
        line.strip()[2:].split(":", 1)[0].strip()
        for line in llms.splitlines()
        if line.strip().startswith("- /")
    ]
    assert "/v1/notarize" in paths
    for path in paths:
        if "{" in path:
            continue
        assert client.get(path).status_code != 404, path


def test_challenge_resource_names_notarize_path(money_client):
    _server, client, _control = money_client
    r = client.post("/v1/notarize", json={"url": "https://example.org/p"})
    assert r.status_code == 402
    body = r.json()
    accepts = body.get("accepts") or []
    assert accepts, body
    resource = accepts[0].get("resource") or ""
    assert resource.endswith("/v1/notarize")


def test_notarize_unexpected_failure_after_credit_debit_refunds(tmp_path, monkeypatch):
    """Invariant 3 on /v1/notarize: credits debit before observe, crash must reverse.

    Mirrors research's structural guard. Notarize reuses the same charge-publish
    / crash-refund shape; without it a raise after debit would bill for our failure.
    """
    eth_account = pytest.importorskip("eth_account")
    from eth_account.messages import encode_defunct

    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://veritas.test")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "11" * 20)
    monkeypatch.setenv("VERITAS_NETWORK", "eip155:84532")
    monkeypatch.setenv("VERITAS_PRICE", "$0.01")
    monkeypatch.setenv("VERITAS_FACILITATOR", "https://facilitator.test")

    import veritas.server as server
    importlib.reload(server)

    def explode(*args, **kwargs):
        raise RuntimeError("unexpected failure after notarize credit debit")

    monkeypatch.setattr(server, "observe", explode)

    client = TestClient(server.app)
    acct = eth_account.Account.create()
    ch = client.post("/v1/siwx/challenge", json={"address": acct.address})
    assert ch.status_code == 200, ch.text
    body = ch.json()
    signed = acct.sign_message(encode_defunct(text=body["message"]))
    sig = signed.signature.hex()
    if not sig.startswith("0x"):
        sig = "0x" + sig
    ver = client.post(
        "/v1/siwx/verify",
        json={"message": body["message"], "signature": sig},
    )
    assert ver.status_code == 200, ver.text
    token = ver.json()["session_token"]
    server.credit_ledger.grant(acct.address, 10_000, note="test_fund")

    with pytest.raises(RuntimeError):
        client.post(
            "/v1/notarize",
            json={"url": "https://example.org/crash"},
            headers={"X-VERITAS-SESSION": token},
        )

    assert server.credit_ledger.balance(acct.address) == 10_000
    kinds = [e.kind for e in server.credit_ledger.entries(acct.address)]
    assert "debit" in kinds and "refund" in kinds, kinds
