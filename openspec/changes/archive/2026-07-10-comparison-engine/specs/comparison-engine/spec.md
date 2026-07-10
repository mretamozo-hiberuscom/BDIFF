# Comparison Engine Specification

## Purpose

Provide a pure, side-effect-free N-way comparison engine that consumes 2+
named `SchemaSnapshot` values (from `schema-extraction`) and produces a
deterministic, order-independent `ComparisonResult` built on a union-of-
objects baseline over qualified table identity, including missing-table
detection as the first fully implemented diff category.

## Non-Goals

This capability MUST NOT implement missing-column detection, column
type/size/precision/scale/nullability mismatch detection, likely-rename
heuristics, or report generation/rendering. These remain out of scope and are
addressed by separate future changes; the result model MUST remain
extensible for them without requiring a reshape.

## Clarifications

### Session 2026-07-10

- Q: Should the `MissingTable` diff entry carry only the qualified table
  identity plus the profile(s) it's missing from, or should it also snapshot
  the column metadata of that table from the profile(s) where it DOES exist?
  → A: **identity-and-profile-only** — `MissingTable` MUST carry only the
  qualified table identity (`schema_name`, `table_name`) and the profile
  lacking the table. It MUST NOT snapshot or embed column metadata from
  profiles where the table exists. Missing-column detection and any related
  data is out of scope for this change per the Non-Goals above; the proposal's
  own extensibility approach is to add new diff-entry type variants to the
  flat sequence for future detection categories, not to enrich existing
  entry types with data outside their own concern. Pre-emptively snapshotting
  column metadata here would be speculative design for a not-yet-specified
  future change and risks locking in a shape that missing-column detection's
  own future exploration phase has not yet chosen.

## Requirements

### Requirement: Accept N-Way Named Snapshot Input {#REQ-comparison-engine-001}

The system MUST accept a sequence of 2 or more `SchemaSnapshot` values as the
sole input to comparison. Each snapshot MUST carry a `profile_name`. The
system MUST reject, with a clear domain error (no raw stack trace), any input
of fewer than 2 snapshots or any input containing 2+ snapshots that share the
same `profile_name`. The system MUST NOT proceed with a union computation
when a precondition is violated.

#### Scenario: Valid multi-profile input is accepted

- GIVEN 3 `SchemaSnapshot` values with distinct profile names `a`, `b`, `c`
- WHEN the comparison engine is invoked with these snapshots
- THEN it SHALL return a `ComparisonResult` that names all of `a`, `b`, `c`
  as compared profiles

#### Scenario: Fewer than 2 snapshots is rejected

- GIVEN a single `SchemaSnapshot` for profile `a`
- WHEN the comparison engine is invoked with only that snapshot
- THEN it SHALL raise a clear domain error indicating at least 2 snapshots
  are required
- AND no `ComparisonResult` SHALL be returned

#### Scenario: Duplicate profile names is rejected

- GIVEN 2 `SchemaSnapshot` values that both carry `profile_name` `staging`
- WHEN the comparison engine is invoked with these snapshots
- THEN it SHALL raise a clear domain error indicating duplicate profile
  names among inputs
- AND no `ComparisonResult` SHALL be returned

### Requirement: Compute Union-of-Objects Baseline {#REQ-comparison-engine-002}

The system MUST derive the baseline as the union of every distinct qualified
table identity (`schema_name`, `table_name`) observed across all input
snapshots. The baseline SHALL NOT be one designated/reference snapshot. The
union computation MUST be independent of the order in which snapshots are
supplied to the engine.

#### Scenario: Union includes tables from every snapshot

- GIVEN snapshot `a` with table `sales.Invoice`, snapshot `b` with table
  `sales.Invoice` and `sales.Payment`, snapshot `c` with table
  `archive.Invoice`
- WHEN the union baseline is computed
- THEN it SHALL contain `sales.Invoice`, `sales.Payment`, and
  `archive.Invoice` as 3 distinct qualified table identities

#### Scenario: Union membership is independent of input order

- GIVEN the same set of snapshots supplied in two different input orders
- WHEN the union baseline is computed for each order
- THEN both computations SHALL produce an identical set of qualified table
  identities

### Requirement: Detect Missing Tables {#REQ-comparison-engine-003}

For every qualified table identity in the union baseline, the system MUST
determine which of the N input profiles lack that table and MUST emit one
`MissingTable` diff entry per missing occurrence, identifying the qualified
table identity and the profile that lacks it. A table present in every input
snapshot MUST NOT produce a diff entry.

#### Scenario: Table missing from one of three profiles

- GIVEN table `sales.Payment` exists in snapshots `a` and `b` but not in
  snapshot `c`
- WHEN comparison is performed across `a`, `b`, `c`
- THEN the result SHALL include exactly one `MissingTable` entry identifying
  `sales.Payment` and profile `c`

#### Scenario: Table missing from multiple profiles

- GIVEN table `archive.Invoice` exists only in snapshot `a` among 3 compared
  snapshots
- WHEN comparison is performed
- THEN the result SHALL include one `MissingTable` entry for `archive.Invoice`
  naming profile `b` and a separate entry naming profile `c`

#### Scenario: Table present everywhere produces no entry

- GIVEN table `sales.Invoice` exists in every compared snapshot
- WHEN comparison is performed
- THEN the result SHALL NOT include any `MissingTable` entry for
  `sales.Invoice`

### Requirement: Return Deterministically Ordered Results {#REQ-comparison-engine-004}

The system MUST order the diff-entry sequence in a `ComparisonResult` by
ascending qualified table identity (schema name, then table name), then by a
stable diff-type ordering. This ordering SHALL be independent of the order in
which input snapshots were supplied, so equivalent input snapshot sets
produce an identical ordered result regardless of input order.

#### Scenario: Result ordering is stable across input snapshot order

- GIVEN the same set of snapshots supplied in two different input orders,
  producing the same missing-table findings
- WHEN comparison is performed for each order
- THEN the resulting diff-entry sequences SHALL be identical, including
  entry order

#### Scenario: Entries are ordered by qualified table identity

- GIVEN missing-table findings for tables `zeta.Report` and `alpha.Customer`
- WHEN the result is produced
- THEN the entry for `alpha.Customer` SHALL precede the entry for
  `zeta.Report` in the result sequence

### Requirement: Handle Degenerate Comparison Cases {#REQ-comparison-engine-005}

When all compared snapshots contain an identical set of qualified table
identities, the system MUST return a `ComparisonResult` naming all compared
profiles with an empty diff-entry sequence, rather than an error. Inputs of
fewer than 2 snapshots remain a precondition violation per
REQ-comparison-engine-001, not a degenerate success case.

#### Scenario: Identical snapshots produce an empty diff

- GIVEN 2 snapshots with distinct profile names that both contain exactly
  the same qualified table identities
- WHEN comparison is performed
- THEN the result SHALL name both profiles as compared
- AND the diff-entry sequence SHALL be empty

## RFC 2119 Keyword Legend

MUST/SHALL denote absolute requirements; MUST NOT/SHALL NOT denote absolute
prohibitions; SHOULD/MAY denote recommended or optional behavior. No
SHOULD/MAY-level requirements apply in this capability.
