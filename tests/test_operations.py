"""Standing up under real traffic: concurrency, limits, and honest failure.

Four audited defects motivate this file. All four are about the service being
unable to protect itself, and the first is the worst:

* O1 — every handler was `def`, so FastAPI ran all of them in one 40-slot
  threadpool. Forty slow retrievals meant `/health` stopped answering, so a
  load balancer would pull a node that was merely busy, and nothing bounded
  how many retrieval passes ran at once.
* O2 — `/v1/verify` accepted a body of any size and re-hashed it, and no
  endpoint had a rate limit. The unpaid surfaces (`/v1/trust`, `/v1/verify`)
  were free to hammer.
* O14 — an unhandled exception escaped as Starlette's plain-text 500, the one
  response on the whole surface that was not a registered error envelope. An
  agent branching on `body["error"]` crashed on it.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.setenv("VERITAS_RATE_LIMIT_PER_MINUTE", "0")  # off unless a test wants it
    import veritas.server as server
    importlib.reload(server)

    from veritas.pipeline import run_research as real
    monkeypatch.setattr(
        server, "run_research", lambda query, **kw: real(query, allow_network=False, **kw)
    )
    # This module is about how the service fails. TestClient re-raises server
    # exceptions by default, which would hide the very response an external
    # caller receives — the one thing under test here.
    return server, TestClient(server.app, raise_server_exceptions=False)


BODY = {"query": "What is the x402 payment protocol?"}


# -- O1: research cannot starve the rest of the surface ---------------------

def test_cheap_endpoints_do_not_share_the_research_threadpool(client):
    """The structural fix. A handler declared `async def` is served on the
    event loop; a `def` handler goes to the shared threadpool that retrieval
    saturates. Health and discovery must be the former."""
    import inspect

    server, _ = client
    for name in ("health", "readyz", "errors", "schema", "well_known",
                 "llms_txt", "constitution", "payment_config"):
        handler = getattr(server, name)
        assert inspect.iscoroutinefunction(handler), (
            f"{name} is sync and will queue behind retrieval in the threadpool"
        )


def test_research_is_capped_and_sheds_load_rather_than_queueing(client):
    """With every slot taken, a further request is refused immediately. The
    alternative — an unbounded queue — turns a slow dependency into a total
    outage while every buyer waits for a deadline they cannot see."""
    server, http = client
    acquired = [server.research_slots.acquire(blocking=False)
                for _ in range(server.MAX_CONCURRENT_RESEARCH)]
    assert all(acquired)
    try:
        response = http.post("/v1/research", json=BODY)
        assert response.status_code == 503
        assert response.json()["error"] == "service_overloaded"
        assert response.headers.get("Retry-After")
    finally:
        for _ in acquired:
            server.research_slots.release()


def test_health_still_answers_while_research_is_saturated(client):
    server, http = client
    held = [server.research_slots.acquire(blocking=False)
            for _ in range(server.MAX_CONCURRENT_RESEARCH)]
    try:
        assert http.get("/health").status_code == 200
    finally:
        for _ in held:
            server.research_slots.release()


def test_a_shed_request_does_no_work_and_claims_no_authorization(client):
    server, http = client
    calls = {"n": 0}
    real = server.run_research

    def counting(query, **kw):
        calls["n"] += 1
        return real(query, **kw)

    server.run_research = counting
    held = [server.research_slots.acquire(blocking=False)
            for _ in range(server.MAX_CONCURRENT_RESEARCH)]
    try:
        assert http.post("/v1/research", json=BODY).status_code == 503
        assert calls["n"] == 0
    finally:
        for _ in held:
            server.research_slots.release()


def test_slots_are_released_even_when_the_handler_raises(client):
    server, http = client

    def exploding(query, **kw):
        raise RuntimeError("boom")

    server.run_research = exploding
    http.post("/v1/research", json=BODY)

    # If the slot leaked, this acquire fails and the endpoint is wedged.
    got = [server.research_slots.acquire(blocking=False)
           for _ in range(server.MAX_CONCURRENT_RESEARCH)]
    for _ in [g for g in got if g]:
        server.research_slots.release()
    assert all(got), "a slot leaked; the endpoint would wedge after N failures"


# -- O2: bounded bodies and bounded callers ---------------------------------

def test_oversized_body_is_refused_without_being_read(client):
    _server, http = client
    payload = "x" * 300_000
    response = http.post("/v1/verify", json={"content": payload, "content_hash": "sha256:x"})
    assert response.status_code == 413
    assert response.json()["error"] == "request_too_large"


def test_verify_content_has_a_declared_maximum(client):
    """Belt and braces: the middleware bounds bytes on the wire, the model
    bounds the field, so a chunked upload with no Content-Length is still
    bounded."""
    from veritas.server import MAX_VERIFY_CONTENT_CHARS, VerifyRequest

    field = VerifyRequest.model_fields["content"]
    limits = [m for m in field.metadata if getattr(m, "max_length", None)]
    assert limits and limits[0].max_length == MAX_VERIFY_CONTENT_CHARS


def test_rate_limit_refuses_with_a_registered_code(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.setenv("VERITAS_RATE_LIMIT_PER_MINUTE", "3")
    import veritas.server as server
    importlib.reload(server)
    http = TestClient(server.app)

    codes = [http.get("/v1/trust").status_code for _ in range(5)]
    assert 429 in codes
    limited = next(r for r in (http.get("/v1/trust"),) if r.status_code == 429)
    assert limited.json()["error"] == "rate_limited"
    assert limited.headers.get("Retry-After")


def test_rate_limiting_is_off_when_configured_to_zero(client):
    _server, http = client
    assert all(http.get("/v1/trust").status_code == 200 for _ in range(20))


def test_liveness_is_never_rate_limited(tmp_path, monkeypatch):
    """A limiter that can starve the health check turns a busy node into a
    node the balancer believes is dead."""
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_RATE_LIMIT_PER_MINUTE", "1")
    import veritas.server as server
    importlib.reload(server)
    http = TestClient(server.app)
    assert all(http.get("/health").status_code == 200 for _ in range(10))


# -- O14: every failure is a registered envelope ----------------------------

def test_an_unhandled_exception_returns_the_registered_envelope(client):
    """Previously Starlette's plain-text 500 — the one response on the whole
    surface an agent could not parse."""
    server, http = client

    def exploding(query, **kw):
        raise RuntimeError("boom")

    server.run_research = exploding
    response = http.post("/v1/research", json=BODY)
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"] == "internal_error"


def test_the_internal_error_body_carries_no_exception_text(client):
    """The message names internals and reaches external callers."""
    server, http = client

    def exploding(query, **kw):
        raise RuntimeError("secret-internal-detail-/srv/veritas")

    server.run_research = exploding
    body = http.post("/v1/research", json=BODY).text
    assert "secret-internal-detail" not in body
    assert "/srv/veritas" not in body


def test_every_new_status_is_in_the_error_registry():
    from veritas.errors import ERROR_REGISTRY

    for code in ("service_overloaded", "request_too_large", "rate_limited",
                 "internal_error"):
        assert code in ERROR_REGISTRY, f"{code} is returned but not documented"


# -- readiness is not liveness ----------------------------------------------

def test_readiness_is_separate_from_liveness(client):
    """`/health` says the process is alive. `/readyz` says it can serve. A
    single endpoint conflating them makes a misconfigured node either
    silently broken or permanently restarted."""
    _server, http = client
    assert http.get("/health").json()["status"] == "ok"
    ready = http.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["ready"] is True


def test_a_misconfigured_service_is_alive_but_not_ready(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PAY_TO", "not-an-address")
    monkeypatch.setenv("VERITAS_RATE_LIMIT_PER_MINUTE", "0")
    import veritas.server as server
    importlib.reload(server)
    http = TestClient(server.app)

    assert http.get("/health").status_code == 200, "the process is alive"
    ready = http.get("/readyz")
    assert ready.status_code == 503
    assert ready.json()["ready"] is False
    assert ready.json()["reasons"]
