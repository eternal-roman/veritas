# Overseer log 005 — O.8 is PR #22 green; merge gate

**Time:** 2026-08-08T17:40:54Z  
**Verdict:** ON_TASK  
**Scores:** on-task 3 / measured 3 / integrity 3 / a2a 2 / claims 3

## Facts verified (this tick)

| Fact | Result |
|------|--------|
| `origin/main` tip | `a4cfc49` (#19) |
| O.6 / retention on main | yes (ancestry) |
| Open product PRs | **#22** O.8 supply chain |
| Open docs PRs | **#21** card hygiene |
| #22 CI | all **SUCCESS** (incl. Package build & install = SBOM path) |
| #22 head | `e6b9a10` on `feat/o.8-supply-chain-hardening` |
| Soft-fail in O.8 workflows | **none** (`continue-on-error` / `\|\| true` empty) |
| Action pins | full 40-hex SHAs + version comments |
| Locks | `requirements.lock` + `requirements-dev.lock` with `--hash=sha256:` |
| CI install | `--require-hashes` |
| Worktree o8b | clean, = PR head, 2 commits ahead of main |
| Worktree o8 | dirty uncommitted, **0** commits ahead — do not ship from here |
| On-chain settlements | **0** |

## Delta vs log 004

004: O.8 uncommitted WIP, no product PR, dual-tree thrash warning.  
005: **#22 open + green**; o8b is the reconciled ship; o8 residual is thrash only if recommitted.

## Integrity spot-check (#22)

- Fail-closed lock generator (off-target refuse) — L1-tested.
- SBOM subject = wheel venv, not CI toolchain — L1-tested + CI assert no pytest/ruff leak.
- Release job does not combine `id-token: write` with `contents: write` — L1-tested.
- Second commit fixed real `--outfile` vs `--output-file` and added generator-help tooth test — measured, not theater.
- PR claim hygiene: PROPERTY / L1 / NOT PROVEN (wild install, benign pins, image path).

## Lazy?

No on #22. **Half-measured risk only if** agents start M7 from PR-local STATE before merge, or open a second O.8 PR from o8.

## Strategic A2A

Merge shortens hostile install-trust path (axis F). Does not prove money (C=0) or notary worth (D). Next real product bet after merge: **M7**, not N0/Bazaar.

## Directive

Human merge **#22** first; abandon o8 WIP; no M7 product code until main carries O.8.

## Gate (this review)

```
PROPERTY: Overseer correctly reclassifies O.8 from mid-flight WIP to green open PR #22 and freezes dual/M7 thrash
EVIDENCE LEVEL: L1 git/gh/worktree/workflow inspection; L0 local pytest this tick (CI is the battery witness)
CHECKED ARTIFACT: PR #22 e6b9a10; checks SUCCESS; o8b clean; o8 dirty 0-ahead; main a4cfc49
ASSUMPTIONS: gh statusCheckRollup reflects head SHA; human owns merge
NOT PROVEN: post-merge main green; settlement; Docker pin; signed SBOM
```
