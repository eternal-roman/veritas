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


# --- X4: the resource a challenge names must be dialable ---------------------

def test_resource_is_an_absolute_url_when_a_public_url_is_configured(monkeypatch):
    """R2. x402 defines `resource` as the resource URL. We advertised the bare
    path `/v1/research`, which a facilitator or buyer matching on absolute URLs
    cannot resolve."""
    import importlib

    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://veritas.example.org")
    import veritas.server as server
    importlib.reload(server)

    assert server.resource_url() == "https://veritas.example.org/v1/research"


def test_live_mode_refuses_to_serve_without_a_public_url(monkeypatch, tmp_path):
    """Without a public URL we cannot name the resource honestly, so live mode
    is misconfiguration rather than a challenge nobody can match."""
    from veritas.payment_config import PaymentConfig

    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://veritas.test")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "1" * 40)
    monkeypatch.delenv("VERITAS_PUBLIC_URL", raising=False)
    cfg = PaymentConfig.from_env()
    assert cfg.mode == "misconfigured"
    assert any("PUBLIC_URL" in e for e in cfg.config_errors)


def test_free_mode_does_not_require_a_public_url(monkeypatch):
    from veritas.payment_config import PaymentConfig

    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.delenv("VERITAS_PUBLIC_URL", raising=False)
    assert PaymentConfig.from_env().mode == "free"


# --- X7: the work must fit inside the authorization it is paid by ------------

def test_deadline_budget_is_bounded_by_the_authorization_window():
    from veritas.deadline import Deadline

    d = Deadline.for_authorization(valid_before=1000, now=900, max_work_seconds=60)
    # 100s of authorization left, minus the safety margin, not the full 60s cap.
    assert 0 < d.seconds_remaining(now=900) <= 60


def test_deadline_refuses_when_the_window_is_already_too_short():
    """R4. Better to refuse before the work than to do it and settle against an
    expired authorization."""
    from veritas.deadline import Deadline, DeadlineTooShort

    with pytest.raises(DeadlineTooShort):
        Deadline.for_authorization(valid_before=1000, now=995, max_work_seconds=60)


def test_deadline_expires():
    from veritas.deadline import Deadline

    d = Deadline.for_authorization(valid_before=1000, now=900, max_work_seconds=30)
    assert d.expired(now=900) is False
    assert d.expired(now=1000) is True


def test_deadline_leaves_a_settlement_margin():
    """Time must remain to actually call settle after the work finishes."""
    from veritas.deadline import SETTLEMENT_MARGIN_SECONDS, Deadline

    d = Deadline.for_authorization(valid_before=1000, now=900, max_work_seconds=600)
    assert d.expires_at <= 1000 - SETTLEMENT_MARGIN_SECONDS


# --- X5 remainder: mainnet needs saying out loud -----------------------------

def test_agent_cli_refuses_mainnet_without_explicit_acknowledgement(tmp_path, monkeypatch):
    """O11. `--paid` on a mainnet network moves real money; it must not be
    reachable by a flag whose name does not say so."""
    from veritas.agent_cli import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr("veritas.server.main", lambda argv=None: None)
    with pytest.raises(SystemExit):
        main(["up", "--paid", "--network", "eip155:8453"])


def test_agent_cli_allows_mainnet_when_acknowledged(tmp_path, monkeypatch):
    pytest.importorskip("eth_account")
    from veritas.agent_cli import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://veritas.example.org")
    monkeypatch.setattr("veritas.server.main", lambda argv=None: None)
    assert main([
        "up", "--paid", "--network", "eip155:8453",
        "--i-understand-this-is-real-money",
    ]) == 0
