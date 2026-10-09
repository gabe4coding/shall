---
name: jrfc-standards
description: Use before writing or changing code, an API, a migration, a design spec or other engineering work in a repository that uses jrfc standards (a .jrfc/ folder or jrfc.yaml, or JRFC_EXTENDS / ~/.config/jrfc set), to find which engineering standards apply and follow them from the start. Also use when the user asks "what are our standards for X", "which RFC covers Y", or cites an id like JRFC-0003.1.
---

# Follow jrfc standards while you work

Load only the statements that apply. Never read the whole corpus into context.

## Before you start a task

```bash
jrfc select --text "<one or two sentences describing the change you will make>"
jrfc show JRFC-0006.1 JRFC-0003.1      # text, level, applicability of the ids it returned
```

Follow MUST statements. Follow SHOULD statements unless you have a reason; tell the user the
reason. Mention the ids you followed in your summary or commit message.

`enforced` MUST statements block merges in CI; `approved` ones give advisory comments; `draft`
ones are proposals, not rules. Local ids (repo prefix, for example `BOOK-`) apply on top of
organisation rules.

## Browse

- `jrfc catalog`: one line per statement, all layers.
- `jrfc list [--domain api] [--status enforced]`: RFCs with status.
- `jrfc show JRFC-0002`: a full RFC with its context.

## Check existing files

`jrfc scan src/payments/` lints files (one Jev request per file). A warning is Jev's judgment on one
file: read the code before you act. Only secret-scanner hits block.

## Before you hand over

```bash
git diff > /tmp/change.diff && jrfc review /tmp/change.diff --out-dir .jrfc-out/self
```

Fix what it reports. If `jrfc` finds no config, the repository has no standards: tell the user
(`jrfc init`, or `JRFC_EXTENDS=<org>/<corpus-repo>@<tag>` for organisation rules only).
