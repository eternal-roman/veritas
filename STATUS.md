# Veritas Status

This repository contains a clean, high-skepticism re-implementation of the Veritas Research core under the Bayesian Knowledge Ledger design.

## What is present
- Content hashing + verification
- Append-only hash-chain custody ledger
- Bayesian belief updating
- Evidence-first pipeline (refuses when evidence is weak)
- Trust scoring
- ERC-8004-compatible identity document
- Basic tests

## What is deliberately minimal
- Retrieval is a conservative placeholder (prefers refusal over hallucination)
- No live x402 facilitator settlement yet
- No on-chain ERC-8004 registration transaction yet

The structural contracts (custody, hashing, Bayesian updating, refusal) are solid and independently verifiable.
