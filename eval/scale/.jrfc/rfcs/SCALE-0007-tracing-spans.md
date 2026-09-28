---
id: SCALE-0007
title: Distributed tracing and span attributes
status: approved
domain: observability
artifacts: [diff, code, spec]
languages: [any]
owner: sre
review_by: 2027-05-31
supersedes: []
summary: >
  Trace context propagation, span naming, span attributes and sampling with
  OpenTelemetry.
applies_when: >
  The content creates spans, sets span attributes, configures an OpenTelemetry or Datadog
  tracer, or passes trace context across HTTP, gRPC or Kafka.
not_applies_when: >
  No span, tracer or trace context propagation is created, changed or configured.
---

# SCALE-0007: Distributed tracing and span attributes

## Context

A booking crosses up to twelve services, two Kafka topics and three third parties.
Traces are only useful when context flows through every hop and spans carry the same
attribute names everywhere, so that the incident tooling can query them.

## Requirements

### SCALE-0007.1 W3C trace context
Services MUST propagate trace context with the W3C `traceparent` and `tracestate` headers
on every outbound HTTP and gRPC call.

- Applies when: the content creates an HTTP or gRPC client, or configures a propagator for a tracer.
- Enforcement: agent

### SCALE-0007.2 Context in messages
Producers MUST write the trace context into Kafka message headers, and consumers MUST
start their processing span as a child or link of that context.

- Applies when: the content produces or consumes Kafka or queue messages in a service that has tracing enabled.
- Enforcement: agent

### SCALE-0007.3 Span names
Span names MUST be low-cardinality, such as `GET /restaurants/{id}` or
`ReservationService.confirm`, and MUST NOT contain ids or query strings.

- Applies when: the content creates a span or sets a span name or resource name.
- Enforcement: agent

### SCALE-0007.4 Semantic conventions
Span attributes SHOULD use the OpenTelemetry semantic convention names (`http.request.method`,
`db.system`, `messaging.destination.name`) instead of custom names for the same thing.

- Applies when: the content sets attributes or tags on a span.
- Enforcement: agent

### SCALE-0007.5 No personal data in spans
Span attributes and span events MUST NOT contain names, emails, phone numbers, full
request bodies or SQL with literal values.

- Applies when: the content sets span attributes, span events or baggage from request, user or database data.
- Enforcement: agent

### SCALE-0007.6 Errors recorded on spans
When an operation fails, the span MUST be marked with error status and the exception
recorded on it before the span ends.

- Applies when: the content catches an exception or error inside code that has an active or manually created span.
- Enforcement: agent

### SCALE-0007.7 Spans always ended
Manually started spans MUST be ended in a `finally` block or with a scoped helper
(`with tracer.start_as_current_span`, `span.use {}`, `defer span.End()`).

- Applies when: the content calls `startSpan`, `start_span`, `spanBuilder().startSpan()` or `tracer.Start` directly.
- Enforcement: agent

### SCALE-0007.8 Sampling at the collector
Services SHOULD send all spans to the local collector and leave sampling decisions to the
collector's tail-sampling policy.

- Applies when: the content configures a sampler, sampling rate or trace exporter in a service.
- Enforcement: agent

### SCALE-0007.9 Span granularity
Code SHOULD NOT create a manual span for each loop iteration or for in-memory functions
that take less than a millisecond.

- Applies when: the content creates spans inside a loop or around small in-process functions.
- Enforcement: agent

### SCALE-0007.10 Business identifiers
Spans MAY carry a small set of business attributes such as `restaurant.id` or `booking.channel`
to help debugging, as long as they contain no personal data.

- Applies when: the content adds a business identifier as a span attribute.
- Enforcement: agent
