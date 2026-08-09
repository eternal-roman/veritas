# Continuous control plane

**Governing stack:** [`GOVERNING.md`](GOVERNING.md) → [`GUARDIAN.md`](GUARDIAN.md)
→ **Overseer** → Conductor / Flywheel.  
**Product org / sequencing / timing:** [`PRODUCT_ORG.md`](PRODUCT_ORG.md).  
**Autonomous (no human gates):** [`AUTONOMOUS.md`](AUTONOMOUS.md).

Primary objective: **agent-to-agent autonomous commerce** substrate with
scalable momentum (L0 multi-billion *direction* — never claim proven).

## Active cadence (v4 — low latency + anti-thrash)

**Full layer map:** [`ORG_LOOPS.md`](ORG_LOOPS.md) (7 watchers, stock protocol, Researcher).

| Loop | Interval | Job |
|------|----------|-----|
| **Conductor** | **6m** | Merge **any** green non-draft PR; restart only if unblocked singular NEXT |
| **Researcher** | **10m** | Claim block board · solve/escalate · inbox (unsolicited) |
| **Overseer** | **12m** | Quality + strategy; enforce hygiene; Scout only if vision≤1 |
| **Pruner** | **15m** | Full-tree sweep every tick; ponytail-audit/debt; **Overseer-agreed** prune PR only; HEAVY on product PR |
| **Scout (Idea)** | **25m** | Freshness stamp under HOLD; pattern fuel if confer |
| **Steward** | **30m** | In-place cohesion only; **no restock PR** under idle-true |
| **Flywheel** | **45m** | Backup builder only when claim/unblocked; else idle_true noop |
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
   agents **noop**; no new tip-restock docs PRs (see `WORKFLOW_HYGIENE.md` §1).  
8. **One hygiene PR max per tip epoch** — not conductor + steward dual (§2).  
9. **Unblock Agent** is the only active track while money is bottleneck and
   RPC/wallet unset (§3).  
10. **Product NEXT only when unblocked** (0.1/G9) or Overseer names explicit
    non-money singular bet — not more mesh without buyer path (§4).  
11. **Never dual continuous/forever workflows** — Access Denied budget race (§5).  
12. **Stock honesty** — use `plane_stock`; if `gh` fails, report `gh_failed` (ORG_LOOPS §0).  
13. **Early-exit noop** under free+HOLD when no merge target (ORG_LOOPS §2).

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

See [`PRODUCT_ORG.md`](PRODUCT_ORG.md). **HOLD** until Unblock/0.1 **or** Overseer
non-money singular. On-chain settlements **0** until proven. Plane economy is T4.

## Re-arm

```text
Ask Grok: "Re-arm Veritas control-plane schedulers to ORG_LOOPS v4 intervals"
```

Tasks expire ~7 days. Use **v4** intervals + phase offsets in `ORG_LOOPS.md`.
Researcher: `RESEARCHER_TICK_PROMPT.md`. Stock: `python -m veritas.plane_stock`.
At most one continuous/forever.
