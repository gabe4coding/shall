---
name: shall-standards
description: Use before writing or changing code, an API, a migration, a design spec or other engineering work in a repository that uses shall standards (a .shall/ folder or shall.yaml, or SHALL_EXTENDS / ~/.config/shall set), to find which engineering standards apply and follow them from the start. Also use when the user asks "what are our standards for X", "which RFC covers Y", or cites an id like JRFC-0003.1.
---

# Follow shall standards while you work

Load only the statements that apply. Never read the whole corpus into context.

## Before you start a task

```bash
shall select --text "<one or two sentences describing the change you will make>"
shall show JRFC-0006.1 JRFC-0003.1      # text, level, applicability of the ids it returned
```

Follow MUST statements. Follow SHOULD statements unless you have a reason; tell the user the
reason. Mention the ids you followed in your summary or commit message.

`enforced` MUST statements block merges in CI; `approved` ones give advisory comments; `draft`
ones are proposals, not rules. Local ids (repo prefix, for example `BOOK-`) apply on top of
organisation rules.

## Browse

- `shall catalog`: one line per statement, all layers.
- `shall list [--domain api] [--status enforced]`: RFCs with status.
- `shall show JRFC-0002`: a full RFC with its context.

## Check existing files

`shall scan src/payments/` lints files (one Jev request per file). A warning is Jev's judgment on one
file: read the code before you act. Only secret-scanner hits block.

## Before you hand over

```bash
git diff > /tmp/change.diff && shall review /tmp/change.diff --out-dir .shall-out/self
```

Fix what it reports. If `shall` finds no config, the repository has no standards: tell the user
(`shall init`, or `SHALL_EXTENDS=<org>/<corpus-repo>@<tag>` for organisation rules only).
