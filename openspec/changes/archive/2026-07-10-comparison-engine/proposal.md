# Proposal: Comparison Engine

## Intent

Implement the N-way, union-of-objects schema comparison engine as a pure,
side-effect-free stage of the CLI pipeline (`config -> connectors ->
discovery -> compare -> report`), and prove the union mechanism end-to-end
with one fully working detection category: missing-table detection. This
turns the discovery stage's per-profile `SchemaSnapshot` values into a single
deterministic, order-independent `ComparisonResult` that later changes
(missing-column detection, mismatch detection, report generation) can build
on without re-deriving the union logic.

## Scope

### In Scope

- A union-of-objects baseline: the set of every qualified table identity
  (`schema_name`, `table_name`) observed across all N input snapshots,
  computed independently of input snapshot order.
- An entry-point function accepting `Sequence[SchemaSnapshot]` (N ≥ 2,
  distinct `profile_name`s) and returning a `ComparisonResult`.
- Missing-table detection: for every table in the union baseline, identify
  which of the N input profiles do not have that table, and emit one diff
  entry per missing occurrence.
- A flat, immutable, ordered diff-entry result model (`ComparisonResult` +
  a `MissingTable` entry type) designed for later extension by
  missing-column and mismatch entry types, without a required reshape.
- Deterministic output ordering (by qualified table identity, then a stable
  diff-type ordering) independent of input snapshot order.
- Explicit precondition validation: reject fewer than 2 snapshots and reject
  duplicate `profile_name`s among inputs, with clear domain errors (no raw
  stack traces).
- Pure in-memory unit tests using hand-built `SchemaSnapshot` fixtures; no
  DB/network dependency.

### Out of Scope

- Missing-column detection (its own future roadmap/SDD change).
- Type/size/nullability mismatch detection (its own future roadmap/SDD
  change).
- Likely-rename heuristics (Milestone 2).
- Report generation/rendering (`src/schema_comparator/report/`), console/TUI
  output, and any grouping/presentation of findings.
- Any change to `discovery/` snapshot models or extraction behavior — this
  change only consumes `SchemaSnapshot` as a read-only input.
- Persistence of comparison results.

## Capabilities

### New Capabilities

- `comparison-engine`: Given 2+ named schema snapshots, compute the
  union-of-objects baseline and produce a deterministic, order-independent
  comparison result that includes missing-table findings.

### Modified Capabilities

None. `schema-extraction` continues to provide `SchemaSnapshot` values
unchanged; this capability only consumes them.

## Approach

Two-pass union-then-evaluate, per the exploration's Approach 1
recommendation:

1. **Union pass**: derive the set of distinct qualified table identities
   across all N input snapshots. This is the baseline — not a materialized
   snapshot, but a derived index used only to know what should be checked
   for presence in each profile.
2. **Evaluation pass**: iterate the union in deterministic sort order; for
   each table, determine which of the N profiles lack it and emit a
   `MissingTable` diff entry per missing profile occurrence.

Add `src/schema_comparator/compare/models.py` with frozen dataclasses for
`ComparisonResult` (compared profile names + ordered tuple of diff entries)
and the `MissingTable` diff-entry variant, mirroring the existing frozen-
dataclass style of `discovery/models.py`. Add
`src/schema_comparator/compare/engine.py` (or similarly named module) with a
single entry-point function taking `Sequence[SchemaSnapshot]`, validating
preconditions (≥2 snapshots, distinct profile names), and returning a
`ComparisonResult`. The compare stage remains pure/synchronous with no I/O,
fully unit-testable with hand-built fixtures — consistent with
schema-extraction's existing test-boundary discipline.

Missing-column and mismatch entry types are not implemented in this change;
the result model is shaped so they can be added later as new entry-type
variants in the same flat, appendable sequence without breaking existing
consumers.

## Affected Areas

| Area | Impact | Description |
|------|--------|--------------|
| `src/schema_comparator/compare/` | New (fills existing docstring-only package) | Diff-entry/result models, union computation, entry-point function. |
| `src/schema_comparator/discovery/models.py` | Read-only consumer | No changes; `SchemaSnapshot` consumed as-is. |
| `tests/unit/compare/` | New | Pure in-memory unit tests: union correctness, missing-table detection, order-independence, precondition errors. |
| `openspec/specs/comparison-engine/spec.md` | Future (`sdd-spec` phase) | Not authored in this phase. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Scope creep into missing-column/mismatch detection, since functional-scope.md lists them adjacently | Med | Proposal and spec explicitly state missing-table detection is the only fully implemented detection category in this change; other categories are out of scope. |
| Same-named profile inputs make finding attribution ambiguous | Low | Reject duplicate `profile_name`s as a precondition violation with a clear domain error. |
| Non-deterministic output ordering across runs/input order, undermining testability | Med | Union and result ordering keyed by qualified table identity and stable diff-type order, independent of input snapshot order; covered by dedicated order-independence unit tests. |
| Degenerate inputs (fewer than 2 snapshots, or all snapshots identical) left undefined | Low | Explicit precondition validation for <2 snapshots; identical-snapshots case defined to produce an empty diff-entry sequence. |
| Result-model shape doesn't fit future missing-column/mismatch/report needs, causing rework | Low | Flat, appendable diff-entry model chosen specifically for incremental extension; re-reviewed at each subsequent change's own exploration phase rather than over-designed now. |

## Rollback Plan

Purely additive: a new `compare/models.py` and `compare/engine.py` (replacing
only the existing docstring-only placeholder), plus new unit tests under
`tests/unit/compare/`. No other module currently imports `compare/`, no
database or persisted state is touched, and no existing behavior changes.
Revert via `git revert` of the change's commit(s); no data migration or
external state cleanup is required.

## Dependencies

- `src/schema_comparator/discovery/models.py` (`SchemaSnapshot`,
  `TableSnapshot`, `ColumnSnapshot`) as the sole input type.
- No new third-party dependencies.

## Success Criteria

- [ ] Given 2+ `SchemaSnapshot` values with distinct profile names, the
      engine returns a `ComparisonResult` naming every compared profile.
- [ ] A table present in some but not all input snapshots produces one
      `MissingTable` diff entry per snapshot missing it.
- [ ] A table present in every input snapshot produces no diff entry for
      that table.
- [ ] Comparison result ordering is identical regardless of the order
      snapshots are passed to the engine.
- [ ] Fewer than 2 snapshots, or duplicate `profile_name`s among inputs,
      raise a clear domain error rather than proceeding or crashing
      unexpectedly.
- [ ] Unit tests cover union correctness, missing-table detection,
      order-independence, and precondition errors without DB/network access.

**Branch advisory:** Before `sdd-apply` begins, a feature branch SHOULD be created following the `<tipo>/<descripción>` convention defined in the `branch-pr` skill (e.g. `git checkout -b feat/comparison-engine main`). This note is SHOULD, not MUST.
