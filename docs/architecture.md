# jrfc architecture

How jrfc decides which standards apply, reviews against them, and keeps the result
trustworthy. For setup and usage see the [README](../README.md); for measurements see
[results.md](results.md).

## Pipeline

```
artifact (diff | spec | doc | code | task)
   │
   ├─ code   split into chunks (one per file; large files by size)
   ├─ code   prefilter: RFC status, artifact kind, language, Enforcement: linter
   ├─ code   known effects: library calls in the chunk, or reached from it through the
   │         repository, matched against effects.yaml → `known_effects` facts
   ├─ Jev    one Noul per remaining statement: "is this requirement relevant to the content?"
   │         (packed into as few requests as the token budget allows)
   ├─ agent  jrfc-reviewer sees one chunk + only its selected statements (claude -p, no tools)
   ├─ code   validate: statement was selected for the chunk, line is a changed line
   │         (quote relocates), dedupe, blocking recomputed from the corpus, comment cap
   ├─ verify every blocking finding (+ those with depends_on): code graph + keyword search
   │         gather evidence, Jev filters excerpts, jrfc-verifier → confirmed | refuted | unknown
   └─ out    review.md · findings.json · github-review.json · health.json · exit 2 on blocking
```

The split of work is deliberate: **code** decides everything that can be decided exactly,
**Jev** answers narrow semantic questions with calibrated probabilities, the **LLM agent**
judges violations, and **code** again validates and applies every agent output.

## Selection: which statements apply

1. **Prefilter (code).** A statement is dropped when its RFC is not in
   `selection.include_status`, when it does not cover the artifact kind (`artifacts:` on the
   RFC, `- Artifacts:` on the statement), when the RFC is for other languages, or when it is
   `Enforcement: linter` (a linter owns it).
2. **Jev (flat, default).** Every remaining statement becomes one Noul whose state is the
   chunk (plus `known_effects`) and whose criteria are the statement's `Applies when:` /
   `Not applies when:` lines. A Noul is an absolute yes/no, so several statements can apply
   at once. Statements at p ≥ `selection.thresholds.statement` (0.50) are selected.
3. **Layered (optional).** `strategy: layered` asks domain Nouls, then RFC Nouls, then
   statement Nouls only inside what was kept. It uses fewer tokens, but a domain or RFC whose
   description does not cover all of its rules silently drops them; at ~540 statements it
   lost 11 points of recall (see [results](results.md)).
4. **Tasks** ("add an endpoint to refund a payment") use different wording: "will the work
   have to follow this requirement?", and are checked against code-level statements.

Documents are classified as `spec` or `doc` with one Jev Choice before selection.

## Known effects: facts Jev cannot read in the text

Jev judges the text it is given. `requests.post(...)` looks like a network call;
`get_parser(lang)`, `h.DB.Query(...)` or `provider.charge(...)` (a wrapper two files away) do
not, so the timeout rule was not selected. Code supplies the fact and Jev judges it:

- `effects.yaml` in each corpus layer lists what library calls do: `module` (import spec,
  prefix match), `calls` (called through the import), `methods` (called on a receiver that
  is traceably from the module), `languages` (built-ins such as `fetch`). `jrfc lint` checks it.
- **Direct**: imports and calls in the chunk text are matched; no repository needed. A
  `methods` hit needs a receiver from the module (`DB *sql.DB`, `c = Consumer(...)`), so
  `r.URL.Query()` is not reported as a database query: a false fact misleads more than a
  missing one.
- **Indirect**: with the repository, the calls on changed lines are followed through the code
  graph (3 hops) to a listed call:
  `` `provider.charge -> _session.post -> make_session` reaches `requests.Session` in payments/http.py:8 ``.
- The facts go into the Jev state as `known_effects` (only when present, so other cached
  answers stay valid) and into the reviewer prompt.

## Review and validation

The reviewer (`plugins/jrfc/agents/jrfc-reviewer.md`) runs as `claude -p` with no tools, a
fixed system prompt and a JSON schema. It sees one chunk, its known effects and only the
selected statements. Code then drops a finding when its statement was not selected for that
chunk or its line is not a changed line (the quote can relocate it), removes duplicates,
recomputes `blocking` from the corpus (enforced RFC + MUST level) and caps the comment count.

## Verification: a finding blocks only if its evidence was seen

The reviewer sees one chunk, so a finding can be wrong because of code elsewhere (a wrapper
adds the missing flag) or a library default. Giving the reviewer tools was rejected: every
chunk would pay for exploration, the evidence would not be recorded, reruns would read
different files (flapping comments), and CI would expose more of the runner to PR code.

1. **Code picks what is verified**: every blocking finding, plus advisory findings where
   the reviewer filled `depends_on`.
2. **Code gathers evidence** with a language-generic code graph (`codegraph.py`). From the
   calls on the flagged line it follows definitions → calls, base classes, decorators and
   imports, up to 3 hops. It uses tree-sitter grammars and their standard *tags* queries,
   generic tree rules for what tags miss (`this.x =` / `self.x =` members, top-level
   constants, nested declarators, base-class nodes), and import resolution by path suffix; a
   package listed in a dependency manifest is external. Files are parsed lazily (`git grep`
   first); hops resolved only by name are marked "(by name)". Keyword search (YAML key path,
   `depends_on`, code spans of the statement, identifiers of the quote; code before docs) runs
   alongside and covers files without a grammar.
3. **Jev filters excerpts** when there are more than 6 (one Noul per excerpt).
4. **The `jrfc-verifier` agent** (no tools) answers confirmed / refuted / unknown and must
   cite excerpt ids.
5. **Code applies the verdict; severity only goes down**: refuted → dropped only if the cited
   evidence exists; unknown or confirmed-without-evidence → advisory; confirmed → unchanged.

Limits: resolution is by imports and names, not types (a language server or SCIP index
would resolve `this.partner.notify` by type); dependency injection, reflection and clients
configured in YAML or environment variables are invisible to the graph.

## Incremental re-review

Every agent call goes through `run_claude`, which can reuse an earlier answer keyed by
`hash(model, system prompt, schema, prompt)` (`AnswerCache`, `.jrfc-cache/review.json`):

- a review prompt contains the chunk's diff, its selected statements and its known effects,
  so a file is reviewed again exactly when one of those changed;
- a verification prompt contains the finding and the evidence excerpts, so a finding is
  re-checked when the code it depends on changed, even in another file;
- only successful answers are stored; entries unused for 30 days are dropped; the file is
  saved even when the run fails, so answers already paid for are kept.

Trade-off: an answer is stable until its input changes, so a wrong finding on an unchanged
file does not disappear by chance on the next push (it also cannot flap). `--no-cache`
forces fresh calls. The PR workflow restores the cache per pull request.

## Run health

A missed rule, a file that could not be parsed, or evidence that was not found all look the
same on a PR: fewer comments. `jrfc review` writes `health.json` and a health line in the
summary, with warnings for:

- review calls that failed (chunks not reviewed);
- blocking findings downgraded because their evidence was not found, and a high `unknown`
  rate in verification;
- code graph problems: parse errors, tags-query errors, grammars downloaded during the run
  (a network call; `jrfc prefetch` avoids it) or missing (`codegraph.download_grammars: false`).

Statements that scored just below the threshold are listed as information. Threads that
reviewers resolve without a fix are counted by `jrfc publish` ("dismissed").

## Publishing to a pull request

Posting is deterministic code, never the agent. `jrfc publish` (called by
`jrfc-pr-review --post N`) makes each push safe to re-run:

- every inline comment carries a hidden key `hash(statement, path, line content)`; line
  content, not line number, so a finding keeps its key when code above it moves;
- only findings without an existing thread are posted, as one `COMMENT` review;
- an open jrfc thread is resolved when its line is **no longer in the PR diff** (fixed); a
  finding the agent simply did not repeat stays open, so model variance cannot flap it;
- a thread jrfc resolved is reopened if the finding comes back;
- a thread a **person** resolved is left alone and written to `dismissed.json` (feedback);
- one summary comment per PR is updated in place (`<!-- jrfc:summary -->`).

Blocking is the job's exit code (`--fail-on-blocking`, exit 2) on a required check, not a
bot "changes requested" review. `--dry-run` reads the PR and writes `publish-plan.json`
without writing to GitHub.

## Corpus layers

```
engineering-standards/          organisation corpus, prefix JRFC
  jrfc.yaml  corpus/rfcs/  corpus/domains.yaml  corpus/effects.yaml  corpus/index/

booking-service/                an application repository
  .jrfc/jrfc.yaml               prefix: BOOK · extends: {repo: your-org/engineering-standards, ref: v2026.09}
  .jrfc/rfcs/BOOK-0001-*.md     rules only this repository follows
  .jrfc/domains.yaml            optional: local domains (cannot redefine org domains)
  .jrfc/effects.yaml            optional: local known effects
  .jrfc/index/                  generated, local layer only
```

- **Discovery** (first match): `--config` / `$JRFC_CONFIG`, then `.jrfc/jrfc.yaml` or
  `jrfc.yaml` walking up from the cwd, then `$JRFC_EXTENDS=owner/name@ref` (org corpus only),
  then `~/.config/jrfc/config.yaml`.
- **Pinned**: `extends.ref` is a tag or commit sha, fetched once into `~/.cache/jrfc`
  (`$JRFC_CACHE_DIR`; private repositories via `$JRFC_GIT_TOKEN`). A PR is reviewed against
  the same org rules on every run; a repository upgrades by bumping the ref. `extends.path`
  points at a local checkout instead.
- **One prefix per layer**: org `JRFC-`, local e.g. `BOOK-`. Comments show which layer a rule
  comes from; org sources are GitHub permalinks at the pinned commit.
- **Add, never weaken**: `jrfc conflicts --local` compares each local statement with every org
  statement (one Jev request per pair: a Choice for the relation plus two Nouls, "does it
  permit what the org rule forbids?" and "would following it violate the org rule?").
  Duplicate / weakens / conflict ≥ `conflicts.fail_threshold` (0.75) fails CI. A local RFC
  cannot supersede an org RFC. There are no waivers: a rule that should not apply to a
  repository is changed upstream by the domain owner.
- **Settings** (`jev`, `selection`, `conflicts`, `review`, `codegraph`) are inherited from the
  org `jrfc.yaml` and may be overridden locally.

## This repository applies its own standards

This repository is both an organisation corpus (root `jrfc.yaml`, `JRFC-`) and a consumer of
it: `.jrfc/` extends `path: ..` and adds `JTOOL-` rules for the tooling itself.

| RFC | Rules |
| --- | --- |
| JTOOL-0001 Using Jev | only through `jrfc.jev.Jev`; small state, no `existing[i]` indirection; gate on Nouls or summed failing classes; pinned model ids |
| JTOOL-0002 Agent boundaries | reviewer runs without tools; agent output validated before use; external writes deterministic with `--dry-run`; blocking from corpus + verification, only lowered by agents; blocking needs seen evidence |
| JTOOL-0003 CLI contract | exit codes 0/1/2/3; deterministic commands never call a model; reproducible generated files |
| JTOOL-0004 Plugin content (approved) | descriptions say when to use; one reviewer prompt; commands in skills exist |

At the root, plain `jrfc` resolves to `.jrfc/` (a note is printed); organisation corpus
commands use `--config jrfc.yaml` (the Makefile does this).

## Known pain points and how they are handled

| Pain point | Handling |
| --- | --- |
| Agents deciding standards | Agents only draft (`status: draft`); promotion is an owner decision (JRFC-0001.4, CI notice) |
| Unstable statement ids | Ids are in the source; `lint --against` fails on silent removal; `retired:` list |
| Duplicates / conflicts | `jrfc conflicts`: one Jev request per statement pair |
| Rot | `owner` + `review_by` required; lint warns when overdue |
| Mechanical rules via AI | `Enforcement: linter` statements are never sent to Jev or the agent |
| Index needs an agent | No: `jrfc build` is deterministic; semantic text lives in the reviewed source |
| Jev is not an embedding model | One **Noul per candidate** (absolute, multi-label), not Choice-as-similarity |
| Size limits (32k/64k tokens) | Chunking + automatic request packing under the token budget |
| Literal reading | `applies_when` / `not_applies_when` per domain, RFC and statement |
| Facts not in the text | `effects.yaml` + code graph add `known_effects` to the Jev state and the reviewer prompt |
| Applicability ≠ violation | Jev selects, the agent judges violation, code validates |
| Prompt injection | Strict criteria; the reviewer prompt treats content as data; tested (case 08) |
| Noise | Blocking recomputed from corpus, comment cap, dedupe, advisory for SHOULD/approved |
| Hallucinated lines / ids | Findings dropped unless the statement was selected for that chunk and the line is changed |
| Unstable reruns | Jev answer cache; pinned model; `jrfc publish` dedupes comments by content key |
| Repo-specific rules | Local `.jrfc/` layer with its own prefix, pinned `extends:`, `conflicts --local` gate |
| Reviewer sees one file | Verification of blocking findings against repository evidence |
| Silent failures | `health.json` + summary warnings |
| Service outages | Jev failures exit 3 (not 2), so CI can tell "service down" from "change blocked" |
| Code leaves the company | **Open.** Diffs go to TypeSafe and Anthropic: get data-protection approval first |
