---
id: SCALE-0010
title: Query performance and indexes
status: enforced
domain: data
artifacts: [diff, code, spec]
languages: [any]
owner: data-platform
review_by: 2027-04-30
supersedes: []
summary: >
  Indexes, bounded result sets and ORM access patterns that keep relational queries fast
  as tables grow.
applies_when: >
  The content writes or changes a SQL query, an ORM query or repository method, or adds or
  drops an index on a relational table.
not_applies_when: >
  No SQL query, ORM query, repository method or index is added, changed or described.
---

# SCALE-0010: Query performance and indexes

## Context

The reservations and availability tables hold billions of rows and grow every day. Most
database incidents trace back to a query that was fast on a test dataset: an unbounded
SELECT, a missing index on a new filter, or an ORM loop issuing thousands of queries.

## Requirements

### SCALE-0010.1 Bounded result sets
Queries that return rows to a request handler MUST have a `LIMIT` or page size, and MUST NOT
load an entire table or an unbounded relation.

- Applies when: the content adds a SELECT, `findAll`, `.all()`, `objects.filter` or repository method whose result is returned or iterated.
- Enforcement: agent

### SCALE-0010.2 No N+1 queries
Code MUST NOT run one query per item of a collection; it has to batch with `IN`, a join or
the ORM's eager loading (`select_related`, `prefetch_related`, `JOIN FETCH`, `include`).

- Applies when: the content accesses a lazy relation or calls a repository or query method inside a loop over results.
- Enforcement: agent

### SCALE-0010.3 Index for new filters
A new query that filters or sorts a table with more than one million rows MUST be backed
by an index on the filtered columns, added in the same change or already present.

- Applies when: the content adds a WHERE clause, ORDER BY or ORM filter on a large table such as reservations, availability, reviews or users.
- Enforcement: agent

### SCALE-0010.4 Concurrent index creation
Indexes on existing PostgreSQL tables MUST be created with `CREATE INDEX CONCURRENTLY`.

- Applies when: the content contains `CREATE INDEX` on an existing table in a migration.
- Enforcement: linter

### SCALE-0010.5 Select only needed columns
Queries on wide tables SHOULD select the needed columns instead of `SELECT *` or full
entity loads.

- Applies when: the content writes `SELECT *` or loads full entities only to read one or two fields.
- Enforcement: agent

### SCALE-0010.6 Keyset pagination for deep pages
Endpoints that page through large tables SHOULD use keyset pagination on an indexed column
rather than `OFFSET`.

- Applies when: the content uses `OFFSET`, `.skip()`, `Pageable` or page-number paging on a large table.
- Enforcement: agent

### SCALE-0010.7 No functions on indexed columns
Filters SHOULD NOT wrap an indexed column in a function (`LOWER(email)`, `DATE(created_at)`)
unless a matching expression index exists.

- Applies when: the content writes a WHERE clause that applies a function or cast to a column.
- Enforcement: agent

### SCALE-0010.8 Statement timeout
Application database users MUST have a `statement_timeout` of at most 5 seconds for
request traffic, and batch jobs MUST set their own explicit timeout.

- Applies when: the content configures a database connection, data source, connection pool or database role.
- Enforcement: agent

### SCALE-0010.9 Heavy reads on replicas
Reporting, export and analytics queries MUST run on a read replica or the warehouse, not on
the primary.

- Applies when: the content adds a report, export, aggregation or analytics query in a service.
- Enforcement: agent

### SCALE-0010.10 Query plans in reviews
A pull request that adds a query on a large table MAY include the `EXPLAIN ANALYZE` output
from staging.

- Applies when: the content adds a new query on a large table.
- Enforcement: agent
