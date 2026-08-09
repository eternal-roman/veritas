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

**When:** mesh ranks **money_loop** high **and** a **dated probe from this
environment fails** (`python -m veritas.unblock_probe`). An unset env var or
an inherited sandbox note is a hypothesis, not a block (MIND §3/§5): egress,
facilitator reachability, and testnet funding all fell to probes on
2026-08-09 (`fable/settlement/`). Re-probe before declaring blocked.

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
   Phase **0.1 / G9** dogfood — all three proven agent-clearable on this
   machine (`fable/settlement/`), so this condition defaults to *satisfiable*
   until a dated probe says otherwise, **or**
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

### 6. Stock honesty + early-exit (latency without thrash)

Every support tick **starts** with:

```bash
git fetch origin
python -m veritas.plane_stock
```

| Rule | Detail |
|------|--------|
| Never invent empty open-PR list | If `open_prs.ok` is false → report `gh_failed`, retry once |
| Early-exit noop | free + no product PR + HOLD + no green merge target → ≤15 tools, `noop_*` |
| Merge green docs/plane | Conductor may merge green non-product PRs without counting as dual product NEXT |
| Tip epoch for restock | Starts on **product or plane-code** merge, not every docs restock |
| Stall fields | Read `stall.claim_stale_building` / `stall.stall_action` (`plane_stock` v2) |

### 7. Claim stall clock (no building theater)

**Observed failure (2026-08-09):** claim flipped `building` and flywheel was
kicked while **no product branch commits and no open product PR** existed for
multiple Conductor ticks. That is narrative, not progress.

| Signal (`plane_stock.stall`) | Meaning | Required action |
|------------------------------|---------|-----------------|
| `claim_stale_building` | status=building and **zero** open product PRs | **free_or_ship** this tick |
| `building_without_branch` | building and claim `branch` empty/pending | set real branch **or** free |
| `stall_action: poll_ci_or_merge` | building **with** product PR | poll CI / merge green; **no dual-kick** |

**Clock:**

1. Kick / claim building **must** open a product PR (or land ≥1 product-code
   commit on a named remote branch **and** open PR) **within the same builder
   cycle** that took the claim.
2. Conductor: if `stall_clock_active` for **>2 consecutive Conductor polls**
   (~12m+), **same tick** either (a) complete WIP → open product PR, or
   (b) **free claim with reason**. Do **not** leave building empty.
3. Overseer: third empty poll → verdict **LAZY** until free or PR exists.
4. Flywheel BACKUP: if primary already shipped the same `bet_id` →
   `noop` / `primary_shipped_same_bet` — **never** open a second PR.

**Not a stall:** building + open product PR (even CI red) — fix CI, do not free.

### 8. Free claim on product merge (no post-merge lie)

**Observed failure:** product PR merged; tip advanced; `flywheel-claim.md` on
main still said `building` until a Steward hygiene PR one tip-epoch later.

| Who | Duty |
|-----|------|
| **Merge payload** | Product merge PR **should** set claim `status: free`, clear `bet_id`/`branch`/`holder`, set `last_merged` to the new tip — **in the same PR** when practical |
| **Conductor** | If tip has product merge and claim still building **and** no product PR open → free claim in-place (or ensure #8 hygiene includes free) **before** invent restart |
| **Steward** | Tip-epoch hygiene **must** free a stale building claim (allowed under §2 once per product epoch) |
| **Flywheel post-merge** | Before exit LEARN, claim must be free |

Settlements / landmass counts still only change with **evidence**, never with
hygiene.

### 9. One continuous kick = one ship surface

When Conductor sets `restart=true` / kicks flywheel for a singular NEXT:

| Required | Forbidden |
|----------|-----------|
| One workflow instance | Dual continuous / dual flywheel forever |
| Claim building + real `branch:` + product PR path | Claim building with only Architect map / docs |
| Prefer implement code over card rewrites | Kick that only flips claim file |
| Auto_merge when green + ship_ok | Merge red Security/Tests |

---

## Agent-specific enforcement

| Agent | Idle true behavior |
|-------|-------------------|
| **Steward** | If rule 1 holds → `noop_coherent` (score cards only if rewriting in-place without PR). **No new restock PR** unless rule 2 slot empty **and** tip lag is material (missing product SHA entirely). |
| **Conductor** | If rule 1 holds → merge green product PRs only; **restart=false**; no tip-align PR; no invent NEXT. If `stall_clock_active` → free_or_ship same tick (§7). Free stale building after product merge (§8). |
| **Overseer** | If rule 1 holds → HOLD + `restart=false`; mark Unblock active (rule 3); refuse mesh-as-product. Escalate **LAZY** on claim theater (§7). |
| **Flywheel / Implement** | Claim building only with product path; open PR same cycle (§7/§9). Free claim in merge payload (§8). |
| **Flywheel backup** | `noop` if free + no product PR **or** `primary_shipped_same_bet`. |
| **Pruner** | LIGHT noop_idle if no product PR. |
| **Evolver** | Freshness stamp only under idle; evolve on confer; no blueprints-as-NEXT. |
| **Mesh Runner** | May run offline cycles without PR. |
| **Unblock** | Only active track under rule 3 for *product money*; plane Researcher may still clear blocks. |
| **Researcher** | Always allowed under free+HOLD: claim block board, local solve, inbox report. **No** tip-restock PRs. Product PR only if §4. |
---

## Self-check (every support tick)

```
[ ] ran plane_stock? (open_prs.ok true? stock_protocol plane_stock_v2?)
[ ] stall.claim_stale_building?
→ free_or_ship same tick (do not leave building empty)
[ ] claim free?
[ ] product PRs empty?
[ ] Overseer HOLD / restart=false?
→ if yes to free+empty product+HOLD: noop; do not open a restock docs PR
[ ] green PR open (docs or product)?
→ Conductor merge one; others do not open competing restock
[ ] product just merged, claim still building?
→ free claim (§8) in hygiene or in-place Conductor fix
[ ] hygiene PR already open this tip epoch?
→ if yes: do not open another
[ ] money bottleneck with dated failing probe?
→ Unblock / Researcher only (MIND ladder)
[ ] dual continuous?
→ kill one
```

```
PROPERTY: idle free+HOLD no restock thrash; claim stall free_or_ship; free-on-merge; stock honesty v2; single continuous
EVIDENCE LEVEL: L1 (process law + plane_stock tests)
NOT PROVEN: agents always obey without host re-arm to ORG_LOOPS v5
```
