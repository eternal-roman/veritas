# Branch Protection (main)

**Status:** Rules are documented here. They must be applied by a repository **admin** in GitHub Settings (or via API). Until applied, direct pushes to `main` remain possible.

## Required settings

Settings → Branches → Add rule → Branch name pattern: `main`

| Setting | Value |
|---------|--------|
| Require a pull request before merging | **On** |
| Require approvals | **1** |
| Dismiss stale PR approvals when new commits are pushed | **On** |
| Require review from Code Owners | **On** |
| Require status checks to pass before merging | **On** |
| Status checks (after first green CI run) | `Tests & syntax`, `Structure checks`, `Security scan`, `Analyze (Python)` |
| Require branches to be up to date before merging | **On** |
| Require conversation resolution before merging | **On** |
| Do not allow bypassing the above settings | **On** |
| Allow force pushes | **Off** |
| Allow deletions | **Off** |

## Also enable (Settings → Code security and analysis)

- Dependabot alerts
- Dependabot security updates
- Secret scanning
- Push protection for secrets

## Apply via gh CLI (admin token required)

```bash
gh api -X PUT repos/eternal-roman/veritas/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f required_status_checks='{"strict":true,"contexts":["Tests & syntax","Structure checks","Security scan","Analyze (Python)"]}' \
  -F enforce_admins=true \
  -f required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true,"require_code_owner_reviews":true}' \
  -F allow_force_pushes=false \
  -F allow_deletions=false
```

## CI hardening already on main

- Tests and compileall **fail the job** on error (no `|| true` soft-fail)
- Bandit high severity fails CI
- pip-audit fails on known vulnerable deps
- `pip-audit` fails the Security scan job on a known vulnerability in the
  runtime or dev dependency tree
- Secret pattern scan fails on obvious private keys
