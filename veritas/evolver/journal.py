"""Evolver problem journal — roadblock to origin mapping."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STATUSES = (
    "open",
    "evolving",
    "synthesized",
    "reported_origin",
    "overseer_queued",
    "engineering",
    "closed",
    "wontfix",
)
KINDS = (
    "block",
    "concern",
    "issue",
    "stall",
    "strategy",
    "money_egress",
    "technical",
    "general",
)


class JournalError(Exception):
    pass


@dataclass(frozen=True)
class Problem:
    problem_id: str
    sender_agent: str
    sender_role: str
    kind: str
    title: str
    detail: str
    severity: int
    status: str
    source_surface: str
    correlation_id: str
    claimed_by: str | None
    best_blueprint: str | None
    best_score: float | None
    synthesis_json_path: str | None
    origin_report_path: str | None
    overseer_report_path: str | None
    engineering_report_path: str | None
    created_ts: float
    updated_ts: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "sender_agent": self.sender_agent,
            "sender_role": self.sender_role,
            "kind": self.kind,
            "title": self.title,
            "detail": self.detail,
            "severity": self.severity,
            "status": self.status,
            "source_surface": self.source_surface,
            "correlation_id": self.correlation_id,
            "claimed_by": self.claimed_by,
            "best_blueprint": self.best_blueprint,
            "best_score": self.best_score,
            "synthesis_json_path": self.synthesis_json_path,
            "origin_report_path": self.origin_report_path,
            "overseer_report_path": self.overseer_report_path,
            "engineering_report_path": self.engineering_report_path,
            "created_ts": self.created_ts,
            "updated_ts": self.updated_ts,
            "workflow": workflow_phase(self.status),
        }


def workflow_phase(status: str) -> str:
    return {
        "open": "1_submitted",
        "evolving": "2_claimed_by_evolver",
        "synthesized": "3_evolved",
        "reported_origin": "4_mapped_to_origin",
        "overseer_queued": "5_overseer_notified",
        "engineering": "6_engineering_handoff",
        "closed": "7_closed",
        "wontfix": "7_closed_wontfix",
    }.get(status, f"unknown_{status}")


def default_journal_path() -> Path:
    return Path.cwd() / ".veritas" / "evolver_journal.sqlite3"


def default_artifact_root() -> Path:
    return Path.cwd() / "docs" / "program" / "evolver"


class ProblemJournal:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else default_journal_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._init()

    def close(self) -> None:
        self._conn.close()

    def _init(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS problems (
                problem_id TEXT PRIMARY KEY,
                sender_agent TEXT NOT NULL,
                sender_role TEXT NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT NOT NULL,
                severity INTEGER NOT NULL CHECK (severity >= 0 AND severity <= 3),
                status TEXT NOT NULL,
                source_surface TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                claimed_by TEXT,
                best_blueprint TEXT,
                best_score REAL,
                synthesis_json_path TEXT,
                origin_report_path TEXT,
                overseer_report_path TEXT,
                engineering_report_path TEXT,
                created_ts REAL NOT NULL,
                updated_ts REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ej_status ON problems(status);
            CREATE INDEX IF NOT EXISTS idx_ej_sender ON problems(sender_agent);
            """
        )

    def _row(self, r: sqlite3.Row) -> Problem:
        return Problem(
            problem_id=str(r["problem_id"]),
            sender_agent=str(r["sender_agent"]),
            sender_role=str(r["sender_role"] or ""),
            kind=str(r["kind"]),
            title=str(r["title"]),
            detail=str(r["detail"]),
            severity=int(r["severity"]),
            status=str(r["status"]),
            source_surface=str(r["source_surface"] or ""),
            correlation_id=str(r["correlation_id"] or ""),
            claimed_by=r["claimed_by"],
            best_blueprint=r["best_blueprint"],
            best_score=r["best_score"],
            synthesis_json_path=r["synthesis_json_path"],
            origin_report_path=r["origin_report_path"],
            overseer_report_path=r["overseer_report_path"],
            engineering_report_path=r["engineering_report_path"],
            created_ts=float(r["created_ts"]),
            updated_ts=float(r["updated_ts"]),
        )

    def submit(
        self,
        sender_agent: str,
        title: str,
        detail: str,
        *,
        kind: str = "block",
        severity: int = 2,
        sender_role: str = "",
        source_surface: str = "",
        correlation_id: str = "",
    ) -> Problem:
        sender_agent = sender_agent.strip()
        title = title.strip()
        kind = (kind or "general").strip().lower()
        if not sender_agent or not title:
            raise JournalError("sender_agent and title required")
        if kind not in KINDS:
            raise JournalError(f"kind must be one of {KINDS}")
        if severity < 0 or severity > 3:
            raise JournalError("severity must be 0..3")
        sender_role = (sender_role or sender_agent).strip()
        existing = self._conn.execute(
            "SELECT * FROM problems WHERE sender_agent = ? AND title = ? "
            "AND status IN ('open','evolving','synthesized','reported_origin',"
            "'overseer_queued','engineering') "
            "ORDER BY created_ts DESC LIMIT 1",
            (sender_agent, title),
        ).fetchone()
        if existing:
            return self._row(existing)
        pid = uuid.uuid4().hex[:12]
        ts = time.time()
        self._conn.execute(
            "INSERT INTO problems("
            "problem_id, sender_agent, sender_role, kind, title, detail, "
            "severity, status, source_surface, correlation_id, claimed_by, "
            "best_blueprint, best_score, synthesis_json_path, origin_report_path, "
            "overseer_report_path, engineering_report_path, created_ts, updated_ts"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                pid, sender_agent, sender_role, kind, title, detail, severity,
                "open", source_surface, correlation_id or pid, None, None, None,
                None, None, None, None, ts, ts,
            ),
        )
        self._audit({"event": "submit", "problem_id": pid, "sender_agent": sender_agent, "title": title, "ts": ts})
        return self.get(pid)

    def get(self, problem_id: str) -> Problem:
        row = self._conn.execute(
            "SELECT * FROM problems WHERE problem_id = ?", (problem_id,)
        ).fetchone()
        if row is None:
            raise JournalError(f"unknown problem {problem_id}")
        return self._row(row)

    def list_open(self, *, limit: int = 20) -> list[Problem]:
        rows = self._conn.execute(
            "SELECT * FROM problems WHERE status = 'open' "
            "ORDER BY severity DESC, created_ts ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row(r) for r in rows]

    def list_for_sender(self, sender_agent: str) -> list[Problem]:
        rows = self._conn.execute(
            "SELECT * FROM problems WHERE sender_agent = ? ORDER BY updated_ts DESC",
            (sender_agent,),
        ).fetchall()
        return [self._row(r) for r in rows]

    def claim(self, problem_id: str, evolver_id: str = "evolver") -> Problem:
        evolver_id = evolver_id.strip() or "evolver"
        c = self._conn.cursor()
        c.execute("BEGIN IMMEDIATE")
        try:
            row = c.execute(
                "SELECT * FROM problems WHERE problem_id = ?", (problem_id,)
            ).fetchone()
            if row is None:
                raise JournalError(f"unknown problem {problem_id}")
            if row["status"] != "open":
                raise JournalError(f"problem {problem_id} not open (status={row['status']})")
            ts = time.time()
            c.execute(
                "UPDATE problems SET status = 'evolving', claimed_by = ?, updated_ts = ? "
                "WHERE problem_id = ?",
                (evolver_id, ts, problem_id),
            )
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        self._audit({"event": "claim", "problem_id": problem_id, "claimed_by": evolver_id, "ts": time.time()})
        return self.get(problem_id)

    def claim_next(self, evolver_id: str = "evolver") -> Problem | None:
        open_ = self.list_open(limit=1)
        if not open_:
            return None
        return self.claim(open_[0].problem_id, evolver_id)

    def attach_synthesis(
        self,
        problem_id: str,
        *,
        best_blueprint: str,
        best_score: float,
        synthesis_json_path: str | None = None,
    ) -> Problem:
        p = self.get(problem_id)
        if p.status not in ("evolving", "synthesized"):
            raise JournalError(f"attach_synthesis requires evolving|synthesized, got {p.status}")
        ts = time.time()
        self._conn.execute(
            "UPDATE problems SET status = 'synthesized', best_blueprint = ?, "
            "best_score = ?, synthesis_json_path = ?, updated_ts = ? WHERE problem_id = ?",
            (best_blueprint, float(best_score), synthesis_json_path, ts, problem_id),
        )
        self._audit({"event": "synthesize", "problem_id": problem_id, "best_score": best_score, "ts": ts})
        return self.get(problem_id)

    def report_to_origin(self, problem_id: str, *, artifact_root: Path | None = None) -> Problem:
        p = self.get(problem_id)
        if p.status not in ("synthesized", "reported_origin", "overseer_queued", "engineering"):
            raise JournalError(f"report_to_origin requires synthesized+, got {p.status}")
        root = artifact_root or default_artifact_root()
        inbox = root / "inbox" / p.sender_agent
        inbox.mkdir(parents=True, exist_ok=True)
        path = inbox / f"{p.problem_id}.md"
        path.write_text(_origin_md(p), encoding="utf-8")
        ts = time.time()
        new_status = "reported_origin" if p.status == "synthesized" else p.status
        self._conn.execute(
            "UPDATE problems SET status = ?, origin_report_path = ?, updated_ts = ? WHERE problem_id = ?",
            (new_status, str(path), ts, problem_id),
        )
        self._audit({"event": "report_origin", "problem_id": problem_id, "sender_agent": p.sender_agent, "path": str(path), "ts": ts})
        return self.get(problem_id)

    def report_to_overseer(self, problem_id: str, *, artifact_root: Path | None = None) -> Problem:
        p = self.get(problem_id)
        if p.status not in ("synthesized", "reported_origin", "overseer_queued", "engineering"):
            raise JournalError(f"report_to_overseer requires synthesized+, got {p.status}")
        if p.status == "synthesized":
            p = self.report_to_origin(problem_id, artifact_root=artifact_root)
        root = artifact_root or default_artifact_root()
        outbox = root / "outbox" / "overseer"
        outbox.mkdir(parents=True, exist_ok=True)
        path = outbox / f"{p.problem_id}.md"
        path.write_text(_overseer_md(p), encoding="utf-8")
        index = outbox / "INDEX.md"
        line = f"- `{p.problem_id}` from **{p.sender_agent}** ({p.kind}/sev{p.severity}): {p.title} → {path.name}\n"
        if index.is_file():
            prev = index.read_text(encoding="utf-8")
            if p.problem_id not in prev:
                index.write_text(prev.rstrip() + "\n" + line, encoding="utf-8")
        else:
            index.write_text("# Evolver → Overseer outbox\n\nWATCH only — never auto STATE NEXT.\n\n" + line, encoding="utf-8")
        ts = time.time()
        new_status = "overseer_queued" if p.status in ("synthesized", "reported_origin") else p.status
        self._conn.execute(
            "UPDATE problems SET status = ?, overseer_report_path = ?, updated_ts = ? WHERE problem_id = ?",
            (new_status, str(path), ts, problem_id),
        )
        self._audit({"event": "report_overseer", "problem_id": problem_id, "path": str(path), "ts": ts})
        return self.get(problem_id)

    def handoff_engineering(self, problem_id: str, *, artifact_root: Path | None = None) -> Problem:
        p = self.get(problem_id)
        if p.status not in ("synthesized", "reported_origin", "overseer_queued", "engineering"):
            raise JournalError(f"handoff_engineering requires synthesized+, got {p.status}")
        if p.status == "synthesized":
            p = self.report_to_origin(problem_id, artifact_root=artifact_root)
        root = artifact_root or default_artifact_root()
        eng = root / "engineering"
        eng.mkdir(parents=True, exist_ok=True)
        path = eng / f"{p.problem_id}.md"
        path.write_text(_engineering_md(p), encoding="utf-8")
        ts = time.time()
        new_status = "engineering" if p.status in ("synthesized", "reported_origin", "overseer_queued") else p.status
        self._conn.execute(
            "UPDATE problems SET status = ?, engineering_report_path = ?, updated_ts = ? WHERE problem_id = ?",
            (new_status, str(path), ts, problem_id),
        )
        self._audit({"event": "handoff_engineering", "problem_id": problem_id, "path": str(path), "ts": ts})
        return self.get(problem_id)

    def close_problem(self, problem_id: str, *, reason: str = "") -> Problem:
        p = self.get(problem_id)
        if p.status in ("closed", "wontfix"):
            return p
        ts = time.time()
        self._conn.execute(
            "UPDATE problems SET status = 'closed', updated_ts = ? WHERE problem_id = ?",
            (ts, problem_id),
        )
        self._audit({"event": "close", "problem_id": problem_id, "reason": reason, "ts": ts})
        return self.get(problem_id)

    def snapshot(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for s in STATUSES:
            n = self._conn.execute(
                "SELECT COUNT(*) AS n FROM problems WHERE status = ?", (s,)
            ).fetchone()["n"]
            counts[s] = int(n)
        return {
            "schema": "veritas.evolver.journal.v0",
            "path": str(self.path),
            "counts": counts,
            "open": [p.to_dict() for p in self.list_open(limit=15)],
            "workflow": [
                "submit", "claim", "synthesize", "report_origin",
                "report_overseer", "handoff_engineering", "close",
            ],
            "not_state_next": True,
        }

    def _audit(self, event: dict[str, Any]) -> None:
        audit = self.path.with_suffix(".audit.jsonl")
        with audit.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True, default=str) + "\n")


def _origin_md(p: Problem) -> str:
    return f"""# Evolver report → origin `{p.sender_agent}`

**Problem id:** `{p.problem_id}`
**Correlation:** `{p.correlation_id}`
**Workflow phase:** `{workflow_phase(p.status)}`
**Sender role:** `{p.sender_role or p.sender_agent}`
**Kind / severity:** `{p.kind}` / {p.severity}
**Claimed by:** `{p.claimed_by or "-"}`
**Source surface:** {p.source_surface or "(none)"}

## Your roadblock

**Title:** {p.title}

{p.detail}

## Evolutionary synthesis (WATCH — not STATE NEXT)

- **Structural score:** {p.best_score}
- **Blueprint:** {p.best_blueprint or "(pending)"}
- **Synthesis JSON:** {p.synthesis_json_path or "(none)"}

## What you should do next

1. Read this file on your next tick (origin agent: **{p.sender_agent}**).
2. Do **not** re-submit the same title while status is active.
3. Product work only under free Flywheel/Implement claim after Overseer judgment.

```
PROPERTY: solution mapped back to origin sender_agent without dual-NEXT
EVIDENCE LEVEL: L1 (evolver journal)
NOT PROVEN: blueprint is product-correct without battery/tests
```
"""


def _overseer_md(p: Problem) -> str:
    return f"""# Evolver → Overseer

**Problem id:** `{p.problem_id}`
**Origin sender:** `{p.sender_agent}` (role `{p.sender_role or p.sender_agent}`)
**Kind / severity:** `{p.kind}` / {p.severity}
**Phase:** `{workflow_phase(p.status)}`

## Roadblock

**{p.title}**

{p.detail}

## WATCH synthesis

Score: **{p.best_score}**

{p.best_blueprint or "(none)"}

## Overseer action (allowed)

- Accept as strategy hypothesis (still not STATE NEXT alone)
- Name singular product NEXT only via STATE discipline + free claim
- Escalate Stage-1 human residues if money/public existence
- Discard as non-pursuant

**Banned:** inventing unsolicited/mainnet; dual continuous; auto-claim.

Origin inbox: `{p.origin_report_path or "pending"}`
Engineering: `{p.engineering_report_path or "pending"}`
"""


def _engineering_md(p: Problem) -> str:
    return f"""# Engineering handoff from Evolver

**Problem id:** `{p.problem_id}`
**Requested by (origin):** `{p.sender_agent}` / `{p.sender_role or p.sender_agent}`
**Kind / severity:** `{p.kind}` / {p.severity}
**Correlation:** `{p.correlation_id}`

## Problem statement

**{p.title}**

{p.detail}

## Proposed recombinant approach (WATCH)

Score: {p.best_score}

{p.best_blueprint or "(none)"}

## Constraints for implementers

1. One product claim only (`flywheel-claim.md`).
2. One engine / one payer path (AGENTS.md invariants).
3. Battery green before PR; no invent of settlement success.
4. Map acceptance checks back to origin agent **{p.sender_agent}**.

## Traceability

| Link | Path |
|------|------|
| Origin report | `{p.origin_report_path or "-"}` |
| Overseer outbox | `{p.overseer_report_path or "-"}` |
| Synthesis JSON | `{p.synthesis_json_path or "-"}` |
| Journal id | `{p.problem_id}` |

```
PROPERTY: engineering handoff preserves sender identity and origin mapping
EVIDENCE LEVEL: L1 (paths on disk)
NOT PROVEN: implementers will adopt without Overseer NEXT
```
"""


def seed_progress_blockers(journal: ProblemJournal) -> list[Problem]:
    seeds = [
        ("conductor", "conductor", "stall",
         "Green PR merge lag risks stall clock",
         "Conductor must merge any green non-draft within <=6m (ORG_LOOPS v5).",
         2, "docs/program/ORG_LOOPS.md"),
        ("overseer", "overseer", "strategy",
         "Stage-1 public existence still human-gated",
         "PyPI trusted publisher, public TLS, mainnet pay-to, registry remain human residues.",
         3, "docs/program/fable/REFOUNDING.md"),
        ("flywheel", "flywheel", "block",
         "Unsolicited demand unproven — existence falsifier window",
         "Settlements are self-dogfood only. Unsolicited=0 is the honest gate. Measure via veritas-ops existence.",
         2, "veritas.existence"),
        ("steward", "steward", "concern",
         "Free-on-merge claim debt after product land",
         "WORKFLOW_HYGIENE section 8: product merge must free claim.",
         2, "docs/program/WORKFLOW_HYGIENE.md"),
        ("money_loop", "track_money_loop", "money_egress",
         "Funded dogfood n=3 blocked by faucet captcha / zero USDC",
         "Dogfood wallets may show 0 USDC; Circle faucet needs headed captcha. Probe first.",
         3, "scripts/dogfood_agent_commerce.py"),
    ]
    out: list[Problem] = []
    for agent, role, kind, title, detail, sev, surface in seeds:
        out.append(journal.submit(
            agent, title, detail, kind=kind, severity=sev,
            sender_role=role, source_surface=surface,
        ))
    return out
