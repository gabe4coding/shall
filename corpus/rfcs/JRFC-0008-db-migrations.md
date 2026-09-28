---
id: JRFC-0008
title: Zero-downtime database migrations
status: approved
domain: data
artifacts: [diff, code, spec]
languages: [any]
owner: data-platform
review_by: 2027-02-28
supersedes: []
summary: >
  How to change relational schemas without downtime, using the expand/contract pattern.
applies_when: >
  The content adds or changes a database migration, DDL statement or schema definition.
not_applies_when: >
  No database schema or migration is involved.
---

# JRFC-0008: Zero-downtime database migrations

## Context

Services are deployed with rolling updates, so the old and the new version of the code
run against the same schema at the same time. Status is `approved`: findings are
non-blocking while teams adopt the tooling.

## Requirements

### JRFC-0008.1 Backward-compatible steps
Each migration MUST be compatible with the previous version of the application code; a
breaking change is split into expand, migrate and contract steps deployed separately.

- Applies when: the content adds a migration that drops, renames or changes the type of a column or table.
- Enforcement: agent

### JRFC-0008.2 New columns are nullable or defaulted
A column added to an existing table MUST be nullable or have a default value.

- Applies when: the content adds a column to an existing table.
- Enforcement: agent

### JRFC-0008.3 No long locks on large tables
Migrations on large tables MUST NOT take locks that block writes for long periods;
indexes are created concurrently and data backfills run in batches outside the
migration.

- Applies when: the content creates an index, rewrites a table, or updates many rows in a migration.
- Enforcement: agent

### JRFC-0008.4 Reversible migrations
Migrations SHOULD provide a down step, or state in a comment why the change cannot be
reversed.

- Applies when: the content adds a migration file.
- Enforcement: agent
