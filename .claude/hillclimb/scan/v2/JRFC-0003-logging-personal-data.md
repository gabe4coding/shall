---
id: JRFC-0003
title: Logging and personal data
status: enforced
domain: observability
artifacts: [diff, code, spec]
languages: [any]
owner: sre
review_by: 2027-03-31
supersedes: []
summary: >
  How services write logs so that they are searchable, correlated and free of personal
  data.
applies_when: >
  The content is code of a service (a backend, API, worker or job that runs in production)
  and writes log lines, error messages, traces or metric attributes, or configures a logger.
not_applies_when: >
  No logging, tracing, metrics or telemetry is written or configured, or the code is not a
  service: a command-line tool, a script, a benchmark, a build or test helper, or a developer
  tool that runs on a laptop.
---

# JRFC-0003: Logging and personal data

## Context

Logs are copied to many systems with broad access and long retention. Personal data in
logs is a GDPR exposure that is hard to purge. Unstructured logs cannot be queried
reliably during incidents.

## Requirements

### JRFC-0003.1 No personal data in logs
Services MUST NOT write personal data — names, email addresses, phone numbers, postal
addresses, payment card data, or free-text messages written by customers — to logs,
traces or metric attributes; use an opaque identifier such as the customer id instead.

- Applies when: service code has a log, print, logger, span attribute or metric label call that includes fields of a user, customer, guest, reservation or payment.
- Not applies when: the code is a command-line tool, script, benchmark or local developer tool, not a service.
- Enforcement: agent

### JRFC-0003.2 Structured logs
Services MUST emit logs as structured key-value records through the shared logger, not
as interpolated free-text strings built by concatenation.

- Applies when: service code adds or changes a log call.
- Not applies when: the content only changes logger configuration, or the code is a command-line tool, script, benchmark or local developer tool, not a service; progress or status messages printed to the terminal for the person running the program are a sign of a command-line tool.
- Enforcement: agent

### JRFC-0003.3 Correlation identifier
Every log record written while handling a request or message MUST include the
correlation id of that request or message.

- Applies when: the content logs inside an HTTP handler, message consumer or job that processes a request or message.
- Enforcement: agent

### JRFC-0003.4 Meaningful levels
Log levels SHOULD be used as follows: `error` for failures that need human action,
`warn` for degraded but handled situations, `info` for business events, and `debug` for
diagnostic detail that is off in production.

- Applies when: service code adds or changes a log call with a level.
- Not applies when: the code is a command-line tool, script, benchmark or local developer tool, not a service.
- Enforcement: agent
