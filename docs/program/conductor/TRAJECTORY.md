# Trajectory — agent commerce vision

**Updated:** 2026-08-08T21:20:00Z (post-merge #58 release-0.8.0)
**Main:** `58beccc`

## Where we are

| Layer | State |
|-------|--------|
| M7 → N0 → N1.1–N1.3 → P7 → cycle-1 | **On main** |
| G9-design | **On main** `6777a92` — gap open |
| N1.4 Merkle log | **On main** `b253532` |
| cycle-5 dogfood | **On main** `bf09a99` (#54) 7/7 offline |
| **v0.8.0 prep** | **On main `58beccc` (#58)** version cut; **not** PyPI |
| On-chain settlements | **0** |

## Primary trajectory

```
… → G9-design DONE → N1.4 DONE → cycle-5 DONE → release-0.8.0 prep DONE
  → Overseer singular NEXT (live-RPC G9 if egress | PyPI ops | other)
```

**This-cycle bet:** none (claim free)

## Parked

- Re-opening release-0.8.0 / cycle-5 / N1.4 / G9-design / **M7** / cycle-1 / N1.x / P7 / N0
- Stale `prefer_bet=M7` or `N0`
- Live RPC G9 close without egress
- Treating version bump as PyPI / revenue-ready
- Bazaar / X1 / X3 / X6
- Settlement fiction

## Landmass

On-chain settlements: **0**. Hub: **L0 only**. v0.8.0 is a local version +
docs cut — not published, not settled, not G9-closed.
