# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| main (latest) | Yes |

## Reporting a vulnerability

Do **not** open a public issue for security vulnerabilities.

Please report privately via GitHub Security Advisories for this repository:

**https://github.com/eternal-roman/veritas/security/advisories/new**

or contact the repository owner.

Include:
- Description of the issue
- Steps to reproduce
- Potential impact (especially if it could affect agent users or payment flows)

We will acknowledge reports as quickly as possible and work on a fix before any public disclosure.

## Automated protections

- CI tests and structure checks on every PR
- CodeQL analysis
- Dependabot for dependency and Actions updates
- `pip-audit` on every push and pull request, over both runtime and dev
  dependency trees (fails the build on a known vulnerability)
- Basic secret pattern scanning in CI
- Recommended branch protection on `main` (see `.github/BRANCH_PROTECTION.md`)

## Supply chain

Three things are pinned, each with a test in `tests/test_supply_chain.py` so
they cannot decay quietly.

**GitHub Actions are pinned to commit SHAs**, with a `# vX.Y.Z` comment so the
pin stays readable and Dependabot can still bump it. A tag is a mutable
pointer; `release.yml` runs with `id-token: write` — the PyPI Trusted
Publishing identity — so whoever controlled a tag at the moment a release ran
could otherwise mint a token and publish as this project.

**Dependencies are hash-pinned.** `requirements.lock` (runtime) and
`requirements-dev.lock` (runtime plus CI tooling) pin every package in the
closure to an exact version and the SHA-256 of its artifact. CI installs with
`--require-hashes`, so a substituted artifact fails the install instead of
executing. The `requirements*.txt` files remain the human-edited floors; the
locks are generated from them.

Regenerate after changing a floor:

```bash
python scripts/lock_requirements.py          # writes both locks
python scripts/lock_requirements.py --check  # verifies they are current
```

This **must run on Linux/CPython 3.12**, and the script refuses to run
anywhere else. pip resolves versions against the tags you request but
evaluates environment markers against the *running interpreter*: generating on
Windows silently yields a tree that gains `pywin32-ctypes` and loses
`SecretStorage`/`jeepney`, which `twine`'s `keyring` dependency needs only on
Linux — and pip then fails at install time on a package the lock has no hash
for. Refusing to generate is fail-closed; noticing afterwards is not. From
Windows, use WSL or a container:

```bash
docker run --rm -v "$PWD":/src -w /src python:3.12-bookworm \
  bash -c "pip install -q -U pip && python scripts/lock_requirements.py"
```

**An SBOM is generated for the published artifact.** CI installs the wheel over
the hash-pinned runtime closure in a clean venv and runs `cyclonedx-py` against
*that* environment, so the SBOM describes what `pip install veritas-research`
gives a buyer — not the CI toolchain, which would over-report by ~100 dev-only
packages that never ship. The job fails if the SBOM disagrees with
`requirements.lock`. It is uploaded as a workflow artifact.

### What this does not establish

- The locks cover what CI and the published wheel install. **The Docker image
  path is not hash-locked** — the Dockerfile still installs from pyproject
  floors.
- The SBOM describes a closure installed in CI. It is not a scan of a running
  container, and it carries **no signature**: on its own it is a claim by the
  publisher, not evidence against the publisher.
- Pinning an Action to a SHA fixes *which* commit runs. It is not a review of
  what that commit does.
- Nothing has been published from this pipeline. `release.yml` stays inert
  until a maintainer configures PyPI Trusted Publishing.
