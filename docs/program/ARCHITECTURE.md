# Architecture living map — money & trust substrate

**Owner:** Architect (plane role). **Stock tip:** `origin/main` @ `c6dc73f` (#121 claim hygiene; product under `fb3b0d5` #119).
**Last updated:** 2026-08-09T03:12:00Z · **Active bet:** Phase **0.1-R** (routine money loop) · branch `feat/phase-0.1-R-routine-money-loop` (no PR yet).

This is the **seam map** builders must obey. It is not a product claim. Every
row is L1 on the tip unless marked L0.

## Guardian non-negotiables (do not dual)

| Seam | Single owner | Forbidden second path |
|------|--------------|------------------------|
| Research | `veritas.pipeline.run_research` | Parallel retrieval/Bayes/custody |
| Buyer pay | `veritas.payer` + `Signer` | Sign outside gate; dual payer |
| Seller money order | verify → claim nonce → work → fsync delivery → settle | Bill before work; bill `unavailable` |
| Chain check (G9) | `veritas.chain_reconcile` **report only** | Mutating ledger from RPC; inventing revenue |
| x402 wire v1→v2 | `FacilitatorClient` (`_wire_requirements` / `_wire_payment_payload`) | Second translation site; piecemeal internal v2 |
| Version / UA | `veritas.__version__` | Default `Python-urllib` on money-path HTTP |

## Money-path surfaces (tip product base `fb3b0d5` / claim tip `c6dc73f`)

```
Buyer harness                 Seller service                    Ops / G9
─────────────────             ────────────────                  ────────
scripts/testnet_settlement.py  POST /v1/research (402→work)     veritas-ops reconcile-chain
  └─ pay_via_policy            └─ ledger claim/delivery/settle    └─ reconcile_settlements_auto
       └─ veritas.payer             └─ FacilitatorClient settle         └─ resolve_rpc_url
            └─ Signer                     (v1 internal / v2 wire)            env wins
                                                                              else testnet DEFAULT_PUBLIC_RPC_URLS
                                                                              mainnet never defaulted
```

**Landed proof (self-dogfood, not demand):** settlements **2 testnet**, both
default-path `chain_checked` with env unset — artifacts under
`docs/program/fable/settlement/`. Mainnet **0**. Unsolicited **0**.

**G9 status:** design surface + defaults shipped; gap **remains open** until
reconcile is *production-routine* (constitution). Do not retire the witness
or claim G9 closed in 0.1-R.

## Phase 0.1-R — architecture constraints (binding on builder)

**Goal:** one agent-clearable **settle → chain reconcile** cycle that records
exit-honest evidence and pins defaults/UA so they cannot silently regress.

**Gap vs tip:** settle harness and default reconcile exist as **separate**
steps; no single orchestrated path + combined evidence artifact yet. Branch
`feat/phase-0.1-R-routine-money-loop` is at tip with **zero product delta**.

### Must

1. **Compose, do not fork.** Orchestrate existing settle harness +
   `reconcile_settlements_auto` / `veritas-ops reconcile-chain`. No second
   payer, facilitator client, or RPC stack.
2. **One evidence artifact** per run: settlement acceptance + tx (if any) +
   reconcile rows with `chain_checked` and per-row `rpc_source`.
3. **Exit honesty:** funded confirmed settle ≠ unfunded honest refusal ≠
   transport failure. Never map RPC outage or missing funds to green acceptance.
4. **RPC policy unchanged:** `resolve_rpc_url` — env wins; only
   `eip155:84532` (and future *testnet* pins) may default; **mainnet always
   requires `VERITAS_RPC_URL`**. Pin with tests.
5. **User-Agent load-bearing** on every money-path HTTP client (facilitator,
   chain RPC, any new probe). Pattern already in `tests/test_payment.py` /
   chain_reconcile transport.
6. **Injectable transport** for all new reconcile-adjacent tests — no live
   sockets in CI.
7. **Ledger identity:** reconcile against the **same** runtime ledger the
   live server used for settle (`VERITAS_RUNTIME_DIR` documented in the
   evidence JSON). Empty reconcile because wrong dir is a fail, not green.
8. **Docs in the same PR only as needed:** recipe pointer + G9 still-open;
   no mainnet/unsolicited/revenue claims; no dual restock cascade.

### Must not

- Close constitution G9 / delete `test_known_gap_*` witness
- Default mainnet RPC or mainnet pay-to
- Dual bet: M7 credits, N0, second pipeline, PyPI publish, TLS host
- Rewrite ledger from reconcile
- Soft-fail CI or simulated-tx sold as Phase 0.1-R proof
- Open a second continuous / second product PR
- Dual-claim another bet while this branch holds G10

### Preferred shape (smallest)

| Layer | Prefer | Avoid |
|-------|--------|--------|
| Entrypoint | Extend `scripts/testnet_settlement.py` **or** thin `python -m veritas.money_loop` that imports settle helpers + `reconcile_settlements_auto` | New payment client; shell-only glue without tests |
| Ledger path | Server runtime dir used for the settle run | Silent empty reconcile against wrong dir |
| Tests | Offline: default RPC source stamp, mainnet unconfigured, UA header present, orchestrator exit codes with fixtures | Live faucet in CI |
| Honesty text | Align `G9_NOTE` / module docs with **testnet defaults + mainnet explicit** (post-#119 truth) | Claiming gap closed |

### Acceptance (L1 for merge)

- Scripted cycle documents non-simulated tx **when funded** (manual/live
  dogfood optional evidence; not required green in CI)
- Reconcile path reports `chain_checked` with `rpc_source` stamped under
  default testnet resolution (unit/integration with injectable transport)
- Mainnet never appears in `DEFAULT_PUBLIC_RPC_URLS`
- Battery: pytest + ruff + bandit + payment_model green
- PROPERTY block: not mainnet, not unsolicited, G9 still open for production-routine

## Seams for later bets (parked — do not invent now)

| Bet | Architectural note when unblocked |
|-----|-----------------------------------|
| M7 credits | **Ledger adapter** on existing claim/delivery/settlement; debit-before-work + idempotent refund already in server — not a second `payer` |
| N0 notary | Retrieval quality / pack path; still one `run_research` |
| Full x402 v2 | Migrate end-to-end or not at all; single translation site until then |
| Multi-instance | Shared ledger/nonce store — out of 0.1-R |

## Doc lag to absorb in product PR (not dual hygiene)

- `docs/program/G9_CHAIN_RECONCILE.md` may still read as if unset env always means
  `rpc_not_configured` — supersede with `resolve_rpc_url` truth from #119
- `G9_NOTE` string partially pre-defaults; `reconcile_settlements_auto` limitation
  text is the post-#119 truth — align the note
- Support cards (Conductor/Overseer CURRENT) may lag tip `c6dc73f` — in-place only

```
PROPERTY: living seam map tip c6dc73f; 0.1-R = compose settle+reconcile, one payer/engine, mainnet never defaulted, G9 report-only; product branch empty of code
EVIDENCE LEVEL: L1 for landed surfaces; L0 for 0.1-R until PR ships
CHECKED ARTIFACT: veritas/chain_reconcile.py; scripts/testnet_settlement.py; branch feat/phase-0.1-R-routine-money-loop @ c6dc73f zero delta
ASSUMPTIONS: claim held by flywheel; n=2 is self-dogfood
NOT PROVEN: 0.1-R shipped; production-routine G9; mainnet; unsolicited buyers
```
