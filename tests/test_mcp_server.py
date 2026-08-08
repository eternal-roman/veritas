"""The MCP surface: local tools over the one engine, honestly scoped.

pyproject has advertised the "mcp" keyword since packaging; this module makes
it true. The tools run the local free-mode engine — no payment path exists
over MCP (an MCP client pays nothing), so paid access remains the HTTP
surface. The SDK is imported lazily: the bare wheel must import without it.
"""

from __future__ import annotations

import asyncio
import importlib
import sys

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
    # Skip on the module actually needed, not on the distribution name: mcp
    # 2.0 imports fine and has no `mcp.server.fastmcp`, so `importorskip("mcp")`
    # let this run and fail against an SDK the code does not target.
    pytest.importorskip("mcp.server.fastmcp")
    server = mcp_server.build_server()
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert names == {"research", "verify", "trust", "constitution"}


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
