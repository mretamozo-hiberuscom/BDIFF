"""Tests for DecisionScreen interactive TUI view."""

from pathlib import Path
import tempfile
import pytest
from textual.app import App, ComposeResult
from textual.widgets import ListView, RadioSet, SelectionList

from schema_comparator.compare.models import (
    ColumnAttributes,
    ColumnMismatch,
    MissingColumn,
    MissingTable,
    NamedColumnAttributes,
)
from schema_comparator.tui.decision_screen import DecisionScreen
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.compare.consolidation import ColumnAction, TableAction


def _sample_entries() -> tuple:
    attr1 = ColumnAttributes(
        data_type="varchar",
        character_maximum_length=100,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    attr2 = ColumnAttributes(
        data_type="varchar",
        character_maximum_length=200,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    mismatch = ColumnMismatch(
        schema_name="dbo",
        table_name="users",
        column_name="email",
        values_by_profile=(("profileA", attr1), ("profileB", attr2)),
    )
    missing = MissingColumn(
        schema_name="dbo",
        table_name="users",
        column_name="age",
        missing_from_profile="profileB",
        present_attributes=(("profileA", attr1),),
    )
    missing_tbl = MissingTable(
        schema_name="dbo",
        table_name="logs",
        missing_from_profile="profileB",
        present_columns=(
            ("profileA", (
                NamedColumnAttributes(name="id", attributes=attr1),
                NamedColumnAttributes(name="message", attributes=attr2),
            )),
        ),
    )
    return mismatch, missing, missing_tbl


def _sample_profiles() -> tuple[ConnectionProfile, ...]:
    return (
        ConnectionProfile(name="profileA", connection_string="Database=db_a;"),
        ConnectionProfile(name="profileB", connection_string="Database=db_b;"),
    )


class DummyApp(App[list[str] | None]):
    """A minimal test application to host DecisionScreen."""

    def __init__(self, entries, profiles, repo_root) -> None:
        super().__init__()
        self.test_entries = entries
        self.test_profiles = profiles
        self.test_repo_root = repo_root
        self.dismissed_result = None

    def on_mount(self) -> None:
        def handle_dismiss(result) -> None:
            self.dismissed_result = result
            self.exit()

        self.push_screen(
            DecisionScreen(
                entries=self.test_entries,
                profiles=self.test_profiles,
                repo_root=self.test_repo_root,
            ),
            callback=handle_dismiss,
        )


@pytest.mark.asyncio
async def test_decision_screen_lists_all_mismatches_and_missing() -> None:
    entries = _sample_entries()
    profiles = _sample_profiles()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = DummyApp(entries, profiles, Path(tmp_dir))
        
        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, DecisionScreen)
            
            # Check left panel list populates correctly (grouped by unique table)
            list_view = screen.query_one("#findings-list", ListView)
            assert len(list_view.children) == 2
            
            from textual.widgets import Label
            item0_label = str(list_view.children[0].query_one(Label).render())
            item1_label = str(list_view.children[1].query_one(Label).render())
            
            assert "dbo.logs" in item0_label
            assert "1 hallazgo" in item0_label
            assert "dbo.users" in item1_label
            assert "2 hallazgos" in item1_label


@pytest.mark.asyncio
async def test_decision_screen_updates_decision_on_radio_change() -> None:
    entries = _sample_entries()
    profiles = _sample_profiles()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = DummyApp(entries, profiles, Path(tmp_dir))
        
        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, DecisionScreen)
            
            # Select second item by focusing the list and pressing enter
            list_view = screen.query_one("#findings-list", ListView)
            list_view.focus()
            list_view.index = 1
            await pilot.press("enter")
            await pilot.pause()
            
            # Verify RadioSets exist in right panel (one for each column)
            radio_sets = list(screen.query(RadioSet))
            assert len(radio_sets) == 2
            assert len(radio_sets[0].children) == 4  # Two attrs options + drop + ignore
            
            # Select first option (index 0) on the first column card
            radio_sets[0].children[0].value = True
            await pilot.pause()
            
            # Check first selection list is now enabled
            selection_lists = list(screen.query(SelectionList))
            assert len(selection_lists) == 2
            assert selection_lists[0].disabled is False
            assert selection_lists[1].disabled is True
            
            # Select "Ignore" (index 3) on the first column card
            radio_sets[0].children[3].value = True
            await pilot.pause()
            
            # Verify internal decision state has been set to None for that entry
            dec = screen.decisions[entries[0]]
            assert dec[0] is None
            assert len(dec[1]) == 0


@pytest.mark.asyncio
async def test_decision_screen_saves_sql_scripts() -> None:
    entries = _sample_entries()
    profiles = _sample_profiles()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        app = DummyApp(entries, profiles, tmp_path)
        
        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, DecisionScreen)
            
            # Select second item by focusing the list and pressing enter
            list_view = screen.query_one("#findings-list", ListView)
            list_view.focus()
            list_view.index = 1
            await pilot.press("enter")
            await pilot.pause()
            
            # Select first option (index 0) on first column card and check profileB
            radio_sets = list(screen.query(RadioSet))
            radio_sets[0].children[0].value = True
            await pilot.pause()
            
            sel_lists = list(screen.query(SelectionList))
            sel_lists[0].select_all()
            await pilot.pause()

            # Press Generate SQL (shortcut G)
            await pilot.press("g")
            await pilot.pause()
            
        # Verify the screen dismissed successfully with file paths
        assert app.dismissed_result is not None
        assert len(app.dismissed_result) > 0
        
        # Verify the files actually exist on disk
        sql_folder = tmp_path / "scripts-db"
        assert sql_folder.exists()
        
        # At least one profile SQL script should have ALTER TABLE statements
        profile_b_sql = sql_folder / "profileB.sql"
        assert profile_b_sql.exists()
        
        content = profile_b_sql.read_text(encoding="utf-8")
        assert "USE [db_b];" in content
        assert "ALTER TABLE [dbo].[users] ALTER COLUMN [email]" in content or "ALTER TABLE [dbo].[users] ADD [age]" in content


@pytest.mark.asyncio
async def test_decision_screen_no_resolutions_notifies_warning() -> None:
    from unittest.mock import MagicMock
    entries = _sample_entries()
    profiles = _sample_profiles()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = DummyApp(entries, profiles, Path(tmp_dir))
        
        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, DecisionScreen)
            
            # Select second item (mounts all columns of dbo.users)
            list_view = screen.query_one("#findings-list", ListView)
            list_view.focus()
            list_view.index = 1
            await pilot.press("enter")
            await pilot.pause()
            
            # All decisions default to Ignore (None, ())
            # Mock notify
            app.notify = MagicMock()
            
            # Press Generate SQL
            await pilot.press("g")
            await pilot.pause()
            
            app.notify.assert_called_once_with(
                "No se seleccionó ninguna corrección para generar SQL.",
                severity="warning"
            )


@pytest.mark.asyncio
async def test_decision_screen_sql_generation_error_notifies_error() -> None:
    from unittest.mock import patch, MagicMock
    entries = _sample_entries()
    profiles = _sample_profiles()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = DummyApp(entries, profiles, Path(tmp_dir))
        
        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, DecisionScreen)
            
            # Select second item
            list_view = screen.query_one("#findings-list", ListView)
            list_view.focus()
            list_view.index = 1
            await pilot.press("enter")
            await pilot.pause()
            
            # Actively select an action so generation is triggered
            radio_sets = list(screen.query(RadioSet))
            radio_sets[0].children[0].value = True
            await pilot.pause()
            
            sel_lists = list(screen.query(SelectionList))
            sel_lists[0].select_all()
            await pilot.pause()

            # Mock notify
            app.notify = MagicMock()
            
            # Mock write_sql_scripts to raise Exception
            with patch("schema_comparator.compare.consolidation.write_sql_scripts", side_effect=Exception("Disk full")):
                await pilot.press("g")
                await pilot.pause()
                
            app.notify.assert_called_once_with(
                "Error al generar scripts: Disk full",
                severity="error"
            )


@pytest.mark.asyncio
async def test_decision_screen_renders_missing_table_card_with_create_option() -> None:
    entries = _sample_entries()
    profiles = _sample_profiles()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = DummyApp(entries, profiles, Path(tmp_dir))
        
        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, DecisionScreen)
            
            # Select dbo.logs (first item) by focusing the list and pressing enter
            list_view = screen.query_one("#findings-list", ListView)
            list_view.focus()
            list_view.index = 0
            await pilot.press("enter")
            await pilot.pause()
            
            # Verify that right panel contains the ColumnResolutionWidget for MissingTable
            from schema_comparator.tui.decision_screen import ColumnResolutionWidget
            cards = list(screen.query(ColumnResolutionWidget))
            assert len(cards) == 1
            # The widget entry is now a MergedMissingTable (same table identity)
            from schema_comparator.tui.decision_screen import MergedMissingTable
            assert isinstance(cards[0].entry, MergedMissingTable)
            assert cards[0].entry.qualified_name == entries[2].qualified_name
            
            # Verify a RadioSet with create, delete and ignore options
            from textual.widgets import RadioSet
            radio_sets = list(cards[0].query(RadioSet))
            assert len(radio_sets) == 1
            assert radio_sets[0].disabled is False
            assert len(radio_sets[0].children) == 3
            
            # Verify a SelectionList IS rendered (disabled by default)
            from textual.widgets import SelectionList
            sel_lists = list(cards[0].query(SelectionList))
            assert len(sel_lists) == 1
            assert sel_lists[0].disabled is True
            
            # Verify the decision defaults to None (No hacer nada)
            from schema_comparator.tui.decision_screen import MergedMissingTable
            merged_key = next(k for k in screen.decisions if isinstance(k, MergedMissingTable))
            dec = screen.decisions[merged_key]
            assert dec[0] is None
            assert len(dec[1]) == 0


@pytest.mark.asyncio
async def test_decision_screen_generates_drop_table_sql() -> None:
    entries = _sample_entries()
    profiles = _sample_profiles()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        app = DummyApp(entries, profiles, tmp_path)

        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, DecisionScreen)

            list_view = screen.query_one("#findings-list", ListView)
            list_view.focus()
            list_view.index = 0
            await pilot.press("enter")
            await pilot.pause()

            radio_set = screen.query_one(RadioSet)
            radio_set.children[1].value = True
            await pilot.pause()
            await pilot.press("g")
            await pilot.pause()

        content = (tmp_path / "scripts-db" / "profileA.sql").read_text(encoding="utf-8")
        assert "DROP TABLE [dbo].[logs];" in content
        from schema_comparator.tui.decision_screen import MergedMissingTable
        merged_key = next(k for k in screen.decisions if isinstance(k, MergedMissingTable))
        assert screen.decisions[merged_key] == (TableAction.DROP, ("profileA",))


@pytest.mark.asyncio
async def test_missing_column_drop_targets_only_present_profiles_and_generates_sql() -> None:
    entries = _sample_entries()
    profiles = _sample_profiles()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        app = DummyApp(entries, profiles, tmp_path)

        async with app.run_test() as pilot:
            screen = app.screen
            list_view = screen.query_one("#findings-list", ListView)
            list_view.focus()
            list_view.index = 1
            await pilot.press("enter")
            await pilot.pause()

            radio_sets = list(screen.query(RadioSet))
            selection_lists = list(screen.query(SelectionList))
            radio_sets[1].children[1].value = True
            await pilot.pause()

            assert selection_lists[1].disabled is False
            assert len(selection_lists[1].options) == 1
            assert selection_lists[1].selected == ["profileA"]
            from schema_comparator.tui.decision_screen import MergedMissingColumn
            merged_col_key = next(k for k in screen.decisions if isinstance(k, MergedMissingColumn))
            assert screen.decisions[merged_col_key] == (ColumnAction.DROP, ("profileA",))

            radio_sets[0].children[3].value = True
            await pilot.pause()
            await pilot.press("g")
            await pilot.pause()

        content = (tmp_path / "scripts-db" / "profileA.sql").read_text(encoding="utf-8")
        assert "DROP COLUMN [age];" in content
        assert "ALTER COLUMN [email]" not in content


@pytest.mark.asyncio
async def test_column_mismatch_drop_defaults_to_all_present_profiles() -> None:
    mismatch, _, _ = _sample_entries()
    profiles = _sample_profiles()

    with tempfile.TemporaryDirectory() as tmp_dir:
        app = DummyApp((mismatch,), profiles, Path(tmp_dir))

        async with app.run_test() as pilot:
            screen = app.screen
            list_view = screen.query_one("#findings-list", ListView)
            list_view.focus()
            list_view.index = 0
            await pilot.press("enter")
            await pilot.pause()

            radio_set = screen.query_one(RadioSet)
            radio_set.children[2].value = True
            await pilot.pause()

            selection_list = screen.query_one(SelectionList)
            assert len(selection_list.options) == 2
            assert selection_list.selected == ["profileA", "profileB"]
            assert screen.decisions[mismatch] == (ColumnAction.DROP, ("profileA", "profileB"))


# ---------------------------------------------------------------------------
# Regression: multi-profile missing table – single consolidated decision
# ---------------------------------------------------------------------------

def _three_profile_missing_table_entries():
    """Simulates engine output for a table present in A, absent from B and C."""
    attr = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    named_col = NamedColumnAttributes(name="id", attributes=attr)
    present_cols = (("profileA", (named_col,)),)
    entry_b = MissingTable(
        schema_name="dbo",
        table_name="logs",
        missing_from_profile="profileB",
        present_columns=present_cols,
    )
    entry_c = MissingTable(
        schema_name="dbo",
        table_name="logs",
        missing_from_profile="profileC",
        present_columns=present_cols,
    )
    return entry_b, entry_c


def _three_profiles():
    return (
        ConnectionProfile(name="profileA", connection_string="Database=db_a;"),
        ConnectionProfile(name="profileB", connection_string="Database=db_b;"),
        ConnectionProfile(name="profileC", connection_string="Database=db_c;"),
    )


@pytest.mark.asyncio
async def test_multiprofile_missing_table_shows_single_decision_card() -> None:
    """Una tabla ausente en 2 perfiles (B, C) debe generar UNA sola tarjeta de decisión."""
    entries = _three_profile_missing_table_entries()
    profiles = _three_profiles()

    with tempfile.TemporaryDirectory() as tmp_dir:
        app = DummyApp(entries, profiles, Path(tmp_dir))

        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, DecisionScreen)

            # El listado tiene UNA entrada (dbo.logs)
            list_view = screen.query_one("#findings-list", ListView)
            assert len(list_view.children) == 1

            # Hay UN SOLO decision dict entry para la tabla
            assert len(screen.decisions) == 1

            # La decisión por defecto es 'No hacer nada' (None, ())
            (target, dests) = list(screen.decisions.values())[0]
            assert target is None
            assert len(dests) == 0

            # Abrir la tarjeta
            list_view.focus()
            list_view.index = 0
            await pilot.press("enter")
            await pilot.pause()

            from schema_comparator.tui.decision_screen import ColumnResolutionWidget
            cards = list(screen.query(ColumnResolutionWidget))
            # Solo UNA tarjeta para los dos MissingTable
            assert len(cards) == 1


@pytest.mark.asyncio
async def test_multiprofile_missing_table_drop_only_targets_present_profile() -> None:
    """Al elegir DROP, solo se genera acción para el perfil donde existe la tabla (A);
    los perfiles donde ya falta (B, C) no deben aparecer en ninguna resolución."""
    entries = _three_profile_missing_table_entries()
    profiles = _three_profiles()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        app = DummyApp(entries, profiles, tmp_path)

        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, DecisionScreen)

            # Fijar decisión DROP manualmente en el entry consolidado
            merged_key = list(screen.decisions.keys())[0]
            screen.decisions[merged_key] = (TableAction.DROP, ("profileA",))

            await pilot.press("g")
            await pilot.pause()

        scripts_dir = tmp_path / "scripts-db"
        assert scripts_dir.exists(), "No se generaron scripts SQL"

        a_sql = (scripts_dir / "profileA.sql").read_text(encoding="utf-8")
        assert "DROP TABLE [dbo].[logs];" in a_sql

        # B y C NO deben tener ninguna instrucción sobre logs
        for profile in ("profileB", "profileC"):
            pf = scripts_dir / f"{profile}.sql"
            if pf.exists():
                content = pf.read_text(encoding="utf-8")
                assert "logs" not in content.lower(), (
                    f"{profile}.sql no debe contener referencias a 'logs' (tabla ya ausente)"
                )


# ---------------------------------------------------------------------------
# Regression: multi-profile missing column – single consolidated decision
# ---------------------------------------------------------------------------

def _three_profile_missing_column_entries():
    """Simulates engine output for a column present in A, absent from B and C."""
    attr = ColumnAttributes(
        data_type="varchar",
        character_maximum_length=50,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=True,
    )
    present_attrs = (("profileA", attr),)
    entry_b = MissingColumn(
        schema_name="dbo",
        table_name="users",
        column_name="phone",
        missing_from_profile="profileB",
        present_attributes=present_attrs,
    )
    entry_c = MissingColumn(
        schema_name="dbo",
        table_name="users",
        column_name="phone",
        missing_from_profile="profileC",
        present_attributes=present_attrs,
    )
    return entry_b, entry_c


@pytest.mark.asyncio
async def test_multiprofile_missing_column_shows_single_decision_card() -> None:
    """Una columna ausente en 2 perfiles (B, C) debe generar UNA sola tarjeta de decisión (MergedMissingColumn)."""
    entries = _three_profile_missing_column_entries()
    profiles = _three_profiles()

    with tempfile.TemporaryDirectory() as tmp_dir:
        app = DummyApp(entries, profiles, Path(tmp_dir))

        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, DecisionScreen)

            # El listado por tabla tiene UNA entrada (dbo.users)
            list_view = screen.query_one("#findings-list", ListView)
            assert len(list_view.children) == 1

            # Hay UN SOLO decision dict entry para la columna fusionada
            assert len(screen.decisions) == 1

            from schema_comparator.tui.decision_screen import MergedMissingColumn
            merged_key = list(screen.decisions.keys())[0]
            assert isinstance(merged_key, MergedMissingColumn)
            assert merged_key.missing_from_profiles == ("profileB", "profileC")

            # La decisión por defecto es 'No hacer nada' (None, ())
            (target, dests) = screen.decisions[merged_key]
            assert target is None
            assert len(dests) == 0

            # Abrir la tarjeta
            list_view.focus()
            list_view.index = 0
            await pilot.press("enter")
            await pilot.pause()

            from schema_comparator.tui.decision_screen import ColumnResolutionWidget
            cards = list(screen.query(ColumnResolutionWidget))
            # Solo UNA tarjeta para las dos entradas MissingColumn
            assert len(cards) == 1
            assert isinstance(cards[0].entry, MergedMissingColumn)


@pytest.mark.asyncio
async def test_multiprofile_missing_column_drop_only_targets_present_profile() -> None:
    """Al elegir DROP en una columna faltante en múltiples perfiles, solo se elimina en el perfil donde existe (A)."""
    entries = _three_profile_missing_column_entries()
    profiles = _three_profiles()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        app = DummyApp(entries, profiles, tmp_path)

        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, DecisionScreen)

            # Abrir la tarjeta
            list_view = screen.query_one("#findings-list", ListView)
            list_view.focus()
            list_view.index = 0
            await pilot.press("enter")
            await pilot.pause()

            # Cambiar a opción DROP (índice 1 en RadioSet)
            radio_set = screen.query_one(RadioSet)
            radio_set.children[1].value = True
            await pilot.pause()

            from schema_comparator.tui.decision_screen import MergedMissingColumn
            merged_key = list(screen.decisions.keys())[0]
            assert isinstance(merged_key, MergedMissingColumn)
            assert screen.decisions[merged_key] == (ColumnAction.DROP, ("profileA",))

            await pilot.press("g")
            await pilot.pause()

        scripts_dir = tmp_path / "scripts-db"
        assert scripts_dir.exists(), "No se generaron scripts SQL"

        a_sql = (scripts_dir / "profileA.sql").read_text(encoding="utf-8")
        assert "ALTER TABLE [dbo].[users] DROP COLUMN [phone];" in a_sql

        # B y C NO deben contener 'phone'
        for profile in ("profileB", "profileC"):
            pf = scripts_dir / f"{profile}.sql"
            if pf.exists():
                content = pf.read_text(encoding="utf-8")
                assert "phone" not in content.lower()

