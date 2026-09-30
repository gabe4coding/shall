---
id: JRFC-0011
title: Python type hints
status: draft
domain: python
artifacts: [diff, code]
languages: [python]
owner: data-platform
review_by: 2027-06-30
supersedes: []
summary: >
  Draft proposal: type hints on public Python functions. Not used by agents until approved.
applies_when: >
  The content is or changes Python source code.
not_applies_when: >
  The content is not Python source code.
---

# JRFC-0011: Python type hints

## Requirements

### JRFC-0011.1 Typed public functions
Public functions and methods in Python modules SHOULD have type hints for all parameters
and the return value.

- Applies when: the content adds or changes a public Python function or method.
- Violated when: at least one public function or method (its name does not start with an underscore) has a parameter other than `self` or `cls` without a type hint, or has no return annotation. One such function is enough: the other functions being fully typed does not make the content follow the requirement.
- Enforcement: agent
