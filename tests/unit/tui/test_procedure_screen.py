"""Unit tests for ProcedureVerificationScreen and procedure TUI components."""

from pathlib import Path
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.schema.models import ProcedureSnapshot, ParameterSnapshot
from schema_comparator.domain.comparison.models import (
    MissingProcedure,
    ProcedureMismatch,
)
from schema_comparator.infrastructure.providers.sqlserver.sp_validator import (
    RoutineIdentity,
    RoutineValidationResult,
    RoutineValidationStatus,
    SignatureStatus,
    clean_sql_error_message,
)
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

    # Check profile-specific script file inside repair_sps/ subfolder
    profile_script_files = list(
        (tmp_path / "scripts-db").glob("*/repair_sps/test_prof.sql")
    )
    assert len(profile_script_files) == 1
    prof_content = profile_script_files[0].read_text(encoding="utf-8")
    assert "INICIANDO RECOMPILACIÓN DE RUTINAS EN PERFIL: test_prof" in prof_content
    assert "BEGIN TRY" in prof_content


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
