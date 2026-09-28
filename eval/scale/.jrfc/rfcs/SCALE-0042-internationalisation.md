---
id: SCALE-0042
title: Internationalisation of user-facing text and formats
status: enforced
domain: i18n
artifacts: [diff, code, spec]
languages: [any]
owner: frontend
review_by: 2027-05-31
supersedes: []
summary: >
  Translatable strings, ICU plurals, locale-aware dates, numbers and prices, time zones
  and right-to-left layout for the web and mobile products.
applies_when: >
  The content adds or changes text shown to users, translation catalogs, or code that
  formats dates, times, numbers or prices for display, or lays out UI with left/right
  positioning.
not_applies_when: >
  No user-facing text, translation catalog or display formatting is added or changed
  (internal logs, backend-only data processing, infrastructure).
---

# SCALE-0042: Internationalisation of user-facing text and formats

## Context

We operate in more than ten countries and ship every product in at least eight
languages. Hard-coded strings, sentence concatenation and fixed date patterns are the
main source of untranslated or ungrammatical screens, and they are costly to fix after
release. These rules apply to web, Android, iOS and server-rendered templates.

## Requirements

### SCALE-0042.1 No hard-coded user-facing strings
Text shown to users MUST come from the translation catalog through the i18n API
(`t('booking.confirm.title')`, `stringResource(R.string.x)`, `String(localized:)`); string
literals MUST NOT be rendered directly as labels, titles, placeholders or error messages.

- Applies when: UI code (JSX/TSX, Compose, SwiftUI, UIKit, server-side templates) adds a literal text node, button label, title, placeholder, tooltip or error message.
- Enforcement: agent

### SCALE-0042.2 Whole sentences with named placeholders
A translated sentence MUST be one message with named placeholders
(`"Table for {guests} at {restaurantName}"`); sentences MUST NOT be built by concatenating
translated fragments or joining them with variables.

- Applies when: the content concatenates strings, uses template literals or `+` around translated text, or passes pieces of a sentence to several translation keys.
- Enforcement: agent

### SCALE-0042.3 Plural forms
Messages that contain a count MUST use ICU plural syntax
(`{count, plural, one {# guest} other {# guests}}`) or platform plurals (`<plurals>`
resources, `.stringsdict`, `^[]` inflection); a ternary on `count === 1` MUST NOT choose
between two strings.

- Applies when: the content displays a number of guests, bookings, reviews, points, days or any other count next to a noun.
- Enforcement: agent

### SCALE-0042.4 Locale-aware dates and times
Dates and times shown to users MUST be formatted with the active locale
(`Intl.DateTimeFormat`, `DateTimeFormatter.ofLocalizedDate`, `DateFormatter` with a
locale and a template); fixed patterns such as `DD/MM/YYYY`, `toISOString()` or
`toLocaleDateString()` without a locale MUST NOT be displayed.

- Applies when: the content formats a date, time, weekday or month name for display to a user.
- Enforcement: agent

### SCALE-0042.5 Restaurant time zone for booking times
Booking dates and times SHOULD be displayed in the restaurant's time zone, with the time
zone name shown when it differs from the time zone of the device.

- Applies when: the content displays or converts the date or time of a booking, a time slot or opening hours.
- Enforcement: agent

### SCALE-0042.6 Currency-aware price formatting
Prices MUST be formatted with a currency-aware formatter
(`Intl.NumberFormat(locale, { style: 'currency', currency })`,
`NumberFormat.getCurrencyInstance`, `.formatted(.currency(code:))`) using the currency
code from the data; a hard-coded symbol such as `'€' + amount` MUST NOT be used.

- Applies when: the content displays a price, a deposit, a discount amount, a bill total or loyalty value in money.
- Enforcement: agent

### SCALE-0042.7 Locale-aware numbers
Numbers shown to users, such as ratings, distances and percentages, SHOULD be formatted
with the locale's decimal and grouping separators rather than `toFixed()` or string
interpolation.

- Applies when: the content displays a decimal number, a rating, a distance, a percentage or a large integer to users.
- Enforcement: agent

### SCALE-0042.8 Logical properties for right-to-left layouts
Layout SHOULD use logical directions (`margin-inline-start`, `padding-inline-end`,
`inset-inline-start`, `text-align: start`, `start`/`end` in Compose and SwiftUI) instead
of left and right, so that Arabic and Hebrew layouts mirror correctly.

- Applies when: CSS or layout code sets left or right margins, padding, positions, floats, text alignment or `Gravity.LEFT`/`RIGHT`.
- Enforcement: agent

### SCALE-0042.9 Language and direction on the document
The root `<html>` element MUST set `lang` and `dir` from the active locale, and a page
that switches locale MUST update both.

- Applies when: the content changes the HTML document shell, the root layout component, or the code that switches the active locale.
- Enforcement: agent

### SCALE-0042.10 Keys exist in the source catalog
Every translation key referenced in code MUST exist in the English source catalog in
the same change.

- Applies when: the content adds or renames a call to the translation function or a string resource reference.
- Enforcement: linter

### SCALE-0042.11 Content that is not translated
Restaurant names, dish names, brand names and text entered by users MAY be rendered
directly without going through the translation catalog.

- Applies when: the content renders restaurant data, menu items, reviews or other user-generated or partner-provided text.
- Enforcement: agent
