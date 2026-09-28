---
id: SCALE-0064
title: Incident reports and postmortems
status: enforced
domain: incidents
artifacts: [doc]
languages: [any]
owner: sre
review_by: 2027-03-31
supersedes: []
summary: >
  The content of an incident report or postmortem: timeline, measured impact, root
  cause, blameless wording and tracked action items.
applies_when: >
  The content is an incident report, a postmortem, a post-incident review or an incident
  timeline.
not_applies_when: >
  The content is not a report or review of a production incident.
---

# SCALE-0064: Incident reports and postmortems

## Context

Postmortems are how the company learns from outages, and they are read months later by
people who were not there. A report that says "some users were affected" or blames a
person teaches nothing and discourages honest reporting. Action items without owners
and dates are not done.

## Requirements

### SCALE-0064.1 Postmortem for major incidents
A postmortem MUST be published within five business days for every SEV1 and SEV2
incident, and for any incident that caused data loss or a personal data breach.

- Applies when: the content is an incident report or incident summary for a SEV1 or SEV2 incident, or for an incident involving data loss or a data breach.
- Enforcement: agent

### SCALE-0064.2 Timeline in UTC
A postmortem MUST include a timeline with UTC timestamps for the start of impact,
detection, first response, mitigation and full resolution.

- Applies when: the content is a postmortem or an incident timeline.
- Enforcement: agent

### SCALE-0064.3 Impact in numbers
A postmortem MUST quantify the impact with numbers: duration, affected bookings or
requests, affected users or restaurants, error rate, and revenue or refunds when known.

- Applies when: the content is a postmortem or incident report that has an impact or summary section.
- Enforcement: agent

### SCALE-0064.4 Root cause and triggers
A postmortem MUST state the root cause and the trigger separately, and MUST explain why
existing safeguards (tests, alerts, rollout checks) did not stop the incident.

- Applies when: the content is a postmortem with a root cause, cause or analysis section.
- Enforcement: agent

### SCALE-0064.5 Blameless language
A postmortem MUST describe actions of people by role (for example "the on-call engineer")
and MUST NOT name or blame individuals for the failure.

- Applies when: a postmortem or incident report describes what a person did, decided or missed.
- Enforcement: agent

### SCALE-0064.6 Action items with owner and date
Every action item in a postmortem MUST have a single owner, a due date and a ticket link.

- Applies when: a postmortem contains an action items, follow-ups or next steps section.
- Enforcement: agent

### SCALE-0064.7 Action items prevent recurrence
A postmortem SHOULD include at least one action item that prevents the same class of
failure or reduces time to detect it, not only a fix of the single defect.

- Applies when: a postmortem lists action items or follow-ups.
- Enforcement: agent

### SCALE-0064.8 Detection analysis
A postmortem SHOULD state how the incident was detected (alert, customer report,
engineer) and how long it took from start of impact to detection.

- Applies when: the content is a postmortem or incident report.
- Enforcement: agent

### SCALE-0064.9 What went well
A postmortem MAY include a section on what went well, such as mitigations or tooling that
shortened the incident.

- Applies when: the content is a postmortem.
- Enforcement: agent

### SCALE-0064.10 No personal data in reports
A postmortem MUST NOT include customer names, emails, phone numbers or screenshots that
show them; affected customers are referred to by count or opaque id.

- Applies when: a postmortem or incident report includes customer examples, screenshots, log excerpts or support tickets.
- Enforcement: agent
