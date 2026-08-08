# Contributing

Thanks for looking. This repository has a few rules that are stricter than
usual, and they exist for one reason: the product is a service that tells
agents the truth about evidence. A codebase that overstates itself cannot ship
that credibly.

Read [AGENTS.md](AGENTS.md) first — it is the working guide for humans and
agents alike (commands, layout, load-bearing invariants).

## Setup

```bash
pip install -e ".[signing,dev]"
python -m pytest tests/ -q
```

## The gates your change must pass

CI runs all of these and **has no soft-fail** — do not add `|| true` or
`continue-on-error` to make a job green.

```bash
python -m pytest tests/ -q                    # suite must stay green
ruff check veritas tests scripts              # lint
bandit -r veritas scripts -ll -q              # security scan
python -m veritas.evaluations.harness         # quality report
python -m veritas.evaluations.payment_model   # bounded payment-invariant check
```

## Rules that are load-bearing

These are the ones a well-meaning change breaks most often. Each is tested.

1. **One engine.** Every surface calls `veritas.pipeline.run_research`. Do not
   add a second retrieval, custody or payment path.
2. **`unavailable` is not `no_evidence`.** If retrieval failed, say so. Never
   report an absence of evidence you did not observe.
3. **Never bill for our own failure.** `billable: false` on `unavailable` gates
   settlement.
4. **Verify payment before work, settle after**, and claim the nonce before the
   work so a resubmitted `X-PAYMENT` cannot buy a second retrieval pass.
5. **Retrievers are untrusted.** They may raise and may ignore `max_results`.
6. **The wire contract is enforced.** Extending the response means extending
   `veritas.schema`.
7. **Exception text never reaches a buyer.** Error bodies carry registered
   codes, not stack detail — server paths and resolver output are information
   disclosure.

## Claims discipline

[`skills/adversarial-code-truth.md`](skills/adversarial-code-truth.md) is a
locked gate on all code work here. Before any success claim, emit its
PROPERTY / EVIDENCE LEVEL block. Tests are **L1** — "holds on these cases" —
not proof the product works in the wild.

The words **"complete", "live-ready", "production-ready", "revenue-ready"** and
**"ZK"** are banned in docs unless evidence carries them, and a test enforces
this on `README.md`, `STATUS.md`, `CONSTITUTION.md` and `ECOSYSTEM.md`. Write
narrow claims and cite what backs them. If you find an overstatement we missed,
a PR that *removes* it is as welcome as one that adds a feature.

## Changing the constitution

`veritas/constitution.py` is the normative source; `CONSTITUTION.md` is a
sync-tested rendering. Changing an article means changing **both** and bumping
`CONSTITUTION_VERSION`. Every new article is either L1 with a resolving
enforcement pointer, or L0 explicitly marked aspirational —
`tests/test_constitution.py` rejects anything in between.

## Tests

New behaviour needs a test that would fail without it. Prefer tests that pin an
invariant over tests that pin an implementation detail: a test asserting a
platform-specific string is a test that will fail on someone else's machine
while the product is correct (see defect W2 in `docs/program/STATE.md` for a
worked example of getting this wrong).

Where a property genuinely cannot hold on some platform, do not weaken the
assertion — make the code report the gap and assert *that*, then register the
limitation in `docs/program/STATE.md` and README "Known limitations".

## Commits and PRs

- Branch off `main`; keep commits focused.
- Explain **why** in the commit body, not just what. The history here is used
  as a design record.
- State honestly in the PR what is proven and what is not.

## Security

Do not open a public issue for a vulnerability — see [SECURITY.md](SECURITY.md)
for private reporting via GitHub Security Advisories.
