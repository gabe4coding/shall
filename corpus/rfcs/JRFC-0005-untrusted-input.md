---
id: JRFC-0005
title: Untrusted input and injection
status: enforced
domain: security
artifacts: [diff, code]
languages: [any]
owner: security
review_by: 2027-01-31
supersedes: []
summary: >
  How code treats data that comes from users, clients or other systems, to prevent
  injection flaws (OWASP A03).
applies_when: >
  The content reads request parameters, bodies, headers, files or messages, or builds a
  database query, shell command, template or HTML from data.
not_applies_when: >
  The content does not read external input and does not build queries, commands or markup.
---

# JRFC-0005: Untrusted input and injection

## Context

Injection remains one of the most exploited classes of vulnerability. Every value that
crosses a trust boundary is untrusted until it is validated.

## Requirements

### JRFC-0005.1 Parameterized queries
Database queries MUST pass values as bound parameters (prepared statements or the ORM
query builder) and MUST NOT build SQL by concatenating or interpolating values into the
query string.

- Applies when: the content builds or executes a SQL or NoSQL query.
- Enforcement: agent

### JRFC-0005.2 Validate at the boundary
Request input MUST be validated against an explicit schema (types, required fields,
lengths, allowed values) before it is used by business logic.

- Applies when: the content reads request parameters, query strings, bodies or headers in a handler.
- Enforcement: agent

### JRFC-0005.3 No dynamic code or shell with input
Code MUST NOT pass untrusted input to `eval`, `Function`, `exec`, a shell, or a template
compiler.

- Applies when: the content calls eval, exec, a subprocess or shell, or compiles a template.
- Enforcement: agent
