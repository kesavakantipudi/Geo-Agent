# Contributing to GeoAgent

Thanks for contributing to GeoAgent — a 4-member academic team project that may evolve into a real product. This document defines how we collaborate so that every contribution is reviewable, documented, and safe to merge.

- [Code of conduct](#code-of-conduct)
- [Getting started](#getting-started)
- [Git workflow](#git-workflow)
  - [Branching model](#branching-model)
  - [Branch naming](#branch-naming)
  - [Commit messages](#commit-messages)
  - [Pull request workflow](#pull-request-workflow)
  - [Code review expectations](#code-review-expectations)
  - [Conflict resolution](#conflict-resolution)
- [Quality bar](#quality-bar)
- [No-secrets policy](#no-secrets-policy)
- [Reporting issues](#reporting-issues)

---

## Code of conduct

By participating, you agree to follow [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

---

## Getting started

1. Read the [`README.md`](README.md) and the full product spec in [`PRD.md`](PRD.md).
2. Read [`DEVELOPMENT.md`](DEVELOPMENT.md) for environment and coding conventions.
3. Complete the setup steps in the README ("Setup" section) on your own machine.
4. Find or create an issue (use the templates in `.github/ISSUE_TEMPLATE/`), then start a feature branch.

---

## Git workflow

The default branch is **`main`**. `main` always contains reviewed, working content.

### Branching model

| Branch | Purpose |
| --- | --- |
| `main` | Stable, reviewed work. Direct pushes are discouraged; changes arrive via pull requests. |
| `develop` (optional) | Integration branch if the team later wants to stage changes before `main`. If adopted, feature branches target `develop`. |
| `feature/<short-description>` | Focused implementation work for one feature or module. |
| `fix/<short-description>` | Bug fixes. |
| `docs/<short-description>` | Documentation changes. |
| `chore/<short-description>` | Repository/tooling maintenance. |

### Branch naming

- Lowercase, hyphens between words, short and descriptive.
- Examples: `feature/satellite-provider-interface`, `fix/ndvi-null-bands`, `docs/setup-guide`.

### Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <short summary>
```

Allowed types:

| Type | Use for |
| --- | --- |
| `feat` | A new capability |
| `fix` | A bug fix |
| `docs` | Documentation only |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or updating tests |
| `chore` | Tooling, dependencies, repository maintenance |

Examples:

```
feat: add satellite provider interface
docs: document local development setup
fix: handle invalid location input
test: add unit tests for geometry validation
```

Write the summary in the imperative mood, keep it under ~72 characters, and add a body only when context is needed. One logical change per commit.

### Pull request workflow

1. Create a branch from `main` (or `develop` if adopted).
2. Make focused changes; commit with Conventional Commit messages.
3. Push the branch and open a pull request using `.github/pull_request_template.md`.
4. Link the related issue in the PR description.
5. Request review from at least one team member (ideally two).
6. Address review comments; keep the discussion on the PR.
7. Keep PRs **small and reviewable**. If a PR grows beyond one clear concern, split it.
8. A PR merges only after the checklist in the template is completed and no secrets are introduced.

### Code review expectations

Reviewers should check:

- Correctness against the issue/PR description.
- No secrets, credentials, or private values introduced.
- Conventions from [`DEVELOPMENT.md`](DEVELOPMENT.md) are followed.
- Tests exist and pass for meaningful functionality (when tests are introduced).
- No fabricated data is presented as real analysis or real results.
- Documentation is updated when behavior or structure changes.
- The branch is up to date with its base branch before merge.

### Conflict resolution

- Prefer rebasing a short feature branch on its base branch to resolve conflicts: `git fetch origin` then `git rebase origin/main`.
- Resolve conflicts carefully; keep both sides' intent when merging others' work.
- If a conflict spans multiple people's work, coordinate on the PR thread before resolving.
- Never force-push shared branches (`main`, `develop`).

---

## Quality bar

- Small, reviewable pull requests.
- No committed secrets.
- Clear documentation for new modules.
- Tests for meaningful functionality once testing is introduced.
- No fabricated data presented as real analysis.
- Planned vs. implemented is always labeled honestly.

---

## No-secrets policy

- Never commit `.env` files, API keys, tokens, passwords, or private configuration.
- Never add real credentials to documentation, examples, or issue/PR content.
- If a secret is accidentally committed, notify the team immediately; rotate the secret and remove it from history.

---

## Reporting issues

Use the templates in `.github/ISSUE_TEMPLATE/`:

- [`bug_report.md`](.github/ISSUE_TEMPLATE/bug_report.md) — something is broken.
- [`feature_request.md`](.github/ISSUE_TEMPLATE/feature_request.md) — a new capability idea.
- [`engineering_task.md`](.github/ISSUE_TEMPLATE/engineering_task.md) — a concrete engineering task.

Provide enough context for a teammate to reproduce or understand the work.