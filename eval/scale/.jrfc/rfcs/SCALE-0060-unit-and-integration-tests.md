---
id: SCALE-0060
title: Unit and integration tests
status: enforced
domain: testing
artifacts: [diff, code]
languages: [any]
owner: sdet
review_by: 2027-04-30
supersedes: []
summary: >
  Which unit and integration tests a change has to ship with, and how to keep them
  deterministic and free of real personal data.
applies_when: >
  The content adds or changes unit tests, integration tests, test fixtures or test
  helpers, or adds production code with new behavior.
not_applies_when: >
  The content only changes documentation, comments, or configuration with no testable
  behavior, and touches no test files.
---

# SCALE-0060: Unit and integration tests

## Context

Most regressions we ship are in code paths that had no test, or had a test that passed
by luck. Flaky tests train engineers to re-run CI instead of reading failures. Fixtures
copied from production have leaked customer data into repositories more than once.

## Requirements

### SCALE-0060.1 Tests for new behavior
A change that adds or changes a branch, error path or business rule in production code
MUST add or update a unit or integration test that fails without the change.

- Applies when: the diff adds or changes an `if`/`switch`/`when` branch, a thrown or returned error, or a calculation in non-test source code.
- Not applies when: the diff only renames, moves or reformats code without changing behavior.
- Enforcement: agent

### SCALE-0060.2 Regression test for bug fixes
A bug fix MUST include a test that reproduces the reported failure and passes only with
the fix.

- Applies when: the change is described as a fix, references a bug ticket, or changes code to correct wrong behavior.
- Enforcement: agent

### SCALE-0060.3 No fixed sleeps in tests
Tests MUST NOT wait with a fixed sleep (`sleep`, `Thread.sleep`, `time.sleep`, `setTimeout` in a test body, `delay`); they wait for a condition with a polling helper and a timeout, or use a fake clock.

- Applies when: a test file calls `sleep`, `Thread.sleep`, `time.sleep`, `delay`, `setTimeout` or `asyncio.sleep` with a constant duration.
- Enforcement: linter

### SCALE-0060.4 Deterministic time
Code under test that reads the current time MUST receive it from an injected clock, and
tests MUST set that clock to a fixed instant instead of reading the real system time.

- Applies when: a test or the code it covers calls `now()`, `Date.now`, `new Date()`, `Instant.now`, `time.Now`, `datetime.now` or `System.currentTimeMillis`.
- Enforcement: agent

### SCALE-0060.5 Seeded randomness
Tests that use random values MUST use a fixed seed or a seeded generator, and the seed MUST be printed on failure so the case can be replayed.

- Applies when: a test or fixture uses `random`, `Math.random`, `Random()`, `rand`, `uuid4`, Faker or property-based test generators.
- Enforcement: agent

### SCALE-0060.6 Synthetic test data only
Fixtures, snapshots and seed files MUST NOT contain real personal data copied from
production; names, emails, phone numbers and addresses in tests are synthetic, and email
domains use `example.com` or another reserved domain.

- Applies when: a test fixture, snapshot, seed file or test body contains names, email addresses, phone numbers, postal addresses or payment card numbers.
- Enforcement: agent

### SCALE-0060.7 Test isolation
Each test SHOULD create the state it needs and SHOULD NOT depend on data left by another
test or on the order in which tests run.

- Applies when: a test reads shared database rows, static or global variables, or files written by another test, or a test suite sets a fixed execution order.
- Enforcement: agent

### SCALE-0060.8 Real dependencies in integration tests
Integration tests of database or broker access SHOULD run against a real engine of the
same major version started in a container (Testcontainers or docker compose), not an
in-memory substitute such as H2 or SQLite.

- Applies when: an integration test configures a database, Kafka or Redis connection, or uses H2, SQLite, an in-memory broker or an embedded fake in place of the production engine.
- Enforcement: agent

### SCALE-0060.9 Assertions on behavior
A test SHOULD assert on returned values, stored state or emitted messages, and SHOULD NOT
only verify that internal collaborators were called.

- Applies when: a test body contains only mock verifications (`verify`, `toHaveBeenCalled`, `assert_called`) and no assertion on a result.
- Enforcement: agent

### SCALE-0060.10 Quarantine of flaky tests
A test that is known to be flaky MAY be moved to a quarantine suite that does not block
merges, when the move links a ticket with an owner who will fix or delete it.

- Applies when: a diff skips, disables or tags a test as flaky, quarantined or ignored (`@Disabled`, `skip`, `xit`, `t.Skip`, `pytest.mark.skip`).
- Enforcement: agent
