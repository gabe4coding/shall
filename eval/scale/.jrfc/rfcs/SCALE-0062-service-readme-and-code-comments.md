---
id: SCALE-0062
title: Service READMEs and code comments
status: enforced
domain: documentation
artifacts: [doc, diff, code]
languages: [any]
owner: architecture
review_by: 2027-03-31
supersedes: []
summary: >
  What every service README contains, and how code comments and docstrings explain the
  reasons behind the code.
applies_when: >
  The content adds or changes a repository README, a code comment, a docstring, or a
  public function, class or module of a service.
not_applies_when: >
  No README, comment, docstring or public code interface is added, changed or described.
---

# SCALE-0062: Service READMEs and code comments

## Context

Engineers joining an incident or a new team start from the README; when it does not name
the owner or explain how to run the service, they lose the first hour. Comments that
restate the code go stale, while comments that record why a choice was made save the
next reader from undoing it.

## Requirements

### SCALE-0062.1 README owner and contact
A service README MUST name the owning team, its Slack channel, and its on-call rotation
or escalation path.

- Applies when: the content adds or changes the top-level `README.md` of a service or library repository.
- Enforcement: agent

### SCALE-0062.2 How to run locally
A service README MUST give the exact commands to install dependencies, run the service
locally and run its tests, and MUST list the environment variables needed to start it.

- Applies when: the content adds or changes the top-level `README.md` of a service repository, or changes build, start or test commands without updating it.
- Enforcement: agent

### SCALE-0062.3 Dependencies listed
A service README MUST list the databases, topics, caches and other services the service
reads from or writes to, with a link to each owner's documentation.

- Applies when: the content adds or changes a service README, or adds a new database, Kafka topic, cache or service client to a service.
- Enforcement: agent

### SCALE-0062.4 Links to dashboards and runbooks
A service README SHOULD link to the service's main dashboard, its alert runbooks and its
architecture diagram.

- Applies when: the content adds or changes the top-level `README.md` of a service repository.
- Enforcement: agent

### SCALE-0062.5 Standard README headings
The README of a repository in the `services/` catalog MUST contain the headings `Owner`,
`Running locally`, `Dependencies` and `Operations`.

- Applies when: the content adds or changes the top-level `README.md` of a repository listed in the service catalog.
- Enforcement: linter

### SCALE-0062.6 Comments explain why
A code comment SHOULD explain the reason for non-obvious code (a constraint, a workaround,
a business rule, a link to a ticket) and SHOULD NOT paraphrase what the next line does.

- Applies when: the diff adds or changes an inline or block comment in source code.
- Enforcement: agent

### SCALE-0062.7 Docstrings on public interfaces
Public functions, classes and modules exported from a shared library MUST have a
docstring or KDoc/JSDoc/GoDoc comment stating what they do, their error behavior and any
side effects.

- Applies when: the diff adds or changes an exported or public function, class, interface or module in a shared library or SDK package.
- Enforcement: agent

### SCALE-0062.8 Workarounds reference a ticket
A comment that marks a workaround, `TODO`, `FIXME` or `HACK` MUST reference a ticket id,
so that the debt can be tracked and removed.

- Applies when: the diff adds a comment containing `TODO`, `FIXME`, `HACK`, `XXX` or the word workaround.
- Enforcement: agent

### SCALE-0062.9 No commented-out code
Changes SHOULD NOT add blocks of commented-out code; removed code is recovered from
version control.

- Applies when: the diff adds comment lines that contain source code statements, such as calls, assignments or control flow.
- Enforcement: agent

### SCALE-0062.10 Architecture decision records
A repository MAY keep architecture decision records in `docs/adr/`, one numbered file per
decision, instead of recording decisions in the README.

- Applies when: the content adds a file under `docs/adr/` or a README section that records a design decision.
- Artifacts: doc, diff
- Enforcement: agent
