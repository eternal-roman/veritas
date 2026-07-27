"""The unified error contract: one envelope, registered codes, no surprises.

Before this module existed the API spoke three shapes: `{"error": code}`
bodies, x402-spec 402 challenges whose `error` is free text, and a 503
retrieval-unavailable path that returned the research body with no `error`
key at all. An agent branching on `body["error"]` crashed on the most common
failure. These tests pin the envelope and the registry that documents it.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from veritas.errors import ERROR_REGISTRY, ErrorCode, error_envelope


@pytest.fixture
def free_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    import veritas.server as main_module
    importlib.reload(main_module)
    return TestClient(main_module.app)


@pytest.fixture
def paid_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "1" * 40)
    monkeypatch.setenv("VERITAS_FACILITATOR", "http://127.0.0.1:1")
    import veritas.server as main_module
    importlib.reload(main_module)
    return TestClient(main_module.app)


@pytest.fixture
def misconfigured_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PAY_TO", "not-an-address")
    import veritas.server as main_module
    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_every_registered_code_has_status_and_retriability():
    assert set(ERROR_REGISTRY) == {c.value for c in ErrorCode}
    for code, entry in ERROR_REGISTRY.items():
        assert isinstance(entry["status"], int) and 400 <= entry["status"] < 600, code
        assert entry["meaning"], code
        assert isinstance(entry["retriable"], bool), code


def test_error_envelope_shape_is_stable():
    body = error_envelope(ErrorCode.RECEIPT_NOT_FOUND, detail="nope", request_id="r1")
    assert body["error"] == "receipt_not_found"
    assert body["detail"] == "nope"
    assert body["request_id"] == "r1"


def test_422_returns_registered_envelope(free_client):
    r = free_client.post("/v1/research", json={"query": "x"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "invalid_request"
    assert body["detail"]


def test_misconfigured_503_uses_registry_code(misconfigured_client):
    r = misconfigured_client.post("/v1/research", json={"query": "What is x402?"})
    assert r.status_code == 503
    assert r.json()["error"] == "payment_misconfigured"


def test_unavailable_503_carries_error_code_and_full_body(free_client, monkeypatch):
    """The one shape that previously had no `error` key at all. The full
    research body stays (buyers need the unavailability report); the code is
    additive."""
    from veritas.pipeline import run_research as real_run

    class _Raising:
        name = "raising"

        def retrieve(self, query, max_results):
            raise ConnectionError("provider down")

    import veritas.server as main_module

    monkeypatch.setattr(
        main_module, "run_research",
        lambda query, max_results=5: real_run(query, retriever=_Raising()),
    )
    r = free_client.post("/v1/research", json={"query": "What is x402?"})
    assert r.status_code == 503
    body = r.json()
    assert body["error"] == "retrieval_unavailable"
    assert body["status"] == "unavailable"
    assert body["billable"] is False
    assert body["payment"]["settled"] is False


def test_402_body_stays_x402_spec_shaped_and_sets_payment_required_header(paid_client):
    """The 402 envelope belongs to the x402 spec, not to our registry — but
    the response now carries the Payment-Required header the repo's own
    settlement harness reads."""
    r = paid_client.post("/v1/research", json={"query": "What is x402?"})
    assert r.status_code == 402
    assert r.headers.get("Payment-Required") == "x402"
    body = r.json()
    assert body["x402Version"] == 1
    assert body["accepts"]


def test_errors_endpoint_serves_registry(free_client):
    body = free_client.get("/v1/errors").json()
    assert body["errors"] == ERROR_REGISTRY
    assert "402" in body["exceptions"]["payment_challenge"]
