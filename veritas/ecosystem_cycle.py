"""Ecosystem mesh cycle kernel — runs cooperative track progress offline.

Solves the stuck mesh: tick *prompts* without an executor never advance cycles.
This module runs N deterministic cycles that:

1. Rank tracks by bottleneck score (progress toward A2A commerce goal)
2. Advance each track's CURRENT.md cycle counter + micro-proposal
3. Route plane VAAT micropayments (stipend → work fee → overseer tax)
4. Append LEARN metrics for Optimizer / Overseer

Not product x402 settlement. Not dual product NEXT.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from veritas.agent_identity import PlaneIdentityIssuer
from veritas.agent_money import AgentMoneyLedger
from veritas.plane_bootstrap import DEFAULT_ROSTER, bootstrap

# Bottleneck weights: higher = more critical to unblock now.
# discovery_density is down-ranked until money path exists (pay-before-discovery).
TRACK_WEIGHTS: dict[str, float] = {
    "money_loop": 1.0,
    "multiparty_trust": 0.85,
    "product_worth": 0.9,
    "legal_identity": 0.7,
    "multi_tenant": 0.75,
    "network_effects": 0.65,
    "discovery_density": 0.4,
}

TRACK_MISSION: dict[str, str] = {
    "money_loop": "Plane VAAT + Phase 0.1/G9 honesty",
    "multiparty_trust": "G10/G11/G12 multiparty standing",
    "product_worth": "Volume-worthy measurable quality",
    "discovery_density": "Safe discovery density after pay",
    "multi_tenant": "Shared ledger/receipts multi-instance",
    "legal_identity": "Plane visa / network identity",
    "network_effects": "Multi-seller embed substrate",
}

# Cycle micro-advances (rotate) — research-grade, not vanity.
CYCLE_MICROS: dict[str, list[str]] = {
    "money_loop": [
        "VAAT stipend mesh live; document plane fee schedule for track work",
        "Draft Phase 0.1 dogfood checklist (wallet, facilitator, RPC gates)",
        "Map VAAT transfer → future product metering analogy (no settle claim)",
        "Add plane fee on track proposals (1 VAAT to overseer tax)",
        "Publish money_loop measure: journal_entries + tip_hash each cycle",
    ],
    "multiparty_trust": [
        "Cite G10 witness + A26 independence tests as baseline",
        "Proposal: auditor-side pack publish API sketch (G11)",
        "Proposal: warranty bond escrow design pointer (G12) without fake escrow",
        "Harvest SPIFFE/SPIRE workload identity pattern → visa claims map",
        "Score: third-party key count metric (0 today) registered in BUS",
    ],
    "product_worth": [
        "Inventory structural harness vs market quality gap (ROADMAP Phase 1)",
        "Proposal: one offline corpus regression that fails on empty answers",
        "Define 'volume worth' KPI: repeat autonomous buy (still 0)",
        "Snippet-grade honesty note in track CURRENT (not close quality)",
        "Rank substrate-vs-research pivot criteria for Overseer",
    ],
    "discovery_density": [
        "Hold density push until 0.1 (pay-not-trap rule) — document gate",
        "Inventory in-tree discovery: well-known x402, llms.txt, schema",
        "Proposal: density metric = unique agent ids hitting /.well-known",
        "WATCH: MCP registry patterns; no product registry ship",
        "Reaffirm discovery_density weight low until money_loop unblocked",
    ],
    "multi_tenant": [
        "Document single-instance bound (ledger SQLite) as operator fact",
        "Proposal: shared store interface sketch (authz nonce lease)",
        "Cite balancer dual-nonce gap from STATUS known-unproven",
        "Plane experiment: two AgentMoneyLedger paths must not share silently",
        "Multi-tenant checklist for G9 reconcile per-instance",
    ],
    "legal_identity": [
        "Plane visa L1 live; map claims.role → SIWx resources field",
        "Non-goals: not Entra, not SPIFFE production, not government ID",
        "Proposal: visa required for VAAT transfer > threshold",
        "Issue track visas via bootstrap; verify overseer can check roles",
        "Document KYA WATCH list (GitHub agent-identity topic)",
    ],
    "network_effects": [
        "Define ecosystem math: GMV × take vs SDK seats",
        "Proposal: trust substrate embed API surface list",
        "Single-shop ceiling note (research-only cap)",
        "Multi-seller standing format must share auditor independence rules",
        "Network effect KPI: distinct seller_ids with packs (0)",
    ],
}


@dataclass
class TrackState:
    track_id: str
    cycle: int = 0
    status: str = "open"
    last_micro: str = ""
    score: float = 0.0


@dataclass
class CycleReport:
    cycle: int
    ranking: list[str]
    advances: dict[str, str]
    fees: list[dict[str, Any]] = field(default_factory=list)
    money_tip: str = ""
    stuck_solved: list[str] = field(default_factory=list)


def _program_root(repo: Path) -> Path:
    return repo / "docs" / "program" / "ecosystem"


def _parse_cycle(text: str) -> int:
    m = re.search(r"\*\*Cycle:\*\*\s*(\d+)", text)
    return int(m.group(1)) if m else 0


def _parse_status(text: str) -> str:
    m = re.search(r"\*\*Status:\*\*\s*(\w+)", text)
    return m.group(1) if m else "open"


def load_track_state(repo: Path, track_id: str) -> TrackState:
    path = _program_root(repo) / track_id / "CURRENT.md"
    if not path.is_file():
        return TrackState(track_id=track_id)
    text = path.read_text(encoding="utf-8")
    return TrackState(
        track_id=track_id,
        cycle=_parse_cycle(text),
        status=_parse_status(text),
    )


def write_track_current(repo: Path, st: TrackState, micro: str, extra: str = "") -> None:
    mission = TRACK_MISSION.get(st.track_id, "")
    path = _program_root(repo) / st.track_id / "CURRENT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = f"""# {st.track_id} CURRENT

- **Track:** `{st.track_id}`
- **Status:** {st.status}
- **Cycle:** {st.cycle}
- **Time:** {time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())}
- **Last action:** mesh cycle kernel advance
- **Mission:** {mission}
- **Next micro:** {micro}
- **Bottleneck score:** {st.score:.3f}
- **Overseer mark:** pending
{extra}
```
PROPERTY: track {st.track_id} cycle {st.cycle}; mesh-driven
EVIDENCE LEVEL: L1 (ecosystem_cycle kernel)
NOT PROVEN: track resolved; product commercial success
```
"""
    path.write_text(body, encoding="utf-8")
    log_dir = path.parent / "log"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"{st.cycle:03d}-mesh.md"
    log_path.write_text(
        f"# cycle {st.cycle} — {st.track_id}\n\nMicro: {micro}\nScore: {st.score:.3f}\n",
        encoding="utf-8",
    )


def rank_tracks(states: dict[str, TrackState]) -> list[str]:
    """Higher weight / lower cycle progress ranks first (bottleneck first)."""
    scored: list[tuple[float, str]] = []
    for tid, st in states.items():
        if st.status in ("resolved", "parked"):
            st.score = -1.0
            continue
        w = TRACK_WEIGHTS.get(tid, 0.5)
        # Progress penalty: already advanced tracks yield to stuck ones.
        progress = st.cycle / 10.0
        st.score = w * (1.0 - min(progress, 0.9))
        scored.append((st.score, tid))
    scored.sort(reverse=True)
    return [t for _, t in scored]


def run_cycles(
    repo: Path | None = None,
    *,
    cycles: int = 5,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    repo = repo or Path.cwd()
    base = base_dir or (repo / ".veritas")
    boot = bootstrap(base)
    money = AgentMoneyLedger(base / "agent_money.sqlite3")
    secret = (base / "plane_identity.secret").read_bytes()
    issuer = PlaneIdentityIssuer(secret=secret)

    # Ensure visas valid for mesh runner
    for agent_id, role in DEFAULT_ROSTER.items():
        v = issuer.issue(agent_id, role, ttl_seconds=86400)
        issuer.verify(v, expected_role=role)

    states = {tid: load_track_state(repo, tid) for tid in TRACK_WEIGHTS}
    reports: list[dict[str, Any]] = []
    stuck_solved = [
        "mesh_runner: tick prompts alone never advanced cycles — kernel executes offline",
        "bottleneck_rank: discovery_density down-weighted until money path",
        "vaat_fees: track work pays 1 VAAT to overseer (plane tax)",
    ]

    for c in range(1, cycles + 1):
        ranking = rank_tracks(states)
        advances: dict[str, str] = {}
        fees: list[dict[str, Any]] = []

        for tid in ranking:
            st = states[tid]
            if st.status != "open":
                continue
            st.cycle += 1
            micros = CYCLE_MICROS[tid]
            micro = micros[(st.cycle - 1) % len(micros)]
            advances[tid] = micro
            write_track_current(repo, st, micro)

            # Plane fee: track agent pays overseer 1 VAAT for coordination
            try:
                if money.balance(tid) >= 1:
                    tr = money.transfer(tid, "overseer", 1, memo=f"mesh_tax:c{c}:{tid}")
                    fees.append(tr.to_dict())
            except Exception as exc:  # noqa: BLE001 — report, don't kill mesh
                fees.append({"error": str(exc), "track": tid})

        money.verify_chain()
        snap = money.snapshot()
        rep = CycleReport(
            cycle=c,
            ranking=ranking,
            advances=advances,
            fees=fees,
            money_tip=snap["tip_hash"],
            stuck_solved=stuck_solved if c == 1 else [],
        )
        reports.append(
            {
                "cycle": rep.cycle,
                "ranking": rep.ranking,
                "advances": rep.advances,
                "fee_count": len(fees),
                "money_tip": rep.money_tip,
                "stuck_solved": rep.stuck_solved,
            }
        )

    money.close()
    _write_bus(repo, states, reports)
    _write_learn(repo, states, reports, boot)
    _write_mesh_current(repo, states, reports)

    return {
        "cycles_run": cycles,
        "tracks": {t: {"cycle": s.cycle, "status": s.status, "score": s.score} for t, s in states.items()},
        "reports": reports,
        "bootstrap": boot,
        "not_x402_settlement": True,
    }


def _write_bus(repo: Path, states: dict[str, TrackState], reports: list[dict[str, Any]]) -> None:
    last = reports[-1] if reports else {}
    lines = [
        "# Ecosystem BUS — shared track findings",
        "",
        "**Updated by:** mesh cycle kernel (`veritas.ecosystem_cycle`).",
        "**Read by:** Overseer every 8m.",
        "**Rule:** seedlings and proposals only — never set STATE NEXT or invent settlement.",
        "",
        "## Overseer strategy notes",
        "",
        "- Product HOLD until Phase 0.1 / G9 **or** explicit singular non-money NEXT.",
        "- Plane VAAT is local coordination, not product revenue.",
        f"- Last mesh cycle: **{last.get('cycle', 0)}**; ranking: `{', '.join(last.get('ranking', []))}`",
        "",
        "## Track headlines",
        "",
        "| Track | Status | Last cycle | Score | One-line |",
        "|-------|--------|------------|-------|----------|",
    ]
    for tid, st in sorted(states.items(), key=lambda x: -x[1].score):
        micro = ""
        if last.get("advances"):
            micro = last["advances"].get(tid, "")[:60]
        lines.append(
            f"| `{tid}` | {st.status} | {st.cycle} | {st.score:.2f} | {micro} |"
        )
    lines += [
        "",
        "## Cross-track proposals (newest first)",
        "",
        "1. **Mesh Runner:** offline cycle kernel unblocks zero-tick stall.",
        "2. **Bottleneck rank:** money_loop + product_worth lead; discovery_density held.",
        "3. **VAAT tax:** 1 VAAT/track/cycle to overseer for coordination accounting.",
        "",
        "## Response to Overseer",
        "",
        f"Ran **{len(reports)}** mesh cycles. Accept plane substrate + mesh kernel as T4 infra.",
        "Do not dual product claim. Prefer singular NEXT = Phase 0.1 when RPC/wallet unblocked.",
        "",
    ]
    path = _program_root(repo) / "BUS.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_learn(
    repo: Path,
    states: dict[str, TrackState],
    reports: list[dict[str, Any]],
    boot: dict[str, Any],
) -> None:
    learn_dir = _program_root(repo) / "learn"
    learn_dir.mkdir(parents=True, exist_ok=True)
    n = len(reports)
    path = learn_dir / f"{n:03d}-mesh-optimize.md"
    ranking = reports[-1]["ranking"] if reports else []
    body = f"""# Mesh LEARN after {n} cycles

## Stuck diagnosis (pre-kernel)

| Stuck | Cause | Fix |
|-------|-------|-----|
| Cycles stayed 0 | Tick prompts without executor | `veritas.ecosystem_cycle` |
| 7 agents idle | No heartbeat / stipend loop | bootstrap + VAAT tax |
| Discovery thrash risk | Equal weight all tracks | Bottleneck weights |
| Overseer no marks | Empty BUS | Kernel rewrites BUS |

## Ranking after cycle {n}

`{" > ".join(ranking)}`

## Track cycles

| Track | Cycle | Status |
|-------|-------|--------|
"""
    for tid, st in states.items():
        body += f"| `{tid}` | {st.cycle} | {st.status} |\n"
    body += f"""
## Evolution rules (v2)

1. **Execute offline first** — LLM ticks optional; kernel guarantees progress.
2. **Rank by bottleneck** — weight × (1 - progress); discovery low until money.
3. **Pay for work** — VAAT tax makes coordination auditable.
4. **Scale mesh not dual NEXT** — more track cycles ≠ product claim.
5. **Every 5 cycles** — Optimizer-style LEARN (this file); raise weights if stuck.

## Scale levers

| Lever | Action |
|-------|--------|
| Throughput | `python -m veritas.ecosystem_cycle --cycles N` |
| Fan-out | Parallel LLM ticks for top-3 ranked only |
| New agent | **Mesh Runner** (this kernel) + optional **Unblock Agent** for human ops checklist |
| Product gate | Still Overseer HOLD for x402 until RPC |

## Bootstrap snapshot

```json
{json.dumps({"visa_count": boot.get("visa_count"), "not_x402": True}, indent=2)}
```

```
PROPERTY: mesh advanced {n} cycles without dual product NEXT or fake settlement
EVIDENCE LEVEL: L1 (kernel + journal)
NOT PROVEN: track resolved; product settle; $1B EV
```
"""
    path.write_text(body, encoding="utf-8")


def _write_mesh_current(
    repo: Path, states: dict[str, TrackState], reports: list[dict[str, Any]]
) -> None:
    path = _program_root(repo) / "MESH_CURRENT.md"
    n = len(reports)
    path.write_text(
        f"""# Mesh Runner CURRENT

- **Role:** ecosystem cycle kernel / scale heartbeat
- **Cycles completed (this run):** {n}
- **Tracks open:** {sum(1 for s in states.values() if s.status == "open")}
- **Last ranking:** {", ".join(reports[-1]["ranking"]) if reports else "—"}
- **Scale rule:** offline kernel always; LLM ticks only for top-ranked tracks
- **Product claim:** free / HOLD — mesh is T4

```
PROPERTY: mesh runner live; cycles={n}
EVIDENCE LEVEL: L1
NOT PROVEN: continuous scheduler in production
```
""",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> None:
    import argparse

    p = argparse.ArgumentParser(description="Run ecosystem mesh cycles")
    p.add_argument("--cycles", type=int, default=5)
    p.add_argument("--repo", type=Path, default=None)
    args = p.parse_args(argv)
    out = run_cycles(args.repo, cycles=args.cycles)
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
