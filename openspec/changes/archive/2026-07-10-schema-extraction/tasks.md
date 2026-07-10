# Tasks: Schema Extraction

## Spec/Design Reconciliation

| Requirement / Scenario | Priority | Design Allocation | Status | Notes |
|------------------------|----------|-------------------|--------|-------|
| REQ-schema-extraction-001 (extract table/column metadata, preserve nulls, exclude views) | MUST | `discovery/models.py` (§2), `discovery/queries.py` CATALOG_QUERY_SQL + `_build_snapshot` (§5) | covered-by-design | Single JOIN query filters `BASE TABLE`; nulls never fabricated. |
| REQ-schema-extraction-002 (qualified table identity, same name/different schema) | MUST | `discovery/queries.py` grouping by `(TABLE_SCHEMA, TABLE_NAME)` (§3), `TableSnapshot.qualified_name` (§2) | covered-by-design | Tuple key grouping, no string concatenation. |
| REQ-schema-extraction-003 (deterministic ordering) | MUST | `discovery/queries.py` `_build_snapshot` sort at construction time (§4) | covered-by-design | Python-side sort, independent of SQL row order. |
| REQ-schema-extraction-004 (read-only, ephemeral, guaranteed cleanup) | MUST | `connectors/__init__.py` `connect()` context manager (§1, §6), `service.py` cursor `finally` (§7) | covered-by-design | Cleanup ordering verified in sequence diagram (§9). |
| REQ-schema-extraction-005 (profile-safe errors, timeout enforcement) | MUST | `discovery/errors.py` translation tables (§7), `connectors.DEFAULT_TIMEOUT_SECONDS` (§6) | covered-by-design | SQLSTATE-only translation; raw `str(exc)` never surfaced. |
| REQ-schema-extraction-006 (database-free unit verification) | MUST | `connect_fn` injectable seam (§1), `FakeConnection`/`FakeCursor` doubles (§8) | covered-by-design | No autospec of `pyodbc` C-extension types. |

### Reconciliation Verdict
- MUST coverage: complete
- SHOULD/MAY gaps: none (spec defines no SHOULD/MAY requirements)
- Ambiguities to track: none

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~550-650 (source ~250, tests ~350, dependency line ~1) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR (size:exception) — reference work units below for reviewer navigation |
| Delivery strategy | exception-ok |
| Chain strategy | size-exception |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Models + connectors boundary (Phases 1-2) | PR 1 (single, size:exception) | Foundation types and the sole `pyodbc.connect` call site. |
| 2 | Query normalization + error translation + service orchestration (Phases 3-4) | PR 1 (single, size:exception) | Depends on Unit 1 types. |
| 3 | Unit tests + integration stub (Phases 5-6) | PR 1 (single, size:exception) | Depends on Units 1-2; delivered together under the accepted size exception. |

### Checklist Status Legend

- `[ ]` Not implemented yet
- `[~]` Implemented but not yet verified locally
- `[x]` Implemented and verified locally

## Phase 1: Foundation — Dependency and Data Model

- [x] 1.1 Add `pyodbc` as a runtime dependency in [pyproject.toml](../../../pyproject.toml).
- [x] 1.2 Create `src/schema_comparator/discovery/models.py` with frozen `slots` dataclasses `ColumnSnapshot`, `TableSnapshot` (including the `qualified_name` property returning `(schema_name, table_name)`), and `SchemaSnapshot`, per design §2.

## Phase 2: Connectors — Connection Boundary and Timeout

- [x] 2.1 Create `src/schema_comparator/connectors/__init__.py` with `DEFAULT_TIMEOUT_SECONDS = 30.0` and a `connect(profile, *, timeout_seconds=DEFAULT_TIMEOUT_SECONDS, connect_fn=pyodbc.connect)` `@contextmanager` that calls `connect_fn(profile.connection_string, timeout=timeout_seconds)`, sets `conn.timeout = timeout_seconds`, yields the connection, and closes it in `finally` (design §1, §6).

## Phase 3: Discovery — Catalog Query and Normalization

- [x] 3.1 Create `src/schema_comparator/discovery/queries.py` with the `CATALOG_QUERY_SQL` module-level constant: single `INFORMATION_SCHEMA.COLUMNS` JOIN `INFORMATION_SCHEMA.TABLES` query filtered to `WHERE t.TABLE_TYPE = 'BASE TABLE'` (design §5).
- [x] 3.2 Add `_build_snapshot(profile_name, rows)` to `queries.py`: group rows by `(TABLE_SCHEMA, TABLE_NAME)`, build `ColumnSnapshot`/`TableSnapshot` objects, and return a `SchemaSnapshot` with tables sorted by `(schema_name, table_name)` and columns sorted by `(ordinal_position, name)` (design §4).

## Phase 4: Discovery — Error Translation and Service Orchestration

- [x] 4.1 Create `src/schema_comparator/discovery/errors.py` with the `DiscoveryError` base class and `DriverUnavailableError`, `ConnectionFailedError`, `MetadataAccessError` subclasses, each exposing a `for_profile(profile_name)` classmethod producing a profile-named, driver-detail-free message (design §7).
- [x] 4.2 Add `translate_connect_error(profile_name, exc)` to `errors.py` mapping SQLSTATE `IM*` → `DriverUnavailableError`, `08*`/`HYT00`/unrecognized → `ConnectionFailedError`, reading only `exc.args[0]` and re-raising with `from exc` (design §7 connect-phase table).
- [x] 4.3 Add `translate_query_error(profile_name, exc)` to `errors.py` mapping SQLSTATE `HYT01`/`08*` → `ConnectionFailedError`, anything else (e.g. `42000`) → `MetadataAccessError`, same `args[0]`-only/`from exc` discipline (design §7 query-phase table).
- [x] 4.4 Create `src/schema_comparator/discovery/service.py` with `extract_schema(profile, *, timeout_seconds=DEFAULT_TIMEOUT_SECONDS, connect_fn=pyodbc.connect)` wiring `connectors.connect(...)`, `cursor.execute(CATALOG_QUERY_SQL)` / `fetchall()` inside a `try/except/finally` that closes the cursor before re-raising via `translate_query_error`, an outer `except pyodbc.Error` calling `translate_connect_error`, and a final call to `_build_snapshot` (design §7 code block, §9 sequence diagram).
- [x] 4.5 Create `src/schema_comparator/discovery/__init__.py` re-exporting `ColumnSnapshot`, `TableSnapshot`, `SchemaSnapshot`, `extract_schema`, `DiscoveryError`, `DriverUnavailableError`, `ConnectionFailedError`, `MetadataAccessError` with an explicit `__all__` (design §1 Public API block).

## Phase 5: Unit Tests (Database-Free)

- [x] 5.1 Create `tests/unit/discovery/conftest.py` with the `FakeCursor`, `FakeConnection`, and `fake_connect_fn` test doubles from design §8 (no `pyodbc` autospec).
- [x] 5.2 Create `tests/unit/discovery/test_models.py` covering `TableSnapshot.qualified_name` identity and dataclass immutability (`frozen=True`).
- [x] 5.3 Create `tests/unit/connectors/test_connect.py` asserting: `connect_fn` is invoked with `timeout=DEFAULT_TIMEOUT_SECONDS`; `connection.timeout == DEFAULT_TIMEOUT_SECONDS` after connect; `connection.close()` runs even when the caller's block raises — covers REQ-schema-extraction-004 and the timeout-parameter checks in design §6/§8.
- [x] 5.4 Create `tests/unit/discovery/test_queries.py` exercising the "Visible base-table metadata is returned" (null size/precision/scale preserved), "Empty visible catalog returns an empty snapshot", "Same-named tables in distinct schemas remain distinct", and "Unordered catalog rows produce a stable snapshot" scenarios from spec.md.
- [x] 5.5 Create `tests/unit/discovery/test_errors.py` covering the full SQLSTATE matrix (`IM002`→`DriverUnavailableError`, `08001`→`ConnectionFailedError`, `HYT00`→`ConnectionFailedError`, `HYT01`→`ConnectionFailedError`, `42000`→`MetadataAccessError`) and asserting raised messages never contain `exc.args[1]`/`str(exc)` raw driver text.
- [x] 5.6 Create `tests/unit/discovery/test_service.py` covering: happy-path `extract_schema` via `FakeConnection`/`FakeCursor`; "Failure still releases extraction resources" (assert `FakeCursor.closed` and `FakeConnection.closed` both `True` after a query-phase error); "Successful extraction leaves no database mutation" (assert `executed_sql == CATALOG_QUERY_SQL`, no write/DDL keywords); and a secret-sentinel guardrail test asserting a sentinel value in a fake connection string never appears in any raised error's `str()`.
- [x] 5.7 Create `tests/integration/test_extraction_live.py` guarded by `pytest.mark.skipif` on an unset `SCHEMA_COMPARATOR_TEST_DSN` environment variable, covering the "Optional integration verification is isolated" scenario.

## Phase 6: Verification

- [x] 6.1 Run `pytest tests/unit` and confirm every scenario in the design §8 coverage matrix has a passing test, with no network/database access attempted.
