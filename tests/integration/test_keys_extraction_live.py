"""Primary keys, foreign keys and indexes read from a real SQL Server.

The catalog queries run through the container's sqlcmd (the container's port
is not published, so the provider cannot connect); their rows go through the
same `build_snapshot` the provider uses. Skipped when Docker is unavailable.
"""

from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.infrastructure.providers.sqlserver import introspector

_SCHEMA = """
CREATE TABLE dbo.customers (
    id int NOT NULL PRIMARY KEY,
    email nvarchar(100) NOT NULL UNIQUE
);
CREATE TABLE dbo.orders (
    id int NOT NULL CONSTRAINT PK_orders PRIMARY KEY,
    customer_id int NOT NULL FOREIGN KEY REFERENCES dbo.customers (id) ON DELETE CASCADE,
    total money NULL,
    status int NULL
);
CREATE NONCLUSTERED INDEX IX_orders_cust ON dbo.orders (customer_id DESC)
    INCLUDE (total) WHERE status IS NOT NULL;
"""

# Positions of the integer columns of each query, for converting sqlcmd text.
_INTS = {
    "columns": {4, 5, 6, 8, 10, 12},
    "primary_keys": {3, 5},
    "foreign_keys": {3, 8},
    "indexes": {3, 4, 6, 8, 9, 10},
}


def _typed(rows, ints: set[int]) -> list[tuple]:
    def convert(position: int, value: str):
        if value == "NULL":
            return None
        return int(value) if position in ints else value

    return [tuple(convert(i, v) for i, v in enumerate(row)) for row in rows]


def _snapshot(server, database: str, name: str):
    def rows(sql: str, kind: str) -> list[tuple]:
        return _typed(server.query(sql, database=database), _INTS[kind])

    return introspector.build_snapshot(
        name,
        rows(introspector.CATALOG_QUERY_SQL, "columns"),
        primary_key_rows=rows(introspector.PRIMARY_KEYS_QUERY_SQL, "primary_keys"),
        foreign_key_rows=rows(introspector.FOREIGN_KEYS_QUERY_SQL, "foreign_keys"),
        index_rows=rows(introspector.INDEXES_QUERY_SQL, "indexes"),
    )


def _setup(server, database: str, sql: str) -> None:
    result = server.run(f"{sql}\nGO\n", database=database)
    assert result.returncode == 0, result.stdout + result.stderr


def _system_names(server, database: str) -> set[str]:
    rows = server.query(
        "SELECT name FROM sys.objects WHERE is_ms_shipped = 0 AND name LIKE N'%\\_\\_%' ESCAPE N'\\'",
        database=database,
    )
    return {row[0] for row in rows}


def test_extracts_keys_and_indexes_and_ignores_generated_names(
    mssql_server, mssql_db
) -> None:
    _setup(mssql_server, mssql_db, _SCHEMA)
    snapshot = _snapshot(mssql_server, mssql_db, "a")
    tables = {t.table_name: t for t in snapshot.tables}

    orders, customers = tables["orders"], tables["customers"]
    assert orders.primary_key.name == "PK_orders"
    assert orders.primary_key.columns == ("id",)
    assert customers.primary_key.name == introspector.AUTO_PRIMARY_KEY_NAME

    (fk,) = orders.foreign_keys
    assert fk.name == "FK (customer_id) -> dbo.customers (id)"
    assert (fk.referenced_schema, fk.referenced_table) == ("dbo", "customers")
    assert (fk.on_delete, fk.on_update) == ("CASCADE", "NO ACTION")

    (index,) = orders.indexes
    assert index.name == "IX_orders_cust"
    assert index.columns == ("customer_id",)
    assert index.descending_columns == ("customer_id",)
    assert index.included_columns == ("total",)
    assert index.filter_expression == "([status] IS NOT NULL)"
    assert not index.is_unique and not index.is_clustered

    (unique,) = customers.indexes
    assert unique.name == "UQ (email)" and unique.is_unique


def test_two_databases_with_different_generated_names_have_no_key_drift(
    mssql_server, mssql_db
) -> None:
    other = mssql_server.create_database()
    try:
        _setup(mssql_server, mssql_db, _SCHEMA)
        # Consume object ids so SQL Server generates other suffixes.
        _setup(
            mssql_server,
            other,
            "CREATE TABLE dbo.tmp (i int); DROP TABLE dbo.tmp;\n" + _SCHEMA,
        )
        assert _system_names(mssql_server, mssql_db) != _system_names(
            mssql_server, other
        )

        a = _snapshot(mssql_server, mssql_db, "a")
        b = _snapshot(mssql_server, other, "b")

        assert compare_snapshots([a, b]).entries == ()

        _setup(
            mssql_server,
            other,
            "DROP INDEX IX_orders_cust ON dbo.orders;\n"
            "CREATE INDEX IX_orders_cust ON dbo.orders (customer_id);",
        )
        changed = compare_snapshots([a, _snapshot(mssql_server, other, "b")])
        assert {type(e).__name__ for e in changed.entries} == {"IndexMismatch"}
    finally:
        mssql_server.drop_database(other)
