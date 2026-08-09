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


def _probe_env(name: str) -> dict[str, Any]:
    val = os.environ.get(name)
    if not val:
        return {"status": "no", "evidence": f"{name} unset"}
    # Never echo secrets
    return {"status": "yes", "evidence": f"{name} set (len={len(val)})"}


def _probe_http(url: str, timeout: float = 3.0) -> dict[str, Any]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            code = getattr(resp, "status", None) or resp.getcode()
        return {"status": "yes", "evidence": f"HTTP {code} from {url}"}
    except urllib.error.HTTPError as e:
        # Reachable enough to get HTTP error
        return {"status": "partial", "evidence": f"HTTP {e.code} from {url}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "no", "evidence": f"{type(e).__name__}: {e}"}


def _probe_rpc(url: str | None, timeout: float = 3.0) -> dict[str, Any]:
    if not url:
        return {"status": "no", "evidence": "VERITAS_RPC_URL unset"}
    body = json.dumps(
        {"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1}
    ).encode("utf-8")
    try:
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        chain = data.get("result", "?")
        return {"status": "yes", "evidence": f"eth_chainId={chain}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "no", "evidence": f"{type(e).__name__}: {e}"}


def run_probes() -> dict[str, dict[str, Any]]:
    rpc = os.environ.get("VERITAS_RPC_URL")
    fac = os.environ.get("VERITAS_FACILITATOR_URL") or os.environ.get(
        "X402_FACILITATOR_URL"
    )
    return {
        "VERITAS_RPC_URL": _probe_rpc(rpc),
        "facilitator": (
            _probe_http(fac.rstrip("/") + "/")
            if fac
            else {"status": "no", "evidence": "facilitator URL unset"}
        ),
        "wallet_key_configured": _probe_env("VERITAS_PRIVATE_KEY")
        if os.environ.get("VERITAS_PRIVATE_KEY")
        else _probe_env("VERITAS_BUYER_KEY"),
        # Funding cannot be proven without chain + address — leave honest.
        "funded_testnet_wallet": {
            "status": "unknown",
            "evidence": "requires human confirmation of faucet balance",
        },
        "test_usdc": {
            "status": "unknown",
            "evidence": "requires human confirmation of USDC balance",
        },
        "public_tls_host": {
            "status": "optional",
            "evidence": "not probed; optional for 0.1",
        },
        "pypi_trusted_publisher": {
            "status": "optional",
            "evidence": "human ops; not required for 0.1",
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
    body = f"""# Unblock CHECKLIST (living — update in place)

**Updated:** {ts} by `python -m veritas.unblock_probe`
**Rule:** Do **not** open a docs PR just to rewrite this file unless a required
row flips with new evidence. Product settle remains **0** until 0.1 dogfood.

## Probes

| Item | Status | Evidence |
|------|--------|----------|
{table}

## Required for Phase 0.1 dogfood

- `VERITAS_RPC_URL` → **yes** and chain responds
- Facilitator URL reachable
- Funded wallet + test USDC (human)

**Required automated ready?** {'**yes** (RPC+facilitator)' if required_ready else '**no**'}

## Next

If required automated ready **and** human confirms funding → confer Overseer:
singular product NEXT = Phase 0.1 / G9 dogfood.

```
PROPERTY: unblock checklist reflects probes; no invent settle
EVIDENCE LEVEL: L1 (env/http probes) / L0 (funding)
NOT PROVEN: on-chain settlement success
```
"""
    path.write_text(body, encoding="utf-8")
    return path


def main() -> None:
    probes = run_probes()
    path = write_checklist(probes)
    print(json.dumps({"checklist": str(path), "probes": probes}, indent=2))


if __name__ == "__main__":
    main()
