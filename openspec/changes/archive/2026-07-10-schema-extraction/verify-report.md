# Verify Report: Schema Extraction

Change: `schema-extraction`
Phase: verify
Date: 2026-07-10

## Overall Result: PASS

## Test Suite Execution

Command: `pytest tests/unit tests/integration -q`

```
70 passed, 1 skipped in 0.16s
```

- 0 failures, 0 errors.
- The single skip is `tests/integration/test_extraction_live.py::test_extract_schema_against_live_database`, correctly gated on the unset `SCHEMA_COMPARATOR_TEST_DSN` environment variable (REQ-schema-extraction-006, "Optional integration verification is isolated" scenario).
- No network/database access occurred during the unit run (confirmed by code inspection: all discovery/connectors unit tests use `FakeConnection`/`FakeCursor`/`fake_connect_fn` doubles, never `pyodbc.connect`).

## Requirement-by-Requirement Compliance

| Requirement | Verdict | Evidence |
|---|---|---|
| REQ-schema-extraction-001 (extract table/column metadata, preserve nulls, exclude views) | PASS | `queries.py` `CATALOG_QUERY_SQL` joins `INFORMATION_SCHEMA.COLUMNS`/`.TABLES` filtered to `BASE TABLE`; `_build_snapshot` never substitutes values for `None` size/precision/scale. Covered by [test_queries.py](../../../tests/unit/discovery/test_queries.py) and [test_models.py](../../../tests/unit/discovery/test_models.py). |
| REQ-schema-extraction-002 (qualified table identity) | PASS | Grouping key is the tuple `(schema, table)`, never a concatenated string; `TableSnapshot.qualified_name` exposes it. Covered by `test_same_named_tables_in_distinct_schemas_remain_distinct` / `test_same_named_tables_in_different_schemas_are_distinct`. |
| REQ-schema-extraction-003 (deterministic ordering) | PASS | `_build_snapshot` sorts `grouped.items()` (schema, table) and each table's columns by `(ordinal_position, name)` in Python, independent of row delivery order. Covered by `test_unordered_catalog_rows_produce_a_stable_snapshot`. |
| REQ-schema-extraction-004 (read-only, ephemeral, guaranteed cleanup) | PASS | `connectors.connect()` closes the connection in `finally`; `service.extract_schema` closes the cursor in `finally` before re-raising. No write/DDL/`NOLOCK`/comparison/report/TUI code present anywhere in `discovery/` or `connectors/`. Covered by `test_failure_still_releases_extraction_resources`, `test_connection_closed_even_when_caller_block_raises`, `test_successful_extraction_executes_only_the_catalog_query` (asserts no write keywords in executed SQL). |
| REQ-schema-extraction-005 (profile-safe errors) | PASS | `translate_connect_error`/`translate_query_error` read only `exc.args[0]` (SQLSTATE), never `str(exc)` or `exc.args[1]`; error messages name the profile and a prerequisite category only. Covered by `test_errors.py` matrix and `test_no_secret_leaks_in_any_translated_error` (sentinel-string guardrail). |
| REQ-schema-extraction-005 timeout enforcement (Clarifications) | PASS | `connectors.DEFAULT_TIMEOUT_SECONDS = 30.0` is applied both as `connect_fn(..., timeout=timeout_seconds)` (login timeout) and `conn.timeout = timeout_seconds` (query timeout), matching the clarify decision. `HYT00` (login timeout expiry) and `HYT01` (query timeout expiry) both translate to `ConnectionFailedError` — the same class used for a plain `08001` connection failure — satisfying "reuse the existing network/connectivity error category" with no raw driver detail exposed. Covered by `test_connection_timeout_is_safely_translated`, `test_query_timeout_is_safely_translated`, `test_translate_connect_error_maps_sqlstate[HYT00-...]`, `test_translate_query_error_maps_sqlstate[HYT01-...]`. |
| REQ-schema-extraction-006 (database-free unit verification) | PASS | All discovery/connectors unit tests inject `connect_fn` doubles (`FakeConnection`/`FakeCursor`), no `pyodbc` autospec, no live DB/network. Integration test isolated behind an environment-variable skip. |

## Design Conformance

- Module layout (`connectors/__init__.py`, `discovery/{models,queries,errors,service}.py`) matches design §1 exactly.
- `connectors/` remains the sole `pyodbc.connect` call site and does not translate errors itself (design §1 rationale) — confirmed by reading the file: driver errors propagate unchanged.
- Single JOIN query, no `ORDER BY` in SQL, Python-side sort — matches design §4/§5.
- Error hierarchy and `for_profile` classmethods match design §7 exactly (message wording, class names).
- Public `__all__` re-export surface in `discovery/__init__.py` matches design's Public API block verbatim.

## Tasks Reconciliation

All 6 phases (24 checklist items) in [tasks.md](tasks.md) are marked `[x]` and verified as actually implemented and passing, not just checked off:

- Phase 1 (models/dependency): `pyodbc>=5.0` present in [pyproject.toml](../../../pyproject.toml); models present with `frozen`/`slots`.
- Phase 2 (connectors boundary): implemented as specified.
- Phase 3 (query/normalization): implemented as specified.
- Phase 4 (errors/service): implemented as specified.
- Phase 5 (unit tests): all listed test files exist and pass.
- Phase 6 (verification): reproduced independently in this phase — `70 passed, 1 skipped`, consistent with apply-progress.md's reported result.

No MUST requirement is uncovered; no SHOULD/MAY requirements are declared in the spec.

## Findings

### CRITICAL
None.

### WARNING
None.

### SUGGESTION

1. **Test package layout inconsistency (test-layout, non-blocking).** `tests/unit/discovery/` and `tests/unit/connectors/` were given `__init__.py` files to resolve a pytest basename collision (`test_models.py`, `test_errors.py` duplicated across `discovery/` and `config/`), while the sibling `tests/unit/config/` was left without one. This is confirmed as a test-collection-only change — it does not touch `src/` package layout, and does not affect any requirement, design allocation, or task. The deviation is acceptable as delivered. For long-term consistency, consider either (a) adding `__init__.py` to `tests/unit/config/` as well so all test packages follow the same convention, or (b) setting `--import-mode=importlib` in `pyproject.toml`'s pytest configuration so future basename collisions across test subpackages don't require ad hoc `__init__.py` additions. Neither action is required for this change to pass verification.

## Standard Phase Result Envelope

- `status`: success
- `question_gate`: none
- `executive_summary`: PASS — all 6 MUST requirements (including the timeout-enforcement clarification) verified against implementation; 70 passed, 1 skipped (correctly isolated integration test), 0 failures.
- `artifacts`: [openspec/changes/schema-extraction/verify-report.md](verify-report.md)
- `next_recommended`: sdd-archive
- `risks`: none CRITICAL, none WARNING; 1 non-blocking SUGGESTION (test package `__init__.py` layout consistency, test-layout origin only)
- `skill_resolution`: none (no `skills/sdd-verify/SKILL.md` or `skills/_shared/sdd-phase-common.md` found in the repository; verification performed directly against the spec/design/tasks/apply artifacts and live pytest execution per this mode's instructions)
- `runtime_observability`: no `quality_gates:` block declared in `openspec/config.yaml` (`verify.test_command` is empty, `coverage_threshold: 0`) — quality gate evaluation contract is a no-op for this change; baseline verify behavior only.
- `approval_updates`: none required; recommend the orchestrator confirm the test-layout deviation noted in `apply-progress.md`'s "Follow-ups for verify phase" is accepted, then proceed to `sdd-archive`.
