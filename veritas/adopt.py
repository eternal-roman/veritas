"""Machine adopt card: what a directed agent fetches and runs.

Committed ``adopt.json`` is this document with no public seller. Live
``GET /adopt.json`` overlays ``VERITAS_PUBLIC_URL`` when set. Registry
listing stays false until a real Bazaar/ERC-8004 write exists.
"""

from __future__ import annotations

import os
from typing import Any

from veritas.funding_proof import FAUCET_URL

ADOPT_SCHEMA = "veritas.adopt.v1"
REPO_URL = "https://github.com/eternal-roman/veritas"
RAW_CARD = "https://raw.githubusercontent.com/eternal-roman/veritas/main/adopt.json"
INSTALL = 'pip install "veritas-research[signing] @ git+https://github.com/eternal-roman/veritas"'


def build_adopt_card(*, public_url: str | None = None) -> dict[str, Any]:
    if public_url is None:
        public_url = (os.environ.get("VERITAS_PUBLIC_URL") or "").strip() or None
    if public_url:
        public_url = public_url.rstrip("/")

    https = bool(public_url and public_url.startswith("https://"))
    return {
        "schema": ADOPT_SCHEMA,
        "name": "Veritas Research",
        "repository": REPO_URL,
        "raw_card": RAW_CARD,
        "public_seller": public_url,
        "listed_in_repo": True,
        "listed_on_registry": False,
        "funded_by_enroll": False,
        "identity_resolves_off_box": https,
        "identity_portable": (
            "did:pkh + EIP-191 card signed by the commerce wallet; "
            "verify the JSON anywhere. ERC-8004 is not implemented."
        ),
        "workflow": [
            {
                "id": "install",
                "command": INSTALL,
                "note": "signing extra creates the USDC-capable keystore",
            },
            {
                "id": "adopt",
                "command": (
                    "veritas-agent adopt --id self --interests research,buy,verify"
                ),
                "note": "creates commerce wallet and a signed did:pkh card",
            },
            {
                "id": "fund",
                "command": f"veritas-agent fund-proof  # after {FAUCET_URL}",
                "note": (
                    "Circle faucet needs a human (reCAPTCHA). fund-proof "
                    "records USDC Transfer custody; enroll does not fund."
                ),
            },
            {
                "id": "sell",
                "command": "veritas-agent up --paid --network eip155:84532",
                "note": (
                    "public TLS is optional for stranger discovery; "
                    "local/LAN A2A works with --allow-local"
                ),
            },
            {
                "id": "connect",
                "command": "veritas-agent connect <peer-url> [--allow-local]",
                "note": "another agent self-hosts; no central network",
            },
            {
                "id": "buy",
                "command": "veritas-buy <seller-url>",
                "note": "does not settle; payer/money_loop settle",
            },
        ],
        "when_public_url": {
            "discovery": "/.well-known/x402",
            "identity": "/v1/identity",
            "whoami_http": "/v1/operator",
            "adopt": "/adopt.json",
        },
        "honesty": {
            "unsolicited_buyers": 0,
            "mainnet_settlements": 0,
            "erc8004": False,
            "bazaar": False,
        },
    }
