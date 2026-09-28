---
id: SCALE-0009
title: Graceful shutdown, health checks and startup
status: enforced
domain: reliability
artifacts: [diff, code, spec]
languages: [any]
owner: sre
review_by: 2027-03-31
supersedes: []
summary: >
  How services start, report health to Kubernetes and stop without dropping requests or
  messages during deploys and autoscaling.
applies_when: >
  The content implements or configures a health, readiness, liveness or startup endpoint
  or probe, a shutdown or signal handler, server startup, or warm-up logic.
not_applies_when: >
  No health endpoint, probe, startup code or shutdown handling is added, changed or described.
---

# SCALE-0009: Graceful shutdown, health checks and startup

## Context

Pods are replaced dozens of times a day by deploys, autoscaling and node rotation. Each
replacement that drops in-flight requests or reports a wrong health state shows up as error
spikes on the booking funnel. These rules make pod turnover invisible to users.

## Requirements

### SCALE-0009.1 Handle SIGTERM
Services MUST handle SIGTERM by stopping new work, finishing in-flight requests and
messages, and then exiting before the termination grace period ends.

- Applies when: the content adds or changes a server entry point, a signal handler, or the shutdown hook of a service or consumer.
- Enforcement: agent

### SCALE-0009.2 Readiness fails first
On shutdown a service MUST mark its readiness check as failing before it closes its
listener, so the load balancer stops sending traffic.

- Applies when: the content implements shutdown logic or a readiness endpoint.
- Enforcement: agent

### SCALE-0009.3 Commit offsets on shutdown
Kafka consumers MUST commit offsets for fully processed messages and leave the consumer
group cleanly during shutdown.

- Applies when: the content implements the shutdown or close path of a Kafka or queue consumer.
- Enforcement: agent

### SCALE-0009.4 Liveness checks the process only
Liveness probes MUST check only that the process can serve, and MUST NOT call databases,
caches or other services.

- Applies when: the content implements a liveness endpoint or configures a `livenessProbe`.
- Enforcement: agent

### SCALE-0009.5 Readiness checks hard dependencies
Readiness SHOULD fail when a dependency the service cannot work without (its own database)
is unreachable, and SHOULD NOT fail for non-essential dependencies.

- Applies when: the content implements a readiness endpoint or adds a check to it.
- Enforcement: agent

### SCALE-0009.6 Health endpoint paths
Health endpoints MUST be served at `/health/live` and `/health/ready` on the management port.

- Applies when: the content adds or changes a health, liveness or readiness route, or the probe paths in a manifest.
- Enforcement: linter

### SCALE-0009.7 Startup probe for slow starts
Services that need more than 10 seconds to start SHOULD use a startup probe instead of a
long initial delay on the liveness probe.

- Applies when: the content configures `startupProbe`, `initialDelaySeconds` or other probe timings.
- Enforcement: agent

### SCALE-0009.8 Fail fast on bad configuration
A service MUST validate its mandatory configuration at startup and exit with a non-zero
code and a clear message when a value is missing or invalid.

- Applies when: the content reads environment variables or configuration files at service startup.
- Enforcement: agent

### SCALE-0009.9 Warm-up before ready
JVM and other services with cold-start latency SHOULD warm up caches and connection pools
before reporting ready.

- Applies when: the content adds startup logic that loads caches, opens connection pools or pre-computes data.
- Enforcement: agent

### SCALE-0009.10 Pre-stop delay
Deployments MAY add a short `preStop` sleep of 5 to 10 seconds to cover load balancer
propagation delay.

- Applies when: the content configures a `preStop` hook or `terminationGracePeriodSeconds`.
- Enforcement: agent
