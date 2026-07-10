# Design: Schema Extraction

Change: `schema-extraction`
Status: design (phase artifact)
Scope: read-only, in-memory extraction of table/column metadata from one
`ConnectionProfile` via a short-lived `pyodbc` connection and
`INFORMATION_SCHEMA` catalog queries. No comparison, report, TUI/CLI
integration, or persistence (all deferred to later capabilities).

This design realizes the six requirements in
`openspec/changes/schema-extraction/specs/schema-extraction/spec.md` and the
clarify decision recorded in `state.yaml` (explicit ~30s timeout on both
connection establishment and the catalog query, translated via the
network/connectivity error category). It builds on, and does not duplicate,
`openspec/changes/archive/2026-07-10-connection-profile-config/design.md`:
this capability only *consumes* `ConnectionProfile` (name +
opaque connection string) — it never parses, reconstructs, or logs the
connection string.

---

## 1. Module / file layout

```text
src/schema_comparator/connectors/
  __init__.py     # connect() context manager: the ONLY pyodbc.connect call site
src/schema_comparator/discovery/
  __init__.py     # public API surface: re-exports models, errors, extract_schema
  models.py       # ColumnSnapshot, TableSnapshot, SchemaSnapshot (frozen dataclasses)
  queries.py      # CATALOG_QUERY_SQL constant + row -> snapshot normalization
  errors.py       # DiscoveryError hierarchy + connect/query failure translation
  service.py      # extract_schema(profile, ...) orchestration
```

Rationale for the connectors/discovery split (mirrors the proposal's
"Affected Areas" table exactly):

- `connectors/` is a **narrow boundary**: its only job is to call
  `pyodbc.connect(profile.connection_string, timeout=...)`, enforce the
  login timeout, and guarantee the connection is closed. It does **not**
  translate driver errors — it lets `pyodbc.Error` propagate unchanged, so
  it never needs to know about domain error categories. This keeps the one
  module that touches `pyodbc.connect` trivially small and auditable for
  "does this ever build/expose a connection string" reviews.
- `discovery/` owns **everything else**: the catalog query text, row
  normalization into the snapshot model, deterministic ordering, and *all*
  error translation (both connect-phase and query-phase failures become
  `DiscoveryError` subclasses here). This matches the proposal's Affected
  Areas row: `discovery/` = "Snapshot models, catalog query, row
  normalization, and errors."
- Neither module imports `schema_comparator.config` beyond the
  `ConnectionProfile` type it receives as a parameter — no coupling to the
  YAML loader.

### Public API (`discovery/__init__.py`)

```python
from schema_comparator.discovery.models import (
    ColumnSnapshot,
    TableSnapshot,
    SchemaSnapshot,
)
from schema_comparator.discovery.errors import (
    DiscoveryError,
    DriverUnavailableError,
    ConnectionFailedError,
    MetadataAccessError,
)
from schema_comparator.discovery.service import extract_schema

__all__ = [
    "ColumnSnapshot",
    "TableSnapshot",
    "SchemaSnapshot",
    "extract_schema",
    "DiscoveryError",
    "DriverUnavailableError",
    "ConnectionFailedError",
    "MetadataAccessError",
]
```

### Public API (`connectors/__init__.py`)

```python
DEFAULT_TIMEOUT_SECONDS: float = 30.0

def connect(
    profile: ConnectionProfile,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    connect_fn: Callable[..., "pyodbc.Connection"] = pyodbc.connect,
) -> AbstractContextManager["pyodbc.Connection"]:
    ...
```

`DEFAULT_TIMEOUT_SECONDS` lives in `connectors/` (not `discovery/`) because it
is fundamentally a *connection-boundary* concern: it is passed straight into
`pyodbc.connect(..., timeout=...)` (login timeout) and then applied once
more as `connection.timeout = timeout_seconds` before the connection is
handed back — see §5. `discovery/service.py` imports the constant only to
expose it as `extract_schema`'s default keyword value; it never re-applies
a timeout itself.

`connect_fn` is an injectable seam (defaults to the real `pyodbc.connect`)
so unit tests can substitute a fake without patching `pyodbc` globally —
see §8.

---

## 2. Data model: normalized table/column metadata

Following the same rationale as `ConnectionProfile` (see baseline design):
plain stdlib `@dataclass(frozen=True, slots=True)` value objects, no
pydantic, no ORM. These models carry no I/O and no secret-bearing fields,
so there is no leakage concern to design around here — the discipline is
purely about correctness (immutability, qualified identity, deterministic
order).

```python
# discovery/models.py
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ColumnSnapshot:
    """One column's normalized metadata. Non-applicable size/precision/
    scale attributes are preserved as None — never fabricated."""
    name: str
    data_type: str
    character_maximum_length: int | None
    numeric_precision: int | None
    numeric_scale: int | None
    is_nullable: bool
    ordinal_position: int


@dataclass(frozen=True, slots=True)
class TableSnapshot:
    """One base table, identified by the (schema_name, table_name) pair.
    `columns` is already sorted (ordinal position, then name) at
    construction time — see §4."""
    schema_name: str
    table_name: str
    columns: tuple[ColumnSnapshot, ...]

    @property
    def qualified_name(self) -> tuple[str, str]:
        """The table identity used for equality, sorting, and dict keys."""
        return (self.schema_name, self.table_name)


@dataclass(frozen=True, slots=True)
class SchemaSnapshot:
    """The full extraction result for one profile. `tables` is already
    sorted (schema, then table name) at construction time — see §4."""
    profile_name: str
    tables: tuple[TableSnapshot, ...]
```

Using `tuple[...]` (not `list[...]`) for `columns` and `tables` keeps the
whole snapshot graph immutable end-to-end, matching REQ-schema-extraction-001
("immutable table and column metadata") and preventing an accidental
downstream mutation from desynchronizing a snapshot from what was actually
read.

---

## 3. Qualified table identity handling

REQ-schema-extraction-002 requires the ordered pair `(schema_name,
table_name)` as table identity — same-named tables in different schemas
(e.g. `sales.Invoice` vs `archive.Invoice`) must remain distinct entries.

Implementation approach:

- The catalog query (§5) always selects `TABLE_SCHEMA` and `TABLE_NAME` as
  separate columns; normalization groups rows by the tuple
  `(TABLE_SCHEMA, TABLE_NAME)`, never by `TABLE_NAME` alone and never by a
  concatenated string (which would risk an ambiguous collision, e.g.
  schema `a.b` + table `c` vs schema `a` + table `b.c`).
- Grouping uses a `dict[tuple[str, str], list[RawColumnRow]]` built while
  iterating the fetched rows once, preserving exact `TABLE_SCHEMA` /
  `TABLE_NAME` string values as returned by SQL Server (no case-folding, no
  trimming — catalog identifiers are returned canonically by
  `INFORMATION_SCHEMA` and are not user-authored free text like the YAML
  profile names in the prior capability, so no normalization is needed here).
- `TableSnapshot.qualified_name` exposes the identity tuple as a single
  property so callers (this capability's tests, and later the compare
  engine) never have to re-derive the tuple from two loose attributes.

---

## 4. Deterministic ordering implementation

REQ-schema-extraction-003 requires snapshots to be ordered independently of
catalog row delivery order: tables by `(schema_name, table_name)` ascending,
columns within a table by `(ordinal_position, name)` ascending.

Implementation: ordering is applied **once, at construction time**, inside
the normalization function (`queries.py: _build_snapshot`), never left to
the SQL `ORDER BY` clause alone (SQL Server does not guarantee row order
without an `ORDER BY`, and relying solely on it would make the guarantee
untestable without a live database):

```python
def _build_snapshot(profile_name: str, rows: list[tuple]) -> SchemaSnapshot:
    grouped: dict[tuple[str, str], list[ColumnSnapshot]] = {}
    for (schema, table, col_name, data_type, char_len, num_prec, num_scale,
         is_nullable, ordinal) in rows:
        grouped.setdefault((schema, table), []).append(
            ColumnSnapshot(
                name=col_name,
                data_type=data_type,
                character_maximum_length=char_len,
                numeric_precision=num_prec,
                numeric_scale=num_scale,
                is_nullable=(is_nullable == "YES"),
                ordinal_position=ordinal,
            )
        )

    tables = tuple(
        TableSnapshot(
            schema_name=schema,
            table_name=table,
            columns=tuple(
                sorted(cols, key=lambda c: (c.ordinal_position, c.name))
            ),
        )
        for (schema, table), cols in sorted(grouped.items())
    )
    return SchemaSnapshot(profile_name=profile_name, tables=tables)
```

`sorted(grouped.items())` sorts by the dict key tuple `(schema, table)`
first, which is exactly the required table order; `sorted(cols, key=...)`
sorts each table's columns by `(ordinal_position, name)`. Both use plain
Python string/int comparison — no locale/collation-aware comparison is
introduced, keeping behavior identical regardless of host OS locale. This
is a documented, non-blocking assumption (SQL Server identifier ordering
semantics are not replicated); revisit only if a future requirement demands
collation-aware ordering.

Because sorting happens in pure Python over already-fetched rows, this path
is fully unit-testable by feeding rows in an intentionally shuffled order
(§8) — no database needed to prove the guarantee.

---

## 5. INFORMATION_SCHEMA query strategy

A **single** round-trip query joins `INFORMATION_SCHEMA.COLUMNS` to
`INFORMATION_SCHEMA.TABLES` and filters to base tables only (excluding
views, matching REQ-schema-extraction-001's "views ... must not be
included"):

```sql
SELECT
    c.TABLE_SCHEMA,
    c.TABLE_NAME,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.CHARACTER_MAXIMUM_LENGTH,
    c.NUMERIC_PRECISION,
    c.NUMERIC_SCALE,
    c.IS_NULLABLE,
    c.ORDINAL_POSITION
FROM INFORMATION_SCHEMA.COLUMNS c
INNER JOIN INFORMATION_SCHEMA.TABLES t
    ON t.TABLE_SCHEMA = c.TABLE_SCHEMA
   AND t.TABLE_NAME = c.TABLE_NAME
WHERE t.TABLE_TYPE = 'BASE TABLE'
```

Rationale for one query instead of two (`TABLES` then `COLUMNS`):

- **One network round trip** = one place the ~30s query timeout applies,
  matching REQ-schema-extraction-005's framing of "the catalog query"
  (singular) rather than "catalog queries."
- A base table in SQL Server always has at least one column, so joining
  through `COLUMNS` cannot silently drop a table that has zero columns —
  there is no such table. A table with no *visible* columns (e.g. all
  columns hidden by a more restrictive column-level grant) would surface as
  zero rows for that table, which is an accepted, documented limitation of
  reading `INFORMATION_SCHEMA` (its columns view is itself permission-
  filtered by SQL Server) rather than a defect in this design.
- No `ORDER BY` is added to the SQL — ordering is enforced in Python (§4),
  so the query does not need it and avoids server-side sort cost on a
  metadata query that is already followed by a mandatory client-side sort.
- Set-based (a single `JOIN` + `WHERE`), matching the baseline's "prefer
  set-based catalog queries over cursors/loops" guidance, and read via
  the connection's default READ COMMITTED isolation (no `NOLOCK`), matching
  the baseline's discovery query approach and REQ-schema-extraction-004.
- An empty result set naturally produces `SchemaSnapshot(profile_name, ())`,
  directly satisfying the "Empty visible catalog returns an empty snapshot"
  scenario with no special-case branch.

`queries.py` exposes the SQL as a single module-level constant
(`CATALOG_QUERY_SQL`) so `service.py` and tests can both reference the exact
same string (tests can assert the query shape without a live database, e.g.
asserting it selects from `INFORMATION_SCHEMA.COLUMNS`/`.TABLES` and filters
`BASE TABLE`, without ever executing it).

---

## 6. Timeout enforcement (connection + catalog query)

Per the clarify decision, both the connection attempt and the catalog query
share one default timeout constant, `DEFAULT_TIMEOUT_SECONDS = 30.0`
(`connectors/__init__.py`), and both expiries are translated via the same
network/connectivity error category.

`pyodbc` exposes two independent timeout knobs that this design intentionally
maps onto the *same* constant and the *same* connect() call:

| Phase | pyodbc mechanism | Applied where |
|---|---|---|
| Connection establishment (login) | `pyodbc.connect(conn_str, timeout=N)` → `SQL_ATTR_LOGIN_TIMEOUT` | `connectors.connect()`, at the `pyodbc.connect(...)` call itself |
| Catalog query execution | `connection.timeout = N` → `SQL_ATTR_QUERY_TIMEOUT`, applied to every statement on that connection | `connectors.connect()`, immediately after a successful `pyodbc.connect(...)`, before yielding the connection |

```python
# connectors/__init__.py
@contextmanager
def connect(profile, *, timeout_seconds=DEFAULT_TIMEOUT_SECONDS, connect_fn=pyodbc.connect):
    conn = connect_fn(profile.connection_string, timeout=timeout_seconds)
    conn.timeout = timeout_seconds  # query timeout: covers the catalog query too
    try:
        yield conn
    finally:
        conn.close()
```

Setting `connection.timeout` once, right after connecting, means the single
`DEFAULT_TIMEOUT_SECONDS` constant governs both phases without `discovery/`
needing to configure anything timeout-related itself — `service.py` just
calls `connectors.connect(profile, timeout_seconds=timeout_seconds)` and
executes its query normally.

`pyodbc.Error` raised for either an expired login timeout (SQLSTATE
`HYT00`) or an expired query timeout (SQLSTATE `HYT01`) is translated by
`discovery/errors.py` to `ConnectionFailedError` — the **same** class used
for a plain connection failure (SQLSTATE class `08`), per the clarify
decision that timeout expiry reuses the existing network/connectivity
category rather than introducing a new one. See §7 for the full mapping.

`connect_fn` is not called with a real timeout in unit tests; tests instead
inject a fake `connect_fn` and assert the `timeout=` keyword and
`.timeout` attribute assignment happened, without ever waiting out a real
timeout (§8).

---

## 7. Driver failure translation strategy

`discovery/errors.py` defines the domain error hierarchy and two pure
translation functions, one per phase, so a caller-facing error always names
the profile and exactly one prerequisite category — never raw driver text.

```python
class DiscoveryError(Exception):
    """Base class for all schema-extraction failures."""


class DriverUnavailableError(DiscoveryError):
    @classmethod
    def for_profile(cls, profile_name: str) -> "DriverUnavailableError":
        return cls(
            f"Schema extraction for '{profile_name}' failed: the required "
            "ODBC driver is not available. Verify Microsoft ODBC Driver 17 "
            "or 18 for SQL Server is installed on this machine."
        )


class ConnectionFailedError(DiscoveryError):
    @classmethod
    def for_profile(cls, profile_name: str) -> "ConnectionFailedError":
        return cls(
            f"Schema extraction for '{profile_name}' failed: could not "
            "establish or maintain a connection within the timeout. Verify "
            "network connectivity and that the server is reachable."
        )


class MetadataAccessError(DiscoveryError):
    @classmethod
    def for_profile(cls, profile_name: str) -> "MetadataAccessError":
        return cls(
            f"Schema extraction for '{profile_name}' failed: the "
            "connection could not read required catalog metadata. Verify "
            "the profile's principal has metadata-read permission."
        )
```

### Translation tables

**Connect-phase** (`translate_connect_error(profile_name, exc: pyodbc.Error)`
— called around the `connectors.connect(...)` call in `service.py`):

| Observed SQLSTATE class/value | Raised as |
|---|---|
| `IM*` (driver manager: e.g. `IM002` data source/driver not found) | `DriverUnavailableError` |
| `08*` (connection exception) | `ConnectionFailedError` |
| `HYT00` (login timeout expired) | `ConnectionFailedError` |
| anything else unrecognized at connect time | `ConnectionFailedError` (fail toward the more generic, still-actionable category rather than leaking an unmapped raw state) |

**Query-phase** (`translate_query_error(profile_name, exc: pyodbc.Error)` —
called around `cursor.execute(CATALOG_QUERY_SQL)` / `cursor.fetchall()` in
`service.py`):

| Observed SQLSTATE class/value | Raised as |
|---|---|
| `HYT01` (query timeout expired) | `ConnectionFailedError` (per clarify: query timeout reuses network/connectivity) |
| `08*` (connection dropped mid-query) | `ConnectionFailedError` |
| anything else (e.g. `42000` permission denied reading a catalog view) | `MetadataAccessError` |

Both functions read only `exc.args[0]` (the SQLSTATE pyodbc places first in
`.args`) to select a category — they never read, log, or embed
`str(exc)`/`exc.args[1]` (the driver's free-text message, which can include
server/database fragments) into the raised message. This mirrors the prior
capability's guardrail of never letting raw driver/parser text become the
primary user-facing message, extended here from YAML errors to ODBC errors.
Both translators `raise ... from exc`, preserving the original exception for
debuggers/tracebacks without it being the message a user reads.

`service.py` wraps exactly two call sites this way:

```python
def extract_schema(profile, *, timeout_seconds=DEFAULT_TIMEOUT_SECONDS, connect_fn=pyodbc.connect):
    try:
        with connectors.connect(profile, timeout_seconds=timeout_seconds, connect_fn=connect_fn) as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(CATALOG_QUERY_SQL)
                rows = cursor.fetchall()
            except pyodbc.Error as exc:
                raise translate_query_error(profile.name, exc) from exc
            finally:
                cursor.close()
    except pyodbc.Error as exc:
        raise translate_connect_error(profile.name, exc) from exc

    return _build_snapshot(profile.name, rows)
```

Resource cleanup ordering satisfies REQ-schema-extraction-004's "failure
still releases extraction resources": `cursor.close()` runs in a `finally`
before the query-error is re-raised, and `connectors.connect`'s own
`finally: conn.close()` runs as the `with` block unwinds regardless of which
exception (if any) propagates.

---

## 8. Testing strategy (no live database)

Runner: **pytest**, same layout as the existing suite
(`tests/unit/discovery/`, `tests/unit/connectors/`), matching
`stack-python-testing` and the baseline's "Testing Bar" (unit tests mock DB
connections; never hit a real network/DB). `strict_tdd` remains `false` for
this project — tests are still written test-first as normal practice, but
the orchestrator does not enforce red-green forwarding evidence for this
change.

### Fakes instead of `unittest.mock` autospec of `pyodbc`

`pyodbc.Connection`/`pyodbc.Cursor` are C-extension types that do not
support `autospec=True` cleanly (no introspectable Python signatures). This
design therefore uses small **hand-written fake classes** conforming to the
subset of the pyodbc API this code actually calls, injected through the
`connect_fn` seam from §1/§6:

```python
class FakeCursor:
    def __init__(self, rows): self._rows = rows; self.closed = False
    def execute(self, sql): self.executed_sql = sql
    def fetchall(self): return self._rows
    def close(self): self.closed = True

class FakeConnection:
    def __init__(self, rows): self._rows = rows; self.timeout = None; self.closed = False
    def cursor(self): return FakeCursor(self._rows)
    def close(self): self.closed = True

def fake_connect_fn(rows, *, raise_on_connect=None):
    def _connect(conn_str, timeout):
        if raise_on_connect:
            raise raise_on_connect
        return FakeConnection(rows)
    return _connect
```

This gives full control over both the happy path (supply rows) and every
failure path (supply a `pyodbc.Error(sqlstate, msg)` instance to raise, or
have `FakeCursor.execute`/`fetchall` raise one) — all without importing a
real driver or opening a socket, directly satisfying
REQ-schema-extraction-006.

### Coverage matrix (one test per spec scenario)

| Spec scenario | Test intent |
|---|---|
| Visible base-table metadata is returned | fake rows for one table/columns → snapshot has profile name, table, columns; null size/precision/scale preserved as `None` |
| Empty visible catalog returns an empty snapshot | fake rows `[]` → `SchemaSnapshot(profile_name, ())` |
| Same-named tables in distinct schemas remain distinct | rows for `sales.Invoice` and `archive.Invoice` → two `TableSnapshot` entries, each with its own `schema_name` |
| Unordered catalog rows produce a stable snapshot | feed the same rows in two different shuffles → identical resulting tuple order both times |
| Successful extraction leaves no database mutation | assert `FakeCursor.execute` was called with `CATALOG_QUERY_SQL` only (no `INSERT`/`UPDATE`/`DELETE`/DDL keywords) |
| Failure still releases extraction resources | inject a query-phase error → assert `FakeCursor.closed` and `FakeConnection.closed` are both `True` |
| Connection failure is safely translated | `connect_fn` raises `pyodbc.Error('08001', ...)` → `ConnectionFailedError` naming the profile, message excludes SQLSTATE/driver text |
| Catalog access failure is safely translated | `FakeCursor.execute` raises `pyodbc.Error('42000', ...)` → `MetadataAccessError` naming the profile |
| Connection establishment timeout is safely translated | `connect_fn` raises `pyodbc.Error('HYT00', ...)` → `ConnectionFailedError` |
| Catalog query timeout is safely translated | `FakeCursor.execute` raises `pyodbc.Error('HYT01', ...)` → `ConnectionFailedError` |
| Driver unavailable | `connect_fn` raises `pyodbc.Error('IM002', ...)` → `DriverUnavailableError` |
| Unit normalization runs without SQL Server | entire matrix above uses `FakeConnection`/`FakeCursor`; a workspace-level guard (or CI marker) keeps `tests/unit/` free of real `pyodbc.connect` calls |
| Optional integration verification is isolated | `tests/integration/` gains a `test_extraction_live.py` guarded by `pytest.mark.skipif` on an unset env var (e.g. `SCHEMA_COMPARATOR_TEST_DSN`), so the normal unit run never attempts live extraction |
| No secret ever leaks in a translated error | guardrail test: build a profile whose connection string contains a sentinel secret, force every failure path, assert the sentinel never appears in `str(exc)` |

### Timeout parameters are asserted, not waited out

Because a real ~30s wait is both slow and non-deterministic in CI, no test
lets a real timeout elapse. Instead:

- One test asserts `connect_fn` is invoked with `timeout=DEFAULT_TIMEOUT_SECONDS`.
- One test asserts `FakeConnection.timeout == DEFAULT_TIMEOUT_SECONDS` after
  `connectors.connect()` returns the connection.
- Timeout *expiry* is simulated by having the fake raise the corresponding
  `HYT00`/`HYT01` `pyodbc.Error` directly (see matrix above), which exercises
  the translation logic without any real elapsed time.

---

## 9. Sequence diagram: extraction flow

Both the happy path and the timeout/error paths are shown in one diagram,
per `openspec/config.yaml` `rules.design` ("sequence diagrams for complex
flows") — this flow has multiple components (service, connectors, pyodbc,
SQL Server) and two independent failure branches, unlike the linear
single-module flow in the prior capability's design.

```mermaid
sequenceDiagram
    participant Caller
    participant Service as discovery.service
    participant Conn as connectors.connect
    participant Driver as pyodbc / ODBC driver
    participant DB as SQL Server

    Caller->>Service: extract_schema(profile)
    Service->>Conn: connect(profile, timeout_seconds=30)
    activate Conn
    Conn->>Driver: pyodbc.connect(conn_str, timeout=30)
    activate Driver

    alt connection succeeds within timeout
        Driver->>DB: establish connection
        DB-->>Driver: connected
        Driver-->>Conn: Connection
        Conn->>Conn: connection.timeout = 30
        Conn-->>Service: yield Connection
        deactivate Driver

        Service->>Driver: cursor.execute(CATALOG_QUERY_SQL)
        activate Driver
        alt query succeeds within timeout
            Driver->>DB: run INFORMATION_SCHEMA JOIN query
            DB-->>Driver: rows
            Driver-->>Service: rows
            deactivate Driver
            Service->>Service: cursor.close()
            Service->>Service: _build_snapshot(rows)\n(group, sort, normalize)
            Service-->>Conn: (context exits)
            Conn->>Driver: connection.close()
            deactivate Conn
            Service-->>Caller: SchemaSnapshot
        else query exceeds timeout (SQLSTATE HYT01) or fails (e.g. 42000)
            Driver-->>Service: pyodbc.Error
            deactivate Driver
            Service->>Service: cursor.close()
            Service->>Service: translate_query_error(profile.name, exc)
            Service-->>Conn: (context exits)
            Conn->>Driver: connection.close()
            deactivate Conn
            Service-->>Caller: raise ConnectionFailedError\n(timeout) or MetadataAccessError
        end

    else connection fails or exceeds timeout (SQLSTATE 08*/HYT00/IM*)
        Driver-->>Conn: pyodbc.Error
        deactivate Driver
        Conn-->>Service: pyodbc.Error propagates\n(no connection was opened to close)
        deactivate Conn
        Service->>Service: translate_connect_error(profile.name, exc)
        Service-->>Caller: raise ConnectionFailedError\nor DriverUnavailableError
    end
```

Key properties this diagram makes explicit:

- Exactly one `pyodbc.connect` call site (`connectors.connect`) and exactly
  one catalog query call site (`service.py`), matching §1/§5.
- `connection.timeout = 30` is set once, immediately after a successful
  connect, before the connection is handed to the caller — covering the
  query phase without a second timeout call (§6).
- Every exit path — happy, query-error, and connect-error — reaches
  resource cleanup (`cursor.close()` then `connection.close()`, or simply no
  connection to close if connect itself failed) before an error is raised
  to the caller, satisfying REQ-schema-extraction-004.
- Both failure branches converge on `discovery/errors.py` translators
  before anything reaches `Caller`; the raw `pyodbc.Error` never crosses
  that boundary.

---

## 10. Dependency addition

Add `pyodbc` to `[project].dependencies` in `pyproject.toml` (currently only
`PyYAML` from the prior capability), per the proposal's Affected Areas row.
No other new runtime dependency is introduced by this change.
