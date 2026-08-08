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
