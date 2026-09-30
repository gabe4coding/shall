---
id: JRFC-0006
title: Resilient outbound calls
status: enforced
domain: reliability
artifacts: [diff, code, spec]
languages: [any]
owner: sre
review_by: 2027-03-31
supersedes: []
summary: >
  Timeouts, retries and fallbacks for calls to other services, databases and third
  parties.
applies_when: >
  The content makes, configures or describes an outbound network call: HTTP client,
  RPC, database driver, message broker or third-party SDK.
not_applies_when: >
  No outbound network call is made, configured or described.
---

# JRFC-0006: Resilient outbound calls

## Context

Most cascading outages start with a slow dependency and a caller that waits forever or
retries too hard. Every remote call is a failure point.

## Requirements

### JRFC-0006.1 Explicit timeouts
Every outbound network call MUST set an explicit timeout that is shorter than the
caller's own deadline.

- Applies when: the content creates an HTTP client, performs a fetch/request/RPC, or configures a client for another service or third party.
- Not applies when: no outbound network call is made, configured or described, or the code makes no network call itself: it only runs local commands or subprocesses, or exchanges messages with a local child process over stdin/stdout.
- Enforcement: agent

### JRFC-0006.2 Bounded retries with backoff
Retries MUST be bounded in count, MUST use exponential backoff with jitter, and MUST only
be applied to idempotent operations or requests carrying an idempotency key.

- Applies when: the content adds or configures retry logic, or loops that repeat a remote call.
- Enforcement: agent

### JRFC-0006.3 Degradation for optional dependencies
A call to a dependency that is not required for the core user flow SHOULD have a
fallback (cached value, default, or feature disabled) instead of failing the request.

- Applies when: the content calls a dependency whose result is optional for the response, such as recommendations, reviews or analytics.
- Enforcement: agent

### JRFC-0006.4 Dependencies in designs
A design that adds a new synchronous dependency MUST state its expected latency, its
timeout, and the behavior of the system when the dependency is down.

- Applies when: the content is a design that adds a call to a new service, database or third party.
- Artifacts: spec
- Enforcement: agent
