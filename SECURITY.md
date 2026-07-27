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
