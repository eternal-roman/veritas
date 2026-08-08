# Monitor — `fable/survival-records` / `fable-veritas`

## Recovery path (this machine)

| Path | Role |
|------|------|
| **`C:\Users\elamj\Dev\fable-veritas`** | Primary Fable handoff + working clone |
| `C:\Users\elamj\Dev\fable-veritas\README_FABLE.md` | Handoff instructions (if present) |
| `C:\Users\elamj\Dev\fable-veritas\fable-survival-records.bundle` | Git bundle of Fable’s three commits |
| `C:\Users\elamj\Dev\fable-veritas\fable-survival-records.patch` | Mailbox patch alternative |
| `C:\Users\elamj\Dev\trial-fable` | **Not Veritas** — parked Money Furnace only |

## Branch (product)

| Item | Value |
|------|--------|
| Branch | `fable/survival-records` |
| Commits | A26 survival records → A27 warranty W0 → standing composition |
| Articles | A26 (L1), A27 (L1); constitution **2.4** |
| Gaps | G10 open; **G11** open (omission); **G12** open (bond escrow) |
| Closes G10? | **No** |

## Re-check

```pwsh
Test-Path C:\Users\elamj\Dev\fable-veritas\veritas\audit.py
Test-Path C:\Users\elamj\Dev\fable-veritas\veritas\warranty.py
Test-Path C:\Users\elamj\Dev\fable-veritas\veritas\standing.py
git -C C:\Users\elamj\Dev\fable-veritas log --oneline -5
git ls-remote --heads origin fable/survival-records
```

## Last verified

- Cherry-picked Fable bundle onto `origin/main` (post P7-C) cleanly.
- Audit/warranty/standing + constitution/known_gaps: **54 passed**, ruff clean.
