"""Rows, counts and wording of the routines screen."""

from schema_comparator.infrastructure.providers.sqlserver.repair_script import (
    CONNECTION_FAILURE_ROUTINE,
)
from schema_comparator.infrastructure.providers.sqlserver.sp_validator import (
    ModuleRefreshResult,
    RoutineIdentity,
    RoutineValidationResult,
    RoutineValidationStatus,
    SignatureStatus,
)
from schema_comparator.tui.routine_model import (
    detail_markup,
    refresh_confirmation_body,
    refresh_plan,
    refresh_rows,
    summary_markup,
    validation_rows,
)


def _validated(
    name: str,
    status: RoutineValidationStatus = RoutineValidationStatus.VALID,
    signature: SignatureStatus = SignatureStatus.UNSIGNED,
    error: str | None = None,
    routine: RoutineIdentity | None = None,
) -> RoutineValidationResult:
    return RoutineValidationResult(
        routine=routine or RoutineIdentity("dbo", name),
        status=status,
        signature_status=signature,
        error_message=error,
    )


def test_refresh_plan_counts_only_unsigned_routines_and_reports_the_rest() -> None:
    plan = refresh_plan(
        {
            "a": (
                _validated("u1"),
                _validated("u2", RoutineValidationStatus.INVALID, error="rota"),
                _validated("signed", signature=SignatureStatus.SIGNED),
                _validated("unknown", signature=SignatureStatus.UNKNOWN),
            ),
            # A profile that could not connect holds only the placeholder.
            "b": (
                _validated(
                    "",
                    RoutineValidationStatus.UNVERIFIABLE,
                    SignatureStatus.UNKNOWN,
                    "Error de conexión",
                    routine=CONNECTION_FAILURE_ROUTINE,
                ),
            ),
        }
    )

    assert plan.recompilable == 2
    assert plan.skipped == 2
    assert not plan.is_empty


def test_refresh_plan_is_empty_when_nothing_is_unsigned() -> None:
    plan = refresh_plan({"a": (_validated("s", signature=SignatureStatus.SIGNED),)})

    assert plan.is_empty
    assert plan.skipped == 1


def test_confirmation_body_names_the_real_count_and_the_skipped_ones() -> None:
    body = refresh_confirmation_body(refresh_plan({"a": (_validated("u"),)}))
    assert "[bold]1[/bold] rutina sin firma" in body
    assert "se omiten" not in body.lower()

    body = refresh_confirmation_body(
        refresh_plan(
            {
                "a": (
                    _validated("u"),
                    _validated("v"),
                    _validated("s", signature=SignatureStatus.SIGNED),
                )
            }
        )
    )
    assert "[bold]2[/bold] rutinas sin firma" in body
    assert "Se omiten 1 firmadas" in body


def test_validation_rows_mark_each_status_and_keep_the_detail() -> None:
    rows = validation_rows(
        {
            "a": (
                _validated("ok"),
                _validated("bad", RoutineValidationStatus.INVALID, error="Falta [t]"),
                _validated("unk", RoutineValidationStatus.UNVERIFIABLE),
            )
        }
    )

    by_name = {row.name: row for row in rows}
    assert not by_name["ok"].is_problem and by_name["ok"].detail == ""
    assert by_name["bad"].is_problem and by_name["bad"].detail == "Falta [t]"
    assert by_name["unk"].is_problem and by_name["unk"].detail == "Error desconocido"
    assert {row.symbol for row in rows} == {"✔", "✖", "!"}


def test_connection_failure_row_is_flagged_and_not_a_routine() -> None:
    rows = validation_rows(
        {
            "b": (
                _validated(
                    "",
                    RoutineValidationStatus.UNVERIFIABLE,
                    SignatureStatus.UNKNOWN,
                    "Error de conexión: sin red",
                    routine=CONNECTION_FAILURE_ROUTINE,
                ),
            )
        }
    )

    assert rows[0].is_connection_failure
    assert rows[0].state == "Sin conexión"
    summary = summary_markup(rows, recompiled=False)
    assert "1[/] perfil sin conexión" in summary
    assert "✔ 0" in summary


def test_refresh_rows_report_failures_with_their_message() -> None:
    rows = refresh_rows(
        {
            "a": (
                ModuleRefreshResult.success(RoutineIdentity("dbo", "p")),
                ModuleRefreshResult.failure(
                    RoutineIdentity("dbo", "q"), error_message="Permiso denegado"
                ),
            )
        }
    )

    assert [row.is_problem for row in rows] == [False, True]
    assert rows[1].detail == "Permiso denegado"
    summary = summary_markup(rows, recompiled=True)
    assert "recompiladas" in summary and "con fallo" in summary


def test_summary_without_rows_is_neutral() -> None:
    assert "Sin rutinas" in summary_markup([], recompiled=False)


def test_detail_escapes_markup_from_names_and_messages() -> None:
    rows = validation_rows(
        {
            "a": (
                _validated(
                    "p[red]", RoutineValidationStatus.INVALID, error="Falta [dbo].[t]"
                ),
            )
        }
    )

    markup = detail_markup(rows[0])

    assert "p\\[red]" in markup
    assert "Falta \\[dbo].\\[t]" in markup
    assert "Selecciona una rutina" in detail_markup(None)
