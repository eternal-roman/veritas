"""Plane-local agent money (VAAT) — not x402, not on-chain settlement.

Each agent holds a balance in **VAAT** (Veritas Agent Atomic Tokens), integer
atomic units only. Transfers are append-only and hash-chained so agents can
audit the journal without trusting a single in-memory dict.

Honesty bound (load-bearing):
- This module is for **plane / agent-to-agent coordination** inside the control
  plane and local experiments.
- It does **not** settle USDC, talk to a facilitator, or close constitution G9.
- Product ``settlements`` remain **0** until Phase 0.1 proves real pay.
- Supply is **limited** (``max_supply``) so VAAT is a scarce local medium.

Inspired by: in-tree ``veritas.credits`` double-entry discipline; local
hash-chained journals; agent-wallet "spend within bounds" patterns (GitHub).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CURRENCY = "VAAT"
CURRENCY_NAME = "Veritas Agent Atomic Token"
SCHEMA_VERSION = 2
DEFAULT_MAX_SUPPLY = 1_000_000
TREASURY_ID = "plane:treasury"


class AgentMoneyError(Exception):
    """Base error for plane money."""


class InsufficientFunds(AgentMoneyError):
    """Spend exceeds available balance."""


class UnknownAgent(AgentMoneyError):
    """Agent id not registered."""


class ChainIntegrityError(AgentMoneyError):
    """Journal hash chain broken."""


class SupplyExhausted(AgentMoneyError):
    """Mint would exceed limited max_supply."""


def _now() -> float:
    return time.time()


def _canonical(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class Transfer:
    seq: int
    from_agent: str
    to_agent: str
    amount: int
    memo: str
    ts: float
    prev_hash: str
    entry_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "amount": self.amount,
            "memo": self.memo,
            "ts": self.ts,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
            "currency": CURRENCY,
        }


class AgentMoneyLedger:
    """SQLite plane ledger: register agents, mint (bootstrap), transfer, verify chain."""

    GENESIS_HASH = "0" * 64

    def __init__(self, path: Path | str | None = None) -> None:
        if path is None:
            path = Path.cwd() / ".veritas" / "agent_money.sqlite3"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        c = self._conn.cursor()
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                created_ts REAL NOT NULL,
                meta_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS balances (
                agent_id TEXT PRIMARY KEY,
                amount INTEGER NOT NULL CHECK (amount >= 0),
                FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
            );
            CREATE TABLE IF NOT EXISTS journal (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                from_agent TEXT NOT NULL,
                to_agent TEXT NOT NULL,
                amount INTEGER NOT NULL CHECK (amount > 0),
                memo TEXT NOT NULL,
                ts REAL NOT NULL,
                prev_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL UNIQUE
            );
            """
        )
        c.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        c.execute(
            "UPDATE meta SET value = ? WHERE key = 'schema_version'",
            (str(SCHEMA_VERSION),),
        )
        c.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('currency', ?)",
            (CURRENCY,),
        )
        c.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ("
            "'not_x402_settlement', 'true')"
        )
        c.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('max_supply', ?)",
            (str(DEFAULT_MAX_SUPPLY),),
        )
        row = c.execute(
            "SELECT value FROM meta WHERE key = 'total_minted'"
        ).fetchone()
        if row is None:
            minted = c.execute(
                "SELECT COALESCE(SUM(amount), 0) AS s FROM journal "
                "WHERE from_agent = ?",
                (TREASURY_ID,),
            ).fetchone()["s"]
            c.execute(
                "INSERT INTO meta(key, value) VALUES ('total_minted', ?)",
                (str(int(minted)),),
            )

    def _meta_get(self, key: str, default: str = "") -> str:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return str(row["value"]) if row else default

    def _meta_set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def max_supply(self) -> int:
        return int(self._meta_get("max_supply", str(DEFAULT_MAX_SUPPLY)))

    def total_minted(self) -> int:
        return int(self._meta_get("total_minted", "0"))

    def remaining_supply(self) -> int:
        return max(0, self.max_supply() - self.total_minted())

    def set_max_supply(self, n: int) -> None:
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            raise AgentMoneyError("max_supply must be non-negative int")
        if n < self.total_minted():
            raise AgentMoneyError("max_supply below total_minted")
        self._meta_set("max_supply", str(n))

    def register(self, agent_id: str, *, meta: dict[str, Any] | None = None) -> None:
        agent_id = agent_id.strip()
        if not agent_id:
            raise AgentMoneyError("empty agent_id")
        meta = meta or {}
        c = self._conn.cursor()
        c.execute(
            "INSERT OR IGNORE INTO agents(agent_id, created_ts, meta_json) "
            "VALUES (?, ?, ?)",
            (agent_id, _now(), json.dumps(meta, sort_keys=True)),
        )
        c.execute(
            "INSERT OR IGNORE INTO balances(agent_id, amount) VALUES (?, 0)",
            (agent_id,),
        )

    def ensure_agents(self, agent_ids: Iterable[str]) -> None:
        for a in agent_ids:
            self.register(a)

    def balance(self, agent_id: str) -> int:
        c = self._conn.cursor()
        row = c.execute(
            "SELECT amount FROM balances WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        if row is None:
            raise UnknownAgent(agent_id)
        return int(row["amount"])

    def agent_meta(self, agent_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT meta_json FROM agents WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        if row is None:
            raise UnknownAgent(agent_id)
        return dict(json.loads(row["meta_json"] or "{}"))

    def list_agent_ids(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT agent_id FROM agents ORDER BY agent_id"
        ).fetchall()
        return [str(r["agent_id"]) for r in rows]

    def _last_hash(self) -> str:
        row = self._conn.execute(
            "SELECT entry_hash FROM journal ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return str(row["entry_hash"]) if row else self.GENESIS_HASH

    def _append(
        self,
        from_agent: str,
        to_agent: str,
        amount: int,
        memo: str,
    ) -> Transfer:
        if amount <= 0:
            raise AgentMoneyError("amount must be positive integer")
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise AgentMoneyError("amount must be int (no floats)")
        prev = self._last_hash()
        ts = _now()
        body = {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "amount": amount,
            "memo": memo,
            "ts": ts,
            "prev_hash": prev,
            "currency": CURRENCY,
        }
        entry_hash = _hash_hex(_canonical(body))
        c = self._conn.cursor()
        c.execute(
            "INSERT INTO journal(from_agent, to_agent, amount, memo, ts, "
            "prev_hash, entry_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (from_agent, to_agent, amount, memo, ts, prev, entry_hash),
        )
        seq = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
        return Transfer(
            seq=seq,
            from_agent=from_agent,
            to_agent=to_agent,
            amount=amount,
            memo=memo,
            ts=ts,
            prev_hash=prev,
            entry_hash=entry_hash,
        )

    def mint(self, to_agent: str, amount: int, *, memo: str = "mint") -> Transfer:
        """Bootstrap mint from plane treasury (not product USDC).

        Enforces limited ``max_supply``. Does **not** create USDC or close G9.
        """
        self.register(to_agent)
        self.register(TREASURY_ID, meta={"role": "treasury"})
        if amount <= 0:
            raise AgentMoneyError("amount must be positive integer")
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise AgentMoneyError("amount must be int (no floats)")
        c = self._conn.cursor()
        c.execute("BEGIN IMMEDIATE")
        try:
            minted = self.total_minted()
            cap = self.max_supply()
            if minted + amount > cap:
                raise SupplyExhausted(
                    f"mint {amount} would exceed max_supply={cap} "
                    f"(minted={minted}, remaining={cap - minted})"
                )
            tr = self._append(TREASURY_ID, to_agent, amount, memo)
            c.execute(
                "UPDATE balances SET amount = amount + ? WHERE agent_id = ?",
                (amount, to_agent),
            )
            self._meta_set("total_minted", str(minted + amount))
            c.execute("COMMIT")
            return tr
        except Exception:
            c.execute("ROLLBACK")
            raise

    def transfer(
        self,
        from_agent: str,
        to_agent: str,
        amount: int,
        *,
        memo: str = "",
    ) -> Transfer:
        self.register(from_agent)
        self.register(to_agent)
        if from_agent == to_agent:
            raise AgentMoneyError("self-transfer forbidden")
        c = self._conn.cursor()
        c.execute("BEGIN IMMEDIATE")
        try:
            bal = self.balance(from_agent)
            if bal < amount:
                raise InsufficientFunds(
                    f"{from_agent} has {bal} {CURRENCY}, need {amount}"
                )
            tr = self._append(from_agent, to_agent, amount, memo)
            c.execute(
                "UPDATE balances SET amount = amount - ? WHERE agent_id = ?",
                (amount, from_agent),
            )
            c.execute(
                "UPDATE balances SET amount = amount + ? WHERE agent_id = ?",
                (amount, to_agent),
            )
            c.execute("COMMIT")
            return tr
        except Exception:
            c.execute("ROLLBACK")
            raise

    def verify_chain(self) -> bool:
        prev = self.GENESIS_HASH
        rows = self._conn.execute(
            "SELECT from_agent, to_agent, amount, memo, ts, prev_hash, entry_hash "
            "FROM journal ORDER BY seq ASC"
        ).fetchall()
        for row in rows:
            if row["prev_hash"] != prev:
                raise ChainIntegrityError(
                    f"prev_hash mismatch at {row['entry_hash']}"
                )
            body = {
                "from_agent": row["from_agent"],
                "to_agent": row["to_agent"],
                "amount": int(row["amount"]),
                "memo": row["memo"],
                "ts": float(row["ts"]),
                "prev_hash": row["prev_hash"],
                "currency": CURRENCY,
            }
            expect = _hash_hex(_canonical(body))
            if expect != row["entry_hash"]:
                raise ChainIntegrityError(f"entry hash mismatch {row['entry_hash']}")
            prev = row["entry_hash"]
        return True

    def snapshot(self) -> dict[str, Any]:
        agents = {
            r["agent_id"]: int(r["amount"])
            for r in self._conn.execute(
                "SELECT b.agent_id, b.amount FROM balances b ORDER BY b.agent_id"
            )
        }
        n = self._conn.execute("SELECT COUNT(*) AS n FROM journal").fetchone()["n"]
        return {
            "currency": CURRENCY,
            "currency_name": CURRENCY_NAME,
            "not_x402_settlement": True,
            "schema_version": SCHEMA_VERSION,
            "journal_entries": int(n),
            "balances": agents,
            "tip_hash": self._last_hash(),
            "max_supply": self.max_supply(),
            "total_minted": self.total_minted(),
            "remaining_supply": self.remaining_supply(),
            "limited_supply": True,
        }
