# Scout CURRENT — 2026-08-08T17:08:56Z

## Method

- `gh search repos` `--stars="0..9"`, themes rotated: **x402**, **agent payment**,
  **facilitator × x402**, **EIP-3009**, **spend/payment policy**, **attestation**,
  **MCP × payment**, **settlement**, **SBOM/lockfile**, **hash-chain/custody**.
- Cap: multi-query hits; **12** retained after filter (noise, marketing shells,
  self-as-trust, unrelated “settlement” senses dropped).
- Spot-checked via `gh api` + README raw for lockvet, agent-audit-chain,
  TrustBench, Rul1an/assay, kahea.
- Patterns (≥3): **Hostile-agent**, **Constraint transfer**, **Time-shift**,
  **Inversion**, **Adjacent possible**, **Combinatorial mash**, **Negative space**,
  **Scale inversion**.
- Convergence: `GUARDIAN.md` + `STATE.md` **NEXT ACTION = O.8**. Main tip context
  from steward stamp: diligence/P7/O.6 on main; **O.8** still the bet. Zero
  proven Veritas on-chain settlements. No product implementation this tick.

## Seedling detail (this tick)

### O.8 supply chain (ladder = now)

| Seedling | ★ | License | Claim | Complement | Risk |
|----------|---|---------|-------|------------|------|
| [matteo-sung/lockvet](https://github.com/matteo-sung/lockvet) | 0 | MIT | Gate/explain lockfile changes: OSV, typosquats, integrity, Actions/Docker/K8s/SBOM formats | **Direct O.8 pattern**: produce lockfile+hashes, then vet diffs before merge | Go CLI; fitness unproven as our CI step |
| [shiftleftcyber/sbom-signing-best-practices](https://github.com/shiftleftcyber/sbom-signing-best-practices) | 5 | Apache-2.0 | Canonical SBOM hashes CycloneDX/SPDX | Produce-then-verify SBOM | Continuity |
| [oorabona/docker-containers](https://github.com/oorabona/docker-containers) | 5 | MIT | SBOM + Sigstore + Trivy on hardened images | O.7/O.8 image honesty | Their images ≠ ours |
| [houdini91/firmware-sbom-supplychain](https://github.com/houdini91/firmware-sbom-supplychain) | 0 | MIT | generate → attest → OPA gate (cosign lane) | Attest-then-gate pipeline shape | Firmware demo |
| [OtowoSamuel/model-supply-chain](https://github.com/OtowoSamuel/model-supply-chain) | 0 | MIT | Cosign + SBOM + SLSA + policy gates | Same produce-attest-gate ladder | MLOps framing |
| [pfenerty/ocidex](https://github.com/pfenerty/ocidex) | 1 | MIT | CycloneDX inventory + release changelog | Post-O.8 inventory of what we shipped | Optional ops |

### Custody / audit honesty (G10, N1 language)

| Seedling | ★ | License | Claim | Complement | Risk |
|----------|---|---------|-------|------------|------|
| [SeansGravy/agent-audit-chain](https://github.com/SeansGravy/agent-audit-chain) | 0 | Apache-2.0 | Hash chains catch **0/5** threats vs attacker who **recomputes** hashes; **external witness** closes all five | **Constraint transfer to custody**: self-held chain alone is not tamper-proof; witness/anchor needed for real dispute | Measurement paper-repo; not a dep |
| [Rul1an/assay](https://github.com/Rul1an/assay) | 9 | MIT | MCP tool-call gate; deny risky calls; **recomputable evidence**; bounded claims; offline replay | Honesty taxonomy for tool actions; “what stays unproven” language | At 9★ near cap; not payment settle layer |
| [MSKazemi/novafabric](https://github.com/MSKazemi/novafabric) | 2 | Apache-2.0 | Signed evidence capsules for agent runs; self-hosted | N0/N1 portable evidence framing | Heavy scope |
| [huguryildiz/research-graph](https://github.com/huguryildiz/research-graph) | 0 | MIT | Provenance hash walk; reviewer ≠ producer | Cycle-5 / non-circular verify culture | Continuity |
| [milonpatowary/double-entry-ledger](https://github.com/milonpatowary/double-entry-ledger) | 1 | MIT | Append-only, balanced-by-construction, reconcilable | M/ledger culture (we already have SQLite ledger) | Node/Mongo — park as dep |

### Pay / settle / G9-adjacent

| Seedling | ★ | License | Claim | Complement | Risk |
|----------|---|---------|-------|------------|------|
| [lithvall/TrustBench](https://github.com/lithvall/TrustBench) | 0 | none | Verify x402 **on-chain**; signed receipts; spend caps; **fail-safe paywall** (no charge if merchant non-conformant) | G9 + our non-billable failure honesty; buyer-side route | License none; multi-network registry scores (G10-adjacent if used as auth) |
| [nickthelegend/outcome](https://github.com/nickthelegend/outcome) | 0 | none | Facilitator can report success while only one path pays | G9 dual-facilitator honesty | Continuity |
| [mimisco-git/Assay](https://github.com/mimisco-git/Assay) | 0 | none | Settlement guarantee / verified-or-refunded | `owed` / indeterminate framing | Distinct from Rul1an/assay |
| [4KInc/circle-prize-submission](https://github.com/4KInc/circle-prize-submission) (Verigate) | 0 | none | Policy-bound authorize receipts | SpendPolicy culture | Unlicensed prize |
| [ETH402/facilitator](https://github.com/ETH402/facilitator) | 0 | Apache-2.0 | Open x402 v2 facilitator (ETH mainnet USDC) | Facilitator market signal | Park; we don’t run dual money path |
| [Vellar-Wallet/vellar-facilitator](https://github.com/Vellar-Wallet/vellar-facilitator) | 0 | Apache-2.0 | Stellar facilitator + **Bazaar discovery** | X6 discovery culture | Non-Base rail |
| [JustaName-id/agentic-payments-cheatsheet](https://github.com/JustaName-id/agentic-payments-cheatsheet) | 1 | MIT | Field guide: x402, facilitators, EIP-3009, CAIP-2, AP2 | Human/peer education only | Not code to integrate |

### Evaluate / agent-call safety

| Seedling | ★ | License | Claim | Complement | Risk |
|----------|---|---------|-------|------------|------|
| [copyleftdev/kahea](https://github.com/copyleftdev/kahea) | 0 | Apache-2.0 | Sealed OpenAPI plans; grant → invoke → evidence MCP tools | Hostile agent: exact calls before money/data leave | Not our product surface |
| [Nikolife2016/pulsefeed-x402](https://github.com/Nikolife2016/pulsefeed-x402) | 0 | none | Verify endpoint before pay | Evaluate stage | Prior README gap |
| [Sigil-Core/ove](https://github.com/Sigil-Core/ove) | 0 | MIT | Intent attestation before capital moves | Authorize-before-move culture | Boilerplate |

### Reject / park hard

| Item | Why |
|------|-----|
| [wyattpalm2-eng/x402-seller](https://github.com/wyattpalm2-eng/x402-seller) | Explicit **self-graded track record** — G10 reject as trust-as-auth |
| TrustBench rankings as authorization | Score ≠ authority; methodology ok, use as input only |
| m402 / ZK-SSL seedlings | Do not claim ZK without L1 on our tree |
| Dual facilitator / multi-chain policy fork | G3 one payer |
| Skipping O.8 for facilitator toys | STATE = O.8 |

## Fit workflow

```
supply (O.8 NOW)
  → lockfile with hashes + SHA-pinned actions + SBOM
  → lockvet-class gate on lockfile diffs; cosign/Sigstore/SBOM verify-after-produce

discover
  → well-known; Vellar/Bazaar language only when X6 unblocked

evaluate
  → pulsefeed/kahea: inspect before call; sealed plans
  → TrustBench-style endpoint hygiene (idea); never trust self-scores

pay
  → veritas.payer + Signer + SpendPolicy ONLY
  → Verigate/ove: policy/intent before move
  → fail-safe: non-billable on our failure / non-conformant work (G4)

consume
  → pipeline.run_research one engine
  → free MCP stays free; Rul1an/assay = tool-call evidence culture for G.1 later

verify
  → content_hash + custody client; research-graph exit-code shape
  → agent-audit-chain: hash chain alone insufficient without external witness

settle
  → delivery fsync before settle; ledger records
  → Outcome/TrustBench: facilitator-OK ≠ chain-OK (G9 needs RPC)

attest
  → facts-only receipts; novafabric capsule language → N1 after ladder
  → 410 ≠ 404 for pruned receipts
```

## Traits (divergent → convergent)

| Trait | Pattern | Scorecard | Ladder |
|-------|---------|-----------|--------|
| Vet lockfile diff before merge | Time-shift | F | **O.8** |
| Hash chain fails vs recompute attacker | Hostile-agent + Constraint transfer | F, C | custody / G10 / N1 witness |
| Fail-safe: no charge if merchant broken | Inversion | C, D | G4 billable:false culture |
| On-chain re-verify receipt | Adjacent possible | C | **G9** (RPC blocked) |
| MCP tool evidence: observed vs unproven | Combinatorial mash | F | free MCP honesty; G.1 later |
| Intent attestation before capital | Scale inversion | D | SpendPolicy (done) + M7 |
| Self-graded seller track record | Negative space / reject | — | G10 |
| Facilitator open-source flood | Negative space | park | X1/X3 need egress |

## Top 3 to watch (not implement this tick)

1. **lockvet + SBOM/Sigstore habits** for shipping **O.8**  
2. **agent-audit-chain finding** (witness required) for custody honesty docs/N1  
3. **TrustBench fail-safe + on-chain verify** language for G9 when RPC exists  

## Program ladder

- **Now:** O.8 supply chain (STATE). Diligence/P7/O.6 already on main — do not re-open.  
- **Then:** M7 credits (SIWx).  
- **Then:** Phase N0 notary.  
- **Park:** X1/X3/X6, G9 (egress/RPC).  
- **Never this tick:** implement seedlings; dual payer; settlement-success claims.

## PROPERTY block

```
PROPERTY: Scout listed tool-fetched <10★ complementary seedlings with ≥3 named
  divergent patterns, fit workflow, and Guardian-aligned park/reject; no adoption
EVIDENCE LEVEL: L1 for gh search/api/README this tick; L0 for foreign fitness
CHECKED ARTIFACT: gh search stars 0..9; gh api; READMEs lockvet, agent-audit-chain,
  TrustBench, Rul1an/assay, kahea
ASSUMPTIONS: GitHub recency ≠ quality; unlicensed repos may be unusable as deps
NOT PROVEN: Integration; Veritas on-chain settlement; O.8 completion
```
