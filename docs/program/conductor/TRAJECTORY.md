# Trajectory — agent commerce vision

**Updated:** 2026-08-08T23:10:00Z (continuous cycle 8)
**Main:** `64b7a1a` (#72) · closeout `e45a2f5` (#71) · product tip `e7f674b` (P7-C #69) · version **0.8.1**

## Where we are

| Layer | State |
|-------|--------|
| M7 → N0 → N1.1–N1.4 → P7 → cycle-1/5 | **On main** |
| G9-design | **On main** `6777a92` — gap **still open** |
| **N1.5** inclusion proof on observe | **On main** `e089f86` (#60) |
| **v0.8.1** | **On main** `070d4c4` (#62) — **not** PyPI |
| **P7-C** free re-fetch `research_slots` | **On main** `e7f674b` (#69) |
| Program closeouts | **On main** `e45a2f5` (#71), `64b7a1a` (#72) |
| On-chain settlements | **0** |
| Claim | **free** |
| Open product PRs | **none** |
| `VERITAS_RPC_URL` | **unset** → live-G9 dogfood **blocked** |

## Primary trajectory

```
… → N1.5 DONE → 0.8.1 DONE → P7-C DONE
  → Overseer HOLD (this era)
     when unblocked: live-RPC G9 dogfood (G9-L-A…E)
     external only: PyPI Trusted Publishing (human ops)
```

**This-cycle bet:** none (claim free · restart=false)

**Refuse:** `prefer_bet=M7` thrash — M7 landed `2171bfa` (#23) + crash refund `386efff` (#28).

## Parked

- Re-opening M7 / N1.5 / P7-C / 0.8.1 / cycle-5 / N1.4 / G9-design / N0 as dual NEXT
- Stale `prefer_bet=M7` or `N0` in continuous params when STATE is free/HOLD
- Live RPC G9 close without egress / invented settlement green
- Treating version bump as PyPI / revenue-ready
- Bazaar / X1 / X3 / X6 before money is real
- Settlement fiction

## Landmass

On-chain settlements: **0**. Hub: **L0 only**. v0.8.0 / v0.8.1 are local version +
docs cuts — not published, not settled, not G9-closed. P7-C is L1 shed path only
— multi-instance / live load **not** proven.
