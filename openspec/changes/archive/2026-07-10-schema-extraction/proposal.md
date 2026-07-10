# Proposal: Schema Extraction

## Intent

Provide a safe, read-only snapshot of table and column metadata from each configured SQL Server profile. This supplies the normalized input required by later drift comparison while preserving profile-secret boundaries.

## Scope

### In Scope
- Connect to each supplied `ConnectionProfile` through a short-lived `pyodbc` connection.
- Extract tables and columns from SQL Server `INFORMATION_SCHEMA` views: names, data type, size, numeric precision, numeric scale, and nullability.
- Normalize results into immutable, profile-named in-memory snapshots using schema-qualified table identity.
- Translate connection and catalog-query failures into actionable, profile-safe domain errors; add mocked unit tests and optional externally configured integration tests.

### Out of Scope
- Snapshot comparison, drift/mismatch detection, rename heuristics, reports, TUI/CLI integration, or persistence.
- Writes, migrations, schema changes, `NOLOCK`, and parsing/reconstructing connection strings.
- PK/FK/index extraction, `sys.*` catalog queries, DDL-file discovery, and parallel extraction.

## Capabilities

### New Capabilities
- `schema-extraction`: Read configured SQL Server profiles and return normalized, secret-safe table-and-column metadata snapshots.

### Modified Capabilities
None. `connection-profile-config` continues to provide opaque, validated profiles; this capability only consumes them.

## Approach

Add a narrow connector boundary that passes the opaque profile connection string only to `pyodbc.connect` and deterministically closes cursor and connection. A discovery service issues set-based `INFORMATION_SCHEMA.TABLES` / `INFORMATION_SCHEMA.COLUMNS` queries, grouping rows by `(TABLE_SCHEMA, TABLE_NAME)` and column name. Preserve null/non-applicable size, precision, and scale rather than fabricating values. Unit tests mock driver objects; optional integration tests require separately supplied test credentials.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `pyproject.toml` | Modified | Add `pyodbc` runtime dependency. |
| `src/schema_comparator/connectors/` | New | Short-lived, profile-safe SQL Server connection boundary. |
| `src/schema_comparator/discovery/` | New | Snapshot models, catalog query, row normalization, and errors. |
| `tests/unit/` | New | Mocked connector/discovery and error-redaction tests. |
| `tests/integration/` | Modified | Optional SQL Server contract tests, excluded from normal unit execution. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `pyodbc` installation lacks a compatible Microsoft ODBC Driver 17/18 | Med | Document the host prerequisite and return driver-safe actionable errors. |
| Principal lacks metadata visibility | Med | Identify only the profile name and access prerequisite; do not claim completeness. |
| Driver exceptions leak infrastructure or secret fragments | Med | Never surface/log raw ODBC exception text, connection/cursor objects, or connection strings. |
| Same table name exists in multiple schemas | Med | Use `(schema, table)` as the table identity. |

## Rollback Plan

Revert the extraction modules, tests, and `pyodbc` dependency in one change. No database rollback is required: the capability performs read-only catalog queries, stores no metadata, and executes no SQL writes or migrations.

## Dependencies

- Python package `pyodbc`.
- Microsoft ODBC Driver 17 or 18 for SQL Server installed on each execution host, plus network and catalog-read permissions for configured profiles.

## Success Criteria

- [ ] Given a valid configured profile and permitted SQL Server, extraction returns its profile name plus every visible table and requested column attributes, retaining null for non-applicable attributes.
- [ ] Tables with identical names in different schemas remain distinct snapshots.
- [ ] Connection and query failures name the profile and actionable prerequisite without exposing a connection string, ODBC text, server, database, user, or password.
- [ ] Unit tests exercise normalization, cleanup, and error redaction without database/network access; optional integration tests remain separately configured.

**Branch advisory:** Before `sdd-apply` begins, a feature branch SHOULD be created following the `<tipo>/<descripción>` convention defined in the `branch-pr` skill (e.g. `git checkout -b feat/my-change main`). This note is SHOULD, not MUST.
