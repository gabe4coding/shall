---
id: SCALE-0025
title: GitHub Actions workflow security
status: enforced
domain: ci
artifacts: [diff, code]
languages: [any]
owner: platform
review_by: 2027-03-31
supersedes: []
summary: >
  Pinned third-party actions, least-privilege workflow tokens, safe handling of secrets and
  untrusted pull request content in GitHub Actions workflows.
applies_when: >
  The content adds or changes a GitHub Actions workflow or composite action under
  `.github/workflows/` or `.github/actions/`.
not_applies_when: >
  No GitHub Actions workflow, composite action or reusable workflow is added or changed.
---

# SCALE-0025: GitHub Actions workflow security

## Context

CI runners hold deploy credentials and write access to the repositories, which makes
workflows a supply-chain target. Compromised third-party actions, over-privileged
`GITHUB_TOKEN`s and workflows that run fork code with secrets are the known attack paths.
These rules close them at the workflow file level.

## Requirements

### SCALE-0025.1 Pin third-party actions to a commit SHA
Actions from outside the `lafourchette` organisation MUST be referenced by a full 40-character
commit SHA, with the version in a trailing comment.

- Applies when: the content adds or changes a `uses:` line that references an action outside the organisation.
- Enforcement: linter

### SCALE-0025.2 Explicit minimal token permissions
Every workflow MUST declare a top-level `permissions:` block, set to `contents: read` or less,
and grant wider scopes only on the jobs that need them.

- Applies when: the content adds a workflow file, or changes a `permissions:` block at workflow or job level.
- Enforcement: agent

### SCALE-0025.3 No secrets for fork pull requests
Workflows triggered by `pull_request_target` or `workflow_run` MUST NOT check out and run code
from the pull request head while secrets or a write token are available.

- Applies when: the content adds or changes a workflow with `pull_request_target` or `workflow_run` triggers, or an `actions/checkout` step with a `ref` from the pull request.
- Enforcement: agent

### SCALE-0025.4 No untrusted input in run scripts
Values from `github.event` such as titles, branch names, bodies and commit messages MUST NOT be
interpolated with `${{ }}` directly inside a `run:` script; they are passed through `env:` and
quoted.

- Applies when: the content adds a `run:` step that contains `${{ github.event.` or `${{ github.head_ref }}`.
- Enforcement: agent

### SCALE-0025.5 Cloud access through OIDC
Workflows that deploy or call cloud APIs SHOULD authenticate with OIDC federation
(`id-token: write`) instead of long-lived cloud keys stored as repository secrets.

- Applies when: the content adds or changes a workflow step that authenticates to AWS, GCP or another cloud provider.
- Enforcement: agent

### SCALE-0025.6 Secrets scoped to environments
Deployment secrets SHOULD be defined on a GitHub environment with protection rules, and the job
that uses them references that `environment:`.

- Applies when: the content adds a job that reads `secrets.` for a deployment, or changes the `environment:` of a job.
- Enforcement: agent

### SCALE-0025.7 No secret echo or artifact upload
A workflow step MUST NOT print a secret, write it to `GITHUB_OUTPUT` or `GITHUB_STEP_SUMMARY`, or
include it in an uploaded artifact or cache.

- Applies when: the content adds a step that uses `secrets.` together with `echo`, `GITHUB_OUTPUT`, `upload-artifact` or `cache`.
- Enforcement: agent

### SCALE-0025.8 Job timeouts
Every job SHOULD set `timeout-minutes` so a hung step does not hold a runner for the default
six hours.

- Applies when: the content adds or changes a job in a GitHub Actions workflow.
- Enforcement: agent

### SCALE-0025.9 Self-hosted runners only for trusted events
Jobs on self-hosted runners MUST NOT run for pull requests from forks.

- Applies when: the content sets `runs-on` to a self-hosted runner label in a workflow triggered by `pull_request`.
- Enforcement: agent

### SCALE-0025.10 Organisation actions by tag
Actions and reusable workflows owned by the organisation MAY be referenced by a release tag
instead of a commit SHA.

- Applies when: the content adds or changes a `uses:` line that references an action or reusable workflow in the `lafourchette` organisation.
- Enforcement: agent
