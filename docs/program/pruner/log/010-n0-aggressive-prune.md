# Pruner log 010 — N0 aggressive multi-worker residue (G13)

**Time:** 2026-08-08T22:15:00Z  
**Claim:** N0 (surface re-gate; branch `feat/n0-notary-core` merged as #30 @ `4cd2d0c`)  
**HEAD base:** `e7f674b` · branch `pruner/n0-residue-gate`

## Path

AGGRESSIVE heavy gate. Product branch gone; purge multi-worker soft-fails and dead package exports on N0 compose path.

## Pruned

| Item | Action |
|------|--------|
| package re-exports | deleted (zero callers) |
| soft-fail pack | fail-closed |
| soft-fail evidence log | fail-closed |
| triple unavailable blocks | `_fetch_unavailable` |
| stale __init__ docstring | accurate N0–N1.5/P7 map |

Net ≈ **−72 LOC**.

## Battery

| Check | Result |
|-------|--------|
| pytest | 752 passed, 1 skipped |
| ruff | pass |
| harness | exit 0 |
| payment_model | I1–I7 holds |

## ship_ok

**true** — LEAN + battery_green + no broken claims
