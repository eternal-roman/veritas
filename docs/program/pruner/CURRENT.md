# Pruner CURRENT

- **Time:** 2026-08-08T21:00:00Z
- **Path:** POST-SHIP confirm (#46) → STANDBY for N1.4
- **Branch / HEAD:** tip **`6777a92`** (#46 G9-design); product surface landed
- **Scope:** Post-merge G13 confirm for G9-design; no open product PR
- **Verdict:** LEAN (fail-closed design surface; no second engine/payer; no ledger rewrite)
- **ship_ok:** **true** for landed #46 @ `6777a92` (retro). Next bet (N1.4) needs **fresh** ship_ok
- **Deleted / pruned:** none this tick
- **Refined:** none
- **Battery:** `tests/test_chain_reconcile.py` 9 passed; ruff clean on surface; `veritas-ops reconcile-chain` → `rpc_not_configured`; payment_model I1–I7 holds. Full suite not re-run (CI Tests SUCCESS on merge head)
- **E2E exercised:** `python -m veritas.ops_cli reconcile-chain` (fail-closed JSON)
- **Denied:** dual NEXT; re-open G9-design/M7/cycle-1 as product; invent settlement; merge red
- **Directive:** Claim free; NEXT = N1.4 Merkle when builders claim. Heavy G13 on that PR before ship.
- **PROPERTY / EVIDENCE / NOT PROVEN:**

```
PROPERTY: #46 on main 6777a92; lean fail-closed; ship_ok retro true; next ship needs fresh G13
EVIDENCE LEVEL: L1
CHECKED ARTIFACT: origin/main 6777a92; gh pr #46 MERGED CI green; local chain_reconcile + ops CLI
ASSUMPTIONS: Conductor/Overseer hold singular N1.4; no dual while next claim holds
NOT PROVEN: G9 closed; live RPC; on-chain settlements (0)
```
