---
id: SCALE-0044
title: Web performance budgets
status: approved
domain: frontend
artifacts: [diff, code]
languages: [typescript, javascript, html]
owner: frontend
review_by: 2027-03-31
supersedes: []
summary: >
  Bundle size budgets, tree-shakable imports, code splitting, image loading, third-party
  scripts and main-thread work, measured by Core Web Vitals (LCP, CLS, INP).
applies_when: >
  The content adds or changes imports or dependencies of web client code, route or
  page components, `<img>` or `<script>` tags, or code that runs in the browser on user
  interaction.
not_applies_when: >
  No browser-side code, page markup or client dependency is added or changed (backend
  services, mobile apps, infrastructure).
---

# SCALE-0044: Web performance budgets

## Context

Search traffic and conversion on the booking site depend on Core Web Vitals, and most
of our visitors are on mid-range phones. Regressions usually come from one heavy
dependency, an unsized hero image, or a new tag in the page head. These rules set the
budgets that keep LCP under 2.5 s, CLS under 0.1 and INP under 200 ms at p75.

## Requirements

### SCALE-0044.1 Route bundle budget
The gzipped initial JavaScript of each route MUST stay within the budget declared in
`bundle-budgets.json` (170 KB by default); the CI size check fails the build when it is
exceeded.

- Applies when: the content adds imports to client code, adds a client dependency, or changes the bundler configuration.
- Enforcement: linter

### SCALE-0044.2 Heavy dependencies loaded on demand
A new client dependency larger than 30 KB gzipped SHOULD NOT be part of the initial
bundle; it SHOULD be loaded with a dynamic `import()` at the point of use.

- Applies when: the content imports a new npm package in browser code or adds a dependency to the web app's `package.json`.
- Enforcement: agent

### SCALE-0044.3 Tree-shakable imports
Libraries MUST be imported by named ESM import or by module path
(`import { format } from 'date-fns'`, `import debounce from 'lodash/debounce'`); whole
packages (`import _ from 'lodash'`, `import * as icons from '...'`) MUST NOT be imported.

- Applies when: the content adds an `import` or `require` of a third-party library in browser code.
- Enforcement: agent

### SCALE-0044.4 Code-split routes and heavy widgets
Route-level pages and below-the-fold widgets (map, photo gallery, reviews carousel)
SHOULD be code-split with `React.lazy` or dynamic `import()`.

- Applies when: the content adds a route, a page component or a large widget such as a map, gallery or carousel.
- Enforcement: agent

### SCALE-0044.5 Sized images
Every `<img>` MUST declare `width` and `height` attributes or sit in a box with a fixed
`aspect-ratio`, so the layout does not shift when the image loads.

- Applies when: markup or JSX adds an `<img>`, `<picture>` or image component.
- Enforcement: agent

### SCALE-0044.6 Lazy loading below the fold
Images and iframes below the fold SHOULD use `loading="lazy"`.

- Applies when: markup or JSX adds an `<img>` or `<iframe>` in a list, gallery, footer or other content below the first screen.
- Enforcement: agent

### SCALE-0044.7 Hero image loads eagerly
The largest above-the-fold image of a page (the LCP element, such as the restaurant hero
photo) MUST NOT use `loading="lazy"` and MUST NOT be injected by client-side JavaScript
after hydration.

- Applies when: the content adds or changes the hero, header or first image of a page.
- Enforcement: agent

### SCALE-0044.8 Images through the image CDN
Restaurant and dish photos MUST be served through the image CDN with `srcset` and
`sizes` and in AVIF or WebP; the original upload URL MUST NOT be used in an `<img>`.

- Applies when: the content renders a restaurant, dish, user or partner photo on a web page.
- Enforcement: agent

### SCALE-0044.9 Short main-thread tasks
Event-handler work longer than about 50 ms (sorting thousands of slots, parsing large
JSON, filtering big lists) SHOULD be chunked, deferred with `requestIdleCallback` or
`scheduler.yield()`, or moved to a Web Worker.

- Applies when: an event handler, input handler or effect loops over large arrays, parses large payloads or does heavy computation in the browser.
- Enforcement: agent

### SCALE-0044.10 Non-blocking third-party scripts
Third-party scripts (tag managers, chat widgets, ads, A/B testing) MUST be loaded with
`async` or `defer`, or after user interaction; they MUST NOT be render-blocking
`<script>` tags in `<head>`.

- Applies when: the content adds a `<script>` tag, a script loader call or a third-party snippet to a page.
- Enforcement: agent

### SCALE-0044.11 Resource hints
A page MAY add `<link rel="preconnect">` or `<link rel="preload">` for the image CDN and
the API origin that it uses above the fold.

- Applies when: the content changes the document `<head>` or adds `<link rel>` hints.
- Enforcement: agent
