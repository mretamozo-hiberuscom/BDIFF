# Apply Progress: Schema Extraction

## Batch 1 (full implementation)

All six phases from `tasks.md` were implemented in a single batch under the
accepted `size:exception` delivery strategy (no chained PRs).

### Implemented

- **Phase 1**: Added `pyodbc>=5.0` to `[project].dependencies` in
  [pyproject.toml](../../../pyproject.toml). Created
  [src/schema_comparator/discovery/models.py](../../../src/schema_comparator/discovery/models.py)
  with frozen `slots` dataclasses `ColumnSnapshot`, `TableSnapshot`
  (`qualified_name` property), `SchemaSnapshot`.
- **Phase 2**: Implemented `connect()` in
  [src/schema_comparator/connectors/__init__.py](../../../src/schema_comparator/connectors/__init__.py)
  — the sole `pyodbc.connect` call site, applying the shared
  `DEFAULT_TIMEOUT_SECONDS = 30.0` to both the login timeout and
  `connection.timeout`, with guaranteed `close()` in `finally`.
- **Phase 3**: Added
  [src/schema_comparator/discovery/queries.py](../../../src/schema_comparator/discovery/queries.py)
  with the `CATALOG_QUERY_SQL` single-JOIN constant and `_build_snapshot`
  performing tuple-key grouping and deterministic sort at construction time.
- **Phase 4**: Added
  [src/schema_comparator/discovery/errors.py](../../../src/schema_comparator/discovery/errors.py)
  (`DiscoveryError` hierarchy + `translate_connect_error` /
  `translate_query_error`, reading only `exc.args[0]`) and
  [src/schema_comparator/discovery/service.py](../../../src/schema_comparator/discovery/service.py)
  (`extract_schema` orchestration matching the design §7/§9 cleanup
  ordering). Updated
  [src/schema_comparator/discovery/__init__.py](../../../src/schema_comparator/discovery/__init__.py)
  with the explicit public `__all__` re-export surface.
- **Phase 5**: Added unit test doubles and coverage:
  - [tests/unit/discovery/conftest.py](../../../tests/unit/discovery/conftest.py) — `FakeCursor`/`FakeConnection`/`fake_connect_fn`.
  - [tests/unit/discovery/test_models.py](../../../tests/unit/discovery/test_models.py)
  - [tests/unit/connectors/test_connect.py](../../../tests/unit/connectors/test_connect.py)
  - [tests/unit/discovery/test_queries.py](../../../tests/unit/discovery/test_queries.py)
  - [tests/unit/discovery/test_errors.py](../../../tests/unit/discovery/test_errors.py)
  - [tests/unit/discovery/test_service.py](../../../tests/unit/discovery/test_service.py) (includes the secret-sentinel guardrail test)
  - [tests/integration/test_extraction_live.py](../../../tests/integration/test_extraction_live.py), skipped unless `SCHEMA_COMPARATOR_TEST_DSN` is set.
- **Phase 6**: Ran `pytest tests/unit tests/integration -q` → **70 passed, 1
  skipped** (the skipped test is the live-DB integration test, correctly
  isolated). No network/database access was attempted by the unit suite.

### Deviations from design

- **Test package layout**: `tests/unit/discovery/` and
  `tests/unit/connectors/` needed an `__init__.py` (absent from the sibling
  `tests/unit/config/` directory) to avoid a pytest "import file mismatch"
  collision — both `discovery/test_models.py`/`test_errors.py` and
  `config/test_models.py`/`test_errors.py` share basenames, and pytest's
  default rootdir-based import mode requires unique dotted module names
  when a bare basename collision occurs. This is a test-collection-only
  change; it does not affect the `src/` package layout specified in the
  design.
- **Environment**: `pyodbc` was not previously installed in the dev
  environment; it was installed via `pip install pyodbc` (resolved to
  `pyodbc==5.3.0`) so the new modules import successfully.
- No functional deviations from `design.md` — module layout, public API,
  timeout wiring, query shape, error translation tables, and cleanup
  ordering match §1–§9 as specified.

### Test results

```
70 passed, 1 skipped in 0.29s
```

### Follow-ups for verify phase

- Confirm the `tests/unit/discovery` / `tests/unit/connectors` `__init__.py`
  addition is acceptable as a test-layout deviation (not a spec/design
  deviation).
- No open blockers.
