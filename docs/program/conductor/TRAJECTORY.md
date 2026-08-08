# Trajectory — agent commerce vision

**Updated:** 2026-08-08T22:25:00Z (post-merge `48d7703`)
**Main:** `48d7703` (#82) · prior plane `458c36a` (#81) / `2876f0a` (#78) · product A26/A27 `ab728a6` (#75) · N0 residue `1c56a0b` (#77) · **version:** `0.8.1`

## Where we are

| Layer | State |
|-------|--------|
| M7 → N0 → N1.1–N1.5 → P7 → cycle-1/5 | **On main** |
| G9-design | **On main** — gap **still open** |
| **v0.8.1** | **On main** — **not** PyPI |
| **P7-C** free re-fetch `research_slots` | **On main** `e7f674b` (#69) |
| **N0 residue** fail-closed pack/log | **On main** `1c56a0b` (#77) |
| **A26/A27** audit + warranty W0 + standing | **On main** `ab728a6` (#75) |
| Plane closeouts | **On main** #78 / #81 / #82 |
| On-chain settlements | **0** |
| Claim | **free** |
| Open product PRs | **none** |
| `VERITAS_RPC_URL` | **unset** → live-G9 dogfood **blocked** |

## Primary trajectory

```
… → P7-C DONE → N0 residue DONE → A26/A27 DONE
  → Overseer HOLD (this era)
     when unblocked: live-RPC G9 dogfood (G9-L-A…E)
     external only: PyPI Trusted Publishing (human ops)
```

**This-cycle bet:** none (claim free · restart=false)

**Refuse:** `prefer_bet=M7` thrash — M7 landed. Do not re-open A26/A27 / N0-residue / P7-C.

## Parked

- Re-opening M7 / N1.5 / P7-C / 0.8.1 / cycle-5 / N1.4 / G9-design / N0 / A26-A27 as dual NEXT
- Stale `prefer_bet=M7` or `N0` in continuous params when STATE is free/HOLD
- Live RPC G9 close without egress / invented settlement green
- Treating version bump as PyPI / revenue-ready
- Claiming G10 closed because A26 exists (gap stays open until trust is not self-reported)
- Bond escrow (G12) before proven settlement
- Bazaar / X1 / X3 / X6 before money is real
- Settlement fiction

## Landmass

On-chain settlements: **0**. Hub: **L0 only**. v0.8.0 / v0.8.1 are local version +
docs cuts — not published, not settled, not G9-closed. A26/A27 are L1 mechanism —
no live multi-auditor volume, no bond escrow, `/v1/trust` still self-reported
(G10 open). G11/G12 open. P7-C is L1 shed path only — multi-instance / live load
**not** proven.
