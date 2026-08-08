# Trajectory — agent commerce vision

**Updated:** 2026-08-08T21:10:00Z (continuous cycle-5)
**Main:** `b253532`

## Where we are

| Layer | State |
|-------|--------|
| M7 credits/SIWx | **On main** — do not re-open |
| N0 notary | **On main** `4cd2d0c` (#30) |
| N1.1–N1.3 / P7 | **On main** |
| cycle-1 dogfood | **On main** `2cbed44` (#44) |
| G9-design reconcile | **On main** `6777a92` (#46) — gap G9 **open** |
| **N1.4 Merkle log** | **On main `b253532` (#49)** |
| On-chain settlements | **0** |

## Primary trajectory

```
M7 → N0 → N1.1 → N1.2 → P7 → N1.3 → cycle-1 → G9-design → N1.4 DONE
  → cycle-5 ecosystem dogfood (STATE NEXT)
```

**This-cycle bet:** **cycle-5**.

## Parked

- Dual product claims; re-open N1.4 / G9-design / N0 / M7 as NEXT
- prefer_bet=N0 while N0 already on main
- Settlement fiction; claiming G9 closed without RPC
- Live RPC G9 dogfood until cycle-5 claim free or Overseer outranks

## Landmass

On-chain settlements: **0**. Multi-billion A2A hub: **L0 only**.
N1.4 = operator-local Merkle inclusion, not public CT / not on-chain.
