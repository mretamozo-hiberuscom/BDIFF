"""Error messages never carry driver free text (host, user, server): only
the profile name, a driver error code, or the exception type."""

import contextlib
import io
from unittest.mock import patch

import pyodbc
import pytest

from schema_comparator.cli import _run_routine_validation, main
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.errors import (
    ConnectionFailedError,
    DriverUnavailableError,
    MetadataAccessError,
)
from schema_comparator.domain.errors import describe_error
from schema_comparator.infrastructure.providers import registry
from schema_comparator.infrastructure.providers.mysql_family import (
    errors as mysql_errors,
)
from schema_comparator.infrastructure.providers.oracle import errors as oracle_errors

_SECRET = "app_user'@'10.0.0.5"


class _OracleError:
    full_code = "ORA-01017"

    def __str__(self) -> str:
        return f"ORA-01017: invalid credential for {_SECRET}"


@pytest.mark.parametrize(
    ("translate", "exc", "code", "expected"),
    [
        (
            mysql_errors.translate_connect_error,
            Exception(1045, f"Access denied for user {_SECRET}"),
            "1045",
            ConnectionFailedError,
        ),
        (
            mysql_errors.translate_query_error,
            Exception(1142, f"SELECT denied to user {_SECRET}"),
            "1142",
            MetadataAccessError,
        ),
        (
            oracle_errors.translate_connect_error,
            Exception(_OracleError()),
            "ORA-01017",
            ConnectionFailedError,
        ),
        (
            oracle_errors.translate_query_error,
            Exception(_OracleError()),
            "ORA-01017",
            MetadataAccessError,
        ),
    ],
)
def test_driver_errors_keep_profile_and_code_but_drop_free_text(
    translate, exc, code, expected
) -> None:
    error = translate("polizas", exc)

    assert isinstance(error, expected)
    message = str(error)
    assert "polizas" in message
    assert code in message
    assert _SECRET not in message


@pytest.mark.parametrize(
    ("translate", "extra"),
    [
        (mysql_errors.translate_connect_error, "mysql"),
        (oracle_errors.translate_connect_error, "oracle"),
    ],
)
def test_missing_python_driver_names_the_package_extra(translate, extra) -> None:
    error = translate("polizas", ImportError("No module named 'x'"))

    assert isinstance(error, DriverUnavailableError)
    assert f"pip install schema-comparator[{extra}]" in str(error)


def test_registry_install_hint_uses_the_package_name() -> None:
    reg = registry.ProviderRegistry()

    def _broken_factory():
        raise ImportError("No module named 'psycopg'")

    reg.register_factory("postgresql", _broken_factory)

    with pytest.raises(DriverUnavailableError) as exc_info:
        reg.get("postgresql")

    assert "pip install schema-comparator[postgresql]" in str(exc_info.value)
    assert "bdiff[" not in str(exc_info.value)


def test_describe_error_shows_only_the_type_of_unexpected_errors() -> None:
    assert describe_error(RuntimeError(f"Server=srv;UID={_SECRET}")) == "RuntimeError"
    assert describe_error(ConnectionFailedError.for_profile("dev")).startswith(
        "La extracción de esquema para 'dev'"
    )


def test_cli_unexpected_error_prints_only_its_type(capsys) -> None:
    with (
        patch("schema_comparator.cli.load_profiles", return_value=[]),
        patch(
            "schema_comparator.cli.run_comparison",
            side_effect=RuntimeError(f"Server=srv;UID={_SECRET}"),
        ),
    ):
        code = main(["--config", "c.yaml"])

    assert code == 2
    err = capsys.readouterr().err
    assert "[ERROR INESPERADO] RuntimeError" in err
    assert _SECRET not in err


def test_routine_validation_connection_failure_hides_driver_text() -> None:
    profiles = [ConnectionProfile(name="dev", connection_string="Server=srv;")]
    out = io.StringIO()
    with (
        patch(
            "schema_comparator.infrastructure.providers.sqlserver.connection.connect",
            side_effect=pyodbc.Error("28000", f"Login failed for user {_SECRET}"),
        ),
        contextlib.redirect_stdout(out),
    ):
        failed = _run_routine_validation(profiles, read_only=True)

    assert failed is True
    output = out.getvalue()
    assert "Perfil 'dev'" in output
    assert _SECRET not in output


def test_sqlserver_describe_failure_translates_pyodbc_errors() -> None:
    from schema_comparator.infrastructure.providers.sqlserver.errors import (
        describe_failure,
    )

    profile = ConnectionProfile(name="dev", connection_string="Server=srv;")
    message = describe_failure(
        profile, pyodbc.Error("08001", f"Login failed for user {_SECRET}")
    )

    assert "dev" in message
    assert _SECRET not in message
    assert describe_failure(profile, ValueError(_SECRET)) == "ValueError"
