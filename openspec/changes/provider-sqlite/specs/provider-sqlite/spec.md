# Spec — `provider-sqlite`

## Specification Delta: SQLite Provider Capabilities and Introspection

### Requirement: SQLite Provider Registration & Connection
- **SHALL** register provider ID `sqlite` in `ProviderRegistry`.
- **SHALL** accept local file system paths and `:memory:` connection strings.
- **SHALL** use Python standard library `sqlite3` without requiring extra `pip` dependencies.

### Requirement: SQLite Schema Introspection
- **SHALL** query `sqlite_schema` (or `sqlite_master`) for base tables (excluding system tables starting with `sqlite_`).
- **SHALL** query `PRAGMA table_xinfo` (falling back to `PRAGMA table_info`) to extract column definitions.
- **SHALL** represent schema name as `"main"` for standard database tables.
- **SHALL** map native type string, char length, precision, scale, nullability, ordinal position, default expression, and identity indicator into `ColumnSnapshot`.

### Requirement: SQLite DDL Generation & Table Rebuild
- **SHALL** quote identifiers using double quotes `"table"` and `"column"`.
- **SHALL** generate `CREATE TABLE IF NOT EXISTS` for missing tables.
- **SHALL** generate `ALTER TABLE "table" ADD COLUMN` for missing columns.
- **SHALL** generate a `table rebuild` migration block (`CREATE TABLE "table_tmp" AS SELECT ...`, `DROP TABLE "table"`, `ALTER TABLE "table_tmp" RENAME TO "table"`) wrapped in `PRAGMA foreign_keys = OFF; BEGIN TRANSACTION; ... COMMIT; PRAGMA foreign_keys = ON;` when column attribute discrepancies require table structural changes.
