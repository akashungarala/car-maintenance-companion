# ADR-0011: `main` is protected, including for administrators

**Status:** Accepted · 2026-09-07

## Context

Every gate this project has built — lint, `mypy --strict`, an 85% coverage ratchet, gitleaks,
`pip-audit`, Trivy, the container smoke test — is only as strong as whatever enforces it. Without
branch protection, all of it is advisory.

Branch protection was first configured with `enforce_admins: false`, on the reasoning that a solo
founder should not be able to lock themselves out of an emergency fix. That reasoning is wrong
here, and it was disproved within a minute of being applied: a test push with `--no-verify`
bypassed both the pre-commit hooks and the required status check, put a formatting error on
`main`, and turned CI red. On a project whose only contributor is also its only administrator,
`enforce_admins: false` means the protection does nothing at all.

## Decision

`main` is protected with `enforce_admins: true`, requiring:

- the aggregate `CI passed` status check, with `strict` (branch must be up to date)
- linear history
- resolved conversations
- no force pushes, no deletions

Pull request reviews are **not** required — a solo founder cannot approve their own PR, and
requiring a review would make the branch unmergeable rather than protected.

## Consequences

**Good:** the gates become real. Nothing reaches `main` without a green pipeline, including work by
the repository owner. The aggregate `CI passed` job is what makes this practical: because path
filters may skip the backend, frontend or image jobs, a single always-running aggregate is the only
stable check name to require.

**Bad:** there is no direct path to `main`. A genuine emergency requires either a PR that waits for
CI (~40s for docs, ~90s with an image build), or deliberately disabling protection first:

```bash
gh api -X DELETE repos/<owner>/<repo>/branches/main/protection   # then re-apply
```

That is a considered, auditable act rather than an accident, which is the point. The protection
payload is kept in the runbook so re-applying it is one command.

**Verified, not assumed:** a direct push to `main` was attempted after the change and was rejected
with `protected branch hook declined`. Force pushes were separately confirmed to be blocked for
administrators even when status checks were bypassable.
