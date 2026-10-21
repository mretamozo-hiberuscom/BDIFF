"""Driver selection for SQL Server connection strings without `Driver=`:
ODBC Driver 17 when installed, otherwise 18; an explicit driver is never
changed, and driver errors name the installed SQL Server drivers."""

import pytest

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.errors import (
    ConnectionFailedError,
    DriverUnavailableError,
)
from schema_comparator.infrastructure.providers.sqlserver import connection
from schema_comparator.infrastructure.providers.sqlserver.errors import (
    translate_connect_error,
)

_D17 = "ODBC Driver 17 for SQL Server"
_D18 = "ODBC Driver 18 for SQL Server"
_RAW = "Server=srv;Database=Polizas;UID=SECRET_USER;PWD=SECRET_PASS;"


class _Conn:
    timeout = 0

    def close(self) -> None:
        pass


def _connected_with(raw: str, installed: list[str]) -> str:
    seen: list[str] = []

    def fake_connect(conn_str, timeout):
        seen.append(conn_str)
        return _Conn()

    profile = ConnectionProfile(name="polizas", connection_string=raw)
    with connection.connect(
        profile, connect_fn=fake_connect, drivers_fn=lambda: installed
    ):
        pass
    return seen[0]


@pytest.mark.parametrize(
    ("installed", "expected"),
    [
        ([_D17, _D18, "SQLite3"], _D17),
        ([_D17], _D17),
        ([_D18, "PostgreSQL Unicode"], _D18),
    ],
)
def test_missing_driver_uses_17_when_installed_otherwise_18(
    installed: list[str], expected: str
) -> None:
    assert _connected_with(_RAW, installed) == f"Driver={{{expected}}};{_RAW}"


def test_missing_driver_with_no_sqlserver_driver_installed_is_left_unset() -> None:
    assert _connected_with(_RAW, ["SQLite3"]) == _RAW


@pytest.mark.parametrize("keyword", ["Driver", "DRIVER", "driver"])
def test_explicit_driver_is_never_replaced(keyword: str) -> None:
    raw = f"{keyword}={{{_D17}}};{_RAW}"
    assert _connected_with(raw, [_D18]) == raw


def test_driver_18_fallback_does_not_add_encryption_options() -> None:
    result = _connected_with(_RAW, [_D18])
    assert "TrustServerCertificate" not in result
    assert "Encrypt" not in result


class _PyodbcError(Exception):
    pass


def test_driver_unavailable_error_names_installed_sqlserver_drivers() -> None:
    error = translate_connect_error(
        "polizas",
        _PyodbcError("IM002", "[unixODBC] Data source name not found"),
        connection_string=f"Driver={{{_D17}}};{_RAW}",
        installed_drivers=(_D18, "SQLite3"),
    )

    assert isinstance(error, DriverUnavailableError)
    message = str(error)
    assert "polizas" in message
    assert _D18 in message
    assert "SQLite3" not in message
    assert "SECRET" not in message


def test_driver_unavailable_error_says_when_no_sqlserver_driver_exists() -> None:
    error = translate_connect_error(
        "polizas",
        _PyodbcError("IM002", "x"),
        connection_string=_RAW,
        installed_drivers=("SQLite3",),
    )

    assert "ninguno" in str(error)


def test_connection_failure_on_driver_18_suggests_trust_server_certificate() -> None:
    error = translate_connect_error(
        "polizas",
        _PyodbcError("08001", "SSL Provider: certificate chain not trusted"),
        connection_string=_RAW,
        installed_drivers=(_D18,),
    )

    assert isinstance(error, ConnectionFailedError)
    message = str(error)
    assert "TrustServerCertificate=yes" in message
    assert "SECRET" not in message
    assert "SSL Provider" not in message


@pytest.mark.parametrize(
    ("raw", "installed"),
    [
        (_RAW, (_D17, _D18)),
        (f"{_RAW}TrustServerCertificate=yes;", (_D18,)),
    ],
)
def test_connection_failure_without_driver_18_risk_has_no_certificate_hint(
    raw: str, installed: tuple[str, ...]
) -> None:
    error = translate_connect_error(
        "polizas",
        _PyodbcError("08001", "x"),
        connection_string=raw,
        installed_drivers=installed,
    )

    assert "TrustServerCertificate" not in str(error)
