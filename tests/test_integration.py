"""Constitution-pinned integration pins. Broader coverage lives in the
module tests (pipeline, payment, custody)."""

from __future__ import annotations

import importlib

from fastapi.testclient import TestClient

from veritas.pipeline import run_research as real_run_research
from veritas.schema import validate_response


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


def test_control_plane_uses_shared_engine(tmp_path, monkeypatch):
    """HTTP and MCP both call veritas.pipeline.run_research (A1).

    The node id stays so constitution A1 does not need a version bump. The
    body used to only run the pipeline once in-process — that would pass
    with a second engine still on the served path.
    """
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_OBSERVE_URLS", "0")
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    monkeypatch.delenv("VERITAS_PUBLIC_URL", raising=False)

    calls: list[str] = []

    def spy(query, **kwargs):
        calls.append(query)
        kwargs["allow_network"] = False
        return real_run_research(query, **kwargs)

    import veritas.pipeline as pipeline
    monkeypatch.setattr(pipeline, "run_research", spy)

    import veritas.server as server
    importlib.reload(server)
    monkeypatch.setattr(server, "run_research", spy)

    client = TestClient(server.app)
    query = "What is the x402 protocol?"
    response = client.post("/v1/research", json={"query": query})
    assert response.status_code == 200
    http_body = response.json()
    assert validate_response(http_body) == []
    assert http_body["status"] in ("completed", "refused", "unavailable")
    assert query in calls

    from veritas import mcp_server

    before = len(calls)
    mcp_body = mcp_server.tool_research(query, allow_network=False)
    assert validate_response(mcp_body) == []
    assert mcp_body["status"] in ("completed", "refused", "unavailable")
    assert len(calls) == before + 1


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
        main_module, "run_research", lambda *a, **k: called.append(1) or {}
    )
    client = TestClient(main_module.app)
    response = client.post("/v1/research", json={"query": "anything"})
    assert response.status_code == 402
    assert called == []


if __name__ == "__main__":
    test_every_supported_network_has_a_settlement_asset()
    print("integration smoke tests passed")
