"""A work budget bounded by the payment authorization that pays for it.

The audited defect (R4): a 402 challenge advertises `maxTimeoutSeconds: 60` and
a buyer signs `validBefore = now + 60`, but the server enforced no deadline at
all between verifying the payment and settling it. Retrieval could take longer
than the window — Wikipedia search, two summary fetches, a keyed provider and a
fallback all ran serially with their own timeouts — so slow requests settled
against an authorization that had already expired. The work was done, the nonce
was burned, and nobody was paid.

Two rules follow:

* Never start work that cannot finish inside the authorization. Refusing before
  the work costs the buyer nothing; refusing after costs them the whole request.
* Always leave time to settle. A deadline that consumes the entire window leaves
  no room for the settle call the work exists to enable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

# Time reserved after the work for the facilitator settle round-trip. The
# facilitator client's own timeout is 15s, so this must comfortably exceed it.
SETTLEMENT_MARGIN_SECONDS = 20

# Below this much usable time there is no point starting: any real retrieval
# pass would overrun and the buyer would be charged for nothing.
MIN_USABLE_SECONDS = 5


class DeadlineTooShort(ValueError):
    """The authorization does not leave enough time to do the work and settle."""


@dataclass(frozen=True)
class Deadline:
    """An absolute point in time by which work must stop."""

    expires_at: float

    @classmethod
    def for_authorization(
        cls,
        valid_before: float,
        now: float | None = None,
        max_work_seconds: float = 60,
    ) -> Deadline:
        """Budget for one paid request.

        `valid_before` is the buyer's EIP-3009 authorization expiry. The budget
        is the earlier of our own work cap and the authorization window minus a
        settlement margin — whichever leaves less time, wins.
        """
        now = time.time() if now is None else now
        settle_by = valid_before - SETTLEMENT_MARGIN_SECONDS
        expires_at = min(now + max_work_seconds, settle_by)
        if expires_at - now < MIN_USABLE_SECONDS:
            raise DeadlineTooShort(
                f"authorization leaves {settle_by - now:.1f}s of usable time "
                f"(need at least {MIN_USABLE_SECONDS}s plus a "
                f"{SETTLEMENT_MARGIN_SECONDS}s settlement margin)"
            )
        return cls(expires_at=expires_at)

    @classmethod
    def after(cls, seconds: float, now: float | None = None) -> Deadline:
        """A plain budget, for unpaid work that still must not run unbounded."""
        now = time.time() if now is None else now
        return cls(expires_at=now + seconds)

    def seconds_remaining(self, now: float | None = None) -> float:
        now = time.time() if now is None else now
        return max(0.0, self.expires_at - now)

    def expired(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        return now >= self.expires_at

    def timeout_for(self, per_call_ceiling: float, now: float | None = None) -> float:
        """The timeout to hand one outbound call, never exceeding what is left."""
        return max(0.0, min(per_call_ceiling, self.seconds_remaining(now)))
