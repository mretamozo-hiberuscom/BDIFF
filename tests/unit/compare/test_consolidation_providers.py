"""Consolidation renders T-SQL only, so it is limited to SQL Server
profiles (decision of 2026-10-21)."""

import datetime

import pytest
from report.conftest import comparison_result_with_findings

from schema_comparator.compare.consolidation import (
    ConsolidationNotSupportedError,
    unsupported_consolidation_profiles,
    write_sql_scripts,
)
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.tui.app import SchemaComparatorApp
from schema_comparator.tui.widgets import FindingsTree, StatusLog


def _profile(name: str, provider: str) -> ConnectionProfile:
    return ConnectionProfile(name=name, connection_string="x", provider=provider)


def test_unsupported_profiles_are_those_of_other_engines() -> None:
    profiles = [_profile("a", "sqlserver"), _profile("b", "postgresql")]

    assert unsupported_consolidation_profiles(profiles) == ["b"]


def test_write_sql_scripts_rejects_non_sqlserver_profiles(tmp_path) -> None:
    with pytest.raises(ConsolidationNotSupportedError, match="b"):
        write_sql_scripts(
            [],
            tmp_path,
            [_profile("a", "sqlserver"), _profile("b", "mysql")],
            timestamp=datetime.datetime(2026, 10, 21),
        )

    assert not (tmp_path / "scripts-db").exists()


@pytest.mark.asyncio
async def test_tui_does_not_open_consolidation_for_other_engines() -> None:
    from schema_comparator.tui.decision_screen import DecisionScreen

    app = SchemaComparatorApp(
        comparison_result_with_findings(),
        profiles=[_profile("a", "postgresql"), _profile("b", "postgresql")],
    )

    async with app.run_test() as pilot:
        app.query_one(FindingsTree).focus()
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()

        assert not isinstance(app.screen, DecisionScreen)
        await pilot.press("l")
        await pilot.pause()
        log = app.query_one(StatusLog)
        assert any(
            "solo está disponible para SQL Server" in str(line) for line in log.lines
        )
