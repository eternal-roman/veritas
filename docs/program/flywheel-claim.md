# flywheel-claim

- **bet_id:** phase-0.1-R
- **branch:** (pending — flywheel/implement)
- **holder:** agent-commerce-flywheel
- **status:** building
- **updated:** 2026-08-09T02:55:00Z
- **last_merged:** product **#119** @ `fb3b0d5` (unblock defaults + n=2 settle artifacts); docs #118 @ `bc0bba3` MIND; plane #117 @ `a3a52c3`; docs #116 @ `42a4378`; docs #115 @ `270fb42`; docs #114 @ `efd5dfd`; product **#112** @ `367a3aa` first testnet settle; plane #111 @ `4aa6c61`
- **settlements:** **2 testnet** self-dogfood on tip · mainnet **0** · unsolicited **0**
- **next_micro:** **Phase 0.1-R — routine money loop** (Overseer-named singular; claim held). Scope: agent-clearable settle → chain reconcile (testnet defaults ok); pin tests so defaults/UA cannot regress; exit-honest evidence; mainnet never defaulted. Non-goals: mainnet, PyPI, TLS, M7, N0, dual product. Do not dual-kick second continuous.

When a flywheel/conductor cycle is building, set `status: building` and holder.
Clear to `free` after merge or abandon. See `AUTONOMOUS.md` and GUARDIAN G10.

## Landed (do not re-claim)
| Bet | SHA / PR |
|-----|----------|
| **Unblock defaults + settlement n=2 + default-path G9 reconcile** | **`fb3b0d5` / #119** — testnet-only public RPC defaults; self-dogfood n=2; not mainnet; not unsolicited |
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

**G10:** Claim **building** `phase-0.1-R`. Open product PRs: **none** yet. Settlements: testnet **2** (self-dogfood); unsolicited **0**; mainnet **0**. Not on PyPI. #119 narrow truth — env-unset ≠ block on testnet defaults; not platform scale.
