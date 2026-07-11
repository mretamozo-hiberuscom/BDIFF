"""Pilot-driven interaction tests for SchemaComparatorApp: the async
findings-browser TUI, exercised headless via Textual's `run_test()`."""

import pytest
from report.conftest import comparison_result_empty, comparison_result_with_findings
from unittest.mock import patch

from schema_comparator.tui.app import SchemaComparatorApp, run_tui
from schema_comparator.tui.widgets import DetailPanel, FindingsTree, SummaryHeader


@pytest.mark.asyncio
async def test_app_shows_header_with_profiles_and_counts() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        header = app.query_one(SummaryHeader)
        rendered = str(header.render())

    assert "a, b, c" in rendered
    assert "Tablas faltantes: 1" in rendered
    assert "Columnas faltantes: 1" in rendered
    assert "Discrepancias de columnas: 1" in rendered


@pytest.mark.asyncio
async def test_app_shows_no_drift_message_for_empty_result() -> None:
    app = SchemaComparatorApp(comparison_result_empty())

    async with app.run_test() as pilot:
        assert len(app.query(FindingsTree)) == 0
        static_texts = [str(w.render()) for w in app.query("#no-drift-message")]

    assert any("No se detectaron diferencias" in text for text in static_texts)


@pytest.mark.asyncio
async def test_app_tree_shows_one_group_per_table() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        tree = app.query_one(FindingsTree)
        labels = [str(child.label) for child in tree.root.children]

    assert labels == ["sales.Invoice", "sales.Payment"]


@pytest.mark.asyncio
async def test_app_expanding_group_reveals_findings() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
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
