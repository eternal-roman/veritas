# Pruner CURRENT

- **Time:** 2026-08-08T20:58:00Z
- **Path:** STANDBY — product surface open; G13 **pending** green #49
- **Branch / HEAD:** tip `b77339f` (#48); product G9-design `6777a92` (#46); WIP **#49**
- **Scope:** #49 N1.4 (`feat/n1.4-merkle-evidence-log`) — claim **building**
- **Verdict:** HOLD (do not ship_ok while Tests fail / CONFLICTING)
- **ship_ok:** **not granted** this tick. Last landed product: G9-design #46 @ `6777a92`
- **Deleted / pruned:** none
- **Refined:** none
- **Battery:** **not run** (wait for rebased green CI on #49 before heavy G13)
- **E2E exercised:** none this tick
- **Denied:** dual NEXT; merge red #49; invent settlement; re-open G9-design surface / cycle-1 / N1.3 as NEXT
- **Directive:** After #49 is green + rebased onto `b77339f`, run full G13 battery before merge.
- **PROPERTY / EVIDENCE / NOT PROVEN:**

```
PROPERTY: Product PR #49 open under claim; no ship_ok while Tests fail / CONFLICTING
EVIDENCE LEVEL: L1
CHECKED ARTIFACT: origin/main b77339f; gh pr #49; flywheel-claim building
ASSUMPTIONS: Flywheel fixes Tests + rebase before requesting G13
NOT PROVEN: on-chain settlement (0); G9 closed; N1.4 ship
```
