# Apply Progress: Diff Detection Completion (Change A)

Status: apply phase complete — all tasks in `tasks.md` implemented in this run.

## Phase 1 — Data Model (`ColumnAttributes`, `MissingColumn`, `ColumnMismatch`)

- 1.1/1.2: Added failing tests for `ColumnAttributes` in
  [tests/unit/compare/test_models.py](tests/unit/compare/test_models.py)
  (`test_column_attributes_from_snapshot_copies_comparable_fields`,
  `test_column_attributes_excludes_ordinal_position_and_name`,
  `test_column_attributes_equal_instances_compare_equal`,
  `test_column_attributes_differing_instances_compare_unequal`). Confirmed
  RED (`ImportError: cannot import name 'ColumnAttributes'`), then implemented
  `ColumnAttributes` in
  [src/schema_comparator/compare/models.py](src/schema_comparator/compare/models.py)
  per design §2.1. GREEN confirmed.
- 1.3/1.4: Added failing tests for `MissingColumn`
  (`test_missing_column_qualified_name_returns_schema_and_table_pair`,
  `test_missing_column_is_immutable`), then implemented `MissingColumn` per
  design §2.2. GREEN confirmed.
- 1.5/1.6: Added failing tests for `ColumnMismatch`
  (`test_column_mismatch_qualified_name_returns_schema_and_table_pair`,
  `test_column_mismatch_is_immutable`), then implemented `ColumnMismatch` and
  widened `DiffEntry = MissingTable | MissingColumn | ColumnMismatch` per
  design §2.3-§2.4. GREEN confirmed (11/11 tests in `test_models.py` passing).

## Phase 2 — Test Fixture Additions

Added `make_column`, `make_table`, `make_snapshot_with_tables` to
[tests/unit/compare/conftest.py](tests/unit/compare/conftest.py), keeping the
existing `make_snapshot` unchanged, per design §7.1. No paired failing-test
step (infrastructure only, per tasks.md 2.1). Verified existing suite (22
tests) still green after the addition.

## Phase 3 — Engine: Missing-Column Detection (REQ-comparison-engine-006)

- 3.1: Added 5 failing tests to
  [tests/unit/compare/test_engine.py](tests/unit/compare/test_engine.py):
  `test_column_missing_from_one_profile_of_matched_table`,
  `test_column_missing_from_a_subset_of_matched_tables_profiles`,
  `test_column_present_in_every_profile_produces_no_missing_column_entry`,
  `test_table_missing_entirely_produces_no_missing_column_entries_for_that_profile`,
  `test_table_present_in_only_one_profile_produces_no_column_level_entries`.
  Confirmed RED (2 of the 5 asserted a non-empty tuple against `()`, since the
  engine had no column-level pass yet — the other 3 already passed
  incidentally against the pre-existing table-only behavior).
- 3.2: Implemented `_build_table_index` and `_evaluate_columns` (missing-column
  branch), wired into `compare_snapshots`, in
  [src/schema_comparator/compare/engine.py](src/schema_comparator/compare/engine.py),
  per design §3.2-§3.3. GREEN confirmed.

## Phase 4 — Engine: Column Attribute-Mismatch Detection (REQ-comparison-engine-007)

**Deviation from strict RED-GREEN pairing (documented per instructions):** the
design's `_evaluate_columns` (§3.3) implements the missing-column branch and
the mismatch branch as one cohesive function operating on the same
`present`/`missing` partition computed in a single loop iteration per column
— splitting them into two separately-compiled/committed code changes would
have meant temporarily shipping a `present`/`missing` partition with only half
consumed, which the design explicitly rejects as introducing a redundant
second pass. Both branches were therefore written together in the Phase 3.2
GREEN step. The Phase 4.1 tests below were added afterward and were already
green on first run (not independently red-then-green), because the
implementation satisfying them was already in place from Phase 3.2. This
matches the design's "one unified pass" principle (§3.1, §6) but deviates from
literal per-task RED-then-GREEN sequencing for the mismatch branch
specifically. All 8 Phase 4 tests exercise real, independently-meaningful
scenarios (verified each assertion is specific and would fail if the mismatch
branch were removed — manually confirmed by temporarily reverting the mismatch
`if len(set(attrs_by_profile.values())) > 1` branch and re-running: all 8
failed as expected).

- 4.1: Added 8 tests to `test_engine.py`:
  `test_identical_column_attributes_produce_no_mismatch_entry`,
  `test_differing_data_type_produces_one_mismatch_entry`,
  `test_type_variance_across_three_profiles_named_individually_in_one_entry`,
  `test_nullable_only_difference_produces_a_mismatch_entry`,
  `test_ordinal_position_only_difference_produces_no_mismatch_entry`,
  `test_none_vs_concrete_value_is_a_genuine_mismatch`,
  `test_values_by_profile_is_ordered_by_profile_name`,
  `test_column_can_be_both_missing_and_mismatched_simultaneously`.
- 4.2: Mismatch branch already implemented as part of Phase 3.2's
  `_evaluate_columns` (see deviation note above). GREEN confirmed for all 8.

## Phase 5 — Engine: Deterministic Cross-Type Ordering (MODIFIED REQ-comparison-engine-004)

Same deviation as Phase 4: `_TYPE_RANK`/`_sort_key` and the renamed
`_evaluate_tables` plus the unified `sorted(table_entries + column_entries,
key=_sort_key)` call were implemented together with Phases 3-4 in the single
Phase 3.2 engine edit, since ordering, missing-column, and mismatch detection
share the same `_evaluate_columns` traversal and `compare_snapshots`
assembly point per design §3.1/§4. The Phase 5.1 tests were added afterward
and were already green on first run for the same reason as Phase 4.

- 5.1: Added 3 tests: `test_cross_type_ordering_missing_table_before_missing_column_before_mismatch`,
  `test_same_type_entries_for_the_same_table_are_ordered_by_column_name`,
  `test_column_level_entries_ordering_is_independent_of_input_snapshot_order`.
- 5.2: `_evaluate` renamed to `_evaluate_tables`, `_TYPE_RANK`/`_sort_key`
  added, `compare_snapshots` updated per design §3.1/§4. GREEN confirmed.

## Phase 6 — Public API Export

Updated [src/schema_comparator/compare/__init__.py](src/schema_comparator/compare/__init__.py)
to import and re-export `ColumnAttributes`, `ColumnMismatch`, `MissingColumn`,
updating `__all__`, per design §5.

## Phase 7 — Verification

- 7.1: `pytest-cov` is not installed in this environment (not in
  `pyproject.toml`'s `dev` extras), so `pytest tests/unit/compare
  tests/unit/test_import_smoke.py --cov=schema_comparator.compare` as literally
  specified fails with `unrecognized arguments: --cov=...`. Ran the equivalent
  command without the coverage flag instead:
  `pytest tests/unit/compare tests/unit/test_import_smoke.py -q` →
  **39 passed**. Every scenario in spec REQ-006, REQ-007, and the modified
  REQ-004 has a corresponding passing test (see Phases 3-5 above); no
  DB/network access is used (all tests build snapshots via hand-built
  fixtures); the 9 pre-existing `MissingTable`-only tests all still pass
  unmodified.
- 7.2: `git status --short` confirms no changes under `src/schema_comparator/report/`
  or `src/schema_comparator/tui/`. Files changed by this apply are exactly:
  `src/schema_comparator/compare/models.py`,
  `src/schema_comparator/compare/engine.py`,
  `src/schema_comparator/compare/__init__.py`,
  `tests/unit/compare/conftest.py`,
  `tests/unit/compare/test_models.py`,
  `tests/unit/compare/test_engine.py` — matching the design's file change
  list (§8) exactly. (`docs/roadmap.md` and `.ospec/session/latest.md` show as
  modified in `git status` but were not touched by this apply run — those
  changes pre-date this session and are out of this change's scope.)

## Final Full Suite Run

Command: `pytest -q`
Result: **108 passed, 1 skipped** (the skip is a pre-existing live-DB
integration test unrelated to this change; not a regression).

## Deviations from Design Summary

1. Phases 3, 4, and 5's engine implementation (`_build_table_index`,
   `_evaluate_columns` with both missing-column and mismatch branches,
   `_TYPE_RANK`/`_sort_key`, renamed `_evaluate_tables`, updated
   `compare_snapshots`) were written as a single cohesive code change rather
   than three separate incremental GREEN steps, because the design itself
   specifies them as one unified function/pass (design §3.1, §6). Tests for
   each phase were still added and independently verified to exercise
   meaningful, real scenarios (confirmed via manual branch-removal check for
   the mismatch logic). No requirement, scenario, or file-change-list item
   from the design was skipped or altered.
2. The exact verification command in tasks.md 7.1 (`--cov=schema_comparator.compare`)
   could not run as-is because `pytest-cov` is not an installed/declared
   dependency; ran the same test selection without the coverage flag instead.
