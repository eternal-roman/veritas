# Continuous control plane

**Governing stack:** [`GOVERNING.md`](GOVERNING.md) → [`GUARDIAN.md`](GUARDIAN.md)
→ **Overseer** → Conductor / Flywheel.  
**Product org / sequencing / timing:** [`PRODUCT_ORG.md`](PRODUCT_ORG.md).  
**Autonomous (no human gates):** [`AUTONOMOUS.md`](AUTONOMOUS.md).

Primary objective: **agent-to-agent autonomous commerce** substrate with
scalable momentum (L0 multi-billion *direction* — never claim proven).

## Active cadence (v5 — continuous ship clocks)

**Full layer map:** [`ORG_LOOPS.md`](ORG_LOOPS.md) (7 watchers, stock protocol, stall clocks).

| Loop | Interval | Job |
|------|----------|-----|
| **Conductor** | **6m** | Merge green PRs; **stall free_or_ship**; restart only if unblocked singular NEXT |
| **Researcher** | **10m** | Claim block board · solve/escalate · inbox (unsolicited) |
| **Overseer** | **12m** | Quality + strategy; hygiene + **LAZY on claim theater**; Scout if vision≤1 |
| **Pruner** | **15m** | Full-tree sweep; Overseer-agreed prune PR; HEAVY on product PR |
| **Scout (Idea)** | **25m** | Freshness stamp under HOLD; pattern fuel if confer |
| **Steward** | **30m** | In-place; **one** tip-epoch free-claim hygiene when needed |
| **Flywheel** | **45m** | Builder when claim/unblocked; backup `primary_shipped_same_bet` noop; else idle_true |
| **Git Agent** | on demand / ~6–12h | Branch archaeology, salvage, local prune |
| **Ecosystem tracks** | offline mesh | Prefer Mesh Runner over LLM track timers |
| **Mesh Runner** | every 5 cycles / demand | `python -m veritas.ecosystem_cycle --cycles 5` |
| **Unblock Agent** | on demand / Researcher | `python -m veritas.unblock_probe` |
| **Implement×n** | on demand | `/workflow agent-commerce-implement {"n":3}` |

**Stock first (all watchers):** `python -m veritas.plane_stock` — never invent empty open-PR list if `open_prs.ok` is false.

**Shared truth:** `STATE.md` · cards · `ecosystem/BUS.md` · block board · **plane_stock**  
**Claim:** `flywheel-claim.md`  
**Plane money:** `python -m veritas.agent_economy` — **not** x402  
**Law:** [`WORKFLOW_HYGIENE.md`](WORKFLOW_HYGIENE.md) · [`ORG_LOOPS.md`](ORG_LOOPS.md)

Orchestrators:

```
.agent-commerce-{pulse,continuous,conductor,flywheel,overseer,steward}.rhai
```

(Scout is scheduler + tick prompt; optional future `agent-commerce-scout.rhai`.)

---

## Progress tree (autonomous v4)

```
event: idle | CI green | merge | LEARN | block post
        │
        ▼
   plane_stock (shared JSON — all watchers)
        │
   ┌────┼────────────┬──────────────┐
   ▼    ▼            ▼              ▼
Overseer Researcher Pruner      Conductor (6m)
 (12m)    (10m)      (15m)      ├── green PR (any) → merge
   │   claim/inbox    LIGHT     ├── CI pending → poll once
   └────────┬──────────┘        └── HOLD → restart=false
            ▼
   Steward (30m) in-place · Scout (25m) stamp · Flywheel (45m) idle_true
```

### Latency targets

| Path | Target |
|------|--------|
| Green PR → merged | ≤ **6m** |
| Block → Researcher claim | ≤ **10m** |
| Claim building → product PR open | **same builder cycle** |
| `stall_clock_active` → free_or_ship | ≤ **2 Conductor ticks** |
| Product merge → claim free on tip | same PR or ≤1 Steward hygiene |
| Idle stock → noop exit | ≤ **15 tool calls** |
| Merge → coherent cards | ≤ **30m** |
| Thin vision → idea harvest | ≤ **25m** |

### Design rules

1. **One product NEXT** — dual bets forbidden (G10 + claim file).  
2. **Scale support + implementer workers in parallel; never dual product NEXT.**  
   Pruner (G13) blocks useless/non-functional/bloated ships.
3. **I ≥ ~2× p95** write roles; **I ≥ ~5×** pure review roles.  
4. **Docs-only dirty PRs** do not freeze product.  
5. **No `await_user`** on commerce workflows.  
6. **noop_*** when facts unchanged.  
7. **Idle truly** — if claim free + no product PR + Overseer HOLD → support
   agents **noop**; no new tip-restock docs PRs (`WORKFLOW_HYGIENE.md` §1).  
8. **One hygiene PR max per tip epoch** (§2).  
9. **Unblock** only when dated probe fails (MIND ladder); unset env ≠ block (§3).  
10. **Product NEXT** when unblocked money path **or** Overseer non-money singular (§4).  
11. **Never dual continuous** (§5).  
12. **Stock honesty** — `plane_stock` v2; `gh_failed` if `open_prs.ok` false.  
13. **Early-exit noop** under free+HOLD when no merge target.  
14. **Claim stall clock** — building without product PR → free_or_ship (§7).  
15. **Free claim on product merge** — no building lie on tip (§8).  
16. **One kick = one ship surface** — restart must open product PR path (§9).

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

## Active schedules (v4 targets — re-arm host to match)

| Name | Prior id (may be stale) | Interval |
|------|-------------------------|----------|
| Conductor | `019fe25403f2` | **6m** |
| **Researcher** | *(create)* | **10m** |
| Overseer | `019fdfde0212` | **12m** |
| **Pruner** | `019fe29d4d61` | **15m** |
| Scout | `019fe0026e7d` | **25m** |
| Steward | `019fdff1fbe4` | **30m** |
| Flywheel | `019fdfd6c9bf` | **45m** |

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

See [`PRODUCT_ORG.md`](PRODUCT_ORG.md). Post-**#122** Phase 0.1-R: routine
settle→reconcile on tip. Settlements **2 testnet** self-dogfood · mainnet **0** ·
unsolicited **0**. Product invent **HOLD** until Overseer names singular or Stage-1
human unblocks public existence. Plane economy is T4 (not x402).

Strategy (L0 judgment): [`ecosystem/STRATEGY_EVAL_AND_PLAN.md`](ecosystem/STRATEGY_EVAL_AND_PLAN.md)
posture F — existence-first + D0 wedge; do not invent settle.

## Re-arm

```text
Ask Grok: "Re-arm Veritas control-plane schedulers to ORG_LOOPS v5 (v4 intervals + stall clocks)"
```

Tasks expire ~7 days. Stock: `python -m veritas.plane_stock` (`plane_stock_v2`).
At most one continuous/forever.
