# RFC file format and wording

## Template

```markdown
---
id: JRFC-0012                 # JRFC-NNNN, also the start of the file name
title: HTTP caching
status: draft                 # draft | approved | enforced | deprecated
domain: api                   # a key of domains.yaml
artifacts: [diff, code]       # which artifacts it can apply to: diff, code, spec, doc
languages: [any]              # or e.g. [typescript]: a deterministic prefilter
owner: platform
review_by: 2027-06-30
supersedes: []
summary: >
  One or two sentences: what the standard covers.
applies_when: >
  The concrete code or text it governs, written literally.
not_applies_when: >
  What looks close but is out of scope.
---

# JRFC-0012: HTTP caching

## Context
Why it exists. Links to incidents, ADRs, external references.

## Requirements

### JRFC-0012.1 Cache-Control on GET responses
GET handlers MUST set a `Cache-Control` header on successful responses.

- Applies when: the content adds or changes a GET handler that returns a response.
- Not applies when: the handler streams server-sent events.
- Artifacts: diff, code          # optional, narrower than the RFC's artifacts
- Enforcement: agent             # agent | linter | human
```

Tool rules (checked by the hooks) also use `Tools:` (regex, full match on the tool name),
`Violated when:` (the Jev criterion) and, for `Enforcement: linter`, `Pattern:` (regex on the
command, quoted strings masked). See JRFC-0012 for examples.

## Wording that works

Jev reads literally: it answers the words written, not the intent.

- **One requirement, one level.** Exactly one level of UPPERCASE keywords per statement:
  MUST/MUST NOT/SHALL/REQUIRED, or SHOULD/SHOULD NOT/RECOMMENDED, or MAY/OPTIONAL. Two levels → two
  statements. Lowercase "must" is not normative (RFC 8174); keywords in backticks are mentions.
- **Self-contained.** The reviewer sees the statement alone. No "as above", no "this service": name the thing.
- **`Applies when:` names things a reader can point at** in a diff or doc ("a log call includes
  fields of a user", not "privacy-sensitive situations"). It is the Jev criterion: vague text means
  missed or noisy reviews.
- **`Artifacts: spec`** for statements that only make sense for a design document. Without it, the
  statement is also asked about code diffs.
- **`Enforcement: linter`** when a linter checks it exactly (config flags, syntax, formatting).
  Models never see it; point to the lint rule in the text (JRFC-0001.5).
- **Observable over intention**: "MUST set a timeout" is checkable, "MUST be resilient" is not.
