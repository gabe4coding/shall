---
id: JRFC-0010
title: Feature flags
status: approved
domain: delivery
artifacts: [diff, code, spec]
languages: [any]
owner: platform
review_by: 2027-03-31
supersedes: []
summary: >
  When to put a change behind a feature flag and how flags are owned and removed.
applies_when: >
  The content adds, reads, changes or removes a feature flag, or changes user-visible
  behavior of a production service.
not_applies_when: >
  No feature flag is involved and no user-visible production behavior changes.
---

# JRFC-0010: Feature flags

## Requirements

### JRFC-0010.1 Risky changes behind a flag
A change to a critical user flow (search, booking, payment, login) SHOULD be released
behind a feature flag that can be turned off without a deploy.

- Applies when: the content changes the behavior of search, booking, payment or login flows.
- Enforcement: agent

### JRFC-0010.2 Owner and expiry
Every new feature flag MUST declare an owning team and an expiry date in its definition.

- Applies when: the content defines a new feature flag.
- Enforcement: agent

### JRFC-0010.3 Safe default
Code that reads a flag MUST behave safely when the flag service is unavailable, using the
old behavior as the default value.

- Applies when: the content reads the value of a feature flag.
- Enforcement: agent
