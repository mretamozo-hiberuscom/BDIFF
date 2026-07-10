"""Shared fixture helper for comparison-engine unit tests."""

from schema_comparator.discovery.models import SchemaSnapshot, TableSnapshot


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
