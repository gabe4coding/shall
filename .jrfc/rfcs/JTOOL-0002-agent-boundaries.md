---
id: JTOOL-0002
title: Agent boundaries
status: enforced
domain: model-calls
artifacts: [diff, code, spec]
languages: [any]
owner: ai-governance
review_by: 2027-03-31
supersedes: []
summary: >
  What an LLM agent may do in the jrfc pipeline: gather and propose. Deterministic code
  validates, decides severity, and performs every write to an external system.
applies_when: >
  The content runs an LLM agent (for example `claude -p`), uses its output, or writes to
  an external system such as GitHub.
not_applies_when: >
  No agent runs, no agent output is used, and nothing is written to an external system.
---

# JTOOL-0002: Agent boundaries

## Requirements

### JTOOL-0002.1 Agents run without tools in the pipeline
The review agent invoked by the pipeline MUST run with no tools (`--tools ""`), so that it
can only return text.

- Applies when: the content builds the command line that runs `claude` or another agent.
- Enforcement: agent

### JTOOL-0002.2 Agent output is validated before use
Findings returned by an agent MUST pass `validate_findings` (statement selected for the
chunk, line or quote present in the artifact) before they reach a report or a comment.

- Applies when: the content reads, transforms or publishes findings produced by an agent.
- Enforcement: agent

### JTOOL-0002.3 Severity comes from the corpus
Whether a finding is blocking MUST be computed from the corpus (RFC status and statement
level) and MUST NOT be taken from agent output.

- Applies when: the content sets or reads the blocking flag or severity of a finding.
- Enforcement: agent

### JTOOL-0002.4 External writes are deterministic and previewable
Writes to external systems (GitHub reviews, comments, thread resolution) MUST be performed
by deterministic code, never by an agent, and the command that performs them MUST offer a
`--dry-run` that performs no write.

- Applies when: the content posts, patches or resolves anything on GitHub or another external system.
- Enforcement: agent
