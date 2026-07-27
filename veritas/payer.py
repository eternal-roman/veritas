"""Buyer-side x402 payment machinery with key-custody inversion.

The load-bearing design decision: no key material ever exists in this
process. This module constructs the full EIP-712 typed-data payload for an
EIP-3009 ``transferWithAuthorization``; the payload travels OUT to a signer
(hardware wallet, remote signing service, agent-held key outside this
process) and only a hex signature comes back. Nothing here reads, stores, or
derives a signing key, and the test suite greps this file to keep it that way.

Two policy layers gate every payment:

1. Validation — :func:`validate_accepts` is the only constructor of
   :class:`ValidatedAccepts`, so authorization parameters (network, asset,
   recipient, amount) can only come from a structurally validated 402
   challenge, never from raw caller input.
2. Spend caps — :class:`SpendPolicy` enforces per-request, per-day, and
   per-counterparty limits that persist across process restarts.

Limits, stated plainly: the ``ValidatedAccepts`` construction token is a
structural guard, not a cryptographic one — deliberate internal code can
bypass it (the bounded model checker in
``veritas.evaluations.payment_model`` exercises the honest paths). Failures
are explicit results, never control-flow exceptions.
"""

from __future__ import annotations

import base64
import datetime
import json
import os
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from veritas.x402 import USDC_ASSETS

_CONSTRUCTION_TOKEN = object()

_CAIP2_RE = re.compile(r"eip155:\d+")
_ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]{40}")

_STATE_FILENAME = "spend_policy.json"
_DEFAULT_RUNTIME_DIR = ".veritas_runtime"


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
        try:
            amount = int(amount_raw)
        except ValueError:
            problems.append(f"maxAmountRequired does not parse as an integer: {amount_raw!r}")
        else:
            if amount <= 0:
                problems.append(f"maxAmountRequired must be > 0, got {amount}")
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
    assert chain_id is not None and amount is not None  # narrowed by the checks above
    return (
        ValidatedAccepts(
            scheme="exact",
            network=network,
            chain_id=chain_id,
            asset=asset,
            pay_to=pay_to,
            amount_atomic=amount,
            domain_name=domain_name,
            domain_version=domain_version,
            _token=_CONSTRUCTION_TOKEN,
        ),
        [],
    )


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
    ``validAfter`` is ``now - 1`` so the authorization is immediately valid;
    ``validBefore`` bounds replay exposure to ``validity_seconds``.
    """
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
    Fail-closed choices: a corrupt or unreadable state file is treated as a
    fresh day (caps still enforced from zero); a failed state WRITE keeps the
    in-memory counters authoritative for this process so we never under-count.
    The residual gap is honest: if the state file is lost AND the process
    restarts, that day's already-spent amount is forgotten.
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
        self._base_dir = Path(
            base_dir or os.environ.get("VERITAS_RUNTIME_DIR") or _DEFAULT_RUNTIME_DIR
        )
        self._date, self._spent, self._per_counterparty = self._load_state()

    # -- state -----------------------------------------------------------

    @property
    def _state_path(self) -> Path:
        return self._base_dir / _STATE_FILENAME

    @staticmethod
    def _today() -> str:
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    def _load_state(self) -> tuple[str, int, dict[str, int]]:
        try:
            raw = json.loads(self._state_path.read_text())
            date = raw["date"]
            spent = raw["spent"]
            per_counterparty = raw["per_counterparty"]
            if (
                not isinstance(date, str)
                or not isinstance(spent, int)
                or not isinstance(per_counterparty, dict)
                or not all(
                    isinstance(k, str) and isinstance(v, int)
                    for k, v in per_counterparty.items()
                )
            ):
                raise ValueError("state file has wrong shape")
            return date, spent, dict(per_counterparty)
        except (OSError, ValueError, KeyError, TypeError):
            # Fail closed toward a fresh day: caps are still enforced from
            # zero; we never crash the buyer over unreadable bookkeeping.
            return self._today(), 0, {}

    def _persist(self) -> None:
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(
                json.dumps(
                    {
                        "date": self._date,
                        "spent": self._spent,
                        "per_counterparty": self._per_counterparty,
                    }
                )
            )
        except OSError:
            # In-memory counters stay authoritative for this process; the
            # next authorize() must not under-count, so we swallow the write
            # failure rather than reset anything.
            pass

    def _roll_day(self, now_utc_date: str) -> None:
        if now_utc_date != self._date:
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
        self._roll_day(now_utc_date or self._today())

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
            already = self._per_counterparty.get(pay_to, 0)
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

    def record(self, amount: int, pay_to: str) -> None:
        """Charge the budget. Called only AFTER a successful signature."""
        self._spent += amount
        self._per_counterparty[pay_to] = self._per_counterparty.get(pay_to, 0) + amount
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
    """Fail-closed payment flow: validate → policy → build → sign → record.

    The signer is the custody boundary — see the module docstring. Any signer
    exception fails closed with the budget untouched. Nonces are tracked
    in-process and a duplicate is refused outright: signing the same nonce
    twice would hand out a replayable authorization.
    """

    def __init__(self, signer: Signer, policy: SpendPolicy) -> None:
        self._signer = signer
        self._policy = policy
        self._used_nonces: set[str] = set()

    def pay(
        self,
        validated: ValidatedAccepts,
        now: int,
        validity_seconds: int = 60,
        now_utc_date: str | None = None,
    ) -> PaymentResult:
        """Attempt one payment. `now_utc_date` (YYYY-MM-DD) pins the policy
        day for deterministic callers (tests, the model checker); production
        callers omit it and the policy uses the real UTC date."""
        if not isinstance(validated, ValidatedAccepts):
            return _denied("unvalidated_input", None)

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

        try:
            signature = self._signer.sign_typed_data(payload)
        except Exception as exc:  # fail closed on ANY signer failure
            return _denied(f"signer_error:{type(exc).__name__}", "signer_error")

        self._used_nonces.add(nonce)
        self._policy.record(validated.amount_atomic, validated.pay_to)
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
