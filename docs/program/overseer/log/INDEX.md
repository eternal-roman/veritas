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
| `005-brief.md` | O.8 = green PR **#22**; merge gate; abandon o8 dual WIP; no M7 pre-merge (2026-08-08T17:40Z) |
| `006-brief.md` | **noop_stable** — #22 still green merge gate; main a4cfc49 (2026-08-08T17:50Z) |
| `007-brief.md` | #22 head **db541ce** mcp pin; CI re-green; o8 local 95c4ab4 thrash watch (2026-08-08T18:00Z) — **stale** after #22 merge |
| `008-brief.md` | **O.8 on main** `96b9013`; remote STATE still “in review”; NEXT=M7; claims score cut (2026-08-08T18:11Z) |
| **`../CURRENT.md`** | **Live steering — source of truth for “now”** (steward 18:20Z noop: tip still `96b9013`, remote STATE lag, M7 worktree) |

**Rule:** CURRENT is source of truth for “now.” Logs are audit, not steering.
Do not treat 002–007 as live if CURRENT says otherwise. Prefer local CURRENT over `origin/main` STATE until docs tip-align.

**Count:** 9 brief files + CURRENT. Compact only if log dir exceeds ~20 files.
