"""Shared block board — agents post blocks; Researchers claim and resolve.

Enables cooperative scale: any watcher can post a blocked problem without
waiting to be asked. Autonomous Researchers pick open blocks, research,
solve when local, and report back to the blocked party.

Honesty: resolutions are local/plane artifacts unless they land as code PRs
under the single product claim. Does **not** invent x402 settlement.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STATUSES = ("open", "claimed", "resolved", "wontfix", "escalated")


class BlockBoardError(Exception):
    """Base block board error."""


@dataclass(frozen=True)
class Block:
    block_id: str
    blocked_agent: str
    title: str
    detail: str
    kind: str
    severity: int
    status: str
    claimed_by: str | None
    resolution: str | None
    report_path: str | None
    created_ts: float
    updated_ts: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "blocked_agent": self.blocked_agent,
            "title": self.title,
            "detail": self.detail,
            "kind": self.kind,
            "severity": self.severity,
            "status": self.status,
            "claimed_by": self.claimed_by,
            "resolution": self.resolution,
            "report_path": self.report_path,
            "created_ts": self.created_ts,
            "updated_ts": self.updated_ts,
        }


class BlockBoard:
    """SQLite queue of blocked problems for autonomous Researchers."""

    def __init__(self, path: Path | str | None = None) -> None:
        if path is None:
            path = Path.cwd() / ".veritas" / "block_board.sqlite3"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._init()

    def close(self) -> None:
        self._conn.close()

    def _init(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS blocks (
                block_id TEXT PRIMARY KEY,
                blocked_agent TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT NOT NULL,
                kind TEXT NOT NULL,
                severity INTEGER NOT NULL CHECK (severity >= 0 AND severity <= 3),
                status TEXT NOT NULL,
                claimed_by TEXT,
                resolution TEXT,
                report_path TEXT,
                created_ts REAL NOT NULL,
                updated_ts REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_blocks_status ON blocks(status);
            CREATE INDEX IF NOT EXISTS idx_blocks_agent ON blocks(blocked_agent);
            """
        )

    def _row(self, r: sqlite3.Row) -> Block:
        return Block(
            block_id=str(r["block_id"]),
            blocked_agent=str(r["blocked_agent"]),
            title=str(r["title"]),
            detail=str(r["detail"]),
            kind=str(r["kind"]),
            severity=int(r["severity"]),
            status=str(r["status"]),
            claimed_by=r["claimed_by"],
            resolution=r["resolution"],
            report_path=r["report_path"],
            created_ts=float(r["created_ts"]),
            updated_ts=float(r["updated_ts"]),
        )

    def post(
        self,
        blocked_agent: str,
        title: str,
        detail: str,
        *,
        kind: str = "general",
        severity: int = 2,
    ) -> Block:
        """Any agent posts a block without being asked to wait."""
        blocked_agent = blocked_agent.strip()
        title = title.strip()
        if not blocked_agent or not title:
            raise BlockBoardError("blocked_agent and title required")
        if severity < 0 or severity > 3:
            raise BlockBoardError("severity must be 0..3")
        # Dedup: same agent+title open → return existing
        existing = self._conn.execute(
            "SELECT * FROM blocks WHERE blocked_agent = ? AND title = ? "
            "AND status IN ('open', 'claimed') ORDER BY created_ts DESC LIMIT 1",
            (blocked_agent, title),
        ).fetchone()
        if existing:
            return self._row(existing)
        bid = uuid.uuid4().hex[:12]
        ts = time.time()
        self._conn.execute(
            "INSERT INTO blocks(block_id, blocked_agent, title, detail, kind, "
            "severity, status, claimed_by, resolution, report_path, created_ts, "
            "updated_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                bid,
                blocked_agent,
                title,
                detail,
                kind,
                severity,
                "open",
                None,
                None,
                None,
                ts,
                ts,
            ),
        )
        return self.get(bid)

    def get(self, block_id: str) -> Block:
        row = self._conn.execute(
            "SELECT * FROM blocks WHERE block_id = ?", (block_id,)
        ).fetchone()
        if row is None:
            raise BlockBoardError(f"unknown block {block_id}")
        return self._row(row)

    def list_open(self, *, limit: int = 20) -> list[Block]:
        rows = self._conn.execute(
            "SELECT * FROM blocks WHERE status = 'open' "
            "ORDER BY severity DESC, created_ts ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row(r) for r in rows]

    def list_for_agent(self, agent_id: str) -> list[Block]:
        rows = self._conn.execute(
            "SELECT * FROM blocks WHERE blocked_agent = ? "
            "ORDER BY updated_ts DESC",
            (agent_id,),
        ).fetchall()
        return [self._row(r) for r in rows]

    def claim(self, block_id: str, researcher_id: str) -> Block:
        researcher_id = researcher_id.strip()
        if not researcher_id:
            raise BlockBoardError("researcher_id required")
        c = self._conn.cursor()
        c.execute("BEGIN IMMEDIATE")
        try:
            row = c.execute(
                "SELECT * FROM blocks WHERE block_id = ?", (block_id,)
            ).fetchone()
            if row is None:
                raise BlockBoardError(f"unknown block {block_id}")
            if row["status"] != "open":
                raise BlockBoardError(
                    f"block {block_id} not open (status={row['status']})"
                )
            ts = time.time()
            c.execute(
                "UPDATE blocks SET status = 'claimed', claimed_by = ?, "
                "updated_ts = ? WHERE block_id = ?",
                (researcher_id, ts, block_id),
            )
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        return self.get(block_id)

    def resolve(
        self,
        block_id: str,
        resolution: str,
        *,
        report_path: str | None = None,
        status: str = "resolved",
    ) -> Block:
        if status not in ("resolved", "wontfix", "escalated"):
            raise BlockBoardError("status must be resolved|wontfix|escalated")
        ts = time.time()
        self._conn.execute(
            "UPDATE blocks SET status = ?, resolution = ?, report_path = ?, "
            "updated_ts = ? WHERE block_id = ?",
            (status, resolution, report_path, ts, block_id),
        )
        return self.get(block_id)

    def snapshot(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for s in STATUSES:
            n = self._conn.execute(
                "SELECT COUNT(*) AS n FROM blocks WHERE status = ?", (s,)
            ).fetchone()["n"]
            counts[s] = int(n)
        open_blocks = [b.to_dict() for b in self.list_open(limit=10)]
        return {
            "counts": counts,
            "open": open_blocks,
            "path": str(self.path),
        }

    def write_inbox(
        self,
        blocked_agent: str,
        block: Block,
        *,
        reports_dir: Path | None = None,
    ) -> Path:
        """Write a report the blocked agent can read next tick (no thrash PR)."""
        base = reports_dir or (
            Path.cwd() / "docs" / "program" / "researcher" / "inbox"
        )
        base.mkdir(parents=True, exist_ok=True)
        path = base / f"{blocked_agent}-{block.block_id}.md"
        body = f"""# Research report for `{blocked_agent}`

**Block:** `{block.block_id}`
**Title:** {block.title}
**Status:** {block.status}
**Claimed by:** {block.claimed_by or "-"}
**Kind:** {block.kind} · severity {block.severity}

## Your block (detail)

{block.detail}

## Resolution

{block.resolution or "(in progress)"}

## Next for you

Read this file on your next tick. Do **not** re-post the same title while
status is resolved/claimed. Prefer action over restock PR.

```
PROPERTY: researcher reported back to blocked party without product dual-NEXT
EVIDENCE LEVEL: L1 (block board)
NOT PROVEN: solution is product-correct without battery when code-touched
```
"""
        path.write_text(body, encoding="utf-8")
        return path


def seed_known_blocks(
    board: BlockBoard,
    *,
    force: bool = False,
) -> list[Block]:
    """Seed catalog plane blocks so Researchers act without being asked.

    Catalog seeds are **one-shot per title** until force=True: if the same
    agent+title was already resolved/escalated/wontfix, do **not** re-open
    it. Open/claimed still dedup via ``post``. This stops Researcher ticks
    from thrashing seed→resolve→seed every cadence under free+HOLD.
    """
    seeds = [
        (
            "money_loop",
            "Money-path env unset — probe the defaults before declaring blocked",
            "G9/0.1 needs RPC + facilitator + funded wallet, but an unset env "
            "var is not a block: pinned public testnet defaults ship in code "
            "(chain_reconcile.DEFAULT_PUBLIC_RPC_URLS; unblock_probe probes "
            "them), testnet funding is permissionless (Circle faucet), and "
            "the recipe is proven (docs/program/fable/settlement/). Run "
            "python -m veritas.unblock_probe; 'blocked' requires a dated "
            "failing probe (MIND §3).",
            "money_egress",
            3,
        ),
        (
            "conductor",
            "Product HOLD — no unblocked NEXT",
            "Claim free + Overseer HOLD. Do not invent M7. Prefer Unblock or "
            "Overseer non-money singular bet.",
            "strategy",
            2,
        ),
        (
            "flywheel",
            "Idle-true gate — free+HOLD",
            "WORKFLOW_HYGIENE §1: noop product build until unblocked.",
            "idle",
            1,
        ),
    ]
    out: list[Block] = []
    for agent, title, detail, kind, sev in seeds:
        if not force:
            prior = board._conn.execute(
                "SELECT * FROM blocks WHERE blocked_agent = ? AND title = ? "
                "ORDER BY updated_ts DESC LIMIT 1",
                (agent, title),
            ).fetchone()
            if prior is not None:
                status = str(prior["status"])
                if status in ("open", "claimed"):
                    out.append(board._row(prior))
                    continue
                if status in ("resolved", "escalated", "wontfix"):
                    # Standing catalog item already handled — no reseed thrash
                    continue
        out.append(
            board.post(agent, title, detail, kind=kind, severity=sev)
        )
    return out


def main() -> None:
    board = BlockBoard()
    seed_known_blocks(board)
    print(json.dumps(board.snapshot(), indent=2))
    board.close()


if __name__ == "__main__":
    main()
