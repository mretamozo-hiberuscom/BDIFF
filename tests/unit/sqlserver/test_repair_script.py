"""Repair scripts that recompile routine metadata: every profile block
selects its database and creates the summary table it uses, so the master
script runs as a whole; names are escaped for T-SQL."""

import datetime

from schema_comparator.infrastructure.providers.sqlserver.repair_script import (
    CONNECTION_FAILURE_ROUTINE,
    render_repair_scripts,
)
from schema_comparator.infrastructure.providers.sqlserver.sp_validator import (
    RoutineIdentity,
    RoutineValidationResult,
    RoutineValidationStatus,
    SignatureStatus,
)

_TS = datetime.datetime(2026, 10, 21, 12, 0, 0)


def _result(schema, name, signature=SignatureStatus.UNSIGNED):
    return RoutineValidationResult(
        routine=RoutineIdentity(schema, name),
        status=RoutineValidationStatus.INVALID,
        signature_status=signature,
    )


def _render(results, databases):
    return render_repair_scripts(results, databases, _TS)


def test_master_script_uses_and_creates_summary_table_per_profile() -> None:
    scripts = _render(
        {"dev": [_result("dbo", "usp_a")], "qa": [_result("dbo", "usp_b")]},
        {"dev": "PolizasDev", "qa": "PolizasQa"},
    )

    master = scripts.master
    assert master.count("CREATE TABLE #RefreshSummary") == 2
    assert master.splitlines().count("DROP TABLE #RefreshSummary;") == 2
    use_dev = master.index("USE [PolizasDev];")
    use_qa = master.index("USE [PolizasQa];")
    assert use_dev < master.index("usp_a") < use_qa < master.index("usp_b")
    for block in master.split("USE [")[1:]:
        assert block.index("CREATE TABLE #RefreshSummary") < block.index(
            "INSERT INTO #RefreshSummary"
        )


def test_profile_script_selects_its_database() -> None:
    scripts = _render({"dev": [_result("dbo", "usp_a")]}, {"dev": "PolizasDev"})

    assert "USE [PolizasDev];" in scripts.per_profile["dev"]


def test_unknown_database_warns_instead_of_guessing() -> None:
    scripts = _render({"dev": [_result("dbo", "usp_a")]}, {"dev": None})

    assert "USE [" not in scripts.per_profile["dev"]
    assert "AVISO" in scripts.per_profile["dev"]


def test_names_are_escaped_for_tsql() -> None:
    scripts = _render(
        {"O'Brien": [_result("dbo", "usp_a]b"), _result("dbo", "usp_o'k")]},
        {"O'Brien": "Db]X"},
    )

    script = scripts.per_profile["O'Brien"]
    assert "USE [Db]]X];" in script
    assert "@name = N'[dbo].[usp_a]]b]'" in script
    assert "@name = N'[dbo].[usp_o''k]'" in script
    assert "PERFIL: O''Brien" in script


def test_only_the_connection_failure_placeholder_is_skipped() -> None:
    placeholder = RoutineValidationResult(
        routine=CONNECTION_FAILURE_ROUTINE,
        status=RoutineValidationStatus.UNVERIFIABLE,
        signature_status=SignatureStatus.UNKNOWN,
    )
    scripts = _render(
        {"dev": [placeholder, _result("dbo", "CONNECT"), _result("SYSTEM", "usp_x")]},
        {"dev": "Db"},
    )

    script = scripts.per_profile["dev"]
    assert "[SYSTEM].[CONNECT]" not in script
    assert "@name = N'[dbo].[CONNECT]'" in script
    assert "@name = N'[SYSTEM].[usp_x]'" in script


def test_signed_routines_are_listed_but_not_recompiled() -> None:
    scripts = _render(
        {"dev": [_result("dbo", "usp_signed", SignatureStatus.SIGNED)]}, {"dev": "Db"}
    )

    script = scripts.per_profile["dev"]
    assert "-- OMITIDO (Firmado): [dbo].[usp_signed]" in script
    assert "sp_refreshsqlmodule" not in script
