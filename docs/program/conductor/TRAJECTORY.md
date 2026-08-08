# Trajectory — agent commerce vision

**Updated:** 2026-08-08T20:27:00Z  
**Main:** `330bf68`

## Where we are

| Layer | State |
|-------|--------|
| M7 credits/SIWx | **On main** — do not re-open |
| N0 notary | **On main** `4cd2d0c` (#30) |
| N1.1 EIP-191 attest | **On main** `db04ae2` (#33) |
| N1.2 free attest verify | **On main** `32d1054` (#34) |
| Plane docs | **On main** `330bf68` (#39) |
| **P7 re-fetch verify** | **On main `4697c8d` (#38)** |
| On-chain settlements | **0** |

## Primary trajectory

```
M7 DONE → N0 DONE → N1.1 DONE → N1.2 DONE → P7 DONE
  → cycle-1 cold install dogfood (building)
  → (parked) N1.3 Merkle | G9 design
```

**This-cycle bet:** **cycle-1**. Continuous prefer_bet=M7 is **retired**.

## Parked

- N1.3 Merkle / evidence pack (not dual under this claim)
- G9 chain reconcile (needs RPC)
- Re-opening P7 / N0 / N1.1 / N1.2 / M7 / O.8
- Settlement fiction without tx hash

## Landmass

On-chain settlements: **0**. Multi-billion A2A hub: **L0 aspiration only**.
