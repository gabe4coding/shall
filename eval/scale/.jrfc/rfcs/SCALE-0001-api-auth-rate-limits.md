---
id: SCALE-0001
title: API authentication, authorization and rate limiting
status: enforced
domain: api
artifacts: [diff, code, spec]
languages: [any]
owner: platform
review_by: 2027-04-30
supersedes: []
summary: >
  How HTTP endpoints authenticate callers, check permissions on each resource and
  limit request rates per client.
applies_when: >
  The content adds or changes an HTTP endpoint, route, controller, API gateway rule or
  middleware that authenticates callers, checks permissions or limits request rates.
not_applies_when: >
  No HTTP endpoint, route, gateway rule or request middleware is added, changed or described.
---

# SCALE-0001: API authentication, authorization and rate limiting

## Context

Our public, partner and internal APIs share the same gateway and service frameworks.
Most API security incidents come from an endpoint that forgot an ownership check or that
anyone can call without limit. These rules make the defaults explicit for every route.

## Requirements

### SCALE-0001.1 Authenticated by default
Every new route MUST require an authenticated caller unless it is listed in the service's
public-route allowlist with a comment giving the reason.

- Applies when: the content adds a route, controller method or handler, or marks a route as public or anonymous (for example `@PermitAll`, `permitAll()`, `auth: false`).
- Enforcement: agent

### SCALE-0001.2 Object-level authorization
A handler that loads a resource by an identifier from the path or body MUST check that the
authenticated caller owns or is granted access to that specific resource before returning or changing it.

- Applies when: the content adds or changes a handler that reads a resource id such as `reservationId`, `restaurantId` or `userId` from the request and loads or updates that record.
- Enforcement: agent

### SCALE-0001.3 Token validation
A service that accepts a bearer JWT MUST verify its signature, issuer, audience and expiry,
and MUST reject tokens signed with the `none` algorithm.

- Applies when: the content decodes, parses or verifies a JWT or bearer token, or configures a JWT validator or auth middleware.
- Enforcement: agent

### SCALE-0001.4 Scopes declared in the contract
Each operation in an OpenAPI document MUST declare its `security` requirement and the
OAuth scopes or roles it needs.

- Applies when: the content adds or changes an operation in an OpenAPI or Swagger file.
- Artifacts: diff, spec
- Enforcement: linter

### SCALE-0001.5 Rate limit on public and partner routes
A route exposed through the public or partner gateway MUST have a per-client rate limit
configured at the gateway or in the service.

- Applies when: the content adds a route to the public or partner API gateway configuration, or adds an endpoint documented for partners or public clients.
- Enforcement: agent

### SCALE-0001.6 Rate limit responses
A request rejected by a rate limiter MUST get status 429 with a `Retry-After` header.

- Applies when: the content implements or configures the response returned when a rate limit or quota is exceeded.
- Enforcement: agent

### SCALE-0001.7 Rate limit key
Rate limits SHOULD be keyed on the authenticated client id or API key, and SHOULD use the
client IP only for anonymous routes.

- Applies when: the content chooses the key, bucket or identifier used by a rate limiter.
- Enforcement: agent

### SCALE-0001.8 Rate limit headers
Responses from partner APIs SHOULD include `RateLimit-Limit`, `RateLimit-Remaining` and
`RateLimit-Reset` headers so clients can pace their calls.

- Applies when: the content adds or changes rate limiting on a partner-facing endpoint or its response headers.
- Enforcement: agent

### SCALE-0001.9 Service-to-service identity
Internal service-to-service calls MUST authenticate with the mesh workload identity or a
short-lived service token, not with a shared static API key.

- Applies when: the content adds authentication between two internal services, or configures a static API key or shared header for an internal caller.
- Enforcement: agent

### SCALE-0001.10 Stricter limits on expensive routes
Login, search and export routes MAY have a separate, lower rate limit than the default for
the same client.

- Applies when: the content adds or configures a login, password reset, search or bulk export endpoint.
- Enforcement: agent
