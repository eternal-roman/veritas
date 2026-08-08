"""x402 protocol types: price parsing, atomic amounts, and challenge construction.

The previous 402 response advertised `maxAmountRequired: "$0.25"`. The x402
spec requires an atomic on-chain amount as a decimal string (USDC has 6
decimals, so $0.25 is "250000"). A conforming client parsing "$0.25" as an
integer fails outright, so the old challenge could not be paid by any real
x402 buyer — the payment path was unreachable in principle, not just unwired.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

X402_VERSION = 1

# Canonical USDC deployments per CAIP-2 network, with decimals.
USDC_ASSETS: dict[str, dict[str, Any]] = {
    # Mainnets
    "eip155:1": {"address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "decimals": 6, "symbol": "USDC"},
    "eip155:8453": {"address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "decimals": 6, "symbol": "USDC"},
    "eip155:137": {"address": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", "decimals": 6, "symbol": "USDC"},
    "eip155:42161": {"address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", "decimals": 6, "symbol": "USDC"},
    "eip155:10": {"address": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85", "decimals": 6, "symbol": "USDC"},
    "eip155:43114": {"address": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E", "decimals": 6, "symbol": "USDC"},
    "eip155:480": {"address": "0x79A02482A880bCE3F13e09Da970dC34db4CD24d1", "decimals": 6, "symbol": "USDC"},
    # Testnets
    "eip155:84532": {"address": "0x036CbD53842c5426634e7929541eC2318f3dCF7e", "decimals": 6, "symbol": "USDC"},
    "eip155:11155111": {"address": "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238", "decimals": 6, "symbol": "USDC"},
    "eip155:80002": {"address": "0x41E94Eb019C0762f9Bfcf9Fb1E58725BfB0e7582", "decimals": 6, "symbol": "USDC"},
    "eip155:421614": {"address": "0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d", "decimals": 6, "symbol": "USDC"},
    "eip155:43113": {"address": "0x5425890298aed601595a70AB815c96711a31Bc65", "decimals": 6, "symbol": "USDC"},
}

# Networks recognised for alias resolution but NOT advertised as payable.
# Solana settlement uses SPL token accounts and a different payload shape than
# the EVM `exact` scheme implemented here; advertising it would publish an
# offer no buyer could actually fulfil.
UNSUPPORTED_SETTLEMENT = {
    "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp": "solana_spl_not_implemented",
    "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1": "solana_spl_not_implemented",
}

DEFAULT_DECIMALS = 6


class DomainVerification(str, Enum):
    """Where an EIP-712 domain value came from. This is the whole point.

    The previous code derived the domain name from the asset symbol for every
    chain at once. The domain must match the deployed token's own `name()` and
    `version()`; where it does not, the buyer's signature is unsettleable and the
    failure is silent. Recording provenance is what stops a guess being mistaken
    for a fact.
    """

    ONCHAIN = "onchain"          # read from the deployed contract, with a date
    REFERENCE_IMPL = "reference" # matches the x402 reference implementation
    UNVERIFIED = "unverified"    # nobody has checked; not advertisable


@dataclass(frozen=True)
class Eip712Domain:
    name: str
    version: str
    source: DomainVerification
    verified_at: str | None = None
    note: str | None = None


# The EIP-712 domain each network's USDC contract signs under.
#
# Only Base and Base Sepolia are populated from the x402 reference
# implementation, which is the basis the ecosystem's own clients use. Everything
# else is UNVERIFIED: this repository has never read `name()`/`version()` from
# those contracts, and `scripts/verify_eip712_domains.py` exists to do that from
# an environment with RPC access. Until then those networks are not advertised —
# an offer a buyer can sign but never settle is worse than no offer at all.
EIP712_DOMAINS: dict[str, Eip712Domain] = {
    "eip155:8453": Eip712Domain(
        "USDC", "2", DomainVerification.REFERENCE_IMPL,
        note="Base mainnet USDC as used by the x402 reference implementation",
    ),
    "eip155:84532": Eip712Domain(
        "USDC", "2", DomainVerification.REFERENCE_IMPL,
        note="Base Sepolia USDC as used by the x402 reference implementation",
    ),
    **{
        network: Eip712Domain(
            "USDC", "2", DomainVerification.UNVERIFIED,
            note="never read from chain; run scripts/verify_eip712_domains.py",
        )
        for network in (
            "eip155:1", "eip155:137", "eip155:42161", "eip155:10",
            "eip155:43114", "eip155:480", "eip155:11155111",
            "eip155:80002", "eip155:421614", "eip155:43113",
        )
    },
}


class UnverifiedDomainError(ValueError):
    """Raised when a challenge is requested for a network we cannot vouch for."""


def eip712_domain(network: str) -> Eip712Domain:
    domain = EIP712_DOMAINS.get(network)
    if domain is None:
        raise UnverifiedDomainError(f"no EIP-712 domain recorded for {network!r}")
    return domain


def advertisable_networks() -> list[str]:
    """Networks we will publish an offer for: settleable AND domain-verified."""
    return sorted(
        network for network in USDC_ASSETS
        if EIP712_DOMAINS.get(network, Eip712Domain("", "", DomainVerification.UNVERIFIED)).source
        is not DomainVerification.UNVERIFIED
    )


class PriceError(ValueError):
    """Raised when a configured price cannot be converted to atomic units."""


def parse_price(price: str) -> Decimal:
    """Parse a human price string ('$0.25', '0.25', 'USD 0.25') to a Decimal."""
    if price is None:
        raise PriceError("price is required")
    cleaned = str(price).strip().upper().replace("USDC", "").replace("USD", "").replace("$", "").strip()
    if not cleaned:
        raise PriceError(f"unparseable price: {price!r}")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise PriceError(f"unparseable price: {price!r}") from exc
    if value <= 0:
        raise PriceError(f"price must be positive: {price!r}")
    return value


def to_atomic_amount(price: str, network: str) -> str:
    """Convert a human price to the atomic string x402 requires."""
    asset = USDC_ASSETS.get(network)
    decimals = asset["decimals"] if asset else DEFAULT_DECIMALS
    value = parse_price(price)
    atomic = int(value * (Decimal(10) ** decimals))
    if atomic <= 0:
        raise PriceError(f"price {price!r} rounds to zero atomic units on {network}")
    return str(atomic)


@dataclass
class PaymentRequirements:
    """One entry in the 402 `accepts` array."""
    scheme: str
    network: str
    maxAmountRequired: str
    resource: str
    description: str
    payTo: str
    asset: str
    mimeType: str = "application/json"
    maxTimeoutSeconds: int = 60
    extra: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if data.get("extra") is None:
            data.pop("extra")
        return data


def build_payment_requirements(
    pay_to: str,
    network: str,
    price: str,
    resource: str,
    description: str = "High-assurance evidence-backed research via Veritas",
) -> PaymentRequirements:
    asset = USDC_ASSETS.get(network)
    if asset is None:
        raise PriceError(
            f"no known settlement asset for network {network!r}; "
            f"supported: {sorted(USDC_ASSETS)}"
        )

    # A network we can settle on may still have an EIP-712 domain nobody has
    # checked. Refuse rather than publish a challenge whose signature cannot
    # settle: the buyer would spend effort producing a useless authorization,
    # and the failure would surface only at settlement.
    domain = eip712_domain(network)
    if domain.source is DomainVerification.UNVERIFIED:
        raise UnverifiedDomainError(
            f"refusing to build a challenge for {network!r}: its USDC EIP-712 "
            "domain has never been verified against the deployed contract "
            "(run scripts/verify_eip712_domains.py)"
        )

    return PaymentRequirements(
        scheme="exact",
        network=network,
        maxAmountRequired=to_atomic_amount(price, network),
        resource=resource,
        description=description,
        payTo=pay_to,
        asset=asset["address"],
        extra={"name": domain.name, "version": domain.version},
    )


def build_402_challenge(
    pay_to: str,
    network: str,
    price: str,
    resource: str,
    error: str = "X-PAYMENT header is required",
) -> dict[str, Any]:
    """Construct a spec-shaped 402 body."""
    requirements = build_payment_requirements(pay_to, network, price, resource)
    return {
        "x402Version": X402_VERSION,
        "error": error,
        "accepts": [requirements.to_dict()],
    }


def decode_payment_header(raw: str) -> dict[str, Any] | None:
    """Decode a base64-JSON X-PAYMENT header, tolerating raw JSON.

    Returns None when the header cannot be interpreted, which every caller
    treats as an invalid payment (fail closed). This is the one decode path:
    the HTTP surface and the agent-native simulator both use it, so their
    notion of "well-formed" cannot drift apart.
    """
    if not raw:
        return None
    try:
        decoded = base64.b64decode(raw, validate=True).decode("utf-8")
        payload = json.loads(decoded)
        return payload if isinstance(payload, dict) else None
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        pass
    try:
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        return None


def payment_authorization(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extract the authorization object from a decoded x402 payment payload.

    Tolerates both the nested spec shape (payload.payload.authorization) and
    a flat authorization key. Returns None when no authorization dict exists
    — the structural minimum for a payment to be worth verifying.
    """
    inner = payload.get("payload")
    if isinstance(inner, dict):
        auth = inner.get("authorization")
        if isinstance(auth, dict):
            return auth
    auth = payload.get("authorization")
    return auth if isinstance(auth, dict) else None


#: An EIP-3009 authorization nonce: 32 bytes, hex, 0x-prefixed.
NONCE_RE = re.compile(r"0x[0-9a-fA-F]{64}")


def extract_nonce(payment_payload: Any) -> str | None:
    """Pull the authorization nonce out of a decoded X-PAYMENT payload.

    Tolerates the shapes seen in the wild: nested under
    ``payload.authorization`` (the x402 exact scheme) or hoisted to the top of
    the payload. Returns None when no well-formed nonce is present — the
    caller decides what that means, because a missing nonce is a malformed
    payment, not a replay.

    The nonce identifies one single-use payment authorization, which is why
    `veritas.ledger` keys the whole delivery/settlement state machine on it.
    """
    if not isinstance(payment_payload, dict):
        return None
    candidates: list[Any] = []
    authorization = payment_authorization(payment_payload)
    if authorization is not None:
        candidates.append(authorization.get("nonce"))
    inner = payment_payload.get("payload")
    if isinstance(inner, dict):
        candidates.append(inner.get("nonce"))
    candidates.append(payment_payload.get("nonce"))
    for candidate in candidates:
        if isinstance(candidate, str) and NONCE_RE.fullmatch(candidate):
            return candidate.lower()
    return None
