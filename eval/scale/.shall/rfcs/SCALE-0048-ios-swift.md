---
id: SCALE-0048
title: iOS app concurrency, memory and token storage
status: enforced
domain: ios
artifacts: [diff, code]
languages: [swift]
owner: mobile
review_by: 2027-02-28
supersedes: []
summary: >
  Main-actor UI updates, retain cycles, Keychain storage of tokens, structured
  async/await and safe unwrapping in the Swift code of the iOS apps.
applies_when: >
  The content adds or changes Swift code of the iOS apps: views, view controllers, view
  models, closures, delegates, async functions, tasks or credential storage.
not_applies_when: >
  The content is not Swift code of an iOS app (Android, web, backend services).
---

# SCALE-0048: iOS app concurrency, memory and token storage

## Context

The iOS app mixes UIKit screens with newer SwiftUI screens and is moving from
completion handlers to async/await. Crashes from UI work off the main thread, leaks
from retain cycles in closures, and tokens stored in UserDefaults are the recurring
findings in reviews and security audits.

## Requirements

### SCALE-0048.1 UI state on the main actor
Types that own UI state (observable view models, `UIViewController` subclasses) MUST be
annotated `@MainActor`, and UIKit or SwiftUI state MUST NOT be changed from a background
thread.

- Applies when: Swift code adds or changes an `ObservableObject`, `@Observable` class, view controller, or code that updates UI after a network or background call.
- Enforcement: agent

### SCALE-0048.2 Main-actor hops in async code
In async code, returning to the main thread SHOULD use `@MainActor` functions or
`await MainActor.run` instead of `DispatchQueue.main.async`.

- Applies when: async Swift code calls `DispatchQueue.main.async` or `DispatchQueue.main.sync`.
- Enforcement: agent

### SCALE-0048.3 Weak self in stored escaping closures
An escaping closure that is stored by an object (completion handler property, Combine
`sink`, `NotificationCenter` observer, `Timer`) and captures `self` MUST capture it as
`[weak self]`.

- Applies when: Swift code passes a closure that references `self` to `sink`, `addObserver`, `Timer.scheduledTimer` or stores it in a property.
- Enforcement: agent

### SCALE-0048.4 Weak delegates
Delegate and data source properties MUST be declared `weak var` with a class-bound
protocol (`protocol BookingDelegate: AnyObject`).

- Applies when: Swift code declares a `delegate` or `dataSource` property or a delegate protocol.
- Enforcement: agent

### SCALE-0048.5 Tokens in the Keychain
Access tokens, refresh tokens and session identifiers MUST be stored in the Keychain with
`kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` or a stricter class, and MUST NOT be
stored in `UserDefaults`, `@AppStorage`, plist files or the file system.

- Applies when: Swift code stores or reads an authentication token, refresh token, session id or API credential.
- Enforcement: agent

### SCALE-0048.6 Cancelled tasks
A `Task` started from a view or view model SHOULD be stored and cancelled when the view
disappears, or started with the SwiftUI `.task` modifier, which cancels it automatically.

- Applies when: Swift code creates a `Task { }` or `Task.detached` in a view, view controller or view model.
- Enforcement: agent

### SCALE-0048.7 Async functions for new APIs
New asynchronous APIs SHOULD be written as `async` functions instead of functions that
take a completion handler.

- Applies when: Swift code adds a function with a completion handler, `@escaping` result callback or a new async function.
- Enforcement: agent

### SCALE-0048.8 Continuations resumed exactly once
A `withCheckedContinuation` or `withCheckedThrowingContinuation` block MUST resume its
continuation exactly once on every code path, including error and early-return paths.

- Applies when: Swift code calls `withCheckedContinuation`, `withCheckedThrowingContinuation` or `withUnsafeContinuation`.
- Enforcement: agent

### SCALE-0048.9 No force unwraps
Force unwraps (`!`), `try!` and `as!` MUST NOT be used in app code outside tests and
`@IBOutlet` declarations.

- Applies when: Swift code contains a force unwrap, `try!` or `as!`.
- Enforcement: linter

### SCALE-0048.10 Wrapping callback APIs
An existing completion-handler API MAY be exposed to async code by wrapping it with
`withCheckedThrowingContinuation` instead of rewriting it.

- Applies when: Swift code bridges a completion-handler or delegate-based API to async/await.
- Enforcement: agent

### SCALE-0048.11 Sendable values across actors
Types passed between actors or into detached tasks SHOULD conform to `Sendable`, and new
modules SHOULD compile with strict concurrency checking set to `complete`.

- Applies when: Swift code passes a value into a `Task`, an actor method or across an actor boundary, or changes Swift concurrency build settings.
- Enforcement: agent
