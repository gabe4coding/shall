# shall architecture

How shall decides which standards apply, reviews against them, and keeps the result
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
   ├─ agent  shall-reviewer sees one chunk + only its selected statements (claude -p, no tools)
   ├─ code   validate: statement was selected for the chunk, line is a changed line
   │         (quote relocates), dedupe, blocking recomputed from the corpus, comment cap
   ├─ verify every blocking finding (+ those with depends_on): code graph + keyword search
   │         gather evidence, Jev filters excerpts, shall-verifier → confirmed | refuted | unknown
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
  is traceably from the module), `languages` (built-ins such as `fetch`). `shall lint` checks it.
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

The reviewer (`plugins/shall/agents/shall-reviewer.md`) runs as `claude -p` with no tools, a
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
4. **The `shall-verifier` agent** (no tools) answers confirmed / refuted / unknown and must
   cite excerpt ids.
5. **Code applies the verdict; severity only goes down**: refuted → dropped only if the cited
   evidence exists; unknown or confirmed-without-evidence → advisory; confirmed → unchanged.

Limits: resolution is by imports and names, not types (a language server or SCIP index
would resolve `this.partner.notify` by type); dependency injection, reflection and clients
configured in YAML or environment variables are invisible to the graph.

## Incremental re-review

Every agent call goes through `run_claude`, which can reuse an earlier answer keyed by
`hash(model, system prompt, schema, prompt)` (`AnswerCache`, `.shall-cache/review.json`):

- a review prompt contains the chunk's diff, its selected statements and its known effects,
  so a file is reviewed again exactly when one of those changed;
- a verification prompt contains the finding and the evidence excerpts, so a finding is
  re-checked when the code it depends on changed, even in another file;
- only successful answers are stored; entries unused for 30 days are dropped; the file is
  saved even when the run fails, so answers already paid for are kept.

Trade-off: an answer is stable until its input changes, so a wrong finding on an unchanged
file does not disappear by chance on the next push (it also cannot flap). `--no-cache`
forces fresh calls. The PR workflow restores the cache per pull request.

## Triage of other AI reviewers' comments

`shall triage` applies the same split of work to comments that Copilot, CodeRabbit and similar
bots left on the pull request. The goal is the opposite of a review: not to find problems, but
to keep the bots' real problems and set the noise aside, with a reason for each.

```
open review threads (gh, read only) or a JSON file
   ├─ code   keep threads started by a bot (GraphQL type Bot, triage.authors), not shall's own,
   │         not resolved; strip folded extras (<details>, HTML comments); anchor on the diff
   │         → outdated when the file or the line is gone
   ├─ Jev    selection of the commented chunk (the review's questions, shared cache)
   ├─ Jev    per comment: actionable? + one Noul per selected statement: does it cover the concern?
   ├─ Jev    per pair on nearby lines (shall findings first, then earlier comments): same problem?
   ├─ agent  shall-comment-verifier (no tools) with the verification evidence: confirmed | refuted | unknown
   └─ code   relevant (confirmed + cited) · unverified (kept) · noise (not actionable, duplicate,
             or refuted + cited evidence that exists) · outdated → triage.json, triage.md
```

- **Noise needs a reason code can show.** An unknown verdict or a verdict without valid
  citations keeps the comment as unverified: a dropped real problem costs more than one comment
  too many.
- **The verifier judges truth, not importance.** "Also log the amount" is literally true, so
  importance is Jev's "actionable" question, before the agent.
- **Never blocking.** A bot comment has no corpus severity; blocking stays with shall's review.
- **Publishing.** `shall publish` adds the triage to the summary comment. With
  `--resolve-noise` it reads the threads again, and for each noise thread that is still open,
  has no reply by a person and no earlier shall reply, it posts the reason (with a hidden
  `shall:triage` key) and resolves it. A person who reopens the thread wins: shall replied once
  and does not resolve it again. `--dry-run` writes `triage-plan.json` only.

## Run health

A missed rule, a file that could not be parsed, or evidence that was not found all look the
same on a PR: fewer comments. `shall review` writes `health.json` and a health line in the
summary, with warnings for:

- review calls that failed (chunks not reviewed);
- blocking findings downgraded because their evidence was not found, and a high `unknown`
  rate in verification;
- code graph problems: parse errors, tags-query errors, grammars downloaded during the run
  (a network call; `shall prefetch` avoids it) or missing (`codegraph.download_grammars: false`).

Statements that scored just below the threshold are listed as information. Threads that
reviewers resolve without a fix are counted by `shall publish` ("dismissed").

## Publishing to a pull request

Posting is deterministic code, never the agent. `shall publish` (called by
`shall-pr-review --post N`) makes each push safe to re-run:

- every inline comment carries a hidden key `hash(statement, path, line content)`; line
  content, not line number, so a finding keeps its key when code above it moves;
- only findings without an existing thread are posted, as one `COMMENT` review;
- an open shall thread is resolved when its line is **no longer in the PR diff** (fixed); a
  finding the agent simply did not repeat stays open, so model variance cannot flap it;
- a thread shall resolved is reopened if the finding comes back;
- a thread a **person** resolved is left alone and written to `dismissed.json` (feedback);
- one summary comment per PR is updated in place (`<!-- shall:summary -->`).

Blocking is the job's exit code (`--fail-on-blocking`, exit 2) on a required check, not a
bot "changes requested" review. `--dry-run` reads the PR and writes `publish-plan.json`
without writing to GitHub.

## Corpus layers

```
engineering-standards/          organisation corpus, prefix JRFC
  shall.yaml  corpus/rfcs/  corpus/domains.yaml  corpus/effects.yaml  corpus/index/

booking-service/                an application repository
  .shall/shall.yaml               prefix: BOOK · extends: {repo: your-org/engineering-standards, ref: v2026.09}
  .shall/rfcs/BOOK-0001-*.md     rules only this repository follows
  .shall/domains.yaml            optional: local domains (cannot redefine org domains)
  .shall/effects.yaml            optional: local known effects
  .shall/index/                  generated, local layer only
```

- **Discovery** (first match): `--config` / `$SHALL_CONFIG`, then `.shall/shall.yaml` or
  `shall.yaml` walking up from the cwd, then `$SHALL_EXTENDS=owner/name@ref` (org corpus only),
  then `~/.config/shall/config.yaml`.
- **Pinned**: `extends.ref` is a tag or commit sha, fetched once into `~/.cache/shall`
  (`$SHALL_CACHE_DIR`; private repositories via `$SHALL_GIT_TOKEN`). A PR is reviewed against
  the same org rules on every run; a repository upgrades by bumping the ref. `extends.path`
  points at a local checkout instead.
- **One prefix per layer**: org `JRFC-`, local e.g. `BOOK-`. Comments show which layer a rule
  comes from; org sources are GitHub permalinks at the pinned commit.
- **Add, never weaken**: `shall conflicts --local` compares each local statement with every org
  statement (one Jev request per pair: a Choice for the relation plus two Nouls, "does it
  permit what the org rule forbids?" and "would following it violate the org rule?").
  Duplicate / weakens / conflict ≥ `conflicts.fail_threshold` (0.75) fails CI. A local RFC
  cannot supersede an org RFC. There are no waivers: a rule that should not apply to a
  repository is changed upstream by the domain owner.
- **Settings** (`jev`, `selection`, `conflicts`, `review`, `codegraph`) are inherited from the
  org `shall.yaml` and may be overridden locally.

## This repository applies its own standards

This repository is both an organisation corpus (root `shall.yaml`, `JRFC-`) and a consumer of
it: `.shall/` extends `path: ..` and adds `JTOOL-` rules for the tooling itself.

| RFC | Rules |
| --- | --- |
| JTOOL-0001 Using Jev | only through `shall.jev.Jev`; small state, no `existing[i]` indirection; gate on Nouls or summed failing classes; pinned model ids |
| JTOOL-0002 Agent boundaries | reviewer runs without tools; agent output validated before use; external writes deterministic with `--dry-run`; blocking from corpus + verification, only lowered by agents; blocking needs seen evidence |
| JTOOL-0003 CLI contract | exit codes 0/1/2/3; deterministic commands never call a model; reproducible generated files |
| JTOOL-0004 Plugin content (approved) | descriptions say when to use; one reviewer prompt; commands in skills exist |

At the root, plain `shall` resolves to `.shall/` (a note is printed); organisation corpus
commands use `--config shall.yaml` (the Makefile does this).

## Hooks: standards on an agent's tool calls

`hooks.py` applies the corpus to Claude Code hook events while an agent works. In a review,
Jev only selects and Claude judges; a hook has no time for Claude, so **Jev is the judge**
and Claude only runs at the end of the turn.

```
PreToolUse   (Bash | Write | Edit | … | mcp__.*)
   ├─ code   secret scanner on the text the call writes (not `old_string`): a hit breaks
   │         the rule `hooks.secrets` maps to the tool (JRFC-0004.1 for writes, JRFC-0012.4 else)
   ├─ code   `Pattern:` of `Enforcement: linter` tool statements, searched in the command with
   │         quoted strings masked: a match is p = 1 (force push, skipped git hooks, TLS off)
   ├─ code   candidates: `tool` statements whose `Tools:` regex matches the tool name,
   │         `Enforcement: agent`, RFC status with an action table
   ├─ Jev    one request: per candidate "does the call break it?" (criterion: `Violated when:`)
   │         and "is the call about it?"; p = min(both). State: tool, redacted input, cwd,
   │         git branch (a plain `git push` pushes the current branch)
   └─ code   action = hooks.actions[status][level] at p → deny | ask | warn (additionalContext) | log
PostToolUse  (Write | Edit | MultiEdit)
   ├─ code   the written lines, found in the file on disk, as a synthetic diff with 15 lines
   │         of context → the same chunk and prefilter (`Selector.eligible`) as a review
   ├─ Jev    one request per chunk: "do the added lines break it?" and "does it apply?"
   └─ code   warn at p ≥ hooks.code_warn, never deny: the lines are not evidence (JTOOL-0002.6)
Stop
   └─ shall review of the working tree (tracked diff + untracked files), once per distinct
      change and session; `decision: block` only for verified blocking findings, at most
      `stop.max_blocks` times per session
```

Why these choices:

- **Violation, not relevance.** The selection question ("is this relevant?") is right for
  choosing what the reviewer reads, but a hook must decide alone. Asking both questions in
  the same request costs no latency (one round trip whatever the number of questions) and
  keeps off-topic rules quiet: on 25 code writes, false positives at 0.5 fell from 40 to 12.
- **Regex where a regex is exact.** Flags such as `--force`, `-nm` or `curl -k` are
  mechanical (JRFC-0001.5): a pattern is instant and never unsure, while Jev scored
  `git commit -nm` 0.66 (an ask, not a deny). Quoted strings are masked first, so a commit
  message that mentions a flag is not a violation; a flag inside `bash -c "…"` is missed.
- **The level and the status decide, not the model.** Jev only gives a probability; the
  action comes from the corpus, as `blocking` does in a review (JTOOL-0002.5). The band
  0.5–0.9 of an enforced MUST asks the user instead of denying.
- **Writes only warn.** On an `Edit` of `self.session.get(path)`, Jev said 0.91 that the
  timeout rule was broken; the timeout was set on the session 30 lines above. The agent has
  that context, so it gets the warning; the Stop review, which gathers evidence, can block.
- **Fail-open.** Jev gets `hooks.timeout` (3 s); past it or on an error the call runs and
  the decision log records `jev: timeout | error`. The answer still lands in the cache.
  `shall hook` exits 3 on a Jev error (JTOOL-0003.1), which Claude Code treats as a
  non-blocking error.
- **Redaction first.** The scanner replaces secrets with `[REDACTED:kind]` (line breaks kept)
  in everything sent to Jev or written to the log; Jev still sees that a credential was there.
- **Plugin wiring.** The plugin's `hooks/hooks.json` runs `bin/shall-hook`, a shell script
  that exits in a few milliseconds where no shall workspace exists, forwards to `shall hookd`
  when it serves the repository, and otherwise runs `shall hook`. `hooks.enabled: false`
  turns everything off in a workspace.
- **No hook loops.** The Stop review runs `claude -p` agents; were they to load the plugin,
  their own Stop would start another review. Agents run with `--setting-sources ""` and
  `SHALL_HOOKS_DISABLED=1` (the hooks answer nothing when it is set), and a lock per change
  (`stop-running-<sha>`) skips a second review of the same change from another session.
- **Warm connection.** A new process per call costs ~0.5 s (Python start, TLS handshake);
  `shall hookd` keeps one `Jev` (and its HTTP connection) for its lifetime: ~0.3 s per call,
  ~20 ms on a cache hit. It binds 127.0.0.1, answers only `application/json` POSTs (a
  browser cannot send one cross-origin without a preflight) and, with `SHALL_HOOK_TOKEN`,
  requires a bearer token.

## Scan: whole files, the hook's judgment

`shall scan` (`scan.py`) lists files with `git ls-files` (tracked and untracked, not ignored)
or a directory walk, keeps known code and config languages (not Markdown), and applies
`scan.exclude` and `scan.max_file_chars`. Per file: the secret scanner on the raw text (exact;
a hit on an enforced MUST is the only blocking finding), then the whole file, redacted, as one
added-lines chunk through `Hooks.judge_code`, the loop the post-write hook uses: prefilter,
one Jev request, p = min(applies, violates), a warning at p >= `scan.threshold` (0.7). Jev
failures are listed and exit 3 instead of failing open: a scan that silently skipped files
would read as clean. `eval/scan` measured this path on 100 files before the command existed;
its hill-climb changed only rule criteria (`applies_when`, `Violated when:`), not code.

## Known pain points and how they are handled

| Pain point | Handling |
| --- | --- |
| Agents deciding standards | Agents only draft (`status: draft`); promotion is an owner decision (JRFC-0001.4, CI notice) |
| Unstable statement ids | Ids are in the source; `lint --against` fails on silent removal; `retired:` list |
| Duplicates / conflicts | `shall conflicts`: one Jev request per statement pair |
| Rot | `owner` + `review_by` required; lint warns when overdue |
| Mechanical rules via AI | `Enforcement: linter` statements are never sent to Jev or the agent |
| Index needs an agent | No: `shall build` is deterministic; semantic text lives in the reviewed source |
| Jev is not an embedding model | One **Noul per candidate** (absolute, multi-label), not Choice-as-similarity |
| Size limits (32k/64k tokens) | Chunking + automatic request packing under the token budget |
| Literal reading | `applies_when` / `not_applies_when` per domain, RFC and statement |
| Facts not in the text | `effects.yaml` + code graph add `known_effects` to the Jev state and the reviewer prompt |
| Applicability ≠ violation | Jev selects, the agent judges violation, code validates |
| Prompt injection | Strict criteria; the reviewer prompt treats content as data; tested (case 08) |
| Noise | Blocking recomputed from corpus, comment cap, dedupe, advisory for SHOULD/approved |
| Hallucinated lines / ids | Findings dropped unless the statement was selected for that chunk and the line is changed |
| Unstable reruns | Jev answer cache; pinned model; `shall publish` dedupes comments by content key |
| Repo-specific rules | Local `.shall/` layer with its own prefix, pinned `extends:`, `conflicts --local` gate |
| Reviewer sees one file | Verification of blocking findings against repository evidence |
| Silent failures | `health.json` + summary warnings |
| Noise from other AI reviewers | `shall triage`: Jev (actionable, covering rule, duplicate) + verifier with repository evidence; noise only with a reason |
| Service outages | Jev failures exit 3 (not 2), so CI can tell "service down" from "change blocked" |
| Code leaves the company | **Open.** Diffs go to TypeSafe and Anthropic: get data-protection approval first |
