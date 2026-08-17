"""VCAE: EIP-3009 authorization as the lock (G12 / W1).

Constitution pointer:
`test_settle_forfeit_submits_locked_authorization`.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from veritas.escrow import (
    BOND_BINDING_ESCROW,
    KIND_CHALLENGE_STAKE,
    METHOD,
    STATE_SETTLING,
    EscrowError,
    EscrowStore,
    canonical_authorization,
    escrow_bond,
    escrow_stake,
    settle_forfeit,
)
from veritas.facilitator import SettlementResult, SimulatedFacilitatorClient

NETWORK = "eip155:84532"


def _auth(**overrides) -> dict[str, str]:
    body = {
        "from": "0x" + "11" * 20,
        "to": "0x" + "22" * 20,
        "value": "250000",
        "validAfter": "0",
        "validBefore": "9999999999",
        "nonce": "0x" + "ab" * 32,
        "signature": "0x" + "cd" * 65,
    }
    body.update(overrides)
    return body


def test_canonical_authorization_refuses_malformed():
    with pytest.raises(EscrowError, match="authorization_malformed"):
        canonical_authorization("not-a-dict")  # type: ignore[arg-type]
    with pytest.raises(EscrowError, match="authorization_malformed:from"):
        canonical_authorization({**_auth(), "from": ""})
    with pytest.raises(EscrowError, match="authorization_malformed:address"):
        canonical_authorization({**_auth(), "to": "0xnotanaddress"})
    with pytest.raises(EscrowError, match="authorization_malformed:value"):
        canonical_authorization({**_auth(), "value": "0"})
    with pytest.raises(EscrowError, match="authorization_malformed:nonce"):
        canonical_authorization({**_auth(), "nonce": "0xzz"})


def test_lock_get_roundtrip_and_nonce_replay(tmp_path):
    store = EscrowStore(tmp_path)
    lock = escrow_bond(_auth(), network=NETWORK, store=store)
    assert lock["state"] == "locked"
    assert lock["binding"] == BOND_BINDING_ESCROW
    assert lock["method"] == METHOD
    assert lock["amount"] == "250000"
    assert store.get(lock["lock_id"])["nonce"] == _auth()["nonce"]
    with pytest.raises(EscrowError, match="authorization_nonce_already_locked"):
        escrow_bond(_auth(), network=NETWORK, store=store)


def test_unknown_network_and_expired_auth_are_refused(tmp_path):
    store = EscrowStore(tmp_path)
    with pytest.raises(EscrowError, match="network_unknown"):
        escrow_bond(_auth(), network="eip155:999", store=store)
    with pytest.raises(EscrowError, match="authorization_expired"):
        escrow_bond(_auth(validBefore="1"), network=NETWORK, store=store)


def test_release_never_submits_and_blocks_forfeit(tmp_path):
    store = EscrowStore(tmp_path)
    lock = escrow_bond(_auth(nonce="0x" + "11" * 32), network=NETWORK, store=store)
    released = store.release(lock["lock_id"])
    assert released["state"] == "released"
    with pytest.raises(EscrowError, match="lock_not_locked:released"):
        settle_forfeit(
            released,
            outcome={"outcome": "fired", "reason": "predicate_fired"},
            facilitator=SimulatedFacilitatorClient(),
            store=store,
        )


def test_expire_due_never_submits(tmp_path):
    store = EscrowStore(tmp_path)
    import time
    from datetime import datetime, timezone

    soon = str(int(time.time()) + 30)
    lock = escrow_bond(
        _auth(nonce="0x" + "22" * 32, validBefore=soon),
        network=NETWORK, store=store,
    )
    later = datetime.fromtimestamp(int(soon) + 5, tz=timezone.utc)
    report = store.expire_due(now=later)
    assert report["expired"] == 1
    assert store.get(lock["lock_id"])["state"] == "expired"


def test_malformed_lock_id_is_a_miss(tmp_path):
    store = EscrowStore(tmp_path)
    assert store.get("../etc/passwd") is None
    assert store.get("sha256:" + "aa" * 32) is None
    with pytest.raises(EscrowError, match="lock_id_malformed"):
        store.release("../etc/passwd")


def test_settle_forfeit_submits_locked_authorization(tmp_path):
    """G12. A fired challenge submits the locked EIP-3009 authorization
    through the existing facilitator and records a settlement. Not a vault
    contract; local facilitator still G2."""
    store = EscrowStore(tmp_path)
    lock = escrow_bond(_auth(nonce="0x" + "44" * 32), network=NETWORK, store=store)
    sim = SimulatedFacilitatorClient()
    collected = settle_forfeit(
        lock,
        outcome={"outcome": "fired", "reason": "predicate_fired"},
        facilitator=sim,
        store=store,
    )
    assert collected["binding"] == BOND_BINDING_ESCROW
    assert collected["settlement"]["success"] is True
    assert "simulated" in (collected["settlement"]["transaction"] or "")
    updated = store.get(lock["lock_id"])
    assert updated["state"] == "forfeited"
    assert updated["settlement_tx"] == collected["settlement"]["transaction"]


def test_settle_forfeit_refuses_unfired_and_unsigned(tmp_path):
    store = EscrowStore(tmp_path)
    lock = escrow_bond(_auth(nonce="0x" + "55" * 32), network=NETWORK, store=store)
    sim = SimulatedFacilitatorClient()
    with pytest.raises(EscrowError, match="forfeit_requires_fired_challenge"):
        settle_forfeit(
            lock, outcome={"outcome": "not_fired"}, facilitator=sim, store=store
        )
    unsigned = escrow_bond(
        _auth(nonce="0x" + "56" * 32, signature=""),
        network=NETWORK, store=store,
    )
    # empty signature is dropped by canonical_authorization
    assert "signature" not in unsigned["authorization"]
    with pytest.raises(EscrowError, match="authorization_not_signed"):
        settle_forfeit(
            unsigned,
            outcome={"outcome": "fired"},
            facilitator=sim,
            store=store,
        )


def test_facilitator_refusal_leaves_the_lock_collectable(tmp_path):
    store = EscrowStore(tmp_path)
    lock = escrow_bond(_auth(nonce="0x" + "66" * 32), network=NETWORK, store=store)

    class Refusing:
        def settle(self, payload, requirements):
            return SettlementResult(False, error_reason="authorization_invalid")

    with pytest.raises(EscrowError, match="settlement_refused"):
        settle_forfeit(
            lock,
            outcome={"outcome": "fired"},
            facilitator=Refusing(),
            store=store,
        )
    assert store.get(lock["lock_id"])["state"] == "locked"


def test_settle_forfeit_refuses_a_mismatched_lock(tmp_path):
    store = EscrowStore(tmp_path)
    lock = escrow_bond(_auth(nonce="0x" + "67" * 32), network=NETWORK, store=store)
    with pytest.raises(EscrowError, match="forfeit_lock_mismatch"):
        settle_forfeit(
            lock,
            outcome={
                "outcome": "fired",
                "forfeit": {"lock_id": "ff" * 32},
            },
            facilitator=SimulatedFacilitatorClient(),
            store=store,
        )
    assert store.get(lock["lock_id"])["state"] == "locked"


def test_challenge_stake_is_the_same_primitive(tmp_path):
    store = EscrowStore(tmp_path)
    lock = escrow_stake(_auth(nonce="0x" + "77" * 32), network=NETWORK, store=store)
    assert lock["kind"] == KIND_CHALLENGE_STAKE
    assert lock["state"] == "locked"


def test_claim_serializes_collect_and_refusal_unlocks(tmp_path):
    """Two collects cannot both submit. Refusal returns the lock to locked."""
    import time
    from datetime import datetime, timezone

    store = EscrowStore(tmp_path)
    soon = str(int(time.time()) + 30)
    lock = escrow_bond(
        _auth(nonce="0x" + "68" * 32, validBefore=soon),
        network=NETWORK, store=store,
    )
    held = store.claim_for_settle(lock["lock_id"])
    assert held["state"] == STATE_SETTLING
    with pytest.raises(EscrowError, match="lock_not_locked:settling"):
        store.claim_for_settle(lock["lock_id"])
    later = datetime.fromtimestamp(int(soon) + 5, tz=timezone.utc)
    report = store.expire_due(now=later)
    assert report["expired"] == 0
    assert store.get(lock["lock_id"])["state"] == STATE_SETTLING
    collected = settle_forfeit(
        lock,
        outcome={"outcome": "fired", "reason": "predicate_fired"},
        facilitator=SimulatedFacilitatorClient(),
        store=store,
    )
    assert collected["state"] == "forfeited"
    assert store.get(lock["lock_id"])["state"] == "forfeited"


def test_resume_refusal_does_not_unlock(tmp_path):
    """A collect that did not itself claim must not revert. The nonce may
    already have been submitted by the in-flight collect."""
    store = EscrowStore(tmp_path)
    lock = escrow_bond(_auth(nonce="0x" + "69" * 32), network=NETWORK, store=store)
    store.claim_for_settle(lock["lock_id"])

    class Refusing:
        def settle(self, payload, requirements):
            return SettlementResult(False, error_reason="authorization_invalid")

    with pytest.raises(EscrowError, match="settlement_refused"):
        settle_forfeit(
            lock,
            outcome={"outcome": "fired"},
            facilitator=Refusing(),
            store=store,
        )
    assert store.get(lock["lock_id"])["state"] == STATE_SETTLING


def test_http_lock_get_release(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    import veritas.server as server

    importlib.reload(server)
    client = TestClient(server.app)
    body = {
        "authorization": _auth(nonce="0x" + "88" * 32),
        "kind": "bond",
        "network": NETWORK,
    }
    created = client.post("/v1/escrow", json=body)
    assert created.status_code == 200, created.text
    lock_id = created.json()["lock_id"]
    fetched = client.get(f"/v1/escrow/{lock_id}")
    assert fetched.status_code == 200
    assert fetched.json()["state"] == "locked"
    assert client.get("/v1/escrow/not-a-lock").status_code == 404
    released = client.post(f"/v1/escrow/{lock_id}/release")
    assert released.status_code == 200
    assert released.json()["state"] == "released"


def test_http_forfeit_without_live_facilitator_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    import veritas.server as server

    importlib.reload(server)
    client = TestClient(server.app)
    created = client.post("/v1/escrow", json={
        "authorization": _auth(nonce="0x" + "99" * 32),
        "network": NETWORK,
    })
    lock_id = created.json()["lock_id"]
    refused = client.post(
        f"/v1/escrow/{lock_id}/forfeit",
        json={"outcome": {"outcome": "fired", "reason": "predicate_fired"}},
    )
    assert refused.status_code == 503
    assert refused.json()["error"] == "escrow_settlement_unavailable"
    assert client.get(f"/v1/escrow/{lock_id}").json()["state"] == "locked"
