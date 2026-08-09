# flywheel-claim

- **bet_id:** (none)
- **branch:** (none)
- **holder:** (none)
- **status:** free
- **updated:** 2026-08-09T03:20:00Z
- **last_merged:** product **#122** @ `0c2cef9` (Phase 0.1-R routine money_loop); docs #121 @ `c6dc73f`; product **#119** @ `fb3b0d5` unblock defaults + n=2; docs #118 @ `bc0bba3` MIND; plane #117 @ `a3a52c3`; product **#112** @ `367a3aa` first testnet settle; plane #111 @ `4aa6c61`
- **settlements:** **2 testnet** self-dogfood on tip · mainnet **0** · unsolicited **0**
- **next_micro:** Claim **free**. **#122** landed (compose settle→reconcile + L1 offline pins). Do **not** re-claim 0.1-R / invent n=3 from merge. Await Overseer LEARN singular. Parked: PyPI/TLS/mainnet human ops. No dual M7/N0/#112 thrash.

When a flywheel/conductor cycle is building, set `status: building` and holder.
Clear to `free` after merge or abandon. See `AUTONOMOUS.md` and GUARDIAN G10.

## Landed (do not re-claim)
| Bet | SHA / PR |
|-----|----------|
| **Phase 0.1-R routine money loop** | **`0c2cef9` / #122** — `veritas.money_loop` + tests; compose existing payer+reconcile; not mainnet; not unsolicited; G9 production-routine still open |
| Steward tip-epoch post-#119 hygiene | `c6dc73f` / #121 |
| **Unblock defaults + settlement n=2 + default-path G9 reconcile** | **`fb3b0d5` / #119** — testnet-only public RPC defaults; self-dogfood n=2 |
| MIND.md shared operating core / unblock ladder | `bc0bba3` / #118 |
| Visa binary secret strip fix (CI flaky) | `a3a52c3` / #117 |
| Field notes first settlement lessons | `270fb42` / #115 |
| Tip-true post-#112 settle honesty | `42a4378` / #116 |
| Pruner comprehensive sweep | `efd5dfd` / #114 |
| **First on-chain settlement (testnet) + refounding** | **`367a3aa` / #112** |
| Org loops v4 stock protocol | `4aa6c61` / #111 |
| **Plane org loops v3 / Researcher / limited VAAT economy** | **`4d15033` / #106** |
| Workflow hygiene idle-true / Unblock-only | `b66901f` / #105 |
| **Ecosystem advance / VAAT / plane visas** | **`9359b79` / #98** |
| **A26/A27** survival / warranty W0 / standing | **`ab728a6` / #75** |
| **N0 residue** fail-closed pack/log | **`1c56a0b` / #77** |
| **Git Agent** | **`e78a7a9` / #76** |
| **P7-C** re-fetch research_slots | **`e7f674b` / #69** |
| **v0.8.1** / N1.5 / v0.8.0 / prior ladder | through tags `v0.8.1` / `v0.8.0` |

**G10:** Claim **free**. Open product PRs: **none**. Settlements: testnet **2** (self-dogfood); unsolicited **0**; mainnet **0**. Not on PyPI. #122 ships the routine compose path — does **not** invent extra on-chain settlements or close production G9.
