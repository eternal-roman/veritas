"""The integration registry: every surface registered, nothing phantom.

Constitution A28's enforcement lives here. The registry at /v1/hooks must
cover every route the app mounts (or name it in the exclusion list), must
never advertise a surface that does not exist, and must state the absence
of push delivery rather than leave it to be inferred. The registry is the
superset: discovery links and llms.txt paths must all appear in it.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from veritas.hooks import (
    EXCLUDED_ROUTE_PATHS,
    HOOKS,
    build_hooks,
    http_paths,
    validate_hooks,
)

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def free_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.delenv("VERITAS_PUBLIC_URL", raising=False)
    monkeypatch.delenv("VERITAS_METRICS_TOKEN", raising=False)
    import veritas.server as main_module
    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_hooks_endpoint_serves_module_registry(free_client):
    body = free_client.get("/v1/hooks").json()
    assert validate_hooks(body) == []
    assert body["hooks"] == [dict(h) for h in HOOKS]
    assert body["content_hash"] == build_hooks()["content_hash"]


def test_hooks_document_hash_stable():
    """generatedAt is added after hashing; two builds must agree (the
    identity document once hashed its own timestamp)."""
    assert build_hooks()["content_hash"] == build_hooks()["content_hash"]


def test_every_app_route_is_registered_or_excluded(free_client):
    """A28: a route the app mounts that the registry does not name is a
    surface agents can only discover by accident."""
    import veritas.server as main_module

    app_paths = {route.path for route in main_module.app.routes}
    missing = app_paths - http_paths() - EXCLUDED_ROUTE_PATHS
    assert not missing, (
        f"routes mounted but not in the hooks registry: {sorted(missing)}"
    )


def test_registry_advertises_no_phantom_routes(free_client):
    """A28: the registry must never list an HTTP surface that does not
    exist — a phantom entry is a discovery-document lie."""
    import veritas.server as main_module

    app_paths = {route.path for route in main_module.app.routes}
    phantom = http_paths() - app_paths
    assert not phantom, f"registry advertises non-existent routes: {sorted(phantom)}"


def test_every_registered_http_path_answers(free_client):
    """GET each non-templated registered path: 405 proves existence, 404 is
    a lie — except /metrics, whose absence without a token is deliberate and
    flagged in its own record."""
    for hook in HOOKS:
        if hook["kind"] != "http":
            continue
        path = hook["interface"]["path"]
        if "{" in path:
            continue
        status = free_client.get(path).status_code
        if hook.get("absent_without_config"):
            assert status == 404, f"{path} should be absent without config"
        else:
            assert status != 404, f"registry lists dead path {path}"


def test_links_and_llms_paths_are_subset_of_registry(free_client):
    """The registry is the superset of every other discovery surface, so an
    endpoint added to links or llms.txt without a registry record fails."""
    registered = http_paths()
    links = free_client.get("/.well-known/x402").json()["links"]
    for name, path in links.items():
        assert path in registered, f"links[{name!r}]={path} not in hooks registry"
    text = free_client.get("/llms.txt").text
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("- /"):
            continue
        path = line[2:].split(":", 1)[0].strip()
        assert path in registered, f"llms.txt path {path} not in hooks registry"


def test_push_absence_is_honest():
    """A28: no push machinery exists; the registry must say so, and the
    validator must reject a document that claims otherwise."""
    doc = build_hooks()
    assert doc["push"]["available"] is False
    tampered = build_hooks()
    tampered["push"] = dict(tampered["push"], available=True)
    assert any("push" in problem for problem in validate_hooks(tampered))


def test_metric_help_declares_every_incremented_metric():
    """A counter incremented in server.py but absent from METRIC_HELP renders
    as 'Undeclared metric.' — the refund counter shipped that way."""
    from veritas.observability import METRIC_HELP

    source = (REPO / "veritas" / "server.py").read_text(encoding="utf-8")
    names = set(re.findall(r'increment\(\s*"([a-z_]+)"', source))
    assert names, "no metric increments found in server.py"
    undeclared = names - set(METRIC_HELP)
    assert not undeclared, f"incremented but undeclared metrics: {sorted(undeclared)}"


def test_mcp_records_match_mcp_server():
    """The registry's MCP announcement must match what veritas-mcp actually
    registers (single-sourced from the same constant)."""
    from veritas.mcp_server import MCP_TOOL_NAMES

    registered = {h["interface"]["tool"] for h in HOOKS if h["kind"] == "mcp-tool"}
    assert registered == set(MCP_TOOL_NAMES)


def test_cli_records_match_source_exit_codes():
    """Machine-readable exit codes must equal the constants the CLIs exit
    with — a wrong registry teaches an agent to misread a verdict."""
    from veritas import audit_cli, diligence_cli

    by_id = {h["id"]: h for h in HOOKS}
    dil = by_id["cli_diligence"]["interface"]["exit_codes"]
    assert dil == {
        str(diligence_cli.EXIT_PASS): "pass",
        str(diligence_cli.EXIT_FAIL): "fail",
        str(diligence_cli.EXIT_UNVERIFIABLE): "unverifiable",
        str(diligence_cli.EXIT_BAD_INPUT): "bad_input",
    }
    aud = by_id["cli_audit"]["interface"]["exit_codes"]
    assert aud == {
        str(audit_cli.EXIT_CONFIRMED): "confirmed",
        str(audit_cli.EXIT_DIVERGED): "diverged",
        str(audit_cli.EXIT_UNOBSERVED): "unobserved",
        str(audit_cli.EXIT_BAD_INPUT): "bad_input",
    }


def test_cli_records_cover_every_console_script():
    """Every [project.scripts] entry point is a surface an agent can shell
    out to; each must carry a registry record."""
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    section = text.split("[project.scripts]", 1)[1].split("[", 1)[0]
    scripts = set(re.findall(r"^([a-z-]+)\s*=", section, re.MULTILINE))
    assert scripts, "no console scripts parsed from pyproject"
    registered = {h["interface"]["command"] for h in HOOKS if h["kind"] == "cli"}
    assert registered == scripts


def test_identity_endpoints_are_registered_http_hooks():
    """Identity's endpoint map is a discovery surface; a path it names
    that the registry does not is a phantom for any agent that started
    at /v1/identity."""
    from urllib.parse import urlparse

    from veritas.identity import build_identity

    registered = http_paths()
    for name, raw in build_identity().get("endpoints", {}).items():
        path = urlparse(raw).path if "://" in raw else raw
        assert path in registered, f"identity endpoints[{name!r}]={path} not in hooks"

