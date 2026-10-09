# Known effects (`effects.yaml`)

A rule about network calls, databases or processes is selected only when Jev sees that the code
does that. When a library hides it (`get_parser(lang)` downloads a grammar, `db.Query` goes to the
network), add an entry to `corpus/effects.yaml` (or `.shall/effects.yaml`):

```yaml
- id: go-database-sql
  module: database/sql                     # import spec, prefix match
  calls: [Open]                            # called through the import: sql.Open(...)
  methods: [Query, QueryRow, Exec]         # on a receiver from the module: db.Query(...)
  effect: runs a query on a remote database over the network
  owner: data-platform
```

- `effect` is a literal clause ("<call> <effect>").
- Prefer `calls` to `methods`: a method name matches only when its receiver traces to the module.
  A false fact misleads more than a missing one.
- The owner reviews entries like statements; `shall lint` checks the fields.
