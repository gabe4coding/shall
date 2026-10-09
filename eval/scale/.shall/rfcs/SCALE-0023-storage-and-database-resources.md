---
id: SCALE-0023
title: Storage buckets and managed databases
status: enforced
domain: infrastructure
artifacts: [diff, code, spec]
languages: [any]
owner: sre
review_by: 2027-02-28
supersedes: []
summary: >
  Encryption, public access, versioning, backups and deletion protection for object storage
  buckets and managed databases defined as infrastructure code.
applies_when: >
  The content creates or changes an object storage bucket (S3, GCS), a managed database
  (RDS, Aurora, Cloud SQL, DynamoDB, ElastiCache) or their backup, encryption or access settings.
not_applies_when: >
  No storage bucket, managed database or their encryption, backup or access configuration is
  added, changed or described.
---

# SCALE-0023: Storage buckets and managed databases

## Context

Buckets and databases hold booking, diner and restaurant data. Public buckets and missing
backups are the two failure modes with the highest impact on the company, and both are
decided in the Terraform definition. These rules make the safe settings explicit on every
resource instead of relying on account defaults.

## Requirements

### SCALE-0023.1 Block public access on buckets
Every S3 bucket MUST have an `aws_s3_bucket_public_access_block` with all four settings set to
`true`, unless it is a static asset origin served only through the CDN.

- Applies when: the content adds or changes an `aws_s3_bucket`, `google_storage_bucket` or its public access block.
- Enforcement: linter

### SCALE-0023.2 No public ACLs or wildcard bucket policies
A bucket policy or ACL MUST NOT grant access to `*`, `AllUsers` or `allAuthenticatedUsers`.

- Applies when: the content adds or changes a bucket policy, a bucket ACL or an IAM binding on a bucket.
- Enforcement: agent

### SCALE-0023.3 Encryption at rest with managed keys
Buckets and databases that store personal or booking data MUST be encrypted with a customer
managed KMS key owned by the service, not only the provider default key.

- Applies when: the content adds a bucket or database resource, or changes its `kms_key_id`, `server_side_encryption_configuration` or `storage_encrypted` settings.
- Enforcement: agent

### SCALE-0023.4 TLS-only access to buckets
Bucket policies SHOULD deny requests where `aws:SecureTransport` is `false`.

- Applies when: the content adds or changes an S3 bucket policy.
- Enforcement: agent

### SCALE-0023.5 Versioning and lifecycle on data buckets
Buckets that hold data other than temporary files SHOULD enable versioning and SHOULD define a
lifecycle rule that expires non-current versions.

- Applies when: the content adds or changes an S3 or GCS bucket, its versioning or its lifecycle configuration.
- Enforcement: agent

### SCALE-0023.6 Automated backups with retention
Production relational databases MUST enable automated backups with a retention of at least 14
days and point-in-time recovery.

- Applies when: the content adds or changes an RDS, Aurora or Cloud SQL instance or cluster, or its `backup_retention_period` or backup settings.
- Enforcement: agent

### SCALE-0023.7 Deletion protection and final snapshot
Production databases MUST set `deletion_protection = true` and MUST NOT set
`skip_final_snapshot = true`.

- Applies when: the content adds or changes a production database resource or its `deletion_protection` or `skip_final_snapshot` attributes.
- Enforcement: linter

### SCALE-0023.8 Databases in private subnets only
Databases and caches MUST be placed in private subnets and MUST set `publicly_accessible = false`.

- Applies when: the content adds or changes a database or cache resource, its subnet group or its `publicly_accessible` attribute.
- Enforcement: agent

### SCALE-0023.9 Multi-AZ for production databases
Production databases that serve the booking flow SHOULD run Multi-AZ or with a replica in a
second zone.

- Applies when: the content adds or changes a production database instance or cluster, or its `multi_az` or replica settings.
- Enforcement: agent

### SCALE-0023.10 Restore tested in designs
A design that introduces a new production datastore MUST state its backup schedule, retention,
recovery point objective and how a restore is tested.

- Applies when: the content is a design that adds a new database, bucket or other datastore.
- Artifacts: spec
- Enforcement: agent

### SCALE-0023.11 Access logging on sensitive buckets
Buckets holding exports of personal data MAY forward access logs to the central logging
bucket instead of enabling server access logging on each bucket.

- Applies when: the content adds or changes a bucket that stores data exports, or its logging configuration.
- Enforcement: agent
