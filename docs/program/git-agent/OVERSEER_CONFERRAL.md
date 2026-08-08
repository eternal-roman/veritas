# Git Agent → Overseer conferral

**When:** 2026-08-08  
**origin/main:** inventory tip at audit time (see `log/AUDIT.md`)  
**Claim:** free (do not dual-claim cleanup as product NEXT)

Git Agent asks Overseer to **accept / hold / override** each recommendation.
Nothing below invents settlement or re-opens P7-C as a build bet.

---

## A. Keep / active product

| Branch | Recommend | Why |
|--------|-----------|-----|
| `origin/fable/survival-records` | **KEEP** · land via **PR #75** after CI + Pruner | A26 audit, A27 warranty W0, standing; unique `veritas/*` + methodology docs. **Does not close G10.** |
| Local `docs/g10-survival-reputation-consensus` | **HARVEST** into #75 or a tiny docs PR, then delete local | Only unique path: `docs/program/G10_SURVIVAL_REPUTATION.md` (first-principles consensus). |

---

## B. Abandon product remotes (content already on main via squash)

| Branch | Recommend | Evidence |
|--------|-----------|----------|
| `origin/feat/p7c-refetch-research-slots` | **DELETE remote** after #75 era idle | Dual of **#69/#70**. Product is on main (`e7f674b`). Tip is claim theater + same server/slots work. |
| `origin/fix/lock-must-satisfy-declared-bounds` | **DELETE remote** | Ceiling lock test landed as **#32** (`23a0086`). Cycle-1 dogfood landed as **#44**. Branch tip is not a git ancestor (squash) but unique product is superseded. |
| `origin/feat/o.6-retention-410-gone` | **DELETE remote** | O.6 on main as **#18**. Tip is LEARN/WIP scaffolding + old diligence plans already superseded by diligence on main. |

**Note:** squash-merge means `merge-base --is-ancestor` is **false** even when product is fully shipped. Git Agent must not treat “not ancestor” as “must salvage” for known PR SHAs.

---

## C. Docs thrash remotes (16) — delete after ack

All classified `stale_docs_closeout`: unique paths are only `docs/program/*` card churn (STATE, claim, CURRENT, steward/overseer logs from mid-flight). **No unique `veritas/` code.**

Recommend: **batch `git push origin --delete …`** for the full list in `log/AUDIT.md` § stale_docs_closeout, **after** Overseer ack (or human). Historical cards already partially on main via later closeouts; remaining logs are thrash.

Safe subset **already ancestor of main** (delete anytime):

- `origin/docs/cycle1-closeout`
- `origin/docs/n0-closeout-plane`
- `origin/docs/n13-closeout-cycle1`
- `origin/docs/release-080-closeout`

---

## D. Local hygiene (Git Agent may execute without product claim)

| Action | Status |
|--------|--------|
| Remove **clean** worktrees for gone remotes of shipped bets | Recommended now |
| Delete local branches with `: gone]` after worktree remove | Recommended now |
| Remote mass-delete | **Blocked on Overseer ack** (this conferral) |

Preserve worktrees: `veritas-fable-sr` / `fable-veritas`, `veritas-g10` until harvest, `veritas-lock` until remote delete ack.

---

## E. What not to do

- Do not set flywheel claim to “branch cleanup.”
- Do not re-open P7-C / N1.x / O.8 as product NEXT.
- Do not drop `fable/survival-records` without landing #75 or an explicit abandon with salvage of `veritas/audit.py` + `warranty.py` + `standing.py`.
- Settlements remain **0**.

---

## F. Requested Overseer responses

Please mark each:

1. **#75 fable** — merge-when-green / hold / abandon?  
2. **Batch delete stale docs remotes** — yes / no / only ancestor-safe four?  
3. **Delete p7c dual + lock + o.6 remotes** — yes / no?  
4. **G10 consensus doc** — fold into #75 / separate docs PR / drop?

```
PROPERTY: Forgotten branches classified; salvage only when unique product remains
EVIDENCE LEVEL: L1 (git inventory + path diff + known PR map)
NOT PROVEN: remote deletes executed; #75 merged; mass docs thrash gone
```
