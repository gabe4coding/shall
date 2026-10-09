JRFC := plugins/shall/bin/shall
# This repo holds two workspaces: the organisation corpus (shall.yaml, prefix JRFC) and the
# repo's own rules (.shall/, prefix JTOOL, extends the organisation corpus). Plain `shall` at
# the root resolves to .shall/; organisation targets pass --config explicitly.
ORG := $(JRFC) --config shall.yaml

.PHONY: check lint build test eval eval-scale eval-facts eval-hooks eval-triage review-example self-check self-conflicts self-review

check: lint          ## organisation corpus: deterministic CI checks (no model calls)
	$(ORG) build --check

lint:
	$(ORG) lint

build:
	$(ORG) build

test:                ## tooling unit tests (no network)
	uv run --quiet --project plugins/shall/tooling pytest -q plugins/shall/tooling/tests

eval:                ## selection recall/precision on eval/cases (needs TYPESAFE_API_KEY)
	$(ORG) eval --out .shall-out/eval.json

eval-facts:          ## hidden effects: known_effects on vs off (eval/facts, needs TYPESAFE_API_KEY)
	$(ORG) eval --strategy flat --labels eval/facts/labels.yaml --out .shall-out/eval-facts.json
	$(ORG) eval --strategy flat --labels eval/facts/labels.yaml --no-facts --out .shall-out/eval-facts-off.json

eval-scale:          ## selection at scale: ~540 statements (eval/scale), layered vs flat (needs TYPESAFE_API_KEY)
	$(JRFC) --config eval/scale/.shall/shall.yaml eval --labels eval/scale/labels.yaml --out .shall-out/eval-scale.json

eval-triage:         ## triage of AI review comments on eval/triage (needs TYPESAFE_API_KEY and claude)
	$(ORG) eval-triage --out .shall-out/eval-triage.json

eval-hooks:          ## hook judge: 75 labelled tool calls and writes (eval/hooks, needs TYPESAFE_API_KEY)
	$(ORG) eval-hooks --out .shall-out/eval-hooks.json

review-example:      ## full pipeline on one case (needs TYPESAFE_API_KEY and claude)
	$(ORG) review eval/cases/01-booking-endpoint.diff --out-dir .shall-out/example --format github

self-check:          ## this repo's own rules (.shall/): lint + index, no model calls
	$(JRFC) lint
	$(JRFC) build --check

self-conflicts:      ## own rules must not duplicate/weaken/conflict with org rules (needs TYPESAFE_API_KEY)
	$(JRFC) conflicts --local

self-review:         ## review this repo's working-tree changes against org + own rules
	git diff --no-color HEAD > .shall-out/self.diff 2>/dev/null || git diff --no-color > .shall-out/self.diff
	$(JRFC) review .shall-out/self.diff --out-dir .shall-out/self
