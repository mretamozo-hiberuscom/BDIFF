"""Database identifiers and profile names are shown literally in the TUI:
brackets in them are never read as Rich markup (which could raise
MarkupError or hide text)."""

import pytest

from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.schema.models import (
    ColumnSnapshot,
    SchemaSnapshot,
    TableSnapshot,
)
from schema_comparator.tui.app import SchemaComparatorApp
from schema_comparator.tui.widgets import DetailPanel, FindingsTree, StatusLog

_TABLE = "[/bold]Pólizas"
_COLUMN = "precio[eur]"


def _column(data_type: str) -> ColumnSnapshot:
    return ColumnSnapshot(_COLUMN, data_type, None, 10, 2, False, 1)


def _result():
    return compare_snapshots(
        [
            SchemaSnapshot(
                "dev[1]", (TableSnapshot("dbo", _TABLE, (_column("int"),)),)
            ),
            SchemaSnapshot(
                "qa[/red]", (TableSnapshot("dbo", _TABLE, (_column("bigint"),)),)
            ),
        ]
    )


def _profiles():
    return [
        ConnectionProfile(name="dev[1]", connection_string="x"),
        ConnectionProfile(name="qa[/red]", connection_string="x"),
    ]


@pytest.mark.asyncio
async def test_tree_and_detail_panel_show_identifiers_literally() -> None:
    app = SchemaComparatorApp(_result(), profiles=_profiles())

    async with app.run_test() as pilot:
        tree = app.query_one(FindingsTree)
        group = tree.root.children[0]
        assert group.label.plain == f"dbo.{_TABLE}  (1)"
        leaf = group.children[0]
        assert _COLUMN in leaf.label.plain
        assert "qa[/red]" in leaf.label.plain

        tree.focus()
        tree.move_cursor(leaf)
        await pilot.pause()
        detail = str(app.query_one(DetailPanel).render())
        assert _COLUMN in detail
        assert f"dbo.{_TABLE}" in detail


@pytest.mark.asyncio
async def test_status_log_shows_messages_literally() -> None:
    app = SchemaComparatorApp(_result(), profiles=_profiles())

    async with app.run_test() as pilot:
        await pilot.press("l")
        log = app.query_one(StatusLog)
        log.error("Falló [/bold] algo")
        log.info("Ruta reportes/[x]")
        await pilot.pause()

        lines = [line.text for line in log.lines]
        assert any("Falló [/bold] algo" in line for line in lines)
        assert any("Ruta reportes/[x]" in line for line in lines)
        assert not any("[red]" in line for line in lines)


@pytest.mark.asyncio
async def test_decision_screen_renders_identifiers_literally() -> None:
    from schema_comparator.tui.decision_screen import DecisionScreen

    app = SchemaComparatorApp(_result(), profiles=_profiles())

    async with app.run_test() as pilot:
        app.query_one(FindingsTree).focus()
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, DecisionScreen)

        screen.show_resolution_form(screen.table_keys[0])
        await pilot.pause()

        texts = " ".join(str(label.render()) for label in screen.query("Label"))
        assert _TABLE in texts
        assert _COLUMN in texts
