#!/usr/bin/env python3
"""Generate hash-pinned lockfiles from pip's own resolver.

Why this exists
---------------
``requirements.txt`` and ``requirements-dev.txt`` state *floors* (``>=``), so
two CI runs of the same commit can install different dependency trees. That
makes a green run a statement about one moment on PyPI rather than about the
commit, and it means a compromised release of any transitive dependency lands
in CI with no review. The lockfiles pin every package in the closure to an
exact version and a SHA-256 of the artifact, and CI installs with
``--require-hashes``, so a substituted artifact fails the install instead of
running.

Outputs
-------
* ``requirements.lock`` — runtime closure from ``requirements.txt``
* ``requirements-dev.lock`` — runtime + dev/CI tools from ``requirements-dev.txt``

Why it refuses to run off-target
--------------------------------
pip resolves *versions* against the tags you ask for, but evaluates
**environment markers against the running interpreter**. Generating this lock
on Windows silently produces a Windows tree: it gains ``pywin32-ctypes`` and
loses ``SecretStorage``/``jeepney``, which ``twine``'s ``keyring`` dependency
requires only on Linux. Installing that lock on CI fails, because pip needs a
package the lock has no hash for.

Rather than detect that afterwards, this script refuses to write a lock unless
it is running on the platform the lock declares. A wrong lock cannot be
produced, which is the same fail-closed posture the service takes toward
misconfigured payment. On Windows, generate under Docker:

    docker run --rm -v "%CD%":/src -w /src python:3.12-bookworm \\
      bash -c "pip install -q -U pip && python scripts/lock_requirements.py"

Usage
-----
    python scripts/lock_requirements.py                # write both lockfiles
    python scripts/lock_requirements.py --check        # verify committed locks
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The environment CI actually runs. Both halves are asserted before writing:
# the lock is only correct for the platform whose markers produced it.
TARGET_PLATFORM = "linux"
TARGET_PYTHON = (3, 12)

LOCK_SPECS: tuple[tuple[str, str], ...] = (
    ("requirements.txt", "requirements.lock"),
    ("requirements-dev.txt", "requirements-dev.lock"),
)

HEADER = """\
# Hash-pinned dependency lock. GENERATED — do not edit by hand.
#
# Regenerate:  python scripts/lock_requirements.py
#   (on Linux CPython {py_major}.{py_minor}; from Windows use Docker — see SECURITY.md)
# Verify:      python scripts/lock_requirements.py --check
#
# Source:   {source}
# Target:   CPython {py_major}.{py_minor} on {platform}  (ubuntu-latest, as CI runs)
# Packages: {count}
#
# Every entry is pinned to an exact version and the SHA-256 of the artifact pip
# resolved. CI installs with --require-hashes, so a tampered or resubstituted
# artifact fails the install rather than executing.
#
# This lock is target-specific: environment markers were evaluated on
# {platform}. It is NOT the developer install path — use `pip install -e
# ".[signing,dev]"` for that. scripts/lock_requirements.py refuses to generate
# this file anywhere but the target platform, so it cannot be silently
# regenerated into a tree CI will reject.
"""


def _fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def _assert_on_target() -> None:
    """Refuse to generate a lock whose markers came from the wrong platform."""
    problems = []
    if not sys.platform.startswith(TARGET_PLATFORM):
        problems.append(
            f"platform is {sys.platform!r}, lock targets {TARGET_PLATFORM!r}"
        )
    if sys.version_info[:2] != TARGET_PYTHON:
        running = f"{sys.version_info[0]}.{sys.version_info[1]}"
        target = f"{TARGET_PYTHON[0]}.{TARGET_PYTHON[1]}"
        problems.append(f"Python is {running}, lock targets {target}")
    if problems:
        _fail(
            "cannot generate the lock here — "
            + "; ".join(problems)
            + ".\n"
            "  Environment markers are evaluated against the running interpreter,\n"
            "  so a lock built off-target is wrong in ways CI only discovers at\n"
            "  install time. Generate under Docker (see SECURITY.md)."
        )


def _resolve(source: str) -> list[dict]:
    """Ask pip to resolve the requirements and report what it would install."""
    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "report.json"
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--dry-run",
            "--ignore-installed",
            "--quiet",
            "--report",
            str(report_path),
            "-r",
            str(REPO_ROOT / source),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            _fail(f"pip resolution failed for {source}:\n{result.stderr.strip()}")
        report = json.loads(report_path.read_text(encoding="utf-8"))
    return report["install"]


def _entries(install: list[dict]) -> list[tuple[str, str, list[str]]]:
    """(name, version, [sha256, ...]) for every resolved package, sorted by name.

    A package pip resolved without a recorded hash cannot be pinned, and
    emitting it unhashed would quietly defeat --require-hashes for that entry.
    That is an error, not a line to skip.

    When pip reports multiple artifacts (wheel + sdist), keep every sha256 so
    --require-hashes accepts whichever artifact the install host selects.
    """
    grouped: dict[tuple[str, str], list[str]] = {}
    unhashed: list[str] = []
    for item in install:
        name = item["metadata"]["name"]
        version = item["metadata"]["version"]
        digest = (
            item.get("download_info", {})
            .get("archive_info", {})
            .get("hashes", {})
            .get("sha256")
        )
        if not digest:
            unhashed.append(f"{name}=={version}")
            continue
        key = (name, version)
        hashes = grouped.setdefault(key, [])
        if digest not in hashes:
            hashes.append(digest)
    if unhashed:
        _fail(
            "pip reported no SHA-256 for: "
            + ", ".join(sorted(unhashed))
            + "\n  Refusing to write a lock with unhashed entries."
        )
    return sorted(
        ((name, version, digests) for (name, version), digests in grouped.items()),
        key=lambda e: e[0].lower(),
    )


def _render(source: str, entries: list[tuple[str, str, list[str]]]) -> str:
    body = HEADER.format(
        source=source,
        py_major=TARGET_PYTHON[0],
        py_minor=TARGET_PYTHON[1],
        platform=TARGET_PLATFORM,
        count=len(entries),
    )
    lines = [body]
    for name, version, digests in entries:
        hash_lines = [f"    --hash=sha256:{d}" for d in digests]
        # pip requirements format: package==ver \\ then indented --hash lines
        if len(hash_lines) == 1:
            lines.append(f"{name}=={version} \\\n{hash_lines[0]}")
        else:
            cont = " \\\n".join(hash_lines)
            lines.append(f"{name}=={version} \\\n{cont}")
    return "\n".join(lines) + "\n"


def _build_one(source: str, lock_name: str) -> str:
    return _render(source, _entries(_resolve(source)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed locks match a fresh resolution; write nothing",
    )
    args = parser.parse_args()

    _assert_on_target()

    rendered: list[tuple[str, str]] = []
    for source, lock_name in LOCK_SPECS:
        rendered.append((lock_name, _build_one(source, lock_name)))

    if args.check:
        for lock_name, content in rendered:
            path = REPO_ROOT / lock_name
            if not path.exists():
                _fail(f"{lock_name} does not exist")
            current = path.read_text(encoding="utf-8")
            if current != content:
                _fail(
                    f"{lock_name} is out of date with a fresh resolution.\n"
                    "  Regenerate: python scripts/lock_requirements.py"
                )
            print(f"{lock_name} is current")
        return 0

    for lock_name, content in rendered:
        path = REPO_ROOT / lock_name
        path.write_text(content, encoding="utf-8", newline="\n")
        n = content.count("--hash=sha256:")
        print(f"wrote {lock_name} ({n} hashes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
