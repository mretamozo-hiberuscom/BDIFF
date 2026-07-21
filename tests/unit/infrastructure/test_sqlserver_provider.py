"""Unit tests for SqlServerProvider."""

from unittest.mock import MagicMock, patch

import pyodbc
import pytest

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.errors import ConnectionFailedError, MetadataAccessError
from schema_comparator.infrastructure.providers.sqlserver.provider import SqlServerProvider


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
    profile = ConnectionProfile(name="test_prof", connection_string="Server=srv;Database=db;")

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("dbo", "users", "id", "int", None, 10, 0, "NO", 1),
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("schema_comparator.infrastructure.providers.sqlserver.connection.connect") as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_conn

        snapshot = provider.introspect(profile)

        assert snapshot.profile_name == "test_prof"
        assert len(snapshot.tables) == 1
        assert snapshot.tables[0].table_name == "users"
        mock_cursor.close.assert_called_once()


def test_sql_server_provider_introspect_query_error() -> None:
    provider = SqlServerProvider()
    profile = ConnectionProfile(name="test_prof", connection_string="Server=srv;Database=db;")

    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = pyodbc.Error("42000", "Permission denied")

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("schema_comparator.infrastructure.providers.sqlserver.connection.connect") as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_conn

        with pytest.raises(MetadataAccessError):
            provider.introspect(profile)

        mock_cursor.close.assert_called_once()


def test_sql_server_provider_introspect_connect_error() -> None:
    provider = SqlServerProvider()
    profile = ConnectionProfile(name="test_prof", connection_string="Server=srv;Database=db;")

    with patch("schema_comparator.infrastructure.providers.sqlserver.connection.connect") as mock_connect:
        mock_connect.side_effect = pyodbc.Error("08001", "Unable to connect")

        with pytest.raises(ConnectionFailedError):
            provider.introspect(profile)
