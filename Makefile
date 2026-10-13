JRFC := plugins/shall/bin/shall
# This repo holds two workspaces: the organisation corpus (shall.yaml, prefix JRFC) and the
# repo's own rules (.shall/, prefix JTOOL, extends the organisation corpus). Plain `shall` at
# the root resolves to .shall/; organisation targets pass --config explicitly.
ORG := $(JRFC) --config shall.yaml

TOOLING := uv run --quiet --project plugins/shall/tooling

.PHONY: check lint build test typecheck lint-imports test-plugin eval eval-scale eval-facts eval-hooks eval-hooks-claude eval-triage eval-realpr review-example self-check self-conflicts self-review

# test-plugin is not part of check: it needs the claude CLI, and check must run with uv only.
check: lint typecheck lint-imports  ## deterministic CI checks: corpus, index, types, module layers (no model calls)
	$(ORG) build --check

lint:
	$(ORG) lint

build:
	$(ORG) build

test:                ## tooling unit tests (no network)
	$(TOOLING) pytest -q plugins/shall/tooling/tests

typecheck:           ## pyright: Literal statuses/levels/verdicts, Optional narrowing, exhaustive match
	$(TOOLING) --group check pyright -p plugins/shall/tooling/pyproject.toml

lint-imports:        ## import-linter: deterministic modules never import a model module (JTOOL-0003.2)
	$(TOOLING) --group check lint-imports --config plugins/shall/tooling/pyproject.toml

test-plugin:         ## plugin manifest and TypeScript hook tests (needs the claude CLI)
	claude plugin validate plugins/shall
	claude plugin test plugins/shall

eval:                ## selection recall/precision on eval/cases (needs TYPESAFE_API_KEY)
	$(ORG) eval --out .shall-out/eval.json

eval-facts:          ## hidden effects: known_effects on vs off (eval/facts, needs TYPESAFE_API_KEY)
	$(ORG) eval --strategy flat --labels eval/facts/labels.yaml --out .shall-out/eval-facts.json
	$(ORG) eval --strategy flat --labels eval/facts/labels.yaml --no-facts --out .shall-out/eval-facts-off.json

eval-scale:          ## selection at scale: ~540 statements (eval/scale), layered vs flat (needs TYPESAFE_API_KEY)
	$(JRFC) --config eval/scale/.shall/shall.yaml eval --labels eval/scale/labels.yaml --out .shall-out/eval-scale.json

eval-triage:         ## triage of AI review comments on eval/triage (needs TYPESAFE_API_KEY and claude)
	$(ORG) eval-triage --out .shall-out/eval-triage.json

eval-hooks:          ## hook judge: 97 labelled tool calls and writes (eval/hooks, needs TYPESAFE_API_KEY)
	$(ORG) eval-hooks --out .shall-out/eval-hooks.json

eval-hooks-claude:   ## the same cases with Claude (hooks.claude.model) as the judge (needs claude)
	$(ORG) eval-hooks --judge claude --out .shall-out/eval-hooks-claude.json

eval-realpr:         ## real public PRs with AI-bot comments: review + triage graded (needs gh, TYPESAFE_API_KEY, claude; ~$16)
	uv run --quiet --project plugins/shall/tooling python eval/realpr/run.py fetch
	uv run --quiet --project plugins/shall/tooling python eval/realpr/run.py run
	uv run --quiet --project plugins/shall/tooling python eval/realpr/run.py label
	uv run --quiet --project plugins/shall/tooling python eval/realpr/run.py grade

review-example:      ## full pipeline on one case (needs TYPESAFE_API_KEY and claude)
	$(ORG) review eval/cases/01-booking-endpoint.diff --out-dir .shall-out/example --format github

self-check:          ## this repo's own rules (.shall/): lint + index, no model calls
	$(JRFC) lint
	$(JRFC) build --check

self-conflicts:      ## own rules must not duplicate/weaken/conflict with org rules (needs TYPESAFE_API_KEY)
	$(JRFC) conflicts --local

self-review:         ## review this repo's working-tree changes against org + own rules
	mkdir -p .shall-out
	git diff --no-color HEAD > .shall-out/self.diff 2>/dev/null || git diff --no-color > .shall-out/self.diff
	$(JRFC) review .shall-out/self.diff --out-dir .shall-out/self
