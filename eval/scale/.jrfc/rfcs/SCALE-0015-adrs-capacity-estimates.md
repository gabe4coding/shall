---
id: SCALE-0015
title: Architecture decision records and capacity estimates
status: approved
domain: specs
artifacts: [spec, doc]
languages: [any]
owner: architecture
review_by: 2027-06-30
supersedes: []
summary: >
  When and how to write an architecture decision record, and the capacity and cost
  estimates a design has to contain.
applies_when: >
  The content is an architecture decision record (ADR), or a technical design that
  introduces a new service, datastore, queue or technology, or changes expected load.
not_applies_when: >
  The content is code, a diff, an incident report, or a document that neither records an
  architecture decision nor proposes a system design.
---

# SCALE-0015: Architecture decision records and capacity estimates

## Context

Design specs describe how a system will be built; ADRs record why a lasting choice was
made so that the next team does not repeat the debate. Several past redesigns were caused
by designs that never estimated load or cost. This RFC defines both documents' minimum
content.

## Requirements

### SCALE-0015.1 ADR for lasting technology choices
Adopting a new language, datastore, message broker, framework or cloud service MUST be
recorded in an ADR in the `architecture-decisions` repository.

- Applies when: the content proposes introducing a technology, datastore, broker, framework or managed cloud service not already used by the organisation.
- Enforcement: agent

### SCALE-0015.2 ADR structure
An ADR MUST contain the sections Status, Context, Decision, Consequences and Options
Considered.

- Applies when: the content is an architecture decision record.
- Enforcement: linter

### SCALE-0015.3 ADR status values
An ADR's status MUST be one of Proposed, Accepted, Rejected or Superseded, and a
superseded ADR MUST link to the ADR that replaces it.

- Applies when: the content is an architecture decision record or changes its status.
- Enforcement: agent

### SCALE-0015.4 ADRs are immutable
An accepted ADR SHOULD NOT be rewritten; a changed decision SHOULD be recorded as a new
ADR that supersedes it.

- Applies when: the content edits the Decision or Context section of an ADR with status Accepted.
- Enforcement: agent

### SCALE-0015.5 Traffic estimate
A design that adds a service or endpoint MUST estimate peak requests per second, including
the Friday dinner peak and expected growth over 18 months.

- Applies when: the content is a design that adds a service, endpoint, consumer or job.
- Enforcement: agent

### SCALE-0015.6 Storage estimate
A design that adds a datastore or table MUST estimate row count or data size after one and
three years, and the growth rate.

- Applies when: the content is a design that adds a database, table, bucket, index or topic.
- Enforcement: agent

### SCALE-0015.7 Cost estimate
A design SHOULD include the expected monthly infrastructure cost and the main cost driver.

- Applies when: the content is a design that adds cloud resources, a managed service, a third-party vendor or significant traffic.
- Enforcement: agent

### SCALE-0015.8 Scaling limit
A design SHOULD name the first component that saturates as load grows and the load at which
it does.

- Applies when: the content is a design that states or implies expected load, throughput or data volume.
- Enforcement: agent

### SCALE-0015.9 Load test plan
A design for a component on the booking path MUST include a load test plan with a target
of at least twice the estimated peak.

- Applies when: the content is a design for a component used in search, availability, booking or payment.
- Enforcement: agent

### SCALE-0015.10 Lightweight ADRs
Small team-local decisions MAY be recorded as a short ADR in the service repository's
`docs/adr` folder instead of the central repository.

- Applies when: the content records a decision that affects only one team's services.
- Enforcement: agent
