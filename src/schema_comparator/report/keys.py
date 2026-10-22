"""Shared wording of primary key, foreign key and index findings for the
console, HTML, Excel, PDF and TUI, so the same finding never reads two ways."""

from schema_comparator.compare.models import (
    ForeignKeyMismatch,
    IndexMismatch,
    PrimaryKeyMismatch,
)
from schema_comparator.domain.schema.models import (
    ForeignKeySnapshot,
    IndexSnapshot,
    PrimaryKeySnapshot,
)
from schema_comparator.report.attributes import MISSING_MARKER

KeyMismatch = PrimaryKeyMismatch | ForeignKeyMismatch | IndexMismatch
KeySnapshot = PrimaryKeySnapshot | ForeignKeySnapshot | IndexSnapshot | None

KEY_MISMATCH_TYPES = (PrimaryKeyMismatch, ForeignKeyMismatch, IndexMismatch)


def _columns(names: tuple[str, ...], descending: tuple[str, ...] = ()) -> str:
    return ", ".join(f"{n} DESC" if n in descending else n for n in names)


def format_key(value: KeySnapshot, missing: str = MISSING_MARKER) -> str:
    """One definition on one line; `missing` stands for a profile without it."""
    if value is None:
        return missing
    if isinstance(value, PrimaryKeySnapshot):
        return f"{value.name} ({_columns(value.columns)})"
    if isinstance(value, ForeignKeySnapshot):
        target = (
            f"{value.referenced_schema}.{value.referenced_table}"
            if value.referenced_schema
            else value.referenced_table
        )
        parts = [
            f"({_columns(value.columns)}) -> {target} "
            f"({_columns(value.referenced_columns)})"
        ]
        if value.on_delete:
            parts.append(f"ON DELETE {value.on_delete}")
        if value.on_update:
            parts.append(f"ON UPDATE {value.on_update}")
        return ", ".join(parts)
    parts = []
    if value.is_unique:
        parts.append("UNIQUE")
    if value.is_clustered:
        parts.append("CLUSTERED")
    parts.append(f"({_columns(value.columns, value.descending_columns)})")
    if value.included_columns:
        parts.append(f"INCLUDE ({_columns(value.included_columns)})")
    if value.filter_expression:
        parts.append(f"WHERE {value.filter_expression}")
    return " ".join(parts)


def key_subject(entry: KeyMismatch) -> str:
    """What the finding is about: `PK`, the foreign key or the index name."""
    if isinstance(entry, PrimaryKeyMismatch):
        return "PK"
    if isinstance(entry, ForeignKeyMismatch):
        return entry.fk_name
    return entry.index_name


def key_values(
    entry: KeyMismatch, missing: str = MISSING_MARKER
) -> tuple[tuple[str, str], ...]:
    """`(profile, definition)` for every compared profile that has the table."""
    return tuple(
        (profile, format_key(value, missing))
        for profile, value in entry.values_by_profile
    )


def key_summary(entry: KeyMismatch) -> str:
    """Short phrase for a tree leaf: where it is absent, or who differs."""
    missing = [profile for profile, value in entry.values_by_profile if value is None]
    if missing:
        return f"falta en {', '.join(missing)}"
    profiles = ", ".join(profile for profile, _ in entry.values_by_profile)
    return f"definición distinta entre {profiles}"
