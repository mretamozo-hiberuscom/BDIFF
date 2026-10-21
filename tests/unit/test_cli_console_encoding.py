"""Console output must survive a Windows code page (cp1252) when stdout is
redirected: no emoji in CLI messages, and unencodable identifiers are
replaced instead of aborting the run."""

import contextlib
import io
import sys
from unittest.mock import MagicMock, patch

from schema_comparator.cli import _run_routine_validation, main
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.infrastructure.providers.sqlserver.sp_validator import (
    RoutineIdentity,
    RoutineValidationResult,
    RoutineValidationStatus,
    SignatureStatus,
)

_SP_VALIDATOR = "schema_comparator.infrastructure.providers.sqlserver.sp_validator"


def _cp1252_stream() -> io.TextIOWrapper:
    return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")


def _result(name: str, status: RoutineValidationStatus) -> RoutineValidationResult:
    return RoutineValidationResult(
        routine=RoutineIdentity(schema_name="dbo", object_name=name),
        status=status,
        signature_status=SignatureStatus.UNSIGNED,
        error_message="Invalid object name" if status != "valid" else None,
    )


def _run_validation(results: list[RoutineValidationResult]) -> str:
    profiles = [ConnectionProfile(name="dev", connection_string="DSN=dev")]
    out = io.StringIO()
    with (
        patch(
            "schema_comparator.infrastructure.providers.sqlserver.connection.connect",
            return_value=contextlib.nullcontext(MagicMock()),
        ),
        patch(f"{_SP_VALIDATOR}.enumerate_routines", return_value=()),
        patch(f"{_SP_VALIDATOR}.validate_routines_read_only", return_value=results),
        contextlib.redirect_stdout(out),
    ):
        _run_routine_validation(profiles, read_only=True)
    return out.getvalue()


def test_routine_validation_failures_print_cp1252_safe_prefixes() -> None:
    output = _run_validation(
        [
            _result("usp_ok", RoutineValidationStatus.VALID),
            _result("usp_broken", RoutineValidationStatus.INVALID),
        ]
    )

    output.encode("cp1252")
    assert "[ERROR] Perfil 'dev': 1 objeto(s) con fallos:" in output
    assert "[dbo].[usp_broken]: Invalid object name" in output


def test_routine_validation_success_prints_cp1252_safe_prefix() -> None:
    output = _run_validation([_result("usp_ok", RoutineValidationStatus.VALID)])

    output.encode("cp1252")
    assert "[OK] Perfil 'dev'" in output


def test_refresh_without_yes_warning_is_cp1252_safe() -> None:
    stderr = _cp1252_stream()
    fake_result = MagicMock(entries=())
    with (
        patch("schema_comparator.cli.load_profiles", return_value=[]),
        patch("schema_comparator.cli.run_comparison", return_value=fake_result),
        patch("schema_comparator.cli.write_reports"),
        patch.object(sys, "stderr", stderr),
    ):
        code = main(["--config", "c.yaml", "--refresh-modules"])

    stderr.seek(0)
    assert code == 1
    assert "[AVISO] ATENCIÓN: --refresh-modules" in stderr.read()


def test_unencodable_identifier_is_replaced_instead_of_aborting() -> None:
    stdout = _cp1252_stream()
    fake_result = MagicMock(entries=())

    def print_identifier(result, **_kwargs):
        print("Tabla dbo.客户 FALTA")

    with (
        patch("schema_comparator.cli.load_profiles", return_value=[]),
        patch("schema_comparator.cli.run_comparison", return_value=fake_result),
        patch("schema_comparator.cli.write_reports", side_effect=print_identifier),
        patch.object(sys, "stdout", stdout),
    ):
        code = main(["--config", "c.yaml"])

    stdout.seek(0)
    assert code == 0
    assert "Tabla dbo.?? FALTA" in stdout.read()
