---
id: SCALE-0061
title: End-to-end and contract tests
status: approved
domain: testing
artifacts: [diff, code, spec]
languages: [any]
owner: sdet
review_by: 2027-05-31
supersedes: []
summary: >
  How end-to-end tests of user journeys and consumer-driven contract tests between
  services are written, run and kept reliable.
applies_when: >
  The content adds or changes end-to-end tests (Playwright, Cypress, Espresso, XCUITest),
  contract tests (Pact or schema checks), or an API or event that other services consume.
not_applies_when: >
  No end-to-end test, contract test or cross-service interface is added, changed or
  described.
---

# SCALE-0061: End-to-end and contract tests

## Context

End-to-end tests are slow and fragile, so we keep them for the few journeys that make
money: search, booking, payment and cancellation. Correctness between services is
checked with contract tests, which fail on the provider's pull request instead of in
staging after both sides have shipped.

## Requirements

### SCALE-0061.1 Critical journeys covered
Each critical user journey (search, booking, payment, cancellation, restaurant sign-in)
MUST have at least one end-to-end test that runs against staging before every production
deploy of the services it touches.

- Applies when: the content adds or changes a user flow for search, booking, payment, cancellation or restaurant sign-in, or removes an end-to-end test of one.
- Enforcement: agent

### SCALE-0061.2 Stable selectors
End-to-end tests MUST locate elements by test id or accessible role and name, and MUST
NOT use CSS class names, XPath positions or visible copy that is translated.

- Applies when: an end-to-end test uses a locator such as `page.locator`, `cy.get`, `onView`, `XCUIElement` query or `find_element`.
- Enforcement: agent

### SCALE-0061.3 Explicit waits in UI tests
End-to-end tests MUST wait for a visible state (element shown, network response,
navigation) and MUST NOT use fixed pauses such as `waitForTimeout` or `cy.wait(<number>)`.

- Applies when: an end-to-end test calls `waitForTimeout`, `cy.wait` with a number, `Thread.sleep` or `sleep`.
- Enforcement: linter

### SCALE-0061.4 Isolated test accounts
End-to-end tests MUST create or lease their own diner and restaurant test accounts per
run, and MUST NOT share a single account across parallel runs.

- Applies when: an end-to-end test signs in, books a table, or uses a hard-coded test user, restaurant id or account email.
- Enforcement: agent

### SCALE-0061.5 No real payment or messages
End-to-end tests MUST use the payment provider's sandbox and a sink for emails, SMS and
push notifications, so that no real charge or message reaches a real person.

- Applies when: an end-to-end test goes through payment, prepayment, deposit or notification sending steps.
- Enforcement: agent

### SCALE-0061.6 Consumer contract for new integrations
A service that starts consuming another internal service's HTTP API or Kafka event MUST
publish a consumer contract (Pact or a schema compatibility test) that the provider's CI
verifies.

- Applies when: the content adds a client for an internal HTTP API, or a consumer of an internal Kafka topic, owned by another team.
- Enforcement: agent

### SCALE-0061.7 Provider verification before merge
A provider MUST run verification of all published consumer contracts in its pull request
pipeline, and a failing verification MUST block the merge.

- Applies when: the content changes a CI workflow of a service that exposes an HTTP API or produces Kafka events consumed by other services, or disables contract verification.
- Enforcement: agent

### SCALE-0061.8 Contracts assert only what is used
A consumer contract SHOULD cover only the fields and status codes that the consumer
actually reads, so that providers can add fields freely.

- Applies when: the content adds or changes a Pact interaction, contract file or schema test with expected response bodies.
- Enforcement: agent

### SCALE-0061.9 Test plan in designs
A design that adds or changes a cross-service flow SHOULD list which end-to-end and
contract tests will cover it and which team owns each.

- Applies when: the content is a design spec that adds a new call or event between services or a new user journey.
- Artifacts: spec
- Enforcement: agent

### SCALE-0061.10 Retries of end-to-end tests
A CI job MAY retry a failed end-to-end test once, provided the retry is reported as a
flaky result in the test dashboard and does not hide the first failure.

- Applies when: the content configures `retries`, `rerun`, `flaky` or retry options for an end-to-end test runner.
- Enforcement: agent
