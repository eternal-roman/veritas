"""Prepaid credits ledger — double-entry grants, debits, and refunds (M7).

Credits are integer **atomic units** of the settlement asset (USDC atomic
units on the configured network), never floats. A balance is the sum of
signed journal entries for one account; it is never stored as a mutable
counter that can drift from the journal.

Entry kinds:

* ``topup`` — buyer prepaid via x402 (or an explicit operator grant in tests)
* ``debit`` — reserved/spent against a research request
* ``refund`` — reverse a debit when work was non-billable (our failure)
* ``grant`` — non-payment grant (tests / documented operator path only)

Rules (fail closed):

* Debit refuses when balance would go negative.
* Refund requires a prior debit for the same ``request_id`` and never
  refunds more than that debit.
* Account keys are case-folded hex addresses.
* Shared-store seam (same as ``veritas.ledger``): unset
  ``VERITAS_DATABASE_URL`` keeps per-directory SQLite; a sqlite file URL
  or postgres URL shares the journal across instances.
* Per-call connections (handlers run in a threadpool; sqlite3 connections
  are not shareable across threads — same trade as ``Ledger``).

This module does **not** talk to a facilitator or the chain. Settlement that
funds a top-up happens in the payment path; this store only records the
credit once payment has already succeeded (or a deliberate test grant).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .runtime import resolve_runtime_dir
from .store import StoreUnavailable, connect_target, parse_database_url

_DB_FILENAME = "credits.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS credit_entries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account      TEXT NOT NULL,
    kind         TEXT NOT NULL,
    amount       INTEGER NOT NULL,
    request_id   TEXT,
    note         TEXT,
    recorded_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS credit_entries_by_account
    ON credit_entries(account);
CREATE INDEX IF NOT EXISTS credit_entries_by_request
    ON credit_entries(request_id);
"""


class CreditKind(str, Enum):
    TOPUP = "topup"
    DEBIT = "debit"
    REFUND = "refund"
    GRANT = "grant"


class CreditError(Exception):
    """Base for credit ledger refusals."""


class InsufficientCredits(CreditError):
    """Debit would make balance negative."""


class RefundNotAllowed(CreditError):
    """No matching debit, or refund would exceed it."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_account(account: str) -> str:
    """Ledger key for a buyer. Hex-address casing is meaningless on-chain."""
    if not isinstance(account, str) or not account.strip():
        raise CreditError("account must be a non-empty string")
    return account.strip().lower()


@dataclass(frozen=True)
class CreditEntry:
    id: int
    account: str
    kind: str
    amount: int
    request_id: str | None
    note: str | None
    recorded_at: str

    @classmethod
    def _from_row(cls, row: sqlite3.Row) -> CreditEntry:
        return cls(
            id=int(row["id"]),
            account=row["account"],
            kind=row["kind"],
            amount=int(row["amount"]),
            request_id=row["request_id"],
            note=row["note"],
            recorded_at=row["recorded_at"],
        )


class CreditLedger:
    """Append-only double-entry credit journal for one runtime directory."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = resolve_runtime_dir(base_dir)

    @property
    def path(self) -> Path:
        target = self._target()
        if target is not None and target.kind == "sqlite" and target.path is not None:
            return target.path
        return self.base_dir / _DB_FILENAME

    def _target(self):
        try:
            return parse_database_url()
        except StoreUnavailable:
            raise

    def _connect(self):
        try:
            target = self._target()
        except StoreUnavailable as exc:
            raise CreditError(f"store_unavailable:{type(exc).__name__}") from exc
        if target is not None:
            try:
                conn = connect_target(target)
                conn.executescript(_SCHEMA)
                return conn
            except StoreUnavailable as exc:
                raise CreditError(f"store_unavailable:{type(exc).__name__}") from exc
        self.base_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.executescript(_SCHEMA)
        return conn

    def close(self) -> None:
        """No persistent connection; kept for test teardown symmetry."""

    def balance(self, account: str) -> int:
        key = normalize_account(account)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS bal FROM credit_entries WHERE account = ?",
                (key,),
            ).fetchone()
            return int(row["bal"])

    def entries(self, account: str, *, limit: int = 100) -> list[CreditEntry]:
        key = normalize_account(account)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM credit_entries WHERE account = ? "
                "ORDER BY id DESC LIMIT ?",
                (key, max(1, min(limit, 1000))),
            ).fetchall()
            return [CreditEntry._from_row(r) for r in rows]

    def _append(
        self,
        conn: sqlite3.Connection,
        account: str,
        kind: CreditKind,
        amount: int,
        *,
        request_id: str | None = None,
        note: str | None = None,
    ) -> CreditEntry:
        key = normalize_account(account)
        if not isinstance(amount, int) or isinstance(amount, bool) or amount == 0:
            raise CreditError("amount must be a non-zero int")
        if kind is CreditKind.DEBIT:
            amount = -abs(amount)
        else:
            amount = abs(amount)
        if kind is CreditKind.DEBIT and amount >= 0:
            raise CreditError("debit amount must be negative")
        if kind is not CreditKind.DEBIT and amount <= 0:
            raise CreditError(f"{kind.value} amount must be positive")

        cur = conn.execute(
            "INSERT INTO credit_entries (account, kind, amount, request_id, note, recorded_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (key, kind.value, amount, request_id, note, _now()),
        )
        row = conn.execute(
            "SELECT * FROM credit_entries WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        return CreditEntry._from_row(row)

    def grant(
        self,
        account: str,
        amount: int,
        *,
        note: str | None = None,
        kind: CreditKind = CreditKind.GRANT,
    ) -> CreditEntry:
        """Add credits. Prefer TOPUP after settled payment; GRANT is for tests."""
        if kind not in (CreditKind.GRANT, CreditKind.TOPUP):
            raise CreditError("grant path only accepts grant or topup kinds")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise CreditError("grant amount must be a positive int")
        with self._connect() as conn:
            return self._append(conn, account, kind, amount, note=note)

    def topup(
        self,
        account: str,
        amount: int,
        *,
        note: str | None = None,
        request_id: str | None = None,
    ) -> CreditEntry:
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise CreditError("topup amount must be a positive int")
        with self._connect() as conn:
            return self._append(
                conn, account, CreditKind.TOPUP, amount,
                request_id=request_id, note=note,
            )

    def debit(
        self,
        account: str,
        amount: int,
        *,
        request_id: str,
        note: str | None = None,
    ) -> CreditEntry:
        """Reserve/spend credits for a request. Atomic check-and-write.

        Idempotent on ``request_id``: a retry returns the existing debit even
        when the remaining balance would not cover a new spend (full-spend
        retries must not fail closed as insufficient).
        """
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise CreditError("debit amount must be a positive int")
        if not request_id or not isinstance(request_id, str):
            raise CreditError("request_id required for debit")
        key = normalize_account(account)
        with self._connect() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                # Idempotency before balance: a resubmitted request that already
                # spent the account to zero must return the prior entry.
                existing = conn.execute(
                    "SELECT * FROM credit_entries WHERE account = ? AND kind = ? "
                    "AND request_id = ? ORDER BY id DESC LIMIT 1",
                    (key, CreditKind.DEBIT.value, request_id),
                ).fetchone()
                if existing is not None:
                    conn.execute("COMMIT")
                    return CreditEntry._from_row(existing)
                row = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) AS bal FROM credit_entries "
                    "WHERE account = ?",
                    (key,),
                ).fetchone()
                bal = int(row["bal"])
                if bal < amount:
                    raise InsufficientCredits(
                        f"balance {bal} < debit {amount} for {key}"
                    )
                entry = self._append(
                    conn, key, CreditKind.DEBIT, amount,
                    request_id=request_id, note=note,
                )
                conn.execute("COMMIT")
                return entry
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise

    def refund(
        self,
        account: str,
        *,
        request_id: str,
        note: str | None = None,
    ) -> CreditEntry:
        """Refund the debit tied to ``request_id`` (non-billable work).

        Refund total for a request never exceeds abs(debit): one full refund
        entry, further calls return that entry (idempotent, no over-refund).
        """
        if not request_id or not isinstance(request_id, str):
            raise CreditError("request_id required for refund")
        key = normalize_account(account)
        with self._connect() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                debit = conn.execute(
                    "SELECT * FROM credit_entries WHERE account = ? AND kind = ? "
                    "AND request_id = ? ORDER BY id DESC LIMIT 1",
                    (key, CreditKind.DEBIT.value, request_id),
                ).fetchone()
                if debit is None:
                    raise RefundNotAllowed(f"no debit for request_id={request_id!r}")
                already = conn.execute(
                    "SELECT * FROM credit_entries WHERE account = ? AND kind = ? "
                    "AND request_id = ? ORDER BY id DESC LIMIT 1",
                    (key, CreditKind.REFUND.value, request_id),
                ).fetchone()
                if already is not None:
                    conn.execute("COMMIT")
                    return CreditEntry._from_row(already)
                # Cap: refund equals the debit magnitude only (never more).
                refunded_row = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) AS refunded FROM credit_entries "
                    "WHERE account = ? AND kind = ? AND request_id = ?",
                    (key, CreditKind.REFUND.value, request_id),
                ).fetchone()
                refunded = int(refunded_row["refunded"])
                debit_amount = abs(int(debit["amount"]))
                remaining = debit_amount - refunded
                if remaining <= 0:
                    raise RefundNotAllowed(
                        f"debit for request_id={request_id!r} already fully refunded"
                    )
                entry = self._append(
                    conn,
                    key,
                    CreditKind.REFUND,
                    remaining,
                    request_id=request_id,
                    note=note or "refund_non_billable",
                )
                conn.execute("COMMIT")
                return entry
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise

    def summary(self, account: str) -> dict[str, Any]:
        key = normalize_account(account)
        return {
            "account": key,
            "balance": self.balance(key),
            "unit": "atomic_usdc",
            "entries": [
                {
                    "id": e.id,
                    "kind": e.kind,
                    "amount": e.amount,
                    "request_id": e.request_id,
                    "note": e.note,
                    "recorded_at": e.recorded_at,
                }
                for e in self.entries(key, limit=20)
            ],
        }
