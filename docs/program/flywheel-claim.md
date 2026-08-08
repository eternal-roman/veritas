# flywheel-claim

- **bet_id:** N1.4
- **branch:** feat/n1.4-merkle-evidence-log
- **holder:** flywheel
- **status:** building
- **updated:** 2026-08-08T20:58:00Z
- **last_merged:** docs #48 @ `b77339f`; G9-design #46 @ `6777a92`; docs #45 @ `df1cc8f`; cycle-1 #44 @ `2cbed44`; N1.3 #41 @ `622429c`; P7 #38 @ `4697c8d`
- **next_micro:** #49 only — rebase onto `b77339f` (CONFLICTING), fix Tests failure, G13 before green merge. Operator-local Merkle evidence log. Settlements **0**. Gap G9 still open.

When a flywheel/conductor cycle is building, set `status: building` and holder.
Clear to `free` after merge or abandon. See `AUTONOMOUS.md` and GUARDIAN G10.

## Landed (do not re-claim)
| Bet | SHA / PR |
|-----|----------|
| M7 credits/SIWx | `2171bfa` / #23 |
| inv-3 credit refund | `386efff` / #28 |
| O.8 / O.8b | `96b9013` / #22 · `5d6492f` / #24 |
| **N0 notary core** | **`4cd2d0c` / #30** |
| **N1.1 EIP-191 attestation** | **`db04ae2` / #33** |
| **N1.2 free attestation verify** | **`32d1054` / #34** |
| **P7 origin re-fetch verify** | **`4697c8d` / #38** |
| P7 post-merge plane closeout | `330bf68` / #39 |
| **N1.3 portable EvidencePack** | **`622429c` / #41** |
| **cycle-1 cold install dogfood** | **`2cbed44` / #44** |
| cycle-1 closeout docs | `df1cc8f` / #45 |
| **G9-design fail-closed reconcile** | **`6777a92` / #46** |
| G9-design plane closeout | `b77339f` / #48 |

**G10:** Claim **building** N1.4 on `feat/n1.4-merkle-evidence-log` (#49). Open product PRs: **#49 only**. Docs #50 is closeout thrash vs tip `#48` — do not dual product. Settlements: **0**. Gap G9 **still open**.
