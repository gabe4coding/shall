---
id: SCALE-0027
title: Dockerfiles and container images
status: enforced
domain: containers
artifacts: [diff, code]
languages: [any]
owner: platform
review_by: 2027-04-30
supersedes: []
summary: >
  Approved and pinned base images, non-root users, multi-stage builds, minimal layers and no
  secrets baked into container images.
applies_when: >
  The content adds or changes a Dockerfile, Containerfile, `.dockerignore`, or a container image
  build configuration such as Jib or buildpacks.
not_applies_when: >
  No Dockerfile, `.dockerignore` or container image build configuration is added or changed.
---

# SCALE-0027: Dockerfiles and container images

## Context

Every service ships as a container image built in CI and scanned before release. Images
based on unpatched or unknown base images, running as root or carrying build tools and
credentials account for most findings of the image scanner. These rules keep images small,
patched and free of secrets.

## Requirements

### SCALE-0027.1 Approved base images only
The final stage of a Dockerfile MUST start `FROM` an image in the internal
`registry.internal/base/` catalogue or a distroless image.

- Applies when: the content adds or changes a `FROM` line of the final stage of a Dockerfile.
- Enforcement: linter

### SCALE-0027.2 Pinned base image versions
`FROM` lines MUST pin a specific version tag and MUST NOT use `latest`; base image updates
arrive through the dependency bot.

- Applies when: the content adds or changes a `FROM` line in a Dockerfile.
- Enforcement: agent

### SCALE-0027.3 Run as a non-root user
The final stage MUST set `USER` to a non-root numeric UID, and MUST NOT switch back to root
after that line.

- Applies when: the content adds or changes a `USER` instruction or the final stage of a Dockerfile.
- Enforcement: agent

### SCALE-0027.4 Multi-stage builds for compiled code
Images for compiled languages or bundled frontends MUST use a multi-stage build so compilers,
package managers and source code are absent from the final stage.

- Applies when: the content adds or changes a Dockerfile that runs a compiler, `npm`, `gradle`, `go build`, `pip install` or similar build step.
- Enforcement: agent

### SCALE-0027.5 No secrets in layers or build args
Dockerfiles MUST NOT `COPY` credential files or pass tokens through `ARG` or `ENV`; build-time
secrets use `RUN --mount=type=secret`.

- Applies when: the content adds `ARG`, `ENV`, `COPY` or `ADD` with names or files such as token, password, key, `.npmrc`, `.netrc` or credentials.
- Enforcement: agent

### SCALE-0027.6 Dockerignore excludes local files
A repository with a Dockerfile SHOULD have a `.dockerignore` that excludes `.git`, `.env`
files, local build outputs and test fixtures.

- Applies when: the content adds a Dockerfile, a `COPY . .` instruction, or changes `.dockerignore`.
- Enforcement: agent

### SCALE-0027.7 Exec form for entrypoint
`ENTRYPOINT` and `CMD` SHOULD use the JSON exec form so the process receives `SIGTERM`
directly and shuts down gracefully.

- Applies when: the content adds or changes an `ENTRYPOINT` or `CMD` instruction.
- Enforcement: linter

### SCALE-0027.8 Clean package manager caches in the same layer
A `RUN` that installs OS packages MUST remove the package manager cache in the same
instruction and MUST install with `--no-install-recommends` or the equivalent.

- Applies when: the content adds a `RUN` with `apt-get install`, `apk add` or `dnf install`.
- Enforcement: agent

### SCALE-0027.9 COPY instead of ADD
Dockerfiles SHOULD use `COPY` instead of `ADD` for local files, and download remote files
in a `RUN` step that verifies a checksum.

- Applies when: the content adds an `ADD` instruction to a Dockerfile.
- Enforcement: agent

### SCALE-0027.10 Image metadata labels
Images MAY carry OCI labels such as `org.opencontainers.image.source` and
`org.opencontainers.image.revision` set by CI build arguments.

- Applies when: the content adds or changes `LABEL` instructions or the image labels in a build configuration.
- Enforcement: agent
