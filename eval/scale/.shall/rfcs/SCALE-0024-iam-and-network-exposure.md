---
id: SCALE-0024
title: Cloud IAM least privilege and network exposure
status: enforced
domain: infrastructure
artifacts: [diff, code, spec]
languages: [any]
owner: sre
review_by: 2027-01-31
supersedes: []
summary: >
  Least-privilege IAM roles and policies for workloads and people, and limits on what cloud
  resources expose to the internet through security groups, firewall rules and load balancers.
applies_when: >
  The content adds or changes an IAM role, policy, binding or service account, a security group,
  firewall rule, network ACL, load balancer listener or public IP in infrastructure code.
not_applies_when: >
  No IAM role, policy, service account or network exposure setting is added, changed or described.
---

# SCALE-0024: Cloud IAM least privilege and network exposure

## Context

A leaked workload credential is only as dangerous as the permissions attached to it, and an
open port is only reachable if the network allows it. Both are defined in Terraform and
reviewed in pull requests, so these rules target the concrete policy and network blocks that
reviewers see.

## Requirements

### SCALE-0024.1 No wildcard actions and resources
An IAM policy statement with `Effect = "Allow"` MUST NOT combine `Action = "*"` or a service
wildcard like `s3:*` with `Resource = "*"`.

- Applies when: the content adds or changes an IAM policy document, `aws_iam_policy`, `aws_iam_role_policy` or `jsonencode` policy block.
- Enforcement: linter

### SCALE-0024.2 Resource-scoped permissions
IAM statements SHOULD name the specific ARNs the workload uses instead of `*`, and SHOULD use
conditions such as `aws:ResourceTag` when the ARNs are not known in advance.

- Applies when: the content adds or changes the `Resource` or `Condition` of an IAM policy statement.
- Enforcement: agent

### SCALE-0024.3 Workload identity instead of static keys
Workloads on Kubernetes MUST obtain cloud credentials through IRSA or Workload Identity and
MUST NOT use `aws_iam_access_key` or exported service account key files.

- Applies when: the content adds an `aws_iam_access_key`, a `google_service_account_key`, or an IAM role for a Kubernetes service account.
- Enforcement: agent

### SCALE-0024.4 One role per service
Each service MUST have its own IAM role or service account; roles MUST NOT be shared between
services.

- Applies when: the content adds an IAM role or service account, or attaches an existing role to a new workload.
- Enforcement: agent

### SCALE-0024.5 No managed admin policies on workloads
Workload roles MUST NOT attach `AdministratorAccess`, `PowerUserAccess` or the `roles/owner` and
`roles/editor` roles.

- Applies when: the content attaches a managed policy or predefined role to an IAM role, user, group or service account.
- Enforcement: linter

### SCALE-0024.6 Human access through groups and SSO
Permissions for people SHOULD be granted to SSO permission sets or groups, not to individual
IAM users.

- Applies when: the content adds an `aws_iam_user`, a user policy attachment, or an IAM binding for an individual `user:` member.
- Enforcement: agent

### SCALE-0024.7 No open ingress except public load balancers
Security group and firewall ingress rules MUST NOT allow `0.0.0.0/0` or `::/0` except on ports
80 and 443 of a public load balancer.

- Applies when: the content adds or changes an ingress rule, `aws_security_group_rule`, `aws_vpc_security_group_ingress_rule` or `google_compute_firewall`.
- Enforcement: agent

### SCALE-0024.8 No administrative ports from the internet
SSH, RDP and database ports MUST NOT be reachable from outside the VPC; access goes through
the bastion-less session manager.

- Applies when: the content opens port 22, 3389, 5432, 3306, 6379 or 9092 in a security group or firewall rule.
- Enforcement: agent

### SCALE-0024.9 Internal services behind internal load balancers
Services that are only called by other services SHOULD use internal load balancers and SHOULD
NOT receive a public IP address.

- Applies when: the content adds or changes a load balancer, its `internal` or `scheme` attribute, or assigns a public IP to an instance.
- Enforcement: agent

### SCALE-0024.10 Cross-account trust scoped by external id
A role trust policy that allows another account or a third party MAY omit an `sts:ExternalId`
condition only when the trusted principal is an account owned by the company.

- Applies when: the content adds or changes an IAM role `assume_role_policy` that trusts another AWS account or a third-party principal.
- Enforcement: agent
