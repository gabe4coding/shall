---
id: SCALE-0005
title: Third-party dependencies and supply chain
status: approved
domain: security
artifacts: [diff, code, spec]
languages: [any]
owner: security
review_by: 2027-06-30
supersedes: []
summary: >
  Rules for adding, pinning and updating open-source libraries, packages and build
  plugins.
applies_when: >
  The content adds, removes, upgrades or pins a dependency in a package manifest or lock
  file (package.json, pnpm-lock.yaml, pyproject.toml, uv.lock, build.gradle.kts, go.mod),
  or changes a package registry configuration.
not_applies_when: >
  No package manifest, lock file or registry configuration is added or changed.
---

# SCALE-0005: Third-party dependencies and supply chain

## Context

A typical service pulls hundreds of transitive packages. Typosquatted packages, install
scripts and unpinned versions have all hit the industry. We accept open source freely,
but every dependency change has to be reproducible and traceable.

## Requirements

### SCALE-0005.1 Lock files committed
Every service and library MUST commit its lock file, and CI MUST install from the lock file
without updating it (`npm ci`, `pnpm install --frozen-lockfile`, `uv sync --locked`).

- Applies when: the content adds or changes a package manifest, a lock file, or an install command in a build script.
- Enforcement: linter

### SCALE-0005.2 Internal registry proxy
Packages MUST be resolved through the company Artifactory proxy, not directly from public
registries or Git URLs.

- Applies when: the content changes `.npmrc`, `pip.conf`, `uv` index settings, Gradle repositories, `GOPROXY`, or adds a dependency pointing to a Git URL or tarball.
- Enforcement: agent

### SCALE-0005.3 No known critical vulnerabilities
A change MUST NOT add or upgrade to a dependency version with a known critical or high
vulnerability that has a fixed version available.

- Applies when: the content adds a new dependency or changes a dependency version.
- Enforcement: agent

### SCALE-0005.4 New dependency justification
A pull request that adds a new direct dependency SHOULD state why it is needed and why an
existing dependency or the standard library does not cover it.

- Applies when: the content adds a new direct dependency to a package manifest.
- Enforcement: agent

### SCALE-0005.5 Package health
A new direct dependency SHOULD have a compatible open-source license (no AGPL or
unlicensed packages), a release in the last 18 months and more than one maintainer.

- Applies when: the content adds a new direct dependency to a package manifest.
- Enforcement: agent

### SCALE-0005.6 Install scripts
Packages that run install or postinstall scripts MUST be listed in the repository's
allowlist of trusted build scripts before they are added.

- Applies when: the content adds an npm or pnpm dependency, or changes `onlyBuiltDependencies`, `ignore-scripts` or similar install-script settings.
- Enforcement: agent

### SCALE-0005.7 Pinned GitHub Actions and base images
Third-party GitHub Actions MUST be pinned to a full commit SHA, and container base images
MUST be pinned by digest.

- Applies when: the content adds or changes a `uses:` line in a GitHub Actions workflow or a `FROM` line in a Dockerfile.
- Enforcement: agent

### SCALE-0005.8 Automated update bot
Repositories SHOULD enable Renovate with grouped minor and patch updates and a weekly
schedule.

- Applies when: the content adds or changes `renovate.json`, Dependabot configuration or a new repository skeleton.
- Enforcement: agent

### SCALE-0005.9 Vendored code
Copied third-party source files MUST keep their original license header and a note giving
the upstream project and version.

- Applies when: the content adds source code copied from an external project into a `vendor`, `third_party` or `lib` folder.
- Enforcement: agent

### SCALE-0005.10 SBOM publication
Services MAY publish a CycloneDX SBOM as a build artifact for each release.

- Applies when: the content changes the release build of a service or adds SBOM generation.
- Enforcement: agent
