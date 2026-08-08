"""Retention window configuration: no silent mass-delete."""

from __future__ import annotations

import pytest

from veritas.retention import (
    DEFAULT_RETENTION_DAYS,
    RetentionConfigError,
    is_expired,
    retention_cutoff,
    retention_days_from_env,
)


def test_default_retention_is_thirty_days(monkeypatch):
    monkeypatch.delenv("VERITAS_RETENTION_DAYS", raising=False)
    assert retention_days_from_env() == DEFAULT_RETENTION_DAYS == 30


def test_env_override_is_honoured(monkeypatch):
    monkeypatch.setenv("VERITAS_RETENTION_DAYS", "7")
    assert retention_days_from_env() == 7


@pytest.mark.parametrize("raw", ["0", "-1", "99999", "abc", "", "  "])
def test_nonsense_retention_is_rejected(raw):
    with pytest.raises(RetentionConfigError):
        retention_days_from_env(raw)


def test_cutoff_is_injectable_for_tests():
    from datetime import datetime, timezone

    now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    cutoff = retention_cutoff(days=30, now=now)
    assert cutoff == datetime(2024, 5, 16, 12, 0, 0, tzinfo=timezone.utc)


def test_unparseable_timestamp_is_never_expired():
    from datetime import datetime, timezone

    cutoff = datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert is_expired("not-a-date", cutoff) is False
    assert is_expired(None, cutoff) is False
    assert is_expired("2020-01-01T00:00:00Z", cutoff) is True
    assert is_expired("2025-01-01T00:00:00Z", cutoff) is False
