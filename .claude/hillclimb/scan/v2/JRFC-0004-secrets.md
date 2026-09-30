---
id: JRFC-0004
title: Secrets management
status: enforced
domain: security
artifacts: [diff, code, spec]
languages: [any]
owner: security
review_by: 2027-01-31
supersedes: []
summary: >
  Where credentials, tokens and keys live and how code obtains and handles them.
applies_when: >
  The content uses, stores, passes or describes a password, API key, token, private key,
  connection string or other credential.
not_applies_when: >
  No credential of any kind is used, stored, passed or described.
---

# JRFC-0004: Secrets management

## Context

Leaked credentials are the most common root cause of cloud security incidents. Secrets in
source control stay in the git history forever, even after they are removed.

## Requirements

### JRFC-0004.1 No secrets in source
Source code, configuration files and tests MUST NOT contain real credentials (passwords,
API keys, tokens, private keys, connection strings with passwords).

- Applies when: the content contains a string literal, constant, config value or default that is or looks like a password, key, token or credential.
- Violated when: the content contains a literal value that is a real credential of a real account or system: a password, API key, token, private key, or a connection string with a password. Public demo logins published for a practice or test site, placeholders, example values, and passwords of throwaway keys or keystores that the code itself generates for a local test fixture are not real credentials.
- Enforcement: agent

### JRFC-0004.2 Secrets from the secret manager
Services MUST read credentials at runtime from the secret manager (directly or through
environment variables injected by the platform), never from files committed to the
repository.

- Applies when: the content loads, configures or passes a credential for a database, broker, third-party API or service.
- Enforcement: agent

### JRFC-0004.3 Secrets never in URLs or logs
Credentials MUST NOT be placed in URL query strings, log records, error messages or
exception text.

- Applies when: the content builds a URL, a log record or an error message in code that has access to a credential.
- Enforcement: agent

### JRFC-0004.4 Rotation
A design that introduces a new credential SHOULD describe how it is rotated and who owns
the rotation.

- Applies when: the content is a design that introduces a new credential, key or service account.
- Artifacts: spec
- Enforcement: agent
