# Trajectory — agent commerce vision

**Updated:** 2026-08-08T22:20:00Z (post-#78)
**Main:** `2876f0a` (#78 free claim) · product A26/A27 `ab728a6` (#75) · N0 residue `1c56a0b` (#77) · **version:** `0.8.1`

## Where we are

| Layer | State |
|-------|--------|
| M7 → N0 → N1.1–N1.5 → P7 → cycle-1/5 | **On main** |
| G9-design | **On main** — gap **still open** |
| **v0.8.1** | **On main** — **not** PyPI |
| **P7-C** free re-fetch `research_slots` | **On main** `e7f674b` (#69) |
| **N0 residue** fail-closed pack/log | **On main** `1c56a0b` (#77) |
| **A26/A27** audit + warranty W0 + standing | **On main** `ab728a6` (#75) |
| On-chain settlements | **0** |
| Claim | **free** (`2876f0a` / #78) |
| Open product PRs | **none** |

## Primary trajectory

```
… → P7-C DONE → N0 residue DONE → A26/A27 DONE
  → Overseer singular NEXT only
     candidates (blocked/external): live-RPC G9 | PyPI human ops | W1 after settle
```

**This-cycle bet:** none (claim free)

**Refuse:** prefer_bet=M7; re-open N0 / P7-C / A26-A27 dual.

## Parked

- Re-opening M7 / N1.5 / P7-C / N0 / A26-A27 as dual NEXT
- Live RPC G9 without egress
- Claiming G10 closed because A26 exists (gap stays open until trust is not self-reported)
- Bond escrow (G12) before proven settlement
- Settlement fiction

## Landmass

On-chain: **0**. Hub: **L0 only**. A26/A27 are L1 mechanism — no live multi-auditor
volume, no bond escrow, `/v1/trust` still self-reported (G10 open). G11/G12 open.
