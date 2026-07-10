# Exploration: Diff Detection Completion (missing-column + mismatch detection)

## Current State

`comparison-engine` (archived) ships a working two-pass, union-of-identities
engine in `src/schema_comparator/compare/`:

- [engine.py](../../../src/schema_comparator/compare/engine.py) —
  `_validate` (precondition checks), `_build_presence_index` (Pass 1: union +
  per-profile presence set over `(schema_name, table_name)`),
  `_evaluate` (Pass 2: emits `MissingTable` per missing occurrence),
  `compare_snapshots` (orchestration entry point).
- [models.py](../../../src/schema_comparator/compare/models.py) —
  `MissingTable` (frozen dataclass: `schema_name`, `table_name`,
  `missing_from_profile`), a `DiffEntry` type alias currently aliased to
  `MissingTable` alone (explicitly documented as a future widening point —
  `DiffEntry = MissingTable | MissingColumn | ...`), and `ComparisonResult`
  (`compared_profiles: tuple[str, ...]`, `entries: tuple[DiffEntry, ...]`).
- [errors.py](../../../src/schema_comparator/compare/errors.py) —
  `ComparisonError` base, `InsufficientSnapshotsError`,
  `DuplicateProfileNameError`.

The archived [design.md](../archive/2026-07-10-comparison-engine/design.md)
and [spec.md](../../specs/comparison-engine/spec.md) explicitly reserve this
change's scope as Non-Goals: missing-column detection and
type/size/precision/scale/nullability mismatch detection. The spec's own
Clarifications section records the deliberate decision that `MissingTable`
carries *only* qualified table identity + missing profile, never column
metadata — column-level data belongs exclusively to the diff-entry types this
change introduces.

Column metadata is already fully available and immutable per profile via
`ColumnSnapshot` in
[discovery/models.py](../../../src/schema_comparator/discovery/models.py):
`name`, `data_type`, `character_maximum_length`, `numeric_precision`,
`numeric_scale`, `is_nullable`, `ordinal_position`. `TableSnapshot.columns` is
already sorted (ordinal position, then name) — this change only ever reads
that tuple, never re-derives or re-sorts it, mirroring the discipline
`comparison-engine` already applied to `TableSnapshot`/`SchemaSnapshot`
themselves.

`docs/roadmap.md` splits Milestone 1's remaining comparison work into exactly
the two categories this change covers (missing-column, mismatch); everything
else (report rendering in HTML/PDF/console) is Change B and explicitly out of
scope here per the task framing.

## Affected Areas

- `src/schema_comparator/compare/models.py` — add new frozen-dataclass
  diff-entry variant(s) (`MissingColumn`, `ColumnMismatch` or similar) and
  widen the `DiffEntry` alias. `ComparisonResult` itself needs no reshape —
  its `entries: tuple[DiffEntry, ...]` field already anticipated this.
- `src/schema_comparator/compare/engine.py` — extend the evaluation pass(es)
  to iterate columns of matched tables (tables present in the union AND
  present in ≥2 profiles being compared for that table) and detect
  missing-column and mismatch conditions. Precondition validation
  (`_validate`) is unaffected; the union/presence infrastructure for tables
  is unaffected and reused as the entry point to per-table column iteration.
- `src/schema_comparator/compare/errors.py` — likely unaffected; no new
  precondition category is evident (column-level detection has no analogous
  "reject the whole comparison" failure mode — every column-level finding is
  a diff entry, not an error).
- `tests/unit/compare/` — new test cases per new spec scenarios, following
  the existing `make_snapshot`-style fixture-builder pattern, now needing a
  column-fixture builder (`make_table(schema, name, *columns)` or similar)
  since column contents now matter to comparison for the first time.
- `openspec/specs/comparison-engine/spec.md` — the future `sdd-spec` phase
  adds new Requirement blocks (missing-column, mismatch categories) to this
  existing spec file; the two current Non-Goals bullets for these categories
  must be removed/narrowed since this change fills them in.
- No changes anticipated to `discovery/` (read-only consumer, as before) or
  to `report/`/`tui/` (Change B's concern).

## Key Design Questions

### 1. How should missing-column and mismatch detection extend the existing model?

The existing `DiffEntry` alias and flat, ordered `ComparisonResult.entries`
sequence were explicitly designed in `comparison-engine` for this widening.
Two new frozen dataclasses, siblings of `MissingTable`, fit the established
shape:

```python
@dataclass(frozen=True, slots=True)
class MissingColumn:
    """A column present in the union of a matched table's columns across
    compared profiles, but absent from one profile — for a table that
    itself exists in that profile (a table missing entirely is
    MissingTable's concern, not this type's)."""

    schema_name: str
    table_name: str
    column_name: str
    missing_from_profile: str

    @property
    def qualified_name(self) -> tuple[str, str]:
        return (self.schema_name, self.table_name)


@dataclass(frozen=True, slots=True)
class ColumnMismatch:
    """A column present under the same name in 2+ profiles (for a table
    present in those same profiles) whose type/size/precision/scale/
    nullable attributes differ across at least one pair of those profiles.

    `values_by_profile` carries the *comparable attribute tuple* observed
    in each profile that has the column, keyed by profile name — not the
    full ColumnSnapshot (ordinal_position is irrelevant to "mismatch" and
    must not leak in as false drift)."""

    schema_name: str
    table_name: str
    column_name: str
    values_by_profile: tuple[tuple[str, ColumnAttributes], ...]

    @property
    def qualified_name(self) -> tuple[str, str]:
        return (self.schema_name, self.table_name)
```

`ColumnAttributes` would be a small frozen dataclass/NamedTuple carrying
exactly `data_type`, `character_maximum_length`, `numeric_precision`,
`numeric_scale`, `is_nullable` — the subset of `ColumnSnapshot` that defines
"same or different", explicitly excluding `ordinal_position` (column reorder
alone is not drift per the glossary's definition of mismatch) and `name`
(identity, not an attribute being compared).

`values_by_profile` is deliberately **all** profiles that have the column
(not just the "odd one out"), so a report can render "type varies: A=int,
B=int, C=bigint" without re-deriving majority/minority — consistent with
`MissingTable`'s existing pattern of naming every affected profile
individually rather than picking one as "the" reference.

`DiffEntry` widens to:

```python
DiffEntry = MissingTable | MissingColumn | ColumnMismatch
```

No reshape of `ComparisonResult` — exactly the extensibility the archived
design already committed to.

### 2. One unified pass over columns, or two separate passes?

**Recommendation: one unified pass, per matched table.**

For each qualified table identity that exists in 2+ of the compared profiles
(i.e. every table except those already fully absent from all-but-one
profile, which `MissingTable` already covers at the table level):

1. Build the union of column names across the profiles that have this table.
2. For each column name in that union, in one iteration:
   - Determine which of those profiles have the column at all. If fewer
     than all of them do → emit `MissingColumn` for each profile lacking it
     (mirrors `MissingTable`'s exact evaluate-pass shape at the column
     level).
   - Among the profiles that **do** have the column, compare the
     `ColumnAttributes` tuple. If not all identical → emit one
     `ColumnMismatch` entry naming every profile's observed attributes.
   - A column can produce **both** a `MissingColumn` entry (for the profiles
     lacking it) **and** a `ColumnMismatch` entry (for the profiles that
     have it but disagree) in the same pass — these are independent,
     non-exclusive findings for the same column identity.

Rationale for unifying rather than two separate table-then-column passes:

- Both detections need the exact same per-table "union of column names +
  per-profile presence" scaffolding — this is structurally identical to
  `comparison-engine`'s own `_build_presence_index`/`_evaluate` shape, just
  one level deeper (columns within a matched table, instead of tables within
  the whole comparison). Building it twice (once per detection category)
  would duplicate the union-and-presence mechanism for no benefit — the same
  argument the archived exploration already made for why the table-level
  engine shouldn't be split into 3 separate engines for missing-table,
  missing-column, and mismatch: build the per-table column union+presence
  index once, then only branch between "emit MissingColumn" vs "emit
  ColumnMismatch" per column, depending on presence-count outcome.
- A two-pass-per-concern design (fully iterate all matched tables' columns
  once for missing-columns, then again for mismatches) would need to
  recompute "which profiles have this column" twice per column with no
  differing input — pure duplication, not a genuine separation of concerns.

This keeps the same two-level structure `comparison-engine` established:
Pass 1 = union + presence (now applied per-table, over columns, in addition
to the existing whole-comparison union over tables), Pass 2 = evaluate (now
column-aware, emitting up to 2 entry types per column instead of 1 per
table).

### 3. Edge cases to resolve during spec writing

- **Column present in a subset (not 1, not N) of the compared profiles.**
  E.g. comparing 4 profiles, column exists in 3 of them. `MissingColumn`
  must be emitted once per lacking profile (exactly `MissingTable`'s existing
  precedent for "missing from multiple profiles" — one entry per missing
  profile, not one combined entry). Needs an explicit spec scenario since
  the archived spec's analogous scenario was only tested at N=3.
- **Type variance across more than 2 distinct values.** E.g. `int` in A,
  `bigint` in B, `smallint` in C. `ColumnMismatch.values_by_profile` must
  name all 3 values, not just flag "differs" — the recommended model already
  supports this by construction (it's a tuple over all present profiles, not
  a boolean or a 2-value pair), but the spec must state explicitly that
  *any* pairwise difference among present profiles triggers one mismatch
  entry for that column, not one entry per differing pair.
- **Nullable-only difference (same type/size/precision/scale, differing
  `is_nullable`).** Per the glossary's own mismatch definition
  ("...or nullability"), this MUST still count as a mismatch even though
  storage-shape is otherwise identical — this must be an explicit spec
  scenario so it isn't silently dropped by an implementation that only
  diffs `data_type`/size, without also checking `is_nullable`.
- **Column missing from a table that is itself entirely missing from a
  profile.** A table absent from profile C already produces `MissingTable`
  entries (one per missing profile) from the existing engine. Its columns
  MUST NOT additionally produce `MissingColumn` entries for that same
  profile — column-level detection only applies to tables present in the
  profile being evaluated, to avoid a redundant/misleading double report
  ("table missing" + "every column of it missing" for the same profile).
  This needs to be a stated non-goal/exclusion in the spec, and the
  design's "matched table" scope in Q2 above already encodes it (only
  tables present in 2+ profiles are eligible for column-level passes at
  all; a table present in exactly 1 profile has no "matched" peer to diff
  columns against).
- **Column ordinal position differing across profiles.** Per `ColumnSnapshot`
  docs, `ordinal_position` is preserved verbatim from the catalog; this
  change's `ColumnAttributes` comparison subset deliberately excludes it, so
  a column that's simply declared in a different order but otherwise
  identical MUST NOT be flagged as a mismatch. This should be an explicit
  spec scenario, not just an implementation detail, since it's easy to
  accidentally include ordinal in a naive full-`ColumnSnapshot` equality
  check.
- **Character-length/precision/scale being `None` on one profile and a
  concrete value on another for the same `data_type`.** E.g. `varchar`
  with `character_maximum_length=50` in A vs `character_maximum_length=None`
  (unusual, but catalog-dependent) in B — this is a genuine mismatch by the
  existing tuple-equality comparison and needs no special-casing, but is
  worth one explicit scenario to document the None-vs-value case isn't
  silently coerced to "equal".

### 4. Risks / open questions to resolve during spec writing

- **Naming**: whether the entry-count semantics for `ColumnMismatch` should
  be "one entry per column with 2+ distinct attribute tuples among present
  profiles" (recommended, matches `MissingTable`'s "one finding, N profiles
  named" style) vs. "one entry per differing profile pair" (would fragment
  a single 3-way type variance into 3 pairwise entries, complicating both
  the model and later report grouping) — the exploration recommends the
  former, but this is a genuine open decision for spec/clarify since the
  glossary doesn't disambiguate it.
- **Deterministic ordering** must extend `comparison-engine`'s existing
  scheme (REQ-comparison-engine-004): the archived design already flagged
  "when a second diff-entry type is added... `_evaluate` gains an explicit
  type-rank tuple" as a forward-compatibility note. This change introduces
  *two* new types at once, so the spec must pin down a concrete
  cross-type tie-break order (e.g. `MissingTable` < `MissingColumn` <
  `ColumnMismatch` for entries sharing the same qualified table identity,
  then column name ascending within each type) rather than leaving it
  implicit.
- **Should a `ColumnMismatch`'s `values_by_profile` be sorted by profile
  name** (consistent with `MissingTable.missing_from_profile` sorting and
  `compared_profiles` ordering) — recommended yes, for the same
  order-independence-from-input guarantee already normative for the rest of
  the engine.
- **No new precondition/error category identified.** Column-level detection
  has no analogous "reject the whole comparison" failure the way
  `InsufficientSnapshotsError`/`DuplicateProfileNameError` do — every
  column-level finding is a diff entry, not a validation failure. This
  should be confirmed (not assumed) during spec writing; if a design
  discussion surfaces a genuine new precondition, it would need its own
  error type in `errors.py`.
- **Scope boundary with Change B** must stay explicit in the proposal/spec:
  this change produces diff-entry data only; it MUST NOT add any
  rendering, grouping-by-table-for-display, or console/HTML/PDF output —
  those consume `ComparisonResult.entries` unchanged, in Change B.
