---
id: SCALE-0006
title: Metrics naming and cardinality
status: enforced
domain: observability
artifacts: [diff, code, spec]
languages: [any]
owner: sre
review_by: 2027-03-31
supersedes: []
summary: >
  Names, units, types and tag cardinality for application metrics sent to Datadog and
  Prometheus.
applies_when: >
  The content creates, records or configures an application metric (counter, gauge,
  histogram, timer, distribution) or its tags and labels.
not_applies_when: >
  No metric is created, recorded or configured.
---

# SCALE-0006: Metrics naming and cardinality

## Context

Metrics are billed per unique time series, and one unbounded tag once multiplied our bill
by four in a week. Consistent names also let the shared dashboards and SLO monitors work
for every service without custom queries.

## Requirements

### SCALE-0006.1 Metric name format
Metric names MUST be lowercase, dot-separated and start with the service or domain prefix,
for example `booking.reservation.created`.

- Applies when: the content defines a new metric name in code or configuration.
- Enforcement: linter

### SCALE-0006.2 Unit in the name
Metrics that measure a quantity with a unit MUST put the base unit as the last name part,
such as `_seconds`, `_bytes` or `_ms`, and MUST use the same unit across the service.

- Applies when: the content records a duration, size, amount or other measured value as a metric.
- Enforcement: agent

### SCALE-0006.3 No unbounded tags
Metric tags MUST NOT contain user ids, reservation ids, emails, raw URLs, request ids or
other values with unbounded cardinality.

- Applies when: the content adds a tag or label to a metric, or builds a tag value from request data.
- Enforcement: agent

### SCALE-0006.4 Route templates, not paths
HTTP metrics MUST tag the route template (`/restaurants/{id}`) and never the concrete path.

- Applies when: the content tags a request metric with a path, route or endpoint value.
- Enforcement: agent

### SCALE-0006.5 Cardinality budget
A new metric SHOULD stay below 1,000 unique tag combinations per service, and a design that
expects more SHOULD state the estimate and get SRE approval.

- Applies when: the content adds a metric with several tags, or tags with values taken from a list that grows over time (restaurants, cities, partners).
- Enforcement: agent

### SCALE-0006.6 Latency as histograms
Latencies MUST be recorded as histograms or distributions, not as gauges or averages
computed in the application.

- Applies when: the content records a duration, latency or response time as a metric.
- Enforcement: agent

### SCALE-0006.7 Counters for events
Events that happen (bookings created, payments failed) SHOULD be counters with an outcome
tag instead of separate metrics for success and failure.

- Applies when: the content adds metrics counting successes, failures or occurrences of an event.
- Enforcement: agent

### SCALE-0006.8 Standard tags
Every metric MUST carry the `service`, `env` and `version` tags set by the shared
telemetry library rather than by hand.

- Applies when: the content configures a metrics client, a StatsD or OpenTelemetry meter provider, or sets global metric tags.
- Enforcement: agent

### SCALE-0006.9 Removing metrics
Removing or renaming a metric SHOULD be preceded by a search for dashboards and monitors
that use it, and the pull request SHOULD list them.

- Applies when: the content deletes a metric, renames it or changes its tags.
- Enforcement: agent

### SCALE-0006.10 Business metrics
Services MAY emit business counters such as covers booked per market, provided the tags
stay within the cardinality budget.

- Applies when: the content adds a metric that counts a business event like bookings, covers, reviews or payouts.
- Enforcement: agent
