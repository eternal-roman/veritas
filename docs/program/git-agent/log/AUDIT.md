# Git branch audit

**Generated:** 2026-08-08T22:02:44.166168+00:00
**origin/main:** `1e89e245d446`
**Remote branches:** 25

## Buckets

### active_product (1)
- `origin/fable/survival-records`

### fully_merged (4)
- `origin/docs/cycle1-closeout`
- `origin/docs/n0-closeout-plane`
- `origin/docs/n13-closeout-cycle1`
- `origin/docs/release-080-closeout`

### protected (1)
- `origin/main`

### stale_docs_closeout (16)
- `origin/docs/conductor-c1-assign`
- `origin/docs/conductor-c6-final`
- `origin/docs/conductor-c6-n15-close`
- `origin/docs/cycle5-closeout`
- `origin/docs/g9-design-closeout-c6`
- `origin/docs/n1.3-post-merge-closeout`
- `origin/docs/n14-closeout`
- `origin/docs/p7c-assign`
- `origin/docs/post-merge-tip-330bf68`
- `origin/docs/steward-post-080-cards`
- `origin/docs/steward-post-081-free`
- `origin/docs/steward-post-45-g9-hygiene`
- `origin/docs/steward-post-g9-n14-hygiene`
- `origin/docs/steward-post-n14-cycle5-claim`
- `origin/docs/steward-post-p7c-tip`
- `origin/docs/v080-tip-align`

### unmerged_product (3)
- `origin/feat/o.6-retention-410-gone`
- `origin/feat/p7c-refetch-research-slots`
- `origin/fix/lock-must-satisfy-declared-bounds`

## Overseer review required

- **`origin/fable/survival-records`** — active_product / keep_open_pr_or_confer: A26/A27/standing mechanism — PR #75 family; do not drop
- **`origin/feat/o.6-retention-410-gone`** — unmerged_product / overseer_review_diff: inspect unique commits vs main; open salvage PR or abandon with reason
- **`origin/feat/p7c-refetch-research-slots`** — unmerged_product / overseer_review_diff: inspect unique commits vs main; open salvage PR or abandon with reason
- **`origin/fix/lock-must-satisfy-declared-bounds`** — unmerged_product / overseer_review_diff: inspect unique commits vs main; open salvage PR or abandon with reason

## Safe delete candidates (tip ancestor of main)

- `origin/docs/cycle1-closeout`
- `origin/docs/n0-closeout-plane`
- `origin/docs/n13-closeout-cycle1`
- `origin/docs/release-080-closeout`

## Local gone-tracking (cleanup worktrees/branches)

- `docs/conductor-c4-plane                 75d79e4 [origin/docs/conductor-c4-plane: gone] docs(program): conductor cycle-4 cards post N1.1/N1.2/tip #36`
- `docs/p7c-post-merge-refresh             c82c926 [origin/docs/p7c-post-merge-refresh: gone] docs(program): conductor continuous cycle 7 — free claim, refuse M7 thrash`
- `+ docs/release-081-closeout               2d2d9de (C:/Users/elamj/Dev/veritas-close081) [origin/docs/release-081-closeout: gone] docs(program): v0.8.1 closeout — free claim, tip 070d4c4, tags noted`
- `docs/steward-card-hygiene-o8            1130b3f [origin/docs/steward-card-hygiene-o8: gone] merge origin/main: resolve STATE.md — O.8 on main, NEXT=M7`
- `+ feat/cycle1-cold-install                ebd3311 (C:/Users/elamj/Dev/veritas-c1) [origin/feat/cycle1-cold-install: gone] cycle-1: cold autonomous install / first-boot dogfood`
- `+ feat/cycle5-ecosystem-dogfood           855a96d (C:/Users/elamj/Dev/veritas-c5) [origin/feat/cycle5-ecosystem-dogfood: gone] cycle-5: ecosystem participant dogfood (discovery + offline verify)`
- `+ feat/g9-chain-reconcile-design          311f2a3 (C:/Users/elamj/Dev/veritas-g9) [origin/feat/g9-chain-reconcile-design: gone] docs(g9): tip-align STATE/claim after rebase onto df1cc8f`
- `+ feat/n1.3-evidence-pack                 4dc2cbd (C:/Users/elamj/Dev/veritas-n13) [origin/feat/n1.3-evidence-pack: gone] N1.3: portable EvidencePack for agent-to-agent handoff`
- `+ feat/n1.4-merkle-evidence-log           889efeb (C:/Users/elamj/Dev/veritas-n14) [origin/feat/n1.4-merkle-evidence-log: gone] fix(n1.4): map inclusion ValueError to fixed index code`
- `feat/n1.5-inclusion-proof-on-observe    f791e65 [origin/feat/n1.5-inclusion-proof-on-observe: gone] N1.5: embed Merkle inclusion proof on completed observe envelopes`
- `+ feat/o.8-supply-chain-hardening         db541ce (C:/Users/elamj/Dev/veritas-o8b) [origin/feat/o.8-supply-chain-hardening: gone] O.8: pin mcp>=1.0,<2 in dev lock (O19 / FastMCP)`
- `+ feat/o.8b-container-hash-lock           cfe3678 (C:/Users/elamj/Dev/veritas-o8c) [origin/feat/o.8b-container-hash-lock: gone] docs(program): tip-align STATE for O.8b — NEXT=N0 after M7 on main`
- `feat/p7-refetch-verify                  d8b7fa0 [origin/feat/p7-refetch-verify: gone] Merge branch 'main' into feat/p7-refetch-verify`
- `feat/p7c-refetch-v2                     e8bffb3 [origin/feat/p7c-refetch-v2: gone] P7-C: free re-fetch takes research_slots on POST /v1/verify`
- `feat/session-2026-08-08                 e456782 [origin/feat/session-2026-08-08: gone] Add a standalone verifier a buyer can vendor and read whole`
- `+ fix/credit-refund-on-unexpected-failure 3a4b316 (C:/Users/elamj/Dev/veritas-m7b) [origin/fix/credit-refund-on-unexpected-failure: gone] Reverse a credit debit when a request dies unexpectedly (invariant 3)`
- `+ fix/sdk-surface-must-fail-not-skip      54d3f14 (C:/Users/elamj/Dev/veritas-sdk) [origin/fix/sdk-surface-must-fail-not-skip: gone] Restore the mcp<2 bound, with the wheel inspected rather than the comment trusted`
- `+ fix/verify-claim-retraction             0297f65 (C:/Users/elamj/Dev/veritas-session) [origin/fix/verify-claim-retraction: gone] Retract the /v1/verify independence claim, and pin P7 with a witness`
- `+ release/v0.8.0-prep                     8b638fb (C:/Users/elamj/Dev/veritas-v080) [origin/release/v0.8.0-prep: gone] chore(release): prepare v0.8.0 — A2A notary spine cut`
- `+ release/v0.8.1-prep                     04ef9a3 (C:/Users/elamj/Dev/veritas-v081) [origin/release/v0.8.1-prep: gone] chore(release): prepare v0.8.1 — N1.5 inclusion proof on observe`

## Worktrees

```
C:/Users/elamj/Dev/veritas           1e89e24 [main]
C:/Users/elamj/Dev/veritas-c1        ebd3311 [feat/cycle1-cold-install]
C:/Users/elamj/Dev/veritas-c5        855a96d [feat/cycle5-ecosystem-dogfood]
C:/Users/elamj/Dev/veritas-close081  2d2d9de [docs/release-081-closeout]
C:/Users/elamj/Dev/veritas-fable     6ce53ae (detached HEAD)
C:/Users/elamj/Dev/veritas-fable-sr  6ce53ae [fable/survival-records]
C:/Users/elamj/Dev/veritas-g10       3794969 [docs/g10-survival-reputation-consensus]
C:/Users/elamj/Dev/veritas-g9        311f2a3 [feat/g9-chain-reconcile-design]
C:/Users/elamj/Dev/veritas-lock      2a1eb32 [fix/lock-must-satisfy-declared-bounds]
C:/Users/elamj/Dev/veritas-m7b       3a4b316 [fix/credit-refund-on-unexpected-failure]
C:/Users/elamj/Dev/veritas-n13       4dc2cbd [feat/n1.3-evidence-pack]
C:/Users/elamj/Dev/veritas-n14       889efeb [feat/n1.4-merkle-evidence-log]
C:/Users/elamj/Dev/veritas-o8        95c4ab4 [feat/o.8-supply-chain]
C:/Users/elamj/Dev/veritas-o8b       db541ce [feat/o.8-supply-chain-hardening]
C:/Users/elamj/Dev/veritas-o8c       cfe3678 [feat/o.8b-container-hash-lock]
C:/Users/elamj/Dev/veritas-sdk       54d3f14 [fix/sdk-surface-must-fail-not-skip]
C:/Users/elamj/Dev/veritas-session   0297f65 [fix/verify-claim-retraction]
C:/Users/elamj/Dev/veritas-v080      8b638fb [release/v0.8.0-prep]
C:/Users/elamj/Dev/veritas-v081      04ef9a3 [release/v0.8.1-prep]
```

## Per-branch table

| Branch | SHA | A/B | Class | Action |
|--------|-----|-----|-------|--------|
| `origin/fable/survival-records` | `6ce53ae` | +4/-2 | active_product | keep_open_pr_or_confer |
| `origin/docs/cycle1-closeout` | `2cbed44` | +0/-17 | fully_merged | delete_remote_and_local |
| `origin/docs/n0-closeout-plane` | `32d1054` | +0/-23 | fully_merged | delete_remote_and_local |
| `origin/docs/n13-closeout-cycle1` | `622429c` | +0/-18 | fully_merged | delete_remote_and_local |
| `origin/docs/release-080-closeout` | `e5092ca` | +0/-8 | fully_merged | delete_remote_and_local |
| `origin/main` | `1e89e24` | +0/-0 | protected | never_delete |
| `origin/docs/conductor-c1-assign` | `2da6816` | +1/-19 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/conductor-c6-final` | `83bbd7f` | +2/-3 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/conductor-c6-n15-close` | `ce050dd` | +1/-6 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/cycle5-closeout` | `f83d3b1` | +3/-11 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/g9-design-closeout-c6` | `d66404a` | +1/-15 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/n1.3-post-merge-closeout` | `84799c4` | +3/-18 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/n14-closeout` | `3186172` | +1/-13 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/p7c-assign` | `177fa12` | +1/-5 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/post-merge-tip-330bf68` | `599cc1c` | +1/-19 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/steward-post-080-cards` | `90633ad` | +2/-8 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/steward-post-081-free` | `d264b6c` | +3/-5 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/steward-post-45-g9-hygiene` | `1ee5e3d` | +1/-16 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/steward-post-g9-n14-hygiene` | `53f027b` | +1/-14 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/steward-post-n14-cycle5-claim` | `38ad9a5` | +1/-12 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/steward-post-p7c-tip` | `6229eb8` | +1/-1 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/docs/v080-tip-align` | `a0c5904` | +1/-9 | stale_docs_closeout | delete_after_overseer_ack |
| `origin/feat/o.6-retention-410-gone` | `fa02ab6` | +5/-39 | unmerged_product | overseer_review_diff |
| `origin/feat/p7c-refetch-research-slots` | `2db13a0` | +2/-4 | unmerged_product | overseer_review_diff |
| `origin/fix/lock-must-satisfy-declared-bounds` | `2a1eb32` | +4/-22 | unmerged_product | overseer_review_diff |

