"""requirements.txt and pyproject.toml must not drift apart.

pyproject.toml is the install contract (the floors a `pip install` user
gets); requirements.txt is the CI/dev environment pin file and the
pip-audit target. The pin file may be stricter than the contract, never
looser, and every runtime dependency in the contract must be present in it
— otherwise CI tests an environment the install contract does not describe.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

_REQ_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*>=\s*([0-9][0-9a-zA-Z.]*)\s*$")


def _parse_requirements(path: Path) -> dict[str, tuple[int, ...]]:
    floors: dict[str, tuple[int, ...]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-r"):
            continue
        match = _REQ_RE.match(line)
        assert match, f"unparseable requirement line: {line!r}"
        floors[match.group(1).lower().replace("_", "-")] = _version_tuple(match.group(2))
    return floors


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def _pyproject_runtime_deps(text: str) -> list[str]:
    # Regex extraction rather than tomllib, which is 3.11+ while the package
    # supports 3.10. The dependencies array is the first `dependencies = [...]`
    # block in the file.
    block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.DOTALL | re.MULTILINE)
    assert block, "pyproject.toml has no dependencies array"
    return re.findall(r'"([^"]+)"', block.group(1))


def test_requirements_cover_pyproject_floors():
    deps = _pyproject_runtime_deps((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert deps, "no runtime dependencies parsed from pyproject.toml"
    contract: dict[str, tuple[int, ...]] = {}
    for dep in deps:
        match = _REQ_RE.match(dep)
        assert match, f"unparseable pyproject dependency: {dep!r}"
        contract[match.group(1).lower().replace("_", "-")] = _version_tuple(match.group(2))

    pins = _parse_requirements(REPO / "requirements.txt")
    for name, floor in contract.items():
        assert name in pins, f"{name} is in pyproject dependencies but not requirements.txt"
        assert pins[name] >= floor, (
            f"{name} pin {pins[name]} in requirements.txt is looser than "
            f"the pyproject floor {floor}"
        )


def _pyproject_extras(text: str) -> dict[str, list[str]]:
    """Every `[project.optional-dependencies]` extra and its requirement strings."""
    block = re.search(
        r"^\[project\.optional-dependencies\](.*?)(?=^\[)", text, re.DOTALL | re.MULTILINE
    )
    assert block, "pyproject.toml has no [project.optional-dependencies] table"
    extras: dict[str, list[str]] = {}
    for match in re.finditer(r"^(\w[\w-]*)\s*=\s*\[(.*?)\]", block.group(1),
                             re.DOTALL | re.MULTILINE):
        extras[match.group(1)] = re.findall(r'"([^"]+)"', match.group(2))
    assert extras, "no extras parsed from [project.optional-dependencies]"
    return extras


def _requirement_clauses(spec: str) -> tuple[str, set[str]]:
    """('mcp>=1.0,<2') -> ('mcp', {'>=1.0', '<2'})."""
    from packaging.requirements import Requirement

    parsed = Requirement(spec)
    return parsed.name.lower().replace("_", "-"), {str(s) for s in parsed.specifier}


def test_pin_file_is_never_looser_than_an_optional_dependency_contract():
    """The direction rule applies to extras too, not only runtime deps.

    This gap shipped a real defect. `pyproject` declared the MCP surface as
    `mcp>=1.0,<2`, while `requirements-dev.txt` said `mcp>=1.0` with no upper
    bound. The hashed CI lock then froze `mcp==2.0.0`, which removed
    `mcp.server.fastmcp` — so `test_tools_register_with_mcp_sdk` began
    skipping through `importorskip` and kept skipping, leaving STATUS's
    "tested against the SDK" claim held up by a test that no longer ran.

    A missing upper bound is exactly as loose as a missing floor; the original
    test only ever checked floors, and only for runtime dependencies.
    """
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    pin_clauses: dict[str, set[str]] = {}
    for line in (REPO / "requirements-dev.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-r"):
            continue
        name, clauses = _requirement_clauses(line)
        pin_clauses[name] = clauses

    for extra, specs in _pyproject_extras(text).items():
        for spec in specs:
            name, contract = _requirement_clauses(spec)
            if name not in pin_clauses:
                # Not every extra is installed in the dev/CI tree; only the
                # ones that are must agree with the contract.
                continue
            missing = contract - pin_clauses[name]
            assert not missing, (
                f"requirements-dev.txt pins {name} without {sorted(missing)}, which "
                f"pyproject's [{extra}] extra requires. The pin file may be stricter "
                f"than the install contract, never looser."
            )
