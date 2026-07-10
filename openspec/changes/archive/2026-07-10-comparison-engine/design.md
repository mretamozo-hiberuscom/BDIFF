# Design: Comparison Engine

Change: `comparison-engine`
Status: design (phase artifact)
Scope: a pure, in-memory, side-effect-free N-way comparison stage that
consumes 2+ named `SchemaSnapshot` values (from `schema-extraction`) and
produces a deterministic, order-independent `ComparisonResult` built on a
union-of-objects baseline over qualified table identity, with missing-table
detection as the one fully implemented diff category. No missing-column
detection, mismatch detection, report rendering, or persistence (all
deferred to later capabilities per the proposal's Non-Goals).

This design realizes the five requirements in
`openspec/changes/comparison-engine/specs/comparison-engine/spec.md` and the
clarify decision recorded in `state.yaml` (`MissingTable` carries only
qualified table identity + the missing profile, never column metadata). It
builds on, and does not duplicate,
`openspec/changes/archive/2026-07-10-schema-extraction/design.md`: this
capability only *consumes* `SchemaSnapshot`/`TableSnapshot` (already
immutable, already sorted, already keyed by `(schema_name, table_name)`) — it
never re-derives, mutates, or re-sorts the snapshot models themselves.

---

## 1. Module / file layout

```text
src/schema_comparator/compare/
  __init__.py     # public API surface: re-exports models, errors, compare_snapshots
  models.py       # ComparisonResult, MissingTable (frozen dataclasses)
  errors.py       # ComparisonError hierarchy + precondition validation
  engine.py       # compare_snapshots(snapshots, ...) — union + evaluate orchestration
```

This mirrors the `discovery/` package shape from the prior capability
(`models.py` / `errors.py` / a single orchestration module), which the
proposal's Affected Areas table already calls for. There is no equivalent of
`connectors/` here — the compare stage has no I/O boundary to isolate; it
only ever touches in-memory `SchemaSnapshot` values passed in by the caller.

### Public API (`compare/__init__.py`)

```python
from schema_comparator.compare.models import (
    ComparisonResult,
    MissingTable,
)
from schema_comparator.compare.errors import (
    ComparisonError,
    InsufficientSnapshotsError,
    DuplicateProfileNameError,
)
from schema_comparator.compare.engine import compare_snapshots

__all__ = [
    "ComparisonResult",
    "MissingTable",
    "compare_snapshots",
    "ComparisonError",
    "InsufficientSnapshotsError",
    "DuplicateProfileNameError",
]
```

`compare_snapshots` is the single entry point, matching the proposal's
"entry-point function accepting `Sequence[SchemaSnapshot]`". No other public
function is exposed — callers (the future CLI orchestrator, and this
change's own tests) never need to call the union pass or the evaluation
pass independently.

---

## 2. Data model: `ComparisonResult` / `MissingTable`

Following the same rationale as `discovery/models.py`: plain stdlib
`@dataclass(frozen=True, slots=True)` value objects, no pydantic, no ORM.
Per the clarify decision, `MissingTable` carries *only* the qualified table
identity and the profile lacking it — no column metadata is snapshotted or
embedded, keeping the entry's concern strictly scoped to its own diff
category.

```python
# compare/models.py
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MissingTable:
    """A table present in the union baseline but absent from one profile.

    Carries only the qualified table identity and the profile lacking the
    table — never column metadata from profiles where the table exists
    (missing-column detection is a separate, future diff-entry type)."""

    schema_name: str
    table_name: str
    missing_from_profile: str

    @property
    def qualified_name(self) -> tuple[str, str]:
        """The table identity, matching `TableSnapshot.qualified_name`."""
        return (self.schema_name, self.table_name)


# Only one diff-entry variant exists in this change. Future changes add
# sibling frozen dataclasses (e.g. MissingColumn, ColumnMismatch) and widen
# this alias — no reshape of ComparisonResult or existing entry types.
DiffEntry = MissingTable


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """The full comparison output across N compared profiles.

    `compared_profiles` names every input profile, in the same normalized
    ascending order as `entries` (see §4), so a report can render "compared:
    A, B, C" even for tables/columns present everywhere. `entries` is a flat,
    ordered, immutable sequence — deliberately not grouped or nested — so
    later diff-entry types can be appended without reshaping this
    container."""

    compared_profiles: tuple[str, ...]
    entries: tuple[DiffEntry, ...]
```

Using a type alias (`DiffEntry = MissingTable`) rather than an abstract base
class or `Protocol` keeps this change's code honest about what actually
exists today: exactly one entry type. When missing-column detection is
added, the alias becomes `DiffEntry = MissingTable | MissingColumn`, a
one-line widening that every existing consumer (including this change's own
tests) keeps working against unchanged, since `ComparisonResult.entries` was
never typed as `tuple[MissingTable, ...]` in a way call sites depend on
structurally.

`tuple[...]` (not `list[...]`) for both fields keeps `ComparisonResult`
fully immutable end-to-end, matching the same discipline already applied to
`SchemaSnapshot`/`TableSnapshot`.

---

## 3. Precondition validation

Per REQ-comparison-engine-001, `compare_snapshots` MUST reject fewer than 2
snapshots and duplicate `profile_name`s with a clear domain error before any
union computation starts — never a raw stack trace, and never a partial
`ComparisonResult`.

```python
# compare/errors.py
class ComparisonError(Exception):
    """Base class for all comparison-engine failures."""


class InsufficientSnapshotsError(ComparisonError):
    @classmethod
    def for_count(cls, count: int) -> "InsufficientSnapshotsError":
        return cls(
            f"Comparison requires at least 2 snapshots, got {count}. "
            "Provide 2 or more named schema snapshots to compare."
        )


class DuplicateProfileNameError(ComparisonError):
    @classmethod
    def for_names(cls, names: list[str]) -> "DuplicateProfileNameError":
        joined = ", ".join(sorted(set(names)))
        return cls(
            "Comparison requires distinct profile names among inputs; "
            f"duplicate profile name(s) found: {joined}."
        )
```

`engine.py` validates both preconditions before touching the snapshot
contents, in this order (count first, since a duplicate-name check on a
single-element input is meaningless):

```python
def _validate(snapshots: Sequence[SchemaSnapshot]) -> None:
    if len(snapshots) < 2:
        raise InsufficientSnapshotsError.for_count(len(snapshots))

    names = [s.profile_name for s in snapshots]
    if len(set(names)) != len(names):
        duplicates = [n for n in names if names.count(n) > 1]
        raise DuplicateProfileNameError.for_names(duplicates)
```

This mirrors the prior capability's discipline of translating failure
conditions into named, profile/context-carrying domain errors rather than
letting a bare `ValueError`/`IndexError` propagate — kept in `errors.py` so
`engine.py`'s orchestration function stays a thin, readable sequence of
validate → union → evaluate → return.

---

## 4. Two-pass union-of-identities algorithm

Per the exploration's Approach 1 recommendation, the algorithm is a
deliberate two-pass computation — never pairwise (O(N²)) cross-comparison,
which the exploration already rejected as semantically wrong for a union
model.

**Pass 1 — union**: derive the set of every distinct qualified table
identity across all N snapshots, and build a per-snapshot presence index for
O(1) membership checks in Pass 2.

```python
def _build_presence_index(
    snapshots: Sequence[SchemaSnapshot],
) -> tuple[set[tuple[str, str]], dict[str, set[tuple[str, str]]]]:
    union: set[tuple[str, str]] = set()
    presence: dict[str, set[tuple[str, str]]] = {}
    for snapshot in snapshots:
        identities = {t.qualified_name for t in snapshot.tables}
        union |= identities
        presence[snapshot.profile_name] = identities
    return union, presence
```

The union is a plain `set`, not a materialized snapshot — consistent with
the exploration's framing that "baseline" is a derived index used only to
know what to check, never a stored/designated reference database.

**Pass 2 — evaluate**: iterate the union in deterministic sort order (§5);
for each table identity, compute the profiles lacking it (`all profile
names - profiles present`) and emit one `MissingTable` entry per missing
profile, itself in ascending profile-name order.

```python
def _evaluate(
    union: set[tuple[str, str]],
    presence: dict[str, set[tuple[str, str]]],
    profile_names: tuple[str, ...],
) -> tuple[MissingTable, ...]:
    entries: list[MissingTable] = []
    for schema_name, table_name in sorted(union):
        identity = (schema_name, table_name)
        missing_from = sorted(
            name for name in profile_names if identity not in presence[name]
        )
        entries.extend(
            MissingTable(
                schema_name=schema_name,
                table_name=table_name,
                missing_from_profile=name,
            )
            for name in missing_from
        )
    return tuple(entries)
```

A table present in every profile contributes an empty `missing_from` list
and therefore no entries, directly satisfying REQ-comparison-engine-003's
"present in every input snapshot MUST NOT produce a diff entry" without a
special-case branch.

`engine.py`'s entry point composes both passes and precondition validation:

```python
def compare_snapshots(snapshots: Sequence[SchemaSnapshot]) -> ComparisonResult:
    _validate(snapshots)
    profile_names = tuple(sorted(s.profile_name for s in snapshots))
    union, presence = _build_presence_index(snapshots)
    entries = _evaluate(union, presence, profile_names)
    return ComparisonResult(compared_profiles=profile_names, entries=entries)
```

Because both passes operate on plain Python `set`/`dict` structures built
once from already-immutable snapshot inputs, and both passes are pure
functions of their arguments, this is trivially unit-testable with
hand-built fixtures and requires no mocking.

---

## 5. Deterministic ordering approach

Per REQ-comparison-engine-004, both `compared_profiles` and `entries` MUST
be ordered independently of input snapshot order:

- **`compared_profiles`**: `tuple(sorted(...))` by profile name ascending —
  the input list order (whatever order the caller happened to pass
  snapshots in) is discarded entirely.
- **Union iteration order**: `sorted(union)` sorts the `(schema_name,
  table_name)` tuples by ordinary Python tuple comparison (schema name
  first, then table name), matching REQ-comparison-engine-004's "ascending
  qualified table identity (schema name, then table name)".
- **Diff-type ordering**: this change has exactly one diff-entry type
  (`MissingTable`), so no explicit cross-type tie-break rule is needed yet.
  When a second diff-entry type is added (e.g. `MissingColumn`), `_evaluate`
  gains an explicit type-rank tuple (e.g. `(table_identity, TYPE_RANK,
  ...)`) as the sort key so type ordering stays a single, visible decision
  point rather than emerging accidentally from insertion order — this is a
  documented forward-compatibility note, not code shipped in this change.
- **Within-table missing-profile ordering**: `sorted(...)` on
  `missing_from` orders multiple entries for the same table by profile name
  ascending, so "table missing from profiles b and c" always produces the
  `b` entry before the `c` entry regardless of input order.

No sort is ever performed over the raw input `snapshots` sequence itself
(the caller's order is read once, for `profile_name`/presence extraction,
and never influences output ordering thereafter) — this is what makes
order-independence provable by construction rather than by convention.

---

## 6. Testing strategy (no live database)

Runner: **pytest**, new `tests/unit/compare/` package, matching
`tests/unit/discovery/`'s existing layout and `stack-python-testing`.
`strict_tdd` remains `false` for this project. All tests are pure in-memory:
hand-built `SchemaSnapshot`/`TableSnapshot` fixtures, no `pyodbc`, no
network, no mocking framework needed (the compare stage has no I/O
boundary to fake).

### Fixture helpers

A small module-level helper builds minimal snapshots without repeating
`ColumnSnapshot` boilerplate irrelevant to comparison (comparison only reads
`TableSnapshot.qualified_name`, never column contents, per the clarify
decision):

```python
def make_snapshot(profile_name: str, *tables: tuple[str, str]) -> SchemaSnapshot:
    """Build a SchemaSnapshot with empty-column tables for the given
    (schema_name, table_name) pairs — sufficient for comparison-engine
    tests, which never inspect column data."""
    return SchemaSnapshot(
        profile_name=profile_name,
        tables=tuple(
            TableSnapshot(schema_name=s, table_name=t, columns=())
            for s, t in sorted(tables)
        ),
    )
```

### Coverage matrix (one test per spec scenario)

| Spec scenario | Test intent |
|---|---|
| Valid multi-profile input is accepted | 3 snapshots, distinct names → `ComparisonResult.compared_profiles == ("a", "b", "c")` |
| Fewer than 2 snapshots is rejected | 1 snapshot → `InsufficientSnapshotsError`, no result returned |
| Duplicate profile names is rejected | 2 snapshots both named `staging` → `DuplicateProfileNameError` |
| Union includes tables from every snapshot | 3 snapshots with overlapping/disjoint tables → union (inferred from resulting entries/no-entries) covers all distinct identities |
| Union membership is independent of input order | same snapshots in two input orders → identical `entries` |
| Table missing from one of three profiles | table in `a`,`b` not `c` → exactly one `MissingTable(..., missing_from_profile="c")` |
| Table missing from multiple profiles | table only in `a` → one entry naming `b`, one entry naming `c` |
| Table present everywhere produces no entry | table in all snapshots → no `MissingTable` entry for it |
| Result ordering is stable across input snapshot order | same snapshot set, two input orders → identical `entries` tuples, element-for-element |
| Entries are ordered by qualified table identity | findings for `zeta.Report` and `alpha.Customer` → `alpha.Customer` entry precedes `zeta.Report` entry |
| Identical snapshots produce an empty diff | 2 snapshots, same table set → `entries == ()`, both profiles named in `compared_profiles` |

This matrix is a direct, one-to-one mapping of the spec's own Scenario
blocks (`REQ-comparison-engine-001` through `-005`), so verify-phase
traceability from spec scenario to test is unambiguous.

---

## 7. Sequence diagram: comparison flow

Per `openspec/config.yaml` `rules.design` ("sequence diagrams for complex
flows") — this flow has two internal passes plus two independent
precondition-failure branches, similar in shape to the prior capability's
two-branch extraction flow.

```mermaid
sequenceDiagram
    participant Caller
    participant Engine as compare.engine
    participant Validate as _validate
    participant Union as _build_presence_index
    participant Eval as _evaluate
    participant Model as ComparisonResult

    Caller->>Engine: compare_snapshots(snapshots)
    Engine->>Validate: _validate(snapshots)
    activate Validate

    alt fewer than 2 snapshots
        Validate-->>Engine: raise InsufficientSnapshotsError
        deactivate Validate
        Engine-->>Caller: propagate InsufficientSnapshotsError
    else duplicate profile_name among snapshots
        Validate-->>Engine: raise DuplicateProfileNameError
        deactivate Validate
        Engine-->>Caller: propagate DuplicateProfileNameError
    else preconditions satisfied
        Validate-->>Engine: ok
        deactivate Validate

        Engine->>Engine: profile_names = sorted(profile_name for each snapshot)
        Engine->>Union: _build_presence_index(snapshots)
        activate Union
        Union->>Union: union |= qualified_names(snapshot.tables)\n(per snapshot, Pass 1)
        Union-->>Engine: (union, presence)
        deactivate Union

        Engine->>Eval: _evaluate(union, presence, profile_names)
        activate Eval
        Eval->>Eval: for identity in sorted(union):\n  missing = sorted(profiles lacking identity)\n  emit MissingTable per missing profile
        Eval-->>Engine: entries (ordered tuple)
        deactivate Eval

        Engine->>Model: ComparisonResult(profile_names, entries)
        Model-->>Engine: ComparisonResult
        Engine-->>Caller: ComparisonResult
    end
```

Key properties this diagram makes explicit:

- Precondition validation (`_validate`) is the single gate before any union
  computation begins — both failure branches return before Pass 1 ever
  runs, matching REQ-comparison-engine-001's "MUST NOT proceed with a union
  computation when a precondition is violated."
- The union (Pass 1) and evaluation (Pass 2) are separate, sequential steps
  with no shared mutable state beyond the `union`/`presence` values passed
  explicitly between them — there is no hidden pass-order dependency to
  reason about.
- Every sort (`profile_names`, `sorted(union)`, `sorted(missing)`) is shown
  at the exact step it applies, making the "output never depends on caller's
  input order" property traceable directly from the diagram rather than
  only from prose.

---

## 8. Dependency addition

None. This change introduces no new third-party dependency; it only adds
`src/schema_comparator/compare/*` modules and `tests/unit/compare/*` tests,
consuming the existing `discovery/models.py` types as-is.
