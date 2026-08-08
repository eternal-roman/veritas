# Counterparty Diligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a buyer agent refuse a seller on machine-checkable grounds, and make that refusal bind money rather than advise about it.

**Architecture:** A pure evaluator (`veritas/diligence.py`) turns already-fetched seller documents into a verdict; `PaymentClient.pay()` gains a third gate between validation and spend policy, so a refused counterparty never reaches the signer. No network I/O is added anywhere.

**Tech Stack:** Python 3.10+, stdlib only, pytest. No new dependencies.

## Global Constraints

- Python >= 3.10. `from __future__ import annotations` at the top of every new module, matching the codebase.
- **No new runtime dependencies.** stdlib only.
- **Do not modify** `veritas/server.py`, `veritas/custody.py`, `veritas/ledger.py`, `veritas/ops_cli.py`, `veritas/errors.py`, `veritas/retention.py`, or anything under `docs/program/`. Another agent is working those concurrently. Only `veritas/payer.py` is modified; everything else is created.
- `ruff check veritas tests` must pass. Line length 100, ignore E501. Rules: E, F, W, I, B, UP.
- `bandit -r veritas scripts -ll -q` must pass.
- Failures are explicit results, never control-flow exceptions — matching `veritas/payer.py`'s stated contract.
- Every success claim must carry the PROPERTY / EVIDENCE LEVEL block from `skills/adversarial-code-truth.md`. Tests are **L1**.
- Banned words in docs and docstrings: "complete", "live-ready", "ZK", "revenue-ready".

---

### Task 1: Make the test suite deterministic

**Why first:** `main` @ `4c3b23c` measures `2 failed, 418 passed, 2 skipped, 4 errors`. All six pass in isolation, so the suite is order-dependent, not flaky. Nothing built in Task 2+ can be honestly verified until this is fixed, because "the tests pass" would not be a reproducible statement.

**Root cause (measured, not assumed):** `veritas/server.py:96-98` constructs `CustodyStore()`, `OutcomeLog()` and `Ledger()` at **import time**. Each reads `VERITAS_RUNTIME_DIR`, defaulting to the cwd-relative `.veritas_runtime` (open defect O5). Test modules import `veritas.server` at collection time, before any fixture runs, so the singletons bind to the repository root and are shared by the whole session. The suite works around this with 23 `importlib.reload` calls across 11 files; all three failing files are reload sites.

**Fix:** set `VERITAS_RUNTIME_DIR` to a temporary directory *at conftest import time* — which pytest executes before collecting any test module — so the import-time singletons can never bind to the repository root.

**Files:**
- Create: `tests/conftest.py`

**Interfaces:**
- Consumes: nothing.
- Produces: no importable symbols. Side effect only: `VERITAS_RUNTIME_DIR` is set in `os.environ` before test collection, and each test additionally gets a per-test runtime directory.

- [ ] **Step 1: Record the failing baseline as evidence**

```bash
python -m pytest tests/ -q > /tmp/before.txt 2>&1; echo "exit=$?"
tail -8 /tmp/before.txt
```

Expected: non-zero exit, and a summary line reading `2 failed, 418 passed, 2 skipped, ... 4 errors`.

**Do not use a pipe here.** `pytest ... | tail` returns `tail`'s exit code and hides pytest's, which is how this red baseline went unnoticed.

- [ ] **Step 2: Write the conftest**

```python
"""Test-session isolation for Veritas.

`veritas/server.py` builds its CustodyStore, OutcomeLog and Ledger at import
time, and each reads VERITAS_RUNTIME_DIR with a cwd-relative default of
`.veritas_runtime` (open defect O5). Test modules import the server at
collection time, before any fixture can run, so without this file the whole
session shares one runtime directory in the repository root — and the suite
becomes order-dependent, which is exactly what it was.

The environment variable is therefore set at *conftest import* time. pytest
imports conftest before collecting test modules, so this is the only hook that
runs early enough to reach an import-time singleton.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Bound before collection. setdefault, not assignment: an operator or CI job
# that pins VERITAS_RUNTIME_DIR deliberately keeps their value.
_SESSION_RUNTIME = Path(tempfile.mkdtemp(prefix="veritas-test-runtime-"))
os.environ.setdefault("VERITAS_RUNTIME_DIR", str(_SESSION_RUNTIME))


@pytest.fixture(autouse=True)
def isolated_runtime_dir(tmp_path, monkeypatch):
    """Give each test its own runtime directory.

    The session-level binding above stops state reaching the repository root.
    This stops it reaching the *next test*: any test that reloads
    `veritas.server` rebinds the singletons, and it should rebind them
    somewhere private rather than into a directory a sibling test also uses.
    """
    runtime = tmp_path / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(runtime))
    return runtime
```

- [ ] **Step 3: Verify the six measured failures are resolved**

```bash
python -m pytest tests/ -q > /tmp/after.txt 2>&1; echo "exit=$?"
tail -8 /tmp/after.txt
```

Expected: `exit=0`, zero failed, zero errors, and a passed count of at least 418.

**If any failure remains:** STOP. Do not proceed to Task 2 and do not add a second fix on top. Return to Phase 1 of `superpowers:systematic-debugging` with the new traceback — a partial fix here means the root cause was mis-identified.

- [ ] **Step 4: Verify no runtime directory is left in the repository root**

```bash
test ! -e .veritas_runtime && echo "CLEAN: no runtime dir in repo root" || { echo "FAIL: .veritas_runtime still written"; ls -la .veritas_runtime; }
git status --porcelain
```

Expected: `CLEAN`, and `git status` showing only `tests/conftest.py` as untracked.

- [ ] **Step 5: Lint**

```bash
ruff check veritas tests
```

Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py
git commit -m "Bind the test runtime directory before collection, not after

main was 2 failed / 4 errors locally with all six passing in isolation: the
suite was order-dependent, not flaky. server.py builds its CustodyStore,
OutcomeLog and Ledger at import time against a cwd-relative
VERITAS_RUNTIME_DIR (open defect O5), and test modules import it during
collection, so the whole session shared one runtime directory in the
repository root.

conftest sets the variable at import time because that is the only hook that
runs before collection, and an autouse fixture then gives each test its own
directory so reloading tests cannot reach a sibling.

This does not fix O5. server.py still binds at import and still defaults to a
relative path; the 23 importlib.reload workarounds are untouched. It makes the
suite's verdict reproducible, which is a precondition for every enforcement
pointer in the constitution meaning anything.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: The diligence evaluator

**Files:**
- Create: `veritas/diligence.py`
- Test: `tests/test_diligence.py`

**Interfaces:**
- Consumes: `veritas.payer.validate_accepts`, `veritas.payer.ValidatedAccepts`.
- Produces:
  - `Verdict` — `str` enum-like constants: `Verdict.PASS = "pass"`, `Verdict.FAIL = "fail"`, `Verdict.UNVERIFIABLE = "unverifiable"`.
  - `CheckResult(name: str, verdict: str, detail: str)` — frozen dataclass.
  - `DiligencePolicy(require_constitution: bool = True, require_gap_register: bool = True, require_trust_self_disclosure: bool = True, require_challenge_matches_discovery: bool = True, min_enforced_articles: int = 1)` — frozen dataclass.
  - `DiligenceReport(verdict: str, checks: tuple[CheckResult, ...])` with properties `passed: bool`, `reasons: tuple[str, ...]`, and method `to_dict() -> dict`.
  - `assess(*, challenge: object = None, discovery: object = None, constitution: object = None, trust: object = None, policy: DiligencePolicy | None = None) -> DiligenceReport`.

- [ ] **Step 1: Write the failing tests**

```python
"""Buyer-side counterparty diligence."""

from __future__ import annotations

import pytest

from veritas.diligence import (
    DiligencePolicy,
    Verdict,
    assess,
)

PAY_TO = "0x" + "11" * 20
OTHER_PAY_TO = "0x" + "22" * 20
ASSET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


def _accepts(pay_to=PAY_TO, amount="10000", asset=ASSET):
    return {
        "scheme": "exact",
        "network": "eip155:8453",
        "asset": asset,
        "payTo": pay_to,
        "maxAmountRequired": amount,
        "resource": "https://seller.test/v1/research",
        "extra": {"name": "USD Coin", "version": "2"},
    }


def _discovery(pay_to=PAY_TO, amount="10000"):
    return {"x402Version": 1, "accepts": [_accepts(pay_to, amount)]}


def _challenge(pay_to=PAY_TO, amount="10000"):
    return {"x402Version": 1, "accepts": [_accepts(pay_to, amount)]}


def _constitution():
    return {
        "version": "2.2",
        "articles": [
            {"id": "A1", "statement": "One engine.", "evidence_level": "L1",
             "enforcement": "tests/test_integration.py::test_control_plane_uses_shared_engine"},
            {"id": "A16", "statement": "Portable reputation.", "evidence_level": "L0",
             "enforcement": None, "aspirational": True},
        ],
        "known_gaps": [{"id": "G10", "status": "open"}],
    }


def _trust():
    return {
        "overall": None,
        "recommendation": "UNPROVEN",
        "basis": {
            "min_samples": 10,
            "self_reported": "Computed by the graded party from its own records.",
        },
    }


# -- the central discipline -------------------------------------------------


def test_missing_documents_are_unverifiable_not_failed():
    """UNVERIFIABLE is not FAIL. This is the module's central claim: it is the
    buyer-side form of `unavailable is not no_evidence`."""
    report = assess(challenge=_challenge(), discovery=None,
                    constitution=None, trust=None)
    assert report.verdict == Verdict.UNVERIFIABLE
    assert report.verdict != Verdict.FAIL
    assert not report.passed


def test_an_observed_defect_is_failed_not_unverifiable():
    """A document that is present and inconsistent is a real observation."""
    report = assess(
        challenge=_challenge(pay_to=OTHER_PAY_TO),
        discovery=_discovery(pay_to=PAY_TO),
        constitution=_constitution(),
        trust=_trust(),
    )
    assert report.verdict == Verdict.FAIL


# -- check 1: challenge/discovery agreement ---------------------------------


def test_a_challenge_billing_an_unadvertised_address_fails():
    report = assess(
        challenge=_challenge(pay_to=OTHER_PAY_TO),
        discovery=_discovery(pay_to=PAY_TO),
        constitution=_constitution(), trust=_trust(),
    )
    assert report.verdict == Verdict.FAIL
    assert any("pay_to" in r for r in report.reasons)


def test_a_challenge_charging_more_than_advertised_fails():
    report = assess(
        challenge=_challenge(amount="99999"),
        discovery=_discovery(amount="10000"),
        constitution=_constitution(), trust=_trust(),
    )
    assert report.verdict == Verdict.FAIL
    assert any("amount" in r for r in report.reasons)


def test_a_challenge_charging_less_than_advertised_passes():
    """Undercharging is not fraud against the buyer, so the amount check is
    one-sided by design."""
    report = assess(
        challenge=_challenge(amount="5000"),
        discovery=_discovery(amount="10000"),
        constitution=_constitution(), trust=_trust(),
    )
    assert report.verdict == Verdict.PASS


def test_a_consistent_seller_passes():
    report = assess(
        challenge=_challenge(), discovery=_discovery(),
        constitution=_constitution(), trust=_trust(),
    )
    assert report.verdict == Verdict.PASS
    assert report.passed


# -- check 2: register integrity --------------------------------------------


def test_an_article_claiming_enforcement_without_a_pointer_fails():
    bad = _constitution()
    bad["articles"][0]["enforcement"] = None
    report = assess(challenge=_challenge(), discovery=_discovery(),
                    constitution=bad, trust=_trust())
    assert report.verdict == Verdict.FAIL
    assert any("A1" in r for r in report.reasons)


def test_a_constitution_with_no_enforced_articles_fails():
    bare = {"version": "0", "articles": [
        {"id": "A1", "statement": "Trust us.", "evidence_level": "L0",
         "enforcement": None, "aspirational": True},
    ], "known_gaps": [{"id": "G1"}]}
    report = assess(challenge=_challenge(), discovery=_discovery(),
                    constitution=bare, trust=_trust())
    assert report.verdict == Verdict.FAIL


# -- check 5: a seller claiming perfection ----------------------------------


def test_a_seller_declaring_no_gaps_fails():
    """An empty defect register is evidence of concealment, not of quality."""
    perfect = _constitution()
    perfect["known_gaps"] = []
    report = assess(challenge=_challenge(), discovery=_discovery(),
                    constitution=perfect, trust=_trust())
    assert report.verdict == Verdict.FAIL
    assert any("gap" in r.lower() for r in report.reasons)


# -- check 4: self-report disclosure ----------------------------------------


def test_a_bare_trust_number_without_disclosure_fails():
    undisclosed = {"overall": 99.0, "recommendation": "RECOMMENDED", "basis": {}}
    report = assess(challenge=_challenge(), discovery=_discovery(),
                    constitution=_constitution(), trust=undisclosed)
    assert report.verdict == Verdict.FAIL
    assert any("self" in r.lower() for r in report.reasons)


def test_unproven_with_disclosure_passes():
    """Publishing UNPROVEN honestly beats publishing a flattering number."""
    report = assess(challenge=_challenge(), discovery=_discovery(),
                    constitution=_constitution(), trust=_trust())
    assert report.verdict == Verdict.PASS


# -- policy -----------------------------------------------------------------


def test_policy_can_waive_a_check():
    relaxed = DiligencePolicy(require_trust_self_disclosure=False)
    undisclosed = {"overall": 99.0, "recommendation": "RECOMMENDED", "basis": {}}
    report = assess(challenge=_challenge(), discovery=_discovery(),
                    constitution=_constitution(), trust=undisclosed,
                    policy=relaxed)
    assert report.verdict == Verdict.PASS


# -- contract ---------------------------------------------------------------


@pytest.mark.parametrize("garbage", ["", 0, [], "not-a-dict", {"accepts": "no"}])
def test_assess_never_raises_on_garbage(garbage):
    """Failures are results, never control-flow exceptions."""
    report = assess(challenge=garbage, discovery=garbage,
                    constitution=garbage, trust=garbage)
    assert report.verdict in (Verdict.FAIL, Verdict.UNVERIFIABLE)


def test_report_is_serialisable_with_a_reason_per_check():
    report = assess(challenge=_challenge(), discovery=_discovery(),
                    constitution=_constitution(), trust=_trust())
    body = report.to_dict()
    assert body["verdict"] == Verdict.PASS
    assert len(body["checks"]) >= 4
    for check in body["checks"]:
        assert check["name"] and check["verdict"] and check["detail"]
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest tests/test_diligence.py -q
```

Expected: collection error, `ModuleNotFoundError: No module named 'veritas.diligence'`.

- [ ] **Step 3: Implement `veritas/diligence.py`**

Write the module to satisfy exactly the tests above. Required structure:

```python
"""Buyer-side counterparty diligence: grounds for refusing a seller.

veritas/payer.py records the gap this closes: pinning payment parameters to a
validated challenge does not authenticate the seller, so a hostile
counterparty can name any recipient at any price and only SpendPolicy bounds
the loss. A spend cap is a budget, not a decision.

The discipline here is the buyer-side form of the one this service sells.
`unavailable` is not `no_evidence`; likewise UNVERIFIABLE is not FAIL. "I
could not check this seller" and "this seller failed the check" are different
facts. Both block a payment, because the gate is fail-closed, but they are
reported apart: FAIL means find another seller, UNVERIFIABLE means fix your own
fetch path and retry.

What every check here is evidence of: cross-document consistency and register
integrity. **None of them proves the seller will deliver.** A careful liar
with a coherent set of documents passes all of them. This raises the cost of
dishonesty and gives a buyer machine-checkable grounds to refuse; it is not
proof of honesty and must not be described as such.

No network I/O: `assess` evaluates documents the caller already fetched. That
keeps it pure, adds no request surface, and lets a buyer fetch as it likes.
"""
```

Implementation requirements:

- `Verdict` is a plain class holding three `str` constants (`PASS`, `FAIL`, `UNVERIFIABLE`). Not an `enum.Enum` — the values go into JSON and must compare equal to plain strings.
- `assess()` runs each enabled check, collects `CheckResult`s, and folds the verdict: **any `FAIL` → `FAIL`; else any `UNVERIFIABLE` → `UNVERIFIABLE`; else `PASS`.** `FAIL` dominates because an observed defect outranks a missing observation.
- Each check is its own module-level function taking already-extracted values and returning one `CheckResult`. Keep them small enough to read whole.
- Check 1 extracts the first `accepts` entry from both challenge and discovery and runs each through `veritas.payer.validate_accepts`. If either fails validation → `UNVERIFIABLE` naming which document. If both validate, compare `pay_to`, `network` and `asset` case-insensitively for equality, and require `challenge.amount_atomic <= discovery.amount_atomic`. Compare atomic ints, never the human price string.
- Check 2 walks `constitution["articles"]`: any article whose `evidence_level` is `"L1"` with an empty or missing `enforcement` → `FAIL` naming the article id. Any article that is both `L1` and `aspirational` → `FAIL`. Fewer than `policy.min_enforced_articles` L1 articles → `FAIL`.
- Check 4 requires `trust["basis"]` to contain a non-empty `self_reported` string and a `min_samples` value; otherwise `FAIL`.
- Check 5 requires `constitution["known_gaps"]` to be a non-empty list; an empty or missing register → `FAIL`.
- A document that is `None` → `UNVERIFIABLE` for every check that needs it. A document that is present but not a mapping → `UNVERIFIABLE` (it is unreadable, not defective).
- `assess` catches nothing broadly; it uses `isinstance` guards so no exception can arise. Verify with the garbage-input test.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest tests/test_diligence.py -q
```

Expected: all pass.

- [ ] **Step 5: Verify Veritas's own documents pass their own bar**

Add to `tests/test_diligence.py`:

```python
def test_veritas_own_constitution_passes_its_own_bar():
    """The venue's reference implementation must clear the bar it publishes."""
    from veritas.constitution import constitution_document

    report = assess(constitution=constitution_document(),
                    policy=DiligencePolicy(
                        require_challenge_matches_discovery=False,
                        require_trust_self_disclosure=False))
    assert report.verdict == Verdict.PASS, report.reasons
```

Run: `python -m pytest tests/test_diligence.py -q`

If `constitution_document` is not the real export name, read `veritas/constitution.py` and use the actual one; do not stub it.

**If this test fails, that is a finding about Veritas, not about the test.** Report it rather than weakening the assertion.

- [ ] **Step 6: Lint and security scan**

```bash
ruff check veritas tests && bandit -r veritas -ll -q
```

Expected: both clean.

- [ ] **Step 7: Commit**

```bash
git add veritas/diligence.py tests/test_diligence.py
git commit -m "Add buyer-side counterparty diligence

payer.py records that pinning parameters to a validated challenge does not
authenticate the seller: a hostile counterparty can name any recipient at any
price and only SpendPolicy bounds the loss. This gives a buyer agent grounds
to refuse, computed from documents the seller already publishes.

UNVERIFIABLE is not FAIL, which is the buyer-side form of the distinction this
service sells. Both block, because the gate is fail-closed, but a buyer
answers them differently.

The strongest check needs no trust at all: the 402 challenge must agree with
advertised discovery on payout address, network and asset, and must not
exceed the advertised price. Undercharging passes - it is not fraud against
the buyer.

Limits: every check is cross-document consistency and register integrity.
None proves the seller will deliver, and a careful liar with coherent
documents passes all of them.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Bind the verdict to the money

**Files:**
- Modify: `veritas/payer.py` — module docstring, `PaymentClient.__init__`, `PaymentClient.pay`
- Test: `tests/test_diligence_gate.py`

**Interfaces:**
- Consumes: `veritas.diligence.DiligenceReport`, `Verdict` from Task 2.
- Produces: `PaymentClient(signer, policy, base_dir=None, require_diligence: bool = False)`; `pay(..., diligence: DiligenceReport | None = None)` returning the existing `PaymentResult` shape with `check="diligence"` on refusal.

- [ ] **Step 1: Write the failing tests**

```python
"""The diligence verdict must bind money, not advise about it."""

from __future__ import annotations

import pytest

from veritas.diligence import DiligencePolicy, Verdict, assess
from veritas.payer import PaymentClient, SpendPolicy, validate_accepts

PAY_TO = "0x" + "11" * 20
OTHER_PAY_TO = "0x" + "22" * 20
ASSET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


class ExplodingSigner:
    """A signer that fails the test if it is ever reached.

    Mirrors constitution article A20: a refused payment never reaches the
    signer. A diligence refusal must hold the same line.
    """

    address = "0x" + "99" * 20

    def sign_typed_data(self, payload):
        raise AssertionError("signer reached despite a refused counterparty")


def _accepts(pay_to=PAY_TO, amount="10000"):
    return {
        "scheme": "exact", "network": "eip155:8453", "asset": ASSET,
        "payTo": pay_to, "maxAmountRequired": amount,
        "resource": "https://seller.test/v1/research",
        "extra": {"name": "USD Coin", "version": "2"},
    }


@pytest.fixture
def client(tmp_path):
    policy = SpendPolicy(
        max_per_request=1_000_000, max_per_day=1_000_000,
        max_per_day_per_counterparty=1_000_000, base_dir=tmp_path,
    )
    return PaymentClient(ExplodingSigner(), policy, base_dir=tmp_path,
                         require_diligence=True)


def _validated(pay_to=PAY_TO, amount="10000"):
    validated, problems = validate_accepts(_accepts(pay_to, amount))
    assert not problems, problems
    return validated


def test_a_refused_counterparty_never_reaches_the_signer(client):
    report = assess(
        challenge={"accepts": [_accepts(pay_to=OTHER_PAY_TO)]},
        discovery={"accepts": [_accepts(pay_to=PAY_TO)]},
        constitution=None, trust=None,
    )
    assert report.verdict == Verdict.FAIL

    result = client.pay(_validated(pay_to=OTHER_PAY_TO), now=1_760_000_000,
                        diligence=report)
    assert result.paid is False
    assert result.check == "diligence"
    assert result.header is None


def test_absent_diligence_is_refused_when_required(client):
    """Fail-closed: a client that requires diligence and is handed none must
    refuse, not proceed."""
    result = client.pay(_validated(), now=1_760_000_000, diligence=None)
    assert result.paid is False
    assert result.check == "diligence"


def test_unverifiable_is_refused_but_named_distinctly(client):
    report = assess(challenge={"accepts": [_accepts()]}, discovery=None,
                    constitution=None, trust=None)
    assert report.verdict == Verdict.UNVERIFIABLE

    result = client.pay(_validated(), now=1_760_000_000, diligence=report)
    assert result.paid is False
    assert result.check == "diligence"
    assert "unverifiable" in result.denial.lower()
    assert "fail" not in result.denial.lower().replace("unverifiable", "")


def test_diligence_is_opt_in_and_off_by_default(tmp_path):
    """An existing caller that passes no diligence keeps working: this change
    is additive, and turning the gate on is the buyer's decision."""
    policy = SpendPolicy(
        max_per_request=1_000_000, max_per_day=1_000_000,
        max_per_day_per_counterparty=1_000_000, base_dir=tmp_path,
    )

    class RecordingSigner:
        address = "0x" + "99" * 20
        reached = False

        def sign_typed_data(self, payload):
            RecordingSigner.reached = True
            return "0x" + "ab" * 65

    default_client = PaymentClient(RecordingSigner(), policy, base_dir=tmp_path)
    result = default_client.pay(_validated(), now=1_760_000_000)
    assert result.paid is True
    assert RecordingSigner.reached is True
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest tests/test_diligence_gate.py -q
```

Expected: `TypeError` on the unexpected `require_diligence` / `diligence` keyword arguments.

- [ ] **Step 3: Implement the gate**

In `veritas/payer.py`:

1. Add `require_diligence: bool = False` as the last parameter of `PaymentClient.__init__`, storing `self._require_diligence = require_diligence`. Default `False` keeps every existing caller working.

2. In `pay()`, add `diligence: DiligenceReport | None = None` as the last parameter.

3. Insert the gate **after** the validity-window check and **before** `self._policy.authorize(...)`, so a refused counterparty consumes no budget state and never reaches the journal or the signer:

```python
        # Third policy layer, beside validation and spend caps. A hostile
        # seller can name any payee at any price in its own challenge, so
        # bounding the loss with a cap is a budget, not a decision. This is
        # the decision. UNVERIFIABLE and FAIL both refuse, and are named
        # apart: one means find another seller, the other means fix your own
        # fetch path.
        if self._require_diligence:
            if diligence is None:
                return _denied(
                    "diligence required but none supplied", "diligence"
                )
            if diligence.verdict != Verdict.PASS:
                return _denied(
                    f"counterparty diligence {diligence.verdict}: "
                    + "; ".join(diligence.reasons),
                    "diligence",
                )
```

4. Import at module top: `from .diligence import DiligenceReport, Verdict`.

   **Check for a circular import first.** `veritas/diligence.py` imports `validate_accepts` from `veritas/payer.py`. If `payer` also imports `diligence` at module level, the cycle will break. If `python -c "import veritas.payer"` fails, resolve it by importing `diligence` lazily *inside* `pay()`, and note why in a comment. Do not restructure `diligence.py` to remove its use of `validate_accepts` — reusing the existing validator is the point.

5. Extend the `payer.py` module docstring: the "Counterparty vetting is roadmap 5.2, not this module" sentence is now wrong. Replace it with a sentence stating that counterparty vetting is available via `veritas.diligence` and is opt-in per client, and that a spend cap remains the only bound when it is off.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest tests/test_diligence_gate.py -q
```

Expected: all pass.

- [ ] **Step 5: Verify nothing regressed, including the bounded model check**

```bash
python -m pytest tests/ -q > /tmp/full.txt 2>&1; echo "exit=$?"; tail -5 /tmp/full.txt
python -m veritas.evaluations.payment_model > /dev/null && echo "payment model OK"
ruff check veritas tests && bandit -r veritas scripts -ll -q && echo "lint+security OK"
```

Expected: `exit=0`, zero failures, payment model passes, lint and bandit clean.

`tests/test_payer.py` greps `payer.py` to prove no key material is handled there. Confirm that still passes — the new import must not trip it.

- [ ] **Step 6: Commit**

```bash
git add veritas/payer.py tests/test_diligence_gate.py
git commit -m "Let a buyer refuse a seller before the signer is reached

payer.py said counterparty vetting was roadmap 5.2 and not its problem, which
left a spend cap as the buyer's only defence against a hostile seller: it
would pay the wrong party, for the wrong thing, at the wrong price, just not
more than N per day.

The gate sits between validation and spend caps, so a refused counterparty
consumes no budget state, is never journalled, and never reaches the signer -
the line article A20 already draws for a refused payment.

Opt-in per client and off by default, so every existing caller is unchanged
and turning it on stays the buyer's decision.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Documentation, honestly scoped

**Files:**
- Modify: `README.md` (Capabilities list), `AGENTS.md` (invariant 8 wording)

Do **not** touch `STATUS.md`, `CONSTITUTION.md`, `veritas/constitution.py`, or `docs/program/`. Adding a constitution article would require bumping `CONSTITUTION_VERSION` and re-rendering, which collides with concurrent work; the article is left for a later cycle and named as such.

- [ ] **Step 1: Add one README bullet under Capabilities**

```markdown
- **Buyer-side counterparty diligence** (`veritas/diligence.py`) — a buyer agent
  refuses a seller on machine-checkable grounds: the 402 challenge must agree
  with advertised discovery on payee, network and asset and must not exceed the
  advertised price; the constitution's L1 articles must carry enforcement
  pointers; and a seller declaring no known gaps is refused for claiming
  perfection. `UNVERIFIABLE` is reported apart from `FAIL`. Every check is
  cross-document consistency — none proves a seller will deliver
```

- [ ] **Step 2: Correct invariant 8 in AGENTS.md**

Invariant 8 currently reads that `veritas.payer` owns "challenge validation, spend caps, the attempt journal, and the `Signer` seam". Add counterparty diligence to that list so the invariant still describes the module.

- [ ] **Step 3: Verify the banned-claims gate still passes**

```bash
python -m pytest tests/ -q -k "banned or claims or sync" > /tmp/claims.txt 2>&1; echo "exit=$?"; tail -5 /tmp/claims.txt
```

Expected: `exit=0`. A CI gate scans `README.md` for banned words; if it trips, reword rather than weakening the gate.

- [ ] **Step 4: Commit**

```bash
git add README.md AGENTS.md
git commit -m "Document counterparty diligence, and its limits

Records what the checks are evidence of - cross-document consistency and
register integrity - and states plainly that none of them proves a seller will
deliver.

No constitution article yet: promoting one means bumping CONSTITUTION_VERSION
and re-rendering CONSTITUTION.md, which is deferred to avoid colliding with
concurrent work on that surface.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| Check 1 challenge/discovery agreement | Task 2, steps 1 & 3 |
| Check 2 register integrity | Task 2, steps 1 & 3 |
| Check 3 aspirational discount | Task 2, step 3 (`min_enforced_articles`, L1-vs-aspirational rule) |
| Check 4 self-report disclosure | Task 2, steps 1 & 3 |
| Check 5 gap register present | Task 2, steps 1 & 3 |
| UNVERIFIABLE is not FAIL | Task 2 step 1 (named test); Task 3 step 1 (distinct denial) |
| Refused counterparty never reaches the signer | Task 3, step 1 (`ExplodingSigner`) |
| Fail-closed gate | Task 3, step 1 (`test_absent_diligence_is_refused_when_required`) |
| No network I/O | Task 2, step 3 (stated; `assess` takes documents) |
| Errors are results, never raises | Task 2, step 1 (garbage parametrize) |
| Veritas passes its own bar | Task 2, step 5 |
| Deterministic suite prerequisite | Task 1 |
| Honest limits documented | Task 2 step 3 docstring; Task 4 step 1 |

**Placeholder scan:** none. Every code step carries runnable content; Task 2 step 3 gives explicit construction rules rather than a body, which is a deliberate constraint list, not a TODO.

**Type consistency:** `Verdict.PASS/FAIL/UNVERIFIABLE`, `DiligenceReport.verdict/.reasons/.passed/.to_dict()`, `CheckResult.name/.verdict/.detail`, `DiligencePolicy` field names, and `PaymentResult.check == "diligence"` are used identically in Tasks 2, 3 and 4.

**Known risk, flagged not hidden:** Task 3 introduces a potential import cycle (`payer → diligence → payer`). Step 3.4 names it and gives the resolution. It is the one place this plan can fail on contact.
