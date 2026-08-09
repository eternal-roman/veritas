"""Unblock Agent probe — update human-ops checklist in place (no docs thrash).

Writes/updates ``docs/program/ecosystem/unblock/CHECKLIST.md`` with honest
env/network probe results. Does **not** invent funded wallets or settlement.

Run: ``python -m veritas.unblock_probe``
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from veritas import __version__
from veritas.chain_reconcile import DEFAULT_PUBLIC_RPC_URLS
from veritas.safeurl import UnsafeUrlError, require_http_url

# Load-bearing, not cosmetic (AGENTS.md field note 1): Cloudflare fronts both
# sepolia.base.org and x402.org and 403s the default Python-urllib agent.
# Observed live 2026-08-09 from this probe itself — without this header both
# pinned defaults report "no" while curl succeeds against the same URLs.
USER_AGENT = f"veritas-unblock-probe/{__version__}"

#: Pinned public endpoints probed when the env vars are unset. An unset
#: variable is a hypothesis, not a block (docs/program/MIND.md §3): the probe
#: answers "can this host reach the money-path counterparties", and both
#: endpoints are public. Env vars always override.
DEFAULT_TESTNET_RPC = DEFAULT_PUBLIC_RPC_URLS["eip155:84532"]
DEFAULT_FACILITATOR = "https://x402.org/facilitator"


def _probe_env(name: str) -> dict[str, Any]:
    val = os.environ.get(name)
    if not val:
        return {"status": "no", "evidence": f"{name} unset"}
    # Never echo secrets
    return {"status": "yes", "evidence": f"{name} set (len={len(val)})"}


def _probe_http(url: str, timeout: float = 3.0) -> dict[str, Any]:
    try:
        safe = require_http_url(url)
        req = urllib.request.Request(
            safe, headers={"User-Agent": USER_AGENT}, method="GET"
        )
        with urllib.request.urlopen(  # nosec B310 - scheme checked by require_http_url
            req, timeout=timeout
        ) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
        return {"status": "yes", "evidence": f"HTTP {code} from {url}"}
    except UnsafeUrlError as e:
        return {"status": "no", "evidence": f"UnsafeUrlError: {e}"}
    except urllib.error.HTTPError as e:
        # Reachable enough to get HTTP error
        return {"status": "partial", "evidence": f"HTTP {e.code} from {url}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "no", "evidence": f"{type(e).__name__}: {e}"}


def _probe_rpc(url: str | None, timeout: float = 3.0) -> dict[str, Any]:
    if not url:
        return {"status": "no", "evidence": "no RPC URL to probe"}
    body = json.dumps(
        {"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1}
    ).encode("utf-8")
    try:
        safe = require_http_url(url)
        req = urllib.request.Request(
            safe,
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        with urllib.request.urlopen(  # nosec B310 - scheme checked by require_http_url
            req, timeout=timeout
        ) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        chain = data.get("result", "?")
        return {"status": "yes", "evidence": f"eth_chainId={chain}"}
    except UnsafeUrlError as e:
        return {"status": "no", "evidence": f"UnsafeUrlError: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "no", "evidence": f"{type(e).__name__}: {e}"}


def run_probes() -> dict[str, dict[str, Any]]:
    rpc_env = os.environ.get("VERITAS_RPC_URL")
    fac_env = os.environ.get("VERITAS_FACILITATOR_URL") or os.environ.get(
        "X402_FACILITATOR_URL"
    )

    rpc = _probe_rpc(rpc_env or DEFAULT_TESTNET_RPC)
    if not rpc_env:
        rpc["evidence"] += (
            f" — via pinned public default {DEFAULT_TESTNET_RPC} "
            "(VERITAS_RPC_URL unset; setting it overrides)"
        )

    if fac_env:
        fac = _probe_http(fac_env.rstrip("/") + "/")
    else:
        fac = _probe_http(DEFAULT_FACILITATOR + "/supported")
        fac["evidence"] += (
            f" — via pinned public default {DEFAULT_FACILITATOR} "
            "(facilitator env unset; setting it overrides)"
        )

    return {
        "VERITAS_RPC_URL": rpc,
        "facilitator": fac,
        "wallet_key_configured": _probe_env("VERITAS_PRIVATE_KEY")
        if os.environ.get("VERITAS_PRIVATE_KEY")
        else _probe_env("VERITAS_BUYER_KEY"),
        # Funding cannot be proven without chain + address — leave honest,
        # but the path is permissionless: Circle faucet, 20 testnet USDC per
        # address per 2h, no account (proven 2026-08-09, fable/settlement/).
        "funded_testnet_wallet": {
            "status": "unknown",
            "evidence": "balance not probed; funding is permissionless "
            "(faucet.circle.com) — see docs/program/fable/STATE.md walkthrough",
        },
        "test_usdc": {
            "status": "unknown",
            "evidence": "balance not probed; permissionless faucet covers it",
        },
        "public_tls_host": {
            "status": "optional",
            "evidence": "not probed; optional for 0.1 (Stage-1 human residue)",
        },
        "pypi_trusted_publisher": {
            "status": "optional",
            "evidence": "human minutes: PyPI-side trusted-publisher config; "
            "agent-prepared 90%: .github/workflows/release.yml (tag-triggered)",
        },
    }


def write_checklist(
    probes: dict[str, dict[str, Any]],
    path: Path | None = None,
) -> Path:
    path = path or (
        Path.cwd() / "docs" / "program" / "ecosystem" / "unblock" / "CHECKLIST.md"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())
    rows = []
    for key, p in probes.items():
        rows.append(f"| {key} | {p['status']} | {p['evidence']} |")
    table = "\n".join(rows)
    required_ready = all(
        probes[k]["status"] == "yes"
        for k in ("VERITAS_RPC_URL", "facilitator")
        if k in probes
    )
    # Markdown checklist template only — not SQL. Bandit B608 false-positives on
    # the words "update" / "or" inside this f-string (CI security scan gate).
    body = (  # nosec B608
        f"""# Unblock CHECKLIST (living — refresh in place)

**Updated:** {ts} by `python -m veritas.unblock_probe`
**Rule:** Do **not** open a docs PR just to rewrite this file unless a required
row flips with new evidence. Settlement count lives with its evidence
(`docs/program/fable/settlement/`), never restated here (MIND §5).

## Probes

| Item | Status | Evidence |
|------|--------|----------|
{table}

## Required for Phase 0.1 dogfood

- Chain RPC responds (env **or** pinned public testnet default — env unset is
  not a block, MIND §3)
- Facilitator reachable (env **or** pinned public default)
- Funded wallet + test USDC (permissionless faucet; balance unconfirmed until
  a run spends it)

**Required automated ready?** {'**yes** (RPC+facilitator)' if required_ready else '**no**'}

## Next

If required automated ready → confer Overseer: singular product NEXT =
Phase 0.1 repeat / G9 routine reconcile (recipe: docs/program/fable/STATE.md).

```
PROPERTY: unblock checklist reflects live probes with sources labelled; no invented settle
EVIDENCE LEVEL: L1 (env/http probes) / L0 (funding balance)
NOT PROVEN: mainnet settlement; unsolicited buyers
```
"""
    )
    path.write_text(body, encoding="utf-8")
    return path


def main() -> None:
    probes = run_probes()
    path = write_checklist(probes)
    print(json.dumps({"checklist": str(path), "probes": probes}, indent=2))


if __name__ == "__main__":
    main()
