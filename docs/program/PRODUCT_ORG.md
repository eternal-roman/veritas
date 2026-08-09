# Product organization — A2A commerce at scale

How Veritas **manages product**, sequences bets, times agents, and scales
without thrash. Subordinate to [`GOVERNING.md`](GOVERNING.md). Honesty bar:
[`GUARDIAN.md`](GUARDIAN.md).

**L0 direction (never claim proven):** substrate for a multi-billion-dollar
**agent-to-agent autonomous commerce** business with scalable momentum.

---

## 1. Value ladder (what “product” optimises)

Ship only work that moves this ladder (same order as Overseer strategy):

```
C  Money is real     ── settlement proof, G9, fail-closed pay
D  Product worth     ── notary / quality buyers can verify (N0+)
A  Buy alone         ── unattended buyer path (credits, policy, diligence)
B  Sell alone        ── unattended serve, retention, ops
E  Found alone       ── discovery AFTER pay is not a trap
F  Lifecycle         ── trust, metering, attestations compound
```

**Current era (post-O.8 @ `96b9013`):**

| Priority | Bet | Axis | Why now |
|----------|-----|------|---------|
| **1 NEXT** | **M7** credits via SIWx | A/B | Last Phase M; prepaid agents without per-request human |
| **2** | **N0** notary core | D | Product worth — without it, scale is plumbing |
| **3** | **G9 design / measure** | C | Instrumentation only until RPC; never fake settle |
| Parked | Bazaar / X1/X3/X6 | E | Discovery before real money is a trap |

One primary NEXT only. Outrank only for security/money-path severity (Overseer
writes why).

---

## 2. Org chart (who scales what)

```
                    ┌─────────────────────────┐
                    │  GOVERNING LOOPS         │
                    │  goals · scorecard · NEXT│
                    └───────────┬─────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
         GUARDIAN          OVERSEER           STATE/TRAJECTORY
         fail-closed     quality·vision·      single objective
         code truth      strategy gate
              │                 │
              │         confer if vision≤1
              │                 ▼
              │              SCOUT (Idea)
              │              pattern fuel
              ▼                 │
         ┌────────────────────────────────┐
         │  CONDUCTOR  (orchestration)    │
         │  merge green · claim · restart │
         └───────────────┬────────────────┘
                         ▼
         ┌────────────────────────────────┐
         │  IMPLEMENT (N workers)  or     │
         │  FLYWHEEL (single builder)     │
         │  → PRUNER (ship veto) → merge  │
         └────────────────────────────────┘
                         │
              STEWARD · SCOUT (support)
```

| Tier | Agents | Scale rule |
|------|--------|------------|
| **T0 Governing** | Loops, STATE, Guardian | Documents; not parallelised |
| **T1 Gate** | Overseer | 1 instance; top-tier; may call Idea |
| **T1b Lean/QA** | **Pruner** | 1 instance; aggressive bloat denial + battery/E2E; **ship veto** |
| **T1c Self-improve** | **Optimizer** | Every **5 product cycles** forever; edits org/cadence/workflows (Overseer veto thrash) |
| **T2 Orchestrate** | Conductor | 1 instance; owns merge+restart |
| **T3 Build** | Flywheel **or** Implement×**n** | **1 product bet**; N workers share one claim |
| **T4 Support** | Steward, Scout, **Git Agent**, **Ecosystem tracks** | Parallel OK; tracks may ship plane substrate (`agent_money` / `agent_identity`) + research docs; **no dual product NEXT** |
| **T5 Burst** | continuous / pulse | Multi-cycle under budget cap |

**Scale agents by fan-out of *support, audit, track research, and implementer workers*, never by dual product NEXT.**  
See [`PRUNER.md`](PRUNER.md) · [`IMPLEMENTERS.md`](IMPLEMENTERS.md) · [`GIT_AGENT.md`](GIT_AGENT.md) · [`ECOSYSTEM_ADVANCE.md`](ECOSYSTEM_ADVANCE.md).

### Ecosystem track agents (T4)

Cooperative loops under Overseer strategy (not product claim):

| Track | Cadence | Charter tick |
|-------|---------|--------------|
| money_loop | 20m | `TRACK_MONEY_LOOP_TICK_PROMPT.md` |
| multiparty_trust | 25m | `TRACK_MULTIPARTY_TRUST_TICK_PROMPT.md` |
| product_worth | 25m | `TRACK_PRODUCT_WORTH_TICK_PROMPT.md` |
| discovery_density | 30m | `TRACK_DISCOVERY_DENSITY_TICK_PROMPT.md` |
| multi_tenant | 30m | `TRACK_MULTI_TENANT_TICK_PROMPT.md` |
| legal_identity | 25m | `TRACK_LEGAL_IDENTITY_TICK_PROMPT.md` |
| network_effects | 30m | `TRACK_NETWORK_EFFECTS_TICK_PROMPT.md` |
| **mesh_runner** | 5-cycle / demand | `TRACK_MESH_RUNNER_TICK_PROMPT.md` — offline kernel |
| **unblock** | on demand | `TRACK_UNBLOCK.md` — human ops for Phase 0.1 |

Bus: `ecosystem/BUS.md`. Conferral: `ecosystem/OVERSEER_CONFERRAL.md`.  
Kernel: `python -m veritas.ecosystem_cycle --cycles 5`.

---

## 3. Sequencing model (implementation order)

### Cycle atom (Flywheel)

```
Gate → Select → Claim → Build → Audit×rounds → Verify
  → PRUNER (ship_ok) → Ship+auto-merge → Learn
```

### Implement atom (scaled workers)

```
Plan → parallel Implementers[1..n] → Integrate → PRUNER → Ship
```

`/workflow agent-commerce-implement {"n": 3, "prefer_bet": "M7"}`

### Pulse atom (scaled org heartbeat) — preferred interactive entry

```
parallel:
  Overseer │ Steward │ Scout skim │ (optional Pruner skim)
serial:
  Conductor (merge green → else kick implement or flywheel)
```

Workflow: `/workflow agent-commerce-pulse`

### Era sequence (program)

```
M7 credits ──► N0 notary ──► C-measure/G9 design ──► E discovery
     │              │                │
     └── each era: one NEXT; full battery; auto-merge green; LEARN
```

Do **not** start N0 until M7 is on main or honestly parked with Overseer note.

---

## 4. Timing model (optimized for progress latency)

Measured work vs interval. Critical path = **merge lag + restart lag + build**.

| Role | Work p95 | Interval | Role in latency |
|------|----------|----------|-----------------|
| **Overseer** | ~2.5m | **8m** | Strategy gate; thrash catch |
| **Pruner** | ~3–8m | **10m** | Bloat denial + battery/E2E; pre-ship veto |
| **Conductor** | ~2m + build | **12m** | Merge + restart (primary lever) |
| **Steward** | ~6m | **15m** | Cohesion; lags Overseer slightly |
| **Flywheel** | 10–40m cycle | **20m** | Backup single-builder cycle |
| **Scout** | ~3m | **25m** | Idea fuel for vision |
| **Implement×n** | on demand | workflow | N workers for large bets (not a timer) |

### Progress-tree latency (target)

| Event | Target worst-case |
|-------|-------------------|
| Green product PR → merged | ≤ **12m** (Conductor) |
| Merge → cards coherent | ≤ **15m** (Steward) |
| Idle queue → build kick | ≤ **12m** (Conductor) |
| Vision thin → Idea harvest | ≤ **25m** (Scout) |
| Full flywheel ship | ≤ **1 cycle** (~20–45m wall) |

### Anti-thrash

1. **One claim** — `flywheel-claim.md` (G10).  
2. **Write ownership:** Overseer→`overseer/*`; Steward→cards/STATE hygiene; Conductor→`conductor/*`; Flywheel→product code+cycles; Scout→`scout/*`.  
3. **Docs PR dirty** (#21 class) never freezes product NEXT.  
4. **noop_stable / noop_coherent** when facts unchanged.

---

## 5. Flywheel / implementation model

| Principle | Practice |
|-----------|----------|
| One bet | STATE NEXT only |
| Functioning | Full battery before PR; auto-merge only on green CI |
| Necessary | Smallest axis-raising slice (M7: SIWx credits path, not full marketplace) |
| Pursuant | Overseer a2a/vision scores; reject strategically empty green |
| Autonomous | No human gates (`AUTONOMOUS.md`) |
| Scale | `max_cycles` 3–6; parallel audits; pulse for support fan-out |
| Learn | Cycle file + STATE NEXT advance only after merge on main |

### M7 acceptance sketch (for Select/Build)

- Credits issued/consumed via SIWx (or documented SIWx-shaped surface) with tests  
- Refunds-as-credits path documented + tested where code exists  
- No second payer path; Guardian money-path order intact  
- PROPERTY + NOT PROVEN (on-chain still 0)

---

## 6. How to run the org

```text
/workflow agent-commerce-pulse {"prefer_bet": "M7"}
/workflow agent-commerce-implement {"n": 3, "prefer_bet": "M7", "auto_merge": true}
/workflow agent-commerce-pruner
/workflow agent-commerce-continuous {"max_cycles": 4, "prefer_bet": "M7"}
/workflow agent-commerce-flywheel {"max_cycles": 2, "prefer_bet": "M7", "auto_merge": true}
```

Schedulers: see [`CONTINUOUS.md`](CONTINUOUS.md).

---

## 7. Success metrics (honest)

| Metric | Counts as progress |
|--------|-------------------|
| Axis A–F +1 with evidence | Yes |
| Critical gap closed (e.g. M7 shipped) | Yes |
| Green merges of product PRs | Yes |
| Tick frequency alone | **No** |
| Docs-only PR churn | **No** |
| Multibillion revenue | **Not claimed** until measured |

Landmass always: **on-chain settlements = 0** until a tx hash + (later) G9.
