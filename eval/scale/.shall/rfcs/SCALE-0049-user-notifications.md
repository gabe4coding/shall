---
id: SCALE-0049
title: Emails, push notifications and SMS
status: approved
domain: notifications
artifacts: [diff, code, spec]
languages: [any]
owner: crm
review_by: 2027-05-31
supersedes: []
summary: >
  Classification as transactional or marketing, opt-in and unsubscribe, quiet hours,
  frequency caps, deduplication and templates for messages sent to diners and
  restaurants.
applies_when: >
  The content sends, schedules, templates or configures an email, push notification or
  SMS, or describes a new notification or campaign.
not_applies_when: >
  No email, push notification or SMS is sent, scheduled, templated, configured or
  described (in-app UI text, internal alerts to engineers).
---

# SCALE-0049: Emails, push notifications and SMS

## Context

We send booking confirmations, reminders, review requests and marketing campaigns to
millions of diners and to restaurant staff. Duplicate reminders, pushes at night and
marketing sent without consent generate complaints, app uninstalls and regulatory risk.
These rules apply to every service that calls the notification platform.

## Requirements

### SCALE-0049.1 Declared message category
Every notification type MUST be declared in the notification catalog as `transactional`
(booking confirmation, reminder, cancellation, receipt) or `marketing` (promotions,
newsletters, recommendations).

- Applies when: the content adds a new notification type, campaign or template, or changes the category of one.
- Enforcement: agent

### SCALE-0049.2 Marketing opt-in checked at send time
Marketing emails, pushes and SMS MUST be sent only to users with an active opt-in for that
channel, checked at send time and not only when the audience is built.

- Applies when: the content sends a marketing message, builds a campaign audience or schedules a batch of marketing sends.
- Enforcement: agent

### SCALE-0049.3 One-click unsubscribe
Every marketing email MUST contain a one-click unsubscribe link and the
`List-Unsubscribe` and `List-Unsubscribe-Post` headers, and an unsubscribe MUST take
effect within 24 hours.

- Applies when: the content adds or changes a marketing email template, email headers or the unsubscribe handler.
- Enforcement: agent

### SCALE-0049.4 No promotions in transactional messages
Transactional messages SHOULD NOT contain promotional blocks such as offers or
restaurant suggestions; a message with promotions is treated as marketing.

- Applies when: the content adds content blocks, offers or recommendations to a booking confirmation, reminder, cancellation or receipt template.
- Enforcement: agent

### SCALE-0049.5 Quiet hours
Push notifications and SMS that are not time-critical MUST NOT be delivered between
21:00 and 08:00 in the recipient's local time zone; they are deferred to 08:00.

- Applies when: the content sends or schedules a push notification or SMS, or changes send-time scheduling.
- Enforcement: agent

### SCALE-0049.6 Deduplication key
Each send MUST carry a deduplication key built from the notification type and the
business event (for example `booking-reminder:{bookingId}`), and the sender MUST drop a
second send with the same key within 24 hours.

- Applies when: the content triggers a notification from an event consumer, a scheduled job, a retry or a webhook.
- Enforcement: agent

### SCALE-0049.7 Marketing frequency cap
Marketing push notifications SHOULD be capped at two per user per week across all
campaigns.

- Applies when: the content schedules marketing push campaigns or changes frequency capping rules.
- Enforcement: agent

### SCALE-0049.8 Versioned templates
Message content MUST be rendered from versioned, localised templates in the template
service; message bodies MUST NOT be built as inline strings in service code.

- Applies when: the content builds the subject, title or body of an email, push notification or SMS.
- Enforcement: agent

### SCALE-0049.9 Escaped template variables
Template variables that hold user or partner content (diner name, restaurant name,
review text, special requests) MUST be HTML-escaped in email templates.

- Applies when: an email template inserts a variable, or the content disables auto-escaping in a template.
- Enforcement: agent

### SCALE-0049.10 Single-segment SMS
SMS text SHOULD fit in one 160-character GSM-7 segment in every supported language.

- Applies when: the content adds or changes the text of an SMS template.
- Enforcement: agent

### SCALE-0049.11 Critical messages during quiet hours
Critical transactional messages, such as a booking cancelled by the restaurant less than
two hours before the booking time, MAY be delivered during quiet hours.

- Applies when: the content sends an urgent booking change, cancellation or no-show message by push notification or SMS.
- Enforcement: agent
