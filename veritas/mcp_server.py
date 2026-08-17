"""MCP surface: Veritas catalog + verify tools (stdio).

Honest scope: these tools run the local free-mode engine in-process. There
is no payment path over MCP — an MCP client pays nothing — so paid access
remains the HTTP surface (`/v1/signals` with x402).

The MCP SDK is imported lazily inside `build_server`/`main`: the bare wheel
imports this module without the `mcp` extra installed
(`pip install "veritas-research[mcp]"` enables serving).
"""

from __future__ import annotations

from typing import Any


def tool_signals_list(venue: str | None = None, q: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Latest catalog snapshots from the local store. Prices, not verdicts."""
    from veritas.signals import SignalStore

    items = SignalStore().list(venue=venue, q=q, limit=limit)
    return {
        "signals": items,
        "count": len(items),
        "method": "veritas.signals.v1",
        "note": "latest snapshot per market; prices, not a verdict",
    }


def tool_signals_pull(
    query: str, venues: list[str] | None = None, limit: int = 8
) -> dict[str, Any]:
    """Pull Kalshi/Polymarket books into the local store (free-mode MCP)."""
    from veritas.signals import SignalStore, analyze, pull

    items = pull(query, venues=venues, limit=limit)
    stored = SignalStore().put_many(items)
    return {
        "signals": items,
        "stored": stored,
        "analysis": analyze(items),
        "method": "veritas.signals.v1",
        "note": "market-implied prices, not a verdict",
    }


def tool_verify(content: str, content_hash: str) -> dict[str, Any]:
    """Re-check a published content hash over caller-supplied text.

    Arithmetic on bytes already in the caller's hands — the same non-independent
    check the HTTP legacy mode labels `caller_supplied`. Independent origin
    re-fetch is `POST /v1/verify` with url+content_hash on the HTTP surface.
    """
    from veritas.hashing import verify_content_hash

    valid, details = verify_content_hash(content, content_hash)
    return {"valid": valid, "detail": details, "binding": "caller_supplied"}


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


def tool_verify_pack(pack: dict[str, Any]) -> dict[str, Any]:
    """Check an N1.3 portable EvidencePack (pack_hash + optional attestation)."""
    from veritas.notary.pack import verify_evidence_pack

    return verify_evidence_pack(pack)


def tool_verify_log_inclusion(proof: dict[str, Any]) -> dict[str, Any]:
    """Verify an N1.4 local Merkle inclusion proof (not public CT / not on-chain)."""
    from veritas.notary.log import verify_log_inclusion

    return verify_log_inclusion(proof)


def tool_trust() -> dict[str, Any]:
    """GET-equivalent trust: UNPROVEN from the operator log (no buyer records)."""
    from veritas.trust import score_service

    return score_service().to_dict()


def tool_constitution() -> dict[str, Any]:
    """The venue constitution: norms with enforcement pointers or an explicit aspirational marker."""
    from veritas.constitution import build_constitution

    return build_constitution()


def tool_whoami() -> dict[str, Any]:
    """Local agent account: identity, wallets, bound skills — or how to enroll.

    Reads the local home (VERITAS_AGENT_HOME or .veritas_agent). Does not
    create an account and does not touch payment.
    """
    from veritas.agent_account import whoami_document

    return whoami_document()


#: Tool name → implementation. The single source for what `veritas-mcp`
#: serves: `build_server` registers from this mapping and the hooks registry
#: (`veritas/hooks.py`) imports `MCP_TOOL_NAMES`, so the HTTP-discoverable
#: announcement cannot drift from what actually registers.
_TOOL_IMPLEMENTATIONS = {
    "signals_list": tool_signals_list,
    "signals_pull": tool_signals_pull,
    "verify": tool_verify,
    "verify_attestation": tool_verify_attestation,
    "verify_pack": tool_verify_pack,
    "verify_log_inclusion": tool_verify_log_inclusion,
    "trust": tool_trust,
    "constitution": tool_constitution,
    "whoami": tool_whoami,
}

MCP_TOOL_NAMES: tuple[str, ...] = tuple(_TOOL_IMPLEMENTATIONS)


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
            "Prediction-market catalog (local free-mode). Snapshots are "
            "prices, not verdicts. Paid pull with settlement is the HTTP "
            "surface, not these tools."
        ),
    )
    for name, implementation in _TOOL_IMPLEMENTATIONS.items():
        server.tool(name=name)(implementation)
    return server


def main(argv: list[str] | None = None) -> None:
    """Console entry point (`veritas-mcp`): serve over stdio.

    The parser exists so `veritas-mcp --help` explains itself instead of
    silently blocking on stdio.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="veritas-mcp",
        description=(
            "Serve the Veritas engine as MCP tools over stdio (free-mode "
            "local engine; paid access with settlement is the HTTP surface). "
            "Register it with an MCP client as an stdio server: veritas-mcp"
        ),
    )
    parser.parse_args(argv)
    build_server().run()


if __name__ == "__main__":
    main()
