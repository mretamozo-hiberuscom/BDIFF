# Exploration: Comparison Engine (N-way union-of-objects baseline diff)

## Current State

`schema-extraction` (archived) provides `SchemaSnapshot` → `TableSnapshot` →
`ColumnSnapshot` (all frozen dataclasses in
[src/schema_comparator/discovery/models.py](../../../src/schema_comparator/discovery/models.py)),
one snapshot per profile, tables keyed by `(schema_name, table_name)` and
already sorted deterministically; columns keyed by name and already sorted by
ordinal position. `src/schema_comparator/compare/__init__.py` currently only
holds a module docstring ("N-way diff engine over schema snapshots
(union-of-objects baseline)") — no code exists. No comparison, diff-result, or
report model exists anywhere in the codebase yet.

The glossary (`docs/product/glossary.md`) already defines the key domain
terms this change must implement precisely:

- **Baseline database**: *not* a fixed/designated database — the baseline is
  the **union of all objects observed across all compared snapshots**; any
  snapshot missing an object relative to that union is flagged.
- **Missing table/column**: an object present in at least one snapshot but
  absent in another.
- **Mismatch**: a column present under the same name in ≥2 snapshots but
  differing in data type, size/precision/scale, or nullability.

`docs/roadmap.md` explicitly splits this Milestone 1 area into four
consecutive items: this engine, then missing-table detection, then
missing-column detection, then type/size/nullability mismatch detection. This
exploration treats the latter three as **out of scope** for `comparison-engine`
itself — they are the *content* that will eventually flow through the engine's
result model, but their own detection rules/specs are future changes.

## Affected Areas

- `src/schema_comparator/compare/` — new comparison engine module(s): input
  aggregation, union-of-objects baseline construction, diff result model,
  entry-point function(s).
- `src/schema_comparator/discovery/models.py` — read-only consumer; no changes
  expected (snapshots are already immutable and identity-stable).
- `tests/unit/compare/` (new) — pure in-memory unit tests using hand-built
  `SchemaSnapshot` fixtures; no DB/network dependency, consistent with the
  discovery test pattern in `tests/unit/discovery/`.
- `openspec/specs/comparison-engine/spec.md` (future `sdd-spec` phase output,
  not this phase).
- Later report generation (`src/schema_comparator/report/`) will consume this
  engine's result model — not implemented now, but the result shape must be
  designed for that consumption.

## Key Design Questions

### 1. What does "baseline" mean with N databases and no single source of truth?

Per the glossary, baseline = union of every table/column identity seen across
all input snapshots, not any one designated database. This has direct
consequences for the diff model:

- A table/column is "missing" **relative to the union**, not relative to one
  chosen reference snapshot. E.g., with 3 snapshots A, B, C where a table
  exists in A and B but not C, C is missing it — regardless of extraction
  order or which snapshot was passed first.
- The union must be computed independently of input order, and the engine's
  output must not depend on which snapshot appears first in the input list
  (order-independence is testable and should be a normative property, mirroring
  the deterministic-ordering discipline already established in
  schema-extraction).
- "Baseline" is therefore not a stored/materialized snapshot — it can be
  implemented as a derived index (e.g. a dict/set of all distinct qualified
  table identities, and per-table all distinct column names) built once from
  the N inputs, used only to know what *should* be checked for presence in
  each snapshot.

### 2. How do missing-table / missing-column / mismatch detection interact with the engine, given they're separate future changes?

The engine's job in *this* change is the union-of-objects mechanism and the
result container — not the detection rule bodies themselves. Two viable
boundaries:

- **(a) Engine owns iteration + empty diff shape; detection changes fill in
  each diff category's rule.** The engine computes the union, iterates
  per-table and per-column across all N snapshots, and produces a result
  structure with (initially empty or minimal) fields for missing tables,
  missing columns, and mismatches. Each subsequent roadmap item
  (missing-table, missing-column, mismatch) adds/refines the specific
  detection logic and populates its corresponding field, without needing to
  touch the union/iteration scaffolding again.
- **(b) Engine only builds the union index and exposes it; each detection
  change owns its own iteration.** Three separate consumers would each
  redundantly re-derive "what exists everywhere" from the union.

(a) avoids duplicated N-way iteration logic and gives a single place where
"what exists across all snapshots" is computed once and reused for all three
detection concerns. It also matches the modular monolith's `compare` stage
being one pipeline stage, not three. Recommendation: (a).

Practically, this means `comparison-engine` should ship a real, working
end-to-end diff for at least one detection category (missing tables is the
simplest and most natural to include as a concrete correctness proof of the
union mechanism), while explicitly deferring column-level mismatch rule
richness and full missing-column semantics to their own changes. This must be
made explicit and narrow in the proposal so scope doesn't silently expand to
cover all three roadmap bullets at once.

### 3. How should the diff result model be represented for later report consumption?

Requirements from functional-scope.md capability #5 ("N-way schema
comparison... normalized 'union of all known objects' baseline") and the
future HTML/console report (grouped by table, color-coded by diff type):
Report generation will need to group findings **by table** and by **diff
type**, and needs to know **which profiles/databases** are the outliers for
each finding.

Design options considered:

1. **Flat list of typed diff entries** (e.g. a sequence of tagged records:
   `MissingTable`, `MissingColumn`, `ColumnMismatch`), each self-describing
   with qualified table identity, affected profile name(s), and (for
   mismatches) the differing attribute values per profile.
   - Pros: simple to produce incrementally per detection category; easy to
     filter/group later (by table, by type, by profile) without needing a
     pre-built tree; extensible — a new diff-entry type variant can be added
     per future roadmap item without breaking existing consumers.
   - Cons: report generation must group entries itself (acceptable — that's
     naturally the report stage's job).

2. **Table-centric nested tree**: one node per union table, containing
   per-column-per-profile presence/attribute maps, with derived
   missing/mismatch flags computed lazily by the report layer.
   - Pros: naturally grouped by table already, matching the report's display
     structure.
   - Cons: pushes "what counts as a mismatch" decision into the report layer
     or requires the tree to already encode it, which recouples concerns; the
     tree quickly becomes large/redundant for tables with no drift; less
     natural to build incrementally across three separate future roadmap
     changes without repeatedly reshaping the tree structure.

3. **Comparison matrix per table** (profile × column grid) exposed
   in full, with drift interpretation added on top.
   - Pros: precise low-level fidelity, could support advanced future views.
   - Cons: substantial complexity/memory for no near-term benefit; V1 report
     scope only needs the three drift categories, not a general-purpose grid.

Recommendation: **Option 1**, a flat, typed, immutable sequence of diff-entry
values (mirroring the existing frozen-dataclass style of `discovery/models.py`),
wrapped in one top-level `ComparisonResult` that also records the qualified
identities of every profile compared (so a report can render "compared: A, B,
C" even when a table/column is present everywhere and produces no findings).
This keeps grouping-by-table/type as a report-stage concern (append-only
filtering over the flat list), keeps the engine's contract stable while
missing-column and mismatch detection are added in later changes, and avoids
inventing report-shaped structure prematurely.
