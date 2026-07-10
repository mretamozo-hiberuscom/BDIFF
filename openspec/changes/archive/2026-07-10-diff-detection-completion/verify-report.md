# Verify Report: Diff Detection Completion (Change A)

Status: verify phase complete
Overall outcome: **PASS WITH WARNINGS**

## Test Suite Re-Run (independent confirmation)

Command: `python -m pytest -q` (run fresh in this verify session, not copied
from apply-progress.md)

Result: **108 passed, 1 skipped** — matches `apply-progress.md`'s "Final Full
Suite Run" exactly. Not stale.

`pytest-cov` availability re-checked: `pip show pytest-cov` → "Package(s) not
found", confirming apply-progress.md's claim that task 7.1's literal command
(`--cov=schema_comparator.compare`) could not run in this environment.

## Requirement-by-Requirement Scenario Check (code read directly, not
narrative-trusted)

### REQ-comparison-engine-006 (Detect Missing Columns)

All four spec scenarios have a corresponding test with a real, non-trivial
equality assertion against the exact expected entry tuple (not just
"non-empty" or "truthy"):

- Column missing from one profile → `test_column_missing_from_one_profile_of_matched_table`. PASS, assertion is exact-tuple equality.
- Column missing from a subset (c, d) → `test_column_missing_from_a_subset_of_matched_tables_profiles`. PASS, asserts both entries present in ascending profile-name order.
- Column present everywhere → no entry → `test_column_present_in_every_profile_produces_no_missing_column_entry`. PASS, asserts `entries == ()`.
- Table missing entirely → no MissingColumn for that profile → `test_table_missing_entirely_produces_no_missing_column_entries_for_that_profile`. PASS, asserts only a `MissingTable` entry, no `MissingColumn` siblings.

Code in [engine.py](../../../src/schema_comparator/compare/engine.py)
`_evaluate_columns`: the `profiles_with_table` gate (`len(...) < 2` → skip)
is structural, matching design §3.3 — confirmed by reading the function
directly, not just trusting the design narrative.

### REQ-comparison-engine-007 (Detect Column Attribute Mismatches)

All eight spec scenarios have a corresponding test, each asserting the
exact `ColumnMismatch` tuple (including `values_by_profile` ordering), not
an incidental pass:

- Identical attributes → no entry: `test_identical_column_attributes_produce_no_mismatch_entry`. PASS.
- Differing `data_type`, 2 profiles: `test_differing_data_type_produces_one_mismatch_entry`. PASS.
- 3-way variance, one entry: `test_type_variance_across_three_profiles_named_individually_in_one_entry`. PASS, asserts a single entry naming all three profiles.
- Nullable-only difference: `test_nullable_only_difference_produces_a_mismatch_entry`. PASS.
- Ordinal-position-only, no entry: `test_ordinal_position_only_difference_produces_no_mismatch_entry`. PASS — confirms `ColumnAttributes` correctly excludes `ordinal_position` from comparison (also independently confirmed by reading the dataclass field list in models.py, which has no `ordinal_position` field at all).
- None-vs-concrete value: `test_none_vs_concrete_value_is_a_genuine_mismatch`. PASS, confirms no coercion.
- `values_by_profile` sorted by profile name: `test_values_by_profile_is_ordered_by_profile_name`. PASS, feeds profiles in `c, a` input order and asserts output order `a, c`.
- Column both missing and mismatched: `test_column_can_be_both_missing_and_mismatched_simultaneously`. PASS, and this test also incidentally proves `MissingColumn` sorts before `ColumnMismatch` for the same column/table.

### REQ-comparison-engine-004 MODIFIED (cross-type ordering)

Three of four spec scenarios are well covered:

- Input-order independence: `test_union_result_ordering_is_independent_of_input_order` (pre-existing) plus `test_column_level_entries_ordering_is_independent_of_input_snapshot_order` (new). PASS.
- Qualified-table-identity-first ordering: pre-existing tests plus implicitly re-confirmed. PASS.
- Same-type entries ordered by column name: `test_same_type_entries_for_the_same_table_are_ordered_by_column_name`. PASS, asserts `alpha` before `zeta`.

**WARNING — incomplete test evidence for the same-table, all-three-kinds
scenario.** The spec's own worked scenario ("Cross-type ordering for the
same table follows MissingTable < MissingColumn < ColumnMismatch") requires
one qualified table to simultaneously produce a `MissingTable`, a
`MissingColumn`, and a `ColumnMismatch` entry, and asserts their relative
order. The test named for this
(`test_cross_type_ordering_missing_table_before_missing_column_before_mismatch`)
does **not** actually construct that situation: it uses two different
tables (`sales.Invoice`, mismatch only, and `sales.Payment`, missing only),
so the observed ordering in that test is fully explained by the pre-existing
qualified-table-identity sort field (`Invoice` < `Payment` alphabetically),
not by the new `_TYPE_RANK` tie-break field being exercised for
same-identity entries. `test_column_can_be_both_missing_and_mismatched_simultaneously`
does independently prove the `MissingColumn` < `ColumnMismatch` half of the
ordering for a shared table, but no test proves `MissingTable` ranks before
`MissingColumn`/`ColumnMismatch` when all three co-occur for the identical
`(schema_name, table_name)` pair (achievable, e.g., 3 profiles where one
profile lacks the table and the other two have a column mismatch).

Manual code reading of `_sort_key` in
[engine.py](../../../src/schema_comparator/compare/engine.py) confirms the
implementation is structurally correct regardless (the `_TYPE_RANK` field
sits ahead of `column_name`/`missing_from_profile` in the sort tuple, so
`MissingTable` always sorts first for a shared identity), but this is a
**test-evidence gap, not a verified-only-by-inspection guarantee** for that
specific scenario. Classified as a tasks-gap (task 5.1 did not literally
include a same-table three-kind fixture), not a code-bug — the code is
correct on inspection.

## Deviation Review

**Deviation 1 (Phases 3-5 implemented as one unified pass instead of
strictly sequential RED-then-GREEN).** Verified as claimed: reading
`test_engine.py`, every Phase 3/4/5 test asserts an exact expected
`ComparisonResult.entries` tuple (full dataclass equality), not a
loosely-typed "something changed" check. These are genuine behavioral
proofs — if any branch of `_evaluate_columns` or `_sort_key` were reverted,
each of these tests would fail on the exact-tuple comparison, independent of
whether it was literally red-then-green during authoring. Accepted: no
CRITICAL raised for this deviation. The one caveat is the cross-type-ordering
gap documented above, which is a scenario-coverage gap, not a symptom of
the phases being merged.

**Deviation 2 (`pytest-cov` unavailable, task 7.1's literal command
could not run).** Confirmed independently (`pip show pytest-cov` fails).
Per the project's testing rules (target 80%+ coverage, `pytest --cov`) this
is a genuine gap in coverage *evidence*, but per the task instructions this
is not to be treated as CRITICAL on its own since `strict_tdd_mode` is
disabled for this project. Classified as WARNING.

## Non-Goals / Scope Boundary Check

`git diff --stat` / `git status` confirm no changes under
`src/schema_comparator/report/` or `src/schema_comparator/tui/`, and no new
precondition category in `compare/errors.py` — matches the design's
Non-Goals and the proposal's Rollback Plan.

## Findings Summary

### CRITICAL
None.

### WARNING
1. **[tasks-gap]** No test constructs the literal REQ-004 scenario of a
   single qualified table producing `MissingTable` + `MissingColumn` +
   `ColumnMismatch` entries simultaneously, so the `MissingTable`-ranks-first
   half of the cross-type ordering is verified by code inspection only, not
   by an independent failing/passing test, for that exact combination.
   Recommend adding one focused test before archive, or explicitly accepting
   the residual risk.
2. **[tasks-gap]** Task 7.1's literal verification command
   (`pytest ... --cov=schema_comparator.compare`) could not run because
   `pytest-cov` is not declared in `pyproject.toml`'s dev extras. Coverage
   percentage evidence for the new `_evaluate_columns`/`ColumnAttributes`/
   `MissingColumn`/`ColumnMismatch` code is therefore unmeasured, only
   scenario-covered. Not CRITICAL per `strict_tdd_mode: disabled`, but a gap
   against the project's stated 80%+ coverage testing standard.

### SUGGESTION
1. Add `pytest-cov` to the project's dev dependencies so future verify runs
   can execute the coverage command as literally specified in tasks.md,
   rather than substituting an equivalent flag-less run.
2. Consider renaming
   `test_cross_type_ordering_missing_table_before_missing_column_before_mismatch`
   to reflect what it actually proves (cross-table qualified-identity
   ordering) once the same-table three-kind test is added, to avoid the test
   name implying broader coverage than it has.

## Verdict

PASS WITH WARNINGS. No CRITICAL issues found; production code was read
directly (not narrative-trusted) for both REQ-006 and REQ-007 and matches
spec and design exactly. The one ordering scenario gap and the missing
coverage command are WARNING-level, non-blocking per this project's
disabled `strict_tdd_mode`. Recommended next step: `sdd-archive`, optionally
after addressing WARNING 1 with a small follow-up test (orchestrator's
call).
