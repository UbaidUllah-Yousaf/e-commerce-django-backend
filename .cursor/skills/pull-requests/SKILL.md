---
name: pull-requests
description: Opens focused branches, writes conventional commits, runs automated tests before any pull request, and opens PRs with clear titles and structured descriptions (summary, test plan, risk, rollout). Use when opening a PR, shipping a branch, preparing for review, writing a PR description, or when the user mentions pull request, merge request, CI, or code review handoff.
---

# Pull requests (standard workflow)

## Before you branch

- Confirm base branch (usually `main`) is up to date.
- Scope one logical change per PR; split unrelated work.

## Branch naming

Use lowercase, hyphens, short type prefix:

- `feat/short-topic`
- `fix/short-topic`
- `chore/short-topic`
- `docs/short-topic`
- `refactor/short-topic`

## Commits

- Prefer [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): imperative summary` (max ~72 chars subject).
- One commit message should explain *why* when the diff is not obvious.
- Avoid noisy history: rebase or squash locally when appropriate before opening the PR.

## PR title

Same shape as the primary commit: `type(scope): concise customer-facing summary`

## Testing gate (required before PR)

- **Do not open or mark ready for review** until automated tests pass locally (same commands CI uses when known; otherwise the project’s default test entrypoint).
- Fix failures or widen coverage when the change warrants it; do not rely on “CI will catch it.”
- If tests cannot run in the environment, say so explicitly in the PR **Test plan** with what you ran instead and why—only when unavoidable.

**This repository (Django):** from `ecommerce/`, run `venv/bin/python manage.py test` (or the subset that covers the change) before pushing the PR branch.

## PR description (copy template)

Fill every section; delete lines that truly do not apply.

```markdown
## Summary

[What changed and why in plain language. Link tickets: Fixes #123 / Ref #456]

## Test plan

- [ ] Tests run locally: [paste command(s) and result]
- [ ] [Scenario or edge case exercised]
- [ ] [Regression check]

## Risk / rollout

[Data migrations, feature flags, deploy order, rollback]

## Screenshots / API notes

[If UI or contract changed]
```

## Verification

- Satisfy **Testing gate** above first; then run linters or type checks the repo expects, if any.
- Keep the diff easy to review: minimal unrelated formatting, no drive-by refactors unless agreed.

## Handoff

- Request review from the right owner; note anything reviewers should ignore (generated files, lockfile-only noise).
- If CI fails, push fixes or comment with blocker and next step—do not leave a red PR silent.
