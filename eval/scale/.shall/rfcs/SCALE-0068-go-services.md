---
id: SCALE-0068
title: Go services
status: enforced
domain: go
artifacts: [diff, code]
languages: [go]
owner: platform
review_by: 2027-04-30
supersedes: []
summary: >
  Conventions for Go service code: context propagation, error wrapping, goroutine
  lifetimes and closing resources.
applies_when: >
  The content is or changes Go source code (.go files) of a service, worker or
  command-line tool.
not_applies_when: >
  The content is not Go source code.
---

# SCALE-0068: Go services

## Context

Our availability and notification services are written in Go. The incidents we trace
back to Go code are almost always one of four things: a lost context that ignores
cancellation, an error returned without the information needed to find its source, a
goroutine that never exits, or a response body or file that is never closed.

## Requirements

### SCALE-0068.1 Context as first parameter
Functions that do I/O or call other services MUST take a `context.Context` as their first
parameter and pass it to every downstream call.

- Applies when: Go code declares a function that performs an HTTP request, database query, Kafka or Redis operation, or calls another such function.
- Enforcement: agent

### SCALE-0068.2 No background context in request paths
Code that handles a request or message MUST NOT create a new `context.Background()` or
`context.TODO()`; it derives contexts from the incoming one.

- Applies when: Go code in an HTTP handler, gRPC method, consumer or function called from one uses `context.Background()` or `context.TODO()`.
- Enforcement: agent

### SCALE-0068.3 Cancel derived contexts
Every `context.WithTimeout`, `WithDeadline` or `WithCancel` call MUST be followed by
`defer cancel()` in the same function.

- Applies when: Go code calls `context.WithTimeout`, `context.WithDeadline` or `context.WithCancel`.
- Enforcement: linter

### SCALE-0068.4 Wrap errors with context
Errors returned from a call SHOULD be wrapped with `fmt.Errorf("<operation>: %w", err)`
so the caller can see where they came from and still match them with `errors.Is`.

- Applies when: Go code returns an error received from another function call, for example `return err` or `return nil, err`.
- Enforcement: agent

### SCALE-0068.5 Match errors with errors.Is and errors.As
Code MUST compare errors with `errors.Is` or `errors.As`, and MUST NOT compare error
strings or use `==` on wrapped errors.

- Applies when: Go code compares an error with `==`, `!=`, `err.Error()`, `strings.Contains` on an error message, or a type assertion on an error.
- Enforcement: agent

### SCALE-0068.6 No ignored errors
Code MUST NOT discard a returned error with `_` or by ignoring the return value, except
for documented best-effort calls marked with a comment.

- Applies when: Go code assigns an error result to `_`, or calls a function that returns an error without checking it.
- Enforcement: agent

### SCALE-0068.7 Goroutines have an exit
Every goroutine MUST have a way to stop: it listens to `ctx.Done()`, reads from a channel
that is closed, or is tracked by an `errgroup` or `sync.WaitGroup` that is waited on.

- Applies when: Go code starts a goroutine with the `go` keyword.
- Enforcement: agent

### SCALE-0068.8 Close bodies and resources
Response bodies, files, rows and other `io.Closer` values MUST be closed with `defer`
right after the error check of the call that opened them.

- Applies when: Go code calls `http.Get`, `client.Do`, `os.Open`, `db.Query`, `sql.Rows` or another function returning an `io.Closer`.
- Enforcement: agent

### SCALE-0068.9 Errors from deferred Close on writes
For files or writers opened for writing, code SHOULD check the error returned by `Close`
instead of discarding it in a bare `defer f.Close()`.

- Applies when: Go code opens a file or writer for writing, such as `os.Create`, `os.OpenFile` with write flags, or a `gzip.Writer`.
- Enforcement: agent

### SCALE-0068.10 Bounded concurrency
Code that starts goroutines in a loop SHOULD bound concurrency with a worker pool,
`errgroup.SetLimit` or a semaphore.

- Applies when: Go code starts goroutines inside a `for` or `range` loop.
- Enforcement: agent

### SCALE-0068.11 Panics at startup only
Code MAY use `panic` or `log.Fatal` during program startup for invalid configuration,
but not in request handling paths.

- Applies when: Go code calls `panic`, `log.Fatal` or `os.Exit`.
- Enforcement: agent
