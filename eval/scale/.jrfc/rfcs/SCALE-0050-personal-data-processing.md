---
id: SCALE-0050
title: Personal data processing and consent
status: enforced
domain: privacy
artifacts: [diff, code, spec]
languages: [any]
owner: dpo
review_by: 2027-01-31
supersedes: []
summary: >
  Consent before tracking, data minimisation, retention limits, data subject access and
  deletion, and sharing personal data with processors, under GDPR.
applies_when: >
  The content collects, stores, exports, shares, retains or deletes personal data of
  diners or restaurant staff, adds analytics or advertising tracking, or describes a
  new store of personal data.
not_applies_when: >
  No personal data is collected, stored, shared, exported, retained or deleted and no
  user tracking is added or changed.
---

# SCALE-0050: Personal data processing and consent

## Context

We process names, contact details, booking history and dining preferences of diners in
the EU, so GDPR and ePrivacy rules apply to every product change. Audit findings
usually come from trackers firing before consent, new tables nobody deletes, and data
sent to a new vendor without a contract. Logging of personal data is covered by the
logging standard and is not repeated here.

## Requirements

### SCALE-0050.1 Consent before tracking
Analytics, advertising and session-replay SDKs (Google Analytics, Meta Pixel, Amplitude,
Hotjar) MUST NOT be initialised or send events before the user has granted consent for
that purpose in the consent management platform.

- Applies when: the content adds, initialises or configures an analytics, advertising, attribution or session-replay SDK or tag, or sends tracking events.
- Enforcement: agent

### SCALE-0050.2 Purpose-specific consent checks
Code MUST check the consent for the specific purpose (`analytics`, `advertising`,
`personalisation`) rather than one global consent flag.

- Applies when: the content reads the consent state or gates a feature on user consent.
- Enforcement: agent

### SCALE-0050.3 Documented purpose for new personal data
A new field of personal data (phone number, birth date, dining preferences, precise
location) MUST have a documented purpose in the data inventory, and a field not needed
for that purpose MUST NOT be collected.

- Applies when: the content adds a form field, API field, database column or event property that holds personal data.
- Enforcement: agent

### SCALE-0050.4 Special category data
Health data, such as allergies or medical dietary needs, MUST NOT be stored on the user
profile without the user's explicit consent for that purpose.

- Applies when: the content collects or stores allergies, dietary needs, accessibility needs or other health-related information.
- Enforcement: agent

### SCALE-0050.5 Retention period for every store
Every table, bucket, index or topic that holds personal data MUST have a defined
retention period, and a TTL or scheduled job MUST delete or anonymise records older
than that period.

- Applies when: the content creates a table, bucket, search index, cache or topic that stores personal data, or changes its retention.
- Enforcement: agent

### SCALE-0050.6 Stores registered for access requests
A new store of personal data MUST be registered with the data subject request service so
that access and export requests include its data.

- Applies when: the content adds a new database, table, bucket or third-party system that stores data linked to a user id, email or phone number.
- Enforcement: agent

### SCALE-0050.7 Deletion reaches every copy
An account deletion request MUST remove or anonymise the user's data in every store
within 30 days, including search indexes, caches, warehouse tables and processors.

- Applies when: the content handles account deletion, erasure requests, or adds a copy of user data to another store.
- Enforcement: agent

### SCALE-0050.8 Processors under contract
Personal data MUST NOT be sent to a new third-party processor (SaaS tool, SDK or external
API) before a data processing agreement is signed and the processor is listed in the
processor register.

- Applies when: the content sends user data to a third-party service, adds a third-party SDK that receives user data, or describes a new vendor integration.
- Enforcement: agent

### SCALE-0050.9 Pseudonymous ids in analytics
Data exported to the data warehouse or to analytics tools SHOULD identify users by a
pseudonymous id instead of email address or phone number.

- Applies when: the content exports user-level data to the warehouse, an analytics tool or a data science dataset.
- Enforcement: agent

### SCALE-0050.10 No production personal data outside production
Production personal data SHOULD NOT be copied to staging, development or local
environments; synthetic or anonymised datasets are used instead.

- Applies when: the content copies, dumps, restores or seeds data from production into another environment.
- Enforcement: agent

### SCALE-0050.11 Aggregates beyond retention
Aggregated statistics with no user-level rows, such as bookings per city per day, MAY be
kept beyond the retention period of the personal data they were computed from.

- Applies when: the content computes or stores aggregated statistics from personal data, or applies retention to aggregate tables.
- Enforcement: agent
