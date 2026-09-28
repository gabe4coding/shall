---
id: SCALE-0046
title: Use of design system components
status: draft
domain: styling
artifacts: [diff, code, spec]
languages: [any]
owner: design-system
review_by: 2027-06-30
supersedes: []
summary: >
  Product code builds UI from the shared design system components and icons on web,
  Android and iOS instead of custom look-alikes, without deep imports or style overrides.
applies_when: >
  The content adds or changes UI components, buttons, inputs, modals, icons, imports of
  the design system packages, or describes a new UI pattern.
not_applies_when: >
  No user interface component, icon or design system dependency is added, changed or
  described.
---

# SCALE-0046: Use of design system components

## Context

Teams keep rebuilding buttons, modals and date pickers that already exist in the design
system, each with its own accessibility gaps and visual drift. This proposal makes the
design system the default building block on every platform and defines the escape
hatch for missing components.

## Requirements

### SCALE-0046.1 Design system component first
UI MUST use the design system component (`Button`, `TextField`, `Modal`, `DatePicker`,
`Toast`, `Tabs`) when one exists for the need; a custom re-implementation of the same
control MUST NOT be added.

- Applies when: the content adds a component that renders a button, text input, select, modal, date picker, toast, tabs, chip or similar UI primitive.
- Enforcement: agent

### SCALE-0046.2 Variants instead of overrides
Design system components SHOULD be customised through their `variant`, `size` and `tone`
props, not by overriding their internal styles with `className`, `style` or nested
selectors.

- Applies when: the content passes `className`, `style`, `sx` or a styled wrapper to a design system component.
- Enforcement: agent

### SCALE-0046.3 Public entry points only
Design system components MUST be imported from the package entry point
(`@thefork/design-system`); internal paths such as `@thefork/design-system/dist/...` or
`/src/...` MUST NOT be imported.

- Applies when: the content adds an import from a design system package.
- Enforcement: agent

### SCALE-0046.4 One major version per app
An application MUST depend on a single major version of the design system; two major
versions MUST NOT be bundled together.

- Applies when: the content changes the design system dependency in `package.json`, `build.gradle(.kts)` or `Package.swift`.
- Enforcement: agent

### SCALE-0046.5 Layout primitives over raw containers
Product components SHOULD be composed from the design system layout primitives (`Stack`,
`Box`, `Text`) rather than raw `div` or `span` elements with custom CSS.

- Applies when: the content adds a web component whose markup is mostly `div` and `span` elements with custom class names.
- Enforcement: agent

### SCALE-0046.6 Icons from the icon set
Icons MUST come from the design system icon set; inline SVG icons, icon fonts or
third-party icon packages MUST NOT be added to product code.

- Applies when: the content adds an icon, an inline `<svg>`, an icon font or an icon library dependency.
- Enforcement: agent

### SCALE-0046.7 Native design system libraries
The Android and iOS apps MUST use the Compose and SwiftUI design system libraries for
buttons, text fields, dialogs and bottom sheets instead of raw Material or UIKit
components.

- Applies when: Kotlin or Swift code adds a `Button`, `TextField`, `AlertDialog`, `ModalBottomSheet`, `UIButton` or `UIAlertController`.
- Enforcement: agent

### SCALE-0046.8 Requesting a missing component
When no design system component fits, the team SHOULD open a request in the design
system repository and place the local component under `src/ui/local/` with a comment
linking to that request.

- Applies when: the content adds a new generic UI component in a product repository.
- Enforcement: agent

### SCALE-0046.9 Components listed in UI specs
A design spec that introduces a new UI pattern SHOULD list the design system components
it uses and any new component it needs from the design system team.

- Applies when: the content is a design spec that describes new screens, flows or UI patterns.
- Artifacts: spec
- Enforcement: agent

### SCALE-0046.10 Experiments behind a flag
An experiment behind a feature flag MAY use local components for up to one quarter
before it is moved to design system components or removed.

- Applies when: the content adds UI for an A/B test or experiment behind a feature flag.
- Enforcement: agent
