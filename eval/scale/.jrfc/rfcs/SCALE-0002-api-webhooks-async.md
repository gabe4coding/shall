---
id: SCALE-0002
title: Webhooks and long-running API operations
status: approved
domain: api
artifacts: [diff, code, spec]
languages: [any]
owner: platform
review_by: 2027-05-31
supersedes: []
summary: >
  How services send webhooks to partners and expose operations that take longer than a
  normal request.
applies_when: >
  The content sends or receives a webhook, registers webhook subscriptions, or adds an
  HTTP endpoint that starts a job or operation that finishes after the response.
not_applies_when: >
  No webhook is sent or received and no endpoint starts an asynchronous job or operation.
---

# SCALE-0002: Webhooks and long-running API operations

## Context

Restaurants' POS vendors and channel partners receive booking events by webhook, and
several of our APIs start exports or bulk updates that take minutes. Partners have to be
able to trust webhook payloads and to poll long jobs without guessing.

## Requirements

### SCALE-0002.1 Signed webhook payloads
Every outgoing webhook MUST carry an HMAC-SHA256 signature of the raw body and a timestamp
in request headers, computed with a secret specific to that subscription.

- Applies when: the content builds or sends an outgoing webhook request to a partner or customer URL.
- Enforcement: agent

### SCALE-0002.2 Verify incoming webhooks
A handler for an incoming webhook MUST verify the provider's signature on the raw body and
MUST reject requests whose timestamp is older than five minutes.

- Applies when: the content adds or changes an endpoint that receives webhooks or callbacks from a third party (payment provider, POS vendor, messaging provider).
- Enforcement: agent

### SCALE-0002.3 Webhook event identity
Each webhook payload MUST include a unique event id and an event type so receivers can
deduplicate deliveries.

- Applies when: the content defines or changes the payload body of an outgoing webhook.
- Enforcement: agent

### SCALE-0002.4 Delivery off the request path
Webhook delivery MUST run from a queue or outbox worker, not inline in the request that
caused the event.

- Applies when: the content sends an HTTP request to a subscriber URL inside a request handler, transaction or domain service.
- Enforcement: agent

### SCALE-0002.5 Redelivery and disabling
Failed webhook deliveries SHOULD be retried for at least 24 hours, and a subscription
SHOULD be disabled with a notification to its owner after repeated failure over three days.

- Applies when: the content implements or configures retry, dead-lettering or disabling of webhook deliveries.
- Enforcement: agent

### SCALE-0002.6 Subscriber URL validation
Webhook subscription URLs MUST use HTTPS and MUST NOT resolve to private, loopback or
link-local addresses.

- Applies when: the content registers, validates or stores a webhook subscription or callback URL supplied by a customer.
- Enforcement: agent

### SCALE-0002.7 Accepted status for long operations
An endpoint that starts work expected to take longer than two seconds SHOULD return 202
with a `Location` header pointing to an operation status resource.

- Applies when: the content adds an endpoint that starts an export, import, bulk update, report generation or other long-running job.
- Enforcement: agent

### SCALE-0002.8 Operation status resource
An operation status resource MUST expose a state from a fixed set (`pending`, `running`,
`succeeded`, `failed`) and, when finished, a link to the result or an error.

- Applies when: the content adds or changes an endpoint that reports the status of an asynchronous job or operation.
- Enforcement: agent

### SCALE-0002.9 Callback instead of polling
A long-running operation MAY accept a callback URL so the client is notified on completion
instead of polling.

- Applies when: the content designs or implements the request body of an endpoint that starts a long-running job.
- Enforcement: agent
