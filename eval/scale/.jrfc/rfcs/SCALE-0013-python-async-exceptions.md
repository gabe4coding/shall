---
id: SCALE-0013
title: Python async code, exceptions and packaging
status: enforced
domain: python
artifacts: [diff, code]
languages: [python]
owner: data-platform
review_by: 2027-03-31
supersedes: []
summary: >
  Asyncio usage, exception handling, data classes and project packaging in Python
  services, jobs and tools.
applies_when: >
  The content is or changes Python source code (.py files) or a Python project file
  (pyproject.toml), including async functions, exception handling or data classes.
not_applies_when: >
  The content is not Python source code or a Python project file.
---

# SCALE-0013: Python async code, exceptions and packaging

## Context

Our Python code runs FastAPI services, Kafka consumers, Airflow tasks and ML jobs. The
common failures are blocking calls inside the event loop, exceptions swallowed by broad
handlers and projects that cannot be rebuilt the same way twice.

## Requirements

### SCALE-0013.1 No blocking calls in async functions
An `async def` function MUST NOT call blocking I/O such as `requests`, `time.sleep`, `open()`
on network storage or a synchronous database driver; it has to use an async client or
`asyncio.to_thread`.

- Applies when: the content calls `requests.`, `time.sleep`, `psycopg2`, `urllib` or other synchronous I/O inside an `async def` function.
- Enforcement: agent

### SCALE-0013.2 Tasks are awaited or kept
Every `asyncio.create_task` result MUST be awaited, gathered, or stored in a task group so
that its exceptions are not lost.

- Applies when: the content calls `asyncio.create_task`, `asyncio.ensure_future` or `loop.create_task`.
- Enforcement: agent

### SCALE-0013.3 No bare except
Code MUST NOT use a bare `except:` or `except BaseException:` except at the top level of a
process, where it has to re-raise after logging.

- Applies when: the content writes an `except:` clause without an exception type, or catches `BaseException`.
- Enforcement: linter

### SCALE-0013.4 Broad exceptions re-raised or reported
`except Exception` blocks MUST either re-raise, or report the error to Sentry and return an
explicit failure value; they MUST NOT silently `pass`.

- Applies when: the content writes an `except Exception` clause or an except clause whose body is `pass` or `continue`.
- Enforcement: agent

### SCALE-0013.5 Exception chaining
Exceptions raised while handling another exception SHOULD use `raise ... from err` to keep
the original cause.

- Applies when: the content raises a new exception inside an `except` block.
- Enforcement: agent

### SCALE-0013.6 Domain exceptions
Libraries and services SHOULD define their own exception classes for domain errors instead
of raising `Exception` or `ValueError` with a message string.

- Applies when: the content raises `Exception(...)`, `RuntimeError(...)` or `ValueError(...)` for a business rule violation.
- Enforcement: agent

### SCALE-0013.7 Frozen data classes for values
Value objects and messages SHOULD be `@dataclass(frozen=True, slots=True)` or Pydantic
models with `frozen=True`, rather than plain dicts.

- Applies when: the content defines a data class, NamedTuple, Pydantic model or passes structured records as dicts.
- Enforcement: agent

### SCALE-0013.8 Mutable defaults
Functions and data classes MUST NOT use mutable default values (`[]`, `{}`, `set()`);
data classes have to use `field(default_factory=...)`.

- Applies when: the content defines a function parameter or data class field with a list, dict or set default.
- Enforcement: agent

### SCALE-0013.9 Project managed with uv
Python projects MUST declare dependencies in `pyproject.toml` and commit a `uv.lock`; new
projects MUST NOT add `requirements.txt` or `setup.py`.

- Applies when: the content adds or changes `pyproject.toml`, `requirements.txt`, `setup.py` or `setup.cfg`.
- Enforcement: agent

### SCALE-0013.10 Python version
Projects MUST declare `requires-python` with a supported minor version (3.11 or later).

- Applies when: the content adds or changes `requires-python` or the Python version of a project, Dockerfile or CI job.
- Enforcement: agent

### SCALE-0013.11 Structured concurrency
New async code MAY use `asyncio.TaskGroup` in place of `asyncio.gather` for groups of
related tasks.

- Applies when: the content runs several coroutines concurrently with `asyncio.gather` or `asyncio.wait`.
- Enforcement: agent
