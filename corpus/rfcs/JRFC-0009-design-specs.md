---
id: JRFC-0009
title: Technical design specs
status: enforced
domain: specs
artifacts: [spec]
languages: [any]
owner: architecture
review_by: 2027-06-30
supersedes: []
summary: >
  The sections every technical design spec contains before implementation starts.
applies_when: >
  The content is a technical design document or spec that proposes how to build or
  change a system.
not_applies_when: >
  The content is code, a diff, an incident report or a document that does not propose a
  system design.
---

# JRFC-0009: Technical design specs

## Context

A spec is reviewed by people who were not in the room. Missing sections are the main
reason reviews go around in circles.

## Requirements

### JRFC-0009.1 Problem before solution
A spec MUST state the problem, who has it and why it matters now, before it describes
the solution.

- Applies when: the content is a design spec.
- Enforcement: agent

### JRFC-0009.2 Non-goals
A spec MUST list explicit non-goals.

- Applies when: the content is a design spec.
- Enforcement: agent

### JRFC-0009.3 Alternatives considered
A spec MUST describe at least one alternative that was considered and why it was not
chosen.

- Applies when: the content is a design spec.
- Enforcement: agent

### JRFC-0009.4 Rollout and rollback
A spec MUST describe how the change is rolled out to production and how it is rolled
back if it misbehaves.

- Applies when: the content is a design spec for a change that reaches production.
- Enforcement: agent

### JRFC-0009.5 Operability
A spec SHOULD define how success and failure are observed: key metrics, alerts, and
service level objectives where relevant.

- Applies when: the content is a design spec for a service, job or pipeline that runs in production.
- Enforcement: agent

### JRFC-0009.6 Security and privacy
A spec MUST describe what personal or sensitive data the system handles and how access to
it is controlled, or state that it handles none.

- Applies when: the content is a design spec.
- Enforcement: agent
