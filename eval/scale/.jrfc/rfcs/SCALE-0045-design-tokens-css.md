---
id: SCALE-0045
title: Design tokens and CSS conventions
status: enforced
domain: styling
artifacts: [diff, code]
languages: [css, typescript, javascript]
owner: design-system
review_by: 2027-06-30
supersedes: []
summary: >
  Colours, spacing, typography, breakpoints and z-index from design tokens; no
  `!important`; dark-mode-ready semantic tokens in CSS, SCSS and styled components.
applies_when: >
  The content adds or changes CSS, SCSS, CSS modules, styled components, `sx`/`style`
  props or theme files that set colours, spacing, fonts, media queries or z-index.
not_applies_when: >
  No styles or style values are added or changed (component logic without styling,
  backend code, mobile apps).
---

# SCALE-0045: Design tokens and CSS conventions

## Context

The web products share one design language through design tokens published by the
design-system package. Raw values in component styles break theming, dark mode and
brand updates, and each one has to be found by hand later. These rules apply to CSS,
SCSS, CSS modules and CSS-in-JS.

## Requirements

### SCALE-0045.1 Colours from tokens
Colours in component styles MUST come from design tokens (`var(--color-text-primary)`,
`theme.colors.primary`); raw hex, `rgb()`, `hsl()` or named colours MUST NOT be used.

- Applies when: CSS, SCSS or CSS-in-JS sets `color`, `background`, `border-color`, `fill`, `stroke` or `box-shadow` colour values.
- Enforcement: agent

### SCALE-0045.2 Spacing from the spacing scale
Margins, paddings and gaps SHOULD use spacing tokens (`var(--space-4)`, `theme.space[2]`)
instead of raw pixel or rem values.

- Applies when: CSS, SCSS or CSS-in-JS sets `margin`, `padding`, `gap`, `top`/`left` offsets or grid gaps.
- Enforcement: agent

### SCALE-0045.3 Typography from tokens
Font family, size, weight and line height MUST come from typography tokens or the
`text-style()` mixin; components MUST NOT declare their own `font-family`.

- Applies when: CSS, SCSS or CSS-in-JS sets `font-family`, `font-size`, `font-weight`, `line-height` or the `font` shorthand.
- Enforcement: agent

### SCALE-0045.4 No !important
Component styles MUST NOT use `!important`.

- Applies when: CSS, SCSS or CSS-in-JS contains `!important`.
- Enforcement: linter

### SCALE-0045.5 Shared breakpoints
Media queries MUST use the shared breakpoint mixins or tokens (`@include bp(md)`,
`theme.breakpoints.up('md')`); ad-hoc pixel widths such as `@media (max-width: 767px)`
MUST NOT be used.

- Applies when: the content adds or changes an `@media` query, a container query or a breakpoint helper call.
- Enforcement: agent

### SCALE-0045.6 Mobile-first media queries
Responsive styles SHOULD be written mobile-first: base styles for small screens and
`min-width` breakpoints for larger ones.

- Applies when: the content adds responsive styles or `max-width` media queries.
- Enforcement: agent

### SCALE-0045.7 Semantic tokens for dark mode
Components MUST use semantic tokens (`--color-surface`, `--color-text-muted`) that have a
dark theme value; primitive palette tokens (`--palette-grey-900`) MUST NOT be used
directly in components.

- Applies when: component styles reference a colour token or palette variable.
- Enforcement: agent

### SCALE-0045.8 Theme switching through the app shell
Components SHOULD NOT read `prefers-color-scheme` directly; dark mode is applied by the
`data-theme` attribute that the app shell sets on the root element.

- Applies when: the content adds a `prefers-color-scheme` media query, a `matchMedia` call for colour scheme, or theme-dependent styles in a component.
- Enforcement: agent

### SCALE-0045.9 Relative font sizes
Font sizes SHOULD be expressed in `rem` (usually through tokens) so that the user's
browser font setting applies; `px` font sizes SHOULD NOT be used.

- Applies when: CSS, SCSS or CSS-in-JS sets a `font-size`.
- Enforcement: agent

### SCALE-0045.10 z-index from the layer scale
`z-index` values MUST come from the layer tokens (`--z-dropdown`, `--z-modal`, `--z-toast`);
arbitrary values such as `z-index: 9999` MUST NOT be used.

- Applies when: CSS, SCSS or CSS-in-JS sets `z-index`.
- Enforcement: agent

### SCALE-0045.11 Local custom properties
A component MAY define its own CSS custom property for a value local to that component
(for example `--card-image-height`) when no design token exists for it, as long as the
value is not a colour.

- Applies when: the content declares a new CSS custom property (`--name: value`) inside a component stylesheet.
- Enforcement: agent
