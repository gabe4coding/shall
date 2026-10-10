---
id: JRFC-0002
title: HTTP API design
status: enforced
domain: api
artifacts: [diff, code, spec]
languages: [any]
owner: platform
review_by: 2027-03-31
supersedes: []
summary: >
  Conventions for HTTP endpoints: resource paths, methods, errors, pagination,
  idempotency and versioning.
applies_when: >
  The content adds, changes or describes an HTTP endpoint, route, controller, handler,
  request/response payload or OpenAPI contract.
not_applies_when: >
  No HTTP endpoint or API contract is added, changed or described.
---

# JRFC-0002: HTTP API design

## Context

Consistent APIs reduce integration bugs between teams and make client code generic.
These rules follow common public guidance (resource-oriented design, RFC 9110 semantics,
RFC 9457 problem details).

## Requirements

### JRFC-0002.1 Resource-oriented paths
Endpoint paths MUST name resources with plural nouns in kebab-case (for example
`/booking-requests/{id}`) and MUST NOT contain verbs such as `get`, `create` or `update`.

- Applies when: the content defines or changes an HTTP route path.
- Not applies when: the code only calls an HTTP API as a client (it builds a URL or sends a request to another service) and defines no route of its own.
- Enforcement: agent

### JRFC-0002.2 Methods match semantics
Handlers MUST use HTTP methods according to RFC 9110: GET and HEAD MUST NOT change
server state, and state changes use POST, PUT, PATCH or DELETE.

- Applies when: the content defines an HTTP handler and its method.
- Enforcement: agent

### JRFC-0002.3 Problem details for errors
Error responses MUST use the `application/problem+json` format of RFC 9457 with at least
`type`, `title` and `status`, and MUST NOT expose stack traces or internal exception text.

- Applies when: the content builds or returns an HTTP error response, or describes API errors.
- Enforcement: agent

### JRFC-0002.4 Paginated collections
Endpoints that return a collection MUST be paginated with a bounded maximum page size.

- Applies when: the content adds or changes an endpoint that returns a list or collection of items.
- Enforcement: agent

### JRFC-0002.5 Idempotent creation of money- or booking-related resources
POST endpoints that create reservations, payments or other resources with business side
effects MUST accept an `Idempotency-Key` header and return the original result for a
repeated key.

- Applies when: the content adds or changes a POST endpoint that creates a reservation, booking, payment, order or similar resource.
- Enforcement: agent

### JRFC-0002.6 Versioning of breaking changes
A breaking change to a public API contract SHOULD be released as a new major version
path (for example `/v2/`) while the previous version keeps working during a deprecation
period.

- Applies when: the content removes or renames response fields, changes field types, or changes required request fields of an existing endpoint.
- Enforcement: agent
