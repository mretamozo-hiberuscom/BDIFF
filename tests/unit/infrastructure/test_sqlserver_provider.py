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
    mock_cursor.fetchall.return_value = [
        ("dbo", "users", "id", "int", None, 10, 0, "NO", 1),
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
        introspector.PROCEDURES_QUERY_SQL,
    ]
    for sql in executed:
        for write_keyword in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER "):
            assert write_keyword not in sql.upper()
