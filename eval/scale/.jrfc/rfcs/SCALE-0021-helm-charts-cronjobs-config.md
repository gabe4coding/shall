---
id: SCALE-0021
title: Helm charts, CronJobs and configuration objects
status: approved
domain: kubernetes
artifacts: [diff, code, spec]
languages: [any]
owner: sre
review_by: 2027-05-31
supersedes: []
summary: >
  Conventions for Helm chart layout and values, image references, labels, Kubernetes
  CronJobs, ConfigMaps and Secret references.
applies_when: >
  The content adds or changes a Helm chart, a values file, a Kubernetes CronJob or Job, a
  ConfigMap, or the way a workload reads configuration from Kubernetes objects.
not_applies_when: >
  No Helm chart, values file, CronJob, Job, ConfigMap or Kubernetes configuration reference is
  added, changed or described.
---

# SCALE-0021: Helm charts, CronJobs and configuration objects

## Context

All services deploy through Helm charts built on the shared `service` library chart, with
one values file per environment. Drift between environments, mutable image tags and
CronJobs that overlap or never get cleaned up are the main sources of deployment surprises.
These rules make a chart render the same way every time and make scheduled jobs predictable.

## Requirements

### SCALE-0021.1 Use the shared library chart
A new service chart MUST declare the shared `service` library chart as a dependency and
MUST NOT copy its Deployment, Service or HPA templates into the service chart.

- Applies when: the content adds a new `Chart.yaml`, or adds templates for Deployment, Service or HorizontalPodAutoscaler to a service chart.
- Enforcement: agent

### SCALE-0021.2 One values file per environment
Environment differences MUST live in `values-<env>.yaml` files on top of a common
`values.yaml`, and templates MUST NOT branch on the environment name.

- Applies when: the content adds or changes a Helm values file, or a template that tests `.Values.env`, `.Release.Namespace` or a similar environment name.
- Enforcement: agent

### SCALE-0021.3 Immutable image references
Image references in values files MUST pin a version tag or digest produced by CI and MUST
NOT use `latest` or a branch name as the tag.

- Applies when: the content sets `image.tag`, `image.repository` or an `image:` field in a values file or manifest.
- Enforcement: linter

### SCALE-0021.4 Standard labels
Every rendered object SHOULD carry the labels `app.kubernetes.io/name`,
`app.kubernetes.io/version`, `team` and `tier`, set from the library chart helpers rather than
written by hand.

- Applies when: the content adds or changes `metadata.labels` in a Helm template or manifest.
- Enforcement: agent

### SCALE-0021.5 CronJob concurrency policy
Every CronJob MUST set `concurrencyPolicy` explicitly, and it MUST be `Forbid` unless the job
is documented as safe to run in parallel with itself.

- Applies when: the content adds or changes a Kubernetes `CronJob` manifest or its Helm values.
- Enforcement: agent

### SCALE-0021.6 CronJob deadlines and history
A CronJob MUST set `startingDeadlineSeconds`, `activeDeadlineSeconds` on its job template and
bounded `successfulJobsHistoryLimit` and `failedJobsHistoryLimit`.

- Applies when: the content adds or changes a Kubernetes `CronJob` or the `jobTemplate` of one.
- Enforcement: agent

### SCALE-0021.7 Explicit CronJob time zone
A CronJob schedule SHOULD set `timeZone` explicitly instead of relying on the controller's
default UTC, when the schedule is tied to restaurant opening hours or local business time.

- Applies when: the content sets or changes the `schedule` field of a CronJob.
- Enforcement: agent

### SCALE-0021.8 Job retry limit
A Job or CronJob job template MUST set `backoffLimit` to a value of 3 or less, so a failing
job does not create pods indefinitely.

- Applies when: the content adds or changes a Kubernetes `Job` or the `jobTemplate` of a `CronJob`.
- Enforcement: linter

### SCALE-0021.9 Roll pods when configuration changes
A Deployment that reads a ConfigMap SHOULD carry a pod template annotation with the checksum
of that ConfigMap, so that a configuration change triggers a rollout.

- Applies when: the content adds or changes a ConfigMap consumed by a Deployment, or the pod template annotations of that Deployment.
- Enforcement: agent

### SCALE-0021.10 No sensitive values in ConfigMaps
A ConfigMap MUST NOT contain passwords, tokens or connection strings with credentials; those
values come from an ExternalSecret synced from the secret manager.

- Applies when: the content adds or changes the `data` of a ConfigMap or the Helm values rendered into one.
- Enforcement: agent

### SCALE-0021.11 Chart version bump
A change to a chart's templates or default values MAY skip the `version` bump in `Chart.yaml`
only when the chart is not published to the chart repository.

- Applies when: the content changes files under a Helm chart's `templates/` directory or its `values.yaml`.
- Enforcement: agent
