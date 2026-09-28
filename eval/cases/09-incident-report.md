# Incident report: booking confirmations delayed (2026-09-12)

## Summary

Between 18:02 and 18:47 CET, 14% of booking confirmations were delayed by up to 30
minutes. No booking was lost.

## Timeline

- 18:02 Queue lag alert fires for `booking-confirmations`.
- 18:10 On-call acknowledges; consumer pods are healthy.
- 18:31 Root cause found: a restaurant integration partner was slow and the consumer
  waited on it without a timeout.
- 18:47 Partner recovered; lag back to normal.

## Follow-up actions

- Add a timeout to the partner call (owner: bookings team, due 2026-09-30).
- Add an alert on partner latency (owner: SRE, due 2026-10-07).
