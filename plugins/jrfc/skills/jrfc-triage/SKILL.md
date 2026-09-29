---
name: jrfc-triage
description: Use when asked which comments of Copilot, CodeRabbit or other AI reviewers on a pull request matter ("triage the bot comments", "which review comments are noise", "clean up AI review noise on PR 123"). Sorts the open bot comments into relevant, unverified, noise and outdated with `jrfc triage` (Jev + a tool-less verifier with repository evidence), and can reply to and resolve the noise threads with `jrfc publish --resolve-noise`.
---

# jrfc triage

`jrfc triage` keeps the AI reviewers' comments that point to real problems and sets the rest
aside, each with a reason. Code anchors comments on the diff; Jev asks whether a comment is
actionable, which applicable standard covers it, and whether it repeats a jrfc finding or an
earlier comment; a verifier without tools checks the claim against repository evidence; code
decides the status.

## Steps

Run from the root of the repository the PR belongs to (evidence is searched there).

1. Get the diff: `gh pr diff <n> > /tmp/pr.diff`
2. Optional, so bot comments that repeat a jrfc finding count as noise:
   `jrfc review /tmp/pr.diff --out-dir .jrfc-out/pr`
3. `jrfc triage /tmp/pr.diff --pr <n> --findings .jrfc-out/pr/findings.json --out-dir .jrfc-out/pr`
   (without step 2, leave out `--findings`; `--comments threads.json` reads a file instead of the PR)
4. Show the user `.jrfc-out/pr/triage.md`: relevant first, then unverified, noise folded.

## Resolving noise threads on GitHub

This writes to the PR. Show the user the noise list first and wait for a clear yes.

1. `jrfc review /tmp/pr.diff --out-dir .jrfc-out/pr --format github` (publish needs `github-review.json`)
2. `jrfc publish --pr <n> --dir .jrfc-out/pr --resolve-noise --dry-run`, then show `triage-plan.json`
3. After the user agrees: the same command without `--dry-run`.

Threads a person answered, resolved or reopened are never touched.

## Rules for you

- Do not change a status by hand. If a status looks wrong, say why and point to the reason in
  `triage.json`; the fix is a label in `eval/triage/` and a measured change.
- `unverified` is not noise: the verifier could not decide. Present those comments to the user.
- A triaged comment never blocks a merge.
