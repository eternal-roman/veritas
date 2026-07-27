"""CAIP-2 network identifiers supported by Veritas / x402."""

from __future__ import annotations
from typing import Dict, List

# Canonical CAIP-2 identifiers used by x402 v2
CAIP2_NETWORKS: Dict[str, str] = {
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

DEFAULT_NETWORK = "eip155:8453"  # Base mainnet
DEFAULT_TESTNET = "eip155:84532"  # Base Sepolia

def normalize_network(network: str) -> str:
    """Accept alias or CAIP-2 and return canonical CAIP-2."""
    if not network:
        return DEFAULT_NETWORK
    network = network.strip()
    if ":" in network:  # already CAIP-2-like
        return network
    return CAIP2_NETWORKS.get(network.lower(), network)

def supported_networks() -> List[str]:
    return list(CAIP2_NETWORKS.values())
