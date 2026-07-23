"""Unit tests for discovery.service.extract_schema."""

import pyodbc
import pytest
from discovery.conftest import fake_connect_fn

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.errors import (
    ConnectionFailedError,
    DriverUnavailableError,
    MetadataAccessError,
)
from schema_comparator.discovery.queries import CATALOG_QUERY_SQL, PROCEDURES_QUERY_SQL

from schema_comparator.discovery.service import extract_schema

_PROFILE = ConnectionProfile(name="claims-service", connection_string="SECRET-SENTINEL-VALUE")

_ROWS = [
    ("sales", "Invoice", "id", "int", None, 10, 0, "NO", 1),
]


def test_extract_schema_happy_path_returns_snapshot() -> None:
    connect_fn = fake_connect_fn(rows=_ROWS)

    snapshot = extract_schema(_PROFILE, connect_fn=connect_fn)

    assert snapshot.profile_name == "claims-service"
    assert len(snapshot.tables) == 1
    assert snapshot.tables[0].qualified_name == ("sales", "Invoice")


def test_successful_extraction_executes_only_the_catalog_query() -> None:
    connect_fn = fake_connect_fn(rows=_ROWS)

    extract_schema(_PROFILE, connect_fn=connect_fn)

    connection = connect_fn.connection_holder["connection"]
    assert connection.last_cursor.executed_sql in (CATALOG_QUERY_SQL, PROCEDURES_QUERY_SQL)
    for write_keyword in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"):
        assert write_keyword not in connection.last_cursor.executed_sql.upper()



def test_failure_still_releases_extraction_resources() -> None:
    connect_fn = fake_connect_fn(rows=_ROWS, execute_error=pyodbc.Error("42000", "denied"))

    with pytest.raises(MetadataAccessError):
        extract_schema(_PROFILE, connect_fn=connect_fn)

    connection = connect_fn.connection_holder["connection"]
    assert connection.last_cursor.closed is True
    assert connection.closed is True


def test_connection_failure_is_safely_translated() -> None:
    connect_fn = fake_connect_fn(raise_on_connect=pyodbc.Error("08001", "unreachable"))

    with pytest.raises(ConnectionFailedError) as exc_info:
        extract_schema(_PROFILE, connect_fn=connect_fn)

    assert "claims-service" in str(exc_info.value)


def test_connection_timeout_is_safely_translated() -> None:
    connect_fn = fake_connect_fn(raise_on_connect=pyodbc.Error("HYT00", "login timeout"))

    with pytest.raises(ConnectionFailedError):
        extract_schema(_PROFILE, connect_fn=connect_fn)


def test_query_timeout_is_safely_translated() -> None:
    connect_fn = fake_connect_fn(rows=_ROWS, execute_error=pyodbc.Error("HYT01", "query timeout"))

    with pytest.raises(ConnectionFailedError):
        extract_schema(_PROFILE, connect_fn=connect_fn)


def test_driver_unavailable_is_safely_translated() -> None:
    connect_fn = fake_connect_fn(raise_on_connect=pyodbc.Error("IM002", "driver not found"))

    with pytest.raises(DriverUnavailableError):
        extract_schema(_PROFILE, connect_fn=connect_fn)


def test_no_secret_leaks_in_any_translated_error() -> None:
    sentinel = "SECRET-SENTINEL-VALUE"
    scenarios = [
        fake_connect_fn(raise_on_connect=pyodbc.Error("08001", f"conn={sentinel}")),
        fake_connect_fn(rows=_ROWS, execute_error=pyodbc.Error("42000", f"conn={sentinel}")),
    ]

    for connect_fn in scenarios:
        with pytest.raises(Exception) as exc_info:
            extract_schema(_PROFILE, connect_fn=connect_fn)
        assert sentinel not in str(exc_info.value)
