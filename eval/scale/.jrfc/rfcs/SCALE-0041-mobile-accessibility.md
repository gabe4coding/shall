---
id: SCALE-0041
title: Mobile app accessibility
status: enforced
domain: accessibility
artifacts: [diff, code, spec]
languages: [any]
owner: mobile
review_by: 2027-04-30
supersedes: []
summary: >
  Screen reader labels, dynamic text size, touch target size and semantics for the
  Android and iOS apps (Compose, Android views, SwiftUI, UIKit).
applies_when: >
  The content adds or changes a screen, view, composable, layout XML, image, button or
  gesture in the Android or iOS app, or describes a new mobile screen.
not_applies_when: >
  No native mobile user interface is added, changed or described (web pages, backend
  code, build configuration).
---

# SCALE-0041: Mobile app accessibility

## Context

A growing share of bookings come from the apps, and TalkBack and VoiceOver users hit
the same defects over and over: unlabelled icon buttons, text that does not grow, and
targets too small to hit. These rules cover Jetpack Compose, Android views, SwiftUI and
UIKit.

## Requirements

### SCALE-0041.1 Labels on icon-only controls
An icon-only button or tappable image MUST have an accessible label: `contentDescription`
on Android, `accessibilityLabel` on iOS.

- Applies when: the content adds an `Icon`, `IconButton`, `ImageButton`, `Image`, `UIButton` or SwiftUI `Button` that has no visible text.
- Enforcement: agent

### SCALE-0041.2 Decorative images hidden
Decorative images MUST be hidden from screen readers: `contentDescription = null` in
Compose, `importantForAccessibility="no"` in Android XML, `.accessibilityHidden(true)` or
`isAccessibilityElement = false` on iOS.

- Applies when: the content adds a background image, divider, illustration or other image that carries no information.
- Enforcement: agent

### SCALE-0041.3 Scalable text units on Android
Android text sizes MUST be declared in `sp`; text sizes in `dp` or `px` MUST NOT be used.

- Applies when: Android layout XML, a style resource or Compose code sets `textSize`, `fontSize` or a text style size.
- Enforcement: linter

### SCALE-0041.4 Dynamic Type on iOS
iOS text MUST use Dynamic Type text styles (`.font(.body)`, `UIFont.preferredFont(forTextStyle:)`
or `UIFontMetrics` for custom fonts), and UIKit labels MUST set
`adjustsFontForContentSizeCategory = true`.

- Applies when: Swift code sets a font on a `Text`, `UILabel`, `UITextField` or `UIButton`, or creates a `UIFont` with a fixed size.
- Enforcement: agent

### SCALE-0041.5 Layout at the largest text size
Screens SHOULD remain usable at the largest accessibility text size (200% on Android,
AX5 on iOS): text SHOULD wrap instead of being truncated, and text containers SHOULD NOT
have fixed heights.

- Applies when: the content sets a fixed height, `maxLines`, `lineLimit` or truncation on a view that contains text.
- Enforcement: agent

### SCALE-0041.6 Minimum touch target size
Every interactive element MUST have a touch target of at least 48x48dp on Android and
44x44pt on iOS, extended with padding, `minimumInteractiveComponentSize()` or a larger
hit area when the visible icon is smaller.

- Applies when: the content adds or resizes a button, icon button, checkbox, chip, link or other tappable element in a mobile screen.
- Enforcement: agent

### SCALE-0041.7 Grouped content read as one item
Elements that form one item, such as a restaurant card with name, rating and price,
SHOULD be merged into one accessibility node (`Modifier.semantics(mergeDescendants = true)`,
`.accessibilityElement(children: .combine)`).

- Applies when: the content adds a card, list row or cell composed of several text and image elements.
- Enforcement: agent

### SCALE-0041.8 Alternatives to custom gestures
An action available only through swipe, long press or drag MUST also be available as a
visible control or as a custom accessibility action (`customActions`, `.accessibilityAction`).

- Applies when: the content adds a swipe-to-delete, long-press menu, drag gesture or other gesture handler in a mobile screen.
- Enforcement: agent

### SCALE-0041.9 Role and state of custom controls
Custom toggles, checkboxes, radio buttons and tabs MUST expose their role and their
checked or selected state (`Modifier.toggleable`, `semantics { role = Role.Switch }`,
`.accessibilityAddTraits(.isSelected)`).

- Applies when: the content builds a custom toggle, checkbox, radio button, segmented control or tab instead of using the platform component.
- Enforcement: agent

### SCALE-0041.10 Announcing state changes
A state change not tied to focus, such as "Booking confirmed" or "Slot no longer
available", SHOULD be announced with a live region on Android
(`semantics { liveRegion = LiveRegionMode.Polite }`) or
`UIAccessibility.post(notification: .announcement, argument:)` on iOS.

- Applies when: the content shows a snackbar, toast, banner or inline status after an asynchronous result in a mobile screen.
- Enforcement: agent

### SCALE-0041.11 Reduced motion
Non-essential animations MAY be replaced by a cross-fade or skipped when the system
reduce-motion setting is on (`UIAccessibility.isReduceMotionEnabled`, animator duration
scale of 0 on Android).

- Applies when: the content adds a transition, parallax, auto-playing or looping animation in a mobile screen.
- Enforcement: agent
