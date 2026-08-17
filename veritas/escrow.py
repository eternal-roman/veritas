"""Veritas Conditional Authorization Escrow (VCAE).

A2A commerce at machine scale cannot deploy a contract per trade and cannot
wait on an arbiter. The hardened pattern this adapts is already on the
rails this repository uses:

* **EIP-3009 ``transferWithAuthorization``** — the signed authorization
  *is* the locked value. Funds stay with the signer until someone submits.
* **Hashed-timelock / Lightning** — claim with a preimage (here: a
  deterministic challenge verdict), refund by doing nothing before
  ``validBefore``.
* **x402 batch settlement** — one authorization covers one warranty;
  millions of agents share one lock table, not one process each.

VCAE is that primitive specialized for warranty bonds and challenge stakes.

1. Signer produces an EIP-3009 authorization (same shape as an x402 exact
   payload). ``to`` is the published payee — a known counterparty, or the
   venue address advertised on identity.
2. ``lock`` stores it, keyed by nonce. A replayed nonce is refused.
3. ``settle_forfeit`` (only after a ``fired`` challenge) claims the lock
   (``locked`` → ``settling``) then submits the authorization through the
   existing facilitator. A second collect on the same lock cannot start
   another submit. That is a settlement event — unomittable once the rail
   accepts it or answers indeterminate.
4. ``release`` / ``expire`` never submit. The chain itself refuses a late
   claim once ``validBefore`` passes. An in-flight ``settling`` row is
   not expired (the rail may still accept the nonce).

Scale: the lock table lives in the shared store when
``VERITAS_DATABASE_URL`` is set. No per-agent thread. Expire sweep is an
indexed scan of ``state='locked'`` rows.

Honesty: this is not a deployed vault contract. The local facilitator
recovers EIP-712 signatures (G2 closed). Mainnet collect is unproven, same
as payments. A warranty that omits a lock stays
``signed_commitment_not_escrow`` and cannot be collected. A facilitator
refusal leaves the lock ``locked`` so a later collect can retry.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from veritas.hashing import compute_content_hash
from veritas.runtime import resolve_runtime_dir
from veritas.store import StoreUnavailable, connect_target, parse_database_url
from veritas.x402 import NONCE_RE, USDC_ASSETS

METHOD = "veritas.escrow.v1"
BOND_BINDING_ESCROW = "eip3009_authorization"
BOND_BINDING_COMMITMENT = "signed_commitment_not_escrow"

KIND_BOND = "bond"
KIND_CHALLENGE_STAKE = "challenge_stake"
KINDS = frozenset({KIND_BOND, KIND_CHALLENGE_STAKE})

STATE_LOCKED = "locked"
STATE_SETTLING = "settling"
STATE_RELEASED = "released"
STATE_FORFEITED = "forfeited"
STATE_EXPIRED = "expired"
STATES = frozenset({
    STATE_LOCKED, STATE_SETTLING, STATE_RELEASED, STATE_FORFEITED, STATE_EXPIRED,
})

ADDRESS_RE = re.compile(r"\A0x[0-9a-fA-F]{40}\Z")
ATOMIC_RE = re.compile(r"\A[0-9]+\Z")
LOCK_ID_RE = re.compile(r"\A[0-9a-f]{64}\Z")

_DB_FILENAME = "escrow.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS escrow_locks (
    lock_id          TEXT PRIMARY KEY,
    nonce            TEXT NOT NULL UNIQUE,
    kind             TEXT NOT NULL,
    state            TEXT NOT NULL,
    authorization    TEXT NOT NULL,
    warranty_hash    TEXT,
    network          TEXT,
    asset            TEXT,
    amount           TEXT,
    signer           TEXT,
    pay_to           TEXT,
    valid_after      TEXT,
    valid_before     TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    settlement_tx    TEXT,
    settlement_state TEXT,
    reason           TEXT
);
CREATE INDEX IF NOT EXISTS escrow_locks_by_state_expiry
    ON escrow_locks(state, valid_before);
CREATE INDEX IF NOT EXISTS escrow_locks_by_warranty
    ON escrow_locks(warranty_hash);
"""


class EscrowError(ValueError):
    """Lock, release, or forfeit could not proceed."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_safe_lock_id(value: object) -> bool:
    return isinstance(value, str) and bool(LOCK_ID_RE.fullmatch(value))


def canonical_authorization(auth: dict[str, Any]) -> dict[str, str]:
    """Normalize the EIP-3009 fields we persist. Refuses a malformed lock."""
    if not isinstance(auth, dict):
        raise EscrowError("authorization_malformed")
    required = ("from", "to", "value", "validAfter", "validBefore", "nonce")
    out: dict[str, str] = {}
    for key in required:
        raw = auth.get(key)
        if not isinstance(raw, str) or not raw:
            raise EscrowError(f"authorization_malformed:{key}")
        out[key] = raw
    if not ADDRESS_RE.fullmatch(out["from"]) or not ADDRESS_RE.fullmatch(out["to"]):
        raise EscrowError("authorization_malformed:address")
    if not ATOMIC_RE.fullmatch(out["value"]) or int(out["value"]) <= 0:
        raise EscrowError("authorization_malformed:value")
    if not NONCE_RE.fullmatch(out["nonce"]):
        raise EscrowError("authorization_malformed:nonce")
    # validAfter / validBefore are unix seconds as decimal strings on the
    # x402 wire. Also accept ISO-8601 so tests and operators can read them.
    for stamp_key in ("validAfter", "validBefore"):
        text = out[stamp_key]
        if ATOMIC_RE.fullmatch(text):
            continue
        try:
            _parse_iso(text)
        except ValueError as exc:
            raise EscrowError(f"authorization_malformed:{stamp_key}") from exc
    signature = auth.get("signature")
    if isinstance(signature, str) and signature:
        out["signature"] = signature
    return out


def lock_id_for(auth: dict[str, str]) -> str:
    body = json.dumps(
        {k: auth[k] for k in ("from", "to", "value", "validAfter", "validBefore", "nonce")},
        sort_keys=True, separators=(",", ":"),
    )
    return compute_content_hash(body).split(":", 1)[1]


def authorization_still_valid(auth: dict[str, str], *, now: datetime | None = None) -> bool:
    moment = now or datetime.now(timezone.utc)
    before = auth["validBefore"]
    if ATOMIC_RE.fullmatch(before):
        return moment.timestamp() < int(before)
    return moment < _parse_iso(before)


def to_payment_payload(auth: dict[str, str], *, network: str, scheme: str = "exact") -> dict[str, Any]:
    """Shape an x402 exact payload a facilitator can settle."""
    return {
        "x402Version": 1,
        "scheme": scheme,
        "network": network,
        "payload": {
            "signature": auth.get("signature", ""),
            "authorization": {
                "from": auth["from"],
                "to": auth["to"],
                "value": auth["value"],
                "validAfter": auth["validAfter"],
                "validBefore": auth["validBefore"],
                "nonce": auth["nonce"],
            },
        },
        "payer": auth["from"],
    }


def to_requirements(auth: dict[str, str], *, network: str, asset: str | None = None) -> dict[str, Any]:
    token = asset or (USDC_ASSETS.get(network) or {}).get("address") or ""
    return {
        "scheme": "exact",
        "network": network,
        "maxAmountRequired": auth["value"],
        "payTo": auth["to"],
        "asset": token,
    }


class EscrowStore:
    """Durable locks. Shared when VERITAS_DATABASE_URL is set."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = resolve_runtime_dir(base_dir)

    def _target(self):
        try:
            return parse_database_url()
        except StoreUnavailable:
            raise

    def _connect(self):
        try:
            target = self._target()
        except StoreUnavailable as exc:
            raise EscrowError(f"store_unavailable:{type(exc).__name__}") from exc
        if target is not None:
            conn = connect_target(target)
            conn.executescript(_SCHEMA)
            return conn
        self.base_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(self.base_dir / _DB_FILENAME), timeout=10, isolation_level=None
        )
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        return conn

    def lock(
        self,
        authorization: dict[str, Any],
        *,
        kind: str,
        network: str,
        asset: str | None = None,
        warranty_hash: str | None = None,
    ) -> dict[str, Any]:
        if kind not in KINDS:
            raise EscrowError(f"kind_unknown:{kind}")
        if network not in USDC_ASSETS:
            raise EscrowError(f"network_unknown:{network}")
        auth = canonical_authorization(authorization)
        if not authorization_still_valid(auth):
            raise EscrowError("authorization_expired")
        lock_id = lock_id_for(auth)
        now = _now()
        record = {
            "lock_id": lock_id,
            "nonce": auth["nonce"],
            "kind": kind,
            "state": STATE_LOCKED,
            "authorization": json.dumps(auth, separators=(",", ":"), sort_keys=True),
            "warranty_hash": warranty_hash,
            "network": network,
            "asset": asset or USDC_ASSETS[network]["address"],
            "amount": auth["value"],
            "signer": auth["from"].lower(),
            "pay_to": auth["to"].lower(),
            "valid_after": auth["validAfter"],
            "valid_before": auth["validBefore"],
            "created_at": now,
            "updated_at": now,
            "settlement_tx": None,
            "settlement_state": None,
            "reason": None,
            "method": METHOD,
            "binding": BOND_BINDING_ESCROW,
        }
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT lock_id FROM escrow_locks WHERE nonce = ?",
                (auth["nonce"],),
            ).fetchone()
            if existing is not None:
                conn.execute("ROLLBACK")
                raise EscrowError("authorization_nonce_already_locked")
            conn.execute(
                "INSERT INTO escrow_locks ("
                "lock_id, nonce, kind, state, authorization, warranty_hash, "
                "network, asset, amount, signer, pay_to, valid_after, "
                "valid_before, created_at, updated_at, settlement_tx, "
                "settlement_state, reason"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    record["lock_id"], record["nonce"], record["kind"],
                    record["state"], record["authorization"],
                    record["warranty_hash"], record["network"], record["asset"],
                    record["amount"], record["signer"], record["pay_to"],
                    record["valid_after"], record["valid_before"],
                    record["created_at"], record["updated_at"],
                    record["settlement_tx"], record["settlement_state"],
                    record["reason"],
                ),
            )
            conn.execute("COMMIT")
        except EscrowError:
            raise
        except Exception as exc:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise EscrowError(f"store_unavailable:{type(exc).__name__}") from exc
        finally:
            conn.close()
        return self.get(lock_id) or record

    def get(self, lock_id: str) -> dict[str, Any] | None:
        if not is_safe_lock_id(lock_id):
            return None
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM escrow_locks WHERE lock_id = ?", (lock_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return _row_to_record(row)

    def _transition(
        self,
        lock_id: str,
        *,
        expect: str,
        new_state: str,
        reason: str,
        settlement_tx: str | None = None,
        settlement_state: str | None = None,
    ) -> dict[str, Any]:
        if not is_safe_lock_id(lock_id):
            raise EscrowError("lock_id_malformed")
        now = _now()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM escrow_locks WHERE lock_id = ?", (lock_id,),
            ).fetchone()
            if row is None:
                conn.execute("ROLLBACK")
                raise EscrowError("lock_not_found")
            if row["state"] != expect:
                conn.execute("ROLLBACK")
                raise EscrowError(f"lock_not_{expect}:{row['state']}")
            conn.execute(
                "UPDATE escrow_locks SET state=?, reason=?, updated_at=?, "
                "settlement_tx=?, settlement_state=? WHERE lock_id=?",
                (new_state, reason, now, settlement_tx, settlement_state, lock_id),
            )
            conn.execute("COMMIT")
        except EscrowError:
            raise
        except Exception as exc:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise EscrowError(f"store_unavailable:{type(exc).__name__}") from exc
        finally:
            conn.close()
        found = self.get(lock_id)
        if found is None:
            raise EscrowError("lock_not_found")
        return found

    def release(self, lock_id: str, *, reason: str = "released") -> dict[str, Any]:
        """Mark locked value unclaimable. Never submits on-chain."""
        return self._transition(
            lock_id, expect=STATE_LOCKED, new_state=STATE_RELEASED, reason=reason,
        )

    def expire_due(self, *, now: datetime | None = None) -> dict[str, int]:
        """Expire locked rows whose validBefore has passed. Never submits."""
        moment = now or datetime.now(timezone.utc)
        expired = 0
        skipped = 0
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT lock_id, authorization FROM escrow_locks WHERE state = ?",
                (STATE_LOCKED,),
            ).fetchall()
        finally:
            conn.close()
        for row in rows:
            try:
                auth = json.loads(row["authorization"])
            except (TypeError, json.JSONDecodeError):
                skipped += 1
                continue
            if authorization_still_valid(auth, now=moment):
                continue
            try:
                self._transition(
                    row["lock_id"],
                    expect=STATE_LOCKED,
                    new_state=STATE_EXPIRED,
                    reason="valid_before_elapsed",
                )
                expired += 1
            except EscrowError:
                skipped += 1
        return {"expired": expired, "skipped": skipped}

    def claim_for_settle(self, lock_id: str) -> dict[str, Any]:
        """locked → settling. Second collect fails here, before another submit."""
        return self._transition(
            lock_id,
            expect=STATE_LOCKED,
            new_state=STATE_SETTLING,
            reason="settlement_in_flight",
        )

    def revert_settle(self, lock_id: str) -> dict[str, Any]:
        """settling → locked after a facilitator refusal. Nonce was not spent."""
        return self._transition(
            lock_id,
            expect=STATE_SETTLING,
            new_state=STATE_LOCKED,
            reason="settlement_refused",
        )

    def forfeit(
        self,
        lock_id: str,
        *,
        reason: str = "predicate_fired",
        settlement_tx: str | None = None,
        settlement_state: str | None = None,
        expect: str = STATE_SETTLING,
    ) -> dict[str, Any]:
        return self._transition(
            lock_id,
            expect=expect,
            new_state=STATE_FORFEITED,
            reason=reason,
            settlement_tx=settlement_tx,
            settlement_state=settlement_state,
        )


def _row_to_record(row: Any) -> dict[str, Any]:
    auth_raw = row["authorization"]
    try:
        auth = json.loads(auth_raw) if isinstance(auth_raw, str) else dict(auth_raw)
    except (TypeError, json.JSONDecodeError):
        auth = {}
    return {
        "lock_id": row["lock_id"],
        "nonce": row["nonce"],
        "kind": row["kind"],
        "state": row["state"],
        "authorization": auth,
        "warranty_hash": row["warranty_hash"],
        "network": row["network"],
        "asset": row["asset"],
        "amount": row["amount"],
        "signer": row["signer"],
        "pay_to": row["pay_to"],
        "valid_after": row["valid_after"],
        "valid_before": row["valid_before"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "settlement_tx": row["settlement_tx"],
        "settlement_state": row["settlement_state"],
        "reason": row["reason"],
        "method": METHOD,
        "binding": BOND_BINDING_ESCROW,
    }


def public_lock(record: dict[str, Any]) -> dict[str, Any]:
    """HTTP view of a lock. The signature *is* the money — it never leaves
    the store except when ``settle_forfeit`` submits it. GET must not
    publish a collectable authorization.
    """
    out = dict(record)
    auth = out.get("authorization")
    if isinstance(auth, dict):
        visible = {k: v for k, v in auth.items() if k != "signature"}
        visible["signature_present"] = bool(auth.get("signature"))
        out["authorization"] = visible
    return out


def escrow_bond(
    authorization: dict[str, Any],
    *,
    network: str,
    asset: str | None = None,
    warranty_hash: str | None = None,
    store: EscrowStore | None = None,
) -> dict[str, Any]:
    """Lock a seller bond authorization. The name the G12 witness watched for."""
    return (store or EscrowStore()).lock(
        authorization,
        kind=KIND_BOND,
        network=network,
        asset=asset,
        warranty_hash=warranty_hash,
    )


def escrow_stake(
    authorization: dict[str, Any],
    *,
    network: str,
    asset: str | None = None,
    warranty_hash: str | None = None,
    store: EscrowStore | None = None,
) -> dict[str, Any]:
    """Lock a challenger's stake. Same primitive, different kind label."""
    return (store or EscrowStore()).lock(
        authorization,
        kind=KIND_CHALLENGE_STAKE,
        network=network,
        asset=asset,
        warranty_hash=warranty_hash,
    )


def settle_forfeit(
    lock: dict[str, Any],
    *,
    outcome: dict[str, Any],
    facilitator: Any,
    store: EscrowStore | None = None,
) -> dict[str, Any]:
    """Submit a locked bond after a fired challenge. Fail-closed.

    Requires ``outcome['outcome'] == 'fired'``. Does not invent a
    settlement: the facilitator result is recorded as-is. A missing or
    unsigned authorization is refused rather than waved through.

    A facilitator *refusal* leaves the lock ``locked`` so a later collect
    can retry. Success or an indeterminate answer (the rail may have
    moved the funds) transitions to ``forfeited`` so the same nonce is
    not submitted twice. Concurrent collects serialize on the
    ``locked`` → ``settling`` claim; a crash after a successful submit
    leaves ``settling`` so a retry can finish the persist without
    unlocking. A resume that is refused does *not* revert — the nonce
    may already have been spent.
    """
    if not isinstance(outcome, dict) or outcome.get("outcome") != "fired":
        raise EscrowError("forfeit_requires_fired_challenge")
    lock_id = lock.get("lock_id")
    if not is_safe_lock_id(lock_id):
        raise EscrowError("lock_id_malformed")
    claimed_lock = (outcome.get("forfeit") or {}).get("lock_id")
    if claimed_lock and claimed_lock != lock_id:
        raise EscrowError("forfeit_lock_mismatch")

    db = store or EscrowStore()
    current = db.get(lock_id)
    if current is None:
        raise EscrowError("lock_not_found")
    claimed_now = False
    if current["state"] == STATE_SETTLING:
        held = current
    elif current["state"] == STATE_LOCKED:
        held = db.claim_for_settle(lock_id)
        claimed_now = True
    else:
        raise EscrowError(f"lock_not_locked:{current['state']}")

    submitted = False
    try:
        auth = held.get("authorization")
        if not isinstance(auth, dict) or not auth.get("signature"):
            raise EscrowError("authorization_not_signed")
        bound = held.get("warranty_hash")
        claimed_response = (outcome.get("forfeit") or {}).get("response_hash")
        if bound and claimed_response and bound != claimed_response:
            raise EscrowError("forfeit_warranty_mismatch")
        network = held.get("network") or ""
        payload = to_payment_payload(auth, network=network)
        requirements = to_requirements(auth, network=network, asset=held.get("asset"))
        result = facilitator.settle(payload, requirements)
        settled = result.to_dict() if hasattr(result, "to_dict") else dict(result)
        state = settled.get("state")
        if hasattr(result, "outcome"):
            state = result.outcome
        success = bool(settled.get("success"))
        if not success and state != "indeterminate":
            raise EscrowError(
                f"settlement_refused:{settled.get('error_reason') or state or 'failed'}"
            )
        submitted = True
        updated = db.forfeit(
            lock_id,
            reason=str(outcome.get("reason") or "predicate_fired"),
            settlement_tx=settled.get("transaction"),
            settlement_state=state or settled.get("error_reason"),
        )
    except Exception:
        # Only the call that just claimed may unlock. A resume must not
        # revert: another collect may already have spent the nonce.
        if not submitted and claimed_now:
            try:
                db.revert_settle(lock_id)
            except EscrowError:
                pass
        raise
    return {
        "lock_id": lock["lock_id"],
        "state": updated.get("state"),
        "binding": BOND_BINDING_ESCROW,
        "settlement": settled,
        "method": METHOD,
        "note": (
            "Forfeit submitted through the existing facilitator. "
            "Mainnet collect is unproven."
        ),
    }
