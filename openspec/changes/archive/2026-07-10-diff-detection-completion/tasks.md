# Tasks: Diff Detection Completion (Change A)

## Spec/Design Reconciliation

| Requirement / Scenario | Priority | Design Allocation | Status | Notes |
|------------------------|----------|-------------------|--------|-------|
| REQ-comparison-engine-006 (missing-column detection, scoped to matched tables, no double-reporting with `MissingTable`) | MUST | `compare/models.py` `MissingColumn` (§2.2), `compare/engine.py` `_evaluate_columns` missing-branch (§3.3) | covered-by-design | Exclusion of profiles missing the table is structural via `profiles_with_table` membership, not a post-filter. |
| REQ-comparison-engine-007 (column attribute-mismatch detection, one entry per column naming every present profile, `values_by_profile` sorted by profile name) | MUST | `compare/models.py` `ColumnAttributes`/`ColumnMismatch` (§2.1, §2.3), `compare/engine.py` `_evaluate_columns` mismatch-branch (§3.3) | covered-by-design | Plain dataclass field equality on `ColumnAttributes` handles `None`-vs-concrete and nullable-only cases with no special-case code. |
| REQ-comparison-engine-004 MODIFIED (cross-type ordering `MissingTable` < `MissingColumn` < `ColumnMismatch`, then column name ascending) | MUST | `compare/engine.py` `_TYPE_RANK`/`_sort_key`, unified `sorted()` in `compare_snapshots` (§4) | covered-by-design | Single total sort-key function over concatenated table+column entries; no per-pass sort + merge. |
| Non-Goals narrowing (no HTML/PDF/console rendering, no likely-rename heuristics) | MUST | N/A (scope boundary, not implemented behavior) | covered-by-design | No task touches `report/` or `tui/`; enforced by scope, verified in Phase 5. |

### Reconciliation Verdict
- MUST coverage: complete
- SHOULD/MAY gaps: none (spec delta defines no SHOULD/MAY requirements)
- Ambiguities to track: none — all five proposal risks are pinned as explicit spec scenarios per design §7.

## Review Workload Forecast

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Medium

| Field | Value |
|-------|-------|
| Estimated changed lines | ~520-620 (source ~140: `models.py` +~70 for `ColumnAttributes`/`MissingColumn`/`ColumnMismatch`/widened alias, `engine.py` +~60 for `_build_table_index`/`_evaluate_columns`/`_sort_key`/rename, `__init__.py` +~10; tests ~380-480 across fixture additions and 2 test-module extensions covering the ~24-scenario matrix) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR (size:exception) — `delivery_strategy: exception-ok` per this task's instructions; work units below are for reviewer navigation only, not separate PRs |
| Delivery strategy | exception-ok |
| Chain strategy | size-exception |

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Data model: `ColumnAttributes`, `MissingColumn`, `ColumnMismatch` (Phase 1) | PR 1 (single, size:exception) | No behavior yet; pure value types, TDD-paired. |
| 2 | Test fixture additions (Phase 2) | PR 1 (single, size:exception) | `make_column`/`make_table`/`make_snapshot_with_tables`; needed before Phase 3-5 tests can be written. |
| 3 | Missing-column detection (Phase 3) | PR 1 (single, size:exception) | Depends on Units 1-2; REQ-006. |
| 4 | Mismatch detection (Phase 4) | PR 1 (single, size:exception) | Depends on Units 1-3; REQ-007; extends the same `_evaluate_columns`. |
| 5 | Cross-type ordering (Phase 5) | PR 1 (single, size:exception) | Depends on Units 3-4 producing both entry kinds; modified REQ-004. |
| 6 | Public API export + verification (Phase 6-7) | PR 1 (single, size:exception) | Depends on Units 1-5. |

### Checklist Status Legend

- `[ ]` Not implemented yet
- `[~]` Implemented but not yet verified locally
- `[x]` Implemented and verified locally

## Phase 1: Data Model — `ColumnAttributes`, `MissingColumn`, `ColumnMismatch`

- [x] 1.1 **(RED)** In `tests/unit/compare/test_models.py`, write failing tests `test_column_attributes_from_snapshot_copies_comparable_fields`, `test_column_attributes_excludes_ordinal_position_and_name` (assert via `dataclasses.fields(...)`), `test_column_attributes_equal_instances_compare_equal`, `test_column_attributes_differing_instances_compare_unequal`, per design §2.1 and §7.2.
- [x] 1.2 **(GREEN)** In `src/schema_comparator/compare/models.py`, add the frozen `slots` dataclass `ColumnAttributes` (`data_type`, `character_maximum_length`, `numeric_precision`, `numeric_scale`, `is_nullable`) with `from_snapshot(column: ColumnSnapshot)` classmethod, per design §2.1, to make 1.1 pass.
- [x] 1.3 **(RED)** In `tests/unit/compare/test_models.py`, write failing tests `test_missing_column_qualified_name_returns_schema_and_table_pair` and `test_missing_column_is_immutable`, per design §2.2 and §7.2.
- [x] 1.4 **(GREEN)** In `models.py`, add the frozen `slots` dataclass `MissingColumn` (`schema_name`, `table_name`, `column_name`, `missing_from_profile`, plus `qualified_name` property), per design §2.2, to make 1.3 pass.
- [x] 1.5 **(RED)** In `tests/unit/compare/test_models.py`, write failing tests `test_column_mismatch_qualified_name_returns_schema_and_table_pair` and `test_column_mismatch_is_immutable`, per design §2.3 and §7.2.
- [x] 1.6 **(GREEN)** In `models.py`, add the frozen `slots` dataclass `ColumnMismatch` (`schema_name`, `table_name`, `column_name`, `values_by_profile: tuple[tuple[str, ColumnAttributes], ...]`, plus `qualified_name` property) and widen `DiffEntry = MissingTable | MissingColumn | ColumnMismatch`, per design §2.3-§2.4, to make 1.5 pass.

## Phase 2: Test Fixture Additions

- [x] 2.1 In `tests/unit/compare/conftest.py`, add `make_column(name, *, data_type="int", character_maximum_length=None, numeric_precision=None, numeric_scale=None, is_nullable=False, ordinal_position=1)`, `make_table(schema_name, table_name, *columns)`, and `make_snapshot_with_tables(profile_name, *tables)` helpers, keeping the existing `make_snapshot` unchanged, per design §7.1. (Test infrastructure only — no paired failing-test step; consumed by Phases 3-5.)

## Phase 3: Engine — Missing-Column Detection (REQ-comparison-engine-006)

- [x] 3.1 **(RED)** In `tests/unit/compare/test_engine.py`, write failing tests `test_column_missing_from_one_profile_of_matched_table`, `test_column_missing_from_a_subset_of_matched_tables_profiles`, `test_column_present_in_every_profile_produces_no_missing_column_entry`, `test_table_missing_entirely_produces_no_missing_column_entries_for_that_profile`, and `test_table_present_in_only_one_profile_produces_no_column_level_entries`, using the Phase 2 fixtures, per design §7.3 and spec REQ-006 scenarios.
- [x] 3.2 **(GREEN)** In `src/schema_comparator/compare/engine.py`, add `_build_table_index(snapshots)` (per-profile qualified-name-keyed `TableSnapshot` lookup) and `_evaluate_columns(union, presence, table_index, profile_names)` with the missing-column branch only (matched-table gate `len(profiles_with_table) < 2` → skip; emit one `MissingColumn` per profile lacking each column name in the union), and wire both into `compare_snapshots`, per design §3.2-§3.3, to make 3.1 pass.

## Phase 4: Engine — Column Attribute-Mismatch Detection (REQ-comparison-engine-007)

- [x] 4.1 **(RED)** In `tests/unit/compare/test_engine.py`, write failing tests `test_identical_column_attributes_produce_no_mismatch_entry`, `test_differing_data_type_produces_one_mismatch_entry`, `test_type_variance_across_three_profiles_named_individually_in_one_entry`, `test_nullable_only_difference_produces_a_mismatch_entry`, `test_ordinal_position_only_difference_produces_no_mismatch_entry`, `test_none_vs_concrete_value_is_a_genuine_mismatch`, `test_values_by_profile_is_ordered_by_profile_name`, and `test_column_can_be_both_missing_and_mismatched_simultaneously`, per design §7.3 and spec REQ-007 scenarios.
- [x] 4.2 **(GREEN)** In `engine.py`, extend `_evaluate_columns` with the mismatch branch: for each column name with 2+ present profiles, build `ColumnAttributes.from_snapshot(...)` per present profile, and emit exactly one `ColumnMismatch` (with `values_by_profile` sorted ascending by profile name) when `set(attrs_by_profile.values())` has more than one distinct value, per design §3.3, to make 4.1 pass.

## Phase 5: Engine — Deterministic Cross-Type Ordering (MODIFIED REQ-comparison-engine-004)

- [x] 5.1 **(RED)** In `tests/unit/compare/test_engine.py`, write failing tests `test_cross_type_ordering_missing_table_before_missing_column_before_mismatch`, `test_same_type_entries_for_the_same_table_are_ordered_by_column_name`, and `test_column_level_entries_ordering_is_independent_of_input_snapshot_order`, per design §7.3 and spec REQ-004 scenarios.
- [x] 5.2 **(GREEN)** In `engine.py`, rename `_evaluate` to `_evaluate_tables` (logic unchanged), add the module-level `_TYPE_RANK` mapping (`MissingTable: 0`, `MissingColumn: 1`, `ColumnMismatch: 2`) and `_sort_key(entry)` function (qualified table identity, then type rank, then `column_name`/`missing_from_profile` defaults via `getattr`), and update `compare_snapshots` to compute `entries = tuple(sorted(table_entries + column_entries, key=_sort_key))`, per design §3.1 and §4, to make 5.1 pass.

## Phase 6: Public API Export

- [x] 6.1 Update `src/schema_comparator/compare/__init__.py` to import and re-export `ColumnAttributes`, `ColumnMismatch`, `MissingColumn` alongside the existing exports, updating `__all__` accordingly, per design §5.

## Phase 7: Verification

- [x] 7.1 Run `pytest tests/unit/compare tests/unit/test_import_smoke.py --cov=schema_comparator.compare` and confirm every scenario in spec REQ-006, REQ-007, and the modified REQ-004 has a passing test, with no DB/network access attempted and no regression in existing `MissingTable`-only tests.
- [x] 7.2 Confirm `src/schema_comparator/report/` and `src/schema_comparator/tui/` are untouched (`git status`/`git diff --stat` shows no changes under either path), per the proposal's Non-Goals and Rollback Plan.

## Review Workload Forecast

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Medium

| Field | Value |
|-------|-------|
| Estimated changed lines | ~520-620 total: `models.py` ~+70, `engine.py` ~+60 (net, after rename), `compare/__init__.py` ~+10; test changes ~380-480 across `conftest.py` fixture additions, `test_models.py` (+8 tests), and `test_engine.py` (+16 tests) |
| Files touched | `src/schema_comparator/compare/models.py`, `src/schema_comparator/compare/engine.py`, `src/schema_comparator/compare/__init__.py`, `tests/unit/compare/conftest.py`, `tests/unit/compare/test_models.py`, `tests/unit/compare/test_engine.py` (6 files; `errors.py`, `discovery/`, `report/`, `tui/` unchanged) |
| Chained PRs recommended | No — single additive change to one capability's implementation, no cross-cutting surface to slice by reviewer concern |
| 400-line budget risk | Medium — estimated total exceeds the 400-line guideline, but the change is one cohesive, non-severable unit (data model + engine pass + tests for two tightly coupled requirements); `delivery_strategy: exception-ok` was set for this change |
| Decision needed before apply | No — delivery strategy and scope are already fixed by the proposal/design; no open question blocks starting `sdd-apply` |
