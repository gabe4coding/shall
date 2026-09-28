---
id: JRFC-0007
title: TypeScript code
status: enforced
domain: typescript
artifacts: [diff, code]
languages: [typescript]
owner: frontend
review_by: 2027-03-31
supersedes: []
summary: >
  Type-safety and async conventions for TypeScript services and frontends.
applies_when: >
  The content is or changes TypeScript source code (.ts or .tsx).
not_applies_when: >
  The content is not TypeScript source code.
---

# JRFC-0007: TypeScript code

## Requirements

### JRFC-0007.1 Strict compiler mode
Projects MUST compile with `"strict": true` in `tsconfig.json`.

- Applies when: the content adds or changes a tsconfig file.
- Enforcement: linter

### JRFC-0007.2 No `any` in exported signatures
Exported functions, classes and types MUST NOT use `any` in their public signatures; use
`unknown` or a precise type instead.

- Applies when: the content adds or changes an exported function, class, interface or type.
- Enforcement: agent

### JRFC-0007.3 No floating promises
A promise MUST be awaited, returned, or explicitly handled with `.catch`; it MUST NOT be
created and silently dropped.

- Applies when: the content calls an async function or creates a promise.
- Enforcement: agent

### JRFC-0007.4 Narrow caught errors
Code in a `catch` block SHOULD treat the error as `unknown` and narrow it (for example
with `instanceof`) before reading its properties.

- Applies when: the content adds or changes a try/catch block or a `.catch` handler.
- Enforcement: agent
