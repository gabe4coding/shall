---
id: SCALE-0040
title: Web accessibility
status: enforced
domain: accessibility
artifacts: [diff, code, spec]
languages: [any]
owner: frontend
review_by: 2027-04-30
supersedes: []
summary: >
  Semantic HTML, labels, alternative text, keyboard access, focus handling, colour
  contrast and ARIA for the web booking site and the restaurant back office.
applies_when: >
  The content adds or changes web markup, JSX/TSX components, CSS that affects focus or
  colour, forms, images, dialogs or keyboard handlers, or describes a new web user flow.
not_applies_when: >
  No web user interface is added, changed or described (backend code, native mobile
  screens, infrastructure).
---

# SCALE-0040: Web accessibility

## Context

Diners book tables with screen readers, keyboard only, and zoomed screens, and the
European Accessibility Act makes WCAG 2.2 AA a legal floor for our web products. Most
defects we find in audits come from a small set of repeated mistakes in markup and
focus handling. These rules target those mistakes directly.

## Requirements

### SCALE-0040.1 Native elements for controls
Clickable controls MUST use a native `<button>` or `<a href>` element; a `div` or `span`
with a click handler MUST NOT be used as a button or link.

- Applies when: markup or JSX adds an element with `onClick`, `@click` or a `click` event listener, or a custom button or link component.
- Enforcement: agent

### SCALE-0040.2 Labelled form fields
Every `<input>`, `<select>` and `<textarea>` MUST have an accessible name from a `<label for>`,
a wrapping `<label>` or `aria-labelledby`; placeholder text alone MUST NOT act as the label.

- Applies when: markup or JSX adds or changes a form field element or a text input component.
- Enforcement: agent

### SCALE-0040.3 Alt attribute on images
Every `<img>` element MUST have an `alt` attribute; purely decorative images MUST use `alt=""`.

- Applies when: markup or JSX adds an `<img>` element or an image component that renders one.
- Enforcement: linter

### SCALE-0040.4 Meaningful alternative text
Alternative text for an informative image SHOULD describe its content or function (for
example "Terrace of Le Petit Bistro") and SHOULD NOT repeat the file name or start with
"image of".

- Applies when: the content sets a non-empty `alt` value or an `aria-label` on an image or icon.
- Enforcement: agent

### SCALE-0040.5 Keyboard operable widgets
Every interactive element MUST be reachable and operable with the keyboard alone (Tab,
Enter, Space, Escape, arrow keys for composite widgets), and `tabindex` values greater
than 0 MUST NOT be used.

- Applies when: the content adds a custom interactive widget (dropdown, date picker, carousel, slot selector), a `keydown` handler or a `tabindex` attribute.
- Enforcement: agent

### SCALE-0040.6 Visible focus indicator
Focus MUST stay visible: a rule that removes the outline on `:focus` or `:focus-visible`
(`outline: none`, `outline: 0`) MUST replace it with another visible focus style.

- Applies when: CSS, SCSS or a styled component sets `outline`, `box-shadow` or `border` on `:focus` or `:focus-visible`, or removes the outline of an element.
- Enforcement: agent

### SCALE-0040.7 Focus management in dialogs
A modal dialog MUST move focus into itself when it opens, keep Tab inside it while open,
close on Escape, and return focus to the element that opened it when it closes.

- Applies when: the content adds or changes a modal, dialog, drawer, bottom sheet or overlay component on the web.
- Enforcement: agent

### SCALE-0040.8 Text colour contrast
Text MUST meet WCAG 2.2 AA contrast against its background: 4.5:1 for normal text and
3:1 for text of at least 24px or bold text of at least 18.66px.

- Applies when: the content sets a text colour, a background colour behind text, or opacity on text.
- Enforcement: agent

### SCALE-0040.9 Colour is not the only signal
State such as an unavailable time slot, a form error or a selected filter SHOULD NOT be
conveyed by colour alone; an icon, text or pattern SHOULD accompany the colour.

- Applies when: the content shows status, validation errors, availability or selection by changing a colour.
- Enforcement: agent

### SCALE-0040.10 ARIA only when native semantics are missing
ARIA roles and attributes SHOULD be added only when no native HTML element provides the
semantics, and an element with `aria-hidden="true"` SHOULD NOT contain focusable elements.

- Applies when: markup or JSX adds a `role` attribute, an `aria-*` attribute or `aria-hidden`.
- Enforcement: agent

### SCALE-0040.11 Live announcements for async updates
Asynchronous status changes (booking confirmed, slot no longer available) MAY be announced
through an `aria-live="polite"` region instead of moving focus to the message.

- Applies when: the content shows a toast, inline status or error message after an asynchronous request completes.
- Enforcement: agent
