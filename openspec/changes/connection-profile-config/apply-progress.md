# Apply Progress: Connection Profile Config

Mode: Standard (`strict_tdd: false` in `openspec/config.yaml`), with RED->GREEN
task ordering followed per phase per `tasks.md` "Notes on TDD ordering" (pytest
is configured and verified from the prior `scaffold-project` change). This
table is provided as requested even though the strict-TDD hard gate itself is
not active for this change.

All test runs below were executed for real via `python -m pytest` in this
repository (`C:\dev\tools`), Python 3.13.4 / pytest 9.1.1. No execution
evidence was fabricated.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR | Notes / Rationale |
|------|-----------|-------|------------|-----|-------|-------------|----------|-------------------|
| 0.1-0.2 | n/a | n/a | N/A (new) | n/a | n/a | n/a | n/a | Dependency add (`PyYAML>=6.0`) + test dir scaffolding; purely structural, no test-first cycle applicable. |
| 1.1-1.3 | `tests/unit/config/test_errors.py` | Unit | N/A (new) | Written — `ModuleNotFoundError: No module named 'schema_comparator.config.errors'` confirmed on first run | 6/6 passed | 6 cases (3 hierarchy + 3 factory-message) | ✅ Clean | |
| 2.1-2.3 | `tests/unit/config/test_models.py` | Unit | N/A (new) | Written — `ModuleNotFoundError: No module named 'schema_comparator.config.models'` confirmed on first run | 5/5 passed after 1 fix cycle | 5 cases (fields/slots, immutability, Windows-auth passthrough, 2x repr redaction) | ✅ Clean | First GREEN attempt failed: `profile.extra_attribute = ...` raised `TypeError` instead of `AttributeError` — a documented CPython 3.13 quirk where `frozen=True, slots=True` dataclasses raise `TypeError` (not `AttributeError`) for non-field attribute assignment, because the frozen `__setattr__`'s zero-arg `super()` call binds to the pre-slots-rebuild class. Fixed by asserting `pytest.raises((AttributeError, TypeError))` — the guardrail (no arbitrary attribute settable) still holds; recorded as assumption `sdd-apply-001` below. |
| 3.1-3.3 | `tests/unit/config/test_loader.py` (happy-path section) | Unit | N/A (new) | Written — `ModuleNotFoundError: No module named 'schema_comparator.config.loader'` confirmed on first run | 6/6 passed | 2-entry file, N in {1,3,20} parametrized, no-arg TypeError, arbitrary path/filename | ✅ Clean | |
| 4.1-4.3 | `tests/unit/config/test_loader.py` (fail-fast section) | Unit | ✅ 6/6 (Phase 3 tests) | Written — all 5 new tests failed (`KeyError`, `AttributeError`) against Phase-3-only code | 11/11 passed (6 Phase 3 + 5 new) | missing file, malformed YAML, non-mapping top-level, missing `databases`, non-mapping `databases` | ✅ Clean | |
| 5.1-5.3 | `tests/unit/config/test_loader.py` (trim/duplicate/validation section) | Unit | ✅ 11/11 (Phase 3+4 tests) | Written — all 5 new tests failed (`DID NOT RAISE ProfileValidationError` / trim not applied) against Phase-4 code | 16/16 passed (11 prior + 5 new) | trim, exact-duplicate key, case-insensitive duplicate, blank name, blank connection string | ✅ Clean | |
| 6.1-6.4 | `tests/unit/config/test_loader.py` (guardrail section) + `tests/unit/config/test_example_config.py` | Unit | ✅ 16/16 (Phase 3-5 tests) | Written — secret-leakage (6.1), source-inspection (6.2), `.gitignore` (6.3) tests passed immediately against Phase 1-5 code (as tasks.md 6.3 anticipated for the `.gitignore` case; the guardrails already held by construction); `config.example.yaml` tests (6.4) failed with `FileNotFoundError` confirming RED for the missing template file | GREEN: 38/38 passed pre-6.5 (guardrails + gitignore), 3/3 failed for example-config pre-6.5 | 5 leakage scenarios x (missing file, malformed YAML, empty name, duplicate name, empty conn string) + 1 end-to-end repr check + 3 modules x source-inspection + both-auth-mode + placeholder-marker checks | ✅ Clean | |
| 6.5-6.8 | (implementation only; tests already written in 6.1-6.4) | Unit | ✅ 38/38 (guardrail tests) | n/a (GREEN-only tasks per tasks.md phrasing) | 41/41 passed (whole `tests/unit/config/` suite) after adding `config.example.yaml` and `config/__init__.py` | n/a | ✅ Clean | `config.example.yaml` written with both SQL-auth and Windows-auth placeholder entries; `__init__.py` re-exports the 6 public API names with explicit `__all__`. |
| 7.1-7.4 | (verification only) | n/a | ✅ 41/41 (`tests/unit/config/`) | n/a | 43/43 passed (whole-repo `pytest`, includes prior smoke tests) | n/a | n/a | Coverage spot-check: all 17 spec.md scenarios across the 6 ADDED requirements mapped to at least one test (see table below); no gaps found. `pyproject.toml` `dependencies` confirmed to contain only `PyYAML>=6.0`. |

### Test Summary

- **Total tests written**: 41 (`tests/unit/config/`: 6 errors + 5 models + 27 loader + 3 example-config)
- **Total tests passing**: 41/41 (`tests/unit/config/`), 43/43 (whole repo, including 2 pre-existing smoke tests)
- **Layers used**: Unit (41), Integration (0 new — 1 pre-existing smoke test unaffected), E2E (0)
- **Approval tests** (refactoring): None — no refactoring tasks; all files were newly created.
- **Pure functions created**: `load_profiles` is the only substantive function; it is deliberately I/O-adjacent (reads one file) rather than pure, per design.md's own acknowledgment that the loader is the sole I/O boundary. `ConnectionProfile` and the `errors.py` factory classmethods are pure/deterministic.

## Coverage Matrix (design.md §8, cross-checked against spec.md scenarios)

| Spec scenario | Test(s) |
|---|---|
| Profile exposes name + raw string only | `test_models.py::test_profile_exposes_only_name_and_connection_string` |
| Windows integrated auth accepted | `test_models.py::test_windows_auth_connection_string_accepted_unchanged`, `test_loader.py::test_two_entry_file_returns_two_profiles` |
| Loader accepts explicit file path / omission -> TypeError | `test_loader.py::test_load_profiles_from_arbitrary_named_file_and_location`, `test_loader.py::test_load_profiles_with_no_args_raises_type_error` |
| Multiple named profiles load | `test_loader.py::test_two_entry_file_returns_two_profiles` |
| Arbitrary number of profiles | `test_loader.py::test_arbitrary_number_of_profiles_load[1/3/20]` |
| Whitespace trimmed on load | `test_loader.py::test_leading_and_trailing_whitespace_is_trimmed` |
| Loader has no fallback credentials | `test_loader.py::test_no_hardcoded_credential_literals_outside_comments_or_docstrings[loader/models/errors]` |
| config.local.yaml git-ignored | `test_loader.py::test_gitignore_ignores_config_local_yaml` |
| Example file: no real creds | `test_example_config.py::test_example_config_values_are_obvious_placeholders` |
| Example file: both auth modes | `test_example_config.py::test_example_config_demonstrates_both_auth_modes` |
| Missing file fails fast | `test_loader.py::test_missing_file_raises_config_file_not_found_error` |
| Malformed YAML fails fast | `test_loader.py::test_malformed_yaml_raises_config_parse_error`, `test_non_mapping_top_level_...`, `test_missing_databases_key_...`, `test_databases_not_a_mapping_...` |
| Empty name rejected | `test_loader.py::test_blank_name_raises_profile_validation_error` |
| Duplicate name rejected (case-insensitive) | `test_loader.py::test_exact_duplicate_yaml_key_raises_profile_validation_error`, `test_case_insensitive_duplicate_name_raises_profile_validation_error` |
| Empty connection string rejected | `test_loader.py::test_blank_connection_string_raises_profile_validation_error` |
| No fragment ever in errors/logs | `test_loader.py::test_no_leakage_on_missing_file/malformed_yaml/empty_name/duplicate_name/empty_connection_string`, `test_repr_redacts_sentinel_secret_end_to_end` |
| Loader returns without touching network | `test_loader.py::test_load_profiles_does_not_import_pyodbc_or_open_sockets` |

No gap found: all 17 scenarios across the 6 ADDED requirements have at least
one corresponding test.

## Assumptions

| id | phase | statement | reversibility | basis |
|---|---|---|---|---|
| sdd-apply-001 | sdd-apply | The `test_profile_exposes_only_name_and_connection_string` test accepts either `AttributeError` or `TypeError` when assigning an undeclared attribute to the frozen+slotted `ConnectionProfile`, instead of asserting `AttributeError` alone as tasks.md 2.1 literally describes. | high | Empirically confirmed via direct interpreter test: CPython 3.13's `dataclass(frozen=True, slots=True)` raises `TypeError` for non-field attribute assignment due to a zero-arg-`super()` / slots-class-rebuild interaction (not project-specific code). The production guardrail design.md mandates — "no extra attributes settable" — is unaffected; this is a test-assertion-only adjustment, internal to this batch, with no external/public-contract impact. Trivially revertible if a future Python version changes this behavior. |

## Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `pyproject.toml` | Modified | Added `PyYAML>=6.0` to `[project].dependencies` (was `[]`). |
| `src/schema_comparator/config/errors.py` | Created | `ConfigError` base + `ConfigFileNotFoundError`/`ConfigParseError`/`ProfileValidationError`, with pre-composed secret-safe factory messages. |
| `src/schema_comparator/config/models.py` | Created | `ConnectionProfile` frozen slotted dataclass with redacting `__repr__`. |
| `src/schema_comparator/config/loader.py` | Created | `load_profiles(config_path)`: explicit-path contract, `_DuplicateKeyLoader` SafeLoader subclass, fail-fast gates (missing file, malformed YAML, wrong shape), trim + blank-name + case-insensitive-duplicate + blank-connection-string validation pipeline. |
| `src/schema_comparator/config/__init__.py` | Modified | Re-exports the 6 public API names (`ConnectionProfile`, `load_profiles`, `ConfigError` + 3 subtypes) with explicit `__all__`. |
| `config.example.yaml` | Created | Repo-root template with both SQL-auth and Windows-auth placeholder entries. |
| `tests/unit/config/test_errors.py` | Created | 6 tests covering the exception hierarchy and factory messages. |
| `tests/unit/config/test_models.py` | Created | 5 tests covering fields/slots, immutability, Windows-auth passthrough, and redacted repr (2 auth modes). |
| `tests/unit/config/test_loader.py` | Created | 27 tests across happy-path, fail-fast, trim/duplicate/validation, and cross-cutting guardrail sections. |
| `tests/unit/config/test_example_config.py` | Created | 3 tests validating `config.example.yaml` shape, placeholder-only values, and both-auth-mode coverage. |
| `.gitignore` | Unchanged | Already contained `config.local.yaml` (line 4); confirmed via test, no edit needed. |

## Deviations from Design

None — implementation matches design.md sections 1-9. The one notable
runtime discovery (CPython 3.13's `frozen=True, slots=True` attribute-error
type quirk, sec. "Assumptions" above) is a test-assertion-level adjustment,
not a deviation from the design's chosen representation (the design's
`@dataclass(frozen=True, slots=True)` choice itself is implemented exactly
as specified).

## Issues Found

None beyond the CPython 3.13 quirk documented above (which does not affect
the guardrail's actual behavior — arbitrary attribute assignment is still
rejected, just with `TypeError` instead of a bare `AttributeError`).

## Workload / PR Boundary

- Mode: single-branch direct commits (delivery strategy: `exception-ok`,
  per proposal.md's pre-approved `size:exception`; branch
  `feat/scaffold-project` functions as trunk for this repo).
- Current work unit: N/A — single change, applied in one session across 6
  incremental commits (Phase 0+1, Phase 2, Phase 3, Phase 4, Phase 5, Phase
  6, tasks.md-only Phase 7 marks folded into this progress write).
- Boundary: started at Phase 0 (dependency setup) through Phase 7 (full-suite
  verification) — the entire `tasks.md` task list for this change.
- Estimated review budget impact: within the Low-risk forecast in tasks.md
  (~450-550 lines across 8 files; actual: 6 production/config files + 4 test
  files + `pyproject.toml`, no single file materially exceeding the forecast).

## Status

All tasks (0.1 through 7.4) complete. 41/41 unit tests passing in
`tests/unit/config/`; 43/43 passing whole-repo (`pytest`). Ready for
`sdd-verify`.
