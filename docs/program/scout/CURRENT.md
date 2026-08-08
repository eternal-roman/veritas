# Scout CURRENT — 2026-08-08T18:40:00Z

## Method

- Stock: `docs/program/STATE.md` **NEXT = M7** (credits via SIWx); CONFERRAL
  primary bet **M7**; parks honored (N0, dual tracks, seedling vendoring,
  settlement fiction, Docker hash-lock / signed SBOM). O.8 on main
  (`96b9013`). Product PRs: none. Settlements: **0**.
- `gh search repos` `--stars="0..9"` themes: **x402 payment agent**, **mcp x402**,
  **micropayment agent**, **facilitator x402**, plus continuity re-check of
  M7-adjacent prior hits (pacioli, Tollgate). Mid-tick **search API 403
  rate-limit** — further breadth stopped; quality retained via `gh api` + raw
  README spot-checks on retained candidates.
- Cap: multi-query hits; **12** retained after filter (+1 park note).
- Spot-checked: pacioli, CodeRush-2.0, Instant-RAG, fireblocks/x402-agent,
  ipfacts-lab, x402-agent-template, x402-directory, mcp-x402-toolkit, alethe,
  AAVE-MCP-X402, zpay, MetaMask/mcp-x402, mcp-x402-bridge.
- Patterns (≥3): **Double-entry**, **Time-shift**, **Constraint transfer**,
  **Hostile-agent**, **Adjacent possible**, **Inversion**, **Freemium honesty**,
  **Negative space**, **Scale inversion**.
- Convergence: `GUARDIAN.md` + STATE **NEXT = M7**. O.8 demoted from “now
  implement.” No product code this tick.

## Seedling detail (this tick)

### M7 credits / reserve / double-entry (ladder = now)

| Seedling | ★ | License | Claim | Complement | Risk |
|----------|---|---------|-------|------------|------|
| [john-broadway/pacioli](https://github.com/john-broadway/pacioli) | 3 | Apache-2.0 | PLAN · CONSENT · PROVE · UNDO; no debit without credit; governed agent door | **M7** credits ledger language | ERPNext spine; not our stack |
| [theveryholypenguin/CodeRush-2.0](https://github.com/theveryholypenguin/CodeRush-2.0) (Tollgate) | 0 | NOASSERTION (README MIT) | Budget **reservation** before task; multi-provider failover; append-only audit | SpendPolicy / credits reserve-before-work | Hackathon; multi-provider router could tempt dual path |
| [sagaritabd/Instant-RAG---…](https://github.com/sagaritabd/Instant-RAG---Infrastructure-for-Autonomous-Agents) | 0 | none | Deposit USDC with agent memo; auto-deduct on `/query`; multi-tenant billing | Prepaid **credits balance** session framing | “Production-ready” marketing; different chain/memo model; fitness unproven |

### Hostile-agent / one signing seam (culture, not deps)

| Seedling | ★ | License | Claim | Complement | Risk |
|----------|---|---------|-------|------------|------|
| [fireblocks/x402-agent](https://github.com/fireblocks/x402-agent) | 0 | Apache-2.0 | CLI+MCP x402 v2 client; **MPC** sign; verify 402 body vs facilitator `did:web`; EIP-3009 + Permit2 `upto` | Integrity-before-pay; key not in model | Vendor lock-in Fireblocks; not our buyer path |
| [CrankingAI/ipfacts-lab](https://github.com/CrankingAI/ipfacts-lab) | 2 | MIT | Lab: pay for MCP tool in **middleware, never LLM** | Hostile-agent: payment not prompt-driven | Teaching lab only |
| [gustavovalverde/zpay](https://github.com/gustavovalverde/zpay) | 4 | MIT | Facilitator never holds funds/keys; wallet signs under bounded grant; x402 v2 adapter | Separate facilitator architecture → **park as dep** | Different L1 (Zcash); dual money path if adopted |
| [MetaMask/mcp-x402](https://github.com/MetaMask/mcp-x402) | 3 | MIT | MCP tools mint `X-PAYMENT` from local private key | Local Signer-shaped seam observation | Experimental; key on agent host |

### Discovery / single catalog

| Seedling | ★ | License | Claim | Complement | Risk |
|----------|---|---------|-------|------------|------|
| [andreasbjornsund-hub/x402-agent-template](https://github.com/andreasbjornsund-hub/x402-agent-template) | 0 | none | One `ENDPOINT_CATALOG` → well-known + llms.txt; prices/paths cannot drift | Discovery honesty habit | Skeleton; mainnet needs CDP facilitator |
| [shipyard-projects/x402-directory](https://github.com/shipyard-projects/x402-directory) | 0 | none | Agent-maintained x402 app/endpoint directory + liveness | X6-adjacent culture only | Thin README; no fitness |

### Guardrails / freemium / evidence honesty

| Seedling | ★ | License | Claim | Complement | Risk |
|----------|---|---------|-------|------------|------|
| [gameonc/mcp-x402-toolkit](https://github.com/gameonc/mcp-x402-toolkit) | 0 | none | Budgets, velocity, circuit breakers for MCP+x402 | SpendPolicy unit language | Early (v0.1 planned); npm not proven here |
| [bonesdefi/AAVE-MCP-X402](https://github.com/bonesdefi/AAVE-MCP-X402) | 0 | none | Free `/sample` redacted; paid full feed; honest “demo not business” | Freemium + claim discipline | Domain-specific indexer; mainnet showcase ≠ our G9 |
| [ss251/alethe](https://github.com/ss251/alethe) | 0 | MIT | Verdict only after real probes; gasless x402 on Celo | Refuse invent; evidence-first | Hackathon; dual product (judge + pay) |

### Park / reject

| Item | Why |
|------|-----|
| [leo-guinan/mcp-x402-bridge](https://github.com/leo-guinan/mcp-x402-bridge) | Multi-endpoint auto-pay proxy → G3 dual-router temptation; **PARK** |
| Open facilitators / zpay as Veritas facilitator | X1/X3 park; one money path |
| lockvet / package-intel as *M7 implement* | O.8 already on main; checklist only if supply-chain thrash returns |
| Foreign “production settlement / mainnet ready” as our green | G6 / G11 |
| Starting N0 or re-opening O.8 in parallel | STATE = M7; CONFERRAL freeze dual |

## Fit workflow

```
supply (O.8 done)
  → pin/hash habits already on main; park Docker/signed SBOM

discover
  → ENDPOINT_CATALOG → well-known/llms single source
  → directory culture later (X6); not this bet

evaluate
  → alethe: probe before verdict
  → free sample is preview, not authorization

pay / credits (M7 NOW)
  → pacioli double-entry language
  → Instant-RAG prepaid deposit framing
  → Tollgate reserve-before-work
  → fireblocks/ipfacts/zpay: model never signs; Signer seam only

consume → pipeline.run_research only

verify
  → content_hash + custody
  → payment-instruction integrity is foreign shape, not our claim

settle
  → fsync delivery then settle; G9 design only
  → never import foreign mainnet blogs as Veritas green

attest → facts-only; 410≠404
```

## Traits (divergent → convergent)

| Trait | Pattern | Scorecard | Ladder |
|-------|---------|-----------|--------|
| No debit without credit | Double-entry | D, F | **M7** |
| Reserve budget before task | Time-shift | D | SpendPolicy / credits |
| Deposit then auto-deduct | Constraint transfer | D | SIWx session balance |
| Middleware/MPC pays; LLM doesn’t | Hostile-agent | D | Signer seam (done) |
| One catalog → discovery surfaces | Adjacent possible | A | schema / well-known |
| Probe-before-verdict | Inversion | C | unavailable ≠ invent |
| Free sample / paid full | Freemium honesty | F | pricing culture |
| Foreign mainnet marketing | Negative space / reject | — | not our evidence |
| Velocity / circuit breaker units | Scale inversion | D | SpendPolicy, not 2nd path |

## Top 3 to watch (not implement this tick)

1. **M7 credits culture:** pacioli double-entry + Instant-RAG prepaid + Tollgate reserve  
2. **Hostile-agent signing:** fireblocks integrity/MPC + ipfacts middleware-not-LLM  
3. **Discovery single-source:** x402-agent-template `ENDPOINT_CATALOG` (habit, not dep)

## Program ladder

- **Now:** M7 (SIWx credits).  
- **Then:** N0 notary.  
- **Park:** X1/X3/X6, G9, Docker hash-lock / signed SBOM.  
- **Never this tick:** implement seedlings; claim Veritas on-chain success; dual N0.

## PROPERTY block

```
PROPERTY: Scout listed tool-fetched <10★ seedlings with ≥3 named divergent
  patterns, fit workflow, Guardian park/reject; no adoption
EVIDENCE LEVEL: L1 for gh search/api/README this tick; L0 for foreign fitness
CHECKED ARTIFACT: pacioli, Tollgate, Instant-RAG, fireblocks/x402-agent,
  ipfacts-lab, x402-agent-template, x402-directory, mcp-x402-toolkit, alethe,
  AAVE-MCP-X402, zpay, MetaMask/mcp-x402 READMEs + api metadata
ASSUMPTIONS: Search rate-limit truncated further queries; foreign settlement
  claims not re-verified by us
NOT PROVEN: Integration; Veritas on-chain settlement; M7 completion
```
