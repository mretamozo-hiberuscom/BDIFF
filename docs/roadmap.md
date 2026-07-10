# Roadmap — SQL Server Schema Comparator

## Milestone 1 (v1) — Core drift detection, local run

First usable slice. Goal: a developer can run the tool locally against
configured SQL Server connections and get a report showing table/column
drift.

- [x] Connection profile config (multi-database, no hardcoded credentials)
- [x] Schema extraction via live connection (tables + columns: name, type,
      size/precision/scale, nullable)
- [x] N-way comparison engine (union-of-objects baseline diff)
- [x] Missing-table detection
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

`scaffold-project` is done (archived: `openspec/changes/archive/2026-07-10-scaffold-project/`).
`pyproject.toml`, the `src/schema_comparator/` package skeleton, and pytest
configuration are in place on `feat/scaffold-project`, verified PASS.

`connection-profile-config` is done (archived: `openspec/changes/archive/2026-07-10-connection-profile-config/`).

`schema-extraction` is done (archived: `openspec/changes/archive/2026-07-10-schema-extraction/`).

`comparison-engine` is done (archived: `openspec/changes/archive/2026-07-10-comparison-engine/`),
including missing-table detection as its first functional diff category.
Missing-column detection and type/size/nullability mismatch detection
remain separate, not-yet-started roadmap items.

Next up: **missing-column detection**, as its own SDD change.
