# Trajectory — agent commerce vision

**Updated:** 2026-08-08T20:15:00Z  
**Main:** 679b76 (docs) · product 32d1054

## Where we are

| Layer | State |
|-------|--------|
| M7 credits/SIWx | **On main** 2171bfa (#23) + 386efff (#28) — do not re-open |
| N0 notary | **On main** 4cd2d0c (#30) |
| N1.1 EIP-191 attest | **On main** db04ae2 (#33) |
| N1.2 free attest verify | **On main** 32d1054 (#34) |
| Plane closeout | **On main** 679b76 (#36) |
| Integrity #29/#32 | **On main** c15b1b · 23a0086 |
| On-chain settlements | **0** |

## Primary trajectory

`
M7 DONE → N0 DONE → N1.1 DONE → N1.2 DONE
  → cycle-1 dogfood | G9 design | N1.3+/P7 re-fetch (Overseer picks one)
`

**This-cycle bet:** none (claim free). Continuous prefer_bet=M7 is **retired**.

## Parked

- Re-opening M7 / O.8 / N0 / N1.1 / N1.2 as product NEXT  
- Dual product claims / off-claim P7 WIP  
- Settlement fiction without tx hash  
- Merkle/anchors until explicit unpark  

## Landmass

On-chain settlements: **0**. Multi-billion A2A hub: **L0 aspiration only**.
