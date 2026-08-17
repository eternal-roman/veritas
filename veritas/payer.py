"""Buyer-side x402 payment machinery with key-custody inversion.

The load-bearing design decision: no key material ever exists in this
process. This module constructs the full EIP-712 typed-data payload for an
EIP-3009 ``transferWithAuthorization``; the payload travels OUT to a signer
(hardware wallet, remote signing service, agent-held key outside this
process) and only a hex signature comes back. Nothing here reads, stores, or
derives a signing key, and the test suite greps this file to keep it that way.

Three policy layers gate every payment:

1. Validation — :func:`validate_accepts` is the only constructor of
   :class:`ValidatedAccepts`, so authorization parameters (network, asset,
   recipient, amount) can only come from a structurally validated 402
   challenge, never from raw caller input.
2. Counterparty diligence — :mod:`veritas.diligence` decides whether this
   seller may be paid at all, from documents it publishes. Opt-in per client
   via ``require_diligence=True``; off by default.
3. Spend caps — :class:`SpendPolicy` enforces per-request, per-day, and
   per-counterparty limits that persist across process restarts.

Limits, stated plainly:

- The ``ValidatedAccepts`` construction token is a structural guard, not a
  cryptographic one. ``PaymentClient`` additionally requires instances to be
  registered by ``validate_accepts`` itself (a ``WeakSet`` membership check),
  which also rejects ``dataclasses.replace``-derived copies — but deliberate
  in-process code can still defeat Python-level guards. The bounded model
  checker in ``veritas.evaluations.payment_model`` exercises the honest paths.
- Pinning parameters to the validated challenge does NOT authenticate the
  seller. The 402 challenge is itself content from an untrusted counterparty
  and is the sole source of ``payTo`` and ``amount``, so a hostile seller can
  name any recipient at any price. With ``require_diligence=False`` — the
  default — :class:`SpendPolicy` remains the only bound on that, which is a
  budget rather than a decision. With the gate on, a counterparty that fails
  :func:`veritas.diligence.assess` is refused before the signer is reached.
  What diligence checks is cross-document consistency and register integrity;
  it does not prove a seller will deliver.
- A signer exception after the payload has left the process is an
  *indeterminate* outcome: a signature may exist even though none was
  returned. The pre-sign attempt journal exists so reconciliation (roadmap
  0.3) can find such orphan authorizations; retrying mints a new nonce and a
  second live authorization, so retries must be bounded and reconciled.

Failures are explicit results, never control-flow exceptions.
"""

from __future__ import annotations

import base64
import datetime
import json
import os
import re
import secrets
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    # `veritas.diligence` imports validate_accepts from this module, so a
    # module-level import here would close the cycle. Annotations are strings
    # under `from __future__ import annotations`, and pay() imports Verdict
    # lazily at the one point it is needed.
    from .diligence import DiligenceReport

try:  # advisory same-host file locking; absent on some platforms
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None  # type: ignore[assignment]

from veritas.runtime import resolve_runtime_dir
from veritas.x402 import USDC_ASSETS

_CONSTRUCTION_TOKEN = object()

# Instances produced by validate_accepts, keyed by identity (id -> instance
# via weak values, with an `is` check on lookup so a recycled id cannot false-
# positive). PaymentClient refuses anything not registered, which closes the
# dataclasses.replace() construction route. Identity, not equality: a WeakSet
# would skip add() for an equal instance and then evict both on GC of the
# first — the model checker caught exactly that.
_VALIDATED_REGISTRY: weakref.WeakValueDictionary = weakref.WeakValueDictionary()


def _register_validated(instance: ValidatedAccepts) -> None:
    _VALIDATED_REGISTRY[id(instance)] = instance


def _is_registered(instance: ValidatedAccepts) -> bool:
    return _VALIDATED_REGISTRY.get(id(instance)) is instance

_CAIP2_RE = re.compile(r"eip155:\d+")
_ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]{40}")
_AMOUNT_RE = re.compile(r"[0-9]+")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

_UINT256_MAX = 2**256 - 1

_STATE_FILENAME = "spend_policy.json"
_ATTEMPTS_FILENAME = "authorization_attempts.jsonl"

# Ceiling on the authorization validity window PaymentClient will sign. The
# window bounds replay exposure only if something bounds the window itself.
MAX_VALIDITY_SECONDS = 3600


@dataclass(frozen=True)
class ValidatedAccepts:
    """A 402 ``accepts`` entry that passed :func:`validate_accepts`.

    Construction is token-guarded so instances only come from
    ``validate_accepts``. This is structural enforcement, bypassable by
    deliberate internal code — it defends against accidental use of raw
    challenge dicts, not against a hostile programmer.
    """

    scheme: str
    network: str
    chain_id: int
    asset: str
    pay_to: str
    amount_atomic: int
    domain_name: str
    domain_version: str
    _token: object = field(kw_only=True, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._token is not _CONSTRUCTION_TOKEN:
            raise TypeError(
                "ValidatedAccepts cannot be constructed directly; "
                "use validate_accepts()"
            )


def validate_accepts(entry: object) -> tuple[ValidatedAccepts | None, list[str]]:
    """Validate one 402 ``accepts`` entry. Returns (validated, problems).

    ``problems`` is empty iff the entry is valid. Never raises: malformed or
    garbage input becomes an enumerated problem list, because a buyer must be
    able to inspect every defect of a challenge without try/except plumbing.
    Asset addresses compare case-insensitively but the caller's casing is
    preserved — we validate, we do not silently rewrite.
    """
    problems: list[str] = []
    if not isinstance(entry, dict):
        return None, [f"accepts entry is not a mapping: {type(entry).__name__}"]

    scheme = entry.get("scheme")
    if scheme != "exact":
        problems.append(f"scheme must be 'exact', got {scheme!r}")

    network = entry.get("network")
    chain_id: int | None = None
    if not isinstance(network, str) or not _CAIP2_RE.fullmatch(network):
        problems.append(f"network is not CAIP-2 'eip155:<chain-id>': {network!r}")
    elif network not in USDC_ASSETS:
        problems.append(f"unknown network {network!r}; known: {sorted(USDC_ASSETS)}")
    else:
        chain_id = int(network.split(":", 1)[1])

    asset = entry.get("asset")
    if chain_id is not None:
        canonical = USDC_ASSETS[network]["address"]
        if not isinstance(asset, str) or asset.lower() != canonical.lower():
            problems.append(
                f"asset {asset!r} is not the known USDC contract {canonical} on {network}"
            )

    pay_to = entry.get("payTo")
    if not isinstance(pay_to, str) or not _ADDRESS_RE.fullmatch(pay_to):
        problems.append(f"payTo is not a 0x-prefixed 20-byte hex address: {pay_to!r}")

    amount_raw = entry.get("maxAmountRequired")
    amount: int | None = None
    if isinstance(amount_raw, str):
        # Strict wire format: ASCII digits only. int() alone also accepts
        # "+1", "1_000", whitespace and non-ASCII digits, which would make the
        # number the buyer signs diverge from what a strict facilitator parses.
        if not _AMOUNT_RE.fullmatch(amount_raw):
            problems.append(f"maxAmountRequired is not a plain decimal integer: {amount_raw!r}")
        else:
            amount = int(amount_raw)
            if amount <= 0:
                problems.append(f"maxAmountRequired must be > 0, got {amount}")
                amount = None
            elif amount > _UINT256_MAX:
                problems.append(f"maxAmountRequired exceeds uint256: {amount_raw!r}")
                amount = None
    else:
        problems.append(f"maxAmountRequired must be a string integer, got {amount_raw!r}")

    extra = entry.get("extra")
    if not isinstance(extra, dict):
        extra = {}
    domain_name = extra.get("name", "USDC")
    if not isinstance(domain_name, str):
        domain_name = "USDC"
    domain_version = extra.get("version", "2")
    if not isinstance(domain_version, str):
        domain_version = "2"

    if problems:
        return None, problems
    if chain_id is None or amount is None:
        # Defence in depth: the checks above should have caught this. An
        # `assert` here would be removed by `python -O`, silencing the guard in
        # exactly the deployment most likely to run optimised.
        return None, problems + ["internal: chain_id or amount unresolved"]
    validated = ValidatedAccepts(
        scheme="exact",
        network=network,
        chain_id=chain_id,
        asset=asset,
        pay_to=pay_to,
        amount_atomic=amount,
        domain_name=domain_name,
        domain_version=domain_version,
        _token=_CONSTRUCTION_TOKEN,
    )
    _register_validated(validated)
    return validated, []


class Signer(Protocol):
    """The out-of-process boundary: a payload goes out, a signature comes back.

    Implementations that touch key bytes must live OUTSIDE veritas/ — test
    doubles live in tests, real signers belong to the caller.
    """

    address: str

    def sign_typed_data(self, payload: dict) -> str:
        """Sign an EIP-712 typed-data payload, returning a hex signature."""
        ...


def build_authorization(
    validated: ValidatedAccepts,
    payer_address: str,
    now: int,
    validity_seconds: int = 60,
    nonce: str | None = None,
) -> dict:
    """Build the full EIP-712 typed-data payload for transferWithAuthorization.

    Every parameter that matters (chain, asset contract, recipient, value)
    comes from the validated challenge, never from free-form caller input.
    ``validAfter`` is ``now - 1`` so the authorization is immediately valid
    under EIP-3009's strict ``validAfter < ts < validBefore`` comparison;
    ``validBefore`` bounds replay exposure to ``validity_seconds`` — a bound
    that only holds if the caller bounds ``validity_seconds`` itself, as
    ``PaymentClient`` does (``MAX_VALIDITY_SECONDS``).

    A caller-supplied ``nonce`` makes the CALLER responsible for uniqueness:
    this function performs no duplicate detection, and two calls with the
    same nonce return identical, independently signable messages. Omit it
    (fresh 32-byte CSPRNG nonce) unless you are reconstructing a payload for
    audit. Raises ``ValueError`` on a non-positive ``now`` or
    ``validity_seconds`` — both would produce a window that can never be
    valid, or one that silently spans millennia on a milliseconds-for-seconds
    mistake.
    """
    if now <= 0:
        raise ValueError(f"now must be a positive unix timestamp in seconds, got {now}")
    if validity_seconds < 1:
        raise ValueError(f"validity_seconds must be >= 1, got {validity_seconds}")
    if nonce is None:
        nonce = "0x" + secrets.token_bytes(32).hex()
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": validated.domain_name,
            "version": validated.domain_version,
            "chainId": validated.chain_id,
            "verifyingContract": validated.asset,
        },
        "message": {
            "from": payer_address,
            "to": validated.pay_to,
            "value": str(validated.amount_atomic),
            "validAfter": str(now - 1),
            "validBefore": str(now + validity_seconds),
            "nonce": nonce,
        },
    }


@dataclass(frozen=True)
class PolicyDecision:
    """Outcome of one SpendPolicy check. ``check`` names the deciding rule."""

    allowed: bool
    check: str
    detail: str


class SpendPolicy:
    """Persistent spend caps in atomic units, enforced before any signature.

    State lives in ``<base_dir>/spend_policy.json`` and survives process
    restarts (a crashed and restarted buyer cannot double its daily budget).
    Counterparty ledger keys are case-folded: hex-address casing is
    meaningless on-chain, so every spelling of one address is one budget.
    Writes are atomic (temp file + rename) and, on POSIX, serialised with an
    advisory file lock plus a read-merge so several policy instances on one
    host sharing a state file accumulate rather than overwrite each other.

    Corrupt state fails closed: a file that exists but cannot be trusted
    latches the policy into ``corrupt_state`` and every authorization is
    refused until an operator repairs or removes it. An ABSENT file is a
    fresh start and is allowed — that distinction is the whole guard, since
    resetting to zero on damage would hand a full daily budget to anything
    able to damage the file.

    Residual gaps, stated plainly: a state file that is DELETED still starts
    a fresh budget (indistinguishable from first run); a failed WRITE keeps
    in-memory counters authoritative for this process only, so other
    processes and later restarts will not see that spend. Local disk is
    trusted. Cross-host enforcement needs shared state (roadmap 6.2), and
    the signer-side policy layer (3.2) is the backstop for all of this.
    """

    def __init__(
        self,
        max_per_request: int,
        max_per_day: int,
        max_per_day_per_counterparty: int | None = None,
        allowed_networks: set[str] | None = None,
        base_dir: Path | str | None = None,
    ) -> None:
        self.max_per_request = max_per_request
        self.max_per_day = max_per_day
        self.max_per_day_per_counterparty = max_per_day_per_counterparty
        self.allowed_networks = allowed_networks
        self._base_dir = resolve_runtime_dir(base_dir)
        self._state_corrupt: str | None = None
        self._date, self._spent, self._per_counterparty = self._load_state()

    # -- state -----------------------------------------------------------

    @property
    def _state_path(self) -> Path:
        return self._base_dir / _STATE_FILENAME

    @staticmethod
    def _today() -> str:
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    @staticmethod
    def _fold(pay_to: str) -> str:
        """Ledger key for a counterparty. Hex-address casing is meaningless
        on-chain; without folding, one recipient owns 2**40 fresh budgets."""
        return pay_to.lower()

    @staticmethod
    def _counter_ok(value: object) -> bool:
        # bool is an int subclass; True would silently load as 1.
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    def _load_state(self) -> tuple[str, int, dict[str, int]]:
        """Load persisted counters.

        Absent state is a fresh start and is allowed. State that EXISTS but
        cannot be trusted is different in kind: we cannot tell how much has
        already been spent today, so the policy latches into a corrupt state
        and refuses to authorize anything until an operator intervenes.
        Resetting to zero instead would hand a fresh daily budget to anyone
        (or anything) able to damage the file.
        """
        if not self._state_path.exists():
            self._state_corrupt = None
            return self._today(), 0, {}
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            date = raw["date"]
            spent = raw["spent"]
            per_counterparty = raw["per_counterparty"]
            if (
                not isinstance(date, str)
                or not _DATE_RE.fullmatch(date)
                or not self._counter_ok(spent)
                or not isinstance(per_counterparty, dict)
                or not all(
                    isinstance(k, str) and self._counter_ok(v)
                    for k, v in per_counterparty.items()
                )
            ):
                raise ValueError("state file has wrong shape or out-of-range counters")
            folded: dict[str, int] = {}
            for key, value in per_counterparty.items():
                fk = self._fold(key)
                folded[fk] = folded.get(fk, 0) + value
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._state_corrupt = f"{type(exc).__name__}: {str(exc)[:120]}"
            return self._today(), 0, {}
        self._state_corrupt = None
        return date, spent, folded

    def _merge_disk(self) -> None:
        """Fold the on-disk counters into memory, taking the maximum per
        counter. With locked read-modify-write in record(), disk carries the
        accumulated spend of every instance on this host; max() keeps our own
        unpersisted spend when the disk is stale or unwritable."""
        disk_date, disk_spent, disk_cp = self._load_state()
        if disk_date > self._date:
            self._roll_day(disk_date)
        if disk_date == self._date:
            self._spent = max(self._spent, disk_spent)
            for key, value in disk_cp.items():
                self._per_counterparty[key] = max(self._per_counterparty.get(key, 0), value)

    def _persist(self) -> None:
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
            tmp = self._state_path.with_suffix(".json.tmp")
            payload = json.dumps(
                {
                    "date": self._date,
                    "spent": self._spent,
                    "per_counterparty": self._per_counterparty,
                }
            )
            # Atomic rename prevents torn state; no fsync — losing the very
            # last write to an OS crash is the already-documented under-count
            # residual, and per-payment fsyncs are not worth their cost here.
            tmp.write_text(payload)
            os.replace(tmp, self._state_path)
        except OSError:
            # In-memory counters stay authoritative for this process; the
            # next authorize() must not under-count, so we swallow the write
            # failure rather than reset anything.
            pass

    def _locked(self):
        """Advisory exclusive lock on the state directory, when available."""

        class _Lock:
            def __init__(self, base_dir: Path) -> None:
                self._base_dir = base_dir
                self._fh = None

            def __enter__(self):
                if fcntl is not None:
                    try:
                        self._base_dir.mkdir(parents=True, exist_ok=True)
                        self._fh = (self._base_dir / ".spend_policy.lock").open("w")
                        fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
                    except OSError:
                        self._fh = None
                return self

            def __exit__(self, *exc):
                if self._fh is not None:
                    try:
                        fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                    finally:
                        self._fh.close()
                return False

        return _Lock(self._base_dir)

    def _roll_day(self, now_utc_date: str) -> None:
        # Forward-only: a caller-supplied earlier date must not reset the
        # day's counters (alternating dates would otherwise multiply the
        # daily budget without limit).
        if now_utc_date > self._date:
            self._date = now_utc_date
            self._spent = 0
            self._per_counterparty = {}

    # -- decisions -------------------------------------------------------

    def authorize(
        self,
        amount: int,
        network: str,
        pay_to: str,
        now_utc_date: str | None = None,
    ) -> PolicyDecision:
        """Check caps without consuming budget; record() charges after signing."""
        if now_utc_date is not None and not _DATE_RE.fullmatch(now_utc_date):
            return PolicyDecision(
                allowed=False,
                check="invalid_date",
                detail=f"now_utc_date is not YYYY-MM-DD: {now_utc_date!r}",
            )
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            return PolicyDecision(
                allowed=False,
                check="invalid_amount",
                detail=f"amount must be a positive integer, got {amount!r}",
            )
        self._roll_day(now_utc_date or self._today())
        self._merge_disk()
        if self._state_corrupt is not None:
            # We cannot establish today's spend, so we cannot bound it.
            return PolicyDecision(
                allowed=False,
                check="corrupt_state",
                detail=(
                    f"spend state at {self._state_path} is unreadable "
                    f"({self._state_corrupt}); refusing to authorize until it is "
                    "repaired or removed"
                ),
            )

        known = self.allowed_networks if self.allowed_networks is not None else set(USDC_ASSETS)
        if network not in known:
            return PolicyDecision(
                allowed=False,
                check="network_allowlist",
                detail=f"network {network!r} not in allowlist {sorted(known)}",
            )
        if amount > self.max_per_request:
            return PolicyDecision(
                allowed=False,
                check="per_request_cap",
                detail=f"amount {amount} exceeds per-request cap {self.max_per_request}",
            )
        if self._spent + amount > self.max_per_day:
            return PolicyDecision(
                allowed=False,
                check="per_day_cap",
                detail=(
                    f"amount {amount} + spent {self._spent} exceeds "
                    f"daily cap {self.max_per_day}"
                ),
            )
        if self.max_per_day_per_counterparty is not None:
            already = self._per_counterparty.get(self._fold(pay_to), 0)
            if already + amount > self.max_per_day_per_counterparty:
                return PolicyDecision(
                    allowed=False,
                    check="per_counterparty_cap",
                    detail=(
                        f"amount {amount} + {already} already sent to {pay_to} exceeds "
                        f"per-counterparty cap {self.max_per_day_per_counterparty}"
                    ),
                )
        return PolicyDecision(allowed=True, check="ok", detail="within all caps")

    def record(self, amount: int, pay_to: str, now_utc_date: str | None = None) -> None:
        """Charge the budget. Called only AFTER a successful signature.

        Locked read-modify-write: under the advisory lock the on-disk
        counters (which accumulate every instance's spend on this host) are
        merged in before the increment is added and persisted, so concurrent
        instances add up instead of overwriting each other.
        """
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise ValueError(f"record() amount must be a positive integer, got {amount!r}")
        with self._locked():
            self._roll_day(now_utc_date or self._today())
            self._merge_disk()
            key = self._fold(pay_to)
            self._spent += amount
            self._per_counterparty[key] = self._per_counterparty.get(key, 0) + amount
            self._persist()


@dataclass(frozen=True)
class PaymentResult:
    """Explicit outcome of a payment attempt; failures are results, not raises."""

    paid: bool
    denial: str | None
    check: str | None
    header: str | None
    authorization: dict | None
    nonce: str | None


def _denied(denial: str, check: str | None) -> PaymentResult:
    return PaymentResult(
        paid=False, denial=denial, check=check, header=None, authorization=None, nonce=None
    )


class PaymentClient:
    """Payment flow: validate → policy → journal → sign → record.

    The signer is the custody boundary — see the module docstring.

    Honest scope of the guards here:

    - ``_used_nonces`` is a per-instance, in-memory, defensive check. pay()
      always generates a fresh CSPRNG nonce, so a duplicate indicates RNG
      failure, not caller error; the set does not survive restarts, is not
      shared between instances or processes, and grows for the life of the
      instance. It is belt-and-braces, not replay protection.
    - A signer exception leaves the BUDGET untouched, but the outcome is
      indeterminate: the payload had already left the process, so a
      signature may exist that we never received. Every attempt is
      journalled to ``authorization_attempts.jsonl`` BEFORE the signer is
      called (fail-closed: an unwritable journal refuses the payment), so
      reconciliation against on-chain transfers (roadmap 0.3) can find
      orphan authorizations. A retry mints a new nonce — a second live
      authorization — so callers must bound retries and reconcile first.
    """

    def __init__(
        self,
        signer: Signer,
        policy: SpendPolicy,
        base_dir: Path | str | None = None,
        require_diligence: bool = False,
    ) -> None:
        self._signer = signer
        self._policy = policy
        self._used_nonces: set[str] = set()
        self._base_dir = Path(base_dir) if base_dir is not None else policy._base_dir
        # Off by default so every existing caller is unchanged. Turning it on
        # is the buyer's risk decision, not ours to make for them.
        self._require_diligence = require_diligence

    def _journal(self, entry: dict) -> bool:
        """Append one line to the attempt journal. Returns False on failure.

        Only the ``pre_sign`` line is fsynced: it is the one write whose loss
        to an OS crash could leave a live authorization undiscoverable.
        Outcome lines are best-effort refinements of it.
        """
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
            with (self._base_dir / _ATTEMPTS_FILENAME).open("a") as fh:
                fh.write(json.dumps(entry) + "\n")
                fh.flush()
                if entry.get("stage") == "pre_sign":
                    os.fsync(fh.fileno())
            return True
        except OSError:
            return False

    def pay(
        self,
        validated: ValidatedAccepts,
        now: int,
        validity_seconds: int = 60,
        now_utc_date: str | None = None,
        diligence: DiligenceReport | None = None,
    ) -> PaymentResult:
        """Attempt one payment. `now_utc_date` (YYYY-MM-DD) pins the policy
        day for deterministic callers (tests, the model checker); production
        callers omit it and the policy uses the real UTC date.

        `diligence` is a :class:`veritas.diligence.DiligenceReport` for the
        counterparty. It is consulted only when this client was constructed
        with ``require_diligence=True``, and a report that did not pass
        refuses the payment before the signer is reached."""
        if not isinstance(validated, ValidatedAccepts):
            return _denied("unvalidated_input", None)
        if not _is_registered(validated):
            # Not produced by validate_accepts — e.g. a dataclasses.replace()
            # copy with altered fields. Parameters must come from a validated
            # challenge, so refuse.
            return _denied("unvalidated_input", "unvalidated_input")
        if now <= 0 or not 1 <= validity_seconds <= MAX_VALIDITY_SECONDS:
            return _denied(
                f"validity window rejected: now={now}, "
                f"validity_seconds={validity_seconds} (allowed 1..{MAX_VALIDITY_SECONDS})",
                "invalid_validity_window",
            )

        # Counterparty diligence, deliberately placed BEFORE the spend policy.
        # A seller refused here consumes no budget, is never journalled, and
        # never reaches the signer — otherwise a hostile counterparty could
        # burn a buyer's daily allowance with challenges destined to be
        # refused, and every refusal would leave a phantom authorization in
        # the journal that reconciliation would go looking for on-chain.
        if self._require_diligence:
            # Imported here, not at module scope: veritas.diligence imports
            # validate_accepts from this module.
            from .diligence import Verdict

            if diligence is None:
                return _denied(
                    "counterparty diligence is required but none was supplied",
                    "diligence",
                )
            if diligence.verdict != Verdict.PASS:
                # The verdict is carried verbatim so a buyer can separate
                # "this seller failed" from "I could not check this seller".
                # They are different facts and they call for different action.
                return _denied(
                    f"counterparty diligence {diligence.verdict}: "
                    + "; ".join(diligence.reasons),
                    "diligence",
                )

        decision = self._policy.authorize(
            validated.amount_atomic, validated.network, validated.pay_to,
            now_utc_date=now_utc_date,
        )
        if not decision.allowed:
            return _denied(decision.detail, decision.check)

        payload = build_authorization(
            validated, self._signer.address, now, validity_seconds
        )
        nonce = payload["message"]["nonce"]
        if nonce in self._used_nonces:
            return _denied("nonce_reuse", "nonce_reuse")

        # Write-ahead of the signer call: once the payload leaves the
        # process a signature may exist even if we never hear back, so the
        # attempt must be durably discoverable BEFORE that can happen.
        journalled = self._journal({
            "nonce": nonce,
            "amount": validated.amount_atomic,
            "pay_to": validated.pay_to,
            "network": validated.network,
            "valid_before": payload["message"]["validBefore"],
            "stage": "pre_sign",
        })
        if not journalled:
            return _denied("attempt journal unwritable; refusing to sign", "journal_error")

        try:
            signature = self._signer.sign_typed_data(payload)
        except Exception as exc:  # budget untouched; outcome INDETERMINATE (see docstring)
            self._journal({"nonce": nonce, "stage": f"signer_error:{type(exc).__name__}"})
            return _denied(f"signer_error:{type(exc).__name__}", "signer_error")

        self._used_nonces.add(nonce)
        self._journal({"nonce": nonce, "stage": "signed"})
        self._policy.record(validated.amount_atomic, validated.pay_to, now_utc_date=now_utc_date)
        header = base64.b64encode(
            json.dumps(
                {
                    "x402Version": 1,
                    "scheme": "exact",
                    "network": validated.network,
                    "payload": {
                        "signature": signature,
                        "authorization": payload["message"],
                    },
                }
            ).encode()
        ).decode()
        return PaymentResult(
            paid=True,
            denial=None,
            check="ok",
            header=header,
            authorization=payload,
            nonce=nonce,
        )
