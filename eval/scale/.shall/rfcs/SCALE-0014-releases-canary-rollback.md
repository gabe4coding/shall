---
id: SCALE-0014
title: Releases, canaries, rollback and deploy freezes
status: enforced
domain: delivery
artifacts: [diff, code, spec, doc]
languages: [any]
owner: platform
review_by: 2027-05-31
supersedes: []
summary: >
  How production releases are versioned, rolled out progressively, rolled back and
  paused during freeze windows.
applies_when: >
  The content changes a deployment pipeline, rollout strategy, release process, canary
  analysis, rollback procedure or deploy freeze calendar, or ships a release of a
  production service or mobile app.
not_applies_when: >
  No deployment, rollout, release or rollback process is added, changed or described.
---

# SCALE-0014: Releases, canaries, rollback and deploy freezes

## Context

We deploy backend services about 300 times a week with Argo Rollouts and ship the mobile
apps every two weeks. Friday-evening dinner rush and the December holidays carry most of
our booking volume, so the rollout process has to limit blast radius and make rollback
routine.

## Requirements

### SCALE-0014.1 Immutable release artifacts
Each release MUST deploy an immutable artifact identified by a git SHA or semantic version,
never a mutable tag such as `latest`.

- Applies when: the content sets the image tag, artifact version or release identifier used by a deployment.
- Enforcement: linter

### SCALE-0014.2 Canary for user-facing services
User-facing backend services MUST roll out through a canary step that sends at most 10% of
traffic to the new version before full promotion.

- Applies when: the content adds or changes an Argo Rollout, deployment strategy or pipeline stage for a user-facing service.
- Enforcement: agent

### SCALE-0014.3 Automated canary analysis
Canary promotion MUST be gated on automated analysis of error rate and p99 latency against
the stable version, with automatic abort on failure.

- Applies when: the content configures a canary step, `AnalysisTemplate`, promotion rule or deployment gate.
- Enforcement: agent

### SCALE-0014.4 One-step rollback
Every service MUST be able to roll back to the previous release with a single pipeline
action, without a code change or manual database work.

- Applies when: the content changes a deployment pipeline, release script or the rollback procedure of a service.
- Enforcement: agent

### SCALE-0014.5 Rollback compatibility
A release that changes a message format, cache format or stored data SHOULD state in the
pull request whether the previous version can still read the new data after rollback.

- Applies when: the content changes the format of a Kafka message, cached value, file or stored payload.
- Enforcement: agent

### SCALE-0014.6 Deploy freeze
Production deploys MUST NOT run during a freeze window from the release calendar unless an
exception is approved by the on-call engineering manager.

- Applies when: the content changes deploy schedules, freeze rules, deploy gates or the release calendar.
- Enforcement: agent

### SCALE-0014.7 Friday evening deploys
Risky changes SHOULD NOT be deployed on Friday after 15:00 local time or on the evening
before a public holiday in a main market.

- Applies when: the content describes the rollout timing of a release or configures deploy windows.
- Enforcement: agent

### SCALE-0014.8 Mobile staged rollout
Mobile app releases SHOULD use staged rollout on Google Play and phased release on the App
Store, pausing when the crash-free rate drops below 99.5%.

- Applies when: the content configures the release of an Android or iOS app, Fastlane lanes or store rollout settings.
- Enforcement: agent

### SCALE-0014.9 Release notes
Each production release MUST have release notes generated from merged pull requests and
linked from the deploy event.

- Applies when: the content changes release tooling, changelog generation or deploy notifications.
- Enforcement: agent

### SCALE-0014.10 Manual promotion
Teams MAY require a manual approval step before full promotion for services that handle
payments.

- Applies when: the content configures a promotion step or approval gate in a deployment pipeline.
- Enforcement: agent
