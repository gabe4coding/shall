---
id: SCALE-0029
title: Kafka consumers and failure handling
status: enforced
domain: messaging
artifacts: [diff, code, spec]
languages: [any]
owner: platform
review_by: 2027-05-31
supersedes: []
summary: >
  Idempotent handling, offset commits, retries, dead-letter topics and poison message
  handling for services that consume from Kafka.
applies_when: >
  The content consumes messages from Kafka, configures a Kafka consumer or listener, or handles
  errors, retries or dead-letter topics for consumed messages.
not_applies_when: >
  No Kafka message is consumed and no consumer, listener or dead-letter topic is configured.
---

# SCALE-0029: Kafka consumers and failure handling

## Context

Kafka delivers at least once: after a rebalance or crash, consumers see messages again. A
consumer that is not idempotent double-books tables or double-sends notifications, and a
single bad message can block a partition for hours. These rules make consumers safe to
replay and keep partitions moving.

## Requirements

### SCALE-0029.1 Idempotent message handling
A consumer MUST produce the same outcome when it processes the same message twice, for
example by recording processed `event_id`s or using conditional writes.

- Applies when: the content adds or changes a Kafka message handler, `@KafkaListener`, consumer loop or `eachMessage` callback that writes state or calls other services.
- Enforcement: agent

### SCALE-0029.2 Commit offsets after processing
Offsets MUST be committed only after the message has been fully processed; consumers MUST NOT
rely on `enable.auto.commit=true` when processing has side effects.

- Applies when: the content configures `enable.auto.commit`, calls `commitSync`, `commitAsync` or `commitOffsets`, or sets the listener ack mode.
- Enforcement: agent

### SCALE-0029.3 Dead-letter topic after bounded retries
A message that still fails after a bounded number of retries MUST be published to the
consumer's dead-letter topic `<topic>.<consumer-group>.dlt` with the error and original offset in
headers.

- Applies when: the content adds or changes consumer error handling, a retry policy, `DefaultErrorHandler`, `DeadLetterPublishingRecoverer` or a dead-letter topic.
- Enforcement: agent

### SCALE-0029.4 Deserialization errors do not block the partition
Deserialization failures MUST be caught and routed to the dead-letter topic instead of
throwing in a loop on the same offset.

- Applies when: the content configures a consumer value deserializer or `ErrorHandlingDeserializer`, or parses message payloads.
- Enforcement: agent

### SCALE-0029.5 Non-blocking retries for slow recovery
Retries that wait longer than a few seconds SHOULD use retry topics instead of sleeping in the
listener thread, so the partition keeps moving and the consumer is not evicted from the group.

- Applies when: the content adds a sleep, backoff or retry loop inside a Kafka message handler.
- Enforcement: agent

### SCALE-0029.6 Poll interval matches processing time
`max.poll.interval.ms` and `max.poll.records` SHOULD be set so that the worst-case processing
time of one batch stays below the poll interval.

- Applies when: the content sets `max.poll.records`, `max.poll.interval.ms` or changes the batch size of a consumer.
- Enforcement: agent

### SCALE-0029.7 Explicit consumer group and offset reset
Each consumer MUST use a dedicated `group.id` named after the service and purpose, and MUST set
`auto.offset.reset` explicitly.

- Applies when: the content creates a Kafka consumer or listener, or sets `group.id` or `auto.offset.reset`.
- Enforcement: linter

### SCALE-0029.8 Tolerate unknown fields and event types
Consumers MUST ignore unknown fields and unknown `event_type` values instead of failing, so
producers can evolve their schemas.

- Applies when: the content deserializes or dispatches consumed events by type or maps them to a class.
- Enforcement: agent

### SCALE-0029.9 Lag and dead-letter alerts
Every production consumer group SHOULD have an alert on consumer lag and on messages arriving
in its dead-letter topic.

- Applies when: the content adds a new consumer group, dead-letter topic or its monitoring configuration.
- Enforcement: agent

### SCALE-0029.10 Replay from the dead-letter topic
Teams MAY replay dead-letter messages with the shared `dlt-replayer` tool instead of writing a
custom replay consumer.

- Applies when: the content adds code or a job that reads a dead-letter topic and republishes messages.
- Enforcement: agent

### SCALE-0029.11 Failure handling in designs
A design that adds a consumer MUST describe its idempotency key, retry policy, dead-letter
handling and the effect of replaying the topic from the start.

- Applies when: the content is a design that proposes consuming a Kafka topic or adding an event-driven flow.
- Artifacts: spec
- Enforcement: agent
