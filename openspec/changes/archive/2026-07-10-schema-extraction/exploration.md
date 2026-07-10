# Exploration: Schema Extraction

## Current State

The archived `connection-profile-config` capability already provides validated,
secret-redacting `ConnectionProfile` values with opaque ODBC connection strings.
The `connectors/` and `discovery/` packages are intentional empty extension
points; `pyproject.toml` currently contains PyYAML only, so no SQL Server driver
is installed. No code currently connects to SQL Server or performs discovery.

## Affected Areas

- `src/schema_comparator/connectors/` — add the narrow-lived `pyodbc` connection boundary.
- `src/schema_comparator/discovery/` — add snapshot models and catalog-query extraction.
- `src/schema_comparator/config/models.py` — consume `ConnectionProfile` without parsing or logging its connection string.
- `pyproject.toml` — add the runtime `pyodbc` dependency; the host must also have Microsoft ODBC Driver 17 or 18.
- `tests/unit/` — mock `pyodbc.connect` and cursor rows; no database/network access.
- `tests/integration/` — optional real/local SQL Server catalog-query contract tests.

## Approaches

1. **Direct pyodbc with INFORMATION_SCHEMA views** — create a short-lived connection per configured profile and issue one set-based query joining `INFORMATION_SCHEMA.TABLES` and `INFORMATION_SCHEMA.COLUMNS`.
   - Pros: matches the architecture baseline; minimal dependency surface; portable SQL Server metadata API; easy to mock as rows; read-only extraction boundary.
   - Cons: metadata visibility follows the connected principal's permissions; type attributes are nullable for types where they do not apply; the ODBC driver remains an external machine prerequisite.
   - Effort: Medium.

2. **Direct pyodbc with sys catalog views** — use `sys.tables`, `sys.columns`, and `sys.types` as the primary extraction query.
   - Pros: richer SQL Server-specific metadata and a natural future path to keys, foreign keys, and indexes.
   - Cons: more SQL Server-specific mapping now; unnecessary complexity for this slice; harder query and mock fixtures.
   - Effort: Medium.

3. **SQLAlchemy reflection** — add an ORM/reflection layer above pyodbc.
   - Pros: abstraction could support other database engines later.
   - Cons: contradicts the direct-pyodbc decision; adds a large dependency and reflection behavior not needed for SQL Server-only, read-only metadata extraction.
   - Effort: High.

## Recommendation

Use direct `pyodbc` with `INFORMATION_SCHEMA.TABLES` and
`INFORMATION_SCHEMA.COLUMNS` for this slice. Normalize rows into immutable
snapshot values keyed by the qualified table identity (`TABLE_SCHEMA` + table
name) and column name. Preserve `DATA_TYPE`, `CHARACTER_MAXIMUM_LENGTH`,
`NUMERIC_PRECISION`, `NUMERIC_SCALE`, and `IS_NULLABLE`; non-applicable size,
precision, and scale values remain absent/null rather than being invented.

Keep connection and query execution behind a small connector/discovery boundary.
The extractor receives a `ConnectionProfile`, passes the opaque string only to
`pyodbc.connect`, closes cursor and connection deterministically, and returns a
profile-named in-memory snapshot. It must not compare snapshots, produce a
report, invoke the TUI, write to SQL Server, or persist metadata.

For tests, unit-test row-to-model normalization and error translation with
autospecced `pyodbc` connection/cursor mocks. Add optional integration tests
only when a local or controlled SQL Server is available; they must use
test-only, externally supplied credentials and never run as the normal unit
suite.

Connection failures and catalog-query failures should become domain errors that
identify the profile name and actionable prerequisites (network/driver/access),
never the raw connection string, ODBC exception text, server, database, user,
or password. Avoid logging connection objects, cursor objects, exception text,
or snapshots that could carry connection context. Existing profile `repr`
redaction is helpful but is not sufficient as the sole protection.

## Risks

- `pyodbc` installation also requires a compatible Microsoft ODBC Driver on each developer machine; a Python dependency alone is insufficient.
- SQL Server metadata visibility is permission-dependent, so an underprivileged profile can yield an incomplete snapshot or an access failure.
- SQL Server permits same-named tables in different schemas; omitting `TABLE_SCHEMA` from identity would silently merge distinct tables.
- Driver exceptions can reveal infrastructure or connection-string fragments if wrapped or logged verbatim.
- `INFORMATION_SCHEMA` deliberately does not cover later PK/FK/index work; that extension should introduce `sys.*` queries separately.

## Ready for Proposal

Yes — the confirmed scope supports a focused extraction capability. The proposal/spec should make qualified table identity, the exact snapshot API, and the profile-safe error taxonomy normative while retaining the stated exclusions: no N-way comparison, mismatch detection, reports, UI, writes, or migrations.
