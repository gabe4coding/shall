---
id: SCALE-0003
title: User authentication and session handling
status: enforced
domain: security
artifacts: [diff, code, spec]
languages: [any]
owner: security
review_by: 2027-03-31
supersedes: []
summary: >
  Login, password, multi-factor and session cookie rules for diner, restaurant and
  back-office accounts.
applies_when: >
  The content implements or changes login, logout, password handling, password reset,
  multi-factor authentication, session creation, session cookies or refresh tokens.
not_applies_when: >
  No login, password, session, cookie or refresh token logic is added, changed or described.
---

# SCALE-0003: User authentication and session handling

## Context

Diners, restaurant staff and internal operators sign in to the web apps, the mobile apps
and the restaurant manager tool. Account takeover gives access to personal data and to
restaurant booking books. These rules fix the minimum session and login hygiene.

## Requirements

### SCALE-0003.1 Session cookie attributes
Session and refresh-token cookies MUST be set with `Secure`, `HttpOnly` and `SameSite=Lax`
or `SameSite=Strict`.

- Applies when: the content sets a cookie that holds a session id, access token or refresh token (`Set-Cookie`, `res.cookie`, `ResponseCookie`).
- Enforcement: linter

### SCALE-0003.2 Session rotation on login
The session identifier MUST be regenerated after a successful login and after a privilege
change such as switching to a restaurant admin role.

- Applies when: the content implements the success path of a login, a role switch or an impersonation start.
- Enforcement: agent

### SCALE-0003.3 Server-side logout
Logout MUST invalidate the session or refresh token on the server, not only delete the
cookie or local storage entry on the client.

- Applies when: the content implements a logout endpoint, a sign-out action or token revocation.
- Enforcement: agent

### SCALE-0003.4 Session lifetime
Diner sessions SHOULD expire after 30 days of inactivity and back-office sessions SHOULD
expire after 8 hours of inactivity.

- Applies when: the content configures session timeouts, refresh-token lifetimes or remember-me duration.
- Enforcement: agent

### SCALE-0003.5 Login throttling
Failed login attempts MUST be throttled per account and per source IP, with a growing delay
or a temporary lock after 10 failures in 15 minutes.

- Applies when: the content implements or changes a login, one-time-code verification or password check endpoint.
- Enforcement: agent

### SCALE-0003.6 Uniform login errors
Login and password reset responses MUST NOT reveal whether an email address has an account.

- Applies when: the content writes the error or success message of a login, sign-up or password reset flow.
- Enforcement: agent

### SCALE-0003.7 Password reset tokens
Password reset tokens MUST be single-use, random with at least 128 bits of entropy, and
expire within one hour.

- Applies when: the content generates, stores or checks a password reset or magic-link token.
- Enforcement: agent

### SCALE-0003.8 MFA for back-office
Back-office and restaurant admin accounts MUST sign in through the corporate SSO with
multi-factor authentication enforced.

- Applies when: the content adds a login path or authentication provider for an internal tool, admin console or back-office application.
- Enforcement: agent

### SCALE-0003.9 Re-authentication for sensitive changes
Changing an email address, password or payout bank details SHOULD require the user to
re-enter their password or a fresh one-time code.

- Applies when: the content implements an endpoint or screen that changes a user's email, password, phone number or payout details.
- Enforcement: agent

### SCALE-0003.10 Passkeys
Diner login MAY offer WebAuthn passkeys as an alternative to a password.

- Applies when: the content designs or implements a new diner login or sign-up method.
- Enforcement: agent
