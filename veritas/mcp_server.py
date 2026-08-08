"""MCP surface: Veritas research as local MCP tools (stdio).

Honest scope: these tools run the local free-mode engine in-process. There
is no payment path over MCP — an MCP client pays nothing — so paid access
remains the HTTP surface (`/v1/research` with x402). What this gives an
agent framework is the same evidence-grounded engine, custody receipts and
all, one `veritas-mcp` command away, and it makes the long-advertised "mcp"
package keyword true instead of aspirational.

The MCP SDK is imported lazily inside `build_server`/`main`: the bare wheel
imports this module without the `mcp` extra installed
(`pip install "veritas-research[mcp]"` enables serving).
"""

from __future__ import annotations

from typing import Any


def tool_research(query: str, max_results: int = 5, allow_network: bool = True) -> dict[str, Any]:
    """Evidence-grounded research over the one shared engine (free mode).

    Returns the full wire-contract body: claims citing content-hashed
    evidence, a Bayesian posterior, custody root, and the honest outcome
    taxonomy (completed / refused / unavailable). `allow_network=False` pins
    the labelled offline corpus (deterministic, not live evidence).
    """
    from veritas.pipeline import run_research

    return run_research(query, max_results=max_results, allow_network=allow_network)


def tool_verify(content: str, content_hash: str) -> dict[str, Any]:
    """Independently re-check a published content hash."""
    from veritas.hashing import verify_content_hash

    valid, details = verify_content_hash(content, content_hash)
    return {"valid": valid, "detail": details}


def tool_verify_attestation(
    evidence_record: dict[str, Any],
    attestation: dict[str, Any],
    expected_signer: str | None = None,
) -> dict[str, Any]:
    """Check an N1.1 EIP-191 EvidenceRecord attestation (local free mode).

    Not an on-chain anchor and not a re-fetch of the origin URL.
    """
    from veritas.notary.sign import SCHEME, verify_attestation

    ok, reason = verify_attestation(
        evidence_record,
        attestation,
        expected_signer=expected_signer,
    )
    return {
        "valid": ok,
        "reason": reason,
        "scheme": attestation.get("scheme") or SCHEME,
        "note": (
            "EIP-191 recovery over bound record fields; "
            "not an on-chain anchor and not a re-fetch of the origin"
        ),
    }


def tool_trust() -> dict[str, Any]:
    """Behaviour-derived trust score; UNPROVEN below the sample floor."""
    from veritas.trust import score_service

    return score_service().to_dict()


def tool_constitution() -> dict[str, Any]:
    """The venue constitution: norms with enforcement pointers or an explicit aspirational marker."""
    from veritas.constitution import build_constitution

    return build_constitution()


def build_server():
    """Wire the plain tool functions into a FastMCP stdio server.

    Targets the MCP 1.x `FastMCP` API. mcp 2.0 removed `mcp.server.fastmcp`
    outright (the package reorganised around `mcp.server.mcpserver`), so the
    extra is pinned `mcp>=1.0,<2` and this raises something a caller can act
    on rather than a bare ModuleNotFoundError from three frames down.
    Migrating to the 2.x API is separate work; the HTTP surface is unaffected.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "veritas-mcp needs the MCP 1.x SDK: mcp 2.0 removed "
            "mcp.server.fastmcp. Install with pip install "
            "'veritas-research[mcp]', which pins mcp>=1.0,<2."
        ) from exc

    server = FastMCP(
        "veritas-research",
        instructions=(
            "Evidence-grounded research (local free-mode engine). The "
            "service separates 'no evidence exists' from 'I could not "
            "look'; an unavailable result is a retrieval failure, not an "
            "absence of evidence. Paid access with settlement is the HTTP "
            "surface, not these tools."
        ),
    )
    server.tool(name="research")(tool_research)
    server.tool(name="verify")(tool_verify)
    server.tool(name="verify_attestation")(tool_verify_attestation)
    server.tool(name="trust")(tool_trust)
    server.tool(name="constitution")(tool_constitution)
    return server


def main() -> None:
    """Console entry point (`veritas-mcp`): serve over stdio."""
    build_server().run()


if __name__ == "__main__":
    main()
