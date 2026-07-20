"""TUI view for consolidating schema mismatches and missing columns (fase de decisiones)."""

from dataclasses import dataclass
from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, RadioButton, RadioSet, SelectionList

from schema_comparator.compare.models import ColumnAttributes, ColumnMismatch, DiffEntry, MissingColumn, MissingTable, NamedColumnAttributes
from schema_comparator.report.attributes import format_attributes
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.compare.consolidation import ColumnAction, TableAction


@dataclass(frozen=True)
class MergedMissingTable:
    """Aggregated view of multiple MissingTable entries sharing the same table identity.

    Used exclusively in DecisionScreen to present a single coherent decision when a
    table is absent from more than one profile. The engine still emits one MissingTable
    per absent profile; this class merges them at the display layer only.

    ``missing_from_profiles`` lists every profile where the table is ABSENT (sorted).
    ``present_columns`` lists every profile where it IS present, with its full column
    definition — same structure as ``MissingTable.present_columns``.
    """

    schema_name: str
    table_name: str
    missing_from_profiles: tuple[str, ...]
    present_columns: tuple[tuple[str, tuple[NamedColumnAttributes, ...]], ...]

    @property
    def qualified_name(self) -> tuple[str, str]:
        return (self.schema_name, self.table_name)


@dataclass(frozen=True)
class MergedMissingColumn:
    """Aggregated view of multiple MissingColumn entries sharing the same column identity.

    Used exclusively in DecisionScreen to present a single coherent decision when a
    column is absent from more than one profile in a matched table. The engine emits
    one MissingColumn per absent profile; this class merges them at the display layer only.

    ``missing_from_profiles`` lists every profile where the column is ABSENT (sorted).
    ``present_attributes`` lists every profile where it IS present, with its attributes —
    same structure as ``MissingColumn.present_attributes``.
    """

    schema_name: str
    table_name: str
    column_name: str
    missing_from_profiles: tuple[str, ...]
    present_attributes: tuple[tuple[str, ColumnAttributes], ...]

    @property
    def qualified_name(self) -> tuple[str, str]:
        return (self.schema_name, self.table_name)


class DecisionScreen(Screen):
    """Interactive form screen to consolidate schema differences and generate SQL DDL fixes."""

    DEFAULT_CSS = """
    DecisionScreen {
        align: center middle;
    }
    #decision-container {
        width: 95%;
        height: 90%;
        border: thick $primary;
        background: $panel;
    }
    #decision-title {
        text-align: center;
        background: $primary;
        color: $text;
        text-style: bold;
        height: 3;
        content-align: center middle;
        border-bottom: tall $primary-darken-2;
    }
    #decision-body {
        layout: horizontal;
        height: 1fr;
    }
    #left-panel {
        width: 35%;
        height: 100%;
        border-right: tall $primary-darken-1;
    }
    #findings-list {
        height: 100%;
        background: $background;
    }
    #findings-list:focus {
        border: double $accent;
    }
    #right-panel {
        width: 65%;
        height: 100%;
        padding: 1 2;
        background: $surface;
        overflow-y: auto;
    }
    #footer-panel {
        height: 4;
        border-top: tall $primary-darken-1;
        layout: horizontal;
        align: right middle;
        padding: 0 2;
        background: $surface-darken-1;
    }
    .panel-title {
        text-style: bold;
        padding: 0 1;
        background: $primary-darken-1;
        color: $text;
        margin-bottom: 1;
        text-align: center;
        height: 1;
    }
    .profile-selection-list {
        height: 12;
        border: round $primary;
        padding: 0 1;
        background: $background;
    }
    .profile-selection-list:focus {
        border: double $accent;
    }
    .button-bar {
        margin-left: 1;
    }
    RadioSet {
        border: round $primary;
        background: $background;
        padding: 0 1;
        margin-bottom: 1;
    }
    RadioSet:focus {
        border: double $accent;
    }
    """

    BINDINGS = [
        Binding("escape,q,Q", "back", "Volver"),
        Binding("g,G", "generate_sql", "Generar SQL"),
    ]

    def __init__(
        self,
        entries: tuple[DiffEntry, ...],
        profiles: tuple[ConnectionProfile, ...],
        repo_root: Path,
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.entries = entries
        self.profiles = profiles
        self.repo_root = repo_root
        self.profile_names = tuple(p.name for p in self.profiles)
        
        # State: maps entry -> (target_attributes, tuple_of_dest_profiles)
        # Keys are DiffEntry for non-merged entries, MergedMissingTable/MergedMissingColumn for merged groups.
        self.decisions: dict = {}
        self.table_by_id: dict[str, str] = {}
        
        # Populate initial decisions for entries that won't be merged below.
        for entry in self.entries:
            if not isinstance(entry, (MissingTable, MissingColumn)):
                self.decisions[entry] = self.get_default_decision(entry)

        # Group raw entries by unique table key
        self.table_groups: dict[str, list[DiffEntry]] = {}
        for entry in self.entries:
            schema, table = entry.qualified_name
            tbl_key = f"{schema}.{table}"
            self.table_groups.setdefault(tbl_key, []).append(entry)
        self.table_keys = sorted(self.table_groups.keys())

        # Build display groups: collapse all MissingTable/MissingColumn siblings for the same identity
        # into MergedMissingTable / MergedMissingColumn so the UI shows one decision card per finding.
        self.display_groups: dict[str, list] = {}
        for tbl_key, grp_entries in self.table_groups.items():
            missing_tbl_entries = [e for e in grp_entries if isinstance(e, MissingTable)]
            non_tbl_entries = [e for e in grp_entries if not isinstance(e, MissingTable)]

            display: list = []
            if missing_tbl_entries:
                first = missing_tbl_entries[0]
                merged_tbl = MergedMissingTable(
                    schema_name=first.schema_name,
                    table_name=first.table_name,
                    missing_from_profiles=tuple(
                        sorted(e.missing_from_profile for e in missing_tbl_entries)
                    ),
                    present_columns=first.present_columns,
                )
                display.append(merged_tbl)
                self.decisions[merged_tbl] = self.get_default_decision(merged_tbl)

            # Process non-table entries while preserving order and merging MissingColumn siblings
            seen_merged_cols: set[str] = set()
            for entry in non_tbl_entries:
                if isinstance(entry, MissingColumn):
                    col_name = entry.column_name
                    if col_name not in seen_merged_cols:
                        seen_merged_cols.add(col_name)
                        siblings = [e for e in non_tbl_entries if isinstance(e, MissingColumn) and e.column_name == col_name]
                        merged_col = MergedMissingColumn(
                            schema_name=entry.schema_name,
                            table_name=entry.table_name,
                            column_name=entry.column_name,
                            missing_from_profiles=tuple(
                                sorted(e.missing_from_profile for e in siblings)
                            ),
                            present_attributes=entry.present_attributes,
                        )
                        display.append(merged_col)
                        self.decisions[merged_col] = self.get_default_decision(merged_col)
                else:
                    display.append(entry)

            self.display_groups[tbl_key] = display

    def compose(self) -> ComposeResult:
        with Container(id="decision-container"):
            yield Label("Fase de Decisiones: Consolidación de Esquemas", id="decision-title")
            with Container(id="decision-body"):
                with Vertical(id="left-panel"):
                    yield Label("Tablas con discrepancias", classes="panel-title")
                    yield ListView(id="findings-list")
                with Vertical(id="right-panel"):
                    yield Label("Selecciona una tabla de la lista", id="empty-state-label")
            with Horizontal(id="footer-panel"):
                yield Button("Cancelar [Esc]", variant="error", id="btn-cancel")
                yield Button("Generar SQL [G]", variant="success", id="btn-generate", classes="button-bar")

    def on_mount(self) -> None:
        self.populate_list()

    def populate_list(self) -> None:
        list_view = self.query_one("#findings-list", ListView)
        list_view.clear()
        self.table_by_id.clear()
        
        for i, tbl_key in enumerate(self.table_keys):
            entries = self.display_groups[tbl_key]
            title = f" 📋 {tbl_key} ({len(entries)} hallazgo{'s' if len(entries) > 1 else ''})"
            item_id = f"table-item-{i}"
            item = ListItem(Label(title), id=item_id)
            list_view.append(item)
            self.table_by_id[item_id] = tbl_key

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item and event.item.id in self.table_by_id:
            tbl_key = self.table_by_id[event.item.id]
            self.show_resolution_form(tbl_key)

    def get_default_decision(self, entry) -> tuple:
        if isinstance(entry, ColumnMismatch):
            _, target_attrs = entry.values_by_profile[0]
            default_dests = tuple(
                prof for prof, attrs in entry.values_by_profile
                if attrs != target_attrs
            )
            return target_attrs, default_dests
            
        elif isinstance(entry, MissingColumn):
            if entry.present_attributes:
                _, target_attrs = entry.present_attributes[0]
                return target_attrs, (entry.missing_from_profile,)

        elif isinstance(entry, MergedMissingColumn):
            if entry.present_attributes:
                _, target_attrs = entry.present_attributes[0]
                return target_attrs, entry.missing_from_profiles
                
        elif isinstance(entry, MissingTable):
            if entry.present_columns:
                source_prof, _ = entry.present_columns[0]
                return source_prof, (entry.missing_from_profile,)

        elif isinstance(entry, MergedMissingTable):
            if entry.present_columns:
                source_prof, _ = entry.present_columns[0]
                # Default CREATE targets ALL absent profiles
                return source_prof, entry.missing_from_profiles
            
        return None, ()

    def show_resolution_form(self, tbl_key: str) -> None:
        right_panel = self.query_one("#right-panel")
        right_panel.remove_children()
        
        # Header title for selected table
        right_panel.mount(Label(f"[bold underline]Consolidación de Tabla:[/bold underline] [cyan]{tbl_key}[/cyan]", classes="table-header-title"))
        right_panel.mount(Label(""))
        
        entries = self.display_groups[tbl_key]
        for entry in entries:
            right_panel.mount(ColumnResolutionWidget(entry, self))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.action_back()
        elif event.button.id == "btn-generate":
            self.action_generate_sql()

    def action_back(self) -> None:
        self.dismiss(None)

    def action_generate_sql(self) -> None:
        from schema_comparator.compare.consolidation import (
            ColumnDeletionResolution,
            ColumnResolution,
            TableDeletionResolution,
            TableResolution,
            write_sql_scripts,
        )

        resolutions = []
        table_resolutions = []
        table_deletions = []
        column_deletions = []
        for entry, (target, dests) in self.decisions.items():
            if target is not None and dests:
                schema, table = entry.qualified_name
                if isinstance(entry, (MissingTable, MergedMissingTable)):
                    if target is TableAction.DROP:
                        # Only drop from profiles where the table actually exists.
                        # For MergedMissingTable this guards against absent profiles
                        # accidentally appearing in dests.
                        if isinstance(entry, MergedMissingTable):
                            present_profiles = {prof for prof, _ in entry.present_columns}
                            actual_dests = tuple(d for d in dests if d in present_profiles)
                        else:
                            actual_dests = tuple(dests)
                        if actual_dests:
                            table_deletions.append(
                                TableDeletionResolution(
                                    schema_name=schema,
                                    table_name=table,
                                    profiles_to_update=actual_dests,
                                )
                            )
                    else:
                        source_prof = target
                        # For MergedMissingTable, only create in profiles where table is absent.
                        if isinstance(entry, MergedMissingTable):
                            absent_profiles = set(entry.missing_from_profiles)
                            actual_dests = tuple(d for d in dests if d in absent_profiles)
                        else:
                            actual_dests = tuple(dests)
                        columns = None
                        for prof, cols in entry.present_columns:
                            if prof == source_prof:
                                columns = cols
                                break
                        if columns and actual_dests:
                            table_resolutions.append(
                                TableResolution(
                                    schema_name=schema,
                                    table_name=table,
                                    columns=columns,
                                    profiles_to_update=actual_dests,
                                )
                            )
                else:
                    is_missing = isinstance(entry, (MissingColumn, MergedMissingColumn))
                    if target is ColumnAction.DROP:
                        present_profiles = {
                            profile_name
                            for profile_name, _ in (
                                entry.present_attributes
                                if isinstance(entry, (MissingColumn, MergedMissingColumn))
                                else entry.values_by_profile
                            )
                        }
                        actual_dests = tuple(d for d in dests if d in present_profiles)
                        if actual_dests:
                            column_deletions.append(
                                ColumnDeletionResolution(
                                    schema_name=schema,
                                    table_name=table,
                                    column_name=entry.column_name,
                                    profiles_to_update=actual_dests,
                                )
                            )
                    else:
                        if isinstance(entry, MergedMissingColumn):
                            absent_profiles = set(entry.missing_from_profiles)
                            actual_dests = tuple(d for d in dests if d in absent_profiles)
                        else:
                            actual_dests = tuple(dests)
                        if actual_dests:
                            resolutions.append(
                                ColumnResolution(
                                    schema_name=schema,
                                    table_name=table,
                                    column_name=entry.column_name,
                                    target_attributes=target,
                                    profiles_to_update=actual_dests,
                                    is_missing_column=is_missing,
                                )
                            )

        if not resolutions and not table_resolutions and not table_deletions and not column_deletions:
            self.app.notify("No se seleccionó ninguna corrección para generar SQL.", severity="warning")
            return

        try:
            generated_files = write_sql_scripts(
                resolutions, self.repo_root, list(self.profiles),
                table_resolutions=table_resolutions,
                table_deletions=table_deletions,
                column_deletions=column_deletions,
            )
            self.dismiss(generated_files)
        except Exception as exc:
            self.app.notify(f"Error al generar scripts: {exc}", severity="error")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Delegate RadioSet change event to the corresponding ColumnResolutionWidget."""
        for widget in self.query(ColumnResolutionWidget):
            try:
                if widget.query_one(RadioSet) == event.radio_set:
                    widget.handle_radio_change(event.index)
                    break
            except Exception:
                pass

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        """Delegate SelectionList change event to the corresponding ColumnResolutionWidget."""
        for widget in self.query(ColumnResolutionWidget):
            try:
                if widget.query_one(SelectionList) == event.selection_list:
                    widget.handle_selection_change(event.selection_list.selected)
                    break
            except Exception:
                pass


class ColumnResolutionWidget(Container):
    """Modular card containing form controls to resolve a single column's differences."""

    DEFAULT_CSS = """
    ColumnResolutionWidget {
        border: round $primary-darken-1;
        background: $panel;
        padding: 1 2;
        margin-bottom: 1;
        height: auto;
    }
    .column-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    .dest-label {
        margin-top: 1;
        text-style: bold;
    }
    """

    def __init__(self, entry: DiffEntry, decision_screen: DecisionScreen, **kwargs) -> None:
        super().__init__(**kwargs)
        self.entry = entry
        self.decision_screen = decision_screen
        self.options = self.build_options()
        
    def build_options(self) -> list[tuple]:
        options = []
        if isinstance(self.entry, ColumnMismatch):
            attr_to_profiles = {}
            for prof, attrs in self.entry.values_by_profile:
                attr_to_profiles.setdefault(attrs, []).append(prof)
                
            for attrs, profs in attr_to_profiles.items():
                label = f"{format_attributes(attrs)}  (ej. en: {', '.join(profs)})"
                options.append((attrs, label))
            options.append((ColumnAction.DROP, "Eliminar columna de perfiles donde existe"))
            options.append((None, "Ignorar discrepancia (no generar cambios)"))
            
        elif isinstance(self.entry, (MissingColumn, MergedMissingColumn)):
            attr_to_profiles = {}
            for prof, attrs in self.entry.present_attributes:
                attr_to_profiles.setdefault(attrs, []).append(prof)
                
            for attrs, profs in attr_to_profiles.items():
                label = f"Agregar como {format_attributes(attrs)}  (copiar de: {', '.join(profs)})"
                options.append((attrs, label))
            options.append((ColumnAction.DROP, "Eliminar columna de perfiles donde existe"))
            options.append((None, "No agregar (Ignorar)"))
            
        elif isinstance(self.entry, (MissingTable, MergedMissingTable)):
            for prof, cols in self.entry.present_columns:
                col_count = len(cols)
                label = f"Crear con definición de '{prof}' ({col_count} columnas)"
                options.append((prof, label))  # value is the source profile name
            options.append((TableAction.DROP, "Eliminar tabla de perfiles donde existe"))
            options.append((None, "Ignorar (no crear)"))
            
        return options

    def compose(self) -> ComposeResult:
        if isinstance(self.entry, (MissingTable, MergedMissingTable)):
            # Build the title label depending on single vs merged
            if isinstance(self.entry, MergedMissingTable):
                absent_str = ", ".join(self.entry.missing_from_profiles)
                yield Label(
                    f"Tabla: [bold]{self.entry.schema_name}.{self.entry.table_name}[/bold]"
                    f" (Tabla Faltante en [bold]{absent_str}[/bold])",
                    classes="column-title",
                )
            else:
                yield Label(
                    f"Tabla: [bold]{self.entry.schema_name}.{self.entry.table_name}[/bold]"
                    f" (Tabla Faltante en [bold]{self.entry.missing_from_profile}[/bold])",
                    classes="column-title",
                )
            
            decision = self.decision_screen.decisions.get(self.entry)
            target, selected_profiles = decision
            
            active_index = len(self.options) - 1
            for i, (val, _) in enumerate(self.options):
                if val == target:
                    active_index = i
                    break
            
            yield Label("[bold]Seleccionar perfil fuente para la definición:[/bold]")
            radio_set = RadioSet(
                *[RadioButton(label, value=(i == active_index)) for i, (_, label) in enumerate(self.options)]
            )
            yield radio_set
            
            # Show column preview of the currently selected source
            if target is not None and target is not TableAction.DROP:
                for prof, cols in self.entry.present_columns:
                    if prof == target:
                        col_preview = ", ".join(f"[cyan]{c.name}[/cyan]" for c in cols[:10])
                        if len(cols) > 10:
                            col_preview += f" ... (+{len(cols) - 10} más)"
                        yield Label(f"[dim]Columnas: {col_preview}[/dim]")
                        break
            
            is_drop = target is TableAction.DROP
            yield Label(
                "[bold]Eliminar tabla en:[/bold]" if is_drop else "[bold]Crear tabla en:[/bold]",
                classes="dest-label",
            )
            selection_list = SelectionList(classes="profile-selection-list")
            # For DROP: show present profiles. For CREATE: show absent profiles.
            if isinstance(self.entry, MergedMissingTable):
                destination_profiles = (
                    [prof for prof, _ in self.entry.present_columns]
                    if is_drop
                    else list(self.entry.missing_from_profiles)
                )
            else:
                destination_profiles = (
                    [prof for prof, _ in self.entry.present_columns]
                    if is_drop
                    else [self.entry.missing_from_profile]
                )
            for profile_name in destination_profiles:
                selection_list.add_option((
                    profile_name,
                    profile_name,
                    profile_name in selected_profiles,
                ))
            selection_list.disabled = (target is None)
            yield selection_list
            return

        if isinstance(self.entry, MergedMissingColumn):
            absent_str = ", ".join(self.entry.missing_from_profiles)
            yield Label(
                f"Columna: [bold]{self.entry.column_name}[/bold] (Columna Faltante en [bold]{absent_str}[/bold])",
                classes="column-title",
            )
        else:
            diff_type = "Discrepancia de Atributos" if isinstance(self.entry, ColumnMismatch) else "Columna Faltante"
            yield Label(f"Columna: [bold]{self.entry.column_name}[/bold] ({diff_type})", classes="column-title")
        
        # RadioSet
        decision = self.decision_screen.decisions.get(self.entry)
        target_attrs, selected_profiles = decision
        
        active_index = len(self.options) - 1
        for i, (attrs, _) in enumerate(self.options):
            if attrs == target_attrs:
                active_index = i
                break
                
        yield Label("[bold]Seleccionar definición correcta:[/bold]")
        radio_set = RadioSet(
            *[RadioButton(label, value=(i == active_index)) for i, (_, label) in enumerate(self.options)]
        )
        yield radio_set
        
        # SelectionList
        is_drop = target_attrs is ColumnAction.DROP
        yield Label(
            "[bold]Eliminar columna en:[/bold]" if is_drop else "[bold]Aplicar corrección en:[/bold] (Presiona [Espacio] para marcar/desmarcar)",
            classes="dest-label",
        )
        if is_drop:
            dest_profiles = [
                profile_name
                for profile_name, _ in (
                    self.entry.present_attributes
                    if isinstance(self.entry, (MissingColumn, MergedMissingColumn))
                    else self.entry.values_by_profile
                )
            ]
        else:
            if isinstance(self.entry, ColumnMismatch):
                dest_profiles = list(self.decision_screen.profile_names)
            elif isinstance(self.entry, MergedMissingColumn):
                dest_profiles = list(self.entry.missing_from_profiles)
            else:
                dest_profiles = [self.entry.missing_from_profile]
        
        selection_list = SelectionList(classes="profile-selection-list")
        for p in dest_profiles:
            selection_list.add_option((p, p, p in selected_profiles))
            
        selection_list.disabled = (target_attrs is None)
        yield selection_list

    def handle_radio_change(self, idx: int) -> None:
        """Handle option changes from the radio button set."""
        if idx < 0 or idx >= len(self.options):
            return
            
        target, _ = self.options[idx]
        selection_list = self.query_one(SelectionList)
        
        if target is None:
            selection_list.disabled = True
            selection_list.deselect_all()
            self.decision_screen.decisions[self.entry] = (None, ())
        elif isinstance(self.entry, (MissingTable, MergedMissingTable)):
            selection_list.disabled = False
            is_drop = target is TableAction.DROP
            # For DROP: destination = profiles where table EXISTS (present_columns).
            # For CREATE: destination = profiles where table is ABSENT.
            if isinstance(self.entry, MergedMissingTable):
                default_dests = (
                    tuple(prof for prof, _ in self.entry.present_columns)
                    if is_drop
                    else self.entry.missing_from_profiles
                )
                destination_profiles = (
                    [prof for prof, _ in self.entry.present_columns]
                    if is_drop
                    else list(self.entry.missing_from_profiles)
                )
            else:
                default_dests = (
                    tuple(prof for prof, _ in self.entry.present_columns)
                    if is_drop
                    else (self.entry.missing_from_profile,)
                )
                destination_profiles = (
                    [prof for prof, _ in self.entry.present_columns]
                    if is_drop
                    else [self.entry.missing_from_profile]
                )
            selection_list.clear_options()
            for profile_name in destination_profiles:
                selection_list.add_option((
                    profile_name,
                    profile_name,
                    profile_name in default_dests,
                ))
            self.decision_screen.decisions[self.entry] = (target, default_dests)
        elif target is ColumnAction.DROP:
            selection_list.disabled = False
            default_dests = tuple(
                profile_name
                for profile_name, _ in (
                    self.entry.present_attributes
                    if isinstance(self.entry, (MissingColumn, MergedMissingColumn))
                    else self.entry.values_by_profile
                )
            )
            selection_list.clear_options()
            for profile_name in default_dests:
                selection_list.add_option((profile_name, profile_name, True))
            self.decision_screen.decisions[self.entry] = (target, default_dests)
        else:
            selection_list.disabled = False
            if isinstance(self.entry, ColumnMismatch):
                default_dests = tuple(
                    prof for prof, attrs in self.entry.values_by_profile
                    if attrs != target
                )
                dest_profiles = list(self.decision_screen.profile_names)
            elif isinstance(self.entry, MergedMissingColumn):
                default_dests = self.entry.missing_from_profiles
                dest_profiles = list(self.entry.missing_from_profiles)
            else:
                default_dests = (self.entry.missing_from_profile,)
                dest_profiles = [self.entry.missing_from_profile]
                
            selection_list.clear_options()
            for p in dest_profiles:
                selection_list.add_option((p, p, p in default_dests))
                
            self.decision_screen.decisions[self.entry] = (target, default_dests)

    def handle_selection_change(self, selected_items: list[str]) -> None:
        """Handle selected profiles changes from the selection list."""
        decision = self.decision_screen.decisions.get(self.entry)
        if decision:
            target, _ = decision
            self.decision_screen.decisions[self.entry] = (target, tuple(selected_items))

