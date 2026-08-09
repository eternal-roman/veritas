# Organization loops — layered scale without thrash

**Status:** binding plane law (v3 org).  
**Pairs with:** [`WORKFLOW_HYGIENE.md`](WORKFLOW_HYGIENE.md) · [`PRODUCT_ORG.md`](PRODUCT_ORG.md) · [`CONTINUOUS.md`](CONTINUOUS.md).

Goal: **exponential cooperative throughput** — many agents work in parallel on
**different owned surfaces**, while product NEXT stays singular. Watchers do
not restock thrash; **Researchers** clear other agents’ blocks without being asked.

---

## 1. The 7 watchers (v3)

| # | Watcher | Layer | Interval | Write surface | Default when free+HOLD |
|---|---------|-------|----------|---------------|------------------------|
| 1 | **Conductor** | L2 Orchestrate | **8m** | `conductor/*`, merge | merge green product only; `restart=false` |
| 2 | **Overseer** | L1 Gate | **10m** | `overseer/*` | HOLD / `noop_stable`; mark Unblock |
| 3 | **Researcher** | L1.5 Unblock | **12m** | `researcher/*`, block board | claim open blocks; solve or escalate |
| 4 | **Pruner** | L1 Lean | **12m** | `pruner/*`, PR comments | LIGHT noop_idle |
| 5 | **Scout** | L4 Idea | **15m** | `scout/*` | freshness stamp; feed Researcher |
| 6 | **Steward** | L3 Cohesion | **20m** | cards in-place only | **noop_coherent** — no restock PR |
| 7 | **Flywheel** | L3 Build | **30m** | product code only if claim | **idle_true noop** |

**Why these times**

- **Conductor fastest (8m):** green-PR merge is the critical path.
- **Overseer 10m:** strategy slightly behind merge sense; cuts thrash on CURRENT.
- **Researcher 12m:** clears blocks so other watchers stay productive.
- **Pruner 12m:** pairs with ship path without racing Steward.
- **Scout 15m:** idea fuel for Researcher/Overseer without write storms.
- **Steward slowest write (20m):** cohesion lag is intentional anti-thrash.
- **Flywheel 30m:** backup builder only; primary build is Conductor kick / implement×n.

**Hard rules still bind:** one product claim; one hygiene PR/epoch; never dual continuous.

---

## 2. Layer cake (org stack)

```
L0  GOVERNING · GUARDIAN · STATE          (documents; not timed)
L1  Overseer · Pruner · Researcher        (gate · ship veto · unblock others)
L2  Conductor                             (merge + restart one NEXT)
L3  Steward · Flywheel / Implement×n      (cohesion · build)
L4  Scout · Mesh · Tracks · Unblock       (fuel · offline cycles · human ops)
L5  Pulse / Continuous (≤1 forever)       (burst orchestration)
```

**Scale law:** fan-out **L1 Researcher×n** and **L3 Implement×n** and **L4 tracks**.  
**Never** fan-out product NEXT or dual continuous.

---

## 3. Cooperative unblock protocol (autonomous researchers)

```
Any agent hits a wall
        │
        ▼
  block_board.post(self, title, detail, kind, severity)
        │
        ▼
  Researcher tick (every 12m, unsolicited)
        │
        ├── claim highest severity open block
        ├── research + local solve (probe, economy, docs-in-place)
        ├── resolve | escalate | wontfix
        └── write researcher/inbox/{blocked_agent}-{id}.md
        │
        ▼
  Blocked agent next tick: read inbox → act or stay HOLD
```

Code:

| Module | Role |
|--------|------|
| `veritas.block_board` | Post / claim / resolve / inbox |
| `veritas.researcher` | One autonomous tick |
| `python -m veritas.block_board` | Seed known blocks |
| `python -m veritas.researcher` | Run Researcher |

**Researchers may open product PRs only** if claim is free **and** Overseer named
that bet **and** WORKFLOW_HYGIENE §4 allows. Default: local resolution + inbox.

---

## 4. Exponential scale patterns

| Pattern | Mechanism | Thrash guard |
|---------|-----------|--------------|
| **N implementers** | one claim, N workers | G10 claim file |
| **N researchers** | different `researcher_id`, claim locking | one claim per block |
| **Mesh cycles** | offline kernel rank+tax | no product dual NEXT |
| **Pulse** | parallel Overseer‖Steward‖Scout → serial Conductor | docs dirty ≠ freeze product |
| **Quality pay** | VAAT for effort | limited supply; not x402 |

Throughput ≈ **(watchers that noop correctly) × (researchers clearing blocks) × (implement×n when unblocked)**.  
Thrash destroys the multiplier — hygiene is load-bearing.

---

## 5. Continuous improvement loop

Every **5 product merges** or **5 mesh cycles**:

1. Optimizer tick (or LEARN file) measures merge lag, idle waste, open blocks age  
2. Adjust intervals only with numbers (never faster than ~2× p95 work)  
3. Overseer vetoes thrash-inducing cadence  
4. Researcher seeds new block kinds from repeated HOLD reasons  

---

## 6. Progress tree (v3)

```
events: CI green | merge | block post | LEARN | idle
              │
    ┌─────────┼──────────────┐
    ▼         ▼              ▼
Overseer   Researcher     Pruner
 (10m)       (12m)         (12m)
    │         │              │
    └────┬────┘              │
         ▼                   │
    Conductor (8m) ◄─────────┘ ship_ok
         │
    ├── green product PR → merge → LEARN
    ├── open blocks for NEXT? → wait Researcher / Unblock
    └── unblocked singular NEXT → Implement×n or Flywheel (30m)

Steward (20m) ── in-place cards only under idle-true
Scout (15m) ── IDEA_BUS + optional block seeds
```

### Latency targets (v3)

| Path | Target |
|------|--------|
| Green PR → merged | ≤ **8m** |
| Block posted → Researcher claim | ≤ **12m** |
| Researcher resolve → inbox | same tick |
| Merge → cards coherent | ≤ **20m** (Steward) |
| Thin vision → Scout fuel | ≤ **15m** |
| Idle → true noop (no PR) | immediate (hygiene) |

---

## 7. Re-arm watchers (host)

```text
Ask Grok: "Re-arm Veritas control-plane schedulers to ORG_LOOPS v3 intervals"
```

| Name | Interval |
|------|----------|
| Conductor | 8m |
| Overseer | 10m |
| Researcher | 12m |
| Pruner | 12m |
| Scout | 15m |
| Steward | 20m |
| Flywheel | 30m |

At most **one** continuous/forever workflow.

```
PROPERTY: 7 watchers layered for merge speed + autonomous unblock + anti-thrash
EVIDENCE LEVEL: L1 (process + block_board/researcher tests)
NOT PROVEN: exponential wall-clock gains without host scheduler re-arm
```
