"""Unit tests for discovery.queries: CATALOG_QUERY_SQL and _build_snapshot."""

from schema_comparator.discovery.models import SchemaSnapshot
from schema_comparator.discovery.queries import CATALOG_QUERY_SQL, _build_snapshot


def test_catalog_query_selects_base_tables_only() -> None:
    assert "INFORMATION_SCHEMA.COLUMNS" in CATALOG_QUERY_SQL
    assert "INFORMATION_SCHEMA.TABLES" in CATALOG_QUERY_SQL
    assert "BASE TABLE" in CATALOG_QUERY_SQL
    for ddl_keyword in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"):
        assert ddl_keyword not in CATALOG_QUERY_SQL.upper()


def test_visible_base_table_metadata_is_returned_with_nulls_preserved() -> None:
    rows = [
        ("sales", "Invoice", "id", "int", None, 10, 0, "NO", 1),
        ("sales", "Invoice", "notes", "text", None, None, None, "YES", 2),
    ]

    snapshot = _build_snapshot("claims-service", rows)

    assert snapshot.profile_name == "claims-service"
    assert len(snapshot.tables) == 1
    table = snapshot.tables[0]
    assert table.schema_name == "sales"
    assert table.table_name == "Invoice"
    assert len(table.columns) == 2
    notes_column = table.columns[1]
    assert notes_column.character_maximum_length is None
    assert notes_column.numeric_precision is None
    assert notes_column.numeric_scale is None
    assert notes_column.is_nullable is True


def test_empty_visible_catalog_returns_empty_snapshot() -> None:
    snapshot = _build_snapshot("claims-service", [])
    assert snapshot == SchemaSnapshot(profile_name="claims-service", provider_id="sqlserver", tables=())


def test_same_named_tables_in_distinct_schemas_remain_distinct() -> None:
    rows = [
        ("sales", "Invoice", "id", "int", None, 10, 0, "NO", 1),
        ("archive", "Invoice", "id", "int", None, 10, 0, "NO", 1),
    ]

    snapshot = _build_snapshot("claims-service", rows)

    assert len(snapshot.tables) == 2
    schema_names = {table.schema_name for table in snapshot.tables}
    assert schema_names == {"sales", "archive"}


def test_unordered_catalog_rows_produce_a_stable_snapshot() -> None:
    rows_a = [
        ("sales", "Invoice", "id", "int", None, 10, 0, "NO", 1),
        ("archive", "Invoice", "id", "int", None, 10, 0, "NO", 1),
        ("sales", "Invoice", "notes", "text", None, None, None, "YES", 2),
    ]
    rows_b = [
        ("sales", "Invoice", "notes", "text", None, None, None, "YES", 2),
        ("sales", "Invoice", "id", "int", None, 10, 0, "NO", 1),
        ("archive", "Invoice", "id", "int", None, 10, 0, "NO", 1),
    ]

    snapshot_a = _build_snapshot("claims-service", rows_a)
    snapshot_b = _build_snapshot("claims-service", rows_b)

    assert snapshot_a == snapshot_b
    assert [t.qualified_name for t in snapshot_a.tables] == [
        ("archive", "Invoice"),
        ("sales", "Invoice"),
    ]
    assert [c.name for c in snapshot_a.tables[1].columns] == ["id", "notes"]
