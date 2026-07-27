# Veritas Status — Integrated

## Integrated and committed

- Epistemic core (custody, hashing, Bayesian, refusal)
- Zero-key free retrieval + agent bootstrap
- Full CAIP-2 network support
- Live/free payment configuration + 402 gate
- JIT Disposable Packet protocol
- ZK-style wallet commitment privacy
- Evaluation harness
- Workflow, distributable, and analysis docs

## Modes

| Mode | human_required | Real money |
|------|----------------|------------|
| Free (default) | false | No |
| Live | false (once running) | Yes (with PAY_TO + facilitator) |

## Next operational steps for production revenue

1. Deploy a public instance
2. Set `VERITAS_PAY_TO` + facilitator + `VERITAS_REQUIRE_PAYMENT=true`
3. Register discovery (Bazaar / well-known)
4. Upgrade retrieval quality for general queries
