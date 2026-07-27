"""Wallet commitments and JIT packet integrity."""

import secrets

import pytest

from autonomous.jit_packet import (
    AgentIdentity,
    JITPacket,
    chain_packet,
    create_packet,
    verify_packet,
)
from autonomous.zk_wallet import (
    commit_wallet,
    open_commitment,
    prove,
    verify_commitment,
    verify_proof,
    verify_revealed,
)

ADDR = "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01"


def test_commitment_opens_correctly():
    wc, opening = commit_wallet(ADDR)
    assert verify_commitment(wc, opening)
    assert open_commitment(wc, opening) == ADDR


def test_public_commitment_leaks_neither_salt_nor_address():
    """The previous scheme published the blinding salt, making the commitment
    brute-forceable against any candidate address list."""
    wc, opening = commit_wallet(ADDR)
    public = wc.to_dict()
    assert "salt" not in public
    assert ADDR.lower() not in str(public).lower()
    assert opening.salt.hex() not in str(public)


def test_proof_requires_the_secret():
    wc, opening = commit_wallet(ADDR)
    challenge = secrets.token_bytes(16)
    assert verify_proof(wc, challenge, prove(opening, challenge), opening)


def test_forged_proof_rejected():
    """The old verifier checked only c == H(commitment||R), which any forger
    could satisfy without knowing the opening."""
    wc, opening = commit_wallet(ADDR)
    challenge = secrets.token_bytes(16)
    assert verify_proof(wc, challenge, "00" * 32, opening) is False


def test_proof_is_challenge_bound():
    wc, opening = commit_wallet(ADDR)
    proof = prove(opening, secrets.token_bytes(16))
    assert verify_proof(wc, secrets.token_bytes(16), proof, opening) is False


def test_static_challenge_rejected():
    _, opening = commit_wallet(ADDR)
    with pytest.raises(ValueError):
        prove(opening, b"")


def test_wrong_address_fails_reveal():
    wc, opening = commit_wallet(ADDR)
    assert verify_revealed(wc, opening.salt.hex(), ADDR) is True
    assert verify_revealed(wc, opening.salt.hex(), "0x" + "0" * 40) is False


def test_unsafe_stealth_derivation_removed():
    """Hash-derived addresses have no private key; funds sent there are burned."""
    from autonomous.zk_wallet import derive_stealth_address

    with pytest.raises(NotImplementedError):
        derive_stealth_address(b"x", b"y")


def test_agent_identity_stable_across_chain():
    """The docstring calls the agent id the only persistent identifier, but
    the prototype regenerated it per packet."""
    identity = AgentIdentity.create("veritas")
    p1 = create_packet(identity, payload={"q": "test"})
    p2 = chain_packet(p1, identity, payload={"r": "ok"})
    assert p1.agent_id == p2.agent_id
    assert p2.prev_packet_id == p1.packet_id
    assert p2.chain_root == p1.packet_id


def test_packet_signature_detects_tampering():
    identity = AgentIdentity.create()
    p = create_packet(identity, payload={"q": "test"})
    forged = JITPacket.decode(p.encode())
    forged.payload = {"q": "tampered"}
    assert forged.verify_signature(identity.signing_key) is False


def test_expired_packet_rejected():
    """expires_at was previously written and never read."""
    identity = AgentIdentity.create()
    expired = create_packet(identity, ttl_seconds=-1)
    assert expired.is_expired() is True
    ok, reason = verify_packet(expired, identity.signing_key)
    assert (ok, reason) == (False, "expired")


def test_chain_hash_mismatch_rejected():
    identity = AgentIdentity.create()
    p1 = create_packet(identity, payload={"q": "one"})
    p2 = chain_packet(p1, identity, payload={"r": "two"})
    impostor = create_packet(identity, payload={"q": "different"})
    ok, reason = verify_packet(p2, identity.signing_key, prev=impostor)
    assert ok is False
    assert reason in ("chain_id_mismatch", "chain_hash_mismatch")


def test_valid_chain_verifies():
    identity = AgentIdentity.create()
    p1 = create_packet(identity, payload={"q": "one"})
    p2 = chain_packet(p1, identity, payload={"r": "two"})
    assert verify_packet(p2, identity.signing_key, prev=p1) == (True, "ok")
