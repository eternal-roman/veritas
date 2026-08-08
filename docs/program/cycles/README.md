# Innovation cycle ledger

Each completed flywheel cycle writes `NNN-<slug>.md` here.

| File | Meaning |
|------|---------|
| [000-baseline.md](000-baseline.md) | Stock of `main` before the loop; scorecard floor |
| [001-o6-retention-410-gone.md](001-o6-retention-410-gone.md) | O.6 retention/pruning; 410 Gone ≠ 404; axis B 2→3; PR #18 |
| `002-…` onward | One shippable bet each: scores, PR, learnings, next bet |

Protocol: [`../INNOVATION_LOOP.md`](../INNOVATION_LOOP.md)  
Orchestration: `.grok/workflows/agent-commerce-flywheel.rhai`

## How to run

```text
# One cycle (build + PR; merge only if you pass auto_merge)
/workflow agent-commerce-flywheel

# Plan only
/workflow agent-commerce-flywheel {"dry_run": true}

# Prefer a bet id from STATE / ROADMAP
/workflow agent-commerce-flywheel {"prefer_bet": "O.6", "max_cycles": 1}

# Burst (pauses between unmerged PRs)
/workflow agent-commerce-flywheel {"max_cycles": 3, "auto_merge": false}
```

Continuous mode: schedule a prompt every few hours that invokes the same
workflow with `max_cycles: 1`. See INNOVATION_LOOP.md § Continuous operation.
