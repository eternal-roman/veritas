# Workflow hygiene — idle, one restock, unblock-first

**Status:** binding plane law (post-#98 retrospect).  
**Why:** After ecosystem mesh landed, support agents burned cycles on dual
conductor/steward tip-align PRs while product money stayed blocked. That is
not progress.

Subordinate to [`GUARDIAN.md`](GUARDIAN.md) · [`GOVERNING.md`](GOVERNING.md) ·
[`OVERSEER.md`](OVERSEER.md). Wired into tick prompts and [`CONTINUOUS.md`](CONTINUOUS.md).

---

## Five hard rules

### 1. Idle truly

**If all of the following hold:**

- `flywheel-claim.md` **status: free**
- open **product** PRs: **none** (docs-only PRs do not count as product)
- Overseer verdict is **HOLD** / product `noop_stable` / `restart=false`

**Then support agents (Steward, Conductor restock path, Scout, Architect card
rewrites, Pruner LIGHT) MUST:**

| Allowed | Forbidden |
|---------|-----------|
| `noop_idle` / `noop_coherent` final reply | Opening a docs PR “to restock tip” |
| Rewrite **own** CURRENT in-place on a worktree **without** push/PR | Dual restock PRs (conductor + steward) |
| Append a single local log line optional | Spamming tip-align every 8–15m |
| Merge **already-open** green docs PRs (Conductor only, one at a time) | Creating new hygiene PR when tip already coherent enough |

**Exception:** a **single** post-product-merge hygiene PR is allowed once per
**tip epoch** (rule 2). Card lag of a few SHAs is **not** enough to open a PR
if claim is free and NEXT is hold.

### 2. One hygiene PR max per tip epoch

A **tip epoch** starts when `origin/main` advances by a **product** merge
(or an explicit Overseer-named hygiene batch). Until the next product merge:

- At most **one** open docs PR whose sole purpose is tip/claim/CURRENT restock.
- Prefer **Conductor OR Steward**, not both. Default owner: **Steward** for
  card restock; **Conductor** only for merge of product PRs + optional one
  post-merge LEARN note if Steward is silent.
- If a hygiene PR already exists (any author), **do not open another**.
- Close/supersede duplicates rather than stacking #100+#101+#103+#104.

### 3. Unblock Agent is the only active track while money is blocked

**When:** mesh ranks **money_loop** high **and** `VERITAS_RPC_URL` is unset
(or funded wallet missing).

**Then:**

| Active | Parked / quiet |
|--------|----------------|
| **Unblock Agent** — checklist + probes (`TRACK_UNBLOCK.md`, `ecosystem/unblock/CHECKLIST.md`) | Extra TRACK charter edits |
| Optional: `python -m veritas.unblock_probe` (in-place checklist update) | New mesh feature code without buyer path |
| Mesh kernel may run offline cycles (no PR required) | Dual continuous workflows |

Unblock updates checklist **in place** (commit only if a real status bit flips
from unknown→yes/no with evidence). Prefer no PR for “still unknown”.

### 4. Product NEXT only when unblocked

Product flywheel / implement may start **only if**:

1. **Money path unblocked:** RPC + facilitator + funded test wallet ready for
   Phase **0.1 / G9** dogfood, **or**
2. Overseer names an **explicit non-money singular bet** (e.g. retrieval eval
   harness) with claim free → building.

**Not product NEXT:** more VAAT features, more track charters, more mesh LEARN
docs without a buyer path, tip restocks.

Plane mesh (`agent_money`, `agent_identity`, `ecosystem_cycle`) stays **T4**:
run offline; do not claim as settlement or dual NEXT.

### 5. Stop dual continuous workflows

Do **not** run two `agent-commerce-continuous` (or forever) workflows in
parallel. Observed failure: `Access is denied` on agent-budget reservation
when dual runs race the same budget journal.

| Allowed | Forbidden |
|---------|-----------|
| One continuous OR pulse at a time | Dual continuous-1 + continuous-2 |
| Retry continuous only after budget path is writable | Resume both failed runs “to be safe” |
| Prefer single pulse for interactive | Stack forever workflows without operator ack |

---

## Agent-specific enforcement

| Agent | Idle true behavior |
|-------|-------------------|
| **Steward** | If rule 1 holds → `noop_coherent` (score cards only if rewriting in-place without PR). **No new restock PR** unless rule 2 slot empty **and** tip lag is material (missing product SHA entirely). |
| **Conductor** | If rule 1 holds → merge green product PRs only; **restart=false**; no tip-align PR; no invent NEXT. |
| **Overseer** | If rule 1 holds → HOLD + `restart=false`; mark Unblock active (rule 3); refuse mesh-as-product. |
| **Flywheel backup** | `noop` if free + no product PR. |
| **Pruner** | LIGHT noop_idle if no product PR. |
| **Scout** | Freshness stamp only; no seedlings-as-NEXT. |
| **Mesh Runner** | May run offline cycles without PR. |
| **Unblock** | Only active track under rule 3. |

---

## Self-check (every support tick)

```
[ ] claim free?
[ ] product PRs empty?
[ ] Overseer HOLD / restart=false?
→ if yes to all three: noop; do not open a docs PR
[ ] hygiene PR already open this tip epoch?
→ if yes: do not open another
[ ] RPC unset and money path is the bottleneck?
→ Unblock checklist/probe only; no new mesh product features
[ ] dual continuous running?
→ kill one; never start a second
```

```
PROPERTY: idle free+HOLD means no restock PR thrash; one hygiene PR max; Unblock when money blocked; product NEXT only if unblocked; single continuous
EVIDENCE LEVEL: L1 (process law)
NOT PROVEN: agents always obey without host enforcement
```
