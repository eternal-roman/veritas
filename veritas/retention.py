"""Retention window for receipts, ledger rows, and related durable state.

Disk is the first production failure mode if receipts and ledger rows grow
without bound. This module is the single place that turns configuration into
a cutoff: ops-scheduled prune jobs share it so custody and the ledger age
together, and tests inject a cutoff without rewriting wall clocks.

Rules:

- Default is 30 days (`VERITAS_RETENTION_DAYS`).
- Nonsense values (zero, negative, non-integer, absurdly large) raise rather
  than silently becoming a mass-delete or "keep forever".
- Prune itself is not on the request path — latency and DoS belong to ops.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

DEFAULT_RETENTION_DAYS = 30
#: Floor: zero or negative would delete everything on the next prune.
MIN_RETENTION_DAYS = 1
#: Ceiling: ~10 years. Above this is almost certainly a typo (days vs seconds).
MAX_RETENTION_DAYS = 3650

ENV_VAR = "VERITAS_RETENTION_DAYS"


class RetentionConfigError(ValueError):
    """The configured retention window is not usable."""


def retention_days_from_env(raw: str | None = None) -> int:
    """Read and validate the retention window in whole days.

    Pass `raw` to validate a value without touching the environment (tests).
    Raises `RetentionConfigError` on missing-sense inputs so a misconfigured
    operator never silently wipes the store.
    """
    if raw is None:
        raw = os.getenv(ENV_VAR, str(DEFAULT_RETENTION_DAYS))
    text = (raw if raw is not None else "").strip()
    if not text:
        raise RetentionConfigError(f"{ENV_VAR} is empty")
    try:
        days = int(text)
    except ValueError as exc:
        raise RetentionConfigError(
            f"{ENV_VAR} must be an integer number of days, got {raw!r}"
        ) from exc
    if days < MIN_RETENTION_DAYS or days > MAX_RETENTION_DAYS:
        raise RetentionConfigError(
            f"{ENV_VAR} must be between {MIN_RETENTION_DAYS} and "
            f"{MAX_RETENTION_DAYS} inclusive, got {days}"
        )
    return days


def retention_cutoff(
    *,
    days: int | None = None,
    now: datetime | None = None,
) -> datetime:
    """UTC instant before which durable artifacts are expired.

    `days` and `now` are injectable so tests pin a deterministic cutoff without
    freezegun. When `days` is omitted the environment is read and validated.
    """
    window = days if days is not None else retention_days_from_env()
    if window < MIN_RETENTION_DAYS or window > MAX_RETENTION_DAYS:
        raise RetentionConfigError(
            f"retention days must be between {MIN_RETENTION_DAYS} and "
            f"{MAX_RETENTION_DAYS} inclusive, got {window}"
        )
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    else:
        moment = moment.astimezone(timezone.utc)
    return moment - timedelta(days=window)


def parse_utc(timestamp: object) -> datetime | None:
    """Parse a stored ISO-8601 timestamp to UTC, or None if unusable.

    Unparseable values must not be treated as expired: silent mass-delete of
    every row whose clock format we do not recognise would be a worse failure
    than leaving a few forever.
    """
    if not isinstance(timestamp, str) or not timestamp:
        return None
    text = timestamp.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_expired(timestamp: object, cutoff: datetime) -> bool:
    """True when `timestamp` is strictly older than `cutoff`.

    Unparseable timestamps are never expired (see `parse_utc`).
    """
    parsed = parse_utc(timestamp)
    if parsed is None:
        return False
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    else:
        cutoff = cutoff.astimezone(timezone.utc)
    return parsed < cutoff
