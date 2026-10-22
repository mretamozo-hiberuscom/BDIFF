"""Behaviour of the redesigned findings screen: leaving, Esc, the drawer,
help, the busy state, narrow terminals and the filter feedback."""

import threading
from unittest.mock import patch

import pytest
from report.conftest import comparison_result_empty, comparison_result_with_findings

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.tui.app import SchemaComparatorApp
from schema_comparator.tui.decision_screen import DecisionScreen
from schema_comparator.tui.modals import HelpModal, QuitModal
from schema_comparator.tui.widgets import (
    DetailPanel,
    ExcludeEditor,
    FindingsTree,
    SummaryHeader,
)

_EMOJI_ONLY = {"⚠", "❌", "✅", "️"}


def _profiles() -> list[ConnectionProfile]:
    return [
        ConnectionProfile(name="a", connection_string="DSN=a"),
        ConnectionProfile(name="b", connection_string="DSN=b"),
    ]


def _has_emoji(text: str) -> bool:
    return any(ord(ch) >= 0x1F000 or ch in _EMOJI_ONLY for ch in text)


@pytest.mark.asyncio
async def test_q_asks_before_leaving_and_cancel_keeps_the_app() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        with patch.object(app, "exit") as leave:
            await pilot.press("q")
            await pilot.pause()
            assert isinstance(app.screen, QuitModal)

            await pilot.press("escape")
            await pilot.pause()

            assert not isinstance(app.screen, QuitModal)
            leave.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("confirm_key", ["enter", "q"])
async def test_confirming_the_quit_modal_exits(confirm_key: str) -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        with patch.object(app, "exit") as leave:
            await pilot.press("q")
            await pilot.pause()
            await pilot.press(confirm_key)
            await pilot.pause()

            leave.assert_called_once()


@pytest.mark.asyncio
async def test_escape_never_quits() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        with patch.object(app, "exit") as leave:
            await pilot.press("escape")
            await pilot.pause()

            leave.assert_not_called()
            assert not isinstance(app.screen, QuitModal)


@pytest.mark.asyncio
async def test_findings_tree_has_focus_on_start() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.focused is app.query_one(FindingsTree)


@pytest.mark.asyncio
async def test_drawer_is_closed_until_asked_for() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        drawer = app.query_one("#drawer")
        assert not drawer.display

        await pilot.press("l")
        await pilot.pause()
        assert drawer.display

        await pilot.press("l")
        await pilot.pause()
        assert not drawer.display


@pytest.mark.asyncio
async def test_escape_closes_the_drawer_and_returns_to_the_findings() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        await pilot.press("e")
        await pilot.pause()
        assert app.query_one("#drawer").display
        assert app.focused is app.query_one(ExcludeEditor)

        await pilot.press("escape")
        await pilot.pause()

        assert not app.query_one("#drawer").display
        assert app.focused is app.query_one(FindingsTree)


@pytest.mark.asyncio
async def test_escape_clears_the_filter_then_returns_to_the_findings() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        await pilot.press("slash")
        await pilot.press(*"notes")
        await pilot.pause()
        assert app.filter_text == "notes"

        await pilot.press("escape")
        await pilot.pause()
        assert app.filter_text == ""
        assert app.focused.id == "filter-input"

        await pilot.press("escape")
        await pilot.pause()
        assert app.focused is app.query_one(FindingsTree)


@pytest.mark.asyncio
async def test_question_mark_opens_help_and_escape_closes_it() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpModal)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, HelpModal)


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["c", "d"])
async def test_consolidate_has_a_new_key_and_keeps_the_old_one(key: str) -> None:
    app = SchemaComparatorApp(comparison_result_with_findings(), profiles=_profiles())

    async with app.run_test() as pilot:
        await pilot.press(key)
        await pilot.pause()

        assert isinstance(app.screen, DecisionScreen)


@pytest.mark.asyncio
async def test_content_is_busy_only_while_a_comparison_runs() -> None:
    release = threading.Event()

    def slow_run(profiles, filters):
        release.wait(timeout=5)
        return comparison_result_empty()

    app = SchemaComparatorApp(comparison_result_with_findings(), profiles=_profiles())

    with patch("schema_comparator.tui.app.run_comparison", side_effect=slow_run):
        async with app.run_test() as pilot:
            content = app.query_one("#content")
            assert not content.loading

            app.action_run_comparison()
            assert content.loading

            release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert not content.loading


@pytest.mark.asyncio
async def test_failed_comparison_clears_the_busy_state() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings(), profiles=_profiles())

    with patch(
        "schema_comparator.tui.app.run_comparison", side_effect=RuntimeError("boom")
    ):
        async with app.run_test() as pilot:
            app.action_run_comparison()
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert not app.query_one("#content").loading


@pytest.mark.asyncio
async def test_layout_stacks_on_narrow_terminals_only() -> None:
    narrow = SchemaComparatorApp(comparison_result_with_findings())
    async with narrow.run_test(size=(80, 30)) as pilot:
        await pilot.pause()
        assert narrow.has_class("-narrow")

    wide = SchemaComparatorApp(comparison_result_with_findings())
    async with wide.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        assert not wide.has_class("-narrow")


@pytest.mark.asyncio
async def test_tree_title_counts_findings_and_says_when_nothing_matches() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        tree = app.query_one(FindingsTree)
        assert tree.border_title == "Hallazgos (3)"

        app.filter_text = "notes"
        await pilot.pause()
        assert tree.border_title == "Hallazgos (1 de 3)"
        assert tree.border_subtitle == ""

        app.filter_text = "no-such-thing"
        await pilot.pause()
        assert tree.border_subtitle == "Sin coincidencias"


@pytest.mark.asyncio
async def test_selecting_a_table_summarises_its_findings() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test() as pilot:
        tree = app.query_one(FindingsTree)
        tree.focus()
        tree.move_cursor(tree.root.children[0])
        await pilot.pause()

        rendered = str(app.query_one(DetailPanel).render())

    assert "sales.Invoice" in rendered
    assert "2 hallazgos" in rendered


@pytest.mark.asyncio
async def test_detail_panel_guides_the_user_before_a_selection() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings())

    async with app.run_test():
        rendered = str(app.query_one(DetailPanel).render())

    assert "Selecciona un hallazgo" in rendered
    assert "?" in rendered


@pytest.mark.asyncio
async def test_main_screen_text_has_no_emoji() -> None:
    app = SchemaComparatorApp(comparison_result_with_findings(), profiles=_profiles())

    async with app.run_test() as pilot:
        texts = [str(app.query_one(SummaryHeader).render())]
        tree = app.query_one(FindingsTree)
        tree.focus()
        for node in [tree.root.children[0], *tree.root.children[0].children]:
            tree.move_cursor(node)
            await pilot.pause()
            texts.append(str(app.query_one(DetailPanel).render()))
            texts.append(str(node.label))
        await pilot.press("question_mark")
        await pilot.pause()
        texts += [str(w.render()) for w in app.screen.query("Static, Label")]

    assert not [t for t in texts if _has_emoji(t)]


@pytest.mark.asyncio
async def test_no_drift_screen_points_to_the_next_actions() -> None:
    app = SchemaComparatorApp(comparison_result_empty())

    async with app.run_test():
        message = str(app.query_one("#no-drift-message").render())
        header = str(app.query_one(SummaryHeader).render())

    assert "No se detectaron diferencias" in message
    assert "recomparar" in message or "volver a comparar" in message
    assert "Sin diferencias" in header
