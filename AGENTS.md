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
make test         # unit + boundary tests, no network
make typecheck    # pyright (Literal types, exhaustive match)
make lint-imports # deterministic modules import no model module
make check        # typecheck + lint-imports + org corpus lint + index current, no model calls
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

## Verification loop
Before every commit, run these steps in order. If a step changes code, start again at step 1.
1. `/simplify` (built-in): cleans up the diff and applies the fixes.
2. `/code-review` (built-in): finds correctness bugs, which `/simplify` does not look for. Check each finding
   against the code. Fix the real ones. For a finding you keep, say in the commit which code shows it is wrong.
3. `make test`, `make check`, `make self-check`. With `TYPESAFE_API_KEY` and a Claude login, also
   `make self-review`.
4. `/verify` (built-in) after a change under `plugins/shall/` or to a rule that the hooks apply. Its recipe is
   `.claude/skills/verify/`. If the recipe fails or misses a step, fix it.
