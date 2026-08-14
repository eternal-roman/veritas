# Monitor — `fable/survival-records` (landed)

A26/A27/standing shipped in core (`veritas/audit.py`, `veritas/warranty.py`,
`veritas/standing.py`). Satellite clones `fable-veritas` and `veritas-fable`
are retired; do not recreate them.

## Re-check (core only)

```pwsh
Test-Path veritas\audit.py
Test-Path veritas\warranty.py
Test-Path veritas\standing.py
```

## Last verified

Cherry-picked onto `origin/main` (post P7-C). Gaps G10/G11/G12 remain open.
