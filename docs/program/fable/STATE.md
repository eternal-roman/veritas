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
