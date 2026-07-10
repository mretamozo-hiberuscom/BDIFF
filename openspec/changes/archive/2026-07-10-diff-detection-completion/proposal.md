# Proposal: Diff Detection Completion (missing-column + mismatch detection)

## Intent

Extend the existing `comparison-engine` (`src/schema_comparator/compare/`)
with the two detection categories it deliberately deferred: missing-column
detection and column type/size/precision/scale/nullability mismatch
detection. This is Change A of a two-change split; Change B (HTML/PDF/console
report generation) is a separate, later change and is explicitly out of
scope here. Change A turns `ComparisonResult.entries` into a data-complete
diff — every table- and column-level finding the tool is meant to detect —
without adding any rendering or presentation concern.

## Scope

### In Scope

- Two new frozen-dataclass diff-entry variants, siblings of `MissingTable`,
  in `src/schema_comparator/compare/models.py`: `MissingColumn` and
  `ColumnMismatch`. Widen the `DiffEntry` alias to
  `MissingTable | MissingColumn | ColumnMismatch`.
- A small `ColumnAttributes` value type carrying the comparable subset of
  `ColumnSnapshot` (`data_type`, `character_maximum_length`,
  `numeric_precision`, `numeric_scale`, `is_nullable`) — explicitly excluding
  `ordinal_position` (reorder alone is not drift) and `name` (identity, not
  an attribute).
- Extension of `src/schema_comparator/compare/engine.py`'s evaluation pass:
  for every qualified table identity present in 2+ of the compared profiles
  (i.e. every "matched" table, as already scoped by the existing
  missing-table detection), build the union of column names across the
  profiles that have that table and, in one unified per-table pass:
  - emit one `MissingColumn` entry per profile lacking a given column name
    (mirroring `MissingTable`'s one-entry-per-missing-profile shape), and
  - among profiles that do have the column, emit one `ColumnMismatch` entry
    naming every present profile's `ColumnAttributes` when they are not all
    identical.
- A concrete, documented cross-type deterministic tie-break order for
  entries sharing the same qualified table identity: `MissingTable` <
  `MissingColumn` < `ColumnMismatch`, then column name ascending within each
  type — extending REQ-comparison-engine-004's existing ordering guarantee
  rather than leaving it implicit.
- `values_by_profile` on `ColumnMismatch` sorted by profile name, consistent
  with the rest of the engine's order-independence guarantee.
- Explicit spec scenarios for the edge cases identified in exploration:
  column present in a subset (not 1, not N) of compared profiles; type
  variance across 3+ distinct values named individually; nullable-only
  mismatch (identical type/size/precision/scale, differing `is_nullable`);
  a table missing entirely from a profile MUST NOT additionally produce
  `MissingColumn` entries for that profile; ordinal-position-only
  differences MUST NOT be flagged as mismatch; `None`-vs-concrete-value in
  `character_maximum_length`/`numeric_precision`/`numeric_scale` is a
  genuine mismatch, not coerced to equal.
- New unit tests under `tests/unit/compare/`, including a column-fixture
  builder addition to the existing `make_snapshot`-style helpers.
- Updates to `openspec/specs/comparison-engine/spec.md`: new Requirement
  blocks for missing-column and mismatch detection, and removal/narrowing
  of the two Non-Goals bullets this change fills in.

### Out of Scope

- HTML report generation, PDF export, and console/TUI output
  (`src/schema_comparator/report/`, `src/schema_comparator/tui/`) — these
  consume `ComparisonResult.entries` unchanged and are Change B, planned
  next.
- Likely-rename heuristics (Milestone 2).
- Any change to `discovery/` snapshot models or extraction behavior — this
  change only reads `ColumnSnapshot`/`TableSnapshot.columns` as an
  already-sorted, immutable input.
- New precondition/error categories in `errors.py` — no design discussion to
  date has identified a column-level failure mode analogous to
  `InsufficientSnapshotsError`/`DuplicateProfileNameError`; every
  column-level finding is a diff entry, not a validation failure. If spec
  writing surfaces a genuine new precondition, it is added there, not
  assumed here.
- Persistence of comparison results.

## Capabilities

### New Capabilities

None. This change extends the existing `comparison-engine` capability; it
does not introduce a new named capability.

### Modified Capabilities

- `comparison-engine`: widened from missing-table-only detection to also
  include missing-column and column-attribute-mismatch detection, per the
  new Requirement blocks added to `openspec/specs/comparison-engine/spec.md`.
  `schema-extraction` is unaffected and continues to be consumed read-only.

## Approach

One unified per-table column pass, extending — not replacing — the existing
two-pass union-then-evaluate structure (per exploration Q2):

1. **Existing Pass 1/2 (unchanged)**: union of qualified table identities
   across all input profiles; `MissingTable` emitted for tables absent from
   some but not all profiles.
2. **New column pass, applied per matched table** (a table present in 2+ of
   the compared profiles — the same set already eligible for
   `MissingTable`'s "present somewhere" precondition):
   - Build the union of column names across the profiles that have this
     table.
   - For each column name, determine which of those profiles have it.
     - If fewer than all: emit one `MissingColumn` per profile lacking it.
     - Among profiles that do have it: compare `ColumnAttributes` tuples;
       if not all identical, emit one `ColumnMismatch` naming every present
       profile's attributes.
   - A single column can produce both a `MissingColumn` entry (for
     profiles lacking it) and a `ColumnMismatch` entry (for profiles that
     have it but disagree) — these are independent, non-exclusive findings.
   - A table absent entirely from a profile is out of scope for this pass
     for that profile (already covered by `MissingTable`); only profiles
     where the table itself is present are eligible for missing-column
     detection on that table.

This reuses the exact union+presence scaffolding `comparison-engine`
established for tables, one level deeper (columns within a matched table),
rather than introducing a second, structurally duplicate mechanism per
detection category — per exploration's recommendation against two separate
per-concern passes.

## Affected Areas

| Area | Impact | Description |
|------|--------|--------------|
| `src/schema_comparator/compare/models.py` | Extended | Add `ColumnAttributes`, `MissingColumn`, `ColumnMismatch`; widen `DiffEntry` alias. `ComparisonResult` shape unchanged. |
| `src/schema_comparator/compare/engine.py` | Extended | Add per-matched-table column union+presence pass; extend ordering to the documented cross-type tie-break. Existing table-level `_validate`/`_build_presence_index`/`_evaluate` logic unaffected. |
| `src/schema_comparator/compare/errors.py` | Unaffected | No new precondition category identified. |
| `tests/unit/compare/` | Extended | New test cases per new spec scenarios; new column-fixture builder helper. |
| `openspec/specs/comparison-engine/spec.md` | Extended (`sdd-spec` phase) | New Requirement blocks for missing-column and mismatch detection; narrow/remove the two corresponding Non-Goals bullets. |
| `src/schema_comparator/discovery/` | Read-only consumer | No changes; `ColumnSnapshot`/`TableSnapshot.columns` consumed as-is. |
| `src/schema_comparator/report/`, `src/schema_comparator/tui/` | Out of scope | Unchanged in this change; consume `ComparisonResult.entries` in Change B. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `ColumnMismatch` entry-count semantics ambiguous (one entry per column vs. one per differing profile pair) | Med | Proposal and spec fix "one entry per column with 2+ distinct attribute tuples among present profiles, naming every present profile" as the single supported semantics; resolved explicitly during spec writing, not left implicit. |
| Cross-type ordering (`MissingTable` vs `MissingColumn` vs `ColumnMismatch` for the same table) left ambiguous, breaking REQ-comparison-engine-004's determinism guarantee | Med | Explicit tie-break order pinned in this proposal (`MissingTable` < `MissingColumn` < `ColumnMismatch`, then column name ascending) and codified as a spec requirement, not left to implementation discretion. |
| Naive full-`ColumnSnapshot` equality accidentally includes `ordinal_position`, producing false-positive mismatches on harmless column reorders | Med | `ColumnAttributes` explicitly excludes `ordinal_position` and `name` by construction; dedicated spec scenario and unit test assert reorder-only columns produce no `ColumnMismatch`. |
| Double-reporting: a table missing entirely from a profile also produces `MissingColumn` entries for every one of its columns in that profile | Low | Column-level pass scoped only to profiles where the table itself is present (mirrors `MissingTable`'s existing "matched table" concept); explicit spec scenario and unit test cover the exclusion. |
| Scope creep into Change B (report/console rendering of the new diff types) | Low | Proposal and spec state HTML/PDF/console output is out of scope; this change's Success Criteria are all data-shape/detection assertions on `ComparisonResult`, none render output. |
| Nullable-only mismatches silently dropped by an implementation that only diffs `data_type`/size fields | Low | `ColumnAttributes` includes `is_nullable` as a first-class comparable field; explicit spec scenario and unit test for nullable-only mismatch. |

## Rollback Plan

Additive-only change: new frozen-dataclass variants and a widened type alias
in `compare/models.py`, an extended (not rewritten) evaluation pass in
`compare/engine.py`, new spec Requirement blocks, and new unit tests. No
existing `MissingTable` detection behavior, field, or ordering changes for
tables that have no column-level findings — pre-existing table-only
comparisons continue to produce identical results. No new third-party
dependency, database, or persisted state is introduced. Revert via
`git revert` of the change's commit(s); no data migration or external state
cleanup is required. If a partial rollback is needed instead (e.g. keep
`MissingColumn` but drop `ColumnMismatch`), the two new entry types are
independent siblings in the `DiffEntry` union with no cross-dependency,
so either can be reverted without affecting the other or `MissingTable`.

## Dependencies

- `src/schema_comparator/compare/models.py` and `engine.py` (this change's
  own prior state, from the archived `comparison-engine` change) as the base
  being extended.
- `src/schema_comparator/discovery/models.py` (`ColumnSnapshot`,
  `TableSnapshot.columns`) as the sole new input surface (already fully
  available; no discovery change required).
- No new third-party dependencies.

## Success Criteria

- [ ] A column present in some but not all profiles of a matched table
      produces one `MissingColumn` entry per profile lacking it.
- [ ] A column present under the same name in 2+ profiles with identical
      `data_type`/size/precision/scale/nullability produces no diff entry.
- [ ] A column whose `data_type`, size, precision, scale, or `is_nullable`
      differs across 2+ profiles that have it produces exactly one
      `ColumnMismatch` entry naming every present profile's attributes.
- [ ] Type variance across 3+ distinct values in 3+ profiles is named
      individually per profile in a single `ColumnMismatch` entry, not
      fragmented into per-pair entries.
- [ ] A column differing only in `is_nullable` (all other attributes equal)
      produces a `ColumnMismatch`.
- [ ] A column differing only in `ordinal_position` (all comparable
      attributes equal) produces no diff entry.
- [ ] A table missing entirely from a profile produces no `MissingColumn`
      entries for that profile (only the existing `MissingTable` entry).
- [ ] Result ordering for entries sharing a qualified table identity follows
      `MissingTable` < `MissingColumn` < `ColumnMismatch`, then column name
      ascending, independent of input snapshot order.
- [ ] `ColumnMismatch.values_by_profile` is sorted by profile name.
- [ ] Unit tests cover all of the above without DB/network access, using
      hand-built `SchemaSnapshot`/`TableSnapshot`/`ColumnSnapshot` fixtures.
- [ ] No HTML/PDF/console rendering code is added; `report/` and `tui/`
      remain unchanged.

**Branch advisory:** Before `sdd-apply` begins, a feature branch SHOULD be
created following the `<tipo>/<descripción>` convention defined in the
`branch-pr` skill (e.g. `git checkout -b feat/diff-detection-completion
main`). This note is SHOULD, not MUST.
