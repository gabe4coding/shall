---
id: SCALE-0028
title: Kafka producers and event schemas
status: enforced
domain: messaging
artifacts: [diff, code, spec]
languages: [any]
owner: platform
review_by: 2027-05-31
supersedes: []
summary: >
  Message keys, registered schemas and compatibility, idempotent producer configuration,
  topic naming and event envelopes for services that publish to Kafka.
applies_when: >
  The content publishes messages to Kafka, configures a Kafka producer, creates a topic, or adds
  or changes an event schema (Avro, Protobuf, JSON Schema) registered for a topic.
not_applies_when: >
  No Kafka message is produced, no producer or topic is configured and no event schema is added
  or changed.
---

# SCALE-0028: Kafka producers and event schemas

## Context

Booking, availability and payment events flow between services over Kafka, with schemas in
the Confluent Schema Registry. Consumers break when a producer changes a schema
incompatibly, loses ordering by using a random key, or produces duplicates on retry. These
rules make every produced event keyed, typed and safe to retry.

## Requirements

### SCALE-0028.1 Key by the entity that needs ordering
Every produced message MUST carry a key equal to the identifier of the entity whose events
have to stay ordered, such as the reservation id or restaurant id.

- Applies when: the content calls `send`, `produce` or `ProducerRecord` with a null, random or constant key, or chooses the key of a new event.
- Enforcement: agent

### SCALE-0028.2 Registered schema for every topic
Values published to a shared topic MUST be serialized with a schema registered in the Schema
Registry; producers MUST NOT publish free-form JSON strings.

- Applies when: the content configures a producer value serializer, or publishes a JSON string, map or dictionary to a Kafka topic.
- Enforcement: agent

### SCALE-0028.3 Backward-compatible schema changes
A schema change MUST keep the subject's `BACKWARD_TRANSITIVE` compatibility: new fields have
defaults and existing fields are not removed, renamed or retyped.

- Applies when: the content adds or changes an `.avsc`, `.proto` or JSON Schema file for a Kafka topic, or a generated event class.
- Enforcement: agent

### SCALE-0028.4 Idempotent producer
Producers MUST set `enable.idempotence=true` and `acks=all`.

- Applies when: the content creates or configures a Kafka producer, or sets `acks`, `enable.idempotence`, `retries` or `max.in.flight.requests.per.connection`.
- Enforcement: linter

### SCALE-0028.5 Outbox for events tied to database writes
An event that reports a database change SHOULD be written through the transactional outbox
table instead of publishing to Kafka directly inside the request handler.

- Applies when: the content publishes a Kafka message in the same code path that commits a database transaction.
- Enforcement: agent

### SCALE-0028.6 Standard event envelope
Every event SHOULD carry the envelope fields `event_id`, `event_type`, `occurred_at` in UTC and
`producer`, so consumers deduplicate and trace events uniformly.

- Applies when: the content defines a new event type or schema, or builds the payload of a produced message.
- Enforcement: agent

### SCALE-0028.7 Topic naming and ownership
New topics MUST follow `<domain>.<entity>.<event>.v<major>` and MUST be declared in the topics
repository with an owning team, partitions and retention.

- Applies when: the content creates a Kafka topic or references a topic name that does not exist yet.
- Enforcement: agent

### SCALE-0028.8 New major version for breaking changes
A breaking change to an event MUST be published on a new `v<major+1>` topic, with the old topic
produced in parallel until its consumers have migrated.

- Applies when: the content removes, renames or retypes a field of a published event, or changes the meaning of an event.
- Enforcement: agent

### SCALE-0028.9 Handle send failures
Code that sends a message MUST handle the failure of the send callback or future and MUST NOT
fire and forget.

- Applies when: the content calls a Kafka producer `send` or `produce` method.
- Enforcement: agent

### SCALE-0028.10 Compression
Producers of high-volume topics MAY enable `compression.type=zstd` or `lz4`.

- Applies when: the content configures a producer for a topic, or sets `compression.type`.
- Enforcement: agent

### SCALE-0028.11 Event contracts in designs
A design that adds a new event MUST name the topic, key, schema, expected throughput and the
known consumers.

- Applies when: the content is a design that proposes publishing a new event or topic.
- Artifacts: spec
- Enforcement: agent
