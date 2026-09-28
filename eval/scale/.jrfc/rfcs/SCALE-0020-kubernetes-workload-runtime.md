---
id: SCALE-0020
title: Kubernetes workload resources, probes and disruption
status: enforced
domain: kubernetes
artifacts: [diff, code, spec]
languages: [any]
owner: sre
review_by: 2027-04-30
supersedes: []
summary: >
  Resource requests and limits, health probes, replica counts, PodDisruptionBudgets and
  pod security context for Kubernetes Deployments and StatefulSets.
applies_when: >
  The content adds or changes a Kubernetes Deployment, StatefulSet or pod template, or the
  Helm values that set its resources, probes, replicas, disruption budget or security context.
not_applies_when: >
  No Kubernetes workload, pod template or the Helm values feeding one is added, changed or
  described.
---

# SCALE-0020: Kubernetes workload resources, probes and disruption

## Context

Most node pressure incidents on the shared clusters come from pods without requests or with
unbounded memory, and most failed rollouts from probes that restart healthy pods or admit
pods that are not ready. Node drains during cluster upgrades take down services that run a
single replica or have no disruption budget. These rules keep workloads schedulable,
observable by the kubelet and safe to evict.

## Requirements

### SCALE-0020.1 CPU and memory requests on every container
Every container and init container in a pod template MUST declare `resources.requests.cpu`
and `resources.requests.memory`.

- Applies when: the content adds or changes a `containers:` or `initContainers:` entry in a Deployment, StatefulSet, DaemonSet, Job or CronJob pod template, or the Helm values that fill its `resources` block.
- Enforcement: linter

### SCALE-0020.2 Memory limit equal to memory request
The memory limit of a container MUST be set and MUST be equal to its memory request, so the
pod is never killed for memory that the scheduler did not reserve.

- Applies when: the content sets or changes `resources.limits.memory` or `resources.requests.memory` on a container.
- Enforcement: agent

### SCALE-0020.3 No CPU limit on latency-sensitive services
Containers that serve synchronous user traffic SHOULD NOT set a CPU limit, because CFS
throttling adds tail latency; they rely on the CPU request for fair sharing instead.

- Applies when: the content sets `resources.limits.cpu` on a container of an HTTP or gRPC service that serves requests.
- Enforcement: agent

### SCALE-0020.4 Readiness probe on serving containers
A container that receives traffic through a Service MUST define a `readinessProbe` that checks
the container's own ability to serve and does not call downstream dependencies.

- Applies when: the content adds or changes a container exposed by a Kubernetes Service, or its `readinessProbe`.
- Enforcement: agent

### SCALE-0020.5 Liveness probe independent of dependencies
A `livenessProbe` MUST NOT check databases, brokers or other services, and its
`failureThreshold` times `periodSeconds` MUST be longer than the worst expected garbage
collection or startup pause.

- Applies when: the content adds or changes a `livenessProbe` on a container.
- Enforcement: agent

### SCALE-0020.6 Startup probe for slow-starting containers
A container that takes more than 30 seconds to become ready, such as a JVM service, SHOULD use
a `startupProbe` instead of a long `initialDelaySeconds` on the liveness probe.

- Applies when: the content sets `initialDelaySeconds` above 30 on a probe, or adds a probe to a JVM or other slow-starting container.
- Enforcement: agent

### SCALE-0020.7 At least two replicas in production
A production Deployment serving user traffic MUST run at least two replicas, set either by
`replicas` or by the `minReplicas` of its HorizontalPodAutoscaler.

- Applies when: the content sets `replicas`, `minReplicas` or the Helm value for replica count of a production service.
- Enforcement: agent

### SCALE-0020.8 PodDisruptionBudget for multi-replica workloads
Every production Deployment or StatefulSet with more than one replica MUST have a
PodDisruptionBudget whose `maxUnavailable` or `minAvailable` still lets a node drain evict
at least one pod.

- Applies when: the content adds a production Deployment or StatefulSet, or adds or changes a `PodDisruptionBudget`.
- Enforcement: agent

### SCALE-0020.9 Spread replicas across zones
A production Deployment SHOULD declare `topologySpreadConstraints` on
`topology.kubernetes.io/zone` so that the loss of one availability zone does not remove all
replicas.

- Applies when: the content adds or changes the pod template spec of a production Deployment with two or more replicas.
- Enforcement: agent

### SCALE-0020.10 Restricted pod security context
Pod templates MUST set `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, drop all Linux
capabilities and MUST NOT set `privileged: true` or `hostNetwork: true`.

- Applies when: the content adds or changes `securityContext`, `privileged`, `hostNetwork`, `hostPID` or `capabilities` in a pod template or container.
- Enforcement: agent

### SCALE-0020.11 Read-only root filesystem
Containers MAY set `readOnlyRootFilesystem: true` and mount an `emptyDir` for the paths they
write, and this is the preferred way to satisfy the security context when the application
allows it.

- Applies when: the content adds or changes a container `securityContext` or its `volumeMounts`.
- Enforcement: agent
