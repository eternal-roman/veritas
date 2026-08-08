# Continuous control plane

**Governing stack:** [`GOVERNING.md`](GOVERNING.md) → [`GUARDIAN.md`](GUARDIAN.md)
→ **Overseer** → Conductor / Flywheel.  
**Product org / sequencing / timing:** [`PRODUCT_ORG.md`](PRODUCT_ORG.md).  
**Autonomous (no human gates):** [`AUTONOMOUS.md`](AUTONOMOUS.md).

Primary objective: **agent-to-agent autonomous commerce** substrate with
scalable momentum (L0 multi-billion *direction* — never claim proven).

## Active cadence (v2 — progress + scale)

| Loop | Interval | Job |
|------|----------|-----|
| **Overseer** | **8m** | Quality + vision + strategy gate; Scout confer if vision≤1 |
| **Pruner** | **10m** | Aggressive clean/prune; battery + E2E; **ship_ok veto** (G13) |
| **Conductor** | **12m** | Merge green product PRs; restart single NEXT bet |
| **Steward** | **15m** | Card/STATE cohesion (lags Overseer to cut thrash) |
| **Flywheel** | **20m** | Full build cycle backup; Pruner gate; auto-merge on green |
| **Scout (Idea)** | **25m** | Pattern fuel for Overseer; answers `scout_question` |
| **Git Agent** | on demand / ~6–12h | Branch archaeology, salvage, local prune; Overseer conferral on remotes |
| **Ecosystem tracks** | 20–30m each | T4 cooperative research: money_loop, multiparty_trust, product_worth, discovery_density, multi_tenant, legal_identity, network_effects — see `ECOSYSTEM_ADVANCE.md` |
| **Implement×n** | on demand | `/workflow agent-commerce-implement {"n":3}` — scale workers |

**Shared truth:** `STATE.md` · `overseer/CURRENT.md` · `conductor/CONFERRAL.md` ·
`conductor/TRAJECTORY.md` · `steward/CURRENT.md` · `ecosystem/BUS.md`  
**Claim:** `flywheel-claim.md` (one product builder)  
**Plane money / visa:** local VAAT + plane visas (`python -m veritas.plane_bootstrap`) — **not** x402 settle

Orchestrators:

```
.agent-commerce-{pulse,continuous,conductor,flywheel,overseer,steward}.rhai
```

(Scout is scheduler + tick prompt; optional future `agent-commerce-scout.rhai`.)

---

## Progress tree (autonomous)

```
event: idle | CI green | merge | LEARN
        │
        ▼
   Overseer (8m) ── quality / vision / strategy
        │                 │
        │                 └── vision≤1 → Scout (25m) Idea fuel
        ▼
   Steward (15m) ── cards ≡ git/gh (parallel OK)
        ▼
   Conductor (12m)
        ├── green product PR → squash-merge → LEARN → advance NEXT
        ├── CI pending → poll once → next tick
        └── queue clear → kick one bet (STATE NEXT / M7)
                ▼
        Implement×n  OR  Flywheel (20m)
                │
                └── battery → PRUNER ship_ok → PR → auto-merge → LEARN

   Pruner (10m) ── continuous deny bloat on open PR / claim (may comment; no dual NEXT)
```

### Latency targets

| Path | Target |
|------|--------|
| Green PR → merged | ≤ 12m |
| Merge → coherent cards | ≤ 15m |
| Idle → build start | ≤ 12m |
| Thin vision → idea harvest | ≤ 25m |

### Design rules

1. **One product NEXT** — dual bets forbidden (G10 + claim file).  
2. **Scale support + implementer workers in parallel; never dual product NEXT.**  
   Pruner (G13) blocks useless/non-functional/bloated ships.
3. **I ≥ ~2× p95** write roles; **I ≥ ~5×** pure review roles.  
4. **Docs-only dirty PRs** do not freeze product.  
5. **No `await_user`** on commerce workflows.  
6. **noop_*** when facts unchanged.

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

---

## Active schedules

| Name | Id | Interval |
|------|-----|----------|
| Overseer | `019fdfde0212` | **8m** |
| **Pruner** | `019fe29d4d61` | **10m** |
| Conductor | `019fe25403f2` | **12m** |
| Steward | `019fdff1fbe4` | **15m** |
| Flywheel | `019fdfd6c9bf` | **20m** |
| Scout | `019fe0026e7d` | **25m** |

### Role briefs

| Role | Charter | Tick |
|------|---------|------|
| Overseer | [`OVERSEER.md`](OVERSEER.md) | [`OVERSEER_TICK_PROMPT.md`](OVERSEER_TICK_PROMPT.md) |
| **Pruner** | [`PRUNER.md`](PRUNER.md) | [`PRUNER_TICK_PROMPT.md`](PRUNER_TICK_PROMPT.md) |
| Conductor | [`CONDUCTOR.md`](CONDUCTOR.md) | [`CONDUCTOR_TICK_PROMPT.md`](CONDUCTOR_TICK_PROMPT.md) |
| Flywheel | [`INNOVATION_LOOP.md`](INNOVATION_LOOP.md) | [`FLYWHEEL_TICK_PROMPT.md`](FLYWHEEL_TICK_PROMPT.md) |
| Implement×n | [`IMPLEMENTERS.md`](IMPLEMENTERS.md) | workflow only |
| Steward | [`STEWARD.md`](STEWARD.md) | [`STEWARD_TICK_PROMPT.md`](STEWARD_TICK_PROMPT.md) |
| Scout | Idea fuel | [`SCOUT_TICK_PROMPT.md`](SCOUT_TICK_PROMPT.md) |

---

## Era (product)

See [`PRODUCT_ORG.md`](PRODUCT_ORG.md). **NOW: M7** → N0 → C-measure/G9 design.
On-chain settlements remain **0** until proven.

## Re-arm

```text
Ask Grok: "Re-arm Veritas control-plane schedulers"
```

Tasks expire ~7 days. Use intervals in the Active schedules table.
