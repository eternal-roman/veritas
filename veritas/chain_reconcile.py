"""G9 design: reconcile facilitator-reported settlements against chain RPC.

Constitution gap G9: the ledger records what the facilitator told us. Closing
the gap requires an RPC endpoint and an explicit operator choice — never a
silent default that invents on-chain confirmation.

This module is the **design + fail-closed implementation surface**:

* Without ``VERITAS_RPC_URL`` (or an injected transport), every call returns
  ``chain_checked: false`` and ``status: rpc_not_configured``.
* With an RPC URL and transport, JSON-RPC ``eth_getTransactionReceipt`` is
  used to classify a single transaction hash.
* Results never rewrite the ledger or invent revenue. Operators act on the
  report; the money path is unchanged.

Honesty: shipping this module does **not** close G9. G9 closes when production
operators run chain reconcile and the constitution witness is retired. Default
sandbox has no RPC; on-chain settlements proven here remain **0**.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

from veritas import __version__

ENV_RPC_URL = "VERITAS_RPC_URL"
ENV_RPC_TIMEOUT = "VERITAS_RPC_TIMEOUT_SECONDS"
DEFAULT_TIMEOUT = 15.0

# Known public JSON-RPC endpoints, keyed by CAIP-2 network id. **Testnets
# only**: a mainnet default could classify real-money settlements against the
# wrong chain (a genuine mainnet tx would read ``not_found`` here), so mainnet
# always requires an explicit VERITAS_RPC_URL. Provenance: Base's published
# network information (docs.base.org); exercised live against a settled tx on
# 2026-08-09 — evidence in docs/program/fable/settlement/.
DEFAULT_PUBLIC_RPC_URLS: dict[str, str] = {
    "eip155:84532": "https://sepolia.base.org",
}

# Injectable JSON-RPC caller: (url, method, params) -> result object
RpcTransport = Callable[[str, str, list[Any]], Any]

G9_NOTE = (
    "chain reconcile design surface; without VERITAS_RPC_URL nothing is "
    "checked on-chain; does not rewrite the ledger or invent revenue; "
    "constitution gap G9 remains open until operators configure RPC and "
    "the production path uses it"
)


def rpc_url_from_env() -> str | None:
    raw = (os.getenv(ENV_RPC_URL) or "").strip()
    return raw or None


def resolve_rpc_url(
    network: str | None, env_url: str | None = None
) -> tuple[str | None, str]:
    """Resolve the RPC URL for one settlement's network.

    An explicit environment URL always wins — the operator's choice covers
    every network. Otherwise a pinned public **testnet** default applies only
    to the network it is pinned for; anything else stays unconfigured, so a
    mainnet settlement can never be checked against the wrong chain by
    default. Returns ``(url, source)`` where source is ``env``,
    ``default_public_rpc:<network>``, or ``unconfigured``.
    """
    url = env_url if env_url is not None else rpc_url_from_env()
    if url:
        return url, "env"
    default = DEFAULT_PUBLIC_RPC_URLS.get(network or "")
    if default:
        return default, f"default_public_rpc:{network}"
    return None, "unconfigured"


def rpc_timeout_from_env() -> float:
    raw = (os.getenv(ENV_RPC_TIMEOUT) or "").strip()
    if not raw:
        return DEFAULT_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT
    return value if value > 0 else DEFAULT_TIMEOUT


def _default_transport(url: str, method: str, params: list[Any]) -> Any:
    """Minimal JSON-RPC over HTTP(S). Used only when RPC URL is configured."""
    if not (url.startswith("https://") or url.startswith("http://")):
        raise ChainReconcileError("rpc_url_scheme_not_http")
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    ).encode("utf-8")
    # The User-Agent is load-bearing, not cosmetic: public RPC endpoints
    # (observed live 2026-08-08 on sepolia.base.org, Cloudflare-fronted)
    # reject the default ``Python-urllib/x.y`` agent outright, which made
    # every reconcile attempt report ``rpc_transport_error:HTTPError`` while
    # curl against the same endpoint succeeded. Same defect class as the
    # facilitator client's error-1010 ban; both money-path HTTP clients now
    # identify themselves the way the retrieval clients always have.
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": f"veritas-chain-reconcile/{__version__}",
        },
        method="POST",
    )
    timeout = rpc_timeout_from_env()
    try:
        # Operator-configured RPC only; scheme restricted to http(s) above.
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise ChainReconcileError(f"rpc_transport_error:{type(exc).__name__}") from exc
    if not isinstance(body, dict):
        raise ChainReconcileError("rpc_malformed_response")
    if body.get("error"):
        err = body["error"]
        code = err.get("code") if isinstance(err, dict) else None
        raise ChainReconcileError(f"rpc_error:{code}")
    return body.get("result")


class ChainReconcileError(RuntimeError):
    """RPC or classification could not complete (not a chain 'failed' outcome)."""


def classify_receipt(receipt: Mapping[str, Any] | None) -> str:
    """Map an eth_getTransactionReceipt result to a stable status code."""
    if receipt is None:
        return "not_found"
    if not isinstance(receipt, Mapping):
        return "malformed_receipt"
    status = receipt.get("status")
    # Post-Byzantium: status 0x1 success, 0x0 failure. Absent → unknown.
    if status in (None, ""):
        return "unknown_status"
    try:
        if isinstance(status, str):
            value = int(status, 16) if status.startswith("0x") else int(status)
        else:
            value = int(status)
    except (TypeError, ValueError):
        return "malformed_status"
    if value == 1:
        return "confirmed"
    if value == 0:
        return "reverted"
    return "unknown_status"


def check_transaction(
    transaction_hash: str,
    *,
    rpc_url: str | None = None,
    transport: RpcTransport | None = None,
) -> dict[str, Any]:
    """Check one tx hash against chain RPC. Fail-closed without configuration."""
    if not transaction_hash or not str(transaction_hash).startswith("0x"):
        return {
            "transaction": transaction_hash,
            "chain_checked": False,
            "status": "invalid_hash",
            "note": G9_NOTE,
        }

    url = rpc_url if rpc_url is not None else rpc_url_from_env()
    if not url:
        return {
            "transaction": transaction_hash,
            "chain_checked": False,
            "status": "rpc_not_configured",
            "note": G9_NOTE,
        }

    call = transport or _default_transport
    try:
        receipt = call(url, "eth_getTransactionReceipt", [transaction_hash])
    except ChainReconcileError as exc:
        return {
            "transaction": transaction_hash,
            "chain_checked": False,
            "status": "rpc_unavailable",
            "reason": str(exc),
            "note": G9_NOTE,
        }

    status = classify_receipt(receipt if isinstance(receipt, Mapping) or receipt is None else None)
    return {
        "transaction": transaction_hash,
        "chain_checked": True,
        "status": status,
        "note": G9_NOTE,
    }


def reconcile_settlements(
    settlements: list[Mapping[str, Any]],
    *,
    rpc_url: str | None = None,
    transport: RpcTransport | None = None,
) -> dict[str, Any]:
    """Classify a list of settlement dicts that may carry ``transaction``.

    Does not mutate the ledger. Entries without a transaction hash are
    ``missing_transaction`` (same class as settled_without_transaction).
    """
    url = rpc_url if rpc_url is not None else rpc_url_from_env()
    results: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    for entry in settlements:
        tx = entry.get("transaction") or entry.get("transaction_hash")
        request_id = entry.get("request_id")
        if not tx:
            row = {
                "request_id": request_id,
                "transaction": None,
                "chain_checked": False,
                "status": "missing_transaction",
                "note": G9_NOTE,
            }
        else:
            row = check_transaction(str(tx), rpc_url=url, transport=transport)
            row["request_id"] = request_id
        results.append(row)
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    return {
        "chain_checked": bool(url) and any(r.get("chain_checked") for r in results),
        "rpc_configured": bool(url),
        "counts": counts,
        "results": results,
        "note": G9_NOTE,
        "limitation": (
            "This report does not rewrite ledger revenue. "
            "G9 remains open until operators configure VERITAS_RPC_URL and "
            "act on chain_checked results in production."
        ),
    }


def reconcile_settlements_auto(
    settlements: list[Mapping[str, Any]],
    *,
    env_url: str | None = None,
    transport: RpcTransport | None = None,
) -> dict[str, Any]:
    """Like :func:`reconcile_settlements`, resolving the RPC per row.

    With ``VERITAS_RPC_URL`` set (or ``env_url`` given) this behaves exactly
    like the explicit path. Unset, rows on a known public **testnet** are
    checked against that network's pinned default and every other row stays
    ``rpc_not_configured`` — an unset variable downgrades coverage, never
    correctness. Each row is stamped with its ``rpc_source``.
    """
    resolved_env = env_url if env_url is not None else rpc_url_from_env()
    results: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    sources: dict[str, int] = {}
    any_url = False

    for entry in settlements:
        tx = entry.get("transaction") or entry.get("transaction_hash")
        request_id = entry.get("request_id")
        url, source = resolve_rpc_url(entry.get("network"), resolved_env)
        if not tx:
            row: dict[str, Any] = {
                "request_id": request_id,
                "transaction": None,
                "chain_checked": False,
                "status": "missing_transaction",
                "note": G9_NOTE,
            }
        elif not url:
            row = {
                "request_id": request_id,
                "transaction": str(tx),
                "chain_checked": False,
                "status": "rpc_not_configured",
                "note": G9_NOTE,
            }
        else:
            any_url = True
            row = check_transaction(str(tx), rpc_url=url, transport=transport)
            row["request_id"] = request_id
        row["rpc_source"] = source
        results.append(row)
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        sources[source] = sources.get(source, 0) + 1

    return {
        "chain_checked": any(r.get("chain_checked") for r in results),
        "rpc_configured": bool(resolved_env) or any_url,
        "rpc_sources": sources,
        "counts": counts,
        "results": results,
        "note": G9_NOTE,
        "limitation": (
            "This report does not rewrite ledger revenue. Defaults cover "
            "known public testnets only; mainnet requires an explicit "
            "VERITAS_RPC_URL. G9 remains open until reconciliation runs "
            "routinely in production."
        ),
    }


__all__ = [
    "DEFAULT_PUBLIC_RPC_URLS",
    "ENV_RPC_URL",
    "ENV_RPC_TIMEOUT",
    "G9_NOTE",
    "ChainReconcileError",
    "RpcTransport",
    "check_transaction",
    "classify_receipt",
    "reconcile_settlements",
    "reconcile_settlements_auto",
    "resolve_rpc_url",
    "rpc_timeout_from_env",
    "rpc_url_from_env",
]
