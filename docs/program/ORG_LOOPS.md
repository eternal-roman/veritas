# Organization loops — layered scale without thrash

**Status:** binding plane law (**v5** — continuous ship clocks + stock honesty).  
**Pairs with:** [`WORKFLOW_HYGIENE.md`](WORKFLOW_HYGIENE.md) · [`PRODUCT_ORG.md`](PRODUCT_ORG.md) · [`CONTINUOUS.md`](CONTINUOUS.md) · [`MIND.md`](MIND.md).

Goal: **cooperative throughput without thrash** — parallel work on **owned
surfaces**, singular product NEXT, **minimum wall-clock** from “green PR” or
“block posted” or “claim taken” to the next correct action.

---

## 0. Inefficiencies observed → fixes

| Inefficiency | Symptom | Fix (version) |
|--------------|---------|----------------|
| **Restock thrash** | Dual tip-align PRs under free+HOLD | Idle-true; one hygiene/epoch (v3/v4) |
| **Stock blindness** | Cards said open [] while PRs open | `plane_stock` first; never invent empty if `gh` fails (v4) |
| **Merge lag** | Green PR sat unmerged | Conductor 6m merges any green non-draft (v4) |
| **Tool bloat on idle** | 50–120 tools for noop | Early-exit ≤15 tools (v4) |
| **Claim theater** | `building` for many ticks with **no product PR** | **Stall clock** free_or_ship; `plane_stock.stall` (v5) |
| **Post-merge claim lie** | Main claim still building after product land | **Free-on-merge** law (hygiene §8) (v5) |
| **Kick without ship surface** | restart=true only flips claim file | Kick = same-cycle product PR path (v5) |
| **Architect map as ship** | Branch with only seam docs | Map alone does **not** clear stall; need product PR (v5) |
| **Backup dual PR** | Flywheel backup races primary | `primary_shipped_same_bet` noop (v5) |
| **Dual continuous** | Access Denied budget race | Still banned (hygiene §5) |

---

## 1. The 7 watchers (v5 timers unchanged from v4)

| # | Watcher | Interval | Offset* | Default free+HOLD | Critical path? |
|---|---------|----------|---------|-------------------|----------------|
| 1 | **Conductor** | **6m** | +0 | merge green; **stall free_or_ship**; `restart=false` under HOLD | **yes** (merge + stall) |
| 2 | **Researcher** | **10m** | +2m | claim blocks; probe; inbox | **yes** (unblock) |
| 3 | **Overseer** | **12m** | +1m | HOLD / enforce hygiene + stall **LAZY** | strategy |
| 4 | **Pruner** | **15m** | +3m | SWEEP; HEAVY on product PR | lean gate |
| 5 | **Evolver** (ex-Scout) | **25m** | +5m | freshness stamp; evolve on confer | no |
| 6 | **Steward** | **30m** | +4m | in-place; **one** tip-epoch free-claim hygiene | claim truth |
| 7 | **Flywheel** | **45m** | +6m | idle_true **or** backup noop if primary shipped | only if claim |

\*Phase offsets stagger writers. When claim **building** with product PR: Pruner
HEAVY; Flywheel may use **20m** backup interval if host re-arms.

---

## 2. Stock protocol (every watcher, step 0)

```bash
git fetch origin
python -m veritas.plane_stock
```

| Field | Use |
|-------|-----|
| `tip.sha` | Card HEAD truth |
| `claim.status` / `bet_id` / `branch` / `pr` | Claim surface |
| `open_prs.product` / `docs` | merge targets |
| `open_prs.ok` | if **false** → `gh_failed` — never invent “open none” |
| `stall.claim_stale_building` | **free_or_ship** if true |
| `stall.stall_action` | `free_or_ship` \| `poll_ci_or_merge` \| null |
| `idle_true_candidate` | free + no product PR (and not stale building) |
| `stock_protocol` | expect `plane_stock_v2` |

**Early-exit noop (≤15 tool calls):** if `idle_true_candidate` **and** Overseer
HOLD **and** `open_prs.all` empty (`ok: true`) **and** no CI-green merge target
→ own CURRENT only if tip SHA changed; `noop_*`; stop.

**Stall path (not noop):** if `stall.stall_clock_active` → Conductor/Flywheel
must free_or_ship; do **not** early-exit as idle.

---

## 3. Handoff matrix (reduce inter-worker latency)

| Event | Producer | Consumer | Max lag |
|-------|----------|----------|---------|
| PR CI green | CI | **Conductor** merge | ≤ **6m** |
| Block posted | any agent | **Researcher** claim | ≤ **10m** |
| Claim → building | Conductor/Flywheel | **product PR open** | **same builder cycle** |
| `stall_clock_active` | plane_stock | Conductor free_or_ship | ≤ **2 Conductor ticks** |
| Product merge | Conductor | claim **free** on tip | **same merge PR** or ≤1 Steward hygiene |
| HOLD directive | Overseer | all | ≤ **12m** |
| Inbox report | Researcher | blocked agent | next consumer tick |

Prefer **block board + plane_stock** over rewriting peer CURRENT to “notify”.

---

## 4. Layer cake

```
L0  GOVERNING · GUARDIAN · MIND · STATE · plane_stock
L1  Overseer · Researcher · Pruner
L2  Conductor (merge + stall clock + restart)
L3  Steward · Flywheel / Implement×n
L4  Evolver · Mesh · Unblock probe · Architect (seams only)
L5  Pulse / Continuous (≤1 forever)
```

**Scale:** Researcher×n · Implement×n · mesh cycles.  
**Never:** dual product NEXT · dual continuous · dual restock PR · claim theater.

---

## 5. Cooperative unblock + cooperation contract

- Unblock: `veritas.block_board` · `veritas.researcher` · `unblock_probe` (MIND ladder).  
- Owned surfaces only (MIND §4).  
- In-flight PR sacred — no force-push over peer PR.  
- Checkpoint fleets ≤8; write to disk before next wave.  
- Strategy judgment: `ecosystem/STRATEGY_EVAL_AND_PLAN.md` is L0 fuel; Overseer
  accepts/holds lines — does not alone set NEXT.

---

## 6. Continuous improvement

Every **5 product or plane code merges** (not restock docs): Optimizer/LEARN
measures: green→merge lag, restock PR count, `stall_clock_active` rate,
`plane_stock` ok rate, idle tool calls p95, claim-stale-building incidents.
Raise only with numbers; Overseer vetoes thrash.

---

## 7. Re-arm (host)

```text
Ask Grok: "Re-arm Veritas control-plane schedulers to ORG_LOOPS v5 (same intervals as v4; stall clocks in prompts)"
```

| Name | Interval |
|------|----------|
| Conductor | 6m |
| Researcher | 10m |
| Overseer | 12m |
| Pruner | 15m |
| Evolver | 25m |
| Steward | 30m |
| Flywheel | 45m (20m when claim building + product PR) |

At most **one** continuous/forever.

```
PROPERTY: v5 adds claim stall free_or_ship + free-on-merge; keeps v4 merge/unblock latency + stock honesty
EVIDENCE LEVEL: L1 (process + plane_stock_v2 tests)
NOT PROVEN: host re-arm without operator; zero stall incidents forever
```
