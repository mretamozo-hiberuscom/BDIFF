"""Unit tests for SqlServerProvider."""

from unittest.mock import MagicMock, patch

import pyodbc
import pytest

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.errors import (
    ConnectionFailedError,
    DriverUnavailableError,
    MetadataAccessError,
)
from schema_comparator.infrastructure.providers.sqlserver import introspector
from schema_comparator.infrastructure.providers.sqlserver.provider import (
    SqlServerProvider,
)

_CONNECT = "schema_comparator.infrastructure.providers.sqlserver.connection.connect"
_SENTINEL = "SECRET-SENTINEL-VALUE"


def test_sql_server_provider_metadata() -> None:
    provider = SqlServerProvider()
    assert provider.provider_id == "sqlserver"


def test_sql_server_provider_validate_empty_connection_string() -> None:
    provider = SqlServerProvider()
    profile = ConnectionProfile(name="test", connection_string="")
    with pytest.raises(ValueError, match="Profile 'test' has empty connection string"):
        provider.validate_profile(profile)


def test_sql_server_provider_introspect_success() -> None:
    provider = SqlServerProvider()
    profile = ConnectionProfile(
        name="test_prof", connection_string="Server=srv;Database=db;"
    )

    mock_cursor = MagicMock()
    # One result per query: columns, primary keys, foreign keys, indexes,
    # routines.
    mock_cursor.fetchall.side_effect = [
        [("dbo", "users", "id", "int", None, 10, 0, "NO", 1)],
        [],
        [],
        [],
        [],
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch(
        "schema_comparator.infrastructure.providers.sqlserver.connection.connect"
    ) as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_conn

        snapshot = provider.introspect(profile)

        assert snapshot.profile_name == "test_prof"
        assert len(snapshot.tables) == 1
        assert snapshot.tables[0].table_name == "users"
        mock_cursor.close.assert_called_once()


def test_sql_server_provider_introspect_query_error() -> None:
    provider = SqlServerProvider()
    profile = ConnectionProfile(
        name="test_prof", connection_string="Server=srv;Database=db;"
    )

    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = pyodbc.Error("42000", "Permission denied")

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch(
        "schema_comparator.infrastructure.providers.sqlserver.connection.connect"
    ) as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_conn

        with pytest.raises(MetadataAccessError):
            provider.introspect(profile)

        mock_cursor.close.assert_called_once()


def test_sql_server_provider_introspect_connect_error() -> None:
    provider = SqlServerProvider()
    profile = ConnectionProfile(
        name="test_prof", connection_string="Server=srv;Database=db;"
    )

    with patch(
        "schema_comparator.infrastructure.providers.sqlserver.connection.connect"
    ) as mock_connect:
        mock_connect.side_effect = pyodbc.Error("08001", "Unable to connect")

        with pytest.raises(ConnectionFailedError):
            provider.introspect(profile)


def _introspect_with(*, connect_error=None, execute_error=None):
    profile = ConnectionProfile(name="claims-service", connection_string=_SENTINEL)
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    if execute_error is not None:
        mock_cursor.execute.side_effect = execute_error
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    with patch(_CONNECT) as mock_connect:
        if connect_error is not None:
            mock_connect.side_effect = connect_error
        mock_connect.return_value.__enter__.return_value = mock_conn
        SqlServerProvider().introspect(profile)
    return mock_cursor


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (
            {"connect_error": pyodbc.Error("HYT00", "login timeout")},
            ConnectionFailedError,
        ),
        (
            {"execute_error": pyodbc.Error("HYT01", "query timeout")},
            ConnectionFailedError,
        ),
        (
            {"connect_error": pyodbc.Error("IM002", "driver not found")},
            DriverUnavailableError,
        ),
    ],
)
def test_sql_server_provider_translates_timeouts_and_missing_driver(
    kwargs, expected
) -> None:
    with pytest.raises(expected):
        _introspect_with(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"connect_error": pyodbc.Error("08001", f"conn={_SENTINEL}")},
        {"execute_error": pyodbc.Error("42000", f"conn={_SENTINEL}")},
    ],
)
def test_sql_server_provider_errors_never_include_the_connection_string(
    kwargs,
) -> None:
    with pytest.raises(Exception) as exc_info:
        _introspect_with(**kwargs)

    assert _SENTINEL not in str(exc_info.value)


def test_sql_server_provider_only_runs_read_only_catalog_queries() -> None:
    cursor = _introspect_with()

    executed = [call.args[0] for call in cursor.execute.call_args_list]
    assert executed == [
        introspector.CATALOG_QUERY_SQL,
        introspector.PRIMARY_KEYS_QUERY_SQL,
        introspector.FOREIGN_KEYS_QUERY_SQL,
        introspector.INDEXES_QUERY_SQL,
        introspector.PROCEDURES_QUERY_SQL,
    ]
    for sql in executed:
        for write_keyword in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER "):
            assert write_keyword not in sql.upper()


def test_catalog_query_reads_default_identity_collation_and_time_precision() -> None:
    sql = introspector.CATALOG_QUERY_SQL

    for fragment in (
        "COLUMN_DEFAULT",
        "'IsIdentity'",
        "DATABASEPROPERTYEX(DB_NAME(), 'Collation')",
        "DATETIME_PRECISION",
    ):
        assert fragment in sql


def test_build_snapshot_keeps_the_extended_column_attributes() -> None:
    rows = [
        ("dbo", "t", "id", "int", None, 10, 0, "NO", 1, None, 1, None, None),
        (
            "dbo",
            "t",
            "at",
            "datetime2",
            None,
            None,
            None,
            "YES",
            2,
            "(getdate())",
            0,
            None,
            3,
        ),
        (
            "dbo",
            "t",
            "code",
            "varchar",
            10,
            None,
            None,
            "YES",
            3,
            None,
            0,
            "Latin1_General_CS_AS",
            None,
        ),
    ]

    (table,) = introspector.build_snapshot("p", rows).tables

    by_name = {c.name: c for c in table.columns}
    assert by_name["id"].is_identity is True
    assert by_name["at"].default_expression == "(getdate())"
    assert by_name["at"].datetime_precision == 3
    assert by_name["code"].collation == "Latin1_General_CS_AS"
    assert by_name["code"].is_identity is False


_COLUMNS = [
    ("dbo", "orders", "id", "int", None, 10, 0, "NO", 1),
    ("dbo", "orders", "customer_id", "int", None, 10, 0, "NO", 2),
    ("dbo", "customers", "id", "int", None, 10, 0, "NO", 1),
]


def _table(snapshot, name):
    return next(t for t in snapshot.tables if t.table_name == name)


def test_primary_key_keeps_explicit_name_and_key_order() -> None:
    rows = [
        ("dbo", "orders", "PK_orders", 0, "customer_id", 2),
        ("dbo", "orders", "PK_orders", 0, "id", 1),
    ]
    # The catalog returns them ordered by key_ordinal; the builder trusts it.
    rows.sort(key=lambda r: r[5])

    snapshot = introspector.build_snapshot("p", _COLUMNS, primary_key_rows=rows)

    pk = _table(snapshot, "orders").primary_key
    assert (pk.name, pk.columns) == ("PK_orders", ("id", "customer_id"))
    assert _table(snapshot, "customers").primary_key is None


def test_system_named_primary_keys_are_equal_across_databases() -> None:
    def pk_of(suffix: str):
        rows = [("dbo", "orders", f"PK__orders__{suffix}", 1, "id", 1)]
        snapshot = introspector.build_snapshot("p", _COLUMNS, primary_key_rows=rows)
        return _table(snapshot, "orders").primary_key

    assert pk_of("3213E83F") == pk_of("9A1B22C4")
    assert pk_of("3213E83F").name == introspector.AUTO_PRIMARY_KEY_NAME


def test_foreign_key_collects_columns_actions_and_names_system_ones_by_structure() -> (
    None
):
    rows = [
        # (schema, table, name, system, ref schema, ref table, column,
        #  ref column, ordinal, on delete, on update)
        (
            "dbo",
            "orders",
            "FK_orders_customers",
            0,
            "dbo",
            "customers",
            "customer_id",
            "id",
            1,
            "CASCADE",
            "NO_ACTION",
        ),
        (
            "dbo",
            "orders",
            "FK__orders__cust__5CD6CB2B",
            1,
            "dbo",
            "customers",
            "customer_id",
            "id",
            1,
            "NO_ACTION",
            "NO_ACTION",
        ),
        (
            "dbo",
            "orders",
            "FK__orders__cust__5CD6CB2B",
            1,
            "dbo",
            "customers",
            "id",
            "id",
            2,
            "NO_ACTION",
            "NO_ACTION",
        ),
    ]

    snapshot = introspector.build_snapshot("p", _COLUMNS, foreign_key_rows=rows)

    auto, named = sorted(_table(snapshot, "orders").foreign_keys, key=lambda f: f.name)
    assert auto.name == "FK (customer_id, id) -> dbo.customers (id, id)"
    assert auto.columns == ("customer_id", "id")
    assert named.name == "FK_orders_customers"
    assert (named.on_delete, named.on_update) == ("CASCADE", "NO ACTION")
    assert (named.referenced_schema, named.referenced_table) == ("dbo", "customers")
    assert named.referenced_columns == ("id",)


def test_index_keeps_order_included_columns_clustering_and_filter() -> None:
    rows = [
        # (schema, table, name, unique, type, filter, system, column,
        #  key ordinal, descending, included)
        ("dbo", "orders", "IX_orders_c", 1, 2, "([id]>(0))", 0, "customer_id", 1, 0, 0),
        ("dbo", "orders", "IX_orders_c", 1, 2, "([id]>(0))", 0, "id", 2, 1, 0),
        ("dbo", "orders", "IX_orders_c", 1, 2, "([id]>(0))", 0, "total", 0, 0, 1),
        ("dbo", "orders", "CIX_orders", 0, 1, None, 0, "id", 1, 0, 0),
    ]

    snapshot = introspector.build_snapshot("p", _COLUMNS, index_rows=rows)

    clustered, nonclustered = _table(snapshot, "orders").indexes
    assert clustered.name == "CIX_orders" and clustered.is_clustered
    assert nonclustered.columns == ("customer_id", "id")
    assert nonclustered.descending_columns == ("id",)
    assert nonclustered.included_columns == ("total",)
    assert nonclustered.filter_expression == "([id]>(0))"
    assert nonclustered.is_unique and not nonclustered.is_clustered


def test_system_named_unique_constraints_are_named_by_their_columns() -> None:
    rows = [
        ("dbo", "orders", "UQ__orders__A1B2C3D4", 1, 2, None, 1, "id", 1, 0, 0),
        # Same columns again: the second one must not collide with the first.
        ("dbo", "orders", "UQ__orders__E5F6A7B8", 1, 2, None, 1, "id", 1, 0, 0),
    ]

    snapshot = introspector.build_snapshot("p", _COLUMNS, index_rows=rows)

    assert [i.name for i in _table(snapshot, "orders").indexes] == [
        "UQ (id)",
        "UQ (id) #2",
    ]


def test_tables_without_keys_keep_the_empty_defaults() -> None:
    (orders, customers) = [
        _table(introspector.build_snapshot("p", _COLUMNS), n)
        for n in ("orders", "customers")
    ]

    for table in (orders, customers):
        assert table.primary_key is None
        assert table.foreign_keys == () and table.indexes == ()


def test_a_failing_key_query_aborts_instead_of_reporting_no_keys() -> None:
    profile = ConnectionProfile(name="p", connection_string=_SENTINEL)
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    cursor.execute.side_effect = lambda sql: (
        (_ for _ in ()).throw(pyodbc.Error("42000", "boom"))
        if sql == introspector.FOREIGN_KEYS_QUERY_SQL
        else None
    )
    conn = MagicMock()
    conn.cursor.return_value = cursor

    with patch(_CONNECT) as mock_connect:
        mock_connect.return_value.__enter__.return_value = conn
        with pytest.raises(Exception) as exc_info:
            SqlServerProvider().introspect(profile)

    assert _SENTINEL not in str(exc_info.value)


def test_key_queries_are_read_only_catalog_selects() -> None:
    for sql in (
        introspector.PRIMARY_KEYS_QUERY_SQL,
        introspector.FOREIGN_KEYS_QUERY_SQL,
        introspector.INDEXES_QUERY_SQL,
    ):
        assert sql.lstrip().upper().startswith("SELECT")
        assert "sys." in sql
