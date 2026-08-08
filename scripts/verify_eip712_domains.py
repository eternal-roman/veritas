#!/usr/bin/env python3
"""Read each USDC contract's real EIP-712 domain and report table drift.

Why this exists: the challenge we publish tells a buyer which EIP-712 domain to
sign under. If that domain does not match the deployed token's own `name()` and
`version()`, the buyer's signature is valid-looking and unsettleable, and nobody
finds out until settlement fails. The repository previously derived the domain
from the asset symbol for all twelve networks without ever reading one contract.

`veritas/x402.py` now records provenance per network, and any network marked
UNVERIFIED is refused when building a challenge. This script is how an operator
with RPC access turns UNVERIFIED into ONCHAIN.

Usage:

    # one RPC per network you care about, CAIP-2 id -> URL
    export VERITAS_RPC_eip155_84532=https://sepolia.base.org
    export VERITAS_RPC_eip155_8453=https://mainnet.base.org
    python scripts/verify_eip712_domains.py

It prints, for each reachable network, the on-chain `name()`/`version()` beside
the pinned entry, and exits non-zero if any reachable network disagrees. It does
not edit the table: promoting an entry to ONCHAIN is a deliberate commit, made
by a person who saw the output.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

from veritas.safeurl import require_http_url
from veritas.x402 import EIP712_DOMAINS, USDC_ASSETS, DomainVerification

# keccak("name()")[:4] and keccak("version()")[:4]
NAME_SELECTOR = "0x06fdde03"
VERSION_SELECTOR = "0x54fd4d50"


def rpc_url(network: str) -> str | None:
    return os.getenv("VERITAS_RPC_" + network.replace(":", "_"))


def _eth_call(url: str, to: str, data: str) -> str | None:
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"],
    }).encode()
    request = urllib.request.Request(
        require_http_url(url), data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:  # nosec B310 - scheme checked
        payload = json.loads(response.read().decode())
    return payload.get("result")


def _decode_string(word: str | None) -> str | None:
    """Decode an ABI-encoded dynamic string returned by eth_call."""
    if not word or word == "0x":
        return None
    raw = bytes.fromhex(word[2:])
    if len(raw) < 64:
        return None
    length = int.from_bytes(raw[32:64], "big")
    return raw[64:64 + length].decode("utf-8", errors="replace") or None


def main() -> int:
    mismatches, checked, skipped = [], 0, []
    for network, asset in sorted(USDC_ASSETS.items()):
        url = rpc_url(network)
        pinned = EIP712_DOMAINS.get(network)
        if url is None:
            skipped.append(network)
            continue
        try:
            name = _decode_string(_eth_call(url, asset["address"], NAME_SELECTOR))
            version = _decode_string(_eth_call(url, asset["address"], VERSION_SELECTOR))
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            print(f"{network}: RPC error: {type(exc).__name__}")
            continue

        checked += 1
        agrees = pinned is not None and (name, version) == (pinned.name, pinned.version)
        status = "MATCHES" if agrees else "DIFFERS"
        pinned_desc = f"{pinned.name}/{pinned.version} ({pinned.source.value})" if pinned else "(no entry)"
        print(f"{network}: onchain {name!r}/{version!r} vs pinned {pinned_desc} -> {status}")
        if not agrees:
            mismatches.append(network)
        elif pinned and pinned.source is DomainVerification.UNVERIFIED:
            print(f"    promote {network} to DomainVerification.ONCHAIN with today's date")

    if skipped:
        print(f"\nskipped (no VERITAS_RPC_* set): {', '.join(skipped)}")
    print(f"\nchecked {checked} network(s); {len(mismatches)} mismatch(es)")
    if mismatches:
        print("A mismatch means every signature produced for that network is unsettleable.")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
