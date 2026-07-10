# Spec Delta: Comparison Engine

Status: extends the existing baseline at
`openspec/specs/comparison-engine/spec.md` (capability `comparison-engine`).
This delta ADDS two new Requirements (missing-column detection, column
attribute-mismatch detection), MODIFIES the existing ordering requirement
(REQ-comparison-engine-004) to pin a concrete cross-type tie-break, and
NARROWS the baseline's Non-Goals section. It does not fork a new domain and
does not modify the baseline file directly; merging happens at archive time.

Scope reminder (per proposal.md): this change is Change A of a two-change
split. It produces diff-entry data only (`MissingColumn`, `ColumnMismatch`
siblings of the existing `MissingTable`). HTML/PDF/console rendering,
likely-rename heuristics, and any change to `discovery/` snapshot models
remain out of scope and are addressed by later changes.

## Clarifications

### Session 2026-07-10

- **Q: Does `ColumnMismatch` produce one entry per column (naming every
  present profile's attributes) or one entry per divergent profile pair?**
  A: **One entry per column.** A single `ColumnMismatch` entry names the
  `ColumnAttributes` of every profile that has the column, keyed by profile
  name, whenever at least one pairwise difference exists among them. This
  matches `MissingTable`'s existing "one finding, N profiles named" style
  and avoids fragmenting a single 3+-way type variance into multiple
  pairwise entries, which would complicate both the result model and any
  later report grouping. See REQ-comparison-engine-007.

- **Q: What is the deterministic type-rank ordering among diff-entry kinds
  sharing the same qualified table identity?**
  A: `MissingTable` < `MissingColumn` < `ColumnMismatch`, then column name
  ascending within `MissingColumn`/`ColumnMismatch`. This extends, rather
  than replaces, REQ-comparison-engine-004's existing table-identity-first
  ordering. See the MODIFIED REQ-comparison-engine-004 below.

- **Q: Can a table already reported as `MissingTable` for a given profile
  also produce `MissingColumn` entries for that same profile/table?**
  A: **No.** Column-level detection (`MissingColumn` and `ColumnMismatch`)
  is only evaluated for profiles in which the table itself is present.
  A profile missing the table entirely is fully covered by its existing
  `MissingTable` entry; it MUST NOT additionally receive `MissingColumn`
  entries for that table's columns. See REQ-comparison-engine-006.

- **Q: Is `ColumnMismatch.values_by_profile` (or equivalent) ordered
  deterministically?**
  A: **Yes.** It MUST be ordered ascending by profile name, consistent with
  the order-independence-from-input guarantee already normative for the
  rest of the engine (`compared_profiles`, table-identity ordering). See
  REQ-comparison-engine-007.

- **Q: Which column attributes participate in mismatch comparison, and is
  `ordinal_position` excluded?**
  A: The comparable attribute set (`ColumnAttributes`) is exactly
  `data_type`, `character_maximum_length`, `numeric_precision`,
  `numeric_scale`, and `is_nullable`. `ordinal_position` is explicitly
  excluded — a column simply declared in a different order, with all other
  attributes identical, is not drift. `name` is also excluded from the
  comparable set (it is the column's identity, not an attribute of it; two
  columns are compared under the same name by construction). See
  REQ-comparison-engine-007.
### Session 2026-07-10 (final clarify pass)

No material ambiguities found; reviewed on 2026-07-10. The five previously
flagged risks (`ColumnMismatch` entry-count semantics, cross-type ordering,
missing-table/missing-column double-reporting, `ordinal_position` exclusion,
`values_by_profile` ordering) are each pinned as explicit MUST requirements
with Given/When/Then scenarios in REQ-comparison-engine-004,
REQ-comparison-engine-006, and REQ-comparison-engine-007 above. Column-name
matching for union/presence purposes is not separately restated here because
it follows the same string-identity convention REQ-comparison-engine-002
already establishes for qualified table identity; this is a consistent
extension, not a new ambiguity, and is left to `sdd-design` to implement
using the same convention.
## MODIFIED Non-Goals

The baseline's Non-Goals section currently reads:

> This capability MUST NOT implement missing-column detection, column
> type/size/precision/scale/nullability mismatch detection, likely-rename
> heuristics, or report generation/rendering. These remain out of scope and
> are addressed by separate future changes; the result model MUST remain
> extensible for them without requiring a reshape.

It is narrowed to:

> This capability MUST NOT implement likely-rename heuristics or report
> generation/rendering (HTML, PDF, or console/TUI output). These remain out
> of scope and are addressed by separate future changes. Missing-column
> detection and column type/size/precision/scale/nullability mismatch
> detection are in scope as of REQ-comparison-engine-006 and
> REQ-comparison-engine-007; the result model MUST remain extensible for
> likely-rename heuristics and report generation without requiring a
> reshape.

## MODIFIED Requirements

### Requirement: Return Deterministically Ordered Results {#REQ-comparison-engine-004}

The system MUST order the diff-entry sequence in a `ComparisonResult` by
ascending qualified table identity (schema name, then table name), then by a
stable cross-type diff-kind ordering: `MissingTable` entries precede
`MissingColumn` entries, which precede `ColumnMismatch` entries, for entries
sharing the same qualified table identity. Within `MissingColumn` and
`ColumnMismatch` entries for the same table, entries MUST be further ordered
by ascending column name. This ordering SHALL be independent of the order in
which input snapshots were supplied, so equivalent input snapshot sets
produce an identical ordered result regardless of input order.

#### Scenario: Result ordering is stable across input snapshot order

- GIVEN the same set of snapshots supplied in two different input orders,
  producing the same missing-table, missing-column, and mismatch findings
- WHEN comparison is performed for each order
- THEN the resulting diff-entry sequences SHALL be identical, including
  entry order

#### Scenario: Entries are ordered by qualified table identity

- GIVEN missing-table findings for tables `zeta.Report` and `alpha.Customer`
- WHEN the result is produced
- THEN the entry for `alpha.Customer` SHALL precede the entry for
  `zeta.Report` in the result sequence

#### Scenario: Cross-type ordering for the same table follows MissingTable < MissingColumn < ColumnMismatch

- GIVEN table `sales.Invoice` produces a `MissingTable` entry (missing from
  profile `c`), a `MissingColumn` entry for column `notes` (missing from
  profile `b`), and a `ColumnMismatch` entry for column `amount` (differing
  `data_type` between profiles `a` and `b`)
- WHEN the result is produced
- THEN, among the entries for `sales.Invoice`, the `MissingTable` entry
  SHALL precede the `MissingColumn` entry, which SHALL precede the
  `ColumnMismatch` entry

#### Scenario: Same-type entries for the same table are ordered by column name

- GIVEN table `sales.Invoice` produces two `MissingColumn` entries, for
  columns `zip_code` and `amount`, both missing from profile `b`
- WHEN the result is produced
- THEN the entry for column `amount` SHALL precede the entry for column
  `zip_code`

## ADDED Requirements

### Requirement: Detect Missing Columns {#REQ-comparison-engine-006}

For every qualified table identity present in 2 or more of the compared
profiles (a matched table), the system MUST build the union of column names
across the profiles that have that table, and for each column name in that
union MUST determine which of those profiles lack the column. The system
MUST emit one `MissingColumn` diff entry per profile lacking a given column,
identifying the qualified table identity, the column name, and the profile
lacking it. A column present in every profile that has the matched table
MUST NOT produce a `MissingColumn` entry. Column-level missing detection
MUST NOT be evaluated for a profile in which the table itself is absent —
that condition is already captured exclusively by `MissingTable`, and a
profile already carrying a `MissingTable` entry for a given table MUST NOT
additionally receive `MissingColumn` entries for that same profile/table.

#### Scenario: Column missing from one profile of a matched table

- GIVEN table `sales.Invoice` exists in profiles `a`, `b`, `c`, with column
  `discount_pct` present in `a` and `b` but absent from `c`
- WHEN comparison is performed across `a`, `b`, `c`
- THEN the result SHALL include exactly one `MissingColumn` entry
  identifying `sales.Invoice`, column `discount_pct`, and profile `c`

#### Scenario: Column missing from a subset of a matched table's profiles

- GIVEN table `sales.Invoice` exists in 4 compared profiles `a`, `b`, `c`,
  `d`, with column `notes` present in `a` and `b` but absent from `c` and
  `d`
- WHEN comparison is performed
- THEN the result SHALL include one `MissingColumn` entry naming profile
  `c` and a separate entry naming profile `d`, for column `notes` of
  `sales.Invoice`

#### Scenario: Column present in every profile that has the table produces no entry

- GIVEN table `sales.Invoice` exists in profiles `a`, `b`, `c`, with column
  `amount` present in all three
- WHEN comparison is performed
- THEN the result SHALL NOT include any `MissingColumn` entry for column
  `amount` of `sales.Invoice`

#### Scenario: A table missing entirely from a profile produces no MissingColumn entries for that profile

- GIVEN table `archive.Invoice` exists in profiles `a` and `b` but is
  entirely absent from profile `c`
- WHEN comparison is performed across `a`, `b`, `c`
- THEN the result SHALL include a `MissingTable` entry for `archive.Invoice`
  naming profile `c`
- AND the result SHALL NOT include any `MissingColumn` entry naming profile
  `c` for any column of `archive.Invoice`

### Requirement: Detect Column Attribute Mismatches {#REQ-comparison-engine-007}

For every matched table (a qualified table identity present in 2 or more
compared profiles) and every column name present in 2 or more of the
profiles that have that table, the system MUST compare the `ColumnAttributes`
tuple — exactly `data_type`, `character_maximum_length`, `numeric_precision`,
`numeric_scale`, and `is_nullable`, explicitly excluding `ordinal_position`
and the column `name` — observed for that column in each such profile. If
the `ColumnAttributes` tuples are not all identical across those profiles,
the system MUST emit exactly one `ColumnMismatch` diff entry for that
column, naming the `ColumnAttributes` observed in every profile that has the
column (not one entry per differing profile pair). The per-profile
attribute mapping (`values_by_profile` or equivalent) MUST be ordered
deterministically ascending by profile name. A column whose
`ColumnAttributes` are identical across every profile that has it MUST NOT
produce a `ColumnMismatch` entry, regardless of any `ordinal_position`
difference. A `MissingColumn` entry and a `ColumnMismatch` entry for the
same column are independent and non-exclusive: a column may simultaneously
be missing from some profiles and mismatched among the profiles that have
it.

#### Scenario: Identical column attributes across profiles produce no entry

- GIVEN column `amount` of table `sales.Invoice` has identical `data_type`,
  `character_maximum_length`, `numeric_precision`, `numeric_scale`, and
  `is_nullable` in profiles `a`, `b`, `c`
- WHEN comparison is performed
- THEN the result SHALL NOT include any `ColumnMismatch` entry for column
  `amount` of `sales.Invoice`

#### Scenario: Differing data_type across two profiles produces one ColumnMismatch entry

- GIVEN column `amount` of table `sales.Invoice` has `data_type` `int` in
  profile `a` and `data_type` `bigint` in profile `b`, with all other
  `ColumnAttributes` fields identical
- WHEN comparison is performed
- THEN the result SHALL include exactly one `ColumnMismatch` entry for
  column `amount` of `sales.Invoice`, naming both profile `a`'s and profile
  `b`'s `ColumnAttributes`

#### Scenario: Type variance across three or more profiles is named individually in a single entry

- GIVEN column `amount` of table `sales.Invoice` has `data_type` `int` in
  profile `a`, `bigint` in profile `b`, and `smallint` in profile `c`
- WHEN comparison is performed across `a`, `b`, `c`
- THEN the result SHALL include exactly one `ColumnMismatch` entry for
  column `amount` of `sales.Invoice`, naming all three profiles'
  `ColumnAttributes` individually
- AND the result SHALL NOT include multiple `ColumnMismatch` entries
  (e.g. one per differing pair) for that column

#### Scenario: Nullable-only difference produces a ColumnMismatch entry

- GIVEN column `middle_name` of table `sales.Customer` has identical
  `data_type`, `character_maximum_length`, `numeric_precision`, and
  `numeric_scale` in profiles `a` and `b`, but `is_nullable` is `true` in
  `a` and `false` in `b`
- WHEN comparison is performed
- THEN the result SHALL include exactly one `ColumnMismatch` entry for
  column `middle_name` of `sales.Customer`, naming both profiles'
  `ColumnAttributes`

#### Scenario: Ordinal-position-only difference produces no entry

- GIVEN column `amount` of table `sales.Invoice` has identical `data_type`,
  `character_maximum_length`, `numeric_precision`, `numeric_scale`, and
  `is_nullable` in profiles `a` and `b`, but a different `ordinal_position`
  in each
- WHEN comparison is performed
- THEN the result SHALL NOT include any `ColumnMismatch` entry for column
  `amount` of `sales.Invoice`

#### Scenario: None-vs-concrete-value in a size/precision/scale field is a genuine mismatch

- GIVEN column `code` of table `sales.Product` has `data_type` `varchar`
  and `character_maximum_length` `50` in profile `a`, and `data_type`
  `varchar` with `character_maximum_length` `None` in profile `b`, with all
  other `ColumnAttributes` fields identical
- WHEN comparison is performed
- THEN the result SHALL include exactly one `ColumnMismatch` entry for
  column `code` of `sales.Product`, naming both profiles' `ColumnAttributes`
  without coercing the `None`-vs-`50` values to equal

#### Scenario: values_by_profile is ordered by profile name

- GIVEN a `ColumnMismatch` entry is produced for column `amount` of table
  `sales.Invoice` across profiles named `zeta`, `alpha`, `mid`, supplied to
  the engine in that input order
- WHEN the result is produced
- THEN the entry's per-profile attribute mapping SHALL list `alpha`, then
  `mid`, then `zeta`, independent of the input snapshot order

#### Scenario: A column can be both missing from some profiles and mismatched among the rest

- GIVEN table `sales.Invoice` exists in profiles `a`, `b`, `c`, with column
  `discount_pct` absent from profile `c`, and present in `a` and `b` with
  differing `data_type`
- WHEN comparison is performed across `a`, `b`, `c`
- THEN the result SHALL include one `MissingColumn` entry for column
  `discount_pct` naming profile `c`
- AND the result SHALL include one `ColumnMismatch` entry for column
  `discount_pct` naming profiles `a` and `b`'s `ColumnAttributes`

## RFC 2119 Keyword Legend

MUST/SHALL denote absolute requirements; MUST NOT/SHALL NOT denote absolute
prohibitions; SHOULD/MAY denote recommended or optional behavior. No
SHOULD/MAY-level requirements are introduced by this delta.
