---
id: BOOK-0001
title: Booking lifecycle events
status: enforced
domain: booking-events
artifacts: [diff, code, spec]
languages: [any]
owner: bookings
review_by: 2027-03-31
supersedes: []
summary: >
  booking-service publishes an event for every booking status change, through the
  transactional outbox, with no personal data.
applies_when: >
  The content changes the status of a booking, publishes a booking event, or consumes one.
not_applies_when: >
  The content does not touch booking status or booking events.
---

# BOOK-0001: Booking lifecycle events

## Context

Search, notifications and restaurant tools rebuild their view of a booking from these
events. A missing or out-of-transaction event leaves them inconsistent.

## Requirements

### BOOK-0001.1 Every status change publishes an event
Code that changes the status of a booking MUST enqueue a `booking.<new-status>` event with
`outbox.enqueue` inside the same database transaction as the status change.

- Applies when: the content sets or updates the status of a booking or confirmation.
- Enforcement: agent

### BOOK-0001.2 Events carry identifiers only
Booking events MUST contain only the booking id, restaurant id, new status and timestamp,
and MUST NOT contain guest names, emails or phone numbers.

- Applies when: the content builds the payload of a booking event.
- Enforcement: agent

### BOOK-0001.3 Idempotent consumers
Consumers of booking events SHOULD process each event id at most once.

- Applies when: the content consumes booking events.
- Enforcement: agent
