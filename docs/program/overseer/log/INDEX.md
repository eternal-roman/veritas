# Overseer log index

Maintained by Steward. Full history may exist only in session working trees;
main may carry a subset.

| File | Note |
|------|------|
| `000-seed.md` | Bootstrap |
| `001-brief.md` | Early tick |
| `002-brief.md` | Early tick (pre-O.6 merge era — **stale** for live steering) |
| `003-brief.md` | Post-merge; O.8 not started that tick |
| `004-brief.md` | O.8 real WIP + dual worktree thrash; PR #21 docs (2026-08-08T17:18Z) |
| **`../CURRENT.md`** | **Live steering — source of truth for “now”** |

**Rule:** CURRENT is source of truth for “now.” Logs are audit, not steering.
Do not treat 002-brief as live if CURRENT says otherwise.

**Count:** 5 brief files + CURRENT. Compact only if log dir exceeds ~20 files.
