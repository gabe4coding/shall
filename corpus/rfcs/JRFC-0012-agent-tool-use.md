---
id: JRFC-0012
title: Agent tool use
status: draft
domain: agents
artifacts: [tool]
languages: [any]
owner: ai-governance
review_by: 2027-03-31
supersedes: []
summary: >
  Limits on the shell commands and tool calls a coding agent runs in a repository:
  git history and branches, checks, credentials, remote scripts and production systems.
applies_when: >
  The content is a tool call made by a coding agent: a shell command, a file write or an MCP call.
not_applies_when: >
  The content is not a tool call made by an agent.
---

# JRFC-0012: Agent tool use

## Context

Coding agents run shell commands and call tools on behalf of an engineer, often many per
minute and without a human reading each one. The `jrfc` hooks (`jrfc hookd`, `jrfc hook`)
check each tool call against the statements below before it runs. `Tools:` limits a
statement to some tools (a regular expression on the tool name); `Violated when:` describes
a violating call for the Jev judgment. The action depends on the RFC status and the
statement level: see "Hooks" in the README.

## Requirements

### JRFC-0012.1 No direct push to the main branch
Agents MUST NOT push commits directly to the `main` or `master` branch of a remote; changes
reach it through a pull request.

- Applies when: the tool call runs `git push` or another command that updates a remote branch.
- Violated when: the command pushes to main or master: it names main or master as the target, or it runs a plain `git push` while the current branch is main or master.
- Tools: Bash
- Enforcement: agent

### JRFC-0012.2 No force push
Agents MUST NOT force-push (`--force`, `-f`, `--force-with-lease`, a `+` refspec) to any
remote branch.

- Applies when: the tool call runs `git push`.
- Violated when: the command force-pushes with --force, -f, --force-with-lease or a refspec that starts with +.
- Tools: Bash
- Enforcement: agent

### JRFC-0012.3 Checks are not skipped
Agents MUST NOT skip git hooks or checks, for example with `--no-verify`, `-n` on commit,
`HUSKY=0` or by disabling a required CI job.

- Applies when: the tool call commits, pushes or changes git hooks or CI configuration.
- Violated when: the command skips or disables git hooks or checks, for example git commit --no-verify, git push --no-verify, HUSKY=0 or SKIP= environment variables.
- Tools: Bash
- Enforcement: agent

### JRFC-0012.4 No credential literals in tool calls
Tool calls MUST NOT contain a real credential (password, token, API key, private key) as a
literal; they reference it through an environment variable or the secret manager.

- Applies when: the tool call input contains a string that is or looks like a credential.
- Tools: .*
- Enforcement: linter

### JRFC-0012.5 No remote scripts piped into a shell
Agents SHOULD NOT download a script and run it in the same command (`curl … | sh`,
`wget -O- … | bash`, `iex (iwr …)`).

- Applies when: the tool call downloads content from the network.
- Violated when: the command downloads a script and pipes it into sh, bash, zsh, python or another interpreter, or evaluates downloaded content.
- Tools: Bash
- Enforcement: agent

### JRFC-0012.6 No destructive commands outside the workspace
Agents MUST NOT delete, overwrite or change the permissions of files outside the working
directory of the session, except in temporary directories.

- Applies when: the tool call deletes, moves, overwrites or changes permissions of files.
- Violated when: the command deletes, overwrites or changes permissions of paths outside the working directory (`cwd`), such as the home directory, / or system folders; paths under /tmp or the working directory are allowed.
- Tools: Bash
- Enforcement: agent

### JRFC-0012.7 No writes to production systems
Agents MUST NOT change data or schema in a production database, queue or cloud resource
(migrations, write queries, deletes, deploys to production).

- Applies when: the tool call connects to a database, cloud account, cluster or deployment tool.
- Violated when: the tool call writes, deletes or migrates data or schema, or deploys, on a system whose name, host, profile, context or environment says production or prod.
- Tools: Bash|mcp__.*
- Enforcement: agent

### JRFC-0012.8 TLS verification stays on
Agents SHOULD NOT disable TLS certificate verification in commands (`curl -k`,
`--insecure`, `GIT_SSL_NO_VERIFY`, `verify=False`).

- Applies when: the tool call makes a network request.
- Violated when: the command disables TLS certificate verification, for example curl -k or --insecure, wget --no-check-certificate, GIT_SSL_NO_VERIFY=1 or NODE_TLS_REJECT_UNAUTHORIZED=0.
- Tools: Bash
- Enforcement: agent
