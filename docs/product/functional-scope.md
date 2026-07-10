# Functional Scope — SQL Server Schema Comparator

## Decision

First usable slice (v1) covers: a TUI where the developer adds and persists
SQL Server connection strings, sees them listed by database name, checks
which ones to include, extracts table/column metadata via live connection
for the checked set, compares across all checked databases, and produces a
drift report in HTML (primary) with a PDF export option, plus a console/TUI
summary. PK/FK/index comparison are next-slice extensions; Excel/CSV export
moves to v2, not blocking v1.

## Capabilities

| # | Capability | Priority | Notes |
|---|---|---|---|
| 1 | TUI shell | Must (v1) | Textual-based terminal app: connections list screen + run/report screens. Entry point for all other capabilities below. |
| 2 | Saved-connection management | Must (v1) | Add/edit/delete a named SQL Server connection string from within the TUI; persisted locally (YAML, git-ignored) so it's available on the next run without re-entering it. No credentials hardcoded in source. |
| 3 | Connection list view with selection | Must (v1) | TUI screen listing all saved connections by name (and resolved database name once connected), with a checkbox per row to mark which ones are included in the current comparison run. |
| 4 | Schema extraction (tables/columns) | Must (v1) | Table name, column name, data type, size/precision/scale, nullable, ordinal position, via live connection to `INFORMATION_SCHEMA`/`sys.*` catalog views, for each checked connection. |
| 5 | N-way schema comparison | Must (v1) | Compares all checked databases against each other simultaneously (not just pairwise), using a normalized "union of all known objects" baseline. |
| 6 | Missing-table detection | Must (v1) | Report tables present in some databases but absent in others. |
| 7 | Missing-column detection | Must (v1) | Report columns present in some databases but absent in others, for tables that exist in more than one database. |
| 8 | Type/size/nullability mismatch detection | Must (v1) | For columns with the same name across databases, flag differing data type, length/precision/scale, or nullability. |
| 9 | Likely-rename detection | Should (v1) | Heuristic match (e.g. same type/shape, high name similarity, or same ordinal position) to flag columns that probably represent the same field under different names across databases. |
| 10 | Report generation — HTML | Must (v1) | HTML report (primary/source-of-truth, shareable/scannable, grouped by table, color-coded by diff type) + in-TUI/console summary (quick overview after a run completes). |
| 11 | Report generation — PDF export | Must (v1) | Export the same HTML report to PDF via `xhtml2pdf`, for sharing/archiving as a static file. |
| 12 | Report generation — Excel/CSV export | Should (v2) | Additional export formats for further analysis/filtering in spreadsheet tools. Moved from v1.1 to v2 per explicit decision to prioritize PDF first. |
| 13 | Primary key / foreign key / index comparison | Could (v1.1+) | Best-effort, secondary to tables/columns per user's stated priority. |
| 14 | DDL-export-based discovery (offline mode) | Could (later) | Fallback discovery source when live DB connection isn't available; v1 focuses on live connection only. |

## Out of Scope (see brief.md Non-Goals)

- Schema migration/write operations.
- Continuous/scheduled execution or server component.
- Data-level (row content) comparison.
- Automatic schema reconciliation.

## Primary Use Case (Given/When/Then, informal)

**Detect schema drift across microservices**

- Given a set of SQL Server connection strings already saved in the TUI
  from previous sessions,
- When the developer opens the TUI, checks the databases to include in
  this run, and triggers the comparison,
- Then the tool connects to each checked database, extracts table/column
  metadata, compares all checked schemas, and produces an HTML report
  (plus an in-TUI/console summary) showing missing tables, missing
  columns, likely renames, and type/size/nullability mismatches, grouped
  so the developer can quickly spot which database is the outlier.

**Add a new connection**

- Given the developer has a SQL Server connection string for a
  microservice not yet tracked,
- When they add it by name through the TUI,
- Then it is persisted locally (git-ignored) and appears in the connection
  list on this and future runs, available to check for comparison.

Formal Given/When/Then scenarios with RFC 2119 keywords belong in
`openspec/specs/**/spec.md`, written during the first `sdd-spec` phase for
the first capability change — not here. This document captures scope and
priority only.
