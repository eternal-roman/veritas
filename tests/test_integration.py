"""Constitution-pinned integration pins. Broader coverage lives in the
module tests (pipeline, payment, custody)."""

from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def test_invalid_pay_to_does_not_become_live(monkeypatch):
    """A typo'd wallet previously passed the len>=20 check and went live,
    settling payments to an address nobody controls."""
    from veritas.payment_config import PaymentConfig
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://veritas.test")
    monkeypatch.setenv("VERITAS_PAY_TO", "0xnot-a-real-address")
    cfg = PaymentConfig.from_env()
    assert cfg.mode == "misconfigured"
    assert cfg.is_live_ready() is False
    assert cfg.config_errors


def test_every_supported_network_has_a_settlement_asset():
    """A network we advertise but cannot settle on is an unpayable offer."""
    from veritas.payment_config import PaymentConfig
    from veritas.x402 import USDC_ASSETS
    cfg = PaymentConfig.from_env()
    unsettleable = [n for n in cfg.supported_networks if n not in USDC_ASSETS]
    assert not unsettleable, f"advertised but unsettleable networks: {unsettleable}"


def test_catalog_engine_is_signals_not_research(tmp_path, monkeypatch):
    """HTTP catalog pull and MCP list share veritas.signals (A1)."""
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)

    import veritas.server as server

    importlib.reload(server)
    client = TestClient(server.app)
    gone = client.post("/v1/research", json={"query": "anything at all"})
    assert gone.status_code == 410
    assert gone.json()["error"] == "product_removed"

    listed = client.get("/v1/signals")
    assert listed.status_code == 200
    assert listed.json()["method"] == "veritas.signals.v1"

    from veritas import mcp_server

    mcp_body = mcp_server.tool_signals_list()
    assert mcp_body["method"] == "veritas.signals.v1"


def test_payment_is_checked_before_work_is_done(monkeypatch, tmp_path):
    """An unpaid live-mode caller must not retrieve (A4)."""
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://veritas.test")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "ab" * 20)
    monkeypatch.setenv("VERITAS_NETWORK", "eip155:84532")

    import veritas.server as main_module
    importlib.reload(main_module)
    called: list[int] = []
    monkeypatch.setattr(
        main_module, "pull_signals", lambda *a, **k: called.append(1) or []
    )
    client = TestClient(main_module.app)
    response = client.post("/v1/signals", json={"query": "anything"})
    assert response.status_code == 402
    assert called == []


if __name__ == "__main__":
    test_every_supported_network_has_a_settlement_asset()
    print("integration smoke tests passed")
