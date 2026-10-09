---
id: SCALE-0026
title: Build and deploy pipeline gates
status: approved
domain: ci
artifacts: [diff, code, spec]
languages: [any]
owner: platform
review_by: 2027-06-30
supersedes: []
summary: >
  Which checks gate a deployment, how build artifacts are produced once and promoted with
  provenance, and how CI caches are keyed.
applies_when: >
  The content adds or changes a CI job that builds, tests, publishes or deploys a service, the
  order and dependencies of those jobs, or CI cache configuration.
not_applies_when: >
  No build, test, publish, deploy or cache step of a CI/CD pipeline is added, changed or described.
---

# SCALE-0026: Build and deploy pipeline gates

## Context

Deployments to production run from GitHub Actions through Argo CD. Incidents have followed
deploys that skipped failing tests, rebuilt the image between staging and production, or
restored a poisoned cache. These rules keep one artifact moving through gated environments
and make every deployed artifact traceable to its commit.

## Requirements

### SCALE-0026.1 Tests gate the deploy job
A deploy job MUST depend through `needs:` on the unit and integration test jobs of the same
commit, and MUST NOT run when those jobs fail or are skipped.

- Applies when: the content adds or changes a deploy job, its `needs:` list or its `if:` condition.
- Enforcement: agent

### SCALE-0026.2 No continue-on-error in gating jobs
Test, lint and security scan steps that gate a deploy MUST NOT set `continue-on-error: true`.

- Applies when: the content adds or changes `continue-on-error` on a test, lint or scan step or job.
- Enforcement: linter

### SCALE-0026.3 Build once, promote the same artifact
The image or package deployed to production MUST be the same artifact, identified by digest,
that was deployed to staging; production jobs MUST NOT rebuild it.

- Applies when: the content adds or changes a job that builds, tags or deploys an image or package for staging or production.
- Enforcement: agent

### SCALE-0026.4 Signed provenance for release artifacts
Release images SHOULD be signed with cosign and carry a SLSA provenance attestation generated
in the build job.

- Applies when: the content adds or changes a job that pushes an image or package to the release registry.
- Enforcement: agent

### SCALE-0026.5 Artifact tagged with commit SHA
Every published image MUST be tagged with the full Git commit SHA it was built from.

- Applies when: the content adds or changes the tags of an image built or pushed by CI.
- Enforcement: agent

### SCALE-0026.6 Manual approval for production
Production deploy jobs MUST target a GitHub environment that requires approval from a member
of the owning team, except for services enrolled in continuous deployment with automated
canary analysis.

- Applies when: the content adds or changes a production deploy job or its `environment:`.
- Enforcement: agent

### SCALE-0026.7 Cache keys from lock files
Dependency caches SHOULD be keyed on the hash of the lock file and the runtime version, and
SHOULD NOT cache build outputs between branches.

- Applies when: the content adds or changes an `actions/cache` step, a `cache:` input of a setup action, or a Gradle or Docker layer cache configuration.
- Enforcement: agent

### SCALE-0026.8 No cache restore into release builds from pull requests
Release builds on the default branch MUST NOT restore caches written by pull request
workflows.

- Applies when: the content adds or changes cache `restore-keys` or cache scope in a workflow that builds release artifacts.
- Enforcement: agent

### SCALE-0026.9 Post-deploy smoke check
A deploy pipeline SHOULD run a smoke check against the deployed version and trigger an
automatic rollback when it fails.

- Applies when: the content adds or changes the steps that run after a deploy job.
- Enforcement: agent

### SCALE-0026.10 Path filters for monorepo jobs
In monorepos, build and test jobs MAY use path filters to skip services that did not change,
provided that the deploy gate still requires the jobs of every changed service.

- Applies when: the content adds or changes `paths:` or `paths-ignore:` filters, or a change-detection step in a workflow.
- Enforcement: agent

### SCALE-0026.11 Rollout plan in release designs
A design that changes how a service is built or deployed MUST describe the pipeline gates, the
promotion path between environments and the rollback procedure.

- Applies when: the content is a design that proposes a new build, release or deployment process.
- Artifacts: spec
- Enforcement: agent
