# shall

RFC 2119 engineering standards plus tooling: Jev selects the statements that apply to a
diff/spec/doc/code/task, `claude -p` (no tools) reviews against them, deterministic code validates,
verifies and posts to GitHub PRs. CLI: `plugins/shall/bin/shall` (wraps `uv run`).

## Read first, by task
- Any code change → `docs/development.mdx` (code map, tests, evals) and the rules in
  `.shall/rfcs/JTOOL-*.md`. Design reasons → `docs/architecture.mdx`.
- Selection, prompts, thresholds, question wording → also `docs/results.mdx`; run the eval before
  and after (`docs/development.mdx#evals`).
- Hooks → `docs/hooks.mdx`; scan → `docs/scan.mdx`; triage → `docs/triage.mdx`.
- Corpus (`corpus/`, `.shall/rfcs/`) → `docs/standards.mdx`, or the `shall-author` skill.
- Skills, agents, `hooks.json` → `JTOOL-0004` and `docs/development.mdx#release-plugin-changes`.
- User docs: `README.md` (pitch, quick start) and `docs/*.mdx`, written in ASD-STE100.

## Workspaces
Plain `shall` resolves to `.shall/` (this repo's `JTOOL-` rules). The example org corpus (`corpus/`,
`JRFC-`) needs `--config shall.yaml`; the Makefile adds it. Wrong workspace = wrong rules, silently.

## Commands
```bash
make test         # unit tests, no network
make check        # org corpus lint + index current, no model calls
make build        # after editing corpus/ (index is committed)
make self-check   # this repo's own rules
```
`select`/`review` cache answers in `.shall-cache/`; use `--no-cache` when you measure model behavior,
else unchanged chunks reuse old answers.

## Rules
- Invariants are statements in `.shall/rfcs/JTOOL-*.md` (Jev only via `shall.jev.Jev`, tool-less
  agents, validated agent output, exit codes 0/1/2/3, model-free deterministic commands). Follow
  them; `make self-review` checks a change against them.
- Agent prompts in `plugins/shall/agents/*.md` are also the CI system prompts: a change shifts
  cache keys and eval numbers. Eval before and after.
- Corpus: never renumber or reuse a statement id (retire it); agents write `status: draft` only.
- Bump `version` in `plugins/shall/.claude-plugin/plugin.json` when skills, agents or hooks change:
  Claude Code caches plugins per version.
- This repo is public: no real company code, names, ids or secrets in tests, evals or docs.
