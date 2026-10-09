---
id: SCALE-0016
title: Cache keys, expiry, invalidation and HTTP cache headers
status: enforced
domain: caching
artifacts: [diff, code, spec]
languages: [any]
owner: platform
review_by: 2027-04-30
supersedes: []
summary: >
  Key design, TTLs, invalidation, stampede protection and HTTP caching headers for
  in-memory, Redis and CDN caches.
applies_when: >
  The content reads from, writes to or configures an in-memory, Redis, Memcached or CDN
  cache, or sets HTTP Cache-Control, ETag or Vary headers.
not_applies_when: >
  No cache is read, written or configured and no HTTP caching header is set.
---

# SCALE-0016: Cache keys, expiry, invalidation and HTTP cache headers

## Context

Restaurant pages, availability and search results are cached at the CDN, in Redis and in
process memory. Cache bugs are rarely loud: they show a diner a wrong price, a closed slot
or another user's data. These rules keep cached data correct, bounded and safe.

## Requirements

### SCALE-0016.1 Namespaced, versioned keys
Cache keys MUST start with the service name and a schema version, for example
`availability:v3:{restaurantId}:{date}`.

- Applies when: the content builds a cache key or key prefix for Redis, Memcached or an in-memory cache.
- Enforcement: agent

### SCALE-0016.2 Every entry expires
Every cache write MUST set a TTL, and in-memory caches MUST have a maximum size.

- Applies when: the content writes to a cache (`set`, `put`, `SETEX`, `@Cacheable`) or creates an in-memory cache (Caffeine, `lru-cache`, `functools.lru_cache`).
- Enforcement: agent

### SCALE-0016.3 Personal data keyed by user
Responses that contain user-specific or personal data MUST include the user id in the
cache key, or MUST NOT be cached in a shared cache.

- Applies when: the content caches a response or object that contains user profile, booking, payment or other per-user data.
- Enforcement: agent

### SCALE-0016.4 Invalidation on write
Code that updates a record served from cache MUST delete or update the cache entry after
the database commit, not before it.

- Applies when: the content updates or deletes a database record that is also stored in a cache.
- Enforcement: agent

### SCALE-0016.5 Stampede protection
Hot keys SHOULD be protected against stampedes with request coalescing, a lock, or early
probabilistic refresh.

- Applies when: the content implements a cache-aside read for data requested by many clients, such as restaurant pages, menus or search results.
- Enforcement: agent

### SCALE-0016.6 TTL jitter
TTLs for large batches of keys written at the same time SHOULD include random jitter of
about 10% so they do not expire together.

- Applies when: the content sets TTLs for many keys in a loop, a warm-up job or a bulk cache fill.
- Enforcement: agent

### SCALE-0016.7 Cache failure is not request failure
A cache read or write error MUST be treated as a cache miss and MUST NOT fail the request.

- Applies when: the content calls a Redis or Memcached client on a request path or handles its errors.
- Enforcement: agent

### SCALE-0016.8 Explicit Cache-Control
HTTP responses from public APIs and web pages MUST set an explicit `Cache-Control` header;
authenticated responses MUST use `private` or `no-store`.

- Applies when: the content sets response headers, adds an endpoint that returns data to browsers or apps, or configures CDN caching rules.
- Enforcement: agent

### SCALE-0016.9 Vary on content negotiation
Responses cached by a CDN that change with `Accept-Language` or `Accept-Encoding` MUST
declare those headers in `Vary` or include them in the CDN cache key.

- Applies when: the content returns localized or content-negotiated responses that pass through a CDN or shared cache.
- Enforcement: agent

### SCALE-0016.10 ETags on large resources
Endpoints returning large, rarely changing resources SHOULD support `ETag` and
`If-None-Match` so clients receive 304 responses.

- Applies when: the content adds or changes a GET endpoint for menus, photos, restaurant details or configuration.
- Enforcement: agent

### SCALE-0016.11 Stale while revalidate
CDN rules MAY use `stale-while-revalidate` for restaurant pages and search results to hide
origin latency.

- Applies when: the content configures CDN caching or `Cache-Control` for public pages.
- Enforcement: agent
