---
id: SCALE-0030
title: Batch and ETL job conventions
status: draft
domain: pipelines
artifacts: [diff, code, spec]
languages: [any]
owner: data-platform
review_by: 2027-06-30
supersedes: []
summary: >
  Idempotent reruns, backfills, data quality checks, scheduling and lineage for batch jobs,
  Airflow DAGs, dbt models and Spark jobs.
applies_when: >
  The content adds or changes an Airflow DAG or task, a dbt model or test, a Spark or batch job,
  or a warehouse load or transformation.
not_applies_when: >
  No batch job, DAG, dbt model, Spark job or warehouse transformation is added, changed or described.
---

# SCALE-0030: Batch and ETL job conventions

## Context

Nightly pipelines load bookings, payments and restaurant data into the warehouse that feeds
finance reports and ranking models. Jobs that append on rerun, read the wall clock instead
of their logical date, or publish unchecked data have produced wrong invoices and duplicated
revenue in reports. These rules make every run reproducible for a given interval.

## Requirements

### SCALE-0030.1 Idempotent writes per partition
A job MUST produce the same output when it runs twice for the same interval, by overwriting
or merging the target partition instead of appending to it.

- Applies when: the content writes to a warehouse table, data lake path or file from a batch job, Airflow task, dbt model or Spark job.
- Enforcement: agent

### SCALE-0030.2 Logical date instead of wall clock
Jobs MUST derive the processed interval from the scheduler's logical date, such as
`data_interval_start` in Airflow, and MUST NOT call `now()` or `CURRENT_DATE` to choose which data to process.

- Applies when: the content filters data by date or time in a batch job, DAG task, dbt model or Spark job.
- Enforcement: agent

### SCALE-0030.3 Backfills through the scheduler
Backfills SHOULD run as scheduler runs for past logical dates with bounded concurrency, not as
ad-hoc scripts that write to production tables.

- Applies when: the content adds a backfill script, sets `catchup`, `max_active_runs`, or describes reprocessing of historical data.
- Enforcement: agent

### SCALE-0030.4 Data quality checks before publishing
A model or table consumed by reports or other teams MUST have checks for primary key
uniqueness, non-null keys and row count, and those checks MUST block the downstream publish
task when they fail.

- Applies when: the content adds or changes a dbt model, a table load consumed by other teams, or its dbt tests or quality checks.
- Enforcement: agent

### SCALE-0030.5 Freshness checks on sources
Sources that arrive from other systems SHOULD declare a freshness threshold, such as dbt
source `freshness`, that alerts when the data is late.

- Applies when: the content adds or changes a dbt source, an external table, or a sensor waiting for upstream data.
- Enforcement: agent

### SCALE-0030.6 Explicit retries and timeouts on tasks
Every Airflow task MUST set `retries`, `retry_delay` and `execution_timeout`.

- Applies when: the content adds or changes an Airflow operator, task or `default_args`.
- Enforcement: linter

### SCALE-0030.7 Dependencies through sensors or datasets
A job that depends on another pipeline's output MUST wait on a sensor or dataset event for that
output, not on a fixed schedule offset.

- Applies when: the content schedules a DAG or job relative to another pipeline, or adds an `ExternalTaskSensor` or dataset trigger.
- Enforcement: agent

### SCALE-0030.8 Owner and SLA on DAGs
Every DAG SHOULD set an `owner` that is a team alias and an SLA or deadline alert for its final
task.

- Applies when: the content adds a DAG or changes its `default_args`, `owner` or SLA settings.
- Enforcement: agent

### SCALE-0030.9 Lineage metadata
Jobs SHOULD emit OpenLineage events or declare dbt `ref`/`source` dependencies so the catalogue
shows which tables feed each output.

- Applies when: the content reads from or writes to a warehouse table without `ref()` or `source()`, or adds a Spark or Python job that reads or writes tables.
- Enforcement: agent

### SCALE-0030.10 Incremental models
dbt models over large fact tables MAY use `materialized='incremental'` with a `unique_key`,
when a full refresh remains possible for backfills.

- Applies when: the content adds or changes the `materialized` config of a dbt model.
- Enforcement: agent

### SCALE-0030.11 Reprocessing in designs
A design for a new pipeline MUST state the schedule, the unit of rerun, the backfill procedure
and the downstream consumers affected by a late or wrong run.

- Applies when: the content is a design that proposes a new batch job, ETL pipeline or warehouse model.
- Artifacts: spec
- Enforcement: agent
