---
name: shall-index
description: Use when the shall index or catalog must be built, refreshed or checked — after any change to corpus/rfcs/*.md or corpus/domains.yaml, when CI reports "stale index", or when someone asks to regenerate index.json / catalog.md. The index is built by a deterministic script, never by hand or by a model.
---

# shall index

`shall build` writes `index/index.json` (tools, CI) and `index/catalog.md` (one line per statement)
from the RFC sources, byte for byte reproducibly. Never edit the index by hand: semantic text
(summaries, `Applies when:`) belongs in the RFC source, where a human reviews it.

In an app repo, `shall build` writes `.shall/index/` for the local layer only; the org corpus is
recorded by name and pinned ref. `shall catalog` prints the merged view.

```bash
shall lint                              # format, ids, one level per statement, references
shall build                             # write the index (refuses while lint has errors)
shall build --check                     # CI: fail if the committed index differs from a fresh build
shall lint --against base-index.json    # CI: fail if a published statement id disappeared
```

## When a check fails

- **Lint error** → fix the RFC source (skill `shall-author`), then build again.
- **`build --check` stale** → run `shall build`; commit the index with the RFC change.
- **`statement-removed`** → restore the id, or add it to the RFC's `retired:` list if the removal is intended.

`blocking` is computed (RFC `enforced` and level MUST), never authored.
