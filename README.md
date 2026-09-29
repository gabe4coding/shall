# jrfc — engineering standards that agents can apply

jrfc keeps your engineering standards as short [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119)
rules ("Every outbound call MUST set a timeout") and checks work against them: pull
requests, design specs, documents, or a task an agent is about to start.

- **Humans** write and own the standards as Markdown files, reviewed like code.
- **[Jev](https://docs.typesafe.ai)** (TypeSafe) decides which rules apply to each file of a
  change, with a calibrated probability per rule.
- **Claude** reviews the change against only those rules and writes inline comments.
- **Deterministic code** validates every comment, checks blocking findings against the rest
  of the repository, and posts to the pull request.

Inspired by Cloudflare's [engineering standards enforcement](https://blog.cloudflare.com/engineering-standards-enforcement/).
Status: **proof of concept** — see [what is measured](docs/results.md) and [known limits](#known-limits).

```
pull request ─► split per file ─► rules that apply (Jev) ─► review (Claude, no tools)
             ─► validate + verify against the repo (code) ─► PR comments + exit code
```

How it works in detail: [docs/architecture.md](docs/architecture.md).

---

## Contents

1. [Prerequisites](#prerequisites)
2. [Try it in 5 minutes](#try-it-in-5-minutes)
3. [Install the Claude Code plugin](#install-the-claude-code-plugin)
4. [Use it in your repository](#use-it-in-your-repository)
5. [Run it in CI on pull requests](#run-it-in-ci-on-pull-requests)
6. [Write and maintain standards](#write-and-maintain-standards)
7. [Create your organisation's corpus](#create-your-organisations-corpus)
8. [Configuration](#configuration)
9. [Commands](#commands)
10. [Outputs and exit codes](#outputs-and-exit-codes)
11. [Evaluate changes to jrfc](#evaluate-changes-to-jrfc)
12. [Repository layout](#repository-layout)
13. [Known limits](#known-limits)

---

## Prerequisites

| Tool | Needed for | Get it |
| --- | --- | --- |
| `git`, `make` | everything | your OS package manager |
| [`uv`](https://docs.astral.sh/uv/) | running the `jrfc` CLI (it installs Python 3.11+ and the dependencies itself) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `TYPESAFE_API_KEY` | choosing which rules apply (Jev) | an API key from [typesafe.ai](https://docs.typesafe.ai) |
| [Claude Code](https://docs.claude.com/en/docs/claude-code) (`claude`) | the review itself | `npm install -g @anthropic-ai/claude-code`, then log in (or set `ANTHROPIC_API_KEY`) |
| [`gh`](https://cli.github.com/) | posting comments to GitHub pull requests | `gh auth login` |

Commands that only read or build the corpus (`lint`, `build`, `list`, `show`, `new`) need
no key and make no network call.

> **Data:** a review sends the diff to TypeSafe (rule selection) and Anthropic (review).
> Check that this is allowed for your code before you run it on private repositories.

## Try it in 5 minutes

```bash
git clone https://github.com/gabe4coding/jrfc.git
cd jrfc
make check                                  # lint the example corpus and check its index (no key needed)
make test                                   # unit tests (no network)
```

Add the CLI to your shell (or install the plugin, next section):

```bash
export PATH="$PWD/plugins/jrfc/bin:$PATH"
export TYPESAFE_API_KEY=...                 # needed from here on
```

Which rules apply to a change? (Jev, about 2 seconds)

```bash
jrfc --config jrfc.yaml select eval/cases/01-booking-endpoint.diff
jrfc --config jrfc.yaml select --text "add an endpoint to refund a payment"
```

Full review of a sample pull request (Jev + Claude, about a minute):

```bash
jrfc --config jrfc.yaml review eval/cases/01-booking-endpoint.diff --out-dir .jrfc-out/demo
cat .jrfc-out/demo/review.md
```

`--config jrfc.yaml` selects the example organisation corpus at the root of this
repository; without it, `jrfc` uses this repository's own rules in `.jrfc/`.

## Install the Claude Code plugin

The plugin gives Claude Code the `jrfc` command, the reviewer and verifier agents, and four
skills:

| Skill | Claude uses it when you… |
| --- | --- |
| `jrfc-standards` | start work in a repository with jrfc: it finds the rules that apply before coding |
| `jrfc-review` | ask "check this PR / spec against our standards" |
| `jrfc-author` | ask to write, change, split or retire a standard |
| `jrfc-index` | change the corpus and the index must be rebuilt |

```bash
claude plugin marketplace add gabe4coding/jrfc     # or a local path to a clone
claude plugin install jrfc@jrfc
```

The repository is private: the machine needs git access to it (for example `gh auth login`).

## Use it in your repository

### A. Only the organisation's rules

Point jrfc at the organisation corpus, pinned to a tag or commit, and review from the root
of your repository:

```bash
export JRFC_EXTENDS=your-org/engineering-standards@v2026.09   # owner/name@ref, or a local path
export JRFC_GIT_TOKEN=...                                      # only if that repository is private
git diff origin/main...HEAD > /tmp/pr.diff
jrfc review /tmp/pr.diff --out-dir .jrfc-out/pr
```

To try it with the example corpus in this repository, use `JRFC_EXTENDS=gabe4coding/jrfc@main`.

### B. Organisation rules plus your repository's own rules

```bash
jrfc init --prefix BOOK --repo your-org/engineering-standards --ref v2026.09
jrfc fetch                                    # download the pinned corpus into ~/.cache/jrfc
jrfc new --domain api --title "Booking events carry a schema version"
$EDITOR .jrfc/rfcs/BOOK-0001-*.md             # write the rule (see "Write and maintain standards")
jrfc lint && jrfc build                       # check the file, regenerate .jrfc/index/
jrfc conflicts --local                        # your rules must not duplicate, weaken or contradict org rules
git add .jrfc && git commit -m "Add BOOK-0001"
```

Rules:
- your rules use your own prefix (`BOOK-`), and may only **add or tighten** requirements;
- a rule that should not apply to your repository is changed in the organisation corpus by
  its owner. There are no local waivers;
- to take new organisation rules, bump `extends.ref` in `.jrfc/jrfc.yaml` and run
  `jrfc fetch --update`.

A complete example is in [`examples/booking-service/.jrfc/`](examples/booking-service/.jrfc/).

### C. Before you write code (agents)

With the plugin installed, Claude Code uses the `jrfc-standards` skill on its own. Without
the plugin:

```bash
jrfc select --text "add a Kafka consumer for booking events"
jrfc show JRFC-0006.1
```

### D. While an agent works (Claude Code hooks)

Hooks apply the rules to each tool call an agent makes, as it makes it. Jev is the judge;
the rule's level and its RFC's status choose the action:

| When | What is checked | Possible actions | Time |
| --- | --- | --- | --- |
| before a Bash / MCP call | `tool` rules (e.g. [JRFC-0012](corpus/rfcs/JRFC-0012-agent-tool-use.md)) | deny · ask · warn | ~0.3 s |
| before a Write / Edit | secret scanner (code, not Jev) | deny | ~1 ms |
| after a Write / Edit | code rules on the written lines plus context | warn only | ~0.3 s |
| end of the agent's turn (Stop) | the whole change through `jrfc review` | block (verified findings only) | seconds; skipped when nothing changed |

Default actions (`hooks.actions`): an **enforced MUST** rule denies at p ≥ 0.9 and asks the
user at 0.5–0.9; an enforced SHOULD warns the agent at p ≥ 0.7; an **approved MUST** warns;
everything else is only logged. After a write nothing is denied: the lines just written are
not enough evidence (the timeout may be set in another file), so the agent gets a warning
it can check, and only the Stop review can block. Every input is redacted by the secret
scanner before it reaches Jev. If Jev is slow (`hooks.timeout`, 3 s) or down, the call
runs: the hooks fail open. Each decision is appended to `.jrfc-cache/hooks/decisions.jsonl`.

```bash
jrfc hookd &                                   # localhost server, keeps the Jev connection warm
jrfc hook-config > /tmp/jrfc-hooks.json        # the hooks block for .claude/settings.json
jrfc hook-config --transport command           # no server: one process per call (~0.5 s)
jrfc hook-config --no-stop                     # without the end-of-turn review
```

Merge the printed `hooks` block into `.claude/settings.json` (project) or
`~/.claude/settings.json`. `jrfc hookd` checks only events whose working directory is
inside its repository; run one per repository (`--port`), or use the command transport.
Set `JRFC_HOOK_TOKEN` before `hookd` and `hook-config` to require a bearer token.

The tool rules in JRFC-0012 are `draft`, so the defaults do not act on them. To try them
before the owner approves them, add a `draft` action table in your workspace:

```yaml
# .jrfc/jrfc.yaml
hooks:
  actions:
    draft: {MUST: [[0.9, deny], [0.5, ask]], SHOULD: [[0.7, warn]], MAY: [[0.7, log]]}
```

A `tool` rule names the tools it covers with `Tools:` (a regular expression on the tool
name, full match) and can describe a violating call with `Violated when:` (the Jev
criterion). Rules with `Enforcement: linter` are left to code: JRFC-0012.4 and JRFC-0004.1
are enforced by the secret scanner (`hooks.secrets` maps a tool to the rule it breaks).

## Run it in CI on pull requests

1. Copy [`ci/github/jrfc-review.yml`](ci/github/jrfc-review.yml) to `.github/workflows/` in your
   repository.
2. Edit the lines marked `TODO`: the tooling repository and ref, and `JRFC_EXTENDS` if your
   repository has no `.jrfc/`.
3. Add repository secrets:

   | Secret | Why |
   | --- | --- |
   | `TYPESAFE_API_KEY` | rule selection (Jev) |
   | `ANTHROPIC_API_KEY` | the review (`claude -p`) |
   | `JRFC_GIT_TOKEN` | read access to the tooling and corpus repositories, if they are private |

4. Open a pull request. The job posts inline comments and one summary comment, and uploads
   `.jrfc-out/pr` as an artifact.
5. To block merges on enforced rules, make the `jrfc / review` job a **required check**: it
   exits 2 when a blocking finding remains after verification.

Other CI systems: run `plugins/jrfc/bin/jrfc-pr-review --base origin/main --post <PR number>
--fail-on-blocking` from the repository root (see the header of that script). Posting uses
`gh`; add `--dry-run` to see what would be posted without writing.

Re-running on every push is safe and cheap:

- comments are keyed by rule and line content, so the same finding is not posted twice, a
  fixed line resolves its thread, and threads a person resolved stay resolved;
- only files whose diff, applicable rules or known effects changed are reviewed again, and a
  blocking finding is only re-checked when its evidence changed. Earlier answers are kept in
  `.jrfc-cache/review.json`, which the workflow caches per pull request. A push that changes
  one file of a two-file PR cost $0.15 instead of $0.39; re-running an unchanged push cost $0.

### Triage the comments of other AI reviewers

Copilot, CodeRabbit and similar bots leave many comments on a pull request. A few point to
real problems; the rest is noise: praise, summaries, nits, optional extras, the same concern
twice, or a claim that code in another file already refutes. `jrfc triage` sorts the open
comments of these bots with the same method as the review:

1. **Code** keeps open threads started by a bot (GitHub type `Bot` or a login in
   `triage.authors`) and sets aside comments whose code changed since (outdated).
2. **Jev** selects the rules that apply to the commented file (the same questions as the
   review), then asks per comment: does it name a concrete problem in this code? which of
   those rules covers it? does it repeat a jrfc finding or an earlier comment on nearby lines?
3. **An agent** without tools checks each remaining claim against evidence from the repository
   (the same code graph and search as verification): confirmed, refuted or unknown.
4. **Code** decides: *relevant* (confirmed), *unverified* (not decided: kept), *noise* (not
   actionable, duplicate, or refuted with cited evidence) or *outdated*, always with the reason.

```bash
gh pr diff 123 > /tmp/pr.diff
jrfc triage /tmp/pr.diff --pr 123 --findings .jrfc-out/pr/findings.json   # reads the PR, writes nothing
jrfc triage /tmp/pr.diff --comments threads.json                         # offline, from a file
```

It writes `triage.md` and `triage.json`. In CI, `jrfc-pr-review --post N --triage` adds the
triage to the summary comment; `--resolve-noise` also replies to each noise thread with the
reason and resolves it. A thread that a person answered, resolved or reopened is never
touched, and a triaged comment never blocks a merge. Cost: about $0.01–0.02 per bot comment
that reaches the agent; not-actionable comments and duplicates cost only Jev.

### What it costs

Estimated per review run, from measured unit costs (Claude review ≈ $0.01–0.08 per changed
file where a rule applies, verification ≈ $0.015 per blocking finding, Jev < $0.003 per file):

| Pull request | Files reviewed | First run | Later pushes |
| --- | --- | --- | --- |
| small | 1–3 | ~$0.05–0.15 | only the files that changed |
| medium | 5–10 | ~$0.30–0.60 | only the files that changed |
| big | 20–40 | ~$1.20–2.50 | only the files that changed |

Files with no applicable rule (styles, typos in docs) are not sent to Claude.

## Write and maintain standards

A standard is one Markdown file per RFC with numbered statements. The shortest useful example:

```markdown
---
id: JRFC-0006
title: Resilient outbound calls
status: approved            # draft → approved (advisory) → enforced (MUST blocks) → deprecated
domain: reliability
artifacts: [diff, code, spec]
languages: [any]
owner: sre
review_by: 2027-03-31
supersedes: []
summary: Timeouts, retries and fallbacks for calls to other services.
applies_when: The content makes, configures or describes an outbound network call.
not_applies_when: No outbound network call is made, configured or described.
---

# JRFC-0006: Resilient outbound calls

## Requirements

### JRFC-0006.1 Explicit timeouts
Every outbound network call MUST set an explicit timeout.

- Applies when: the content performs an HTTP request or RPC, or creates a client for another service.
- Enforcement: agent
```

Rules for writing statements that work:

- **One level per statement**: MUST, SHOULD or MAY, never two. Keywords only in UPPERCASE.
- **Write `Applies when:` literally.** Jev reads it word by word: name the code or text it is
  about ("performs an HTTP request"), not the intent ("resilience matters").
- **Mechanical rules go to linters**: mark them `Enforcement: linter`; jrfc never sends them
  to a model.
- **Never renumber or reuse an id.** To change a meaning, add a new statement and list the old
  id under `retired:`.
- **Only the owner promotes status.** Agents may draft; `approved` and `enforced` need the
  domain owner's approval.

Workflow:

```bash
jrfc new --domain reliability --title "Idempotent retries"   # next free id, status: draft
jrfc lint                                  # format, levels, ids
jrfc conflicts corpus/rfcs/JRFC-0012-*.md  # duplicates / conflicts with existing rules (Jev)
jrfc build                                 # regenerate the index (commit it)
```

With the plugin, ask Claude ("write a standard for idempotent retries"); the `jrfc-author`
skill follows these rules. Full format: [JRFC-0001](corpus/rfcs/JRFC-0001-rfc-format.md).

### Known effects

A rule about network calls, databases or processes only applies when jrfc can see that the
code does that. If a library hides it (`get_parser(lang)` downloads a file,
`db.Query(...)` goes to the network), add an entry to `effects.yaml` instead of widening the
rule:

```yaml
- id: go-database-sql
  module: database/sql                 # import spec, prefix match
  calls: [Open]                        # called through the import: sql.Open(...)
  methods: [Query, QueryRow, Exec]     # called on a value from the module: db.Query(...)
  effect: runs a query on a remote database over the network
  owner: data-platform
```

jrfc also follows calls through your repository (3 hops), so a wrapper around `requests`
two files away is found too. See [`corpus/effects.yaml`](corpus/effects.yaml) for 30+ entries.

## Create your organisation's corpus

The corpus in this repository is an example. For your organisation:

1. Create a repository (for example `your-org/engineering-standards`) with:

   ```
   jrfc.yaml               # prefix: JRFC, paths, pinned Jev model, thresholds (copy this repo's)
   corpus/domains.yaml     # your areas: api, security, reliability, ... (title, owner, applies_when)
   corpus/rfcs/            # your standards
   corpus/effects.yaml     # optional: known effects of the libraries you use
   corpus/index/           # generated by `jrfc build`, committed
   ```

2. Give each domain an owner, and add a `CODEOWNERS` rule so the owner approves changes.
3. Copy [`ci/github/jrfc-corpus.yml`](ci/github/jrfc-corpus.yml): it runs lint, the index
   check and id stability on every pull request, with no model call.
4. Tag releases (`v2026.09`) and let application repositories pin a tag in `extends.ref`.
5. Test that your rules are selected where they should be: add cases to `eval/` and run
   `jrfc eval` (see below).

## Configuration

Settings live in `jrfc.yaml` (organisation) and can be overridden in `.jrfc/jrfc.yaml`
(repository). The main ones:

| Setting | Default | Meaning |
| --- | --- | --- |
| `jev.model` | `jev-1.13.0` | pinned Jev model; thresholds are tuned for it |
| `jev.max_chunk_chars` | `40000` | largest piece of a file sent at once |
| `selection.strategy` | `flat` | `flat` asks every rule; `layered` asks domain → RFC → rule (cheaper, loses recall on large corpora) |
| `selection.thresholds.statement` | `0.50` | a rule applies at or above this probability |
| `selection.include_status` | `[approved, enforced]` | lifecycle states used in reviews (`--include-draft` adds drafts) |
| `selection.facts` | `true` | add known effects to Jev's input and the review |
| `review.model` | `claude-sonnet-5` | reviewer and verifier model |
| `review.verify` | `true` | verify blocking findings against the repository before they block |
| `review.cache` | `true` | reuse Claude's answer when its input is identical (incremental re-review); `--no-cache` forces new calls |
| `review.max_comments` | `25` | cap on comments per review |
| `conflicts.fail_threshold` | `0.75` | `conflicts --local` fails at or above this |
| `codegraph.download_grammars` | `true` | `false`: never download parser grammars during a run (run `jrfc prefetch` first) |
| `triage.authors` | Copilot, CodeRabbit, `*[bot]`… | logins whose comments `jrfc triage` sorts (`*` is the only wildcard); GitHub Apps always count |
| `triage.thresholds` | `actionable 0.5, statement 0.5, duplicate 0.7` | a comment below `actionable` is noise; `duplicate` marks a repeated concern |
| `triage.verify` | `true` | check each actionable comment against repository evidence (`--no-verify` skips it) |
| `hooks.actions` | see [hooks](#d-while-an-agent-works-claude-code-hooks) | status → level → `[[min p, action]]`; a status without a table is not checked |
| `hooks.code_warn` | `0.7` | after a write, warn at or above this (never deny) |
| `hooks.timeout` | `3.0` | seconds for Jev in a hook; past it the call runs (fail-open) |
| `hooks.pre_matcher` / `hooks.code_tools` | `Bash\|Write\|Edit\|…\|mcp__.*` / `Write\|Edit\|MultiEdit\|NotebookEdit` | tools checked before / after the call |
| `hooks.stop` | `enabled, max_blocks 2` | end-of-turn review; blocks at most twice per session |

Environment variables: `TYPESAFE_API_KEY`, `ANTHROPIC_API_KEY` (CI), `JRFC_CONFIG`,
`JRFC_EXTENDS`, `JRFC_GIT_TOKEN`, `JRFC_CACHE_DIR`.

## Commands

| Command | Calls a model? | Purpose |
| --- | --- | --- |
| `jrfc lint [--against base-index.json]` | no | check files, levels, ids and id stability |
| `jrfc build [--check]` | no | regenerate the index; `--check` fails when it is stale |
| `jrfc list`, `jrfc show ID…` | no | browse rules |
| `jrfc new --domain D --title T` | no | new draft with the next free id |
| `jrfc init --prefix P --repo R --ref T` | no | create `.jrfc/` in a repository |
| `jrfc fetch [--update]` | no (git) | download the pinned organisation corpus |
| `jrfc prefetch` | no (download) | download parser grammars for the repository's languages (CI) |
| `jrfc select PATH \| --text T` | Jev | which rules apply, with probabilities |
| `jrfc review PATH` | Jev + Claude | select → review → validate → verify → reports |
| `jrfc publish --pr N [--dry-run] [--resolve-noise]` | no | post a review to a GitHub pull request; with `triage.json`, add the triage and optionally resolve noise threads |
| `jrfc triage DIFF --pr N \| --comments F` | Jev + Claude | sort other AI reviewers' comments: relevant, unverified, noise, outdated |
| `jrfc conflicts FILE` / `--local` | Jev | duplicates, weakening and conflicts between rules |
| `jrfc bundle`, `validate`, `verify` | varies | the review in separate steps (used by the `jrfc-review` skill) |
| `jrfc hook` | Jev (+ Claude on Stop) | handle one Claude Code hook event from stdin (command hook) |
| `jrfc hookd [--port P]` | Jev (+ Claude on Stop) | serve hook events on localhost for `type: http` hooks |
| `jrfc hook-config [--transport http\|command] [--no-stop]` | no | print the `hooks` block for `.claude/settings.json` |
| `jrfc eval`, `jrfc eval-verify`, `jrfc eval-triage`, `jrfc eval-hooks` | Jev (+ Claude) | measure selection, verification, triage and the hook judge on labelled cases |

`jrfc <command> --help` shows every option.

## Outputs and exit codes

`jrfc review --out-dir DIR` writes:

| File | Content |
| --- | --- |
| `review.md` | human summary: findings, applicable rules, health line |
| `findings.json` | validated findings and the ones dropped (with the reason) |
| `selection.json` | every rule's probability per file chunk, and the known effects |
| `github-review.json` | payload for `jrfc publish` (`--format github`) |
| `health.json` | what could have gone wrong silently: failed calls, unverified blocking findings, files not parsed, rules just below the threshold |
| `prompts/` | the exact prompt sent to the reviewer per chunk |

`jrfc triage` writes `triage.md` (relevant and unverified comments first, noise folded) and
`triage.json` (every comment with its status, reason, scores, matched rules and the evidence
the verifier cited). `jrfc publish --resolve-noise` writes `triage-plan.json`.

| Exit code | Meaning |
| --- | --- |
| 0 | done, no blocking finding (or `--fail-on-blocking` not set) |
| 1 | error (configuration, tooling, a failed review call) |
| 2 | blocking findings (an enforced MUST rule, verified) |
| 3 | the Jev service failed after retries: retry the job, do not treat it as a code problem |

## Evaluate changes to jrfc

Before changing thresholds, prompts, rules' wording or the tooling, compare before and after:

```bash
make test          # unit tests, no network
make check         # corpus lint + index
make eval          # selection on 11 cases (needs TYPESAFE_API_KEY)
make eval-scale    # selection with ~540 rules, 20 cases
make eval-facts    # known effects on vs off, 19 files in 9 languages
plugins/jrfc/bin/jrfc --config jrfc.yaml eval-verify --retrieval treesitter   # verification (needs claude)
make eval-triage   # triage of AI review comments, 24 labelled comments (needs claude)
make eval-hooks    # hook judge on 75 labelled tool calls and writes (--no-cache for latency)
```

Jev answers are cached in `.jrfc-cache/`, so re-runs only pay for changed questions. Current
numbers and what they mean: [docs/results.md](docs/results.md).

## Repository layout

| Path | What |
| --- | --- |
| `corpus/` | example organisation corpus: `rfcs/`, `domains.yaml`, `effects.yaml`, generated `index/` |
| `jrfc.yaml` | configuration of the example organisation corpus |
| `plugins/jrfc/` | the Claude Code plugin: skills, agents, `bin/jrfc`, `bin/jrfc-pr-review` |
| `plugins/jrfc/tooling/` | the Python package behind the CLI (`uv` project, tests) |
| `ci/github/` | workflow templates for the corpus repository and for application repositories |
| `examples/booking-service/.jrfc/` | an application repository's local rules (`BOOK-`) |
| `.jrfc/` | this repository's own rules for its tooling (`JTOOL-`) |
| `eval/` | labelled cases: `cases/`, `scale/`, `facts/` (selection), `verify/` (verification), `triage/` (AI review comments), `hooks/` (tool calls and writes) |
| `docs/` | [architecture](docs/architecture.md), [results](docs/results.md) |

## Known limits

- **Proof of concept.** Measured on cases written for it, not on real pull requests.
- **Recall is not perfect.** On hard cases about 1 in 4 applicable rules is not selected;
  `health.json` lists rules that scored just below the threshold.
- **The code graph resolves by imports and names, not types.** Dependency injection,
  reflection and clients configured in YAML or environment variables are not followed.
- **Only blocking findings are verified.** Advisory comments are not checked against the
  rest of the repository.
- **Triage sees bots' comments when the job runs.** A bot that comments after the jrfc job is
  triaged on the next push. Only inline review threads are read, not PR-level comments.
- **Two external services.** An outage fails the job with exit 3.
- **Data leaves your machine.** Diffs are sent to TypeSafe and Anthropic.
- **Hooks see one call at a time.** A violation split over several calls (write a script,
  then run it) is judged per call; the Stop review sees the resulting files, not the
  commands. After a write, Jev judges the written lines plus 15 lines of context only.
