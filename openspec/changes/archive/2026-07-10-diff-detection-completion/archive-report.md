# Archive Report: Diff Detection Completion (Change A)

**Change**: `diff-detection-completion`
**Archive date**: 2026-07-10
**Verification verdict**: PASS WITH WARNINGS (no CRITICAL findings)

## Close Gate

`verify-report.md` reports **PASS WITH WARNINGS**: independent re-run of
`pytest -q` reproduced 108 passed / 1 skipped, matching `apply-progress.md`
exactly. Both new requirements (REQ-comparison-engine-006,
REQ-comparison-engine-007) and the modified ordering requirement
(REQ-comparison-engine-004) were traced scenario-by-scenario to passing
tests by reading `engine.py`/`models.py` directly, not by trusting the
narrative. Zero CRITICAL findings. Two WARNING findings, both accepted as
non-blocking follow-up notes rather than fixed before archive:

1. **Ordering test-evidence gap**: no single test constructs one qualified
   table producing `MissingTable` + `MissingColumn` + `ColumnMismatch`
   simultaneously, so the `MissingTable`-ranks-first half of the cross-type
   tie-break is verified by code inspection of `_sort_key` (structurally
   correct) rather than by an independent test for that exact combination.
   Accepted as a residual, low-risk scenario-coverage gap — recommended as
   a small follow-up test, not a blocker for this change.
2. **Coverage command unavailable**: `pytest-cov` is not declared in
   `pyproject.toml`'s dev extras, so task 7.1's literal
   `--cov=schema_comparator.compare` command could not run. Scenario
   coverage is complete (verified above); percentage coverage evidence is
   unmeasured. Not CRITICAL per this project's disabled `strict_tdd_mode`.
   Recommended as a dev-dependency addition, not a blocker.

Non-goals compliance confirmed: no changes under
`src/schema_comparator/report/` or `src/schema_comparator/tui/`, and no new
precondition category added to `compare/errors.py`. Archive is permitted.

## What Shipped

- `ColumnAttributes` (comparable subset of `ColumnSnapshot`: `data_type`,
  `character_maximum_length`, `numeric_precision`, `numeric_scale`,
  `is_nullable`; excludes `ordinal_position` and `name`), `MissingColumn`,
  and `ColumnMismatch` frozen dataclasses added to
  [src/schema_comparator/compare/models.py](../../../src/schema_comparator/compare/models.py);
  `DiffEntry` widened to `MissingTable | MissingColumn | ColumnMismatch`.
- `_build_table_index` and `_evaluate_columns` (missing-column and
  attribute-mismatch branches, one unified per-matched-table pass) added to
  [src/schema_comparator/compare/engine.py](../../../src/schema_comparator/compare/engine.py);
  `_evaluate` renamed `_evaluate_tables`; new `_TYPE_RANK`/`_sort_key`
  implement the deterministic cross-type ordering
  (`MissingTable` < `MissingColumn` < `ColumnMismatch`, then column name).
- Public API export of `ColumnAttributes`, `ColumnMismatch`, `MissingColumn`
  from `src/schema_comparator/compare/__init__.py`.
- New unit test fixtures (`make_column`, `make_table`,
  `make_snapshot_with_tables`) and 24 new tests across
  `tests/unit/compare/test_models.py` and `tests/unit/compare/test_engine.py`
  covering every REQ-006/REQ-007/modified-REQ-004 scenario.
- Full suite: 108 passed, 1 skipped (pre-existing, unrelated live-DB
  integration test) — no regression to the 9 pre-existing
  `MissingTable`-only tests.

## Specification Synchronization

| Domain | Action | Details |
|--------|--------|---------|
| `comparison-engine` | Merged | Change-local delta spec at [openspec/changes/diff-detection-completion/specs/comparison-engine/spec.md](specs/comparison-engine/spec.md) merged into the baseline at [openspec/specs/comparison-engine/spec.md](../../specs/comparison-engine/spec.md): added REQ-comparison-engine-006 (Detect Missing Columns) and REQ-comparison-engine-007 (Detect Column Attribute Mismatches) with their Given/When/Then scenarios; modified REQ-comparison-engine-004 to pin the concrete `MissingTable` < `MissingColumn` < `ColumnMismatch` cross-type tie-break with two additional scenarios; narrowed the Non-Goals section to remove the missing-column/mismatch-detection exclusions (both are now in scope) while keeping likely-rename heuristics and report/console rendering out of scope; appended the change's clarification session verbatim. |

The canonical specification remains:

- `openspec/specs/comparison-engine/spec.md`

No other capability baseline (`schema-extraction`,
`connection-profile-config`) was touched; this change only reads
`ColumnSnapshot`/`TableSnapshot.columns` as an already-sorted, immutable
input.

## Decisions and ADRs

No `open_decisions` entries or change-local ADR files were present to
promote. The five clarification-session Q&A pairs recorded in the
change-local delta spec (`ColumnMismatch` entry-count semantics, cross-type
ordering, missing-table/missing-column exclusivity, `ordinal_position`
exclusion, `values_by_profile` ordering) were resolved without a blocking
user question and are preserved verbatim in the merged baseline spec's
Clarifications section; none are duplicated as separate project ADRs.

## Archive Copy

Artifacts were copied to
`openspec/changes/archive/2026-07-10-diff-detection-completion/`. The
active source directory (`openspec/changes/diff-detection-completion/`)
remains in place pending orchestrator-owned inventory verification and
deletion — no file-delete tool was available to this executor to remove it
directly (same limitation noted in the prior `comparison-engine` archive).

## Cost

No per-phase cost data was recorded for this change
(`.ospec/session/diff-detection-completion/phase-costs.jsonl` missing or
empty).

**Total user questions asked**: 0 (all clarifications resolved during the
spec-writing phase without a blocking user question).
