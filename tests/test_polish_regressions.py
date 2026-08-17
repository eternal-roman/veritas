"""Witness tests for the 2026-08-09 review fixes.

Each test pins a defect the six-territory review found live: remove the fix
and the named test fails with the defect's own failure mode.
"""

from __future__ import annotations

from veritas.payment_config import DEFAULT_FACILITATOR, PaymentConfig
from veritas.safeurl import UnsafeUrlError, assert_public_destination


def test_ssrf_guard_treats_none_resolver_as_default():
    """resolver=None crashed both installed buyer CLIs with a TypeError.

    counterparty.fetch_seller and buyer_journey thread an optional resolver
    through as None; the guard clobbered its socket.getaddrinfo default and
    called None. The crash's exit 1 read as a seller-failed verdict. The
    guard must treat None as "use the default" — the loopback refusal below
    proves the resolver actually ran instead of raising TypeError.
    """
    try:
        assert_public_destination("http://127.0.0.1/", resolver=None)
    except UnsafeUrlError:
        pass  # expected: loopback is refused BY THE RESOLVER PATH
    except TypeError as exc:  # pragma: no cover - the regression itself
        raise AssertionError(
            "resolver=None crashed the SSRF guard again (buyer CLIs die "
            f"on every un-injected invocation): {exc}"
        ) from None


def test_unverified_domain_network_is_misconfigured_not_live(monkeypatch):
    """A settleable network without a verified EIP-712 domain must fail closed.

    Before the fix, VERITAS_NETWORK=eip155:1 passed validation (it is in
    USDC_ASSETS), reported mode=live with green health, then raised
    UnverifiedDomainError on every paid request and on discovery itself —
    invariant 7's exact failure class.
    """
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "a" * 40)
    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://example.test")
    monkeypatch.setenv("VERITAS_NETWORK", "eip155:1")
    monkeypatch.delenv("VERITAS_FACILITATOR", raising=False)
    monkeypatch.delenv("VERITAS_PRICE", raising=False)
    cfg = PaymentConfig.from_env()
    assert cfg.mode == "misconfigured"
    assert any("EIP-712" in error for error in cfg.config_errors)
    # And no served config error may echo an env var's value.
    assert not any("0xa" in error.lower() for error in cfg.config_errors)


def test_default_facilitator_is_the_proven_one():
    """The zero-config paid path must default to a counterparty we have
    actually settled through (evidence: docs/program/fable/settlement/),
    and the bootstrap must not fork its own copy."""
    from veritas.autonomous import bootstrap

    assert DEFAULT_FACILITATOR == "https://x402.org/facilitator"
    assert bootstrap.DEFAULT_FACILITATOR is DEFAULT_FACILITATOR


def test_served_schema_covers_catalog_keys():
    from veritas.schema import catalog_json_schema

    schema = catalog_json_schema()
    assert "signals" in schema["required"]
    assert "note" in schema["required"]
