# Trajectory — agent commerce vision

**Updated:** 2026-08-08T21:00:00Z (conductor continuous cycle 6)
**Main:** `6777a92`

## Where we are

| Layer | State |
|-------|--------|
| M7 credits/SIWx | **On main** — do not re-open |
| N0 notary | **On main** `4cd2d0c` (#30) |
| N1.1 EIP-191 attest | **On main** `db04ae2` (#33) |
| N1.2 free attest verify | **On main** `32d1054` (#34) |
| P7 re-fetch verify | **On main** `4697c8d` (#38) |
| N1.3 EvidencePack | **On main** `622429c` (#41) |
| cycle-1 dogfood | **On main** `2cbed44` (#44) |
| **G9-design reconcile** | **On main `6777a92` (#46)** — gap G9 still open |
| On-chain settlements | **0** |

## Primary trajectory

```
M7 → N0 → N1.1 → N1.2 → P7 → N1.3 → cycle-1 → G9-design DONE
  → N1.4 Merkle / inclusion anchors (THIS NEXT)
  → cycle-5 / live-RPC G9 dogfood (parked until Merkle or RPC)
```

**This-cycle bet:** **N1.4 Merkle / inclusion anchors**

## Parked

- Re-opening G9-design / cycle-1 / N1.3 / P7 / N0 / N1.1 / N1.2 / **M7** / O.8 as product NEXT
- Stale `prefer_bet=M7` hard-defaults (Optimizer: empty prefer_bet)
- Dual product claims
- Settlement fiction without tx hash
- Live RPC G9 close (needs egress)
- Cycle-5 ecosystem dogfood until Merkle or Overseer re-order

## Landmass

On-chain settlements: **0**. Multi-billion A2A hub: **L0 aspiration only**.
G9-design proves fail-closed operator surface — not chain confirmation.
