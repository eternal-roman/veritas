"""Agent economy: identity + wallet + quality-based local compensation.

Every plane agent has:
  1. **Identity** — plane visa (HMAC; SPIFFE/DID *pattern*, not production SPIRE)
  2. **Wallet** — VAAT balance on the limited-supply ledger
  3. **Compensation** — VAAT paid for effort scaled by quality score 0–3

Honesty bound (load-bearing):
- Local / plane only. **Not** x402, **not** USDC, **not** G9 settlement.
- Quality scores are inputs (caller must supply honest 0–3); this module
  enforces pay math and journal integrity, not human-grade evaluation of code.

Run: ``python -m veritas.agent_economy`` (bootstrap + sample status)
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from veritas.agent_identity import (
    PlaneIdentityIssuer,
    PlaneVisa,
)
from veritas.agent_money import (
    CURRENCY,
    TREASURY_ID,
    AgentMoneyLedger,
    Transfer,
    UnknownAgent,
)

# Quality → pay multiplier (base units). quality 0 → no pay.
BASE_EFFORT_VAAT = 25
QUALITY_MULTIPLIER = {0: 0, 1: 1, 2: 2, 3: 4}

# Plane SPIFFE-like URI shape (not a real SVID).
PLANE_TRUST_DOMAIN = "veritas.local"


class AgentEconomyError(Exception):
    """Base economy error."""


class QualityError(AgentEconomyError):
    """Invalid quality score."""


@dataclass(frozen=True)
class AgentAccount:
    """Identity + wallet snapshot for one agent."""

    agent_id: str
    role: str
    plane_id: str
    did: str
    balance_vaat: int
    visa: dict[str, Any]
    not_x402_settlement: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "plane_id": self.plane_id,
            "did": self.did,
            "balance_vaat": self.balance_vaat,
            "currency": CURRENCY,
            "visa": self.visa,
            "not_x402_settlement": True,
        }


def plane_id_for(agent_id: str, role: str) -> str:
    """SPIFFE-shaped plane path: spiffe://veritas.local/role/{role}/agent/{id}."""
    return f"spiffe://{PLANE_TRUST_DOMAIN}/role/{role}/agent/{agent_id}"


def did_for(agent_id: str) -> str:
    """Local DID method (not registered W3C DID method)."""
    return f"did:veritas:plane:{agent_id}"


def pay_for_quality(quality: int, *, base: int = BASE_EFFORT_VAAT) -> int:
    if quality not in QUALITY_MULTIPLIER:
        raise QualityError(f"quality must be 0..3, got {quality!r}")
    if not isinstance(base, int) or isinstance(base, bool) or base < 0:
        raise AgentEconomyError("base must be non-negative int")
    return base * QUALITY_MULTIPLIER[quality]


class AgentEconomy:
    """Bind identity issuer + limited VAAT ledger + effort compensation journal."""

    def __init__(
        self,
        base_dir: Path | str | None = None,
        *,
        max_supply: int | None = None,
    ) -> None:
        base = Path(base_dir) if base_dir else Path.cwd() / ".veritas"
        base.mkdir(parents=True, exist_ok=True)
        self.base = base
        self.money_path = base / "agent_money.sqlite3"
        self.secret_path = base / "plane_identity.secret"
        self.visa_path = base / "plane_visas.json"
        self.effort_path = base / "agent_effort.sqlite3"
        self.ledger = AgentMoneyLedger(self.money_path)
        if max_supply is not None:
            self.ledger.set_max_supply(max_supply)
        self.secret = self._load_or_create_secret()
        self.issuer = PlaneIdentityIssuer(self.secret)
        self._init_effort()

    def _load_or_create_secret(self) -> bytes:
        import hashlib
        import os

        from veritas.agent_identity import _read_secret_file, _write_secret_file

        if self.secret_path.is_file():
            return _read_secret_file(self.secret_path)
        raw = hashlib.sha256(os.urandom(32)).digest()
        _write_secret_file(self.secret_path, raw)
        return raw

    def close(self) -> None:
        self.ledger.close()
        self._effort.close()

    def _init_effort(self) -> None:
        self._effort = sqlite3.connect(str(self.effort_path), isolation_level=None)
        self._effort.row_factory = sqlite3.Row
        self._effort.executescript(
            """
            CREATE TABLE IF NOT EXISTS efforts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                role TEXT NOT NULL,
                quality INTEGER NOT NULL CHECK (quality >= 0 AND quality <= 3),
                pay_vaat INTEGER NOT NULL CHECK (pay_vaat >= 0),
                effort_kind TEXT NOT NULL,
                evidence TEXT NOT NULL,
                transfer_hash TEXT,
                ts REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_efforts_agent ON efforts(agent_id);
            """
        )

    def ensure_agent(
        self,
        agent_id: str,
        role: str,
        *,
        stipend: int = 0,
        ttl_seconds: int = 86400 * 7,
    ) -> AgentAccount:
        """Register wallet + issue/refresh visa. Optional bootstrap stipend."""
        agent_id = agent_id.strip()
        role = role.strip()
        if not agent_id or not role:
            raise AgentEconomyError("agent_id and role required")
        self.ledger.register(
            agent_id,
            meta={
                "role": role,
                "plane_id": plane_id_for(agent_id, role),
                "did": did_for(agent_id),
            },
        )
        if stipend > 0 and self.ledger.balance(agent_id) == 0:
            self.ledger.mint(agent_id, stipend, memo=f"stipend:{role}")
        visa = self.issuer.issue(
            agent_id,
            role,
            ttl_seconds=ttl_seconds,
            claims={
                "plane_id": plane_id_for(agent_id, role),
                "did": did_for(agent_id),
                "wallet_currency": CURRENCY,
            },
        )
        self._persist_visa(visa)
        return self.account(agent_id)

    def _persist_visa(self, visa: PlaneVisa) -> None:
        data: dict[str, Any] = {}
        if self.visa_path.is_file():
            data = json.loads(self.visa_path.read_text(encoding="utf-8"))
        data[visa.agent_id] = visa.to_dict()
        self.visa_path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def account(self, agent_id: str) -> AgentAccount:
        try:
            meta = self.ledger.agent_meta(agent_id)
        except UnknownAgent as e:
            raise AgentEconomyError(f"unknown agent {agent_id}") from e
        role = str(meta.get("role") or "agent")
        visas: dict[str, Any] = {}
        if self.visa_path.is_file():
            visas = json.loads(self.visa_path.read_text(encoding="utf-8"))
        visa = visas.get(agent_id) or {}
        return AgentAccount(
            agent_id=agent_id,
            role=role,
            plane_id=str(meta.get("plane_id") or plane_id_for(agent_id, role)),
            did=str(meta.get("did") or did_for(agent_id)),
            balance_vaat=self.ledger.balance(agent_id),
            visa=visa,
        )

    def compensate(
        self,
        agent_id: str,
        quality: int,
        *,
        effort_kind: str,
        evidence: str,
        base: int = BASE_EFFORT_VAAT,
    ) -> dict[str, Any]:
        """Pay agent VAAT for effort; amount = base × quality multiplier.

        quality 0 → 0 pay (still journals the effort).
        Pay is **minted** from plane treasury under limited supply.
        """
        if quality not in QUALITY_MULTIPLIER:
            raise QualityError(f"quality must be 0..3, got {quality!r}")
        pay = pay_for_quality(quality, base=base)
        acc = self.account(agent_id)
        tr: Transfer | None = None
        thash: str | None = None
        if pay > 0:
            tr = self.ledger.mint(
                agent_id,
                pay,
                memo=f"effort:{effort_kind}:q{quality}:{evidence[:80]}",
            )
            thash = tr.entry_hash
        ts = time.time()
        self._effort.execute(
            "INSERT INTO efforts(agent_id, role, quality, pay_vaat, effort_kind, "
            "evidence, transfer_hash, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                agent_id,
                acc.role,
                quality,
                pay,
                effort_kind,
                evidence,
                thash,
                ts,
            ),
        )
        return {
            "agent_id": agent_id,
            "role": acc.role,
            "quality": quality,
            "pay_vaat": pay,
            "effort_kind": effort_kind,
            "evidence": evidence,
            "transfer_hash": thash,
            "balance_after": self.ledger.balance(agent_id),
            "currency": CURRENCY,
            "not_x402_settlement": True,
            "treasury": TREASURY_ID,
        }

    def effort_history(self, agent_id: str | None = None) -> list[dict[str, Any]]:
        if agent_id:
            rows = self._effort.execute(
                "SELECT * FROM efforts WHERE agent_id = ? ORDER BY id ASC",
                (agent_id,),
            ).fetchall()
        else:
            rows = self._effort.execute(
                "SELECT * FROM efforts ORDER BY id ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def snapshot(self) -> dict[str, Any]:
        money = self.ledger.snapshot()
        money["effort_count"] = self._effort.execute(
            "SELECT COUNT(*) AS n FROM efforts"
        ).fetchone()["n"]
        money["agents"] = []
        for aid in sorted(money["balances"].keys()):
            if aid.startswith("plane:"):
                continue
            try:
                money["agents"].append(self.account(aid).to_dict())
            except AgentEconomyError:
                pass
        return money


# Full plane roster — every established control-plane role.
FULL_ROSTER: dict[str, str] = {
    "overseer": "overseer",
    "conductor": "conductor",
    "steward": "steward",
    "scout": "scout",
    "pruner": "pruner",
    "flywheel": "flywheel",
    "architect": "architect",
    "git_agent": "git_agent",
    "optimizer": "optimizer",
    "mesh_runner": "mesh_runner",
    "unblock": "unblock",
    "money_loop": "money_loop",
    "multiparty_trust": "multiparty_trust",
    "product_worth": "product_worth",
    "discovery_density": "discovery_density",
    "multi_tenant": "multi_tenant",
    "legal_identity": "legal_identity",
    "network_effects": "network_effects",
}


def bootstrap_economy(
    base_dir: Path | str | None = None,
    *,
    stipend: int = 500,
    roster: dict[str, str] | None = None,
    max_supply: int | None = None,
) -> dict[str, Any]:
    """Ensure every roster agent has identity + wallet; optional stipend."""
    eco = AgentEconomy(base_dir, max_supply=max_supply)
    roster = roster or FULL_ROSTER
    accounts = []
    for agent_id, role in roster.items():
        accounts.append(
            eco.ensure_agent(agent_id, role, stipend=stipend).to_dict()
        )
    eco.ledger.verify_chain()
    out = {
        "accounts": accounts,
        "money": eco.ledger.snapshot(),
        "not_x402_settlement": True,
        "paths": {
            "money": str(eco.money_path),
            "visas": str(eco.visa_path),
            "effort": str(eco.effort_path),
        },
    }
    eco.close()
    return out


def main() -> None:
    out = bootstrap_economy()
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
