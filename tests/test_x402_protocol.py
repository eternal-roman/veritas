"""x402 protocol correctness: the parts that decide whether a payment can settle.

Two audited defects motivate this file.

* **R1** — the EIP-712 domain advertised in a challenge's `extra` was derived
  from the asset's *symbol* (`{"name": "USDC", "version": "2"}` for all twelve
  networks). The domain must match the deployed token's own `name()`/`version()`;
  where it does not, every signature a buyer produces is unsettleable. Nothing
  in the repository had ever checked a single deployment.
* **O11** — the default network was Base **mainnet**, so `veritas-agent up --paid`
  put a freshly generated, unfunded local keystore into live mainnet operation.

The rule: we advertise a network only when we can say where its domain came
from, and mainnet is never reached by default.
"""

from __future__ import annotations

import pytest

from veritas.x402 import (
    EIP712_DOMAINS,
    DomainVerification,
    advertisable_networks,
    build_payment_requirements,
    eip712_domain,
)


def test_domain_table_covers_every_settleable_asset():
    from veritas.x402 import USDC_ASSETS

    missing = set(USDC_ASSETS) - set(EIP712_DOMAINS)
    assert not missing, f"networks with a settlement asset but no domain entry: {missing}"


def test_every_domain_entry_declares_where_it_came_from():
    """An entry with no provenance is a guess, and a guess is what R1 was."""
    for network, entry in EIP712_DOMAINS.items():
        assert entry.name, network
        assert entry.version, network
        assert entry.source in DomainVerification.__members__.values(), network


def test_domain_is_not_derived_from_the_token_symbol():
    """R1. The regression: `name` came from `asset["symbol"]` for every chain."""
    import inspect

    from veritas import x402

    source = inspect.getsource(x402.build_payment_requirements)
    assert 'asset["symbol"]' not in source
    assert '"name": asset' not in source


def test_advertisable_networks_exclude_unverified_domains():
    """A network whose domain nobody checked is not offered for payment.

    Advertising it would produce challenges a buyer can sign but never settle,
    which is worse than advertising nothing — it wastes their gas and trust.
    """
    advertisable = set(advertisable_networks())
    for network, entry in EIP712_DOMAINS.items():
        if entry.source is DomainVerification.UNVERIFIED:
            assert network not in advertisable, (
                f"{network} has an unverified EIP-712 domain but is advertisable"
            )


def test_at_least_the_testnet_path_is_advertisable():
    assert "eip155:84532" in advertisable_networks(), "Base Sepolia must be payable"


def test_requirements_carry_the_pinned_domain_not_a_symbol():
    requirements = build_payment_requirements(
        pay_to="0x" + "1" * 40, network="eip155:84532",
        price="$0.01", resource="https://example.org/v1/research",
    )
    extra = requirements.to_dict()["extra"]
    pinned = eip712_domain("eip155:84532")
    assert extra["name"] == pinned.name
    assert extra["version"] == pinned.version


def test_building_requirements_for_an_unverified_network_is_refused():
    unverified = [
        network for network, entry in EIP712_DOMAINS.items()
        if entry.source is DomainVerification.UNVERIFIED
    ]
    if not unverified:
        pytest.skip("no unverified networks remain in the table")
    from veritas.x402 import PriceError

    with pytest.raises((PriceError, ValueError)):
        build_payment_requirements(
            pay_to="0x" + "1" * 40, network=unverified[0],
            price="$0.01", resource="https://example.org/v1/research",
        )


def test_default_network_is_a_testnet_not_base_mainnet():
    """O11. `veritas-agent up --paid` must not reach mainnet by default."""
    from veritas.networks import DEFAULT_NETWORK

    assert DEFAULT_NETWORK == "eip155:84532"


def test_mainnet_networks_are_identifiable_as_such():
    from veritas.networks import is_testnet

    assert is_testnet("eip155:84532") is True
    assert is_testnet("eip155:8453") is False
