# Working in this repository

Guide for agents (and humans) contributing to or consuming Veritas. The README
covers what the product is; this file covers how to work on it and what rules
are load-bearing.

## Setup and commands

```bash
pip install -e ".[retrieval,dev]"        # everything needed to develop
python -m pytest tests/ -q               # test suite — must stay green
python -m veritas.evaluations.harness    # quality report (JSON to stdout)
ruff check veritas tests                 # lint — CI gates on this
bandit -r veritas -lll -q                # security scan — CI gates on high severity
python -m build && twine check dist/*    # packaging — CI builds and installs the wheel
veritas-server                           # run the service (free mode by default)
```

Offline development: `run_research(query, allow_network=False)` uses the
labelled offline corpus. The corpus is **not** a fallback for provider outages
— an outage must propagate as `unavailable`, never be papered over with
fixture text.

## Layout

One installable package. `veritas/` is the engine plus, as subpackages, the
agent-native layer (`veritas/autonomous/`), the FastAPI surface
(`veritas/server.py`), and the evaluation harness (`veritas/evaluations/`).
`tests/` stays outside the wheel. The wheel must ship exactly one top-level
package — CI's package job asserts this.

## Invariants that must hold (each is CI-gated or tested)

1. **One engine.** All surfaces call `veritas.pipeline.run_research`. Never
   add a second retrieval/custody/Bayes path.
2. **Never report absent evidence when retrieval failed.** `unavailable` is
   not `no_evidence`. This distinction is the product.
3. **Never bill for our own failure.** `billable: false` on `unavailable` is
   load-bearing; settlement is gated on it.
4. **Verify payment before work, settle after.** An unpaid caller must not
   consume a retrieval pass; a buyer must never be charged for undeliverable
   work.
5. **Retrievers are untrusted.** They may raise and may ignore `max_results`;
   the pipeline defends against both.
6. **The wire contract is enforced.** `veritas.schema.validate_response` runs
   against real pipeline output in tests. Extending the response means
   extending the contract.
7. **Misconfiguration never silently becomes free service.** Invalid payment
   config → `mode: misconfigured` → 503.
8. **Version is single-sourced.** `veritas.__version__` feeds pyproject
   (dynamic), the server, the identity document, and the retrieval user-agent.
   Bump it in exactly one place: `veritas/__init__.py`.

## Conventions

- **CI has no soft-fail.** Do not add `|| true` or `continue-on-error`.
- **`compileall` is not an import check.** The explicit import step in CI
  exists because compileall passes on unresolvable imports.
- **`skills/adversarial-code-truth.md` is a locked gate** on all code work
  here. Emit its PROPERTY / EVIDENCE LEVEL block before any success claim.
  Tests are L1 ("holds on these cases"), not proof the product works. Banned
  without carrying evidence: "complete", "live-ready", "ZK", "revenue-ready".
- Docs state limitations plainly (see README "Known limitations", STATUS.md).
  Keep that register: narrow claims, evidence cited.
- **The venue constitution is enforcement-linked.** `veritas/constitution.py`
  is the normative source; `CONSTITUTION.md` is a sync-tested rendering.
  Changing an article means changing both and bumping `CONSTITUTION_VERSION`;
  a new norm is either L1 with a resolving enforcement pointer or L0 marked
  aspirational — `tests/test_constitution.py` rejects anything else.

## Consuming the service as an agent

- Discovery: `GET /.well-known/x402` (payment requirements), `GET /v1/identity`.
- Norms: `GET /v1/constitution` — the venue constitution, each article either
  pointing at its enforcement artifact or marked aspirational (see
  `CONSTITUTION.md` and `ECOSYSTEM.md`).
- Research: `POST /v1/research` — returns 402 with an `accepts` array in live
  mode; retry with an `X-PAYMENT` header (base64 x402 payload).
- Verification: `POST /v1/verify` re-checks any published `content_hash`;
  `GET /v1/receipts/{request_id}` returns the durable custody receipt;
  `veritas.custody.verify_chain_records` re-runs chain validation client-side.
- Trust: `GET /v1/trust` is behaviour-derived and reports `UNPROVEN` below 10
  recorded outcomes. Treat it as an input, not authorization.

## Current state, honestly

Structural invariants above are tested and green. Not yet proven: no payment
has ever settled on-chain (fail-closed paths are exercised; success is not),
retrieval is snippet-grade, and the package is not yet published to PyPI. See
ROADMAP.md for the full evaluation and sequencing.
