# Branch Protection (main)

Apply these rules on GitHub for `main` to protect the public repository and end users.

## Required settings (Settings → Branches → Add rule → Branch name pattern: `main`)

| Setting | Value |
|---------|--------|
| Require a pull request before merging | **On** |
| Require approvals | **1** (or more) |
| Dismiss stale PR approvals when new commits are pushed | **On** |
| Require status checks to pass before merging | **On** |
| Status checks that are required | `Tests & syntax`, `Structure checks`, `Analyze (Python)` |
| Require branches to be up to date before merging | **On** |
| Require conversation resolution before merging | **On** |
| Do not allow bypassing the above settings | **On** (for admins too if possible) |
| Restrict who can push to matching branches | Optional: limit to maintainers |
| Allow force pushes | **Off** |
| Allow deletions | **Off** |

## Why this protects users

- No direct push of unreviewed code to `main`
- CI must pass (tests, structure, CodeQL)
- Dependency review blocks high-severity vulnerable deps on PRs
- Dependabot keeps libraries and Actions patched
- Secret pattern scan fails the build if obvious private keys are introduced

## Apply via GitHub UI or API

If you have admin rights on `eternal-roman/veritas`:

1. Open **Settings → Branches**
2. Add rule for `main`
3. Enable the options above
4. Save

Alternatively use the GitHub API / `gh` CLI:

```bash
gh api -X PUT repos/eternal-roman/veritas/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f required_status_checks='{"strict":true,"contexts":["Tests & syntax","Structure checks","Analyze (Python)"]}' \
  -F enforce_admins=true \
  -f required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  -F allow_force_pushes=false \
  -F allow_deletions=false
```
