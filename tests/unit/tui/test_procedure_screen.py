"""Unit tests for ProcedureVerificationScreen and procedure TUI components."""

from pathlib import Path
from unittest.mock import patch

import pytest
from textual.app import App
from textual.widgets import Button, DataTable, Static

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.schema.models import ProcedureSnapshot, ParameterSnapshot
from schema_comparator.domain.comparison.models import (
    MissingProcedure,
    ProcedureMismatch,
)
from schema_comparator.infrastructure.providers.sqlserver.routine_runner import (
    RoutineRun,
)
from schema_comparator.infrastructure.providers.sqlserver.sp_validator import (
    ModuleRefreshResult,
    RoutineIdentity,
    RoutineValidationResult,
    RoutineValidationStatus,
    SignatureStatus,
    clean_sql_error_message,
    refresh_modules_mutating,
)
from schema_comparator.tui.modals import ConfirmModal, HelpModal
from schema_comparator.tui.formatting import leaf_label, detail_text, entry_matches
from schema_comparator.tui.procedure_screen import ProcedureVerificationScreen


def test_tui_formatting_missing_procedure_label_and_detail():
    entry = MissingProcedure(
        schema_name="dbo",
        procedure_name="sp_CalculateRisk",
        missing_from_profile="Profile2",
        present_procedures=(
            (
                "Profile1",
                ProcedureSnapshot(
                    "dbo",
                    "sp_CalculateRisk",
                    parameters=(ParameterSnapshot("@UserId", "int"),),
                ),
            ),
        ),
    )

    label = leaf_label(entry)
    detail = detail_text(entry)

    assert "sp_CalculateRisk" in label
    assert "rutina/SP faltante (de Profile2)" in label
    assert "dbo.sp_CalculateRisk" in detail
    assert "Faltante en el perfil 'Profile2'" in detail
    assert "Profile1: PROCEDURE (@UserId int)" in detail


def test_tui_formatting_procedure_mismatch_label_and_detail():
    entry = ProcedureMismatch(
        schema_name="dbo",
        procedure_name="sp_UpdateStatus",
        values_by_profile=(
            (
                "Profile1",
                ProcedureSnapshot("dbo", "sp_UpdateStatus", definition_hash="hash1"),
            ),
            (
                "Profile2",
                ProcedureSnapshot("dbo", "sp_UpdateStatus", definition_hash="hash2"),
            ),
        ),
    )

    label = leaf_label(entry)
    detail = detail_text(entry)

    assert "sp_UpdateStatus" in label
    assert "discrepancia de código o parámetros entre Profile1, Profile2" in label
    assert "dbo.sp_UpdateStatus" in detail
    assert "Profile1: PROCEDURE | Params: [sin parámetros] | Hash: hash1" in detail


def test_tui_entry_matches_procedure_and_spanish_keywords():
    entry = MissingProcedure(
        schema_name="dbo",
        procedure_name="sp_SyncPolicy",
        missing_from_profile="Profile2",
    )

    assert entry_matches(entry, "SyncPolicy") is True
    assert entry_matches(entry, "sp_sync") is True
    assert entry_matches(entry, "rutina") is True
    assert entry_matches(entry, "OtherProc") is False


def test_procedure_verification_screen_init(tmp_path: Path):
    prof = ConnectionProfile(
        name="test_prof", connection_string="Server=localhost;Database=db;"
    )
    screen = ProcedureVerificationScreen(
        profiles=(prof,),
        repo_root=tmp_path,
        exclude_patterns=["temp"],
    )

    assert screen._profiles == (prof,)
    assert screen._repo_root == tmp_path
    assert screen._exclude_patterns == ["temp"]


def test_action_generate_script_escapes_single_quotes_and_skips_signed_and_placeholders(
    tmp_path: Path,
):
    prof = ConnectionProfile(
        name="test_prof", connection_string="Server=localhost;Database=db;"
    )
    screen = ProcedureVerificationScreen(
        profiles=(prof,),
        repo_root=tmp_path,
    )
    routine_normal = RoutineIdentity("dbo", "sp_user's_proc")
    routine_signed = RoutineIdentity("dbo", "sp_signed_proc")
    routine_system = RoutineIdentity("SYSTEM", "CONNECT")

    screen._validation_results = {
        "test_prof": (
            RoutineValidationResult(
                routine=routine_normal,
                status=RoutineValidationStatus.VALID,
                signature_status=SignatureStatus.UNSIGNED,
            ),
            RoutineValidationResult(
                routine=routine_signed,
                status=RoutineValidationStatus.VALID,
                signature_status=SignatureStatus.SIGNED,
            ),
            RoutineValidationResult(
                routine=routine_system,
                status=RoutineValidationStatus.UNVERIFIABLE,
                signature_status=SignatureStatus.UNKNOWN,
            ),
        )
    }

    screen.action_generate_script()

    script_files = list((tmp_path / "scripts-db").glob("*/repair_sps.sql"))
    assert len(script_files) == 1
    content = script_files[0].read_text(encoding="utf-8")

    assert "N'[dbo].[sp_user''s_proc]'" in content
    assert "OMITIDO (Firmado): [dbo].[sp_signed_proc]" in content
    assert "[SYSTEM].[CONNECT]" not in content
    assert "BEGIN TRY" in content
    assert "BEGIN CATCH" in content
    assert "#RefreshSummary" in content
    assert "[OK]" in content

    # Check profile-specific script file inside repair_sps/ subfolder
    profile_script_files = list(
        (tmp_path / "scripts-db").glob("*/repair_sps/test_prof.sql")
    )
    assert len(profile_script_files) == 1
    prof_content = profile_script_files[0].read_text(encoding="utf-8")
    assert "INICIANDO RECOMPILACIÓN DE RUTINAS EN PERFIL: test_prof" in prof_content
    assert "BEGIN TRY" in prof_content
    assert "#RefreshSummary" in prof_content


def test_clean_sql_error_message():
    raw_pyodbc = (
        "('42000', \"[42000] [Microsoft][ODBC Driver 17 for SQL Server][SQL Server] "
        "Invalid column name 'Codigo'. (207) (SQLExecDirectW)\")"
    )
    cleaned = clean_sql_error_message(raw_pyodbc)
    assert cleaned == "Invalid column name 'Codigo'. (Error 207)"

    simple_err = "Dependencias con referencias no resueltas: dbo.TablaInexistente"
    assert clean_sql_error_message(simple_err) == simple_err
    assert clean_sql_error_message(None) == "Error desconocido"


# -- routines screen, driven through the real app ---------------------------


class _Host(App):
    def __init__(self, screen: ProcedureVerificationScreen) -> None:
        super().__init__()
        self._screen = screen

    def on_mount(self) -> None:
        self.push_screen(self._screen)


def _screen(tmp_path: Path) -> ProcedureVerificationScreen:
    prof = ConnectionProfile(name="p1", connection_string="Server=x;Database=db;")
    return ProcedureVerificationScreen(profiles=(prof,), repo_root=tmp_path)


def _validation_run(*results: RoutineValidationResult) -> dict[str, RoutineRun]:
    return {"p1": RoutineRun(results=results)}


_UNSIGNED = RoutineValidationResult(
    routine=RoutineIdentity("dbo", "p_unsigned"),
    status=RoutineValidationStatus.INVALID,
    signature_status=SignatureStatus.UNSIGNED,
    error_message="Falta [dbo].[t]",
)
_SIGNED = RoutineValidationResult(
    routine=RoutineIdentity("dbo", "p_signed"),
    status=RoutineValidationStatus.VALID,
    signature_status=SignatureStatus.SIGNED,
)


@pytest.mark.asyncio
async def test_screen_validates_on_open_and_shows_summary_and_detail(tmp_path: Path):
    screen = _screen(tmp_path)
    with patch(
        "schema_comparator.tui.procedure_screen.run_routines",
        return_value=_validation_run(_UNSIGNED, _SIGNED),
    ):
        async with _Host(screen).run_test() as pilot:
            await screen.workers.wait_for_complete()
            await pilot.pause()

            table = screen.query_one(DataTable)
            assert table.row_count == 2
            header = str(screen.query_one("#routines-header", Static).render())
            assert "✔ 1" in header and "✖ 1" in header
            # The first row is selected and its detail is shown.
            detail = str(screen.query_one("#routine-detail", Static).render())
            assert "p_unsigned" in detail and "Falta [dbo].[t]" in detail


@pytest.mark.asyncio
async def test_recompile_asks_with_real_count_and_cancel_is_the_default(
    tmp_path: Path,
):
    screen = _screen(tmp_path)
    with patch(
        "schema_comparator.tui.procedure_screen.run_routines",
        return_value=_validation_run(_UNSIGNED, _SIGNED),
    ) as m_run:
        async with _Host(screen).run_test() as pilot:
            await screen.workers.wait_for_complete()
            await pilot.pause()
            m_run.reset_mock()

            await pilot.press("r")
            await pilot.pause()

            modal = screen.app.screen
            assert isinstance(modal, ConfirmModal)
            body = str(modal.query_one("#confirm-body", Static).render())
            assert "1 rutina sin firma" in body
            assert "Se omiten 1 firmadas" in body
            assert modal.query_one("#btn-cancel", Button).has_focus

            # Enter on the default button cancels: nothing is written.
            await pilot.press("enter")
            await pilot.pause()
            assert not isinstance(screen.app.screen, ConfirmModal)
            m_run.assert_not_called()
            assert screen._refresh_results == {}


@pytest.mark.asyncio
async def test_recompile_runs_only_after_explicit_confirmation(tmp_path: Path):
    screen = _screen(tmp_path)
    refreshed = {
        "p1": RoutineRun(
            results=(ModuleRefreshResult.success(RoutineIdentity("dbo", "p_unsigned")),)
        )
    }
    with patch(
        "schema_comparator.tui.procedure_screen.run_routines",
        return_value=_validation_run(_UNSIGNED),
    ) as m_run:
        async with _Host(screen).run_test() as pilot:
            await screen.workers.wait_for_complete()
            await pilot.pause()

            m_run.return_value = refreshed
            await pilot.press("r")
            await pilot.pause()
            await pilot.press("y")
            await screen.workers.wait_for_complete()
            await pilot.pause()

            assert m_run.call_args.args[2] is refresh_modules_mutating
            assert "p1" in screen._refresh_results
            assert "recompiladas" in str(
                screen.query_one("#routines-header", Static).render()
            )


@pytest.mark.asyncio
async def test_recompile_without_validation_or_unsigned_routines_does_not_ask(
    tmp_path: Path,
):
    screen = _screen(tmp_path)
    with patch(
        "schema_comparator.tui.procedure_screen.run_routines",
        return_value=_validation_run(_SIGNED),
    ):
        async with _Host(screen).run_test() as pilot:
            await screen.workers.wait_for_complete()
            await pilot.pause()

            await pilot.press("r")
            await pilot.pause()

            assert not isinstance(screen.app.screen, ConfirmModal)
            assert "No hay rutinas sin firma" in str(
                screen.query_one("#sp-status", Static).render()
            )


@pytest.mark.asyncio
async def test_help_opens_with_the_routines_card_and_esc_returns(tmp_path: Path):
    screen = _screen(tmp_path)
    with patch(
        "schema_comparator.tui.procedure_screen.run_routines",
        return_value=_validation_run(),
    ):
        async with _Host(screen).run_test() as pilot:
            await screen.workers.wait_for_complete()
            await pilot.pause()

            await pilot.press("question_mark")
            await pilot.pause()
            assert isinstance(screen.app.screen, HelpModal)
            await pilot.press("escape")
            await pilot.pause()
            assert screen.app.screen is screen


@pytest.mark.asyncio
async def test_script_message_shows_where_it_was_saved_without_running_anything(
    tmp_path: Path,
):
    screen = _screen(tmp_path)
    with patch(
        "schema_comparator.tui.procedure_screen.run_routines",
        return_value=_validation_run(_UNSIGNED),
    ):
        async with _Host(screen).run_test() as pilot:
            await screen.workers.wait_for_complete()
            await pilot.pause()

            await pilot.press("s")
            await pilot.pause()

            status = str(screen.query_one("#sp-status", Static).render())
            assert "Script guardado en scripts-db/" in status
            assert list((tmp_path / "scripts-db").glob("*/repair_sps.sql"))
