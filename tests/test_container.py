"""The container image must not carry secrets or lose state.

Defect O12. `veritas-agent up` writes an encrypted wallet keystore *and its
plaintext passphrase* into the working directory (see
`veritas/autonomous/wallet.py`, which states that threat model plainly). The
repository had no `.dockerignore`, so the whole tree — including that
passphrase — was uploaded to the Docker daemon as build context, and one
future `COPY . .` would have baked a private key into a published image.

Defect O13. The runtime directory holds the financial ledger, the custody
receipts and the trust counters. Without a declared volume they live in the
container's writable layer and vanish when it is replaced, taking the record
of what was earned with them.

These tests read the shipped files rather than building an image, so they run
in CI without a Docker daemon. That is a real limit: they prove the
declarations are right, not that a built image is clean.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _dockerignore() -> list[str]:
    return [
        line.strip()
        for line in (REPO / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_the_build_context_is_an_allowlist_not_a_denylist():
    """A forgotten denylist pattern is a private key in a published image.
    An allowlist fails the other way: a missing file breaks the build."""
    lines = _dockerignore()
    assert lines[0] == "*", ".dockerignore must exclude everything first"
    assert any(line.startswith("!") for line in lines), "nothing is allowed back in"


def test_wallet_material_is_not_in_the_build_context():
    from veritas.autonomous.wallet import KEYSTORE_NAME, PASSPHRASE_NAME

    allowed = {line[1:].rstrip("/") for line in _dockerignore() if line.startswith("!")}
    for secret in (KEYSTORE_NAME, PASSPHRASE_NAME, ".veritas_agent", ".veritas_runtime"):
        assert secret not in allowed, f"{secret} is allowed into the build context"


def test_the_dockerfile_copies_named_paths_never_the_whole_tree():
    """`COPY . .` would make the allowlist above the only thing standing
    between a wallet passphrase and a published image. Two defences are one
    too few to rely on the weaker."""
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    copies = re.findall(r"^COPY\s+(.+)$", dockerfile, flags=re.MULTILINE)
    assert copies, "Dockerfile copies nothing"
    for line in copies:
        sources = line.split()[:-1]
        assert "." not in sources, f"Dockerfile copies the whole tree: COPY {line}"


def test_the_image_installs_dependencies_from_the_hashed_lock():
    """Defect O16. `pip install "."` resolved the pyproject floors against
    PyPI at build time, so the image's dependency set was whatever PyPI served
    that day: two builds of one commit could ship different trees, and a
    compromised release of any transitive dependency landed unreviewed. O.8
    hash-pinned CI and the published wheel but explicitly left the image out;
    this closes that."""
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    assert "--require-hashes -r requirements.lock" in dockerfile, (
        "the image must install its dependencies from the hashed lock"
    )


def _run_commands() -> list[str]:
    """The Dockerfile's RUN commands, comments stripped and continuations joined.

    Reading the raw text would match prose: the comments here discuss
    `pip install "."` in order to explain why it is gone.
    """
    text = (REPO / "Dockerfile").read_text(encoding="utf-8")
    without_comments = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    joined = re.sub(r"\\\s*\n\s*", " ", without_comments)
    return [match.group(1).strip() for match in re.finditer(r"^RUN\s+(.+)$", joined,
                                                            flags=re.MULTILINE)]


def test_the_base_image_python_matches_the_lock_target():
    """The base-image pin and the lock are coupled; nothing else says so.

    `requirements.lock` carries CPython 3.12 wheel hashes, and several are
    ABI-specific (pydantic_core ships per-interpreter wheels). Moving the base
    image to another minor makes those hashes unusable, so the build fails deep
    inside pip with an opaque resolution error.

    Not hypothetical: adding the docker ecosystem to dependabot immediately
    produced a `python:3.12-slim` → `3.14-slim` bump whose only failing check
    was the container build. Failing here instead names the cause and the fix.
    """
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    image = re.search(r"^FROM\s+python:(\d+)\.(\d+)-", dockerfile, flags=re.MULTILINE)
    assert image, "cannot read a python X.Y tag from the Dockerfile's FROM line"

    lock_header = (REPO / "requirements.lock").read_text(encoding="utf-8")[:2000]
    target = re.search(r"CPython\s+(\d+)\.(\d+)", lock_header)
    assert target, "requirements.lock does not declare its CPython target"

    assert image.groups() == target.groups(), (
        f"the image builds on Python {'.'.join(image.groups())} but "
        f"requirements.lock pins wheels for CPython {'.'.join(target.groups())}. "
        "Bump both together: change the base image, then regenerate the lock on "
        "that interpreter (see SECURITY.md)."
    )


def test_the_base_image_is_pinned_by_digest():
    """A tag is a moving pointer: the same Dockerfile built twice can produce
    different base contents. This is the same mutable-reference problem the
    Action SHAs and the dependency lock exist to remove, and the base image is
    the largest single component of what ships."""
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    from_lines = re.findall(r"^FROM\s+(\S+)", dockerfile, flags=re.MULTILINE)
    assert from_lines, "Dockerfile has no FROM instruction"
    for image in from_lines:
        assert re.search(r"@sha256:[0-9a-f]{64}$", image), (
            f"base image {image!r} is referenced by tag, not by digest"
        )


def test_pinning_the_base_image_does_not_strand_it_without_updates():
    """A digest pin without an updater is a base image that stops receiving
    security patches. Pinning and updating have to ship together."""
    dependabot = (REPO / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert 'package-ecosystem: "docker"' in dependabot, (
        "the Dockerfile pins a base-image digest, so dependabot must watch the "
        "docker ecosystem or that pin silently goes stale"
    )


def test_the_image_never_resolves_dependencies_while_installing_the_package():
    """Installing the package without --no-deps would re-resolve the floors
    and silently undo the pinning above."""
    installs = [cmd for cmd in _run_commands() if re.search(r'pip install .*"\."', cmd)]
    assert installs, "the Dockerfile no longer installs the package"
    for command in installs:
        assert "--no-deps" in command, (
            "installing the package must use --no-deps; every dependency comes "
            f"from the lock:\n{command}"
        )


def test_the_image_verifies_the_locked_closure_satisfies_the_package():
    """--no-deps trusts the lock to be complete. `pip check` is what turns
    that trust into a build failure rather than a runtime ImportError."""
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    assert "pip check" in dockerfile, (
        "the image installs with --no-deps and must run `pip check`, or a "
        "dependency the lock is missing surfaces at a user's first request"
    )


def test_the_lockfile_is_in_the_build_context():
    """The allowlist is exclusive: a file the Dockerfile COPYs but does not
    allow back in fails the build."""
    allowed = {line[1:].rstrip("/") for line in _dockerignore() if line.startswith("!")}
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    for line in re.findall(r"^COPY\s+(.+)$", dockerfile, flags=re.MULTILINE):
        for source in line.split()[:-1]:
            assert source.rstrip("/") in allowed, (
                f"Dockerfile copies {source!r}, which .dockerignore does not allow back in"
            )


def test_the_runtime_directory_is_a_declared_volume():
    """The ledger, receipts and trust counters live here. In the writable
    layer they vanish with the container, and with them the record of what
    was earned."""
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    assert "VOLUME" in dockerfile
    runtime = re.search(r"VERITAS_RUNTIME_DIR=(\S+)", dockerfile)
    assert runtime, "the image does not set VERITAS_RUNTIME_DIR"
    assert runtime.group(1) in dockerfile.split("VOLUME", 1)[1].splitlines()[0]


def test_the_container_runs_as_a_non_root_user():
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^USER\s+(?!root)", dockerfile, flags=re.MULTILINE)


def test_compose_mounts_a_named_volume_for_the_runtime_directory():
    compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    assert "veritas-runtime" in compose
    assert "/home/veritas/runtime" in compose


#: An env value that is nothing but an interpolation with an empty default.
#: Anything else on a credential line is a value the repository ships.
_EMPTY_INTERPOLATION = re.compile(r'^"?\$\{[A-Z_]+:-\}"?$')


def test_compose_does_not_ship_a_default_secret():
    """A committed compose file with a working token or key in it is a
    credential that ships with the repository — and a missing credential must
    reach the service's own misconfiguration path, not a baked-in fallback."""
    compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    for raw in compose.splitlines():
        line = raw.strip()
        if line.startswith("#") or ":" not in line:
            continue
        name, _, value = line.partition(":")
        if not any(word in name for word in ("TOKEN", "KEY", "PASSPHRASE", "SECRET")):
            continue
        assert _EMPTY_INTERPOLATION.match(value.strip()), (
            f"compose carries a baked-in credential: {line}"
        )
