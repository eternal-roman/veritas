# Pruner CURRENT

- **Time:** 2026-08-08T21:25:00Z
- **Path:** STANDBY — product surface open; G13 **pending** green #60
- **Branch / HEAD:** tip `e5092ca` (#59); release prep `58beccc` (#58); WIP **#60**
- **Scope:** #60 N1.5 (`feat/n1.5-inclusion-proof-on-observe`) — claim **building**
- **Verdict:** HOLD (do not ship_ok while CI incomplete/red)
- **ship_ok:** **not granted** this tick. Last product: cycle-5 #54 @ `bf09a99`
- **Battery:** **not run** (wait full green CI on #60 before heavy G13)
- **Denied:** dual NEXT; merge red/pending #60; invent settlement; re-open cycle-5/N1.4 as NEXT
- **Directive:** After #60 is full green on tip, run full G13 battery before merge.
- **PROPERTY / EVIDENCE / NOT PROVEN:**

```
PROPERTY: Product PR #60 open under claim; no ship_ok until full green CI
EVIDENCE LEVEL: L1
CHECKED ARTIFACT: origin/main e5092ca; gh pr #60; flywheel-claim building
ASSUMPTIONS: Flywheel completes CI before requesting G13
NOT PROVEN: on-chain (0); G9 closed; N1.5 ship
```
