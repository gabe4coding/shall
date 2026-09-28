# Postmortem: booking confirmations delayed (2026-09-12)

## Summary

On Saturday evening booking confirmations were delayed. Bob deployed a bad config to the
notification service without testing it, which caused the queue to back up. It was fixed
after a while.

## What happened

- Evening: alerts fired for the confirmation queue.
- Later: the on-call engineer rolled back the config.
- Everything recovered.

## Root cause

Human error by Bob.

## Next steps

- Be more careful with config changes.
- Maybe add a test.
