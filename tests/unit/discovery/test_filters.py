"""Unit tests for discovery.filters: table-name substring exclusion."""

from schema_comparator.discovery.filters import filter_excluded_tables
from schema_comparator.discovery.models import SchemaSnapshot, TableSnapshot


def _snapshot(*table_names: str) -> SchemaSnapshot:
    return SchemaSnapshot(
        profile_name="a",
        provider_id="sqlserver",
        tables=tuple(
            TableSnapshot(schema_name="dbo", table_name=name, columns=())
            for name in table_names
        ),
    )


def test_no_patterns_returns_snapshot_unchanged() -> None:
    snapshot = _snapshot("Invoice", "AuditLog")

    result = filter_excluded_tables(snapshot, [])

    assert result is snapshot


def test_excludes_tables_containing_any_pattern_case_insensitively() -> None:
    snapshot = _snapshot("Invoice", "AuditLog", "QRTZ_TRIGGERS", "Customer")

    result = filter_excluded_tables(snapshot, ["log", "QRTZ"])

    assert [t.table_name for t in result.tables] == ["Invoice", "Customer"]


def test_keeps_tables_not_matching_any_pattern() -> None:
    snapshot = _snapshot("Invoice", "Customer")

    result = filter_excluded_tables(snapshot, ["LOG"])

    assert [t.table_name for t in result.tables] == ["Invoice", "Customer"]


def test_preserves_profile_name() -> None:
    snapshot = _snapshot("AuditLog")

    result = filter_excluded_tables(snapshot, ["LOG"])

    assert result.profile_name == "a"
    assert result.tables == ()
