"""Result and diff-entry models for N-way schema comparison."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MissingTable:
    """A table present in the union baseline but absent from one profile.

    Carries only the qualified table identity and the profile lacking the
    table — never column metadata from profiles where the table exists
    (missing-column detection is a separate, future diff-entry type).
    """

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
    ascending order as `entries`, so a report can render "compared: A, B, C"
    even for tables/columns present everywhere. `entries` is a flat,
    ordered, immutable sequence — deliberately not grouped or nested — so
    later diff-entry types can be appended without reshaping this
    container.
    """

    compared_profiles: tuple[str, ...]
    entries: tuple[DiffEntry, ...]
