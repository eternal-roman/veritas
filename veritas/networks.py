"""CAIP-2 network identifiers supported by Veritas / x402."""

from __future__ import annotations

# Canonical CAIP-2 identifiers used by x402 v2
CAIP2_NETWORKS: dict[str, str] = {
    # EVM
    "ethereum": "eip155:1",
    "ethereum-sepolia": "eip155:11155111",
    "base": "eip155:8453",
    "base-sepolia": "eip155:84532",
    "polygon": "eip155:137",
    "polygon-amoy": "eip155:80002",
    "arbitrum": "eip155:42161",
    "arbitrum-sepolia": "eip155:421614",
    "optimism": "eip155:10",
    "avalanche": "eip155:43114",
    "avalanche-fuji": "eip155:43113",
    "world": "eip155:480",
    # Solana
    "solana": "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",
    "solana-devnet": "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1",
}

# Reverse lookup
CAIP2_TO_ALIAS = {v: k for k, v in CAIP2_NETWORKS.items()}

# CAIP-2 ids that carry real money. Used to require an explicit opt-in before a
# deployment can reach one.
MAINNET_NETWORKS = frozenset({
    "eip155:1", "eip155:8453", "eip155:137", "eip155:42161",
    "eip155:10", "eip155:43114", "eip155:480",
    "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",
})


def is_testnet(network: str) -> bool:
    """True when the network is not one that moves real funds."""
    return normalize_network(network) not in MAINNET_NETWORKS

# Base Sepolia, deliberately. The default used to be Base mainnet, so
# `veritas-agent up --paid` put a freshly generated, unfunded local keystore
# straight into live mainnet operation with no confirmation step.
DEFAULT_NETWORK = "eip155:84532"  # Base Sepolia
DEFAULT_TESTNET = "eip155:84532"  # Base Sepolia

def normalize_network(network: str) -> str:
    """Accept alias or CAIP-2 and return canonical CAIP-2."""
    if not network:
        return DEFAULT_NETWORK
    network = network.strip()
    if ":" in network:  # already CAIP-2-like
        return network
    return CAIP2_NETWORKS.get(network.lower(), network)

def supported_networks() -> list[str]:
    """Networks we can actually settle on.

    Derived from the settlement asset table rather than the alias table, which
    is the single source of truth for payability. Previously this returned
    every alias — including Solana and testnets with no configured USDC asset —
    so `/.well-known/x402` advertised networks on which a 402 challenge could
    not even be constructed. An offer you cannot fulfil is worse than no offer.
    """
    from .x402 import USDC_ASSETS

    return [net for net in CAIP2_NETWORKS.values() if net in USDC_ASSETS]


def is_settleable(network: str) -> bool:
    from .x402 import USDC_ASSETS

    return normalize_network(network) in USDC_ASSETS
