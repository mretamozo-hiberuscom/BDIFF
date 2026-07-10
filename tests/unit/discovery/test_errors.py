"""Unit tests for discovery.errors: SQLSTATE translation matrix."""

import pytest

from schema_comparator.discovery.errors import (
    ConnectionFailedError,
    DriverUnavailableError,
    MetadataAccessError,
    translate_connect_error,
    translate_query_error,
)


class _FakeDriverError(Exception):
    """Stand-in for `pyodbc.Error` carrying (sqlstate, message) args."""

    def __init__(self, sqlstate: str, message: str):
        super().__init__(sqlstate, message)


@pytest.mark.parametrize(
    ("sqlstate", "expected_type"),
    [
        ("IM002", DriverUnavailableError),
        ("08001", ConnectionFailedError),
        ("HYT00", ConnectionFailedError),
    ],
)
def test_translate_connect_error_maps_sqlstate(sqlstate, expected_type) -> None:
    exc = _FakeDriverError(sqlstate, "Secret server=srv1;pwd=hunter2 driver detail")
    result = translate_connect_error("claims-service", exc)
    assert isinstance(result, expected_type)
    assert "claims-service" in str(result)
    assert sqlstate not in str(result)
    assert "hunter2" not in str(result)


@pytest.mark.parametrize(
    ("sqlstate", "expected_type"),
    [
        ("HYT01", ConnectionFailedError),
        ("08S01", ConnectionFailedError),
        ("42000", MetadataAccessError),
    ],
)
def test_translate_query_error_maps_sqlstate(sqlstate, expected_type) -> None:
    exc = _FakeDriverError(sqlstate, "Secret server=srv1;pwd=hunter2 driver detail")
    result = translate_query_error("claims-service", exc)
    assert isinstance(result, expected_type)
    assert "claims-service" in str(result)
    assert sqlstate not in str(result)
    assert "hunter2" not in str(result)
