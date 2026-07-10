# Roadmap — SQL Server Schema Comparator

## Milestone 1 (v1) — Core drift detection, local run

First usable slice. Goal: a developer can run the tool locally against
configured SQL Server connections and get a report showing table/column
drift.

- [ ] Connection profile config (multi-database, no hardcoded credentials)
- [ ] Schema extraction via live connection (tables + columns: name, type,
      size/precision/scale, nullable)
- [ ] N-way comparison engine (union-of-objects baseline diff)
- [ ] Missing-table detection
- [ ] Missing-column detection
- [ ] Type/size/nullability mismatch detection
- [ ] HTML report generation
- [ ] PDF export of the HTML report (`xhtml2pdf`)
- [ ] Console/TUI summary output

## Milestone 2 (v1.1) — Better signal

- [ ] Likely-rename heuristic detection (name similarity / shape match)
- [ ] PK/FK/index best-effort comparison

## Milestone 3 (v2) — Spreadsheet export

- [ ] CSV/Excel report export

## Milestone 4 (later, not committed)

- [ ] DDL-export-file discovery mode (offline / no direct DB access)
- [ ] Parallel extraction if database count grows large (50+)
- [ ] Configurable ignore-list (known intentional differences, e.g. legacy
      tables that are expected to diverge)

## Explicitly Deferred / Out of Scope

- Schema migration or write operations against target databases.
- Continuous/scheduled execution or a server component.
- Data-level (row content) comparison.
- Automatic schema reconciliation/merge.

## Status

No code exists yet. This roadmap was created during `sdd-foundation`
alongside the product and architecture baseline. The first SDD change
should be a scaffold change (e.g. `scaffold-project`) that sets up
`pyproject.toml`, the `src/schema_comparator/` package skeleton, and
pytest configuration, followed by the Milestone 1 capabilities above as
their own SDD changes.
