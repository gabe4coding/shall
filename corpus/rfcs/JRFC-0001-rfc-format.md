---
id: JRFC-0001
title: Format and lifecycle of shall standards
status: enforced
domain: governance
artifacts: [doc, diff]
languages: [any]
owner: ai-governance
review_by: 2027-06-30
supersedes: []
summary: >
  How a shall standard is structured so humans can read it and agents can select and
  enforce single statements from it.
applies_when: >
  The content is a shall RFC file (front matter with an id like JRFC-0000) or a change to one.
not_applies_when: >
  Any content that is not a shall RFC file.
---

# JRFC-0001: Format and lifecycle of shall standards

## Context

The corpus is read by people and consumed by agents. Agents never read a whole RFC to
decide whether it applies; they receive single statements selected for the change under
review. Every statement must therefore stand on its own and carry its own applicability
hints. Keywords follow [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119) as
clarified by RFC 8174: they have their special meaning only in UPPERCASE.

## Lifecycle

| Status       | Meaning                                                             |
| ------------ | ------------------------------------------------------------------- |
| `draft`      | Proposed. Not used by any agent.                                     |
| `approved`   | Owner approved. Findings are non-blocking comments.                 |
| `enforced`   | MUST statements block merges. SHOULD/MAY stay non-blocking.         |
| `deprecated` | Kept for history; `superseded_by` points to the replacement.        |

## Requirements

### JRFC-0001.1 One normative level per statement
Each statement MUST use normative keywords of exactly one level (`MUST`/`SHALL`/`REQUIRED`,
`SHOULD`/`RECOMMENDED`, or `MAY`/`OPTIONAL`); a statement that needs two levels is split in two.

- Applies when: the content adds or edits a `### JRFC-` statement heading or its text.
- Enforcement: linter

### JRFC-0001.2 Stable statement identifiers
A published statement identifier MUST NOT be renumbered or reused for a different
requirement; a removed statement keeps its number retired.

- Applies when: the content renames, removes or reorders `### JRFC-` statement headings.
- Enforcement: agent

### JRFC-0001.3 Explicit applicability
Each statement SHOULD have an `Applies when:` line that names the concrete code, text or
situation it governs, written literally enough for a classifier to match.

- Applies when: the content adds or edits a `### JRFC-` statement.
- Enforcement: agent

### JRFC-0001.4 Human approval of status
The `status` of an RFC MUST only move to `approved` or `enforced` with the approval of the
domain owner; agents propose drafts and never promote them.

- Applies when: the content changes the `status:` field of an RFC front matter.
- Enforcement: agent

### JRFC-0001.5 Mechanical rules go to linters
A statement that a linter or static check can verify exactly SHOULD be marked
`Enforcement: linter` and implemented as a lint rule instead of an agent check.

- Applies when: the content adds a statement about syntax, formatting, config flags or other mechanically checkable properties.
- Enforcement: agent
