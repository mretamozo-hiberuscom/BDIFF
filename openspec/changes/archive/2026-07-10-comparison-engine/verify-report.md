# Verify Report: Comparison Engine

Change: `comparison-engine`
Phase: verify
Date: 2026-07-10

## Overall Outcome: **PASS**

## Test Suite Execution (actual, re-run during verify)

Command: `python -m pytest -q`

```
s....................................................................... [ 84%]
.............                                                            [100%]
84 passed, 1 skipped in 0.20s
```

- 84 passed, 1 skipped (pre-existing live-DB integration test —
  `tests/integration/test_extraction_live.py`, unrelated to this change,
  skipped due to no live SQL Server connection available).
- 0 failures. Matches the count reported in `apply-progress.md`.
- `tests/unit/compare/` contributes 14 of the 84 passing tests
  (`test_models.py`: 3, `test_errors.py`: 3, `test_engine.py`: 8).

No `quality_gates:` block is declared in `openspec/config.yaml`
(`rules.verify.test_command` is empty, `coverage_threshold: 0`) — no
quality-gate audit block is written to `state.yaml` per the no-op contract.

## Requirement-by-Requirement Traceability

Spec declares **11** Given/When/Then scenarios across 5 requirements (not
12 — see Note below).

| Requirement | Scenario | Test | Result |
|---|---|---|---|
| REQ-001 | Valid multi-profile input is accepted | `test_valid_multi_profile_input_is_accepted` | PASS |
| REQ-001 | Fewer than 2 snapshots is rejected | `test_fewer_than_two_snapshots_is_rejected` | PASS |
| REQ-001 | Duplicate profile names is rejected | `test_duplicate_profile_names_is_rejected` | PASS |
| REQ-002 | Union includes tables from every snapshot | `test_union_includes_tables_from_every_snapshot` | PASS |
| REQ-002 | Union membership is independent of input order | `test_union_result_ordering_is_independent_of_input_order` | PASS |
| REQ-003 | Table missing from one of three profiles | `test_table_missing_from_one_of_three_profiles` | PASS |
| REQ-003 | Table missing from multiple profiles | `test_table_missing_from_multiple_profiles` | PASS |
| REQ-003 | Table present everywhere produces no entry | `test_table_present_everywhere_produces_no_entry` | PASS |
| REQ-004 | Result ordering is stable across input snapshot order | `test_union_result_ordering_is_independent_of_input_order` (shared assertion) | PASS |
| REQ-004 | Entries are ordered by qualified table identity | `test_entries_are_ordered_by_ascending_qualified_table_identity` | PASS |
| REQ-005 | Identical snapshots produce an empty diff | `test_identical_snapshots_produce_an_empty_diff` | PASS |

All 11 scenarios have a corresponding, passing, in-memory unit test. No
scenario is untested or only indirectly covered.

### Note: scenario count (11, not 12)

The task request references "12 scenarios," but the spec
(`specs/comparison-engine/spec.md`), `design.md` §6, and `tasks.md`'s own
reconciliation table all consistently enumerate **11** scenarios (3 + 2 + 3
+ 2 + 1). This is a discrepancy in the phase-kickoff description, not a gap
in the spec, design, tasks, or implementation — all four artifacts agree
with each other. No finding raised against any artifact for this.

### Clarifications section — `MissingTable` minimal payload

Spec's Clarifications section (Session 2026-07-10) resolves that
`MissingTable` MUST carry only `schema_name`, `table_name`, and
`missing_from_profile` — no column metadata from profiles where the table
exists. Verified directly against `src/schema_comparator/compare/models.py`:

```python
@dataclass(frozen=True, slots=True)
class MissingTable:
    schema_name: str
    table_name: str
    missing_from_profile: str
```

Exactly 3 fields, matching the clarify decision precisely. No column data,
no snapshot reference, no extra fields. `test_models.py` further confirms
immutability (`frozen=True`) and the `qualified_name` property shape. PASS.

## Design Conformance

- Module layout matches design §1 exactly: `compare/models.py`,
  `compare/errors.py`, `compare/engine.py`, `compare/__init__.py` — no
  `connectors/`-equivalent, as designed (no I/O boundary in this capability).
- Public API surface (`compare/__init__.py`) matches design's specified
  `__all__` list verbatim: `ComparisonResult`, `MissingTable`,
  `compare_snapshots`, `ComparisonError`, `InsufficientSnapshotsError`,
  `DuplicateProfileNameError`.
- `ComparisonResult` / `MissingTable` shapes match design §2 verbatim,
  including the `DiffEntry = MissingTable` alias and its forward-
  compatibility rationale (docstring-only, no premature type union).
- `errors.py` matches design §3 verbatim: `ComparisonError` base,
  `InsufficientSnapshotsError.for_count`, `DuplicateProfileNameError.for_names`.
- `engine.py`'s `_validate` checks count before duplicate names, matching
  design §3's stated ordering rationale ("count first, since a
  duplicate-name check on a single-element input is meaningless") — also
  independently exercised by `test_count_check_happens_before_duplicate_check`.
- Two-pass algorithm (`_build_presence_index` / `_evaluate`) matches design
  §4 verbatim: plain `set`/`dict`, no materialized reference snapshot, no
  pairwise O(N²) comparison.
- Ordering rules match design §5 verbatim: `sorted(union)` for table
  identity, `sorted(profile_names)` for `compared_profiles`, `sorted(...)`
  for `missing_from` — no sort ever applied over the raw input `snapshots`
  sequence itself.
- `compare_snapshots` composes `_validate → profile_names → union/presence →
  evaluate → ComparisonResult`, matching design §4's final composition
  exactly.

No deviation from `design.md` found. `apply-progress.md`'s own "Deviations
from design: None" claim is confirmed correct.

## Tasks Conformance

All 15 tasks across Phases 1-5 in `tasks.md` are marked `[x]` and verified
as actually implemented:

- Phase 1 (data model): `MissingTable`, `DiffEntry` alias, `ComparisonResult`
  — present, matches spec.
- Phase 2 (errors): `ComparisonError`, `InsufficientSnapshotsError.for_count`,
  `DuplicateProfileNameError.for_names`, `_validate` ordering — present.
- Phase 3 (engine): `_build_presence_index`, `_evaluate`, `compare_snapshots`,
  `__init__.py` re-exports — present.
- Phase 4 (tests): `tests/unit/compare/__init__.py`, `conftest.py`
  (`make_snapshot`), `test_models.py`, `test_errors.py`, `test_engine.py` —
  present, 14 tests total, covering all 11 spec scenarios plus 2 extra
  immutability checks and 1 extra validation-ordering check.
- Phase 5 (verification): `pytest tests/unit/compare` re-run during this
  verify phase — 14 passed, no DB/network access attempted (confirmed: no
  `pyodbc` import or network call anywhere in `tests/unit/compare/`).

Reconciliation table in `tasks.md` claims "MUST coverage: complete,
SHOULD/MAY gaps: none" — confirmed accurate against the spec (spec itself
states "No SHOULD/MAY-level requirements apply in this capability").

## Non-Goals Compliance

Spec's Non-Goals section prohibits missing-column detection, type/size/
precision/scale/nullability mismatch detection, rename heuristics, and
report generation/rendering. Confirmed absent from
`src/schema_comparator/compare/` — the module contains only `MissingTable`,
`ComparisonResult`, and the union/evaluate/validate engine functions. No
report or rendering code exists anywhere in `compare/`.

## Findings

None raised. No CRITICAL, WARNING, or SUGGESTION findings against code,
tasks, design, or spec.

## Skill Resolution

`injected`
