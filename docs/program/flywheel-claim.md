# flywheel-claim

- **bet_id:** N1.4
- **branch:** feat/n1.4-merkle-evidence-log
- **holder:** flywheel-session
- **status:** building
- **updated:** 2026-08-08T20:58:00Z
- **last_merged:** docs #48 @ `b77339f`; G9-design #46 @ `6777a92`; cycle-1 #44 @ `2cbed44`
- **next_micro:** Land N1.4 Merkle evidence log. Fix empty-proof 400 (not 404). No dual. Settlements **0**.

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
| **N1.3 portable EvidencePack** | **`622429c` / #41** |
| **cycle-1 cold install dogfood** | **`2cbed44` / #44** |
| cycle-1 closeout docs | `df1cc8f` / #45 |
| **G9-design fail-closed reconcile** | **`6777a92` / #46** |
| G9-design closeout docs | `b77339f` / #48 |

**G10:** Claim **building N1.4**. Settlements: **0**. Gap G9 still open.
