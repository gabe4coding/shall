---
id: SCALE-0069
title: Personal data in analytics events and data exports
status: enforced
domain: privacy
artifacts: [diff, code, spec]
languages: [any]
owner: dpo
review_by: 2027-03-31
supersedes: []
summary: >
  What personal data can appear in product analytics events and in data exports to
  partners, restaurants and internal teams, and how it is pseudonymised and limited.
applies_when: >
  The content adds or changes a product analytics event (Amplitude, Segment, GA, Firebase),
  a tracking call, or a data export, report download or data share that contains data
  about diners or restaurant staff.
not_applies_when: >
  No analytics event, tracking call, data export or data share is added, changed or
  described.
---

# SCALE-0069: Personal data in analytics events and data exports

## Context

Analytics tools and exported files are copied outside our main systems, kept for years
and read by many people, which makes them the usual source of GDPR complaints. Logging
has its own rule; this RFC covers analytics events and exports, where a pseudonymous id
is often enough and direct identifiers are rarely needed.

## Requirements

### SCALE-0069.1 Pseudonymous user id in events
Analytics events MUST identify the diner or restaurant user with a pseudonymous analytics
id, and MUST NOT send the internal customer id, email, phone number or name as a user id or
event property.

- Applies when: code calls an analytics SDK (`track`, `identify`, `logEvent`, `setUserId`, `setUserProperties`) or builds an analytics event payload.
- Enforcement: agent

### SCALE-0069.2 No free text in events
Analytics events MUST NOT include free text entered by users, such as booking notes,
special requests, review text or search queries typed by the diner.

- Applies when: an analytics event property is filled from a text input, comment, note, message, review or search box value.
- Enforcement: agent

### SCALE-0069.3 Events in the tracking plan
Every new analytics event and property MUST be declared in the tracking plan with its
purpose and legal basis before it is sent from production code.

- Applies when: code adds a new analytics event name or a new event property.
- Enforcement: agent

### SCALE-0069.4 Consent before tracking
Analytics and advertising SDKs MUST NOT send events or set identifiers before the user
has given consent for that purpose in the consent manager.

- Applies when: code initialises an analytics, attribution or advertising SDK, or sends an event on app start or page load.
- Enforcement: agent

### SCALE-0069.5 Coarse location only
Analytics events SHOULD carry location at city or postal-area level at most, and SHOULD
NOT include precise GPS coordinates or full addresses.

- Applies when: an analytics event property contains latitude, longitude, address or device location.
- Enforcement: agent

### SCALE-0069.6 Export only the fields needed
A data export MUST include only the columns needed for its stated purpose, and the
purpose MUST be written in the export job or request definition.

- Applies when: the content adds or changes a data export, CSV or report download, warehouse share, SFTP drop or partner feed containing diner or restaurant staff data.
- Enforcement: agent

### SCALE-0069.7 Pseudonymise exports for analysis
Exports for analysis, data science or external agencies MUST replace direct identifiers
(name, email, phone, customer id) with a keyed hash or a random token that is different
per export recipient.

- Applies when: a data export or dataset share is made for analysis, modelling, research or a third-party agency.
- Enforcement: agent

### SCALE-0069.8 Restaurant exports limited to own guests
Guest lists and reports exported to a restaurant MUST contain only diners who booked at
that restaurant and who have not opted out of sharing with it.

- Applies when: the content adds or changes a guest list, customer report or CSV download offered to restaurant users.
- Enforcement: agent

### SCALE-0069.9 Expiring export links
Download links for exported files SHOULD expire within 7 days and SHOULD require the
requester to be signed in.

- Applies when: the content creates signed URLs, download links or shared storage locations for exported files.
- Enforcement: agent

### SCALE-0069.10 Privacy review in designs
A design that adds a new analytics destination or a recurring export to a third party MUST
state the data fields sent, the purpose, the retention at the destination, and the data
processing agreement that covers it.

- Applies when: the content is a design spec that adds an analytics tool, tracking SDK, data share or partner export.
- Artifacts: spec
- Enforcement: agent

### SCALE-0069.11 Aggregated exports
An export of aggregated counts MAY omit pseudonymisation when every reported group
contains at least 10 people.

- Applies when: the content exports aggregated metrics, counts or statistics about diners or restaurant staff.
- Enforcement: agent
