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
- **The financial tables are paid-path only.** Free-mode traffic writes no
  authorization, delivery or settlement row; those are a record of revenue,
  and unpaid requests are not revenue. Custody receipts
  (`veritas/custody.py`) cover the audit trail for those.
- **The `usage` table is not.** Cost is incurred whether or not anyone paid,
  so metering covers every request. A COGS figure drawn only from paid
  requests would understate what the operator spends.
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
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any

from .metering import UNPRICED, CostTable, Usage, cost_of
from .x402 import NONCE_RE, USDC_ASSETS

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
    nonce         TEXT PRIMARY KEY,
    request_id    TEXT NOT NULL UNIQUE,
    state         TEXT NOT NULL,
    network       TEXT,
    asset         TEXT,
    amount        TEXT,
    pay_to        TEXT,
    payer         TEXT,
    price         TEXT,
    price_version TEXT,
    claimed_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
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
-- Usage is metered on EVERY request, paid or free: a retrieval pass costs the
-- same whether or not anyone paid for it, so a COGS report drawn only from the
-- paid tables above would understate what the operator spends.
CREATE TABLE IF NOT EXISTS usage (
    request_id     TEXT PRIMARY KEY,
    status         TEXT NOT NULL,
    billable       INTEGER NOT NULL,
    paid           INTEGER NOT NULL,
    provider_calls TEXT NOT NULL,
    evidence_bytes INTEGER NOT NULL,
    duration_ms    INTEGER NOT NULL,
    recorded_at    TEXT NOT NULL
);
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
    price_version: str | None
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
        price_version: str | None = None,
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
                    " asset, amount, pay_to, payer, price, price_version,"
                    " claimed_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (key, request_id, NonceState.CLAIMED.value, network, asset,
                     amount, pay_to, payer, price, price_version, now, now),
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
        return [_settlement_dict(r) for r in rows]

    # -- metering -----------------------------------------------------------

    def record_usage(self, usage: Usage) -> bool:
        """Record what one request consumed. Never raises: a metering failure
        must not fail a request the buyer paid for."""
        try:
            conn = self._connect()
        except LedgerUnavailable:
            return False
        try:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO usage (request_id, status, billable,"
                    " paid, provider_calls, evidence_bytes, duration_ms, recorded_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (usage.request_id, usage.status, int(bool(usage.billable)),
                     int(bool(usage.paid)),
                     json.dumps(usage.provider_calls, separators=(",", ":")),
                     int(usage.evidence_bytes), int(usage.duration_ms), _now()),
                )
        except (sqlite3.Error, OSError):
            return False
        finally:
            conn.close()
        return True

    def usage_summary(self, costs: CostTable | None = None) -> dict[str, Any]:
        """What was consumed, and what it cost where a cost is configured.

        `cost_micros` is UNPRICED when any provider that was called has no
        configured price: charging only for the priced subset would understate
        cost while looking like a complete figure.
        """
        costs = CostTable.from_env() if costs is None else costs
        try:
            conn = self._connect()
        except LedgerUnavailable:
            return {"error": "ledger_unavailable"}
        try:
            rows = conn.execute("SELECT * FROM usage").fetchall()
        finally:
            conn.close()

        calls: Counter[str] = Counter()
        evidence_bytes = duration_ms = paid = billable = 0
        for row in rows:
            try:
                per_request = json.loads(row["provider_calls"])
            except json.JSONDecodeError:
                per_request = {}
            calls.update({k: int(v) for k, v in per_request.items()})
            evidence_bytes += row["evidence_bytes"]
            duration_ms += row["duration_ms"]
            paid += bool(row["paid"])
            billable += bool(row["billable"])

        cost_micros, unpriced = cost_of(dict(calls), costs)
        return {
            "requests": len(rows),
            "paid_requests": paid,
            "billable_requests": billable,
            "provider_calls": dict(sorted(calls.items())),
            "evidence_bytes": evidence_bytes,
            "duration_ms_total": duration_ms,
            "cost_micros": cost_micros,
            "unpriced_providers": unpriced,
            "cost_table_rejected": list(costs.rejected),
        }

    def economics(self, costs: CostTable | None = None) -> dict[str, Any]:
        """Revenue, cost and margin in one report, in one unit.

        Revenue is converted from per-asset atomic units to micro-USD only
        where the asset's decimals are known and the conversion is exact; any
        asset that fails either test is listed in `unconvertible_assets` and
        left out of the total rather than rounded into it. Margin is withheld
        entirely whenever either side is incomplete — a margin computed over a
        partial cost base reads as a measurement and is not one.
        """
        costs = CostTable.from_env() if costs is None else costs
        financial = self.summary()
        usage = self.usage_summary(costs)

        revenue_micros = 0
        unconvertible: list[str] = []
        for key, atomic in financial.get("settled_amounts", {}).items():
            micros = _atomic_to_micros(key, atomic)
            if micros is None:
                unconvertible.append(key)
                continue
            revenue_micros += micros
        revenue: int | None = UNPRICED if unconvertible else revenue_micros

        cost_micros = usage["cost_micros"]
        margin = (
            revenue - cost_micros
            if revenue is not UNPRICED and cost_micros is not UNPRICED
            else UNPRICED
        )
        return {
            "revenue_micros": revenue,
            "cost_micros": cost_micros,
            "margin_micros": margin,
            "settled_amounts": financial.get("settled_amounts", {}),
            "unconvertible_assets": unconvertible,
            "unpriced_providers": usage["unpriced_providers"],
            "cost_table_rejected": usage["cost_table_rejected"],
            "financial": financial,
            "usage": usage,
        }

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

    def indeterminate(self) -> list[dict[str, Any]]:
        """Settlements we never got an answer about: exposure, not revenue.

        The authorization is still in `indeterminate`, so this is the live set
        — an attempt later resolved to `settled` drops out of it.
        """
        return self._query_settlements(
            "SELECT s.* FROM settlements s"
            " JOIN authorizations a ON a.request_id = s.request_id"
            " WHERE a.state = ? AND s.outcome = 'indeterminate' ORDER BY s.id",
            (NonceState.INDETERMINATE.value,),
        )

    def settled_without_transaction(self) -> list[dict[str, Any]]:
        """Successes a facilitator reported with no transaction reference.

        Such an entry proves nothing and must not be counted as revenue on the
        facilitator's word alone.
        """
        return self._query_settlements(
            "SELECT s.* FROM settlements s"
            " JOIN authorizations a ON a.request_id = s.request_id"
            " WHERE a.state = ? AND s.outcome = 'settled'"
            " AND (s.transaction_hash IS NULL OR s.transaction_hash = '')"
            " ORDER BY s.id",
            (NonceState.SETTLED.value,),
        )

    def _query_settlements(self, sql: str, params: tuple) -> list[dict[str, Any]]:
        """Run a complete, literal settlements query. Every caller passes a
        whole statement — no fragment is ever concatenated — so there is no
        path by which caller data reaches the SQL text."""
        try:
            conn = self._connect()
        except LedgerUnavailable:
            return []
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [_settlement_dict(r) for r in rows]

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


def _settlement_dict(row: sqlite3.Row) -> dict[str, Any]:
    """One settlement attempt as plain data. `transaction_hash` is renamed to
    `transaction` because `transaction` is a SQL keyword in the column name
    but the wire and the facilitator both call it that."""
    return {
        "request_id": row["request_id"],
        "nonce": row["nonce"],
        "outcome": row["outcome"],
        "transaction": row["transaction_hash"],
        "network": row["network"],
        "payer": row["payer"],
        "amount": row["amount"],
        "asset": row["asset"],
        "reason": row["reason"],
        "recorded_at": row["recorded_at"],
    }


def _atomic_to_micros(network_and_asset: str, atomic: str) -> int | None:
    """Convert `network/asset` atomic units to micro-USD, or None if we can't.

    Atomic units are per-asset: summing them across assets produces a number
    with no unit. Returns None — never an approximation — when the asset's
    decimals are unknown or when the conversion would need rounding, so the
    caller can report the asset as unconvertible instead of folding a guess
    into a revenue total.
    """
    network, _, _asset = network_and_asset.partition("/")
    entry = USDC_ASSETS.get(network)
    if entry is None:
        return None
    try:
        value = Decimal(atomic).scaleb(6 - int(entry["decimals"]))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if value != value.to_integral_value():
        return None
    return int(value)


def _query_hash(query: str) -> str:
    """Index queries without a second plaintext copy of them on disk.

    The deliverable already contains the query; this column exists so
    reconciliation can group and count without reading response blobs.
    """
    return "sha256:" + hashlib.sha256((query or "").encode("utf-8")).hexdigest()
