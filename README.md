# Veritas Research

High-assurance research service for AI agents.

Every claim is backed by content-hashed evidence under an append-only chain of custody. Beliefs are updated only through Bayesian conditionalization on verified evidence. The service refuses when evidence is insufficient.

## Core Guarantees

- **Chain of Custody**: Every evidence item and claim is linked by cryptographic hash chain. Any break is detectable.
- **Bayesian Updating**: Priors become posteriors only on verified evidence. No assertion is accepted as belief.
- **Evidence-First**: Claims without attached, hashed evidence are not emitted.
- **Refusal**: Explicit first-class outcome when support is weak.
- **Discoverable & Payable**: x402 payments, MCP tool, ERC-8004 identity, trust scores.

## Package Structure

```
veritas/
  hashing.py      # Content hashing + normalization
  custody.py      # Append-only hash-chain custody ledger
  bayesian.py     # Bayesian belief updating
  schema.py       # Claim, Evidence, Response models
  pipeline.py     # Research pipeline
  trust.py        # Trust scoring
  identity.py     # ERC-8004 compatible identity
app/
  main.py         # FastAPI + payment middleware skeleton
tests/
  test_core.py
```

## Status

This is a clean, high-skepticism re-implementation of the architecture developed in the design thread. Core custody, hashing, Bayesian updating, and schema are solid. Retrieval and claim generation are deliberately minimal and evidence-constrained so the contracts can be trusted. Production retrieval and calibrated likelihood models are the next layer.

## License

Apache-2.0
