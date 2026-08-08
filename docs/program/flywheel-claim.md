# flywheel-claim

- **bet_id:** (none)
- **branch:** (none)
- **holder:** (none)
- **status:** free
- **updated:** 2026-08-08T20:40:00Z
- **last_merged:** cycle-1 #44 @ `2cbed44`; N1.3 #41 @ `622429c`; docs #39 @ `330bf68`; P7 #38 @ `4697c8d`; N1.2 #34 @ `32d1054`; N1.1 #33 @ `db04ae2`; N0 @ `4cd2d0c`
- **next_micro:** Overseer names single NEXT (G9 design | Merkle anchors | other). Do not dual-reopen cycle-1/N1.3/P7/N0/N1.1/N1.2/M7. Settlements 0.

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

**G10:** Claim **free** after cycle-1 merge. Open product PRs: **none**. Settlements: **0**.
