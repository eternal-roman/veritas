"""robots.txt → fetch allowance classification.

A robots *deny* is a first-class signal on every EvidenceRecord policy stamp:
it is never collapsed into allow. When robots.txt was not obtained, allowance
is ``unknown`` (fail-closed for automated fetch), not assumed allow.

This module is pure: it classifies a body the caller already holds. Network
I/O belongs to fetch/observe. An operator may attach an **explicit override**
class — never an implicit bypass that erases the underlying deny.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser


class FetchClass:
    """Fetch allowance classes. Plain strings for JSON records."""

    ALLOWED = "allowed"
    DENIED = "denied"
    UNKNOWN = "unknown"  # robots body missing / unusable — not assumed allow
    OVERRIDE = "override"  # explicit operator override; underlying still recorded


@dataclass(frozen=True)
class RobotsDecision:
    """Classified fetch allowance for one (user-agent, path) pair."""

    allowance: str
    user_agent: str
    path: str
    detail: str
    matched_rule: str | None = None
    underlying: str | None = None
    override: str | None = None
    assumed_allow: bool = False

    @property
    def may_fetch(self) -> bool:
        """Whether automated fetch is classified as free to proceed.

        ALLOWED and OVERRIDE permit. DENIED and UNKNOWN refuse (fail-closed).
        """
        return self.allowance in (FetchClass.ALLOWED, FetchClass.OVERRIDE)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowance": self.allowance,
            "user_agent": self.user_agent,
            "path": self.path,
            "detail": self.detail,
            "matched_rule": self.matched_rule,
            "underlying": self.underlying,
            "override": self.override,
            "assumed_allow": self.assumed_allow,
            "may_fetch": self.may_fetch,
        }


@dataclass(frozen=True)
class RobotsRules:
    """Parsed robots body. No network; evaluate paths offline."""

    body: str
    _parser: RobotFileParser

    def evaluate(self, url_or_path: str, user_agent: str) -> RobotsDecision:
        path = _request_target(url_or_path)
        allowed = self._parser.can_fetch(user_agent, path)
        if allowed:
            return RobotsDecision(
                allowance=FetchClass.ALLOWED,
                user_agent=user_agent,
                path=path,
                detail="robots.txt permits this path for the user-agent",
                matched_rule=None,
                assumed_allow=False,
            )
        return RobotsDecision(
            allowance=FetchClass.DENIED,
            user_agent=user_agent,
            path=path,
            detail="robots.txt disallows this path for the user-agent",
            matched_rule="disallow",
            assumed_allow=False,
        )


def _request_target(url_or_path: str) -> str:
    """Normalise to a path RobotFileParser can match.

    Accepts absolute URLs or path-only targets. An empty path becomes ``/``.
    """
    text = (url_or_path or "").strip()
    if not text:
        return "/"
    if "://" in text:
        parts = urlsplit(text)
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"
        return path
    if not text.startswith("/"):
        return "/" + text
    return text


def _is_effectively_empty(body: str) -> bool:
    """True when the body has no directive lines (comments/whitespace only)."""
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return False
    return True


def parse_robots(body: str) -> RobotsRules:
    """Parse a robots.txt body. Does not fetch; does not default missing bodies."""
    if body is None:  # type: ignore[comparison-overlap]
        raise TypeError("parse_robots requires a str body; use evaluate_robots for missing")
    parser = RobotFileParser()
    # RobotFileParser expects iterable lines; set a dummy URL so path matching works.
    parser.set_url("https://robots.invalid/robots.txt")
    parser.parse(body.splitlines())
    return RobotsRules(body=body, _parser=parser)


def evaluate_robots(
    body: str | None,
    url_or_path: str,
    user_agent: str,
    *,
    override: str | None = None,
) -> RobotsDecision:
    """Classify fetch allowance for ``user_agent`` against ``url_or_path``.

    * ``body is None`` → ``unknown`` (robots not obtained). Fail-closed.
    * empty / comments-only body → ``allowed`` (RFC treat-as-allow-all).
    * Disallow match → ``denied``. Never silently remapped to allow.
    * ``override`` set to a non-empty reason → ``override`` class; the
      underlying allowance is still recorded so a deny is not erased.
    """
    if override is not None and not str(override).strip():
        raise ValueError("override must be a non-empty reason, or None")

    path = _request_target(url_or_path)
    ua = user_agent or "*"

    if body is None:
        base = RobotsDecision(
            allowance=FetchClass.UNKNOWN,
            user_agent=ua,
            path=path,
            detail="robots.txt not obtained; fetch allowance unknown (not assumed allow)",
            matched_rule=None,
            assumed_allow=False,
        )
    elif _is_effectively_empty(body):
        base = RobotsDecision(
            allowance=FetchClass.ALLOWED,
            user_agent=ua,
            path=path,
            detail="robots.txt empty or comments-only; treat as allow-all",
            matched_rule=None,
            assumed_allow=False,
        )
    else:
        base = parse_robots(body).evaluate(path, ua)

    if override is None:
        return base

    reason = str(override).strip()
    return RobotsDecision(
        allowance=FetchClass.OVERRIDE,
        user_agent=base.user_agent,
        path=base.path,
        detail=f"explicit override ({reason}); underlying={base.allowance}",
        matched_rule=base.matched_rule,
        underlying=base.allowance,
        override=reason,
        assumed_allow=False,
    )


__all__ = [
    "FetchClass",
    "RobotsDecision",
    "RobotsRules",
    "evaluate_robots",
    "parse_robots",
]
