---
name: shall-triage
description: Use when asked which comments of Copilot, CodeRabbit or other AI reviewers on a pull request matter ("triage the bot comments", "which review comments are noise", "clean up AI review noise on PR 123"). Sorts the open bot comments into relevant, unverified, noise and outdated with `shall triage` (Jev + a tool-less verifier with repository evidence), and can reply to and resolve the noise threads with `shall publish --resolve-noise`.
---

# shall triage

Run from the root of the repository the PR belongs to (evidence is searched there).

1. `gh pr diff <n> > /tmp/pr.diff`
2. Optional, so bot comments that repeat a shall finding count as noise:
   `shall review /tmp/pr.diff --out-dir .shall-out/pr`
3. `shall triage /tmp/pr.diff --pr <n> --findings .shall-out/pr/findings.json --out-dir .shall-out/pr`
   (without step 2, leave out `--findings`; `--comments threads.json` reads a file instead of the PR)
4. Show the user `.shall-out/pr/triage.md`: relevant first, then unverified, noise folded.

## Resolve noise threads on GitHub

This writes to the PR. Show the user the noise list first and wait for a clear yes.

1. `shall review /tmp/pr.diff --out-dir .shall-out/pr --format github` (publish needs `github-review.json`)
2. `shall publish --pr <n> --dir .shall-out/pr --resolve-noise --dry-run`, then show `triage-plan.json`
3. After the user agrees: the same command without `--dry-run`.

Threads a person answered, resolved or reopened are never touched.

## Rules for you

- Do not change a status by hand. If one looks wrong, point to its reason in `triage.json`; the fix
  is a label in `eval/triage/` and a measured change.
- `unverified` is not noise: the verifier could not decide. Present those comments to the user.
- A triaged comment never blocks a merge.
