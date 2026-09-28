---
name: jrfc-standards
description: Use before writing or changing code, an API, a migration, a design spec or other engineering work in a repository that uses jrfc standards (a .jrfc/ folder or jrfc.yaml, or JRFC_EXTENDS / ~/.config/jrfc set), to find which engineering standards apply and follow them from the start. Also use when the user asks "what are our standards for X", "which RFC covers Y", or cites an id like JRFC-0003.1.
---

# Follow jrfc standards while you work

The jrfc corpus holds the organisation's engineering standards as RFC 2119 statements
(MUST / SHOULD / MAY). Load only what applies — never read the whole corpus into context.

## Before you start a task

Ask the selector which statements apply to the work you are about to do:

```bash
jrfc select --text "<one or two sentences describing the change you will make>"
```

It returns statement ids with a probability. Then open the ones you need:

```bash
jrfc show JRFC-0006.1 JRFC-0003.1      # statement text, level, applicability, source line
```

Follow MUST statements; follow SHOULD statements unless you have a reason, and tell the
user the reason. Mention the ids you followed in your summary or commit message.

## Browsing

- `jrfc catalog` — one line per statement of all layers (organisation + this repo's
  `.jrfc/`), grouped by domain and RFC. Local ids have the repo prefix (e.g. `BOOK-`);
  they apply in this repo on top of the organisation rules.
- `jrfc list [--domain api] [--status enforced]` — RFCs with status.
- `jrfc show JRFC-0002` — a full RFC with its context.

## Before you hand over

Run the review on your own change and fix what it reports:

```bash
git diff > /tmp/change.diff && jrfc review /tmp/change.diff --out-dir .jrfc-out/self
```

## Status meanings

If `jrfc` says no config is found, the repository has no standards set up; tell the user
(`jrfc init`, or `JRFC_EXTENDS=<org>/<corpus-repo>@<tag>` for organisation rules only).

`enforced` MUST statements block merges in CI; `approved` statements produce advisory
comments; `draft` statements are proposals — do not treat them as rules.
