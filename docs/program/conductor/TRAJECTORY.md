# Trajectory — agent commerce vision

**Updated:** 2026-08-08T20:20:00Z (P7 post-merge)
**Main:** `4697c8d`

## Where we are

| Layer | State |
|-------|--------|
| M7 credits/SIWx | **On main** `2171bfa` (#23) + `386efff` (#28) — do not re-open |
| N0 notary | **On main** `4cd2d0c` (#30) |
| N1.1 EIP-191 attest | **On main** `db04ae2` (#33) |
| N1.2 free attest verify | **On main** `32d1054` (#34) |
| Plane docs | **On main** `a679b76` (#36) + `b7e4f34` (#37) |
| **P7 re-fetch verify** | **On main `4697c8d` (#38)** |
| On-chain settlements | **0** |

## Primary trajectory

```
M7 DONE → N0 DONE → N1.1 DONE → N1.2 DONE → P7 DONE
  → Overseer NEXT (cycle-1 dogfood | G9 design | N1.3 Merkle)
```

**This-cycle bet:** none (claim free). Continuous prefer_bet=M7 is **retired**.

## Parked

- Re-opening P7 / N0 / N1.1 / N1.2 / M7 / O.8 as product NEXT
- Dual product claims
- Settlement fiction without tx hash
- Merkle/anchors until explicit unpark

## Landmass

On-chain settlements: **0**. Multi-billion A2A hub: **L0 aspiration only**.
