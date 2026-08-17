"""Seeing the service: structured logs and counters.

Defect O9 — no logging, metrics, tracing or alerting anywhere. The previous
commit made the service shed load under pressure; without this one it sheds
load silently, and an operator learns about it from a buyer complaint.

Two constraints shape what is here, and both are about what must NOT appear:

* **Buyer queries never reach a log line.** A query is the buyer's business,
  it is already retained in a receipt they can have erased, and a log file is
  the one place that erasure would not reach.
* **Metrics are not public.** Settlement counters are revenue figures. The
  endpoint exists only when a token is configured and requires it, rather than
  publishing a competitor's view of the business by default.
"""

from __future__ import annotations

import importlib
import json
import logging

import pytest
from fastapi.testclient import TestClient

BODY = {"query": "unique-sentinel-query-text-x402"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.setenv("VERITAS_RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setenv("VERITAS_METRICS_TOKEN", "operator-token")
    import veritas.server as server
    importlib.reload(server)

    monkeypatch.setattr(
        server,
        "pull_signals",
        lambda query, **kw: [
            {
                "venue": "polymarket",
                "market_id": "m-obs",
                "question": query,
                "outcomes": [{"name": "Yes", "price": 0.5}],
                "observed_at": "2026-08-17T00:00:00Z",
                "source_url": "https://gamma-api.polymarket.com/markets/m-obs",
                "method": "veritas.signals.v1",
                "note": "market-implied prices, not a verdict",
            }
        ],
    )
    return server, TestClient(server.app, raise_server_exceptions=False)


AUTH = {"Authorization": "Bearer operator-token"}


def _metrics(http) -> str:
    response = http.get("/metrics", headers=AUTH)
    assert response.status_code == 200, response.text
    return response.text


# -- counters ---------------------------------------------------------------


def test_metrics_are_exposed_in_prometheus_text_format(client):
    _server, http = client
    body = _metrics(http)
    assert "# HELP veritas_requests_total" in body
    assert "# TYPE veritas_requests_total counter" in body


def test_requests_are_counted_by_status(client):
    _server, http = client
    http.post("/v1/signals", json=BODY)
    body = _metrics(http)
    assert 'veritas_requests_total{path="/v1/signals",status="200"} 1' in body


def test_shed_requests_are_counted(client):
    """The point of the whole file: load shedding that nobody can see is
    indistinguishable from an outage."""
    server, http = client
    held = [server.research_slots.acquire(blocking=False)
            for _ in range(server.MAX_CONCURRENT_RESEARCH)]
    try:
        http.post("/v1/signals", json=BODY)
    finally:
        for _ in held:
            server.research_slots.release()
    assert "veritas_research_shed_total 1" in _metrics(http)


def test_rate_limited_requests_are_counted(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("VERITAS_METRICS_TOKEN", "operator-token")
    import veritas.server as server
    importlib.reload(server)
    http = TestClient(server.app)

    for _ in range(5):
        http.get("/v1/trust")
    body = http.get("/metrics", headers=AUTH).text
    assert "veritas_rate_limited_total" in body


# -- metrics are not public -------------------------------------------------


def test_metrics_are_absent_when_no_token_is_configured(tmp_path, monkeypatch):
    """Safe by default: settlement counters are revenue figures, so the
    endpoint does not exist until an operator turns it on."""
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_METRICS_TOKEN", raising=False)
    import veritas.server as server
    importlib.reload(server)
    http = TestClient(server.app)
    assert http.get("/metrics").status_code == 404


def test_metrics_reject_a_wrong_token(client):
    _server, http = client
    assert http.get("/metrics").status_code == 401
    assert http.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_metrics_are_not_advertised_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_METRICS_TOKEN", raising=False)
    import veritas.server as server
    importlib.reload(server)
    http = TestClient(server.app)
    assert "metrics" not in http.get("/.well-known/x402").json()["links"]


# -- logs -------------------------------------------------------------------


def test_request_logs_are_one_json_object_per_line(client, caplog):
    from veritas.observability import ACCESS_LOGGER, format_record

    _server, http = client
    with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
        http.post("/v1/signals", json=BODY)

    lines = [format_record(r) for r in caplog.records if r.name == ACCESS_LOGGER]
    assert lines
    entry = json.loads(lines[0])
    assert entry["path"] == "/v1/signals"
    assert entry["status"] == 200
    assert isinstance(entry["duration_ms"], int)


def test_the_buyer_query_never_reaches_a_log_line(client, caplog):
    """A query is the buyer's business and is already erasable from receipts;
    a log file is the one place that erasure would not reach."""
    from veritas.observability import ACCESS_LOGGER, format_record

    _server, http = client
    with caplog.at_level(logging.DEBUG):
        http.post("/v1/signals", json=BODY)

    logged = "\n".join(
        format_record(r) if r.name == ACCESS_LOGGER else r.getMessage()
        for r in caplog.records
    )
    assert "unique-sentinel-query-text-x402" not in logged


def test_the_payment_header_never_reaches_a_log_line(client, caplog):
    from veritas.observability import ACCESS_LOGGER, format_record

    _server, http = client
    secret = "c2VjcmV0LXBheW1lbnQtaGVhZGVy"
    with caplog.at_level(logging.DEBUG):
        http.post("/v1/signals", json=BODY, headers={"X-PAYMENT": secret})

    logged = "\n".join(
        format_record(r) if r.name == ACCESS_LOGGER else r.getMessage()
        for r in caplog.records
    )
    assert secret not in logged


def test_the_formatter_emits_parseable_json_for_a_plain_message():
    from veritas.observability import JsonFormatter

    record = logging.LogRecord(
        "veritas", logging.WARNING, __file__, 1, "something happened", None, None,
    )
    entry = json.loads(JsonFormatter().format(record))
    assert entry["level"] == "WARNING"
    assert entry["message"] == "something happened"
    assert entry["logger"] == "veritas"


def test_counters_are_safe_to_increment_from_many_threads():
    """Handlers run in a threadpool; a counter that loses increments under
    concurrency reports a number that is quietly wrong."""
    import threading

    from veritas.observability import Metrics

    metrics = Metrics()

    def bump():
        for _ in range(500):
            metrics.increment("veritas_requests_total", {"path": "/x", "status": "200"})

    threads = [threading.Thread(target=bump) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert metrics.value("veritas_requests_total", {"path": "/x", "status": "200"}) == 2000


def test_label_values_are_escaped_so_a_path_cannot_forge_a_metric_line():
    """Prometheus text is line-oriented. An unescaped label value containing a
    quote or newline would let a caller inject fabricated metric lines."""
    from veritas.observability import Metrics

    metrics = Metrics()
    metrics.increment("veritas_requests_total", {"path": '/x"\n_forged 99', "status": "200"})
    rendered = metrics.render()
    assert "\n_forged 99" not in rendered
    assert rendered.count("veritas_requests_total{") == 1
