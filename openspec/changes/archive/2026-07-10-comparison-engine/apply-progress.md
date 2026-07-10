# Apply Progress: Comparison Engine

## Batch 1 (complete)

Implemented the full `comparison-engine` capability per `tasks.md` in a
single batch, matching the design's `compare/` module layout
(`models.py`, `errors.py`, `engine.py`, `__init__.py`) and the existing
`discovery/` package's conventions (frozen `slots` dataclasses,
classmethod-based domain error constructors, thin orchestration function).

### Files changed

- `src/schema_comparator/compare/models.py` — `MissingTable` (frozen,
  `slots`, `qualified_name` property) and `ComparisonResult` (frozen,
  `slots`), plus the `DiffEntry = MissingTable` type alias.
- `src/schema_comparator/compare/errors.py` — `ComparisonError` base,
  `InsufficientSnapshotsError.for_count(count)`,
  `DuplicateProfileNameError.for_names(names)`.
- `src/schema_comparator/compare/engine.py` — `_validate`,
  `_build_presence_index` (Pass 1: union + per-profile presence sets),
  `_evaluate` (Pass 2: deterministic missing-table detection), and the
  public `compare_snapshots` entry point.
- `src/schema_comparator/compare/__init__.py` — public API re-exports with
  explicit `__all__` (replaces the prior docstring-only placeholder).
- `tests/unit/compare/__init__.py`, `conftest.py` (`make_snapshot` fixture
  helper), `test_models.py`, `test_errors.py`, `test_engine.py` — full
  coverage of the design §6 scenario matrix (11 spec scenarios).

### Tasks completed

All tasks in Phases 1-5 of `tasks.md` are checked off (`[x]`).

### Test results

- `pytest tests/unit/compare -q` → 14 passed.
- Full suite `pytest -q` → 84 passed, 1 skipped (pre-existing live-DB
  integration test, unaffected by this change).

### Deviations from design

None. Implementation follows `design.md` §1-§6 as written: module layout,
public API surface, data model shapes, precondition validation ordering
(count check before duplicate-name check), the two-pass union algorithm,
and the deterministic ordering rules (`sorted(union)`, `sorted(profile_names)`,
`sorted(missing_from)`).

### Notes

- One test in `test_engine.py` (`test_union_includes_tables_from_every_snapshot`)
  initially asserted only the tables absent from at least one profile;
  corrected to include all three table identities from the spec's own
  scenario, since none of the three tables in that fixture is present in
  every compared profile and therefore all three surface as missing-table
  entries.
- No new third-party dependencies were introduced.
