"""TUI state stays consistent across re-runs and background work: the body
follows the latest result, stale results are dropped, and the routines
screen runs one operation at a time."""

from unittest.mock import patch

import pytest
from report.conftest import comparison_result_empty, comparison_result_with_findings

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.tui.app import SchemaComparatorApp
from schema_comparator.tui.procedure_screen import ProcedureVerificationScreen
from schema_comparator.tui.widgets import DetailPanel, FindingsTree


def _profiles() -> list[ConnectionProfile]:
    return [
        ConnectionProfile(name="a", connection_string="DSN=a"),
        ConnectionProfile(name="b", connection_string="DSN=b"),
    ]


async def _rerun(app, pilot) -> None:
    app.action_run_comparison()
    await app.workers.wait_for_complete()
    await pilot.pause()


@pytest.mark.asyncio
async def test_rerun_from_no_drift_shows_the_new_findings() -> None:
    app = SchemaComparatorApp(comparison_result_empty(), profiles=_profiles())

    with patch(
        "schema_comparator.tui.app.run_comparison",
        return_value=comparison_result_with_findings(),
    ):
        async with app.run_test() as pilot:
            assert not app.query(FindingsTree)
            await _rerun(app, pilot)

            trees = app.query(FindingsTree)
            assert trees and trees.first().root.children
            assert app.query(DetailPanel)
            assert not app.query("#no-drift-message")


@pytest.mark.asyncio
async def test_rerun_without_drift_shows_the_no_drift_message() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings(), profiles=_profiles())

    with patch(
        "schema_comparator.tui.app.run_comparison",
        return_value=comparison_result_empty(),
    ):
        async with app.run_test() as pilot:
            await _rerun(app, pilot)

            assert app.query("#no-drift-message")
            assert not app.query(FindingsTree)


@pytest.mark.asyncio
async def test_results_of_a_superseded_run_are_ignored() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings(), profiles=_profiles())

    async with app.run_test():
        original = app._result
        app._run_id = 2
        app._apply_new_result(comparison_result_empty(), run_id=1)

        assert app._result is original


def test_routines_screen_runs_one_operation_at_a_time(tmp_path) -> None:
    screen = ProcedureVerificationScreen(
        profiles=tuple(_profiles()), repo_root=tmp_path
    )
    screen._busy = True

    with patch.object(screen, "run_worker") as m_run_worker:
        screen.action_validate_read_only()
        screen._execute_module_refresh()

    m_run_worker.assert_not_called()


def test_routines_screen_applies_results_and_becomes_idle(tmp_path) -> None:
    screen = ProcedureVerificationScreen(
        profiles=tuple(_profiles()), repo_root=tmp_path
    )
    screen._busy = True

    screen._apply_validation({"a": ()})

    assert screen._validation_results == {"a": ()}
    assert screen._busy is False
