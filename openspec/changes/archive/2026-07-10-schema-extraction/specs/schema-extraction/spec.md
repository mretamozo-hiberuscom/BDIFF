# Schema Extraction Specification

## Purpose

Provide a profile-named, in-memory, read-only snapshot of visible SQL Server
table and column metadata for later schema comparison.

## Clarifications

### Session 2026-07-10

- Q: Should schema extraction enforce an explicit timeout on connection
  establishment and the catalog query? → A: **enforce-default-timeout** — the
  system MUST enforce an explicit timeout (default ~30s, a sane named
  constant) on both connection establishment and the catalog query. On
  expiry, the timeout MUST be translated using the same profile-safe
  "network/connectivity" error category already defined in
  REQ-schema-extraction-005, without exposing raw ODBC/driver details.

## Requirements

### Requirement: Extract Table and Column Metadata {#REQ-schema-extraction-001}

The system MUST extract the visible base tables and their columns for one
valid `ConnectionProfile`. Each snapshot SHALL retain the profile name and
immutable table and column metadata. A table SHALL include its schema and
name. A column SHALL include its name, data type, character maximum length,
numeric precision, numeric scale, nullability, and ordinal position. The
system MUST preserve null/non-applicable size, precision, and scale values;
it MUST NOT invent substitute values. Views and metadata outside this listed
table/column slice MUST NOT be included.

#### Scenario: Visible base-table metadata is returned

- GIVEN a permitted profile whose catalog exposes a base table and columns
- WHEN schema extraction is requested for that profile
- THEN the returned in-memory snapshot SHALL identify the profile and include
  each visible base table with all required column attributes
- AND non-applicable attribute values SHALL remain null

#### Scenario: Empty visible catalog returns an empty snapshot

- GIVEN a permitted profile with no visible base tables
- WHEN schema extraction is requested
- THEN the system SHALL return a successful snapshot with no tables

### Requirement: Preserve Qualified Table Identity {#REQ-schema-extraction-002}

The system MUST identify a table by the ordered pair of its schema name and
table name. It SHALL NOT merge, overwrite, or otherwise treat tables with the
same name in different schemas as one table. Column identity within a table
MUST be its column name.

#### Scenario: Same-named tables in distinct schemas remain distinct

- GIVEN visible tables `sales.Invoice` and `archive.Invoice`
- WHEN schema extraction normalizes their metadata
- THEN the snapshot SHALL contain two distinct table entries
- AND each entry SHALL retain its originating schema name

### Requirement: Return Deterministically Ordered Snapshots {#REQ-schema-extraction-003}

The system MUST return snapshot tables in ascending schema-name then table-name
order, and columns in ascending ordinal-position then column-name order. This
ordering SHALL be applied independently of catalog row delivery order so
equivalent visible metadata produces equivalent ordered snapshots.

#### Scenario: Unordered catalog rows produce a stable snapshot

- GIVEN equivalent table and column metadata is delivered in differing row
  orders across two extraction attempts
- WHEN each attempt is normalized
- THEN both snapshots SHALL order tables by schema and table name
- AND columns SHALL order by ordinal position and then column name

### Requirement: Read-Only, Ephemeral Extraction {#REQ-schema-extraction-004}

The system MUST use a short-lived connection only to read SQL Server metadata
for the supplied profile and MUST release all extraction resources before
returning or raising an error. It MUST NOT execute data writes, DDL, schema
writes, migrations, persistence, `NOLOCK`, comparison, report generation, or
TUI actions. It MUST NOT parse, reconstruct, expose, or persist the opaque
profile connection string.

#### Scenario: Successful extraction leaves no database mutation

- GIVEN a valid permitted profile
- WHEN extraction completes successfully
- THEN it SHALL return only the in-memory metadata snapshot
- AND it SHALL not write data or alter the database schema

#### Scenario: Failure still releases extraction resources

- GIVEN extraction has acquired resources and metadata retrieval fails
- WHEN the failure is handled
- THEN all acquired resources SHALL be released before the domain error is
  exposed to the caller

### Requirement: Provide Profile-Safe Extraction Errors {#REQ-schema-extraction-005}

The system MUST translate connection and catalog-read failures into actionable
domain errors that identify the profile name and the relevant prerequisite
(driver availability, network/connectivity, or metadata access). Error
messages and emitted logs MUST NOT include a connection string, raw driver
exception text, server, database, username, password, connection object, or
cursor object. The system SHALL NOT present a raw driver traceback as the
primary user-facing error.

The system MUST enforce an explicit timeout on both connection establishment
and the catalog query, using a sane named default constant of approximately
30 seconds. When either the connection attempt or the catalog query exceeds
its timeout, the system MUST treat the expiry as a connection failure and
translate it using the same "network/connectivity" error category defined in
this requirement, naming the profile and the connectivity prerequisite
without exposing raw ODBC/driver details.

#### Scenario: Connection failure is safely translated

- GIVEN the connection attempt for profile `claims-service` fails
- WHEN extraction handles the failure
- THEN it SHALL raise an actionable domain error naming `claims-service` and
  a connection prerequisite without raw driver details or secret material

#### Scenario: Catalog access failure is safely translated

- GIVEN the connected profile cannot read required metadata
- WHEN extraction handles the catalog-read failure
- THEN it SHALL raise an actionable domain error naming the profile and the
  metadata-access prerequisite without infrastructure or secret details

#### Scenario: Connection establishment timeout is safely translated

- GIVEN the connection attempt for profile `claims-service` exceeds the
  configured default timeout
- WHEN extraction handles the timeout expiry
- THEN it SHALL raise an actionable domain error naming `claims-service` and
  the network/connectivity prerequisite without raw driver details or secret
  material

#### Scenario: Catalog query timeout is safely translated

- GIVEN the catalog query for a connected profile exceeds the configured
  default timeout
- WHEN extraction handles the timeout expiry
- THEN it SHALL raise an actionable domain error naming the profile and the
  network/connectivity prerequisite without raw driver details or secret
  material

### Requirement: Support Database-Free Unit Verification {#REQ-schema-extraction-006}

The extraction boundary MUST permit unit verification with substitute
connection/cursor behavior and supplied catalog rows, without a live SQL
Server, network access, installed ODBC driver, or credentials. Unit tests
SHALL verify metadata normalization, qualified identity, deterministic order,
resource cleanup, and safe error translation. Integration verification MAY use
externally supplied test-only credentials and MUST remain separate from the
normal unit suite.

#### Scenario: Unit normalization runs without SQL Server

- GIVEN substitute catalog rows and substitute connection/cursor behavior
- WHEN unit verification exercises extraction normalization
- THEN it SHALL verify the resulting snapshot without network or database
  access

#### Scenario: Optional integration verification is isolated

- GIVEN integration credentials have not been explicitly supplied
- WHEN the normal unit suite is run
- THEN no live SQL Server extraction SHALL be attempted
