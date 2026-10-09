<p align="center">
  <img src="docs/assets/logo.svg" alt="jrfc logo" width="128" height="128">
</p>

<h1 align="center">jrfc</h1>

<p align="center">
  <b>Engineering standards that agents can apply.</b><br>
  You write your standards as short RFC 2119 rules. jrfc finds the rules that apply to a change
  and checks the change against them.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/gabe4coding/jrfc?color=blue"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white">
  <a href="docs/installation.mdx#install-the-claude-code-plugin"><img alt="Claude Code plugin" src="https://img.shields.io/badge/Claude%20Code-plugin-D97757?logo=claude&logoColor=white"></a>
  <img alt="Status: proof of concept" src="https://img.shields.io/badge/status-proof%20of%20concept-orange">
  <a href="https://github.com/gabe4coding/jrfc/commits/main"><img alt="Last commit" src="https://img.shields.io/github/last-commit/gabe4coding/jrfc"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="docs/review.mdx">Review</a> ·
  <a href="docs/standards.mdx">Write standards</a> ·
  <a href="docs/hooks.mdx">Hooks</a> ·
  <a href="docs/architecture.mdx">How it works</a> ·
  <a href="docs/results.mdx">Results</a>
</p>

---

A standard is a Markdown file with numbered rules, for example *"Every outbound call MUST set a
timeout"*. jrfc checks pull requests, design specs, documents, existing code and the tool calls of
an agent against these rules.

- **People** write and own the standards. They review them like code.
- **[Jev](https://docs.typesafe.ai)** (TypeSafe) finds the rules that apply to each file of a
  change. It gives a calibrated probability for each rule.
- **Claude** reviews the change against only those rules and writes inline comments.
- **Deterministic code** validates each comment and checks blocking findings against the rest of the
  repository. Then it posts the comments to the pull request.

```
pull request ─► split per file ─► rules that apply (Jev) ─► review (Claude, no tools)
             ─► validate + verify against the repo (code) ─► PR comments + exit code
```

jrfc is a **proof of concept**. The idea comes from Cloudflare's
[engineering standards enforcement](https://blog.cloudflare.com/engineering-standards-enforcement/).
Read [what we measured](docs/results.mdx) and the [known limits](docs/limits.mdx).

## What you can do with it

| Task | Command | Page |
| --- | --- | --- |
| Find the rules that apply to a change or a task | `jrfc select` | [Review](docs/review.mdx) |
| Review a pull request, a spec or a document | `jrfc review` | [Review](docs/review.mdx) |
| Review each pull request in CI and block merges | `jrfc-pr-review` | [CI](docs/ci.mdx) |
| Check the tool calls of an agent while it works | Claude Code hooks | [Hooks](docs/hooks.mdx) |
| Lint existing files | `jrfc scan` | [Scan](docs/scan.mdx) |
| Sort the comments of other AI reviewers | `jrfc triage` | [Triage](docs/triage.mdx) |
| Write, change and retire standards | `jrfc new`, `lint`, `build` | [Standards](docs/standards.mdx) |

## Quick start

You need `git`, `make`, [`uv`](https://docs.astral.sh/uv/) and a `TYPESAFE_API_KEY`. A full review
also needs [Claude Code](https://docs.claude.com/en/docs/claude-code). Read
[Installation](docs/installation.mdx) for the full list.

> [!IMPORTANT]
> A review sends the diff to TypeSafe and to Anthropic. Make sure that your organisation permits
> this before you use jrfc on private code.

Clone the repository and run the checks. These steps do not need a key:

```bash
git clone https://github.com/gabe4coding/jrfc.git
cd jrfc
make check
make test
```

Put the CLI on your `PATH` and set the key:

```bash
export PATH="$PWD/plugins/jrfc/bin:$PATH"
export TYPESAFE_API_KEY=...
```

Find the rules that apply to a sample change (Jev, approximately 2 seconds):

```bash
jrfc --config jrfc.yaml select eval/cases/01-booking-endpoint.diff
jrfc --config jrfc.yaml select --text "add an endpoint to refund a payment"
```

Review the sample change (Jev and Claude, approximately 1 minute):

```bash
jrfc --config jrfc.yaml review eval/cases/01-booking-endpoint.diff --out-dir .jrfc-out/demo
cat .jrfc-out/demo/review.md
```

`--config jrfc.yaml` selects the example organisation corpus in this repository. Without it,
`jrfc` uses the rules of this repository for its own code (`.jrfc/`).

### With the Claude Code plugin

```bash
claude plugin marketplace add gabe4coding/jrfc
claude plugin install jrfc@jrfc
```

The plugin gives Claude Code the `jrfc` command, the skills, the reviewer agents and the hooks. In a
repository with jrfc standards, Claude finds the rules that apply before it writes code. Ask
*"check this PR against our standards"* or *"write a standard for idempotent retries"*.

## Use it in your repository

Point jrfc at the corpus of your organisation, pinned to a tag. Then review a branch:

```bash
export JRFC_EXTENDS=your-org/engineering-standards@v2026.09
git diff origin/main...HEAD > /tmp/pr.diff
jrfc review /tmp/pr.diff --out-dir .jrfc-out/pr
```

To add rules for one repository only, read [Review → Local rules](docs/review.mdx#organisation-rules-and-local-rules).
To create the corpus of your organisation, read [Standards → Create a corpus](docs/standards.mdx#create-the-corpus-of-your-organisation).

## Documentation

| Page | Content |
| --- | --- |
| [Installation](docs/installation.mdx) | Requirements, the CLI, the Claude Code plugin |
| [Review](docs/review.mdx) | Select and review, local rules, outputs, exit codes |
| [CI](docs/ci.mdx) | Review each pull request in GitHub Actions or another CI, cost |
| [Hooks](docs/hooks.mdx) | Check the tool calls of an agent while it works |
| [Scan](docs/scan.mdx) | Lint whole files with the judgment of the hooks |
| [Triage](docs/triage.mdx) | Sort the comments of Copilot, CodeRabbit and other AI reviewers |
| [Standards](docs/standards.mdx) | Write and maintain standards, known effects, your own corpus |
| [Configuration](docs/configuration.mdx) | Configuration layers, settings, environment variables |
| [Commands](docs/commands.mdx) | Every `jrfc` command |
| [Architecture](docs/architecture.mdx) | How selection, review, verification and hooks work |
| [Results](docs/results.mdx) | Measurements and lessons |
| [Known limits](docs/limits.mdx) | What jrfc does not do yet |
| [Development](docs/development.mdx) | Repository layout, tests, evals, releases |

## License

MIT. See [LICENSE](LICENSE).
