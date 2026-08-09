# Fable: Refounding — working state

Branch: `fable/refounding` (worktree `C:/Users/elamj/Dev/veritas-fable`, base
`origin/main` @ 458c36a). Owner: Fable session 2026-08-08.

## Mission (from the user, 2026-08-08)

Evaluate all work on Veritas from first principles. Find the issues that were
missed. Find a reliable path to agent-to-agent commerce at platform scale —
"multi-billion dollar platform processing agent-to-agent products and
services" — questioning every existing design choice. Deliverable lives on
this branch. Commit all work here; record insights so the task is resumable
after token exhaustion; do not lose state.

## Status

- [x] Session-start branch `docs/g10-survival-consensus-only` concluded —
      merged as PR #81, now the tip of origin/main (458c36a). Nothing to do.
- [x] Isolated worktree + branch created (this file's commit).
- [x] FAILED, resumable: multi-agent audit workflow `wf_dc7565b5-d86` — all 16
      spawned agents (8 auditors, 5 strategists, 3 judges) died on the Claude
      session usage limit ("resets 8pm America/Chicago") after ~1.09M subagent
      tokens and 267 tool uses. Zero structured results; journal empty. The
      script survives at
      `~/.claude/projects/C--Users-elamj-Dev-veritas-veritas/d4709c79-4844-4e01-8bcb-de49bf4cd96a/workflows/scripts/veritas-refounding-audit-wf_dc7565b5-d86.js`
      — a future session after the limit reset can re-launch it verbatim with
      `Workflow({scriptPath: ...})` (cache is empty, it re-runs fresh).
      THIS session continues inline: no more subagents; synthesis is written
      from the primary docs already read (ROADMAP, STATUS, ECOSYSTEM,
      FABLE_INSIGHTS, FALSIFIABLE_COMMERCE, PRODUCT_ORG, program STATE).
- [ ] Adversarial verification of top findings — pending.
- [ ] First-principles strategy panel (5 lenses) + judging — pending.
- [~] **Phase 0.1 live settlement attempt — protocol path PROVEN, funding
      remains.** From this machine (full egress, unlike the cloud sandbox):
      1. Egress probe: Base Sepolia RPC answers (chainId 0x14a34), x402.org
         facilitator `/supported` 200. Recorded above.
      2. Live run 1: facilitator answered **403** — Cloudflare error 1010 bans
         the default `Python-urllib` user-agent. The client could never have
         settled in production; every test was green. Fixed:
         `veritas/facilitator.py` now sends a versioned User-Agent.
      3. Live run 2: **500** — the reference facilitator routes handlers by
         `x402Version` and registers only **v2** for exact/eip155:84532; the
         whole stack speaks v1. Fixed: v1→v2 wire adapter at the client
         boundary (`_wire_requirements` / `_wire_payment_payload`; v2 renames
         `maxAmountRequired`→`amount`, moves resource/description/mimeType
         into a structured `resource` block, echoes selected requirement as
         `accepted`). Spec: coinbase/x402 specs/x402-specification-v2.md.
      4. Live run 3: verify HTTP 200, `payer` recovered = our buyer address
         `0xF355fc4DF7E7A7016EFE530F71835E3a6e6b8599` — **EIP-712 signing
         path cryptographically confirmed against the real facilitator.**
         Refusal: `invalid_exact_evm_insufficient_balance` (buyer holds 0
         USDC), surfaced to the buyer as a 402, not an outage. Correct.
      5. **DONE — Phase 0.1 acceptance MET, first settlement in project
         history.** Circle faucet funded the buyer (20 testnet USDC,
         permissionless web faucet, no account). Unattended run:
         402 → sign → facilitator verify → research `completed`/billable
         (custody root delivered) → settle → HTTP 200.
         **Tx `0xdad0a00eedeeb606d5e693384f0e6021167287280c765db95570302b41452361`**,
         Base Sepolia block 45234918, status success, USDC Transfer of
         10000 atomic ($0.01, the exact request price) from buyer
         `0xF355…8599` to pay-to `0xbbeE…9364`. Independently confirmed by
         `eth_getTransactionReceipt` against the public RPC.
      6. **G9 reconcile ran against a real chain for the first time** and
         found its own defect on the way: `chain_reconcile.py` also sent no
         User-Agent (same Cloudflare-ban class as the facilitator client) —
         `rpc_transport_error:HTTPError` on an endpoint curl could reach.
         Fixed; re-run: `chain_checked: true, counts: {confirmed: 1}` — the
         ledger's settlement record matches the chain.
      Payment-path test subset: 87 passed with the adapter; 17
      chain_reconcile/facilitator tests passed after the UA fix. Evidence in
      `docs/program/fable/settlement/`: the three failed-run reports (403 UA
      ban, 500 v1-routing, insufficient-balance refusal), the successful run
      `settlement_20260809T011519Z.json`, the custody receipt, the on-chain
      tx receipt (`onchain_tx_receipt.json`), and the confirmed reconcile
      (`chain_reconcile_confirmed.json`). Throwaway testnet keys in session
      scratchpad `testnet_keys.json` — testnet only, no real value ever.
- [ ] Synthesis: `docs/program/fable/REFOUNDING.md` — pending.
- [ ] PR opened — pending.

## Resume protocol

If this session dies: read this file, then `AUDIT.md` / `REFOUNDING.md` in
this directory for whatever landed before death. The workflow journal (if the
session dir survives) is at the Workflow run's transcriptDir. Re-run remaining
phases rather than trusting partial synthesis. The shared checkout at
`C:/Users/elamj/Dev/veritas` belongs to concurrent agents — never work there.

## Insights captured so far

- The program's docs-branch cadence is high-frequency: three checkout switches
  observed in minutes (`docs/conductor-c8-final` → `docs/steward-post-81-free`),
  PRs #74–#82 all merged within ~40 minutes on 2026-08-08. Evaluation of the
  program layer must ask whether this churn ships product value or ceremony.

Interim synthesis (mine, pre-workflow; test against audit results before
promoting to REFOUNDING.md):

1. **The wrapper is the product.** The trust machinery — receipts, custody,
   warranties (falsifiable commerce), survival records, standing, diligence,
   constitution-with-enforcement — is the novel asset. The good it wraps
   (snippet-grade research) is admittedly uncompetitive (ROADMAP known-issue
   #2). The program keeps polishing the seller; the platform play is the
   substrate any seller embeds.
2. **Verification-blocked vs demand-blocked.** The program acts as if trust is
   the barrier to agent commerce; the actual near-term barrier is contact:
   nothing deployed, nothing discoverable, 0 settlements, 0 evidence of
   demand. The trust layer solves the scaling problem of a market that does
   not yet locally exist.
3. **Governance consumes the program.** Roughly 7 governance roles per builder
   (conductor/steward/overseer/scout/pruner/optimizer/git-agent/architect);
   recent PR mix is dominated by docs/program churn at 8–25-minute tick
   cadences. The org's fitness function rewards tick completion, not market
   contact. (Quantify from git log before asserting in the deliverable.)
4. **The human-ops list is THE bottleneck and it is being routed around.**
   PyPI name, funded testnet wallet, TLS host, registry listing, RPC egress —
   each marked "human ops" and deferred indefinitely while more self-auditable
   code accretes. The refounding must put a short, concrete unblock list in
   front of the user.
5. **Environment hypothesis:** the "no egress" constraint was the cloud
   sandbox's, not necessarily this Windows machine's. If this machine reaches
   a facilitator + Base Sepolia RPC, Phase 0.1 (first settled payment ever)
   may be executable here with faucet funds. Probe before claiming.
