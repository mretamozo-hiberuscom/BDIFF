"""Pilot-driven interaction tests for SchemaComparatorApp: the async
findings-browser TUI, exercised headless via Textual's `run_test()`."""

import io
from unittest.mock import patch

import pytest
from report.conftest import comparison_result_empty, comparison_result_with_findings

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.comparison.models import ComparisonFilters
from schema_comparator.tui.app import SchemaComparatorApp, run_tui
from schema_comparator.tui.widgets import (
    DetailPanel,
    ExcludeEditor,
    FindingsTree,
    StatusLog,
    SummaryHeader,
)


def _profiles() -> list[ConnectionProfile]:
    return [
        ConnectionProfile(name="a", connection_string="DSN=a"),
        ConnectionProfile(name="b", connection_string="DSN=b"),
    ]


@pytest.mark.asyncio
async def test_app_shows_header_with_profiles_and_counts() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as _pilot:
        header = app.query_one(SummaryHeader)
        rendered = str(header.render())

    assert "a, b, c" in rendered
    assert "Tablas faltantes: 1" in rendered
    assert "Columnas faltantes: 1" in rendered
    assert "Discrepancias de columnas: 1" in rendered


@pytest.mark.asyncio
async def test_app_shows_no_drift_message_for_empty_result() -> None:
    app = SchemaComparatorApp(comparison_result_empty())

    async with app.run_test() as _pilot:
        assert len(app.query(FindingsTree)) == 0
        static_texts = [str(w.render()) for w in app.query("#no-drift-message")]

    assert any("No se detectaron diferencias" in text for text in static_texts)


@pytest.mark.asyncio
async def test_app_tree_shows_one_group_per_table() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as _pilot:
        tree = app.query_one(FindingsTree)
        labels = [str(child.label) for child in tree.root.children]

    assert labels == ["sales.Invoice", "sales.Payment"]


@pytest.mark.asyncio
async def test_app_expanding_group_reveals_findings() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as _pilot:
        tree = app.query_one(FindingsTree)
        invoice_group = tree.root.children[0]

    assert invoice_group.is_expanded
    assert len(invoice_group.children) == 2


@pytest.mark.asyncio
async def test_app_collapsing_group_hides_findings_keeps_header() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        tree = app.query_one(FindingsTree)
        tree.focus()
        await pilot.pause()
        invoice_group = tree.root.children[0]
        assert invoice_group.is_expanded

        await pilot.press("down")
        await pilot.press("space")
        await pilot.pause()

        assert not invoice_group.is_expanded
        assert str(invoice_group.label) == "sales.Invoice"


@pytest.mark.asyncio
async def test_app_filter_input_hides_non_matching_findings() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        app.filter_text = "ColumnMismatch"
        await pilot.pause()
        tree = app.query_one(FindingsTree)
        group_labels = [str(child.label) for child in tree.root.children]

    assert group_labels == ["sales.Invoice"]
    assert len(tree.root.children[0].children) == 1


@pytest.mark.asyncio
async def test_app_clearing_filter_restores_all_findings() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        app.filter_text = "ColumnMismatch"
        await pilot.pause()
        app.filter_text = ""
        await pilot.pause()
        tree = app.query_one(FindingsTree)
        group_labels = [str(child.label) for child in tree.root.children]

    assert group_labels == ["sales.Invoice", "sales.Payment"]


@pytest.mark.asyncio
async def test_app_selecting_leaf_updates_detail_panel() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        tree = app.query_one(FindingsTree)
        tree.focus()
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("down")
        await pilot.press("down")
        await pilot.pause()
        detail = app.query_one(DetailPanel)
        rendered = str(detail.render())

    assert "a: decimal(10,2), NOT NULL" in rendered
    assert "b: decimal(12,2), NOT NULL" in rendered


@pytest.mark.asyncio
async def test_app_quit_key_exits_app() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()

    assert not app.is_running


@pytest.mark.asyncio
async def test_app_escape_key_exits_app() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert not app.is_running


def test_run_tui_catches_app_exception_and_reports_to_stderr(capsys) -> None:
    result = comparison_result_with_findings()

    with patch(
        "schema_comparator.tui.app.SchemaComparatorApp.run",
        side_effect=RuntimeError("boom"),
    ):
        run_tui(result)  # must not raise

    captured = capsys.readouterr()
    assert "[ERROR] Falló la interfaz interactiva" in captured.err


def test_app_accepts_profiles_and_exclude_patterns_constructor_args() -> None:
    app = SchemaComparatorApp(
        comparison_result_with_findings(),
        profiles=_profiles(),
        exclude_patterns=["LOG"],
    )

    assert app._profiles == _profiles()
    assert app._exclude_patterns == ["LOG"]


@pytest.mark.asyncio
async def test_pressing_e_focuses_exclude_editor() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        tree = app.query_one(FindingsTree)
        tree.focus()
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        editor = app.query_one(ExcludeEditor)

        assert app.focused is editor


@pytest.mark.asyncio
async def test_submitting_exclude_editor_updates_patterns_and_triggers_run() -> None:
    new_result = comparison_result_empty()
    calls = []

    def fake_run_comparison(profiles, exclude_patterns):
        calls.append(exclude_patterns)
        return new_result

    app = SchemaComparatorApp(comparison_result_with_findings(), profiles=_profiles())

    with patch(
        "schema_comparator.tui.app.run_comparison", side_effect=fake_run_comparison
    ):
        async with app.run_test() as pilot:
            editor = app.query_one(ExcludeEditor)
            editor.focus()
            await pilot.pause()
            editor.value = "LOG QRTZ"
            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()

    assert app._exclude_patterns == ["LOG", "QRTZ"]
    assert calls == [ComparisonFilters(excluded_tables=("LOG", "QRTZ"))]


@pytest.mark.asyncio
async def test_pressing_r_triggers_run_comparison_without_changing_excludes() -> None:
    new_result = comparison_result_empty()
    calls = []

    def fake_run_comparison(profiles, exclude_patterns):
        calls.append((profiles, exclude_patterns))
        return new_result

    app = SchemaComparatorApp(
        comparison_result_with_findings(),
        profiles=_profiles(),
        exclude_patterns=["LOG"],
    )

    with patch(
        "schema_comparator.tui.app.run_comparison", side_effect=fake_run_comparison
    ):
        async with app.run_test() as pilot:
            tree = app.query_one(FindingsTree)
            tree.focus()
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()
            await app.workers.wait_for_complete()

    assert calls == [(_profiles(), ComparisonFilters(excluded_tables=("LOG",)))]
    assert app._exclude_patterns == ["LOG"]
    assert app._result is new_result


@pytest.mark.asyncio
async def test_run_comparison_failure_leaves_previous_result_and_logs_error() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings(), profiles=_profiles())

    with patch(
        "schema_comparator.tui.app.run_comparison",
        side_effect=RuntimeError("boom"),
    ):
        async with app.run_test() as pilot:
            original_result = app._result
            original_tree_data = app._tree_data
            tree = app.query_one(FindingsTree)
            tree.focus()
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()
            await app.workers.wait_for_complete()
            log = app.query_one(StatusLog)

            assert app._result is original_result
            assert app._tree_data is original_tree_data
            assert any(
                "Falló la comparación: RuntimeError" in str(line) for line in log.lines
            )
            assert not any("boom" in str(line) for line in log.lines)


@pytest.mark.asyncio
async def test_pressing_g_calls_generate_reports_with_string_io_and_logs_output() -> (
    None
):
    captured = {}

    def fake_generate(result, *, out=None):
        captured["out"] = out
        print("Reporte HTML generado: foo.html", file=out)

    app = SchemaComparatorApp(comparison_result_with_findings(), profiles=_profiles())

    with patch(
        "schema_comparator.tui.app.generate_all_reports", side_effect=fake_generate
    ):
        async with app.run_test() as pilot:
            tree = app.query_one(FindingsTree)
            tree.focus()
            await pilot.pause()
            await pilot.press("g")
            await pilot.pause()
            await app.workers.wait_for_complete()
            log = app.query_one(StatusLog)

            assert isinstance(captured["out"], io.StringIO)
            assert any(
                "Reporte HTML generado: foo.html" in str(line) for line in log.lines
            )


@pytest.mark.asyncio
async def test_generate_reports_single_format_failure_does_not_crash_app() -> None:
    def fake_generate(result, *, out=None):
        print("[ERROR] Falló la generación del reporte PDF: boom", file=out)

    app = SchemaComparatorApp(comparison_result_with_findings(), profiles=_profiles())

    with patch(
        "schema_comparator.tui.app.generate_all_reports", side_effect=fake_generate
    ):
        async with app.run_test() as pilot:
            tree = app.query_one(FindingsTree)
            tree.focus()
            await pilot.pause()
            await pilot.press("g")
            await pilot.pause()
            await app.workers.wait_for_complete()
            log = app.query_one(StatusLog)

            assert app.is_running
            assert any(
                "Falló la generación del reporte PDF: boom" in str(line)
                for line in log.lines
            )


def test_run_tui_forwards_profiles_and_exclude_patterns() -> None:
    result = comparison_result_with_findings()
    profiles = _profiles()
    captured = {}

    class _FakeApp:
        def __init__(
            self, result, *, profiles=None, exclude_patterns=None, exclude_routines=None
        ) -> None:
            captured["result"] = result
            captured["profiles"] = profiles
            captured["exclude_patterns"] = exclude_patterns
            captured["exclude_routines"] = exclude_routines

        def run(self) -> None:
            pass

    with patch("schema_comparator.tui.app.SchemaComparatorApp", _FakeApp):
        run_tui(
            result,
            profiles=profiles,
            exclude_patterns=["LOG"],
            exclude_routines=["tmp"],
        )

    assert captured["profiles"] == profiles
    assert captured["exclude_patterns"] == ["LOG"]
    assert captured["exclude_routines"] == ["tmp"]


@pytest.mark.asyncio
async def test_app_opens_decision_screen() -> None:
    from schema_comparator.tui.decision_screen import DecisionScreen

    app = SchemaComparatorApp(comparison_result_with_findings(), profiles=_profiles())

    async with app.run_test() as pilot:
        tree = app.query_one(FindingsTree)
        tree.focus()
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()

        # Verify that DecisionScreen is now the active screen
        assert isinstance(app.screen, DecisionScreen)


@pytest.mark.asyncio
async def test_decision_screen_writes_scripts_under_the_working_directory(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    app = SchemaComparatorApp(comparison_result_with_findings(), profiles=_profiles())

    async with app.run_test() as pilot:
        app.query_one(FindingsTree).focus()
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()

        assert app.screen.repo_root == tmp_path
