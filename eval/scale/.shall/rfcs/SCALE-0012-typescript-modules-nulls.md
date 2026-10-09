---
id: SCALE-0012
title: TypeScript module boundaries, null handling and immutability
status: approved
domain: typescript
artifacts: [diff, code]
languages: [typescript, tsx]
owner: frontend
review_by: 2027-04-30
supersedes: []
summary: >
  Imports across package boundaries, handling of null and undefined, enums and readonly
  data in TypeScript code.
applies_when: >
  The content is or changes TypeScript source code (.ts or .tsx files) that imports
  modules, handles nullable values, declares enums or unions, or defines data types.
not_applies_when: >
  The content is not TypeScript source code.
---

# SCALE-0012: TypeScript module boundaries, null handling and immutability

## Context

The web monorepo holds the diner site, the restaurant manager and a dozen shared
packages. Deep imports and unchecked nullable values are the main sources of broken builds
and runtime `undefined` errors. These rules complement the strict-mode baseline.

## Requirements

### SCALE-0012.1 Imports through package entry points
Code MUST import other workspace packages through their public entry point
(`@tf/booking-core`), never through deep paths such as `@tf/booking-core/src/internal`.

- Applies when: the content adds an import from another workspace package or from a path containing `/src/` or `/internal/` of another package.
- Enforcement: linter

### SCALE-0012.2 No cycles between modules
A change MUST NOT introduce an import cycle between files or packages.

- Applies when: the content adds import statements between modules of the same package or between packages.
- Enforcement: agent

### SCALE-0012.3 No non-null assertions
Code MUST NOT use the non-null assertion operator `!` on values that can be null or
undefined; it has to narrow the value with a check instead.

- Applies when: the content uses a postfix `!` on an expression, such as `user!.id` or `map.get(key)!`.
- Enforcement: agent

### SCALE-0012.4 Nullish operators
Defaults for nullable values SHOULD use `??` rather than `||`, so that `0`, `false` and
empty strings are kept.

- Applies when: the content uses `||` to provide a default for a value that is a number, boolean or string.
- Enforcement: agent

### SCALE-0012.5 Unions instead of enums
New code SHOULD use string literal union types or `as const` objects instead of TypeScript
`enum` declarations.

- Applies when: the content declares an `enum` or `const enum`.
- Enforcement: agent

### SCALE-0012.6 Exhaustive switches
A `switch` on a union or discriminant MUST end with a `default` branch that assigns the
value to `never`, so a new member causes a compile error.

- Applies when: the content writes a `switch` or if/else chain over a union type, discriminated union or status field.
- Enforcement: agent

### SCALE-0012.7 Readonly data
Types for API responses, props and store state SHOULD be declared `readonly` or
`Readonly<>`, and code SHOULD NOT mutate function arguments.

- Applies when: the content declares types for API payloads, component props or state, or modifies an object or array passed as an argument.
- Enforcement: agent

### SCALE-0012.8 Runtime validation of external data
Data parsed from `fetch`, `localStorage`, `postMessage` or URL parameters MUST be
validated with a schema (zod) before being used as a typed value, not cast with `as`.

- Applies when: the content casts the result of `response.json()`, `JSON.parse`, `localStorage.getItem` or URL search params with `as` or assigns it to a typed variable.
- Enforcement: agent

### SCALE-0012.9 Type-only imports
Imports used only as types MUST use `import type`.

- Applies when: the content imports an interface or type alias that is used only in type positions.
- Enforcement: agent

### SCALE-0012.10 Barrel files
A package MAY expose a single `index.ts` barrel file at its root as its public entry
point.

- Applies when: the content adds or changes an `index.ts` file that only re-exports other modules.
- Enforcement: agent
