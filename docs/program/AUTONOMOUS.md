# Autonomous workflow policy

**No human-in-the-loop** for the agent-commerce control plane and flywheel.
Operators may still act (merge, re-arm, fund chains) but **workflows must not
block on `await_user` / human pause** to make progress.

Autonomy does **not** mean ungoverned. Progress remains under:

1. [`GOVERNING.md`](GOVERNING.md) — loops, goals, Overseer vision gate  
2. [`GUARDIAN.md`](GUARDIAN.md) — no failing/fake code (incl. **G13 Pruner**)  
3. Overseer CURRENT directives — quality + strategy  
4. [`PRUNER.md`](PRUNER.md) — no useless / non-functional / bloated ship  
5. [`IMPLEMENTERS.md`](IMPLEMENTERS.md) — scale N workers on **one** bet only

## Defaults

| Setting | Value |
|---------|--------|
| `auto_merge` | **true** — squash-merge when required CI is green on head SHA |
| Human gates | **none** in flywheel / conductor / continuous Rhai |
| Audit rounds | up to **3** fix→re-audit loops; then skip cycle (not pause) |
| Minor findings | **advisory only** — do not block ship alone |
| Open green PR for NEXT | **merge or short-circuit** — do not dual-build |
| Claim file | `docs/program/flywheel-claim.md` — G10 single builder surface |
| Failure mode | log + skip/retry next cycle or tick |

## Progress path (autonomous)

```
Stock → Gate (merge_existing | wait_ci | claim_blocked | proceed)
     → Select → Claim → Build → Audit×N → Verify → PR → auto-merge
     → Learn → next cycle
```

If CI pending: **poll once**, else skip to next cycle/tick (scheduled plane
retries). Never sit on a human gate.

## What still requires a human (out of band)

Not workflow gates — external reality:

- Mainnet funding, TLS, PyPI publisher identity  
- RPC / facilitator egress for true on-chain proof (G9)  
- Re-arming durable schedulers after ~7 days  
- Policy override: pass `auto_merge: false` only if you intentionally want open PRs left unmerged  

## Workflows

| Workflow | Role |
|----------|------|
| `agent-commerce-flywheel` | Full cycle, auto-merge, bounded audit |
| `agent-commerce-conductor` | Confer + merge green + build + recurse |
| `agent-commerce-continuous` | Multi-pass autonomous wrapper |

```text
/workflow agent-commerce-continuous {"max_cycles": 4}
/workflow agent-commerce-flywheel {"max_cycles": 3, "auto_merge": true}
/workflow agent-commerce-conductor {"continuous": true, "max_cycles": 3}
```

## Guardian interaction

- **G8** still fail-closed for **blocker/major**; minors do not veto.  
- **G10** claim file prevents dual O.8-class thrash.  
- **G12** updated: autonomous default is merge-on-green; never merge red.  

## Claim file format (`flywheel-claim.md`)

```markdown
# flywheel-claim
- bet_id: M7
- branch: feat/m7-...
- holder: agent-commerce-flywheel
- status: building | free | audit_exhausted
- updated: <ISO or cycle id>
```

Clear or set `status: free` after merge or abandon.
