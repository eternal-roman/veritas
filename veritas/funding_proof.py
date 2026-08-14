"""Prove USDC arrived at a commerce address — faucet custody, not settlement.

An agent cannot mint USDC. Circle's faucet needs a human (reCAPTCHA). This
module only *observes* chain: ``Transfer`` logs to the address, optionally
one named tx, plus ``balanceOf``. ``funded`` is true only when a Transfer
to the address is seen.

Not product revenue. Not G9 settlement reconcile. Not a balance we invented.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from veritas.chain_reconcile import resolve_rpc_url
from veritas.networks import DEFAULT_NETWORK, normalize_network
from veritas.x402 import USDC_ASSETS

_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

FUNDING_SCHEMA = "veritas.agent.funding_proof.v1"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
FAUCET_URL = "https://faucet.circle.com/"
# keccak Transfer(address,address,uint256)

RpcTransport = Callable[[str, str, list[Any]], Any]


def _pad_address(address: str) -> str:
    return "0x" + address.lower().removeprefix("0x").zfill(64)


def _topic_address(topic: str) -> str:
    return "0x" + str(topic).lower().removeprefix("0x")[-40:]


def _atomic(data: Any) -> int:
    if data is None:
        return 0
    text = str(data)
    if text.startswith("0x"):
        return int(text, 16)
    return int(text)


def parse_transfer_logs(
    logs: list[Any], token: str, to_address: str
) -> list[dict[str, Any]]:
    token_l = token.lower()
    to_l = to_address.lower()
    found: list[dict[str, Any]] = []
    for log in logs:
        if not isinstance(log, dict):
            continue
        if str(log.get("address") or "").lower() != token_l:
            continue
        topics = log.get("topics") or []
        if len(topics) < 3:
            continue
        if str(topics[0]).lower() != TRANSFER_TOPIC:
            continue
        dest = _topic_address(str(topics[2]))
        if dest != to_l:
            continue
        found.append(
            {
                "tx": log.get("transactionHash"),
                "from": _topic_address(str(topics[1])),
                "to": dest,
                "amount_atomic": _atomic(log.get("data")),
                "block": log.get("blockNumber"),
            }
        )
    return found


def _default_transport(url: str, method: str, params: list[Any]) -> Any:
    from veritas.chain_reconcile import _default_transport as rpc

    return rpc(url, method, params)


def prove_funding(
    address: str,
    *,
    network: str = DEFAULT_NETWORK,
    tx_hash: str | None = None,
    rpc_url: str | None = None,
    transport: RpcTransport | None = None,
) -> dict[str, Any]:
    """Observe USDC Transfer custody for ``address`` on ``network``."""
    net = normalize_network(network)
    asset = USDC_ASSETS.get(net)
    addr = address.lower()
    next_step = (
        f"{FAUCET_URL} — paste {addr} on Base Sepolia, then "
        "veritas-agent fund-proof"
    )
    base: dict[str, Any] = {
        "schema": FUNDING_SCHEMA,
        "address": addr,
        "network": net,
        "asset": asset["address"] if asset else None,
        "funded": False,
        "balance_atomic": None,
        "transfers": [],
        "not_x402_settlement": True,
        "not_product_revenue": True,
        "faucet": FAUCET_URL,
        "next": next_step,
        "note": (
            "USDC Transfer observed on chain is funding custody, not a "
            "product settlement. Enroll does not fund."
        ),
    }
    if not _ADDRESS_RE.match(address):
        base["error"] = "invalid_address"
        return base
    if asset is None:
        base["error"] = "unknown_asset"
        base["next"] = f"no USDC asset for {net}"
        return base

    url, source = resolve_rpc_url(net, rpc_url)
    base["rpc_source"] = source
    if not url:
        base["error"] = "rpc_unconfigured"
        return base

    call = transport or _default_transport
    token = asset["address"]
    try:
        if tx_hash:
            receipt = call(url, "eth_getTransactionReceipt", [tx_hash])
            logs = (receipt or {}).get("logs") if isinstance(receipt, dict) else []
            base["transfers"] = parse_transfer_logs(list(logs or []), token, addr)
            base["checked_tx"] = tx_hash
        else:
            transfers, logs_error = _scan_transfers(call, url, token, addr)
            base["transfers"] = transfers
            if logs_error:
                base["logs_error"] = logs_error
        raw_bal = call(
            url,
            "eth_call",
            [
                {
                    "to": token,
                    "data": "0x70a08231" + addr.removeprefix("0x").zfill(64),
                },
                "latest",
            ],
        )
        base["balance_atomic"] = _atomic(raw_bal)
    except Exception as exc:
        base["error"] = f"{type(exc).__name__}: {exc}"
        return base

    base["funded"] = len(base["transfers"]) > 0
    if base["funded"]:
        base["next"] = "veritas-agent whoami"
    elif base.get("logs_error") and (base.get("balance_atomic") or 0) > 0:
        base["note"] = (
            "balanceOf is positive but no Transfer log was recovered "
            "(RPC log range often refuses 0x0→latest). Pass --tx <hash> "
            "from the faucet receipt. Balance alone is not custody."
        )
    return base


def _scan_transfers(
    call: RpcTransport, url: str, token: str, addr: str
) -> tuple[list[dict[str, Any]], str | None]:
    """eth_getLogs over all history; public RPCs often refuse that range.

    Failure is ``logs_error``, not ``funded``. A later ``--tx`` is the
    reliable custody path.
    """
    try:
        logs = call(
            url,
            "eth_getLogs",
            [
                {
                    "fromBlock": "0x0",
                    "toBlock": "latest",
                    "address": token,
                    "topics": [TRANSFER_TOPIC, None, _pad_address(addr)],
                }
            ],
        )
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"
    return parse_transfer_logs(list(logs or []), token, addr), None
