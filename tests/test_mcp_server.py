"""The MCP surface: local tools over the one engine, honestly scoped.

pyproject has advertised the "mcp" keyword since packaging; this module makes
it true. The tools run the local free-mode engine — no payment path exists
over MCP (an MCP client pays nothing), so paid access remains the HTTP
surface. The SDK is imported lazily: the bare wheel must import without it.
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import re
import sys
from pathlib import Path

import pytest

from veritas import mcp_server
from veritas.schema import validate_response


def test_tool_research_returns_contract_valid_body(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    body = mcp_server.tool_research("What is x402?", allow_network=False)
    assert validate_response(body) == []
    assert body["status"] == "completed"


def test_tool_verify_checks_hashes():
    from veritas.hashing import compute_content_hash

    text = "some evidence text"
    good = mcp_server.tool_verify(text, compute_content_hash(text))
    assert good["valid"] is True
    bad = mcp_server.tool_verify(text + "!", compute_content_hash(text))
    assert bad["valid"] is False


def test_tool_trust_reports_honestly(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    body = mcp_server.tool_trust()
    assert body["recommendation"] == "UNPROVEN"


def test_tool_constitution_serves_validated_document():
    from veritas.constitution import validate_constitution

    assert validate_constitution(mcp_server.tool_constitution()) == []


def test_tools_register_with_mcp_sdk():
    """Absent optional extra → skip. Present but wrong surface → fail.

    `importorskip("mcp.server.fastmcp")` conflated the two. The SDK being
    uninstalled is a legitimate skip: it is an optional extra. The SDK being
    installed *without* the surface `veritas-mcp` is built on is not — it means
    the shipped entry point cannot serve, and skipping turned that into a
    silent loss of coverage rather than a failure.

    Not hypothetical: mcp 2.0 imports fine and removed `mcp.server.fastmcp`.
    When the hashed lock briefly resolved to it, this test skipped and kept
    skipping, leaving STATUS's "tested against the SDK" claim held up by a test
    that no longer ran.
    """
    pytest.importorskip("mcp")
    try:
        has_surface = importlib.util.find_spec("mcp.server.fastmcp") is not None
    except (ImportError, AttributeError, ValueError):
        has_surface = False
    if not has_surface:
        import mcp

        pytest.fail(
            f"the installed mcp SDK ({getattr(mcp, '__version__', 'unknown')}) "
            "has no mcp.server.fastmcp. veritas-mcp is built on that surface, so "
            "this is a broken dependency bound, not an absent optional extra. "
            "pyproject constrains mcp for exactly this reason."
        )
    server = mcp_server.build_server()
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "research",
        "verify",
        "verify_attestation",
        "verify_pack",
        "verify_log_inclusion",
        "trust",
        "constitution",
    }


def test_declared_mcp_bound_excludes_versions_without_the_shipped_surface():
    """The bound encodes a behavioural fact, so state it where it is edited.

    An automated dependency bump reads `mcp>=1.0,<2` as a number to raise, and
    a proposal to widen it to `<3` passes every other check: it edits only
    pyproject and requirements-dev, never the lock, so the installed version —
    and therefore the whole test suite — is unchanged. The breakage lands
    later, on whoever next regenerates the lock.

    This fails such a proposal at review time instead. Widening past 2.0 is not
    forbidden forever; it requires first confirming the new major actually
    provides `mcp.server.fastmcp`, and then updating this test with that
    evidence.
    """
    from packaging.specifiers import SpecifierSet

    text = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    match = re.search(r'^mcp\s*=\s*\["mcp([^"]+)"\]', text, re.MULTILINE)
    assert match, "pyproject no longer declares an [mcp] extra as expected"

    specifier = SpecifierSet(match.group(1))
    assert "2.0.0" not in specifier, (
        "the [mcp] extra admits mcp 2.0.0, which removed mcp.server.fastmcp — "
        "the surface veritas-mcp is built on. Widening this bound silently "
        "disables the SDK test on the next lock regeneration."
    )


def test_module_imports_without_mcp_sdk(monkeypatch):
    """The SDK is optional; importing the module must not pull it in."""
    for name in list(sys.modules):
        if name == "mcp" or name.startswith("mcp."):
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.delitem(sys.modules, "veritas.mcp_server", raising=False)
    importlib.import_module("veritas.mcp_server")
    assert not any(n == "mcp" or n.startswith("mcp.") for n in sys.modules), (
        "importing veritas.mcp_server pulled in the mcp SDK eagerly"
    )
