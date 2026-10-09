---
id: SCALE-0047
title: Android app architecture and threading
status: enforced
domain: android
artifacts: [diff, code]
languages: [kotlin]
owner: mobile
review_by: 2027-02-28
supersedes: []
summary: >
  Lifecycle-aware coroutines, main-thread safety, ViewModel state and runtime permissions
  in the Kotlin code of the Android apps.
applies_when: >
  The content adds or changes Kotlin code of the Android apps: activities, fragments,
  composables, ViewModels, repositories, coroutines, flows or permission requests.
not_applies_when: >
  The content is not Kotlin code of an Android app (Kotlin backend services, iOS, web).
---

# SCALE-0047: Android app architecture and threading

## Context

Crash and ANR rates of the Android app are tracked against Play Store thresholds.
Most ANRs come from disk or network work on the main thread, and most crashes after
rotation or backgrounding come from coroutines and references that outlive their
screen. These rules apply to all Android modules.

## Requirements

### SCALE-0047.1 No GlobalScope
`GlobalScope.launch` and `GlobalScope.async` MUST NOT be used in app code.

- Applies when: Kotlin code references `GlobalScope`.
- Enforcement: linter

### SCALE-0047.2 Structured coroutine scopes
Coroutines MUST be launched in `viewModelScope`, `lifecycleScope` or an injected
`CoroutineScope` tied to a component lifecycle; a new unowned `CoroutineScope(...)` MUST
NOT be created inside a function.

- Applies when: Kotlin code calls `launch`, `async` or creates a `CoroutineScope`.
- Enforcement: agent

### SCALE-0047.3 Lifecycle-aware flow collection
A flow collected in an Activity or Fragment MUST be collected inside
`repeatOnLifecycle(Lifecycle.State.STARTED)`, and a flow read in Compose MUST use
`collectAsStateWithLifecycle()`.

- Applies when: an Activity, Fragment or composable calls `collect`, `collectLatest`, `collectAsState` or `observe` on a flow or LiveData.
- Enforcement: agent

### SCALE-0047.4 No blocking work on the main thread
Disk, database and network work MUST NOT run on the main thread; it MUST run in a
`suspend` function that switches to an IO dispatcher with `withContext`.

- Applies when: Kotlin code reads or writes files, SharedPreferences, DataStore or Room, performs a network call, or calls `runBlocking`.
- Enforcement: agent

### SCALE-0047.5 Injected dispatchers
Dispatchers SHOULD be injected through the constructor instead of referencing
`Dispatchers.IO` or `Dispatchers.Default` directly, so tests can pass a test dispatcher.

- Applies when: a ViewModel, repository or use case references `Dispatchers.IO`, `Dispatchers.Default` or `Dispatchers.Main`.
- Enforcement: agent

### SCALE-0047.6 Screen state in a ViewModel
Screen state MUST live in a `ViewModel` and be exposed as a `StateFlow`, not in
Activity, Fragment or composable fields, so that it survives configuration changes.

- Applies when: the content adds state to an Activity, Fragment or screen composable, or adds a ViewModel.
- Enforcement: agent

### SCALE-0047.7 Read-only state exposure
`MutableStateFlow`, `MutableSharedFlow` and `MutableLiveData` SHOULD be private and exposed
through a read-only `StateFlow`, `SharedFlow` or `LiveData` property.

- Applies when: a ViewModel declares a public or internal `MutableStateFlow`, `MutableSharedFlow` or `MutableLiveData`.
- Enforcement: agent

### SCALE-0047.8 No UI references in ViewModels
A ViewModel MUST NOT hold a reference to an Activity, Fragment, View, composable lambda
or Activity `Context`.

- Applies when: a ViewModel constructor or property has a type of `Context`, `Activity`, `Fragment`, `View` or a UI callback.
- Enforcement: agent

### SCALE-0047.9 Runtime permissions at the point of use
Dangerous permissions (location, camera, contacts, `POST_NOTIFICATIONS` on Android 13+)
MUST be requested when the feature is used, through `registerForActivityResult` with
`RequestPermission`, and the denied case MUST be handled without crashing.

- Applies when: the content requests a runtime permission, checks `checkSelfPermission`, or adds a permission to `AndroidManifest.xml`.
- Enforcement: agent

### SCALE-0047.10 Rethrow cancellation
Code that catches `Exception` or `Throwable` inside a coroutine MUST rethrow
`CancellationException`.

- Applies when: a `suspend` function or coroutine body contains `catch (e: Exception)`, `catch (e: Throwable)` or `runCatching`.
- Enforcement: agent

### SCALE-0047.11 Permission rationale
Before asking again for a permission the user denied, the app SHOULD show a rationale
when `shouldShowRequestPermissionRationale` returns true.

- Applies when: the content handles a denied runtime permission or requests a permission a second time.
- Enforcement: agent
