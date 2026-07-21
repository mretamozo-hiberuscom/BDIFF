# Specification: Oracle Provider

## Feature: Oracle Schema Discovery and DDL Rendering

### Scenario: Introspect Oracle database catalog
Given an Oracle connection profile
When schema discovery is requested for an Oracle database target
Then `OracleProvider` MUST query `ALL_TABLES` and `ALL_TAB_COLUMNS`
And return a `SchemaSnapshot` with table and column metadata mapping `OWNER` to schema name.

### Scenario: Format Oracle native data types
Given Oracle native column attributes (`NUMBER`, `VARCHAR2`, `CLOB`, `DATE`)
When formatting column definitions or types
Then `NUMBER(p, s)` MUST include precision and scale when present
And `VARCHAR2(n)` MUST specify character length.

### Scenario: Quoting Oracle identifiers
Given table or column names
When generating SQL queries or DDL for Oracle
Then identifiers MUST be quoted using double quotes (e.g. `"HR"."EMPLOYEES"`).

### Scenario: Generate DDL migration statements
Given schema discrepancies targeting an Oracle database
When DDL script generation is requested
Then missing columns MUST generate `ALTER TABLE "OWNER"."TABLE" ADD ("COL" TYPE NULLABILITY)`
And modified column types MUST generate `ALTER TABLE "OWNER"."TABLE" MODIFY ("COL" TYPE NULLABILITY)`.
