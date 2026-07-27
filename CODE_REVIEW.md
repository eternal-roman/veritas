# Veritas Code Review (Integrated State)

## Architecture

| Layer | Modules | Assessment |
|-------|---------|------------|
| Epistemic core | custody, hashing, bayesian, schema, pipeline | Solid, consistent, evidence-first |
| Networks / payment | networks, payment_config, app gate | CAIP-2 complete; live/free switch clean |
| Agent-native | zero_key_retrieval, bootstrap, control_plane, local_facilitator, self_calibrator | Good separation; free path works |
| Transmission | jit_packet, zk_wallet | JDP + commitment privacy implemented; prototype quality |
| API / discovery | app/main.py, identity, trust | Adequate for distribution; full official x402 middleware still recommended for production |
| Evaluation | evaluations/harness | Structural tests present; not large-scale quality proof |

## Strengths

1. Clear separation between free (zero-key, human_required=false) and live modes.
2. Custody + content hashing are enforced end-to-end.
3. CAIP-2 multi-network support is present and normalized.
4. JIT Disposable Packet + ZK wallet commitment give a real zero-setup, private-offer path.
5. Documentation (WORKFLOW, ANALYSIS, LIVE_PAYMENTS, JIT_PACKET, ZK_WALLET) is honest about limits.

## Issues found and addressed in this pass

- README was stale; updated to current architecture.
- STATUS and integration docs aligned with actual modules.
- ZK wallet and JIT packet exist as sibling modules; integration helper documented.
- Hashing alias (`content_hash` / `compute_content_hash`) kept for compatibility.

## Remaining gaps (not bugs — product limits)

1. **No public deployment** — agents cannot call a live instance until one is hosted.
2. **Live settlement unproven with real funds** — code path ready; needs real wallet + facilitator credentials.
3. **Zero-key retrieval quality ceiling** — adequate for demos, not competitive with paid search for hard queries.
4. **ZK layer is commitment + PoK**, not a full zkSNARK; sufficient for offer privacy, not full shielded payments.
5. **Official x402 SDK middleware** not wired; current gate is a correct but simplified 402 responder.
6. **Tests** cover custody/evaluation paths but not full JDP+ZK+payment matrix.

## Security notes

- Free mode correctly avoids requiring secrets.
- Live mode requires explicit env opt-in (`VERITAS_REQUIRE_PAYMENT`).
- JIT packets are disposable and TTL-bounded.
- Wallet commitments hide addresses in offers; opening material must stay private to the seller.
- No rate limiting or abuse controls yet — required before public exposure.

## Verdict

The repository is a **coherent, distributable reference implementation** of a high-assurance, agent-native research + payment stack. Structural integration is complete. Delivery of a revenue-generating public product still depends on hosting, real wallet control, and search quality upgrades — all documented in ANALYSIS.md.
