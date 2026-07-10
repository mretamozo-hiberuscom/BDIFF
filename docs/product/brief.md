# Product Brief — SQL Server Schema Comparator

## Decision

Build a local-only Python **TUI** (terminal UI) tool that lets developers
save and manage SQL Server connection strings, browse the saved connections
by database name, check which ones to include in a run, then extracts
schema metadata (tables and columns as the priority; PK/FK/indexes as
best-effort), compares the checked N databases against each other, and
generates human-readable drift reports so developers can quickly answer
"which database differs from the rest, and where?"

## Problem

The team runs several microservices, each with its own SQL Server database,
in the insurance domain. The databases are supposed to share overlapping
data structures (many tables/columns represent the same business concepts),
but because several developers evolve each database independently, drift
accumulates silently:

- A column exists in one service's database but not in another's.
- A table is missing entirely in one database.
- The same concept is named differently across databases (e.g. `client_id`
  vs `customer_id`) and nobody notices they are "the same field."
- The same column name exists everywhere but with different data type,
  size/precision/scale, or nullability.

There is currently no tooling to detect this drift. It is discovered
reactively, usually when something breaks in integration or a migration.

## Who

- **Primary user**: the requesting developer/team lead, running the tool
  locally against local or dev-environment SQL Server instances.
- **Secondary users**: other developers on the same team who read the
  generated reports to understand where their service's schema diverges.

This is an internal developer tool, not a product for the insurance
business itself, and not a production/customer-facing system.

## Outcome

A developer opens the TUI locally, sees the list of previously saved
database connections (added once, persisted for reuse), checks which ones
should be part of this run (not necessarily all of them every time), runs
the comparison from within the TUI, and gets a report that clearly shows,
per table/column:

- Which databases have it and which don't.
- Likely renames (same-shape column present under a different name).
- Type/size/nullability mismatches for columns that exist in more than one
  database under the same name.
- A quick way to see "which database is the outlier" across the whole set.

## Explicit Non-Goals (v1)

- Not a schema migration tool — it does not write/alter any database.
- Not a continuously running service — single local execution, on demand
  (the TUI runs interactively in a terminal session, not as a background
  process).
- No web UI/server component in the initial scope — terminal-only.
- No automatic reconciliation/merge of schemas — humans decide what to do
  with the reported drift.
- Not focused on data-level comparison (row counts, data content) — schema
  (structure) only.

## Constraints (known)

| Constraint | Value | Source |
|---|---|---|
| Execution mode | Local only, on-demand interactive TUI run | User instruction |
| Connection management | Connection strings entered once, persisted locally, reused across runs; user selects (checks) which saved connections to include per comparison run | User instruction |
| Target DB engine | SQL Server (multiple instances/databases) | User instruction |
| Domain | Insurance microservices sharing overlapping schema | User instruction |
| Credentials | Must be local config, never hardcoded in source | User instruction |
| Team size context | Multiple developers touching separate DBs independently | User instruction |
| Approx. number of databases to compare | Unknown — assumed small-to-medium (roughly 3-20) for a local, non-distributed comparison run | Assumption, see Open Questions |

## Open Questions

None blocking at this stage — see `docs/architecture/technical-baseline.md`
for the technical decisions taken with reasonable defaults where the user
had no strong preference. The one soft-unknown (exact number of databases)
is documented as an assumption above and should be validated against the
real environment before performance-sensitive design choices (e.g.
parallelizing extraction) are finalized.
