# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

jrfc: a corpus of RFC 2119 engineering standards plus tooling that selects which statements
apply to a diff/spec/doc/code/task (TypeSafe **Jev**), reviews against them (`claude -p`,
no tools), validates and verifies findings with deterministic code, and posts to GitHub PRs.
User guide: `README.md`. Design: `docs/architecture.md`. Measurements: `docs/results.md`.

## Commands

The CLI is `plugins/jrfc/bin/jrfc` (a wrapper around `uv run --project plugins/jrfc/tooling jrfc`).

```bash
make test                     # unit tests, no network
uv run --quiet --project plugins/jrfc/tooling pytest -q plugins/jrfc/tooling/tests/test_effects.py -k fetch   # one test
make check                    # org corpus: lint + index up to date (no model calls)
make build                    # regenerate corpus/index/ after editing corpus/ (the index is committed)
make self-check               # this repo's own rules (.jrfc/, JTOOL-) lint + index
make eval / eval-scale / eval-facts   # selection evals (need TYPESAFE_API_KEY)
make eval-hooks               # hook judge on eval/hooks/cases.yaml (--no-cache to measure latency)
make eval-triage              # triage of AI review comments (needs TYPESAFE_API_KEY and claude)
plugins/jrfc/bin/jrfc --config jrfc.yaml eval-verify --retrieval treesitter   # verification eval (needs claude)
```

**Two workspaces live at the root.** Plain `jrfc` resolves to `.jrfc/` (this repo's own
`JTOOL-` rules, which extend the org corpus via `path: ..`). Anything about the example
organisation corpus (`corpus/`, prefix `JRFC-`) needs `--config jrfc.yaml` (the Makefile
does this). The scale eval corpus is a third workspace: `--config eval/scale/.jrfc/jrfc.yaml`.

Jev answers are cached in `.jrfc-cache/jev.json` and Claude answers in `.jrfc-cache/review.json`
(per workspace, keyed by the exact input: any change to a question, prompt, state or agent
prompt is a new call). Use `--no-cache` on `select`/`review` to force fresh calls — needed when
measuring model behavior, since `review` otherwise reuses answers for unchanged chunks.

## Architecture (plugins/jrfc/tooling/src/jrfc/)

Flow of `jrfc review`: `cli.py` → `config.py` → `corpus.py` → `artifact.py` → `effects.py`
→ `select.py` → `review.py` → `verify.py` (+ `codegraph.py`) → `health.py` → outputs;
`publish.py` posts separately. `jrfc triage` (`triage.py`) sorts other AI reviewers' PR
comments with the same selection and verification evidence (`verify.gather_evidence`).

- **config.py**: layer discovery (`--config`/`JRFC_CONFIG` → `.jrfc/jrfc.yaml` or `jrfc.yaml`
  walking up → `JRFC_EXTENDS` → `~/.config/jrfc`), one optional parent layer via `extends`
  (fetched by `fetch.py` into `~/.cache/jrfc`), settings groups in `SETTINGS` inherited from
  the parent and overridden locally. Defaults in `DEFAULTS`.
- **corpus.py**: parses RFC Markdown (front matter + `### PREFIX-NNNN.n` statements), lint
  rules, merges layers, and loads `effects.yaml` of every layer into `corpus.effects`.
- **artifact.py**: splits input into `Chunk`s (one per file of a diff, size-split), with
  `anchor_lines` (commentable lines) and `line_text`. `Chunk.state()` is the Jev state.
- **effects.py**: known side effects of library calls → `known_effects` facts. Direct
  (imports + calls in chunk text) and indirect (calls on changed lines followed through
  `codegraph.expand`). `methods` matches require a receiver traceably from the module —
  false facts are worse than none; `tests/test_effects.py::test_no_false_facts` guards this.
- **select.py**: code prefilter (`Selector.eligible`: status, artifact kind, language,
  `Enforcement: linter`), then one Jev Noul per statement (`flat`, default) or
  domain → RFC → statement (`layered`). `known_effects` is added to the state only when present.
- **jev.py**: the only access point to TypeSafe (cache, request packing under the token
  budget, retries, usage incl. cache-independent `est_input_tokens`).
- **review.py**: reviewer prompt per chunk, `run_claude` (tool-less `claude -p` with JSON
  schema; system prompt from `plugins/jrfc/agents/*.md`, shared with in-session use;
  `AnswerCache` makes re-reviews incremental),
  `validate_findings`, markdown/GitHub rendering with content-hash comment keys.
- **verify.py / codegraph.py**: evidence for blocking findings (tree-sitter tags + generic
  rules, import resolution, lazy parsing guided by `git grep`, keyword search), verifier
  agent, `apply_verdict`. One `RepoIndex` per run is shared by facts and verification;
  it records parse/download problems in `index.events`.
- **health.py**: `health.json` + summary warnings for silent failures.
- **hooks.py**: Claude Code hooks (`jrfc hook` command transport, `jrfc hookd` localhost HTTP
  server, `jrfc hook-config`). Jev judges tool calls against `tool` statements (`Tools:`,
  `Violated when:`) and written lines against code statements, p = min(applies, violates);
  `hooks.actions[status][level]` maps p to deny/ask/warn/log; writes only warn; Stop runs
  `jrfc review`. Secret scanner redacts before Jev. Fail-open on Jev timeout/error.
- **evaluate.py**: selection eval (per-strategy cost, layer that dropped each miss,
  `--no-facts` A/B, optional `repo:` fixture per case) and verification eval.

## Invariants (this repo's own rules, `.jrfc/rfcs/JTOOL-*.md`)

- Jev only through `jrfc.jev.Jev`; small state, no `existing[i]`-style indirection; gate on
  absolute Nouls (or summed failing Choice classes); pinned model ids (no aliases).
- Agents run without tools (`--tools ""`); every agent output is validated by code before use;
  agents can only lower severity; a finding blocks only if its evidence was seen.
- Writes outside the working directory (GitHub) are deterministic code with `--dry-run`.
- Exit codes: 0 ok, 1 error, 2 blocking findings, 3 Jev service failure. Deterministic
  commands (`lint`, `build`, `list`, `show`, `new`, `init`, `publish`) never call a model.
  Generated files (`index/`) are byte-reproducible.

## Corpus rules when editing standards

One RFC 2119 level per statement, keywords UPPERCASE only; never renumber or reuse a
statement id (retire it); agents create `status: draft` only — promotion is the domain
owner's decision; `Applies when:` lines are Jev criteria, so write them literally. Run
`make build` (and `make check`) after changing `corpus/`, and `jrfc build` for `.jrfc/`.

## Evals

Before changing thresholds, question wording, prompts or selection logic, run the relevant
eval before and after. In `eval/scale/labels.yaml` most labels were auto-accepted where
Claude and Jev-flat agreed, so flat recall is inflated there; the hand-reviewed subset is the
unbiased measure. `eval/verify/*` fixtures are copied to a temp dir and `git init`ed by the
eval (the code graph uses `git grep`).
