# Organization loops — layered scale without thrash

**Status:** binding plane law (**v4** — latency + stock honesty).  
**Pairs with:** [`WORKFLOW_HYGIENE.md`](WORKFLOW_HYGIENE.md) · [`PRODUCT_ORG.md`](PRODUCT_ORG.md) · [`CONTINUOUS.md`](CONTINUOUS.md).

Goal: **cooperative throughput without thrash** — parallel work on **owned
surfaces**, singular product NEXT, **minimum wall-clock** from “green PR” or
“block posted” to the next correct action.

---

## 0. Inefficiencies observed (session evidence) → fixes

| Inefficiency | Symptom | v4 fix |
|--------------|---------|--------|
| **Restock thrash** | #100–#104, #109 tip-align under free+HOLD | Idle-true hard; Steward/Architect **no PR** under free+HOLD |
| **Stock blindness** | Watchers reported `open PRs []` while #106/#110 open | **Stock protocol** — `python -m veritas.plane_stock` first; never invent empty list if `gh` fails |
| **Merge lag** | Green plane PR sat until human/session merged | Conductor merges **any** green non-draft PR (product **or** docs/plane), one per tick |
| **Timer drift** | Host still on old 8m/12m/… while law said v3 | Re-arm table below; mark prior ids **stale** |
| **Tool bloat on idle** | 50–120 tool calls for noop_idle | **Early-exit noop** after stock if idle_true_candidate |
| **Card write races** | Many CURRENT rewrites per hour | Only **owner role** writes its CURRENT; others read `plane_stock` + tip SHA |
| **Worker latency** | Blocked agent waits for next long tick | Researcher **10m**; inbox path; Conductor **6m** for merge |
| **Dual continuous** | Access Denied budget race | Still banned (hygiene §5) |

---

## 1. The 7 watchers (v4)

| # | Watcher | Interval | Offset* | Default free+HOLD | Critical path? |
|---|---------|----------|---------|-------------------|----------------|
| 1 | **Conductor** | **6m** | +0 | merge green PRs; `restart=false`; **no restock PR** | **yes** (merge) |
| 2 | **Researcher** | **10m** | +2m | claim blocks; probe; inbox | **yes** (unblock) |
| 3 | **Overseer** | **12m** | +1m | HOLD / `noop_stable`; enforce hygiene | strategy |
| 4 | **Pruner** | **15m** | +3m | LIGHT noop unless open product PR | ship only |
| 5 | **Scout** | **25m** | +5m | freshness stamp only | no |
| 6 | **Steward** | **30m** | +4m | **noop_coherent** in-place only | no |
| 7 | **Flywheel** | **45m** | +6m | **idle_true noop** | only if claim |

\*Offset = phase delay after Conductor epoch so writers do not collide on the same
minute (host scheduler: stagger `fire_immediately` / next-fire times).

**Why**

- Merge and unblock are the only latency that converts to progress under HOLD.  
- Strategy/cohesion/build backups **slow down** when idle so they stop eating budget.  
- When claim **building** or product PR open: Pruner may drop to **10m** HEAVY; Flywheel **20m**.

---

## 2. Stock protocol (every watcher, step 0)

```bash
git fetch origin
python -m veritas.plane_stock
```

Use the JSON fields:

| Field | Use |
|-------|-----|
| `tip.sha` | Card HEAD truth |
| `claim.status` | free / building |
| `open_prs.product` / `open_prs.docs` | merge targets |
| `open_prs.ok` | if **false**, say `gh_failed` — **do not** claim “open PRs none” |
| `idle_true_candidate` | free + no product PR |
| `env.VERITAS_RPC_URL` | Unblock gate |

**Early-exit noop (≤15 tool calls):** if `idle_true_candidate` **and** Overseer
HOLD **and** `open_prs.all` empty (with `ok: true`) **and** no CI-green PR to
merge → write own CURRENT only if tip SHA changed; final `noop_*`; stop.

---

## 3. Handoff matrix (reduce inter-worker latency)

| Event | Producer | Consumer | Max lag |
|-------|----------|----------|---------|
| PR CI green | CI | **Conductor** merge | ≤ **6m** |
| Block posted | any agent | **Researcher** claim | ≤ **10m** |
| Inbox report | Researcher | blocked agent | next consumer tick |
| HOLD directive | Overseer | all | ≤ **12m** |
| Product claim free→building | Conductor/Flywheel | Pruner HEAVY | ≤ **10m** once building |

Prefer **block board + plane_stock** over rewriting peer CURRENT to “notify”.

---

## 4. Layer cake

```
L0  GOVERNING · GUARDIAN · STATE · plane_stock
L1  Overseer · Researcher · Pruner
L2  Conductor (merge + restart)
L3  Steward · Flywheel / Implement×n
L4  Scout · Mesh · Unblock probe
L5  Pulse / Continuous (≤1 forever)
```

**Scale:** Researcher×n · Implement×n · mesh cycles.  
**Never:** dual product NEXT · dual continuous · dual restock PR.

---

## 5. Cooperative unblock

Unchanged protocol; interval **10m**. Code: `veritas.block_board` ·
`veritas.researcher` · `python -m veritas.unblock_probe`.

---

## 6. Continuous improvement

Every **5 product or plane code merges** (not restock docs): Optimizer or LEARN
measures: green→merge lag, restock PR count, `plane_stock` `ok` rate, idle tool
calls p95. Raise only with numbers; Overseer vetoes thrash.

---

## 7. Re-arm (host)

```text
Ask Grok: "Re-arm Veritas control-plane schedulers to ORG_LOOPS v4"
```

| Name | Interval |
|------|----------|
| Conductor | 6m |
| Researcher | 10m (create if missing) |
| Overseer | 12m |
| Pruner | 15m |
| Scout | 25m |
| Steward | 30m |
| Flywheel | 45m |

At most **one** continuous/forever.

```
PROPERTY: v4 cuts merge/unblock lag and idle thrash via stock protocol + slower support timers
EVIDENCE LEVEL: L1 (process + plane_stock tests)
NOT PROVEN: host re-arm without operator; exponential wall-clock gains
```
