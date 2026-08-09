# Evolver workflow — roadblock → origin (hardened)

**Identity rule:** every problem carries `sender_agent` (origin). Solutions
must map back to that origin. Overseer and engineering receive copies, not
ownership of the origin identity.

## Lifecycle

```
1_submitted          submit(sender_agent, title, detail, kind, severity)
        │
2_claimed_by_evolver claim / claim_next
        │
3_evolved            evolutionary engine → attach_synthesis
        │
4_mapped_to_origin   report_to_origin  → docs/program/evolver/inbox/{sender}/
        │
5_overseer_notified  report_to_overseer → docs/program/evolver/outbox/overseer/
        │
6_engineering_handoff handoff_engineering → docs/program/evolver/engineering/
        │
7_closed             close_problem (optional terminal)
```

## CLI

```bash
# Origin agent journals a roadblock (required: --sender)
python -m veritas.evolver submit \
  --sender conductor --role conductor \
  --kind stall --severity 2 \
  --title "Green PR unmerged past 6m" \
  --detail "..." --source docs/program/ORG_LOOPS.md

# Steady supply + one full cycle (seed plane blockers, claim, map back)
python -m veritas.evolver tick --max-cycles 1

# One known id
python -m veritas.evolver cycle <problem_id>

# Inspect
python -m veritas.evolver list
python -m veritas.evolver snapshot
```

## Artifacts (git-friendly markdown; DB is local)

| Artifact | Path |
|----------|------|
| Journal DB | `.veritas/evolver_journal.sqlite3` (gitignored) |
| Audit JSONL | `.veritas/evolver_journal.audit.jsonl` |
| Origin inbox | `docs/program/evolver/inbox/{sender_agent}/{id}.md` |
| Overseer outbox | `docs/program/evolver/outbox/overseer/{id}.md` + `INDEX.md` |
| Engineering | `docs/program/evolver/engineering/{id}.md` |
| Run JSON | `docs/program/evolver/runs/{id}.json` |

## Who does what

| Actor | Duty |
|-------|------|
| Any agent | `submit` with **own** `sender_agent` when blocked |
| Evolver | `tick` / `cycle` — never set STATE NEXT |
| Origin | Read inbox on next tick; act or re-submit only if closed |
| Overseer | Read outbox; optional singular NEXT via STATE law |
| Engineering / Flywheel | Read handoff; ship only under free claim + product PR |

## Invariants

1. **Sender identity never rewritten** after submit.
2. **Origin report is mandatory** before Overseer/engineering complete.
3. **WATCH only** — blueprints are not approvals or claims.
4. Dedup open `sender+title` prevents thrash.
5. Seed list is plane honesty (Stage-1 human, unsolicited=0, free-on-merge), not invented product NEXT.
