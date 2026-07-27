"""Replay protection for x402 payment authorizations (roadmap 0.4).

An EIP-3009 authorization carries a single-use nonce, and the token contract
burns it on settlement — so a resubmitted `X-PAYMENT` header cannot move funds
twice. What it *can* do is make us perform the paid work twice: the service
verifies, runs a full retrieval pass, and only then discovers the settlement
was already spent. The cost of the second pass is ours, the revenue is not.

This module records nonces at the moment they are first accepted, so a
duplicate is refused *before* a retrieval pass is consumed.

Design choices, and why:

- **Claim before work, never release.** A nonce is claimed once verification
  passes and before research runs. It is not released if the request later
  fails: the authorization it names is still live on chain, so treating it as
  spendable again would reintroduce exactly the double-work this prevents.
- **Fail closed.** If the store cannot be read or written, the claim is
  refused. An unavailable replay guard must not silently become no guard —
  the alternative is unbounded duplicate work under the one condition
  (disk trouble) where we are least able to absorb it.
- **Single-instance scope, stated plainly.** The store is local disk, so it
  guards one instance. Behind a load balancer, two instances do not share it;
  that needs the shared state in roadmap 6.2. This is a real limit, not a
  closed problem.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:  # advisory same-host locking; absent on some platforms
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None  # type: ignore[assignment]

_DEFAULT_RUNTIME_DIR = ".veritas_runtime"
_STORE_FILENAME = "spent_nonces.jsonl"
_NONCE_RE = re.compile(r"0x[0-9a-fA-F]{64}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ClaimResult:
    """Outcome of trying to claim a nonce. Failures are results, not raises."""

    claimed: bool
    reason: str | None = None
    nonce: str | None = None


def extract_nonce(payment_payload: dict) -> str | None:
    """Pull the authorization nonce out of a decoded X-PAYMENT payload.

    Tolerates the two shapes seen in the wild: the nonce nested under
    ``payload.authorization`` (x402 exact scheme) or hoisted to the top of the
    payload. Returns None when no well-formed nonce is present — the caller
    decides what that means, because a missing nonce is a malformed payment,
    not a replay.
    """
    if not isinstance(payment_payload, dict):
        return None
    candidates = []
    payload = payment_payload.get("payload")
    if isinstance(payload, dict):
        authorization = payload.get("authorization")
        if isinstance(authorization, dict):
            candidates.append(authorization.get("nonce"))
        candidates.append(payload.get("nonce"))
    candidates.append(payment_payload.get("nonce"))
    for candidate in candidates:
        if isinstance(candidate, str) and _NONCE_RE.fullmatch(candidate):
            return candidate.lower()
    return None


class SpentNonceStore:
    """Durable record of payment nonces this instance has already accepted."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(
            base_dir or os.getenv("VERITAS_RUNTIME_DIR") or _DEFAULT_RUNTIME_DIR
        )

    @property
    def path(self) -> Path:
        return self.base_dir / _STORE_FILENAME

    def _spent(self) -> set[str]:
        """Every nonce recorded so far. Raises OSError if unreadable."""
        seen: set[str] = set()
        if not self.path.exists():
            return seen
        with self.path.open() as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    # A torn final line is survivable: skip it rather than
                    # discarding every nonce recorded before it.
                    continue
                nonce = entry.get("nonce")
                if isinstance(nonce, str):
                    seen.add(nonce)
        return seen

    def is_spent(self, nonce: str) -> bool:
        try:
            return nonce.lower() in self._spent()
        except OSError:
            # Unknown is not the same as unspent; the caller fails closed.
            raise

    def claim(self, nonce: str | None, request_id: str | None = None) -> ClaimResult:
        """Claim a nonce for one request. Idempotent per nonce, fail-closed.

        Returns claimed=False with a named reason when the nonce is missing,
        malformed, already spent, or the store is unusable.
        """
        if nonce is None:
            return ClaimResult(False, "payment_nonce_missing")
        if not _NONCE_RE.fullmatch(nonce):
            return ClaimResult(False, "payment_nonce_malformed")
        key = nonce.lower()
        try:
            with _lock(self.base_dir):
                if key in self._spent():
                    return ClaimResult(False, "payment_nonce_already_spent", key)
                self.base_dir.mkdir(parents=True, exist_ok=True)
                with self.path.open("a") as fh:
                    fh.write(json.dumps({
                        "nonce": key,
                        "request_id": request_id,
                        "claimed_at": _now(),
                    }) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
        except OSError as exc:
            return ClaimResult(False, f"replay_store_unavailable: {str(exc)[:120]}")
        return ClaimResult(True, None, key)


class _lock:
    """Advisory exclusive lock so concurrent claims cannot both win."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._fh = None

    def __enter__(self):
        if fcntl is not None:
            self._base_dir.mkdir(parents=True, exist_ok=True)
            self._fh = (self._base_dir / ".spent_nonces.lock").open("w")
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if self._fh is not None:
            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._fh.close()
        return False
