---
name: jrfc-index
description: Use when the jrfc index or catalog must be built, refreshed or checked — after any change to corpus/rfcs/*.md or corpus/domains.yaml, when CI reports "stale index", or when someone asks to regenerate index.json / catalog.md. The index is built by a deterministic script, never by hand or by a model.
---

# jrfc index

The index is a pure function of the corpus: `jrfc build` reads `corpus/rfcs/*.md` and
`corpus/domains.yaml` and writes, byte for byte reproducibly:

| File | Consumer | Content |
| --- | --- | --- |
| `corpus/index/index.json` | tools, CI, review pipeline | domains, RFCs, every statement with level, blocking flag, applicability, source line |
| `corpus/index/catalog.md` | agents and humans | domain → RFC → one line per statement; the entry point for progressive disclosure |

In an app repo with a `.jrfc/` layer, `jrfc build` writes `.jrfc/index/` for the **local
layer only**; the organisation corpus is recorded by name and pinned ref, never copied, so
`build --check` depends only on the repo's own files. `jrfc catalog` prints the merged view.

No model runs at build time. Anything semantic (summaries, `Applies when:` text) is
written in the RFC source, where a human reviews it; the build only copies it.

## Commands

```bash
jrfc lint                    # format, ids, one level per statement, references
jrfc build                   # write the index (refuses while lint has errors)
jrfc build --check           # CI: fail if the committed index differs from a fresh build
jrfc lint --against base-index.json   # CI: fail if a published statement id disappeared
```

## When a check fails

- **Lint error** → fix the RFC source (see the `jrfc-author` skill), then build again.
  Never silence a rule by editing the index.
- **`build --check` stale** → someone changed the corpus without rebuilding. Run
  `jrfc build` and commit the index together with the RFC change.
- **`statement-removed`** → a published id was deleted. Restore it, or add it to the
  RFC's `retired:` list if the removal is intended.

`blocking` in the index is computed, not authored: a statement blocks merges only when
its RFC is `enforced` **and** its level is MUST.
