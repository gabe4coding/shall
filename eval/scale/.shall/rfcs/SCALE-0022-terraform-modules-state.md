---
id: SCALE-0022
title: Terraform modules, state and tagging
status: enforced
domain: infrastructure
artifacts: [diff, code, spec]
languages: [any]
owner: sre
review_by: 2027-03-31
supersedes: []
summary: >
  How Terraform code is organised into modules and root stacks, how state is stored and
  locked, how providers and modules are versioned, and which tags every resource carries.
applies_when: >
  The content adds or changes Terraform files (.tf, .tfvars), a Terraform module, a backend or
  provider block, or resource tags.
not_applies_when: >
  No Terraform file, module, backend, provider or resource tag is added, changed or described.
---

# SCALE-0022: Terraform modules, state and tagging

## Context

Infrastructure lives in the `infra-live` repository as root stacks per account and
environment, built from versioned modules in `infra-modules`. Lost or corrupted state and
unpinned providers have caused the worst infrastructure incidents so far, and untagged
resources make cost reports and ownership lookups impossible.

## Requirements

### SCALE-0022.1 Remote locked state
Every root stack MUST use the shared S3 backend with DynamoDB locking and encryption enabled,
and MUST NOT use local state or commit `.tfstate` files.

- Applies when: the content adds or changes a `backend` block, a `terraform { }` block of a root stack, or adds a `.tfstate` file.
- Enforcement: agent

### SCALE-0022.2 One state per environment
Production and non-production resources MUST live in separate root stacks with separate state
files; a single state MUST NOT span environments.

- Applies when: the content adds a root stack or adds resources for another environment to an existing stack.
- Enforcement: agent

### SCALE-0022.3 Pinned provider versions
Every root stack and module MUST pin each provider in `required_providers` with a pessimistic
constraint such as `~> 5.40`, and the `.terraform.lock.hcl` file MUST be committed.

- Applies when: the content adds or changes a `required_providers` block or a `provider` block.
- Enforcement: linter

### SCALE-0022.4 Pinned module sources
A module sourced from `infra-modules` or a public registry MUST reference an immutable tag or
version, never a branch or an unversioned Git reference.

- Applies when: the content adds or changes a `module` block's `source` or `version`.
- Enforcement: agent

### SCALE-0022.5 Mandatory tags
Every taggable resource MUST carry the tags `team`, `service`, `environment` and
`cost-center`, preferably through the provider `default_tags` block.

- Applies when: the content adds a taggable cloud resource, or changes `tags` or `default_tags`.
- Enforcement: agent

### SCALE-0022.6 Protect stateful resources
Databases, buckets with data, KMS keys and DNS zones MUST set `lifecycle { prevent_destroy = true }`
in production stacks.

- Applies when: the content adds or changes a database, storage bucket, KMS key or DNS zone resource in a production stack.
- Enforcement: agent

### SCALE-0022.7 Refactor with moved blocks
Renaming or moving a resource address SHOULD use a `moved` block instead of `terraform state mv`
run by hand, so the refactor is reviewed and reproducible.

- Applies when: the content renames a resource or module block, or moves resources between modules.
- Enforcement: agent

### SCALE-0022.8 Typed and documented module variables
Every module input variable SHOULD declare a `type` and a `description`, and use a
`validation` block when only some values are valid.

- Applies when: the content adds or changes a `variable` block in a Terraform module.
- Enforcement: agent

### SCALE-0022.9 Plan reviewed before apply
Changes to production stacks MUST be applied only by the CI pipeline from the plan attached to
the merged pull request, never by `terraform apply` from a laptop.

- Applies when: the content describes or scripts how Terraform changes are applied, or changes the Terraform CI workflow.
- Enforcement: agent

### SCALE-0022.10 Data sources over hard-coded identifiers
Modules MAY hard-code account, VPC or subnet identifiers only in root stacks; inside a reusable
module those values come from variables or data sources.

- Applies when: the content adds a literal account id, VPC id, subnet id or ARN to Terraform code.
- Enforcement: agent
