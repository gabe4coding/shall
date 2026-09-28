---
id: JTOOL-0003
title: jrfc CLI contract
status: enforced
domain: python
artifacts: [diff, code]
languages: [python, shell]
owner: ai-governance
review_by: 2027-03-31
supersedes: []
summary: >
  Behavior of the `jrfc` commands that CI and agents rely on: exit codes, which commands
  may call a model, and reproducible generated files.
applies_when: >
  The content changes the jrfc CLI (`cli.py`, `bin/` scripts) or code that writes
  generated files such as the index.
not_applies_when: >
  The content does not change CLI commands, exit codes or generated files.
---

# JTOOL-0003: jrfc CLI contract

## Requirements

### JTOOL-0003.1 Stable exit codes
Commands MUST exit with 0 on success, 1 on errors, 2 on blocking findings and 3 when a Jev
request fails after retries, and new failure cases MUST reuse one of these codes.

- Applies when: the content adds or changes a `sys.exit`, a returned exit code, or an `exit` in a script.
- Enforcement: agent

### JTOOL-0003.2 Deterministic commands stay model-free
The commands `lint`, `build`, `new`, `show`, `list`, `catalog`, `init`, `validate`, `bundle`
and `publish` MUST NOT call Jev or Claude.

- Applies when: the content changes the implementation of one of these commands or code they import.
- Enforcement: agent

### JTOOL-0003.3 Reproducible generated files
Generated files MUST be byte-for-byte reproducible from their inputs: no timestamps, no
absolute paths, and sorted keys in JSON.

- Applies when: the content writes an index, catalog or other generated file.
- Enforcement: agent
