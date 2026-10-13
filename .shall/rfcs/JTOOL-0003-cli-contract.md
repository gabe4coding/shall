---
id: JTOOL-0003
title: shall CLI contract
status: enforced
domain: python
artifacts: [diff, code]
languages: [python, shell]
owner: ai-governance
review_by: 2027-03-31
supersedes: []
summary: >
  Behavior of the `shall` commands that CI and agents rely on: exit codes, which commands
  may call a model, and reproducible generated files.
applies_when: >
  The content changes the shall CLI (`cli.py`, `bin/` scripts) or code that writes
  generated files such as the index.
not_applies_when: >
  The content does not change CLI commands, exit codes or generated files.
---

# JTOOL-0003: shall CLI contract

## Checks in code

Code checks part of these rules. Review checks the rest.

- JTOOL-0003.1: `ExitCode` in `plugins/shall/tooling/src/shall/cli.py`, and `plugins/shall/tooling/tests/test_boundaries.py`
  (`test_every_command_returns_an_exit_code`, `test_usage_error_exits_1_not_2`,
  `test_scripts_exit_with_shall_codes_only`).
- JTOOL-0003.2: `make check` (import-linter contract "Deterministic modules call no model"), and `plugins/shall/tooling/tests/test_boundaries.py`
  (`test_deterministic_commands_reach_no_model_module`, `test_deterministic_commands_do_not_load_the_sdk`).
- JTOOL-0003.3: `make check` and `make self-check` (`shall build --check`).

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
