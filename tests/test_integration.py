"""Smoke integration tests for core + autonomous layers."""

def test_hashing():
    from veritas.hashing import compute_content_hash, verify_content_hash
    h = compute_content_hash("hello")
    assert h.startswith("sha256:")
    ok, _ = verify_content_hash("hello", h)
    assert ok

def test_networks():
    from veritas.networks import normalize_network, CAIP2_NETWORKS
    assert normalize_network("base") == "eip155:8453"
    assert "eip155:8453" in CAIP2_NETWORKS.values()

def test_payment_config_free():
    from veritas.payment_config import PaymentConfig
    cfg = PaymentConfig.from_env()
    assert cfg.mode in ("free", "live", "misconfigured")
    assert isinstance(cfg.supported_networks, list)

def test_invalid_pay_to_does_not_become_live(monkeypatch):
    """A typo'd wallet previously passed the len>=20 check and went live,
    settling payments to an address nobody controls."""
    from veritas.payment_config import PaymentConfig
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
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

def test_control_plane_uses_shared_engine():
    """The control plane must not reimplement the pipeline."""
    from autonomous.control_plane import agent_research
    from veritas.schema import validate_response
    result = agent_research("What is the x402 protocol?")
    assert result["status"] in ("completed", "refused", "unavailable", "payment_required")
    if result["status"] != "payment_required":
        assert validate_response({k: v for k, v in result.items()}) == []
        assert result["human_required"] is False

def test_calibrator_reports_untrained_honestly():
    from autonomous.self_calibrator import SelfCalibrator
    c = SelfCalibrator()
    summary = c.summary()
    assert "is_trained" in summary
    # Untrained calibration must pass the value through unchanged.
    if not summary["is_trained"]:
        assert c.calibrate(0.77) == 0.77

if __name__ == "__main__":
    test_hashing()
    test_networks()
    test_payment_config_free()
    test_every_supported_network_has_a_settlement_asset()
    test_control_plane_uses_shared_engine()
    test_calibrator_reports_untrained_honestly()
    print("integration smoke tests passed")
