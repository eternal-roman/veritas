# Overseer log 007 — #22 head db541ce (mcp pin); CI green again

**Time:** 2026-08-08T18:00:53Z  
**Verdict:** ON_TASK  
**Scores:** on-task 3 / measured 3 / integrity 3 / a2a 2 / claims 3  
**noop_stable:** no (vs 006)

## Delta vs 006

| Item | 006 | 007 |
|------|-----|-----|
| #22 head | `e6b9a10` | **`db541ce`** |
| CI | all SUCCESS (old head) | re-run **all SUCCESS** on new head |
| Product change | — | pin `mcp>=1.0,<2` → lock `mcp==1.29.0` (O19/FastMCP) |
| Dual tree | o8 dirty 0-ahead | o8 **local commit `95c4ab4`** (not open PR) |
| main tip | `a4cfc49` | unchanged |

## Integrity note (mcp)

Hashed CI path had frozen mcp 2.x → FastMCP import gone → permanent skip → STATUS claim hollow. Upper bound aligned with `pyproject` optional `[mcp]`. **Anti-lazy.** No soft-fail / unpinned `uses:` on head.

## Dual-worktree watch (G10)

- Ship: `veritas-o8b` / `feat/o.8-supply-chain-hardening` @ `db541ce` = **#22**
- Residue: `veritas-o8` / `feat/o.8-supply-chain` @ `95c4ab4` local only — **do not open PR #23**

## Directive

Human merge **#22**; freeze product; no M7 pre-merge.

## Gate

```
PROPERTY: #22 advanced with measured mcp lock fix; CI all green; still merge-gated; no second product PR
EVIDENCE LEVEL: L1 gh checks + git show db541ce + worktree status
CHECKED ARTIFACT: PR #22 db541ce; checks SUCCESS; o8 95c4ab4 local
ASSUMPTIONS: Agents abandon o8 alternate
NOT PROVEN: Merge; settlement; Docker pin
```
