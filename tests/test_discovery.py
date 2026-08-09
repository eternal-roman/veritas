"""Discovery must be self-traversing and honest about what is configured.

An agent that finds one discovery document must be able to reach every other
machine-readable surface from it, and a default deployment must never
advertise endpoints on a domain that does not exist.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def free_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.delenv("VERITAS_PUBLIC_URL", raising=False)
    import veritas.server as main_module
    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_well_known_is_self_traversing(free_client):
    """Every link must reach a live surface — all of them, not a sample.
    A 405 on a POST-only route is existence; a 404 is a dead link."""
    body = free_client.get("/.well-known/x402").json()
    links = body["links"]
    for name in ("identity", "trust", "constitution", "errors", "schema",
                 "openapi", "llms", "hooks", "research", "verify",
                 "payment_config"):
        assert name in links, f"well-known does not link {name}"
    for name, path in links.items():
        if "{" in path:
            continue
        status = free_client.get(path).status_code
        assert status != 404, f"links[{name!r}] -> {path} is dead"


def test_well_known_free_mode_publishes_empty_accepts_and_configured_price(free_client):
    """Free mode previously revealed nothing about cost. An empty accepts is
    an honest 'no offer'; configured_price is config, not an offer."""
    body = free_client.get("/.well-known/x402").json()
    assert body["mode"] == "free"
    assert body["accepts"] == []
    assert body["configured_price"]


def test_identity_without_public_url_is_relative_and_flagged(free_client):
    """The old default advertised https://api.veritas.example — a reserved
    domain nobody can dial. Unset base URL now means relative paths and an
    explicit flag, never a fabricated absolute URL."""
    body = free_client.get("/v1/identity").json()
    assert body["base_url_configured"] is False
    for name, path in body["endpoints"].items():
        assert path.startswith("/"), f"endpoint {name} is not relative: {path}"
        assert "veritas.example" not in path


def test_identity_does_not_advertise_removed_bayesian_surface(free_client):
    """Phase T removed the posterior from the served path. Identity still
    claimed 'Bayesian belief updating' / bayesian-updating after that retract,
    which is a discovery-document lie. Capabilities must match pipeline +
    support counts."""
    body = free_client.get("/v1/identity").json()
    caps = body["capabilities"]
    assert "bayesian-updating" not in caps
    assert "Bayesian" not in body["description"]
    assert "bayesian" not in body["description"].lower()
    assert "support-counts" in caps
    assert "custody-chain" in caps
    assert "refusal" in caps


def test_llms_and_mcp_do_not_advertise_removed_bayesian_surface(free_client):
    """The identity fix above did not reach llms.txt or the MCP tool
    descriptions, which kept advertising the retracted posterior to agents —
    the same defect class, caught on different surfaces."""
    from veritas import mcp_server
    from veritas.discovery import LLMS_TXT

    assert "bayesian" not in LLMS_TXT.lower()
    assert "bayesian" not in free_client.get("/llms.txt").text.lower()
    for name in mcp_server.MCP_TOOL_NAMES:
        doc = getattr(mcp_server, f"tool_{name}").__doc__ or ""
        assert "bayesian" not in doc.lower(), (
            f"MCP tool {name} advertises the retracted posterior"
        )


def test_identity_with_public_url_is_absolute(free_client, tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://research.example.org")
    import veritas.server as main_module
    importlib.reload(main_module)
    client = TestClient(main_module.app)
    body = client.get("/v1/identity").json()
    assert body["base_url_configured"] is True
    assert body["endpoints"]["research"] == "https://research.example.org/v1/research"


def test_llms_txt_served_and_in_sync_with_repo_root(free_client):
    """The served document is the source (it ships in the wheel); the repo
    root copy exists for agents reading the repository, sync-tested the same
    way CONSTITUTION.md is."""
    served = free_client.get("/llms.txt")
    assert served.status_code == 200
    assert served.text == (REPO / "llms.txt").read_text(encoding="utf-8")


def test_llms_txt_names_only_real_endpoints(free_client):
    """Every path llms.txt lists must exist on the app (a 405 for a POST-only
    route is existence; a 404 is a lie in the discovery document)."""
    text = free_client.get("/llms.txt").text
    paths = [
        line.strip()[2:].split(":", 1)[0].strip()
        for line in text.splitlines()
        if line.strip().startswith("- /")
    ]
    assert paths, "llms.txt lists no endpoints"
    for path in paths:
        if "{" in path:
            continue
        assert free_client.get(path).status_code != 404, f"llms.txt lists dead path {path}"
