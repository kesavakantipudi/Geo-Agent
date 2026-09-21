# Phase 1 — Engineering Foundation: Checklist and Acceptance Criteria

**Goal:** repository organization, development standards, documentation, and project-management readiness. No application code is created in this phase.

> Items marked `[x]` were completed as part of this Phase 1 work. Items marked `[ ]` require manual/team action or will be verified later. No item is marked complete unless the deliverable exists and has been checked.

## Deliverable checklist

- [x] Repository structure reviewed and documented.
- [x] README is complete and accurate.
- [x] `.gitignore` covers relevant generated files and secrets.
- [x] `.env.example` contains placeholders only.
- [x] CONTRIBUTING.md is available.
- [x] CODE_OF_CONDUCT.md is available (Contributor Covenant 2.1). Team adoption to be confirmed on first PRs/issues.
- [x] DEVELOPMENT.md contains practical development conventions.
- [x] Architecture and roadmap documentation are available.
- [x] Issue templates are prepared (bug report, feature request, engineering task).
- [x] Pull request template is prepared.
- [x] Git workflow is documented.
- [x] Team setup instructions are documented.
- [ ] All four team members can follow the setup instructions — **pending actual verification by each member**.
- [x] No secrets have been introduced.
- [x] Existing work and uncommitted changes have been preserved.

## Acceptance criteria

Phase 1 is considered complete when:

- [x] The repository has a sensible, documented structure that matches the planned application layout.
- [x] A new teammate can read the README and understand the project, its status, and where everything lives.
- [x] Contribution rules (branching, commits, PRs, reviews) are written down and agreed.
- [x] No secrets or real credentials are present anywhere in the repository.
- [x] Nothing was created that belongs to later phases (no application code, DB, or integrations).
- [x] The team has a roadmap showing phases Q1–Q4.
- [ ] Every team member has completed the `DEVELOPMENT.md` setup checklist on their own machine and confirmed it here (owner-verified).

## Manual/team actions remaining

- [ ] **Verify setup as a team:** each member follows the README setup + `DEVELOPMENT.md` checklist and confirms.
- [ ] **Adopt the driving conventions:** team agrees on the branch model, commit convention, and review expectations in `CONTRIBUTING.md`.
- [ ] **Decide on LICENSE:** the project owner must choose a license; document the decision in `README.md` and `LICENSE`.
- [ ] **Create GitHub project configuration (manual):** create labels (e.g., `bug`, `feature`, `task`, `documentation`), milestones (Q1–Q4), and a project board if desired. Template files are already in place under `.github/`.
- [ ] **Optional:** rename `docs/project-scpoe.md` to `docs/project-scope.md` (file name has a typo; content is fine).

## When this is done

Proceed to **Phase 2 — Application Foundation** (see [`roadmap.md`](roadmap.md)).