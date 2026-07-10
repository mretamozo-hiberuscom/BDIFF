# Tasks: Comparison Engine

## Spec/Design Reconciliation

| Requirement / Scenario | Priority | Design Allocation | Status | Notes |
|------------------------|----------|-------------------|--------|-------|
| REQ-comparison-engine-001 (accept N-way named snapshot input, reject <2 / duplicate profile names) | MUST | `compare/errors.py` (§3), `compare/engine.py` `_validate` (§3) | covered-by-design | Count check before duplicate-name check, per design ordering rationale. |
| REQ-comparison-engine-002 (union-of-objects baseline, order-independent) | MUST | `compare/engine.py` `_build_presence_index` (§4, Pass 1) | covered-by-design | Plain `set`/`dict`, never a materialized/designated reference snapshot. |
| REQ-comparison-engine-003 (detect missing tables, no entry when present everywhere) | MUST | `compare/models.py` `MissingTable` (§2), `compare/engine.py` `_evaluate` (§4, Pass 2) | covered-by-design | Empty `missing_from` list naturally yields no entries — no special-case branch. |
| REQ-comparison-engine-004 (deterministic ordering independent of input order) | MUST | `compare/engine.py` `_evaluate`/`compare_snapshots` (§4, §5) | covered-by-design | `sorted(union)` + `sorted(profile_names)` + `sorted(missing_from)`; no sort over raw input `snapshots` order. |
| REQ-comparison-engine-005 (identical snapshots → empty diff, not an error) | MUST | `compare/engine.py` `_evaluate` (§4) | covered-by-design | Falls out of the same no-special-case Pass 2 logic as REQ-003. |

### Reconciliation Verdict
- MUST coverage: complete
- SHOULD/MAY gaps: none (spec defines no SHOULD/MAY requirements)
- Ambiguities to track: none

## Review Workload Forecast

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Medium

| Field | Value |
|-------|-------|
| Estimated changed lines | ~480-560 (source ~150: models ~40, errors ~40, engine ~50, `__init__.py` ~20; tests ~330-410 across fixtures + 3 test modules covering the 11-scenario matrix) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR (size:exception) — `delivery_strategy: exception-ok` already recorded in `state.yaml`; reference work units below for reviewer navigation |
| Delivery strategy | exception-ok |
| Chain strategy | size-exception |

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Data model (Phase 1) | PR 1 (single, size:exception) | `ComparisonResult` / `MissingTable`, no behavior yet. |
| 2 | Precondition validation errors (Phase 2) | PR 1 (single, size:exception) | Depends on Unit 1 only for import wiring; independently testable. |
| 3 | Engine algorithm + public API (Phase 3) | PR 1 (single, size:exception) | Depends on Units 1-2; composes union + evaluate + validate. |
| 4 | Unit tests (Phase 4) | PR 1 (single, size:exception) | Depends on Units 1-3; delivered together under the accepted size exception. |

### Checklist Status Legend

- `[ ]` Not implemented yet
- `[~]` Implemented but not yet verified locally
- `[x]` Implemented and verified locally

## Phase 1: Data Model

- [x] 1.1 Create `src/schema_comparator/compare/models.py` with the frozen `slots` dataclass `MissingTable` (`schema_name`, `table_name`, `missing_from_profile`, plus a `qualified_name` property returning `(schema_name, table_name)`), the `DiffEntry = MissingTable` type alias, and the frozen `slots` dataclass `ComparisonResult` (`compared_profiles: tuple[str, ...]`, `entries: tuple[DiffEntry, ...]`), per design §2.

## Phase 2: Errors — Precondition Validation

- [x] 2.1 Create `src/schema_comparator/compare/errors.py` with the `ComparisonError` base exception, `InsufficientSnapshotsError.for_count(count)` and `DuplicateProfileNameError.for_names(names)` classmethods producing clear, profile-detail-free domain error messages (no raw stack traces), per design §3.
- [x] 2.2 Add `_validate(snapshots)` to `src/schema_comparator/compare/engine.py`: raise `InsufficientSnapshotsError` when `len(snapshots) < 2` (checked first), else raise `DuplicateProfileNameError` when any `profile_name` repeats among inputs, per design §3.

## Phase 3: Engine Algorithm

- [x] 3.1 Add `_build_presence_index(snapshots)` to `src/schema_comparator/compare/engine.py`: Pass 1 — derive the `set` union of every `(schema_name, table_name)` qualified identity across all snapshots and a per-`profile_name` presence `set`, per design §4.
- [x] 3.2 Add `_evaluate(union, presence, profile_names)` to `engine.py`: Pass 2 — iterate `sorted(union)`, compute `sorted(missing_from)` profiles per identity, and emit one `MissingTable` per missing profile in that order, per design §4-§5.
- [x] 3.3 Add `compare_snapshots(snapshots)` to `engine.py`: compose `_validate` → `profile_names = tuple(sorted(...))` → `_build_presence_index` → `_evaluate` → return `ComparisonResult(compared_profiles=profile_names, entries=entries)`, per design §4.
- [x] 3.4 Create `src/schema_comparator/compare/__init__.py` re-exporting `ComparisonResult`, `MissingTable`, `compare_snapshots`, `ComparisonError`, `InsufficientSnapshotsError`, `DuplicateProfileNameError` with an explicit `__all__`, per design §1 Public API block (replaces the existing docstring-only placeholder).

## Phase 4: Unit Tests (Database-Free)

- [x] 4.1 Create `tests/unit/compare/__init__.py` and a `make_snapshot(profile_name, *tables)` fixture helper (in `tests/unit/compare/conftest.py` or a shared test module) building minimal `SchemaSnapshot`/`TableSnapshot` values with empty columns, per design §6.
- [x] 4.2 Create `tests/unit/compare/test_models.py` covering `MissingTable.qualified_name` identity and dataclass immutability (`frozen=True`) for both `MissingTable` and `ComparisonResult`.
- [x] 4.3 Create `tests/unit/compare/test_errors.py` covering "Fewer than 2 snapshots is rejected" (`InsufficientSnapshotsError`, no result returned) and "Duplicate profile names is rejected" (`DuplicateProfileNameError`, no result returned), asserting count-check-before-duplicate-check ordering.
- [x] 4.4 Create `tests/unit/compare/test_engine.py` covering the remaining spec scenarios: valid multi-profile input accepted (`compared_profiles == ("a", "b", "c")`); union includes tables from every snapshot; union/result ordering independent of input snapshot order (same set, two input orders → identical `entries`); table missing from one of three profiles; table missing from multiple profiles (one entry per missing profile, profile-name ascending); table present everywhere produces no entry; entries ordered by ascending qualified table identity (`alpha.Customer` before `zeta.Report`); identical snapshots produce an empty diff (`entries == ()`, both profiles named).

## Phase 5: Verification

- [x] 5.1 Run `pytest tests/unit/compare` and confirm every scenario in the design §6 coverage matrix has a passing test, with no DB/network access attempted.
