# Implementers — scalable N workers under one bet

**Operating core:** [`MIND.md`](MIND.md) binds this role.
**Mindset** — optimizes: one shippable bet, tests-first, end to end. Refuses: parallel laundry lists; untested behaviour claims. Unblock bias: rung 3 — the smallest slice that reaches reality this cycle.

**Scale code execution without dual product NEXT.** N implementer agents fan out
on **work packages** of a single STATE NEXT bet, then integrate, pass **Pruner**,
and ship.

Charters: [`PRODUCT_ORG.md`](PRODUCT_ORG.md) · [`GOVERNING.md`](GOVERNING.md) ·
[`PRUNER.md`](PRUNER.md) · [`GUARDIAN.md`](GUARDIAN.md)

---

## Why N agents

| Wrong scale | Right scale |
|-------------|-------------|
| N parallel product NEXT / dual worktrees | N workers on **one** claim + one branch |
| N opinionated architects rewriting STATE | 1 planner shards packages; N builders; 1 integrator |
| Unbounded fan-out | **n** default 3, hard cap **6** (budget-aware) |

Common goal: **A2A autonomous commerce** substrate (L0 multi-billion direction).
Every package must be **functioning, necessary, pursuant** — Pruner enforces lean.

---

## Workflow

```
Plan (1) → packages[1..n] non-overlapping files
    → parallel Implementers[1..n]
    → Integrate (1) reconcile + battery
    → Pruner (1) ship_ok gate
    → Ship / auto-merge (Conductor rules)
```

Entrypoint:

```text
/workflow agent-commerce-implement {"n": 3, "prefer_bet": "M7"}
```

Args:

| Arg | Default | Meaning |
|-----|---------|---------|
| `n` | 3 | Worker count (1–6) |
| `prefer_bet` | from STATE / M7 | Single product bet |
| `auto_merge` | true | Merge when CI green after Pruner |
| `dry_run` | false | Plan only |

---

## Work package rules

1. **One bet_id** for all packages (e.g. M7).  
2. **Non-overlapping `files`** lists — planner must not assign same path twice.  
3. **Tests first** per package where possible.  
4. **No second payer/engine.**  
5. Workers **must not** edit outside their file list without integrator.  
6. Integrator owns conflicts, cross-file wiring, full battery.  
7. Pruner may delete worker output that is bloat.  
8. **Ship surface:** integrator opens **one product PR** before claim may stay
   building (`WORKFLOW_HYGIENE` §7). Map-only / docs-only packages do not satisfy stall.  
9. **Free-on-merge:** claim cleared to free in merge payload when practical (§8).

---

## Worker contract

Each implementer returns: `package_id`, `success`, `files_touched[]`, `tests_added[]`,
`summary`, `blocked_reason`.

Failure of one package: integrator tries to complete remaining coherent subset
or marks bet blocked — **no silent ship of half-broken multi-worker mess**.

---

## Relationship to Flywheel

- **Flywheel** = single-agent full cycle (still valid; Pruner injected before ship).  
- **Implement** = scaled execution for larger bets (M7, N0) under same Guardian.  
- Conductor may kick either; never both as dual NEXT.
