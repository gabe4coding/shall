---
id: SCALE-0067
title: Spring Boot services in Java and Kotlin
status: enforced
domain: jvm
artifacts: [diff, code]
languages: [java, kotlin]
owner: platform
review_by: 2027-04-30
supersedes: []
summary: >
  Conventions for Spring Boot backend code in Java and Kotlin: dependency injection,
  transaction boundaries, null safety and blocking calls in reactive code.
applies_when: >
  The content is or changes Java or Kotlin backend source code of a Spring Boot service.
not_applies_when: >
  The content is not Java or Kotlin backend source code, or is Android app code.
---

# SCALE-0067: Spring Boot services in Java and Kotlin

## Context

Most of our booking and restaurant back-office services run on Spring Boot. Field
injection hides dependencies and breaks tests, transactions that span remote calls hold
database connections for seconds, and a single blocking call on a Netty event loop can
stall every request of a reactive service.

## Requirements

### SCALE-0067.1 Constructor injection
Spring beans MUST receive their dependencies through the constructor, and MUST NOT use
`@Autowired` on fields or setters.

- Applies when: the code declares a class annotated `@Component`, `@Service`, `@Repository`, `@Controller`, `@RestController` or `@Configuration`, or uses `@Autowired`.
- Enforcement: linter

### SCALE-0067.2 Transactions on the service layer
`@Transactional` MUST be placed on public service-layer methods, not on controllers or
repositories, and MUST NOT be on private methods or methods called from the same class.

- Applies when: the code adds or moves a `@Transactional` annotation.
- Enforcement: agent

### SCALE-0067.3 No remote calls inside transactions
A method running in a database transaction MUST NOT make HTTP calls, publish Kafka
messages or call other remote services; publish through an outbox table or after commit.

- Applies when: a method annotated `@Transactional` or run in `TransactionTemplate` calls an HTTP client, `KafkaTemplate`, `WebClient`, `RestTemplate` or another service client.
- Enforcement: agent

### SCALE-0067.4 Read-only transactions
Transactional methods that only read data SHOULD be marked `@Transactional(readOnly = true)`.

- Applies when: a `@Transactional` method only calls repository find, get, count or exists methods.
- Enforcement: agent

### SCALE-0067.5 Kotlin null safety
Kotlin code MUST NOT use the `!!` operator on values from requests, repositories or Java
APIs; it handles null with `?:`, `?.let` or an explicit error.

- Applies when: Kotlin code uses the `!!` operator.
- Enforcement: agent

### SCALE-0067.6 Optional in Java
Java methods that can return no value SHOULD return `Optional<T>` instead of null, and
SHOULD NOT take `Optional` as a parameter or field type.

- Applies when: Java code declares a method that returns null, or uses `Optional` as a parameter, field or return type.
- Enforcement: agent

### SCALE-0067.7 No blocking in reactive code
Code running on a reactive pipeline (WebFlux, Reactor `Mono`/`Flux`, Kotlin coroutines on
the event loop) MUST NOT call blocking APIs such as JDBC, `RestTemplate`, `.block()`,
`Thread.sleep` or blocking file I/O.

- Applies when: code inside a `Mono`, `Flux`, `suspend` function or WebFlux handler calls `.block()`, `blockFirst`, `RestTemplate`, a JDBC repository, `Thread.sleep` or `java.io` file APIs.
- Enforcement: agent

### SCALE-0067.8 Blocking work offloaded
When reactive code has to call a blocking library, it MUST wrap the call in
`Mono.fromCallable` with `subscribeOn(Schedulers.boundedElastic())` or `withContext(Dispatchers.IO)`.

- Applies when: reactive or coroutine code wraps or calls a blocking client or legacy library.
- Enforcement: agent

### SCALE-0067.9 Typed configuration properties
Configuration SHOULD be bound to `@ConfigurationProperties` classes with validation,
instead of scattered `@Value` annotations.

- Applies when: the code adds `@Value` or `@ConfigurationProperties`, or reads values from `Environment`.
- Enforcement: agent

### SCALE-0067.10 Data classes for DTOs
Kotlin request and response DTOs MAY be declared as `data class` with `val` properties,
and Java DTOs MAY be declared as `record`.

- Applies when: the code declares a request, response or event DTO class in Java or Kotlin.
- Enforcement: agent
