"""Structured logs and counters, with no new dependencies.

Defect O9: the service had no logging, metrics, tracing or alerting of any
kind. Once it started shedding load under pressure that became urgent — load
shedding nobody can see is indistinguishable from an outage, and the operator
learns about it from a buyer complaint.

Two constraints shape this module, and both are about what must *not* appear.

**Buyer queries never reach a log line.** A query is the buyer's business. It
is already retained in a custody receipt, which is a record they can have
erased; a log file is the one place that erasure would not reach. So the
access log carries method, path, status, duration and request id — never the
body, never the query, never the `X-PAYMENT` header.

**Counters are not public.** `veritas_settlements_total` is a revenue figure.
`/metrics` therefore does not exist until `VERITAS_METRICS_TOKEN` is set, and
requires that token when it does. Publishing a competitor's view of the
business by default would be a strange thing for a service whose product is
carefulness about what it discloses.

Prometheus text exposition is used rather than JSON because that is what an
operator's monitoring actually scrapes, and it is self-describing (HELP/TYPE)
and trivially parseable by an agent too.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

ACCESS_LOGGER = "veritas.access"

#: Metric name → (type, help text). Declaring them keeps HELP/TYPE lines
#: honest and stops a typo silently creating a second series.
METRIC_HELP: dict[str, tuple[str, str]] = {
    "veritas_requests_total": ("counter", "HTTP requests by path and response status."),
    "veritas_research_total": ("counter", "Research requests by outcome status."),
    "veritas_research_shed_total": (
        "counter",
        "Research requests refused because every concurrency slot was in use.",
    ),
    "veritas_rate_limited_total": ("counter", "Requests refused by the per-caller rate limit."),
    "veritas_request_too_large_total": ("counter", "Requests refused for exceeding the body cap."),
    "veritas_settlements_total": ("counter", "Settlement attempts by outcome."),
    "veritas_research_duration_ms_sum": ("counter", "Total research handler time in milliseconds."),
    "veritas_research_duration_ms_count": ("counter", "Research handler invocations timed."),
}


def _escape(value: str) -> str:
    """Escape a Prometheus label value.

    The exposition format is line-oriented, so an unescaped value containing a
    quote or a newline lets a caller-controlled string (a request path) forge
    whole metric lines.
    """
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
    )


class Metrics:
    """In-process counters. Locked, because handlers run in a threadpool.

    Single-instance scope, like everything else in this service that keeps
    state on the box: behind a load balancer each node counts only itself.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = {}

    @staticmethod
    def _key(name: str, labels: dict[str, str] | None):
        return (name, tuple(sorted((labels or {}).items())))

    def increment(self, name: str, labels: dict[str, str] | None = None, by: int = 1) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + by

    def value(self, name: str, labels: dict[str, str] | None = None) -> int:
        with self._lock:
            return self._counters.get(self._key(name, labels), 0)

    def render(self) -> str:
        """Prometheus text exposition.

        Every declared metric appears even at zero. A series that only springs
        into existence after the first occurrence makes "no shed requests" and
        "shedding is not instrumented" look identical to a scraper, which is
        the failure mode this module exists to prevent. Labelled series cannot
        be pre-declared without inventing label values, so they appear on
        first use.
        """
        with self._lock:
            snapshot = dict(self._counters)
        names = sorted(set(METRIC_HELP) | {n for n, _ in snapshot})
        lines: list[str] = []
        for name in names:
            kind, help_text = METRIC_HELP.get(name, ("counter", "Undeclared metric."))
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} {kind}")
            series = sorted((k, v) for k, v in snapshot.items() if k[0] == name)
            if not series:
                lines.append(f"{name} 0")
                continue
            for (_metric, labels), count in series:
                if labels:
                    rendered = ",".join(f'{k}="{_escape(v)}"' for k, v in labels)
                    lines.append(f"{name}{{{rendered}}} {count}")
                else:
                    lines.append(f"{name} {count}")
        return "\n".join(lines) + "\n"


class JsonFormatter(logging.Formatter):
    """One JSON object per line. Structured fields travel on `record.fields`."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            entry.update(fields)
        if record.exc_info:
            # Type only. The traceback names server internals and this stream
            # may be shipped somewhere less private than the process.
            entry["exception"] = record.exc_info[0].__name__ if record.exc_info[0] else "unknown"
        return json.dumps(entry, default=str)


def format_record(record: logging.LogRecord) -> str:
    """Render one record the way the configured formatter would.

    Exists so tests can assert on the emitted line without depending on which
    handler the root logger happens to carry.
    """
    return JsonFormatter().format(record)


def log_request(**fields: Any) -> None:
    """Emit one access-log line. Callers pass only non-sensitive fields."""
    logging.getLogger(ACCESS_LOGGER).info("request", extra={"fields": fields})


def configure_logging(level: str | None = None, fmt: str | None = None) -> None:
    """Attach a JSON (or plain) handler to the root logger, once.

    Called from the server entry point rather than at import, so importing
    `veritas.server` in a test or a notebook does not reconfigure the host
    application's logging.
    """
    import os

    level = level or os.getenv("VERITAS_LOG_LEVEL", "INFO")
    fmt = (fmt or os.getenv("VERITAS_LOG_FORMAT", "json")).lower()
    root = logging.getLogger()
    for handler in root.handlers:
        if getattr(handler, "_veritas", False):
            return
    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter() if fmt == "json"
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    handler._veritas = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level.upper())
