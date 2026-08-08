# Trajectory — agent commerce vision

**Updated:** 2026-08-08T20:40:00Z (cycle-1 post-merge)
**Main:** `2cbed44`

## Where we are

| Layer | State |
|-------|--------|
| M7 credits/SIWx | **On main** — do not re-open |
| N0 notary | **On main** `4cd2d0c` (#30) |
| N1.1 EIP-191 attest | **On main** `db04ae2` (#33) |
| N1.2 free attest verify | **On main** `32d1054` (#34) |
| P7 re-fetch verify | **On main** `4697c8d` (#38) |
| N1.3 EvidencePack | **On main** `622429c` (#41) |
| **cycle-1 dogfood** | **On main `2cbed44` (#44)** |
| On-chain settlements | **0** |

## Primary trajectory

```
M7 → N0 → N1.1 → N1.2 → P7 → N1.3 → cycle-1 DONE
  → Overseer NEXT (G9 design | Merkle anchors | other)
```

**This-cycle bet:** none (claim free).

## Parked

- Re-opening cycle-1 / N1.3 / P7 / N0 / N1.1 / N1.2 / M7 / O.8 as product NEXT
- Dual product claims
- Settlement fiction without tx hash
- Full Merkle/anchors until explicit unpark
- G9 live chain reconcile (needs RPC)

## Landmass

On-chain settlements: **0**. Multi-billion A2A hub: **L0 aspiration only**.
cycle-1 proves first-boot agent surfaces offline after package install — not blank-machine PyPI cold install, not settlement.
