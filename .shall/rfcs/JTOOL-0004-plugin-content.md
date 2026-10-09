---
id: JTOOL-0004
title: Plugin skills and agents
status: approved
domain: claude-plugin
artifacts: [diff, doc]
languages: [any]
owner: ai-governance
review_by: 2027-03-31
supersedes: []
summary: >
  How the skills and agents of the shall plugin are written so that Claude Code loads the
  right one and follows it.
applies_when: >
  The content adds or changes a SKILL.md, an agent definition under `agents/`, or the
  plugin manifest.
not_applies_when: >
  The content is not a skill, agent definition or plugin manifest.
---

# JTOOL-0004: Plugin skills and agents

## Requirements

### JTOOL-0004.1 Descriptions say when to use
The `description` of a skill or agent MUST state the situations in which it is used, not
only what it does.

- Applies when: the content adds or changes the `description` field of a skill or agent.
- Enforcement: agent

### JTOOL-0004.2 One reviewer prompt
The review instructions MUST live only in `agents/shall-reviewer.md`, which both the
in-session agent and the CI pipeline use; skills and code MUST NOT carry a second copy.

- Applies when: the content adds or changes reviewer instructions or the prompt sent to the review agent.
- Enforcement: agent

### JTOOL-0004.3 Commands in skills exist
Every `shall` command and flag shown in a skill SHOULD exist in the CLI (`shall <command> -h`).

- Applies when: the content adds or changes a `shall` command example in a skill.
- Enforcement: agent
