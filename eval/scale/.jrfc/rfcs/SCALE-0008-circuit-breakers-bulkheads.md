---
id: SCALE-0008
title: Circuit breakers, bulkheads and load shedding
status: enforced
domain: reliability
artifacts: [diff, code, spec]
languages: [any]
owner: sre
review_by: 2027-04-30
supersedes: []
summary: >
  Isolation of slow dependencies with circuit breakers and bulkheads, and protection of a
  service from its own callers with concurrency limits and load shedding.
applies_when: >
  The content configures a circuit breaker, bulkhead, concurrency limit, thread pool for
  remote calls, or server-side load shedding, or calls a dependency on a high-traffic path.
not_applies_when: >
  No circuit breaker, bulkhead, concurrency limit or load shedding is configured and no
  dependency is called.
---

# SCALE-0008: Circuit breakers, bulkheads and load shedding

## Context

Timeouts and retries alone do not stop a slow dependency from filling every worker thread.
During peak dinner hours the search and availability services receive ten times their
normal traffic, so they need to fail fast on broken dependencies and shed excess load.

## Requirements

### SCALE-0008.1 Circuit breaker on critical-path dependencies
Calls to a remote dependency on the search, availability or booking path MUST go through a
circuit breaker (Resilience4j, `opossum`, `gobreaker` or the shared client wrapper).

- Applies when: the content adds or changes a call to another service or third party from search, availability, booking or checkout code.
- Enforcement: agent

### SCALE-0008.2 Breaker thresholds in configuration
Circuit breaker thresholds (failure rate, slow-call threshold, open duration) MUST be set
in configuration with values stated per dependency, not left at library defaults.

- Applies when: the content creates or configures a circuit breaker.
- Enforcement: agent

### SCALE-0008.3 Behavior when open
Code SHOULD handle the open-breaker exception explicitly, returning a fallback or a 503,
instead of letting it surface as a 500.

- Applies when: the content calls a dependency through a circuit breaker or catches its exception.
- Enforcement: agent

### SCALE-0008.4 Separate pools per dependency
Each remote dependency MUST have its own bounded connection pool or bulkhead, so that one
slow dependency cannot use every worker or connection.

- Applies when: the content configures an HTTP client connection pool, thread pool, executor or semaphore used for calls to a dependency.
- Enforcement: agent

### SCALE-0008.5 Server concurrency limit
Services on the booking path SHOULD set a maximum number of in-flight requests and reject
excess requests with 503 and `Retry-After` instead of queueing them.

- Applies when: the content configures server worker counts, request queues, max connections or concurrency limits.
- Enforcement: agent

### SCALE-0008.6 Priority shedding
When shedding load, a service SHOULD reject background and batch traffic before
user-facing traffic, using the `X-Request-Priority` header.

- Applies when: the content implements load shedding, admission control or request prioritisation.
- Enforcement: agent

### SCALE-0008.7 Breaker metrics
Every circuit breaker MUST publish its state and its rejected-call count as metrics tagged
with the dependency name.

- Applies when: the content creates or configures a circuit breaker.
- Enforcement: agent

### SCALE-0008.8 Retries counted by the breaker
Each retry attempt MUST pass through the circuit breaker so the breaker counts it, and
retries MUST stop as soon as the breaker is open.

- Applies when: the content combines a retry policy with a circuit breaker on the same call.
- Enforcement: agent

### SCALE-0008.9 Designs state isolation
A design that adds a dependency to a critical path MUST state which breaker and bulkhead
protect it and what the user sees when the breaker is open.

- Applies when: the content is a design that adds a dependency to search, availability, booking or payment.
- Artifacts: spec
- Enforcement: agent

### SCALE-0008.10 Adaptive limits
Services MAY use adaptive concurrency limits (for example the Netflix concurrency-limits
library) instead of fixed limits.

- Applies when: the content configures a concurrency limit or admission control for a service.
- Enforcement: agent
