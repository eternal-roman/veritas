# Trajectory — agent commerce vision

**Updated:** 2026-08-08T23:25:00Z (continuous cycle 8 final)
**Main:** `2876f0a` (#78) · product `ab728a6` (A26/A27 #75) · prune `1c56a0b` (#77) · version **0.8.1**

## Where we are

| Layer | State |
|-------|--------|
| M7 → N0 → N1.x → P7 → P7-C | **On main** |
| G9-design | **On main** — gap **still open** |
| N0 residue prune (G13) | **On main** `1c56a0b` (#77) |
| **A26/A27** audit / warranty W0 / standing | **On main** `ab728a6` (#75) |
| Git Agent (plane) | **On main** `e78a7a9` (#76) |
| On-chain settlements | **0** |
| Claim | **free** |
| Open product PRs | **none** (open #81 docs only) |
| `VERITAS_RPC_URL` | **unset** → live-G9 **blocked** |

## Primary trajectory

```
… → P7-C DONE → A26/A27 DONE → N0 residue DONE
  → Overseer singular NEXT only
     candidates: live-RPC G9 dogfood (needs egress) | other unblocked slice
     external ops: PyPI Trusted Publishing
```

**This-cycle bet:** none (claim free · **restart=false**)

**Refuse:** `prefer_bet=M7` thrash — M7 landed #23/#28.

## Parked

- Re-opening M7 / N1.5 / P7-C / cycle-5 as dual NEXT
- Stale continuous `prefer_bet=M7` fan-out
- Inventing G9 closed / G10 closed / settlement green
- Discovery-before-money (Bazaar / X1 / X3 / X6)

## Landmass

On-chain settlements: **0**. Hub: **L0 only**. A26/A27 are L1 mechanism for
third-party-signed survival records — **not** multi-auditor volume, **not**
bond escrow (G12), **not** G10 closed. G9 open. Not PyPI.
