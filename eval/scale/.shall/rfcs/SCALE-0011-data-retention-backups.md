---
id: SCALE-0011
title: Data retention, soft delete and table backups
status: draft
domain: data
artifacts: [diff, code, spec]
languages: [any]
owner: data-platform
review_by: 2027-06-30
supersedes: []
summary: >
  How tables declare retention, implement soft delete and purge, and are covered by
  backups and restore tests.
applies_when: >
  The content creates a table, adds a deleted or archived flag, deletes or purges rows, or
  configures database backups, snapshots or point-in-time recovery.
not_applies_when: >
  No table is created, no rows are deleted or archived, and no backup configuration is
  added, changed or described.
---

# SCALE-0011: Data retention, soft delete and table backups

## Context

Tables grow forever unless someone decides otherwise, and a bad deploy that deletes rows
can only be undone with a working backup. This draft proposes that retention and recovery
become part of the schema change itself, not an afterthought.

## Requirements

### SCALE-0011.1 Retention declared for new tables
A migration that creates a table MUST declare the table's retention period in a table
comment or in the service's `data-catalog.yaml`.

- Applies when: the content contains `CREATE TABLE` or an ORM model for a new table.
- Enforcement: agent

### SCALE-0011.2 Purge job for time-bound data
Tables with a finite retention MUST have a scheduled purge or archive job that deletes
expired rows in batches of at most 10,000 rows.

- Applies when: the content adds a table with a retention period, or adds a job that deletes old rows.
- Enforcement: agent

### SCALE-0011.3 Soft delete column
Soft delete SHOULD use a nullable `deleted_at` timestamp rather than a boolean flag.

- Applies when: the content adds a column that marks rows as deleted, archived or inactive.
- Enforcement: agent

### SCALE-0011.4 Soft-deleted rows filtered
Queries on a soft-deleted table MUST exclude deleted rows by default through a global ORM
filter or a view, not by a condition repeated in each query.

- Applies when: the content queries a table that has a `deleted_at` or `is_deleted` column, or adds such a column.
- Enforcement: agent

### SCALE-0011.5 Unique constraints with soft delete
Unique constraints on soft-deleted tables SHOULD be partial indexes that only cover rows
where `deleted_at IS NULL`.

- Applies when: the content adds a unique constraint or unique index on a table with soft delete.
- Enforcement: agent

### SCALE-0011.6 Bulk deletes guarded
A `DELETE` or `UPDATE` without a `WHERE` clause, or one that can touch more than 10,000 rows,
MUST NOT run in a request handler.

- Applies when: the content issues a DELETE or UPDATE statement or an ORM bulk delete or bulk update.
- Enforcement: agent

### SCALE-0011.7 Point-in-time recovery
Production databases MUST have point-in-time recovery enabled with at least 14 days of
retention.

- Applies when: the content creates or changes a production database instance, cluster or its backup settings.
- Enforcement: agent

### SCALE-0011.8 Restore tested
Each production database SHOULD have a restore test run at least every quarter, with the
measured restore time recorded in the service runbook.

- Applies when: the content creates a new production database or changes its backup or restore procedure.
- Enforcement: agent

### SCALE-0011.9 Archive to cold storage
Rows past their online retention MAY be exported to the data lake in Parquet before they
are deleted.

- Applies when: the content implements a purge or archive job for old rows.
- Enforcement: agent
