---
id: SCALE-0043
title: React components and hooks
status: enforced
domain: frontend
artifacts: [diff, code]
languages: [typescript, javascript]
owner: frontend
review_by: 2027-03-31
supersedes: []
summary: >
  Effect cleanup, request cancellation, list keys, dependency arrays, immutable state
  and component structure for React code in the web apps.
applies_when: >
  The content adds or changes a React function component, a custom hook, a `useEffect`,
  `useState` or other hook call, or JSX that renders lists.
not_applies_when: >
  No React component or hook is added or changed (backend TypeScript, build scripts,
  plain utility modules, styles).
---

# SCALE-0043: React components and hooks

## Context

Our web booking funnel and the restaurant back office are React applications. The
bugs that reach production most often are memory leaks from effects that never clean
up, stale responses overwriting fresh state, and lists that lose their state when
reordered. These rules target those defects.

## Requirements

### SCALE-0043.1 Effect cleanup
A `useEffect` that subscribes to a store, starts a timer or interval, adds an event
listener or opens a socket MUST return a cleanup function that undoes it.

- Applies when: a `useEffect` or `useLayoutEffect` calls `setInterval`, `setTimeout`, `addEventListener`, `subscribe`, `new WebSocket` or `new EventSource`.
- Enforcement: agent

### SCALE-0043.2 Cancel or ignore stale requests
A `useEffect` that starts a fetch MUST abort it (`AbortController`) or ignore its result
when the component unmounts or the dependencies change, so a stale response never
overwrites newer state.

- Applies when: a `useEffect` calls `fetch`, `axios` or an API client and then sets state with the result.
- Enforcement: agent

### SCALE-0043.3 Stable list keys
Elements rendered from `.map()` MUST have a `key` taken from a stable id in the data (for
example `restaurant.id`); the array index MUST NOT be used as the key of a list that can
be reordered, filtered or inserted into.

- Applies when: JSX renders a list with `.map()` or sets a `key` prop.
- Enforcement: agent

### SCALE-0043.4 Complete dependency arrays
Hook dependency arrays MUST list every prop, state value and function from component
scope that the hook reads, and the `react-hooks/exhaustive-deps` rule MUST NOT be
disabled with an eslint comment.

- Applies when: the content adds or changes the dependency array of `useEffect`, `useMemo`, `useCallback` or `useLayoutEffect`, or an `eslint-disable` comment for `react-hooks`.
- Enforcement: linter

### SCALE-0043.5 Derived values are computed, not synced
Values that can be computed from props or other state SHOULD be computed during render
(with `useMemo` when expensive) instead of being copied into `useState` and synced by an
effect.

- Applies when: a `useEffect` only calls a state setter with a value computed from props or other state.
- Enforcement: agent

### SCALE-0043.6 No mutation of state
State objects and arrays MUST NOT be mutated in place (`items.push(x)`, `booking.status = 'x'`
followed by a setter call); every update MUST produce a new object or array.

- Applies when: the content calls a `useState` setter or a reducer, or changes an object or array held in state, props or context.
- Enforcement: agent

### SCALE-0043.7 Hooks at the top level
Hooks MUST be called only at the top level of a function component or a custom hook,
never inside conditions, loops, early returns or nested callbacks.

- Applies when: the content calls a function whose name starts with `use` inside a component or custom hook.
- Enforcement: agent

### SCALE-0043.8 Shared data-fetching layer
Data from our APIs SHOULD be read through the shared TanStack Query hooks in
`src/api/queries` rather than through hand-written `useEffect` and `useState` pairs.

- Applies when: a component or hook fetches data from a backend API.
- Enforcement: agent

### SCALE-0043.9 Error boundary per route
Each route-level page SHOULD be wrapped in an error boundary that renders a fallback UI,
so that a render error in one widget does not blank the whole page.

- Applies when: the content adds a route, a page component or changes the router configuration.
- Enforcement: agent

### SCALE-0043.10 Component size
A component file SHOULD NOT exceed 300 lines; a larger component SHOULD be split into
smaller components or custom hooks.

- Applies when: the content adds a React component or grows an existing one.
- Enforcement: agent

### SCALE-0043.11 Memoisation is not a default
`useMemo` and `useCallback` MAY be omitted for cheap computations and for callbacks that
are not passed to memoised children or used as hook dependencies.

- Applies when: the content adds, removes or discusses `useMemo`, `useCallback` or `React.memo`.
- Enforcement: agent
