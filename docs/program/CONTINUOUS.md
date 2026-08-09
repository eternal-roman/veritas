# Continuous control plane

**Governing stack:** [`GOVERNING.md`](GOVERNING.md) → [`GUARDIAN.md`](GUARDIAN.md)
→ **Overseer** → Conductor / Flywheel.  
**Product org / sequencing / timing:** [`PRODUCT_ORG.md`](PRODUCT_ORG.md).  
**Autonomous (no human gates):** [`AUTONOMOUS.md`](AUTONOMOUS.md).

Primary objective: **agent-to-agent autonomous commerce** substrate with
scalable momentum (L0 multi-billion *direction* — never claim proven).

## Active cadence (v3 — cooperative scale + anti-thrash)

**Full layer map:** [`ORG_LOOPS.md`](ORG_LOOPS.md) (7 watchers, Researcher protocol).

| Loop | Interval | Job |
|------|----------|-----|
| **Conductor** | **8m** | Merge green product PRs; restart only if unblocked singular NEXT |
| **Overseer** | **10m** | Quality + vision + strategy; Scout if vision≤1; enforce hygiene |
| **Researcher** | **12m** | **Autonomous:** claim block board · research · solve/escalate · inbox report |
| **Pruner** | **12m** | Aggressive clean/prune; battery + E2E; **ship_ok veto** (G13) |
| **Scout (Idea)** | **15m** | Pattern fuel; may seed blocks for Researcher |
| **Steward** | **20m** | Card cohesion **in-place** (no restock PR under idle-true) |
| **Flywheel** | **30m** | Backup builder only when claim/unblocked; else idle_true noop |
| **Git Agent** | on demand / ~6–12h | Branch archaeology, salvage, local prune |
| **Ecosystem tracks** | offline mesh | T4 — prefer Mesh Runner over 7 LLM track timers |
| **Mesh Runner** | every 5 cycles / demand | `python -m veritas.ecosystem_cycle --cycles 5` |
| **Unblock Agent** | on demand / Researcher | `python -m veritas.unblock_probe` |
| **Implement×n** | on demand | `/workflow agent-commerce-implement {"n":3}` — scale workers |

**Shared truth:** `STATE.md` · `overseer/CURRENT.md` · `conductor/CONFERRAL.md` ·
`conductor/TRAJECTORY.md` · `steward/CURRENT.md` · `ecosystem/BUS.md` ·
`researcher/inbox/*` · block board (`.veritas/block_board.sqlite3`)  
**Claim:** `flywheel-claim.md` (one product builder)  
**Plane money / identity / pay:** `python -m veritas.agent_economy` — **not** x402  
**Workflow hygiene (binding):** [`WORKFLOW_HYGIENE.md`](WORKFLOW_HYGIENE.md)  
**Org loops (binding):** [`ORG_LOOPS.md`](ORG_LOOPS.md)

Orchestrators:

```
.agent-commerce-{pulse,continuous,conductor,flywheel,overseer,steward}.rhai
```

(Scout is scheduler + tick prompt; optional future `agent-commerce-scout.rhai`.)

---

## Progress tree (autonomous v3)

```
event: idle | CI green | merge | LEARN | block post
        │
   ┌────┴────┬──────────────┐
   ▼         ▼              ▼
Overseer  Researcher     Pruner
 (10m)      (12m)         (12m)
   │    claim/solve/inbox    │
   └─────────┬───────────────┘
             ▼
        Conductor (8m)
        ├── green product PR → squash-merge → LEARN
        ├── CI pending → poll once
        └── unblocked singular NEXT → Implement×n OR Flywheel (30m)
                └── battery → ship_ok → PR → auto-merge

   Steward (20m) ── in-place cards; idle-true → no restock PR
   Scout (15m) ── IDEA_BUS + optional block seeds
```

### Latency targets

| Path | Target |
|------|--------|
| Green PR → merged | ≤ **8m** |
| Block → Researcher claim | ≤ **12m** |
| Merge → coherent cards | ≤ **20m** |
| Idle → true noop (no PR) | immediate |
| Thin vision → idea harvest | ≤ **15m** |

### Design rules

1. **One product NEXT** — dual bets forbidden (G10 + claim file).  
2. **Scale support + implementer workers in parallel; never dual product NEXT.**  
   Pruner (G13) blocks useless/non-functional/bloated ships.
3. **I ≥ ~2× p95** write roles; **I ≥ ~5×** pure review roles.  
4. **Docs-only dirty PRs** do not freeze product.  
5. **No `await_user`** on commerce workflows.  
6. **noop_*** when facts unchanged.  
7. **Idle truly** — if claim free + no product PR + Overseer HOLD → support
   agents **noop**; no new tip-restock docs PRs (see `WORKFLOW_HYGIENE.md` §1).  
8. **One hygiene PR max per tip epoch** — not conductor + steward dual (§2).  
9. **Unblock Agent** is the only active track while money is bottleneck and
   RPC/wallet unset (§3).  
10. **Product NEXT only when unblocked** (0.1/G9) or Overseer names explicit
    non-money singular bet — not more mesh without buyer path (§4).  
11. **Never dual continuous/forever workflows** — Access Denied budget race (§5).

---

## Scaled entrypoints

```text
/workflow agent-commerce-pulse {"prefer_bet": "M7"}
/workflow agent-commerce-implement {"n": 3, "prefer_bet": "M7"}
/workflow agent-commerce-pruner
/workflow agent-commerce-continuous {"max_cycles": 5, "forever": true, "prefer_bet": "M7"}
/workflow agent-commerce-optimizer
/workflow agent-commerce-flywheel {"max_cycles": 2, "prefer_bet": "M7", "auto_merge": true}
/workflow agent-commerce-overseer
/workflow agent-commerce-steward
/workflow agent-commerce-conductor {"continuous": true, "max_cycles": 3}
```

**Continuous rule:** run **at most one** continuous/forever workflow at a time.
If one dies with `Access is denied` on budget reservation, fix host path before
resume; do **not** start a second continuous in parallel.

---

## Active schedules (v3 targets — re-arm host to match)

| Name | Prior id (may lag) | Interval |
|------|--------------------|----------|
| Conductor | `019fe25403f2` | **8m** |
| Overseer | `019fdfde0212` | **10m** |
| **Researcher** | *(new)* | **12m** |
| **Pruner** | `019fe29d4d61` | **12m** |
| Scout | `019fe0026e7d` | **15m** |
| Steward | `019fdff1fbe4` | **20m** |
| Flywheel | `019fdfd6c9bf` | **30m** |

### Role briefs

| Role | Charter | Tick |
|------|---------|------|
| Overseer | [`OVERSEER.md`](OVERSEER.md) | [`OVERSEER_TICK_PROMPT.md`](OVERSEER_TICK_PROMPT.md) |
| **Researcher** | [`RESEARCHER.md`](RESEARCHER.md) | [`RESEARCHER_TICK_PROMPT.md`](RESEARCHER_TICK_PROMPT.md) |
| **Pruner** | [`PRUNER.md`](PRUNER.md) | [`PRUNER_TICK_PROMPT.md`](PRUNER_TICK_PROMPT.md) |
| Conductor | [`CONDUCTOR.md`](CONDUCTOR.md) | [`CONDUCTOR_TICK_PROMPT.md`](CONDUCTOR_TICK_PROMPT.md) |
| Flywheel | [`INNOVATION_LOOP.md`](INNOVATION_LOOP.md) | [`FLYWHEEL_TICK_PROMPT.md`](FLYWHEEL_TICK_PROMPT.md) |
| Implement×n | [`IMPLEMENTERS.md`](IMPLEMENTERS.md) | workflow only |
| Steward | [`STEWARD.md`](STEWARD.md) | [`STEWARD_TICK_PROMPT.md`](STEWARD_TICK_PROMPT.md) |
| Scout | Idea fuel | [`SCOUT_TICK_PROMPT.md`](SCOUT_TICK_PROMPT.md) |

---

## Era (product)

See [`PRODUCT_ORG.md`](PRODUCT_ORG.md). **HOLD** until Unblock/0.1 **or** Overseer
non-money singular. On-chain settlements **0** until proven. Plane economy is T4.

## Re-arm

```text
Ask Grok: "Re-arm Veritas control-plane schedulers to ORG_LOOPS v3 intervals"
```

Tasks expire ~7 days. Use **v3** intervals above. Add Researcher 12m tick with
`RESEARCHER_TICK_PROMPT.md`. At most one continuous/forever.
