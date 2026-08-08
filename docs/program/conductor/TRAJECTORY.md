# Trajectory — agent commerce vision

**Updated:** 2026-08-08T20:36:00Z  
**Main:** `622429c`

## Where we are

| Layer | State |
|-------|--------|
| M7 credits/SIWx | **On main** — do not re-open |
| N0 notary | **On main** `4cd2d0c` (#30) |
| N1.1 / N1.2 | **On main** |
| P7 re-fetch verify | **On main** `4697c8d` (#38) |
| **N1.3 EvidencePack** | **On main `622429c` (#41)** |
| On-chain settlements | **0** |

## Primary trajectory

```
… → P7 DONE → N1.3 DONE → cycle-1 cold install (building) → (parked) G9
```

**This-cycle bet:** **cycle-1**.

## Parked

- G9 chain reconcile (RPC)
- Re-open N1.3 / P7 / N0 / N1 / M7 / O.8
- Settlement fiction without tx hash
- Full Merkle inclusion log (beyond pack_hash)

## Landmass

On-chain settlements: **0**. Hub multi-billion: **L0 aspiration only**.
