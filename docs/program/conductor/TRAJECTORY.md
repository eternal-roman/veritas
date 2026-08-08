# Trajectory — agent commerce vision

**Updated:** 2026-08-08T20:35:00Z (N1.3 post-merge)
**Main:** `622429c`

## Where we are

| Layer | State |
|-------|--------|
| M7 credits/SIWx | **On main** — do not re-open |
| N0 notary | **On main** `4cd2d0c` (#30) |
| N1.1 EIP-191 attest | **On main** `db04ae2` (#33) |
| N1.2 free attest verify | **On main** `32d1054` (#34) |
| Plane docs | **On main** `330bf68` (#39) |
| P7 re-fetch verify | **On main** `4697c8d` (#38) |
| **N1.3 EvidencePack** | **On main `622429c` (#41)** |
| On-chain settlements | **0** |

## Primary trajectory

```
M7 DONE → N0 DONE → N1.1 DONE → N1.2 DONE → P7 DONE → N1.3 DONE
  → Overseer NEXT (cycle-1 dogfood | G9 design | Merkle anchors)
```

**This-cycle bet:** none (claim free). Continuous prefer_bet closed for landed product.

## Parked

- Re-opening N1.3 / P7 / N0 / N1.1 / N1.2 / M7 / O.8 as product NEXT
- Dual product claims
- Settlement fiction without tx hash
- Full Merkle/anchors until explicit unpark
- G9 live chain reconcile (needs RPC)

## Landmass

On-chain settlements: **0**. Multi-billion A2A hub: **L0 aspiration only**.
Pack `pack_hash` is transit integrity, not multi-party origin proof.
