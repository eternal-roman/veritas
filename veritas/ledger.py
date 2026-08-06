"""The financial ledger: what was authorized, what was delivered, what settled.

Before this module the money path kept no record of itself. A nonce was
appended to a JSONL file the moment it was accepted and never joined to
anything; the settlement — including the on-chain transaction hash — was
base64'd into a response header and discarded. Three consequences, all of them
audited defects:

* **Revenue could not be reconciled** (gap G8 / defect R5). Nothing durable
  said what was earned, from whom, or for what. A disputed charge had no
  answer, and "how much did we make" was unanswerable except by reading logs
  that were never written.
* **A disconnected buyer was charged for nothing** (gap G6 / defect R11). The
  nonce was burned before the work; if the connection dropped after settlement
  the buyer had paid, received nothing, and got a 409 on retry. The
  authorization is single-use on chain, so they could not even re-sign it.
* **"We do not know" was recorded as "it did not happen"** (defect R7). A
  settlement whose facilitator never answered was reported as a failure. That
  is a claim about the chain we did not observe, and it is wrong in both
  directions: it understates revenue and overstates certainty.

The fix is a state machine over the payment authorization, durable before the
response is written:

    claimed ──work──▶ delivered ──settle──▶ settled
        │                 │            └──▶ indeterminate ──retry──▶ settled
        │                 └──────────────▶ settlement_failed
        └──not billable──▶ abandoned

`delivered` is written and fsynced *before* settlement is attempted, so a
crash between the two leaves a durable record that we owe the buyer a
deliverable and may or may not have been paid — the reconcilable state, rather
than silence. A replayed authorization in `settled` or `indeterminate` returns
the stored deliverable instead of a 409: the buyer gets what they paid for.

Design rules, and why:

- **Fail closed.** If the store cannot be opened or written, the claim is
  refused. An unavailable ledger must not silently become no ledger.
- **Money is integer atomic units.** Amounts are stored and summed as decimal
  integer strings. Float accumulation is a rounding bug waiting for volume.
- **Settlement attempts are append-only.** An indeterminate attempt later
  resolved is two facts, not one overwritten one.
- **Paid path only.** Free-mode traffic writes nothing here; this is a
  financial record, and unpaid requests are not revenue. Custody receipts
  (`veritas/custody.py`) cover the audit trail for those.
- **Single-instance scope, stated plainly.** SQLite on local disk guards one
  instance. Behind a load balancer two instances do not share it; that needs
  the shared state in roadmap 6.2. This is a real limit, not a closed problem.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .x402 import NONCE_RE

_DEFAULT_RUNTIME_DIR = ".veritas_runtime"
_DB_FILENAME = "ledger.sqlite3"


class NonceState(str, Enum):
    """States of one payment authorization. See the diagram above."""

    CLAIMED = "claimed"
    DELIVERED = "delivered"
    SETTLED = "settled"
    INDETERMINATE = "indeterminate"
    SETTLEMENT_FAILED = "settlement_failed"
    ABANDONED = "abandoned"


#: States in which a replayed authorization is answered with the deliverable
#: it already bought rather than a 409. `indeterminate` is included on
#: purpose: we may have taken the buyer's money, so withholding the work is
#: the one outcome that is certainly wrong.
REDELIVERABLE_STATES = frozenset({NonceState.SETTLED, NonceState.INDETERMINATE})

#: Settlement may be attempted (or re-attempted) only from these.
SETTLEABLE_STATES = frozenset({
    NonceState.DELIVERED, NonceState.INDETERMINATE, NonceState.SETTLEMENT_FAILED,
})

_OUTCOME_STATE = {
    "settled": NonceState.SETTLED,
    "indeterminate": NonceState.INDETERMINATE,
    "failed": NonceState.SETTLEMENT_FAILED,
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS authorizations (
    nonce       TEXT PRIMARY KEY,
    request_id  TEXT NOT NULL UNIQUE,
    state       TEXT NOT NULL,
    network     TEXT,
    asset       TEXT,
    amount      TEXT,
    pay_to      TEXT,
    payer       TEXT,
    price       TEXT,
    claimed_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deliveries (
    request_id   TEXT PRIMARY KEY,
    nonce        TEXT NOT NULL,
    status       TEXT NOT NULL,
    billable     INTEGER NOT NULL,
    custody_root TEXT,
    query_hash   TEXT,
    response     TEXT NOT NULL,
    delivered_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settlements (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id       TEXT NOT NULL,
    nonce            TEXT NOT NULL,
    outcome          TEXT NOT NULL,
    transaction_hash TEXT,
    network          TEXT,
    payer            TEXT,
    amount           TEXT,
    asset            TEXT,
    reason           TEXT,
    recorded_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS settlements_by_request ON settlements(request_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Authorization:
    """One payment authorization and the state of the request it bought."""

    nonce: str
    request_id: str
    state: str
    network: str | None
    asset: str | None
    amount: str | None
    pay_to: str | None
    payer: str | None
    price: str | None
    claimed_at: str
    updated_at: str

    @classmethod
    def _from_row(cls, row: sqlite3.Row) -> Authorization:
        return cls(**{k: row[k] for k in cls.__dataclass_fields__})


@dataclass(frozen=True)
class ClaimResult:
    """Outcome of trying to claim a nonce. Failures are results, not raises.

    `existing` carries the authorization already on file when the claim is
    refused as a duplicate, because the caller's next move depends on its
    state: replay the deliverable, or reject.
    """

    claimed: bool
    reason: str | None = None
    nonce: str | None = None
    existing: Authorization | None = None


class LedgerUnavailable(RuntimeError):
    """The store could not be reached. Callers fail closed."""


class Ledger:
    """Durable record of authorizations, deliveries and settlements."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(
            base_dir or os.getenv("VERITAS_RUNTIME_DIR") or _DEFAULT_RUNTIME_DIR
        )

    @property
    def path(self) -> Path:
        return self.base_dir / _DB_FILENAME

    def _connect(self) -> sqlite3.Connection:
        """Open a fresh connection. Handlers run in a threadpool and sqlite3
        connections are not shareable across threads, so per-call connections
        are the correct trade rather than a performance oversight."""
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        except (sqlite3.Error, OSError) as exc:
            # Category only: the sqlite/OS message names server filesystem
            # paths, and this reason reaches external buyers in a 503 detail.
            raise LedgerUnavailable(type(exc).__name__) from exc
        conn.row_factory = sqlite3.Row
        # WAL plus synchronous=FULL means a committed transaction is fsynced
        # before we act on it — which is the whole point of writing the
        # delivery before attempting settlement.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.executescript(_SCHEMA)
        return conn

    # -- claiming -----------------------------------------------------------

    def claim(
        self,
        nonce: str | None,
        request_id: str,
        *,
        network: str | None = None,
        asset: str | None = None,
        amount: str | None = None,
        pay_to: str | None = None,
        payer: str | None = None,
        price: str | None = None,
    ) -> ClaimResult:
        """Claim an authorization for one request, before any work is done.

        Idempotent per nonce and fail-closed. The claim is never released: the
        authorization it names stays live on chain, so re-admitting it would
        restore the duplicate-work this prevents. What a replay gets instead is
        the deliverable, once one exists — see `REDELIVERABLE_STATES`.
        """
        if nonce is None:
            return ClaimResult(False, "payment_nonce_missing")
        if not NONCE_RE.fullmatch(nonce):
            return ClaimResult(False, "payment_nonce_malformed")
        key = nonce.lower()
        now = _now()
        try:
            conn = self._connect()
        except LedgerUnavailable:
            return ClaimResult(False, "replay_store_unavailable")
        try:
            with conn:
                # IMMEDIATE takes the write lock before the read, so two
                # concurrent claims of one nonce cannot both see it free.
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT * FROM authorizations WHERE nonce = ?", (key,)
                ).fetchone()
                if row is not None:
                    return ClaimResult(
                        False, "payment_nonce_already_spent", key,
                        Authorization._from_row(row),
                    )
                conn.execute(
                    "INSERT INTO authorizations (nonce, request_id, state, network,"
                    " asset, amount, pay_to, payer, price, claimed_at, updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (key, request_id, NonceState.CLAIMED.value, network, asset,
                     amount, pay_to, payer, price, now, now),
                )
        except sqlite3.IntegrityError:
            # The nonce was free but the request_id was not. Server-generated
            # ids are uuid4 so this is not reachable in practice; reporting it
            # as "store unavailable" would nonetheless be a lie.
            return ClaimResult(False, "payment_request_id_already_claimed", key)
        except (sqlite3.Error, OSError):
            return ClaimResult(False, "replay_store_unavailable")
        finally:
            conn.close()
        return ClaimResult(True, None, key)

    def authorization(self, nonce: str) -> Authorization | None:
        try:
            conn = self._connect()
        except LedgerUnavailable:
            return None
        try:
            row = conn.execute(
                "SELECT * FROM authorizations WHERE nonce = ?", (nonce.lower(),)
            ).fetchone()
        finally:
            conn.close()
        return Authorization._from_row(row) if row is not None else None

    # -- delivery -----------------------------------------------------------

    def record_delivery(
        self,
        request_id: str,
        *,
        status: str,
        billable: bool,
        custody_root: str | None,
        query: str,
        response: dict[str, Any],
    ) -> bool:
        """Record what we produced, before settlement is attempted.

        Returns False when no authorization claimed this request_id: a
        delivery with no authorization behind it would be revenue attributed
        to nobody, and the paid path always claims first.
        """
        try:
            conn = self._connect()
        except LedgerUnavailable:
            return False
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT nonce, state FROM authorizations WHERE request_id = ?",
                    (request_id,),
                ).fetchone()
                if row is None:
                    return False
                state = (
                    NonceState.DELIVERED if billable else NonceState.ABANDONED
                ).value
                now = _now()
                conn.execute(
                    "INSERT OR REPLACE INTO deliveries (request_id, nonce, status,"
                    " billable, custody_root, query_hash, response, delivered_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (request_id, row["nonce"], status, int(bool(billable)),
                     custody_root, _query_hash(query),
                     json.dumps(response, separators=(",", ":")), now),
                )
                conn.execute(
                    "UPDATE authorizations SET state = ?, updated_at = ?"
                    " WHERE request_id = ?",
                    (state, now, request_id),
                )
        except (sqlite3.Error, OSError):
            return False
        finally:
            conn.close()
        return True

    def deliverable(self, request_id: str) -> dict[str, Any] | None:
        """The response body we produced for this request, if any."""
        try:
            conn = self._connect()
        except LedgerUnavailable:
            return None
        try:
            row = conn.execute(
                "SELECT response FROM deliveries WHERE request_id = ?", (request_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        try:
            return json.loads(row["response"])
        except json.JSONDecodeError:
            return None

    # -- settlement ---------------------------------------------------------

    def record_settlement(
        self,
        request_id: str,
        *,
        outcome: str,
        transaction: str | None = None,
        network: str | None = None,
        payer: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Record one settlement attempt and advance the authorization.

        `outcome` is `settled`, `indeterminate` or `failed`. Indeterminate is
        not failure: it means the facilitator never gave us an answer, so the
        funds may have moved. Raises ValueError when the transition is not
        legal — settling an abandoned request would bill for our own failure,
        and settling before delivery would charge for undeliverable work.
        """
        if outcome not in _OUTCOME_STATE:
            raise ValueError(f"unknown settlement outcome: {outcome!r}")
        try:
            conn = self._connect()
        except LedgerUnavailable as exc:
            raise ValueError("ledger unavailable") from exc
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT * FROM authorizations WHERE request_id = ?", (request_id,)
                ).fetchone()
                if row is None:
                    raise ValueError(f"no authorization for request {request_id!r}")
                if row["state"] not in {s.value for s in SETTLEABLE_STATES}:
                    raise ValueError(
                        f"cannot settle a request in state {row['state']!r}"
                    )
                now = _now()
                conn.execute(
                    "INSERT INTO settlements (request_id, nonce, outcome,"
                    " transaction_hash, network, payer, amount, asset, reason,"
                    " recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (request_id, row["nonce"], outcome, transaction,
                     network or row["network"], payer or row["payer"],
                     row["amount"], row["asset"], reason, now),
                )
                conn.execute(
                    "UPDATE authorizations SET state = ?, updated_at = ?"
                    " WHERE request_id = ?",
                    (_OUTCOME_STATE[outcome].value, now, request_id),
                )
        finally:
            conn.close()

    def settlements(self, request_id: str) -> list[dict[str, Any]]:
        """Every settlement attempt for a request, oldest first."""
        try:
            conn = self._connect()
        except LedgerUnavailable:
            return []
        try:
            rows = conn.execute(
                "SELECT * FROM settlements WHERE request_id = ? ORDER BY id",
                (request_id,),
            ).fetchall()
        finally:
            conn.close()
        return [
            {
                "request_id": r["request_id"],
                "nonce": r["nonce"],
                "outcome": r["outcome"],
                "transaction": r["transaction_hash"],
                "network": r["network"],
                "payer": r["payer"],
                "amount": r["amount"],
                "asset": r["asset"],
                "reason": r["reason"],
                "recorded_at": r["recorded_at"],
            }
            for r in rows
        ]

    # -- reconciliation -----------------------------------------------------

    def awaiting_settlement(self) -> list[Authorization]:
        """Delivered work with no terminal settlement: what we are owed."""
        try:
            conn = self._connect()
        except LedgerUnavailable:
            return []
        try:
            rows = conn.execute(
                "SELECT * FROM authorizations WHERE state IN (?, ?) ORDER BY claimed_at",
                (NonceState.DELIVERED.value, NonceState.SETTLEMENT_FAILED.value),
            ).fetchall()
        finally:
            conn.close()
        return [Authorization._from_row(r) for r in rows]

    def summary(self) -> dict[str, Any]:
        """Revenue and exposure, answerable from the ledger alone.

        Amounts are atomic units summed as integers and reported as decimal
        strings, keyed `network/asset` — the same units the 402 challenge
        quotes, so no conversion is invented here.
        """
        try:
            conn = self._connect()
        except LedgerUnavailable:
            return {"error": "ledger_unavailable"}
        try:
            states = Counter(
                r["state"] for r in conn.execute("SELECT state FROM authorizations")
            )
            deliveries = conn.execute("SELECT billable FROM deliveries").fetchall()
            settled = conn.execute(
                "SELECT s.network, s.asset, s.amount FROM settlements s"
                " JOIN authorizations a ON a.request_id = s.request_id"
                " WHERE s.outcome = 'settled' AND a.state = ?",
                (NonceState.SETTLED.value,),
            ).fetchall()
        finally:
            conn.close()

        amounts: Counter[str] = Counter()
        for row in settled:
            try:
                value = int(row["amount"])
            except (TypeError, ValueError):
                continue
            amounts[f"{row['network']}/{row['asset']}"] += value

        return {
            "deliveries": len(deliveries),
            "billable_deliveries": sum(1 for d in deliveries if d["billable"]),
            "settled_count": states[NonceState.SETTLED.value],
            "indeterminate_count": states[NonceState.INDETERMINATE.value],
            "failed_count": states[NonceState.SETTLEMENT_FAILED.value],
            "abandoned_count": states[NonceState.ABANDONED.value],
            "unsettled_count": states[NonceState.DELIVERED.value],
            "settled_amounts": {k: str(v) for k, v in sorted(amounts.items())},
            "states": dict(states),
        }


def _query_hash(query: str) -> str:
    """Index queries without a second plaintext copy of them on disk.

    The deliverable already contains the query; this column exists so
    reconciliation can group and count without reading response blobs.
    """
    return "sha256:" + hashlib.sha256((query or "").encode("utf-8")).hexdigest()
