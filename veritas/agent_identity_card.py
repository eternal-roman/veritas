"""Portable ecosystem identity: did:pkh + EIP-191 over the commerce key.

The agent creates a USDC-capable wallet and signs a card binding agent_id to
that address. Anyone with the JSON can recover the signer — no host, no
ERC-8004 registry. That is off-box *verification*, not off-box *resolution*.

Honesty bound:
- Not ERC-8004. Not a W3C-registered DID method. Not a Bazaar listing.
- ``did:pkh`` is the CAIP-10 account id; the wallet *is* the identity key.
- ``did_plane`` on the card is a bound label (usually the same ``did:pkh``).
  It is not a second verifier and not an HMAC ticket.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

IDENTITY_SCHEMA = "veritas.agent.ecosystem_identity.v1"
MESSAGE_VERSION = "veritas-agent-identity-v1"
BIND_KEYS = (
    "schema",
    "message_version",
    "agent_id",
    "did_plane",
    "did_pkh",
    "commerce_address",
    "network",
)


class IdentityCardError(ValueError):
    """Identity card could not be issued or verified."""


def did_pkh_for(network: str, address: str) -> str:
    return f"did:pkh:{network}:{address.lower()}"


def canonical_identity_message(body: dict[str, Any]) -> str:
    bound = {key: body[key] for key in BIND_KEYS}
    return json.dumps(bound, sort_keys=True, separators=(",", ":"))


def issue_identity_card(
    *,
    agent_id: str,
    did_plane: str,
    commerce_address: str,
    network: str,
    sign_text: Callable[[str], str],
) -> dict[str, Any]:
    address = commerce_address.lower()
    if not _ADDRESS_RE.match(commerce_address):
        raise IdentityCardError("commerce_address must be 0x-prefixed 20-byte hex")
    body: dict[str, Any] = {
        "schema": IDENTITY_SCHEMA,
        "message_version": MESSAGE_VERSION,
        "agent_id": agent_id,
        "did_plane": did_plane,
        "did_pkh": did_pkh_for(network, address),
        "commerce_address": address,
        "network": network,
        "not_erc8004": True,
        "not_registry_listing": True,
        "note": (
            "EIP-191 personal_sign over the bound fields; recover the signer "
            "to check the wallet. Not ERC-8004. Not a public listing."
        ),
    }
    message = canonical_identity_message(body)
    body["message"] = message
    body["signature"] = sign_text(message)
    return body


def verify_identity_card(card: dict[str, Any]) -> tuple[bool, str]:
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError:
        return False, "eth_account required to verify"

    if not isinstance(card, dict) or card.get("schema") != IDENTITY_SCHEMA:
        return False, "unrecognized schema"
    try:
        message = canonical_identity_message(card)
    except KeyError as exc:
        return False, f"missing field: {exc}"
    if card.get("message") != message:
        return False, "message does not match bound fields"
    signature = card.get("signature")
    if not isinstance(signature, str) or not signature.startswith("0x"):
        return False, "signature missing"
    try:
        recovered = Account.recover_message(
            encode_defunct(text=message), signature=signature
        )
    except Exception as exc:  # eth_account raises varied types
        return False, f"recovery failed: {type(exc).__name__}"
    expect = str(card.get("commerce_address") or "").lower()
    if recovered.lower() != expect:
        return False, f"signer {recovered.lower()} != {expect}"
    expect_did = did_pkh_for(str(card.get("network") or ""), expect)
    if card.get("did_pkh") != expect_did:
        return False, "did_pkh does not match address/network"
    return True, "ok"
