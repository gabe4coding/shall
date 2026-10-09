---
id: JTOOL-0001
title: Using Jev in the shall tooling
status: enforced
domain: model-calls
artifacts: [diff, code]
languages: [python, yaml]
owner: ai-governance
review_by: 2027-03-31
supersedes: []
summary: >
  How the tooling asks Jev questions so that answers are cached, within budget and
  reliable, based on what failed and worked in the PoC.
applies_when: >
  The content creates a TypeSafe client, calls `system_one` or `Jev.ask`, builds Jev state
  or questions, or combines Jev answers into a decision.
not_applies_when: >
  The content does not call Jev and does not use Jev answers.
---

# JTOOL-0001: Using Jev in the shall tooling

## Context

Jev reads literally, has a bounded context, and loses accuracy with indirection and large
unrelated state. The first conflict checker put the whole corpus in one state and asked
about `existing[i]`: almost every pair came back as a conflict. A Choice split 0.51 / 0.49
between two failing classes and hid a real weakening. These rules keep those lessons.

## Requirements

### JTOOL-0001.1 One client, one wrapper
Code MUST call Jev only through `shall.jev.Jev` (which caches answers, packs requests under
the token budget and counts usage) and MUST NOT create a `TypeSafeClient` or
`AsyncTypeSafeClient` anywhere else.

- Applies when: the content creates a TypeSafe client or calls `system_one`.
- Enforcement: agent

### JTOOL-0001.2 Small state, no indirection
Jev state MUST contain only the text the questions judge; code MUST NOT put a whole corpus
or list into the state and refer to one item by index (such as `existing[i]`) in the
question text.

- Applies when: the content builds the state or the instructions of a Jev question.
- Enforcement: agent

### JTOOL-0001.3 Absolute gates
A pass/fail decision based on Jev MUST be gated on Noul probabilities or on the summed
probability of all failing Choice options, not on the probability of the single top
Choice option.

- Applies when: the content compares a Jev probability with a threshold to decide pass, fail, select or drop.
- Enforcement: agent

### JTOOL-0001.4 Pinned models
Model identifiers in configuration and code MUST be pinned versions, not moving aliases
such as `jev-latest`, `jev-preview`, `sonnet` or `opus`.

- Applies when: the content sets a Jev or Claude model name.
- Enforcement: agent
