"""Human operator viewer + loopback enroll."""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from veritas.operator_ui import is_loopback_client


@pytest.fixture
def free_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("VERITAS_AGENT_HOME", str(tmp_path / "agent"))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.delenv("VERITAS_PUBLIC_URL", raising=False)
    import veritas.server as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def _request(host: str) -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": (host, 1234),
            "server": ("127.0.0.1", 80),
        }
    )


def test_loopback_hosts():
    assert is_loopback_client(_request("127.0.0.1"))
    assert is_loopback_client(_request("::1"))
    assert is_loopback_client(_request("testclient"))
    assert is_loopback_client(_request("127.4.5.6"))
    assert not is_loopback_client(_request("8.8.8.8"))
    assert not is_loopback_client(_request("10.0.0.2"))


def test_ui_is_html_and_excluded(free_client):
    r = free_client.get("/ui")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "VERITAS" in r.text
    assert "/v1/operator" in r.text
    assert "/v1/operator/enroll" in r.text
    from veritas.hooks import EXCLUDED_ROUTE_PATHS, http_paths

    assert "/ui" in EXCLUDED_ROUTE_PATHS
    assert "/ui" not in http_paths()


def test_operator_snapshot_has_account(free_client):
    unenrolled = free_client.get("/v1/operator").json()
    assert unenrolled["account"]["enrolled"] is False
    assert "visa" not in unenrolled["account"]
    assert unenrolled["payment"]["mode"] == "free"

    posted = free_client.post(
        "/v1/operator/enroll",
        json={"agent_id": "viewer", "interests": "research,ops"},
    )
    assert posted.status_code == 200
    body = posted.json()
    assert body["agent_id"] == "viewer"
    assert "visa" not in body
    ids = {s["id"] for s in body["skills"]}
    assert "research" in ids and "ops" in ids

    snap = free_client.get("/v1/operator").json()
    assert snap["account"]["enrolled"] is True
    assert snap["account"]["agent_id"] == "viewer"
    assert "visa" not in snap["account"]


def test_enroll_refuses_non_loopback(free_client, monkeypatch):
    monkeypatch.setattr(
        "veritas.server.is_loopback_client", lambda _req: False
    )
    r = free_client.post("/v1/operator/enroll", json={"agent_id": "remote"})
    assert r.status_code == 401
    assert r.json()["error"] == "unauthorized"
