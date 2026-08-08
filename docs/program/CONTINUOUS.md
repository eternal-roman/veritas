# Continuous control plane (builders + overseer)

Two durable loops, one honesty bar (`GUARDIAN.md`):

| Loop | Interval | Job |
|------|----------|-----|
| **Overseer** | **15 minutes** | Review WIP, kill lazy/half-measured work, strategic A2A redirect |
| **Flywheel** | **1 hour** | Build one honest bet (stock → ship → learn) |

Protocol: [`INNOVATION_LOOP.md`](INNOVATION_LOOP.md) · [`OVERSEER.md`](OVERSEER.md)  
**Guardian:** [`GUARDIAN.md`](GUARDIAN.md)  
Orchestrators: `.grok/workflows/agent-commerce-flywheel.rhai`,
`.grok/workflows/agent-commerce-overseer.rhai`  
Ledgers: [`cycles/`](cycles/), [`overseer/`](overseer/)

## Active schedules

### Overseer (every 15 minutes)

| Setting | Value |
|---------|--------|
| Interval | **15 minutes** |
| Scheduler task id | `019fdfde0212` (durable; re-arm after ~7 days) |
| Tick prompt | [`OVERSEER_TICK_PROMPT.md`](OVERSEER_TICK_PROMPT.md) |
| Writes | `overseer/CURRENT.md` + `overseer/log/NNN-brief.md` |
| Merge | Never |
| Role | Honesty + strategy; not a second builder |

### Flywheel (every 1 hour)

| Setting | Value |
|---------|--------|
| Interval | **1 hour** |
| Scheduler task id | `019fdfd6c9bf` (durable; re-arm after ~7 days) |
| Tick prompt | [`FLYWHEEL_TICK_PROMPT.md`](FLYWHEEL_TICK_PROMPT.md) |
| Mode | Durable scheduled task (survives session end) |
| Per tick | One full cycle: stock → select → plan → build → audit → verify → PR |
| Merge | **Off** (`auto_merge: false`) — human owns `main` |
| Concurrency | Skip tick if WIP clash or prior PR CI still pending |

Re-arm after ~7 days or if the task list is empty:

```text
Ask Grok: "Re-arm the Veritas flywheel and overseer schedulers"
```

Cancel:

```text
Ask Grok: "Stop the Veritas overseer scheduler" / "Stop the flywheel scheduler"
```

## Manual / interactive

```text
# Overseer pass (review + steer)
/workflow agent-commerce-overseer

# Builder cycle
/workflow agent-commerce-flywheel
/workflow agent-commerce-flywheel {"prefer_bet": "O.6", "max_cycles": 1}
/workflow agent-commerce-flywheel {"dry_run": true}
/workflow agent-commerce-flywheel {"max_cycles": 3, "auto_merge": false}
```

## Hourly tick contract (what the scheduler runs)

Each hour the agent must:

1. **cwd** = Veritas repo root (`veritas` / this workspace).
2. Read `docs/program/INNOVATION_LOOP.md`, `docs/program/STATE.md`, latest
   `docs/program/cycles/*.md`, `skills/adversarial-code-truth.md`.
3. **Skip** (exit with a one-line reason, change nothing) if:
   - `git status` shows another agent's incomplete flywheel WIP you did not start
     and cannot safely continue, **or**
   - a PR from the previous tick is open and CI is still running (wait for next hour), **or**
   - the battery cannot be run (missing venv) — report, do not invent green.
4. Prefer **STATE.md NEXT ACTION** unless a critical security/money-path defect
   outranks it (write the deviation in the cycle report).
5. Execute **one** shippable bet: tests first, implement, adversarial self-check,
   run `python -m pytest tests/ -q` (and ruff/harness/payment_model when feasible).
6. Push branch + open PR against `main` if there is a real delta. **Do not merge**
   unless explicitly configured. Never force-push `main`. Never claim on-chain
   settlement without a transaction hash.
7. Write `docs/program/cycles/NNN-<slug>.md` and update STATE.md NEXT ACTION.
8. Emit PROPERTY / EVIDENCE LEVEL / NOT PROVEN before any success claim.

### Windows (pwsh) shell rules

No bare `head` / `grep` / `tail` / `find`. Truncate with
`| Out-String -Stream | Select-Object -First N`. Prefer
`.\\scripts\\with-git-bash.cmd "..."` for complex git if the helper exists.

### Interactive workflow vs scheduled tick

| Path | When |
|------|------|
| `/workflow agent-commerce-flywheel` | Human in session; multi-agent phases |
| Hourly scheduler prompt | Unattended; single agent walks the same protocol |

Same protocol file. Same scorecard. Same ledger directory.

## What "done" never means

The hub vision is recursive. Stopping is external (delete the scheduler), not
"scorecard maxed". Volume and on-chain settlements are not inventable in-loop.
