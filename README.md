# shall — engineering standards that agents can apply

shall keeps your engineering standards as short [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119)
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
11. [Evaluate changes to shall](#evaluate-changes-to-shall)
12. [Repository layout](#repository-layout)
13. [Known limits](#known-limits)

---

## Prerequisites

| Tool | Needed for | Get it |
| --- | --- | --- |
| `git`, `make` | everything | your OS package manager |
| [`uv`](https://docs.astral.sh/uv/) | running the `shall` CLI (it installs Python 3.11+ and the dependencies itself) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `TYPESAFE_API_KEY` | choosing which rules apply (Jev) | an API key from [typesafe.ai](https://docs.typesafe.ai) |
| [Claude Code](https://docs.claude.com/en/docs/claude-code) (`claude`) | the review itself | `npm install -g @anthropic-ai/claude-code`, then log in (or set `ANTHROPIC_API_KEY`) |
| [`gh`](https://cli.github.com/) | posting comments to GitHub pull requests | `gh auth login` |

Commands that only read or build the corpus (`lint`, `build`, `list`, `show`, `new`) need
no key and make no network call.

> **Data:** a review sends the diff to TypeSafe (rule selection) and Anthropic (review).
> Check that this is allowed for your code before you run it on private repositories.

## Try it in 5 minutes

```bash
git clone https://github.com/gabe4coding/shall.git
cd shall
make check                                  # lint the example corpus and check its index (no key needed)
make test                                   # unit tests (no network)
```

Add the CLI to your shell (or install the plugin, next section):

```bash
export PATH="$PWD/plugins/shall/bin:$PATH"
export TYPESAFE_API_KEY=...                 # needed from here on
```

Which rules apply to a change? (Jev, about 2 seconds)

```bash
shall --config shall.yaml select eval/cases/01-booking-endpoint.diff
shall --config shall.yaml select --text "add an endpoint to refund a payment"
```

Full review of a sample pull request (Jev + Claude, about a minute):

```bash
shall --config shall.yaml review eval/cases/01-booking-endpoint.diff --out-dir .shall-out/demo
cat .shall-out/demo/review.md
```

`--config shall.yaml` selects the example organisation corpus at the root of this
repository; without it, `shall` uses this repository's own rules in `.shall/`.

## Install the Claude Code plugin

The plugin gives Claude Code the `shall` command, the reviewer and verifier agents, the
[hooks](#d-while-an-agent-works-claude-code-hooks) that check an agent's tool calls in
repositories with a shall workspace, and four skills:

| Skill | Claude uses it when you… |
| --- | --- |
| `shall-standards` | start work in a repository with shall: it finds the rules that apply before coding |
| `shall-review` | ask "check this PR / spec against our standards" |
| `shall-author` | ask to write, change, split or retire a standard |
| `shall-index` | change the corpus and the index must be rebuilt |

```bash
claude plugin marketplace add gabe4coding/shall     # or a local path to a clone
claude plugin install shall@shall
```

The repository is private: the machine needs git access to it (for example `gh auth login`).

## Use it in your repository

### A. Only the organisation's rules

Point shall at the organisation corpus, pinned to a tag or commit, and review from the root
of your repository:

```bash
export SHALL_EXTENDS=your-org/engineering-standards@v2026.09   # owner/name@ref, or a local path
export SHALL_GIT_TOKEN=...                                      # only if that repository is private
git diff origin/main...HEAD > /tmp/pr.diff
shall review /tmp/pr.diff --out-dir .shall-out/pr
```

To try it with the example corpus in this repository, use `SHALL_EXTENDS=gabe4coding/shall@main`.

### B. Organisation rules plus your repository's own rules

```bash
shall init --prefix BOOK --repo your-org/engineering-standards --ref v2026.09
shall fetch                                    # download the pinned corpus into ~/.cache/shall
shall new --domain api --title "Booking events carry a schema version"
$EDITOR .shall/rfcs/BOOK-0001-*.md             # write the rule (see "Write and maintain standards")
shall lint && shall build                       # check the file, regenerate .shall/index/
shall conflicts --local                        # your rules must not duplicate, weaken or contradict org rules
git add .shall && git commit -m "Add BOOK-0001"
```

Rules:
- your rules use your own prefix (`BOOK-`), and may only **add or tighten** requirements;
- a rule that should not apply to your repository is changed in the organisation corpus by
  its owner. There are no local waivers;
- to take new organisation rules, bump `extends.ref` in `.shall/shall.yaml` and run
  `shall fetch --update`.

A complete example is in [`examples/booking-service/.shall/`](examples/booking-service/.shall/).

### C. Before you write code (agents)

With the plugin installed, Claude Code uses the `shall-standards` skill on its own. Without
the plugin:

```bash
shall select --text "add a Kafka consumer for booking events"
shall show JRFC-0006.1
```

### D. While an agent works (Claude Code hooks)

Hooks apply the rules to each tool call an agent makes, as it makes it. Jev is the judge;
the rule's level and its RFC's status choose the action:

| When | What is checked | Possible actions | Time |
| --- | --- | --- | --- |
| before a Bash / MCP call | `tool` rules ([JRFC-0012](corpus/rfcs/JRFC-0012-agent-tool-use.md)): regex patterns, then Jev | deny · ask · warn | ~0.3 s |
| before a Write / Edit | secret scanner (code, not Jev) | deny | ~1 ms |
| after a Write / Edit | code rules on the written lines plus context | warn only | ~0.3 s |
| end of the agent's turn (Stop) | the whole change through `shall review` | block (verified findings only) | seconds; skipped when nothing changed |

Default actions (`hooks.actions`): an **enforced MUST** rule denies at p ≥ 0.9 and asks the
user at 0.5–0.9; an enforced SHOULD warns the agent at p ≥ 0.7; an **approved MUST** warns;
everything else is only logged. After a write nothing is denied: the lines just written are
not enough evidence (the timeout may be set in another file), so the agent gets a warning
it can check, and only the Stop review can block. Every input is redacted by the secret
scanner before it reaches Jev. If Jev is slow (`hooks.timeout`, 3 s) or down, the call
runs: the hooks fail open. Each decision is appended to `.shall-cache/hooks/decisions.jsonl`.

**With the plugin** the hooks are on: `hooks/hooks.json` calls `bin/shall-hook` for every
event. Outside a shall workspace (no `.shall/shall.yaml` or `shall.yaml` up the tree, no
`SHALL_CONFIG`, `SHALL_EXTENDS` or `~/.config/shall/config.yaml`) it exits in a few
milliseconds. Inside one it sends the event to `shall hookd` when one runs for that
repository (~0.3 s per call), and otherwise runs `shall hook` (~0.5 s per call):

```bash
shall hookd &                  # optional: keeps the Jev connection warm (port: hooks.port, 8765)
```

Turn the hooks off in a workspace with `hooks: {enabled: false}`, or only the end-of-turn
review with `hooks: {stop: {enabled: false}}` (it runs `shall review`, with Claude, when the
change is new). Without `TYPESAFE_API_KEY` only the secret scanner runs.

**Without the plugin**, print a settings block and merge it into `.claude/settings.json`
(project) or `~/.claude/settings.json`. Do not use both, or every hook runs twice.

```bash
shall hook-config                      # http hooks to `shall hookd` (start it yourself)
shall hook-config --transport command  # no server: one process per call
shall hook-config --no-stop            # without the end-of-turn review
```

`shall hookd` checks only events whose working directory is inside its repository (others
get 421); run one per repository with `--port` (`SHALL_HOOKD_PORT` for the plugin). Set
`SHALL_HOOK_TOKEN` before `hookd` and the hooks to require a bearer token.

The tool rules are in [JRFC-0012](corpus/rfcs/JRFC-0012-agent-tool-use.md) (`enforced`).
A `tool` rule names the tools it covers with `Tools:` (a regular expression on the tool
name, full match). Rules that code can check exactly have `Enforcement: linter`:

- with a `Pattern:` — a regular expression searched in the command, with quoted strings
  masked so a commit message that mentions `--no-verify` does not match (JRFC-0012.2 force
  push, .3 skipped git hooks, .8 TLS verification off). No Jev call; a match counts as p = 1;
- through the secret scanner — JRFC-0012.4 and JRFC-0004.1 (`hooks.secrets` maps a tool to
  the rule a hit breaks).

The other rules are judged by Jev, with `Violated when:` as the criterion. To try a draft
RFC's tool rules before its owner approves them, add a `draft` action table in a workspace:

```yaml
# .shall/shall.yaml
hooks:
  actions:
    draft: {MUST: [[0.9, deny], [0.5, ask]], SHOULD: [[0.7, warn]], MAY: [[0.7, log]]}
```

### E. Lint existing code (`shall scan`)

`shall scan` applies the code rules to whole files, the way the post-write hook applies them
to written lines: the secret scanner on the raw text, then one Jev request per file (secrets
redacted) with p = min(applies, violates) for every eligible rule. No agent runs.

```bash
shall scan                          # the current folder: git-tracked and untracked, not ignored
shall scan src/ lib/client.py       # files or folders
shall scan --fail-on-blocking       # CI: exit 2 on a secret-scanner hit on an enforced MUST rule
shall scan --threshold 0.5          # more warnings (higher recall, more noise)
```

It prints one line per warning (`path[:line]: ID [level, p] title`) and writes `scan.md` and
`scan.json` to `--out-dir` (`.shall-out`). A Jev warning never blocks: one file is not
evidence, so check it against the code, or run `shall review` on the change for verified
findings. Only secret-scanner hits can block. Markdown documents, `scan.exclude` globs
(node_modules, dist, vendor, lock files, ...) and files over `scan.max_file_chars` are
skipped; statuses default to `selection.include_status` (`--status draft,approved,enforced`
to trial drafts). Answers are cached, so a second scan pays only for changed files.

Measured on 100 real files (`eval/scan`, [docs/results.md](docs/results.md)): ~$0.0005 and
~0.4 s per file (48 files in 5 s with 4 requests in flight); precision 0.96 and recall 0.72 at
p ≥ 0.7 on the held-out half, after the criteria fixes the eval found. Rules a linter can check
exactly (type hints, formatting) belong to a linter (`Enforcement: linter`), not to Jev.

## Run it in CI on pull requests

1. Copy [`ci/github/shall-review.yml`](ci/github/shall-review.yml) to `.github/workflows/` in your
   repository.
2. Edit the lines marked `TODO`: the tooling repository and ref, and `SHALL_EXTENDS` if your
   repository has no `.shall/`.
3. Add repository secrets:

   | Secret | Why |
   | --- | --- |
   | `TYPESAFE_API_KEY` | rule selection (Jev) |
   | `ANTHROPIC_API_KEY` | the review (`claude -p`) |
   | `SHALL_GIT_TOKEN` | read access to the tooling and corpus repositories, if they are private |

4. Open a pull request. The job posts inline comments and one summary comment, and uploads
   `.shall-out/pr` as an artifact.
5. To block merges on enforced rules, make the `shall / review` job a **required check**: it
   exits 2 when a blocking finding remains after verification.

Other CI systems: run `plugins/shall/bin/shall-pr-review --base origin/main --post <PR number>
--fail-on-blocking` from the repository root (see the header of that script). Posting uses
`gh`; add `--dry-run` to see what would be posted without writing.

Re-running on every push is safe and cheap:

- comments are keyed by rule and line content, so the same finding is not posted twice, a
  fixed line resolves its thread, and threads a person resolved stay resolved;
- only files whose diff, applicable rules or known effects changed are reviewed again, and a
  blocking finding is only re-checked when its evidence changed. Earlier answers are kept in
  `.shall-cache/review.json`, which the workflow caches per pull request. A push that changes
  one file of a two-file PR cost $0.15 instead of $0.39; re-running an unchanged push cost $0.

### Triage the comments of other AI reviewers

Copilot, CodeRabbit and similar bots leave many comments on a pull request. A few point to
real problems; the rest is noise: praise, summaries, nits, optional extras, the same concern
twice, or a claim that code in another file already refutes. `shall triage` sorts the open
comments of these bots with the same method as the review:

1. **Code** keeps open threads started by a bot (GitHub type `Bot` or a login in
   `triage.authors`) and sets aside comments whose code changed since (outdated).
2. **Jev** selects the rules that apply to the commented file (the same questions as the
   review), then asks per comment: does it name a concrete problem in this code? which of
   those rules covers it? does it repeat a shall finding or an earlier comment on nearby lines?
3. **An agent** without tools checks each remaining claim against evidence from the repository
   (the same code graph and search as verification): confirmed, refuted or unknown.
4. **Code** decides: *relevant* (confirmed), *unverified* (not decided: kept), *noise* (not
   actionable, duplicate, or refuted with cited evidence) or *outdated*, always with the reason.

```bash
gh pr diff 123 > /tmp/pr.diff
shall triage /tmp/pr.diff --pr 123 --findings .shall-out/pr/findings.json   # reads the PR, writes nothing
shall triage /tmp/pr.diff --comments threads.json                         # offline, from a file
```

It writes `triage.md` and `triage.json`. In CI, `shall-pr-review --post N --triage` adds the
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
- **Mechanical rules go to linters**: mark them `Enforcement: linter`; shall never sends them
  to a model.
- **Never renumber or reuse an id.** To change a meaning, add a new statement and list the old
  id under `retired:`.
- **Only the owner promotes status.** Agents may draft; `approved` and `enforced` need the
  domain owner's approval.

Workflow:

```bash
shall new --domain reliability --title "Idempotent retries"   # next free id, status: draft
shall lint                                  # format, levels, ids
shall conflicts corpus/rfcs/JRFC-0012-*.md  # duplicates / conflicts with existing rules (Jev)
shall build                                 # regenerate the index (commit it)
```

With the plugin, ask Claude ("write a standard for idempotent retries"); the `shall-author`
skill follows these rules. Full format: [JRFC-0001](corpus/rfcs/JRFC-0001-rfc-format.md).

### Known effects

A rule about network calls, databases or processes only applies when shall can see that the
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

shall also follows calls through your repository (3 hops), so a wrapper around `requests`
two files away is found too. See [`corpus/effects.yaml`](corpus/effects.yaml) for 30+ entries.

## Create your organisation's corpus

The corpus in this repository is an example. For your organisation:

1. Create a repository (for example `your-org/engineering-standards`) with:

   ```
   shall.yaml               # prefix: JRFC, paths, pinned Jev model, thresholds (copy this repo's)
   corpus/domains.yaml     # your areas: api, security, reliability, ... (title, owner, applies_when)
   corpus/rfcs/            # your standards
   corpus/effects.yaml     # optional: known effects of the libraries you use
   corpus/index/           # generated by `shall build`, committed
   ```

2. Give each domain an owner, and add a `CODEOWNERS` rule so the owner approves changes.
3. Copy [`ci/github/shall-corpus.yml`](ci/github/shall-corpus.yml): it runs lint, the index
   check and id stability on every pull request, with no model call.
4. Tag releases (`v2026.09`) and let application repositories pin a tag in `extends.ref`.
5. Test that your rules are selected where they should be: add cases to `eval/` and run
   `shall eval` (see below).

## Configuration

Settings live in `shall.yaml` (organisation) and can be overridden in `.shall/shall.yaml`
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
| `codegraph.download_grammars` | `true` | `false`: never download parser grammars during a run (run `shall prefetch` first) |
| `triage.authors` | Copilot, CodeRabbit, `*[bot]`… | logins whose comments `shall triage` sorts (`*` is the only wildcard); GitHub Apps always count |
| `triage.thresholds` | `actionable 0.5, statement 0.5, duplicate 0.7` | a comment below `actionable` is noise; `duplicate` marks a repeated concern |
| `triage.verify` | `true` | check each actionable comment against repository evidence (`--no-verify` skips it) |
| `hooks.enabled` | `true` | `false`: the hooks (also the plugin's) do nothing in this workspace |
| `hooks.actions` | see [hooks](#d-while-an-agent-works-claude-code-hooks) | status → level → `[[min p, action]]`; a status without a table is not checked |
| `hooks.code_warn` | `0.7` | after a write, warn at or above this (never deny) |
| `hooks.timeout` | `3.0` | seconds for Jev in a hook; past it the call runs (fail-open) |
| `hooks.pre_matcher` / `hooks.code_tools` | `Bash\|Write\|Edit\|…\|mcp__.*` / `Write\|Edit\|MultiEdit\|NotebookEdit` | tools checked before / after the call |
| `hooks.stop` | `enabled, max_blocks 2` | end-of-turn review; blocks at most twice per session |

Environment variables: `TYPESAFE_API_KEY`, `ANTHROPIC_API_KEY` (CI), `SHALL_CONFIG`,
`SHALL_EXTENDS`, `SHALL_GIT_TOKEN`, `SHALL_CACHE_DIR`; for hooks `SHALL_HOOKD_PORT`,
`SHALL_HOOK_TOKEN` and `SHALL_HOOKS_DISABLED` (set by shall for the agents it runs).

## Commands

| Command | Calls a model? | Purpose |
| --- | --- | --- |
| `shall lint [--against base-index.json]` | no | check files, levels, ids and id stability |
| `shall build [--check]` | no | regenerate the index; `--check` fails when it is stale |
| `shall list`, `shall show ID…` | no | browse rules |
| `shall new --domain D --title T` | no | new draft with the next free id |
| `shall init --prefix P --repo R --ref T` | no | create `.shall/` in a repository |
| `shall fetch [--update]` | no (git) | download the pinned organisation corpus |
| `shall prefetch` | no (download) | download parser grammars for the repository's languages (CI) |
| `shall select PATH \| --text T` | Jev | which rules apply, with probabilities |
| `shall review PATH` | Jev + Claude | select → review → validate → verify → reports |
| `shall scan [PATHS…]` | Jev | lint whole files: secret scanner + one Jev request per file; warnings, `scan.md` / `scan.json` |
| `shall publish --pr N [--dry-run] [--resolve-noise]` | no | post a review to a GitHub pull request; with `triage.json`, add the triage and optionally resolve noise threads |
| `shall triage DIFF --pr N \| --comments F` | Jev + Claude | sort other AI reviewers' comments: relevant, unverified, noise, outdated |
| `shall conflicts FILE` / `--local` | Jev | duplicates, weakening and conflicts between rules |
| `shall bundle`, `validate`, `verify` | varies | the review in separate steps (used by the `shall-review` skill) |
| `shall hook` | Jev (+ Claude on Stop) | handle one Claude Code hook event from stdin (command hook) |
| `shall hookd [--port P]` | Jev (+ Claude on Stop) | serve hook events on localhost for `type: http` hooks |
| `shall hook-config [--transport http\|command] [--no-stop]` | no | print the `hooks` block for `.claude/settings.json` |
| `shall eval`, `shall eval-verify`, `shall eval-triage`, `shall eval-hooks` | Jev (+ Claude) | measure selection, verification, triage and the hook judge on labelled cases |

`shall <command> --help` shows every option.

## Outputs and exit codes

`shall review --out-dir DIR` writes:

| File | Content |
| --- | --- |
| `review.md` | human summary: findings, applicable rules, health line |
| `findings.json` | validated findings and the ones dropped (with the reason) |
| `selection.json` | every rule's probability per file chunk, and the known effects |
| `github-review.json` | payload for `shall publish` (`--format github`) |
| `health.json` | what could have gone wrong silently: failed calls, unverified blocking findings, files not parsed, rules just below the threshold |
| `prompts/` | the exact prompt sent to the reviewer per chunk |

`shall scan --out-dir DIR` writes `scan.md` (warnings per file, skipped files, files Jev could not
check) and `scan.json` (every file's scores, findings, skips and Jev usage). It exits 3 when Jev
failed for a file, and 2 only with `--fail-on-blocking` (secret-scanner hits) or `--fail-on-warn`.

`shall triage` writes `triage.md` (relevant and unverified comments first, noise folded) and
`triage.json` (every comment with its status, reason, scores, matched rules and the evidence
the verifier cited). `shall publish --resolve-noise` writes `triage-plan.json`.

| Exit code | Meaning |
| --- | --- |
| 0 | done, no blocking finding (or `--fail-on-blocking` not set) |
| 1 | error (configuration, tooling, a failed review call) |
| 2 | blocking findings (an enforced MUST rule, verified) |
| 3 | the Jev service failed after retries: retry the job, do not treat it as a code problem |

## Evaluate changes to shall

Before changing thresholds, prompts, rules' wording or the tooling, compare before and after:

```bash
make test          # unit tests, no network
make check         # corpus lint + index
make eval          # selection on 11 cases (needs TYPESAFE_API_KEY)
make eval-scale    # selection with ~540 rules, 20 cases
make eval-facts    # known effects on vs off, 19 files in 9 languages
plugins/shall/bin/shall --config shall.yaml eval-verify --retrieval treesitter   # verification (needs claude)
make eval-triage   # triage of AI review comments, 24 labelled comments (needs claude)
make eval-hooks    # hook judge on 75 labelled tool calls and writes (--no-cache for latency)
```

Jev answers are cached in `.shall-cache/`, so re-runs only pay for changed questions. Current
numbers and what they mean: [docs/results.md](docs/results.md).

## Repository layout

| Path | What |
| --- | --- |
| `corpus/` | example organisation corpus: `rfcs/`, `domains.yaml`, `effects.yaml`, generated `index/` |
| `shall.yaml` | configuration of the example organisation corpus |
| `plugins/shall/` | the Claude Code plugin: skills, agents, `hooks/hooks.json`, `bin/shall`, `bin/shall-hook`, `bin/shall-pr-review` |
| `plugins/shall/tooling/` | the Python package behind the CLI (`uv` project, tests) |
| `ci/github/` | workflow templates for the corpus repository and for application repositories |
| `examples/booking-service/.shall/` | an application repository's local rules (`BOOK-`) |
| `.shall/` | this repository's own rules for its tooling (`JTOOL-`) |
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
- **Triage sees bots' comments when the job runs.** A bot that comments after the shall job is
  triaged on the next push. Only inline review threads are read, not PR-level comments.
- **Two external services.** An outage fails the job with exit 3.
- **Data leaves your machine.** Diffs are sent to TypeSafe and Anthropic.
- **Hooks see one call at a time.** A violation split over several calls (write a script,
  then run it) is judged per call; the Stop review sees the resulting files, not the
  commands. After a write, Jev judges the written lines plus 15 lines of context only.
