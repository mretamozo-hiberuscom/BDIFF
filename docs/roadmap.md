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
- [x] Missing-column detection
- [x] Type/size/nullability mismatch detection
- [x] HTML report generation
- [x] PDF export of the HTML report (`xhtml2pdf`)
- [x] Console/TUI summary output

## Milestone 2 (v1.1) — Better signal

- [ ] Likely-rename heuristic detection (name similarity / shape match)
- [ ] PK/FK/index best-effort comparison
- [x] Interactive TUI (`textual`), opt-in via `--tui` flag, alongside the
      existing always-on HTML/PDF/console outputs (archived:
      `openspec/changes/archive/2026-07-10-interactive-tui/`)
- [x] Accept ADO.NET-style connection string fragments (`Data Source=`,
      `Initial Catalog=`, `User Id=`, ...) and translate them to the ODBC
      keywords `pyodbc` requires, auto-prepending `Driver=...`. Revises
      technical-baseline.md decision #2 (archived:
      `openspec/changes/archive/2026-07-10-connection-string-translation/`).
- [ ] Expand the TUI to manage connection profiles (list, add, edit,
      delete, checkbox selection of which profiles to compare), matching
      the original technical-baseline.md decision #7 vision — supersedes
      the current read-only-viewer-only scope shipped in
      `interactive-tui`.

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

The remaining Milestone 1 scope (missing-column detection, type/size/nullability
mismatch detection, HTML report generation, PDF export, console/TUI summary)
is split into two SDD changes instead of one, to keep each change reviewable:

- **Change A — `diff-detection-completion`** is done (archived:
  `openspec/changes/archive/2026-07-10-diff-detection-completion/`).
  Missing-column detection and type/size/nullability mismatch detection are
  implemented, verified PASS (2 non-critical warnings, see its verify-report),
  and merged into the `comparison-engine` baseline spec.
- **Change B — `reporting-and-output`** is done (archived:
  `openspec/changes/archive/2026-07-10-reporting-and-output/`). HTML report
  generation, PDF export (`xhtml2pdf`), and console summary output are
  implemented, verified PASS (1 cosmetic warning, 1 process suggestion, see
  its verify-report), with a new `reporting-and-output` baseline spec at
  `openspec/specs/reporting-and-output/spec.md`.

**Milestone 1 is complete.** All items are implemented and archived. Next up:
Milestone 2 (`likely-rename heuristic detection`, `PK/FK/index comparison`),
as its own SDD change(s) — not started yet.
