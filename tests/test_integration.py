"""Smoke integration tests for core + autonomous layers."""

def test_hashing():
    from veritas.hashing import compute_content_hash, verify_content_hash, content_hash
    h = compute_content_hash("hello")
    assert h == content_hash("hello")
    ok, _ = verify_content_hash("hello", h)
    assert ok

def test_networks():
    from veritas.networks import normalize_network, CAIP2_NETWORKS
    assert normalize_network("base") == "eip155:8453"
    assert "eip155:8453" in CAIP2_NETWORKS.values()

def test_payment_config_free():
    from veritas.payment_config import PaymentConfig
    cfg = PaymentConfig.from_env()
    assert cfg.mode in ("free", "live")
    assert isinstance(cfg.supported_networks, list)

def test_zk_commitment():
    from autonomous.zk_wallet import commit_wallet, verify_commitment, open_commitment
    addr = "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01"
    wc, opening = commit_wallet(addr, network="eip155:8453")
    assert verify_commitment(wc)
    assert verify_commitment(wc, claimed_address=addr)
    assert open_commitment(wc, opening) == addr.lower() or open_commitment(wc, opening) == addr

def test_jit_packet():
    from autonomous.jit_packet import create_packet, chain_packet
    p1 = create_packet(pay_to="0xabc", payload={"q": "test"})
    assert p1.packet_id.startswith("pkt:")
    assert p1.agent_id.startswith("sid:")
    p2 = chain_packet(p1, payload={"r": "ok"})
    assert p2.prev_packet_id == p1.packet_id

if __name__ == "__main__":
    test_hashing()
    test_networks()
    test_payment_config_free()
    test_zk_commitment()
    test_jit_packet()
    print("integration smoke tests passed")
