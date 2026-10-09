---
id: SCALE-0065
title: Incident response and communication
status: approved
domain: incidents
artifacts: [doc, spec]
languages: [any]
owner: sre
review_by: 2027-05-31
supersedes: []
summary: >
  How an ongoing production incident is declared, classified by severity, coordinated
  and communicated internally and on the status page.
applies_when: >
  The content describes incident response: declaring an incident, severity, incident
  roles, internal updates, status page messages or customer communication during an
  incident.
not_applies_when: >
  The content does not describe responding to or communicating about a production
  incident.
---

# SCALE-0065: Incident response and communication

## Context

During an incident, confusion about who leads and what severity applies costs more time
than the technical fix. Diners and restaurants need honest, timely status updates, and
support teams need to know what to tell them. These rules apply to incident logs,
channel templates, status page drafts and on-call process documents.

## Requirements

### SCALE-0065.1 Severity from the shared scale
Every declared incident MUST be assigned a severity from SEV1 to SEV4 using the shared
definitions, based on user impact and not on the size of the technical fault.

- Applies when: the content declares an incident, assigns or changes its severity, or defines severity levels.
- Enforcement: agent

### SCALE-0065.2 Incident commander named
A SEV1 or SEV2 incident MUST have a named incident commander who is not the engineer
applying the fix.

- Applies when: the content is an incident log, incident channel summary or response plan for a SEV1 or SEV2 incident.
- Enforcement: agent

### SCALE-0065.3 Dedicated channel
Each SEV1 or SEV2 incident MUST be coordinated in a dedicated Slack channel named
`inc-<date>-<short-name>`, linked from the incident ticket.

- Applies when: the content describes opening or running coordination for an incident.
- Enforcement: agent

### SCALE-0065.4 Internal update cadence
The incident commander MUST post a status update in the incident channel at least every
30 minutes for SEV1 and every 60 minutes for SEV2 until mitigation.

- Applies when: the content is an incident log, timeline of updates or incident communication plan.
- Enforcement: agent

### SCALE-0065.5 Status page for customer impact
A public status page incident MUST be opened within 15 minutes when diners or restaurants
cannot search, book, pay or manage bookings.

- Applies when: the content is an incident with impact on diners or restaurants, or a status page message or procedure.
- Enforcement: agent

### SCALE-0065.6 Status page wording
Status page messages SHOULD state the affected product and region, the user impact and
the time of the next update, and SHOULD NOT include internal system names, root cause
guesses or blame of third parties.

- Applies when: the content is a status page message, customer-facing incident update or template for one.
- Enforcement: agent

### SCALE-0065.7 Mitigate before root cause
Responders SHOULD first apply a known mitigation (rollback, flag off, fail over) and
investigate the root cause after user impact has stopped.

- Applies when: the content is an incident log or response plan that describes investigation and mitigation steps.
- Enforcement: agent

### SCALE-0065.8 Record decisions in the log
Every action that changes production during an incident MUST be recorded in the incident
log with its UTC time and the role of who performed it.

- Applies when: the content is an incident log or incident channel summary that lists actions taken.
- Enforcement: agent

### SCALE-0065.9 Response section in designs
A design for a new customer-facing service SHOULD state its expected severity when down
and which team is paged.

- Applies when: the content is a design spec for a new service or user-facing feature.
- Artifacts: spec
- Enforcement: agent

### SCALE-0065.10 Downgrading severity
The incident commander MAY lower the severity once user impact has stopped, when the
change and its reason are posted in the incident channel.

- Applies when: the content lowers, downgrades or closes the severity of an ongoing incident.
- Enforcement: agent
