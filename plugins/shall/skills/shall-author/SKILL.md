---
name: shall-author
description: Use when creating, changing, splitting, deprecating or reviewing the wording of a shall engineering standard (an RFC file under the corpus, ids like JRFC-0003) — for example "write a standard for X", "turn this guideline into an RFC", "update the logging RFC", "retire JRFC-0004.2". Covers the file format, the RFC 2119 rules, the lint and conflict checks, and what an agent may and may not change.
---

# Authoring shall standards

You write **drafts** that a human domain owner approves. You never decide that a standard is in force.

## Hard rules

- New RFCs get `status: draft`. Never set or change `status` to `approved` or `enforced`, and never
  remove an `Enforcement:` line to bypass a linter rule: promotion is the owner's decision
  (JRFC-0001.4). If asked to promote, prepare the change and say the RFC's `owner` approves it in review.
- Never renumber or reuse a published statement id. To remove a statement, delete its section and add
  its id to `retired: [...]` (JRFC-0001.2). To change a meaning, add a new statement and retire the
  old one, so past review comments still match the text they quoted.
- Never edit `index/*` by hand; `shall build` writes it.
- A new domain is a human decision: ask first.

## Workflow

1. Check what exists: `shall catalog`. Add a statement to an existing RFC when the rule belongs there.
2. Scaffold: `shall new --domain <domain> --title "<title>"` (prints the path, picks the next id).
3. Write the statements. Read `references/format.md` first: it has the file template and how to
   word `Applies when:` so Jev selects the rule.
4. `shall lint`. Fix every error; treat warnings as work to do.
5. `shall conflicts <file> [--all-domains]` (`--local` for all local rules of an app repo). Resolve
   every `FAIL` (duplicate, weakens, conflict) by merging, rewording or citing the existing
   statement. Report `overlap` results to the user; some are intended refinements.
6. `shall build`, then commit the index with the RFC.
7. Self-review: `shall review <rfc file> --kind doc` (checks the draft against JRFC-0001).
8. Hand over: new statements, open questions, conflict results. Leave the PR to the user unless asked.

## Organisation corpus or local `.shall/`?

- A rule for every team → organisation corpus (prefix `JRFC-`), owned by the domain owner.
- A rule for one repository → that repo's `.shall/rfcs/` with its prefix (for example `BOOK-`).
  Create the layer once: `shall init --prefix BOOK --repo <org>/<corpus-repo> --ref <tag>`.
- Local rules may only add or tighten requirements. `shall conflicts --local` must pass. A local
  exception to an org rule is not a local rule: propose the change to the org RFC's owner. No waivers.
- Reuse org domains; add one in `.shall/domains.yaml` only for an area the org corpus lacks.
- Same local rule in several repos → suggest upstreaming it.

## Rule not selected because a library hides the effect?

When a call hides a network, database or process effect (`get_parser(lang)` downloads a file), add
a known effect instead of widening `Applies when:`. Read `references/effects.md`.

## Deprecate or refresh

- Deprecate: `status: deprecated` + `superseded_by: JRFC-NNNN` (owner approval).
- `review_by` in the past (lint warns): ask the owner whether the RFC is still right, then bump the
  date in the same change as any fix.
