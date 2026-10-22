"""TUI view for consolidating schema mismatches and missing columns (fase de decisiones).

The decision logic lives in `decision_model`; this module only renders it.
"""

from dataclasses import replace
from pathlib import Path

from rich.markup import escape
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    ListItem,
    ListView,
    RadioButton,
    RadioSet,
    SelectionList,
    Static,
)

from schema_comparator.compare.consolidation import ColumnAction, TableAction
from schema_comparator.compare.models import (
    ColumnMismatch,
    DiffEntry,
    MissingColumn,
    MissingTable,
)
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.report.attributes import format_attributes
from schema_comparator.tui.decision_model import (
    ColumnOptions,
    DecisionEntry,
    DropItem,
    MergedMissingColumn,
    MergedMissingTable,
    build_resolutions,
    default_destinations,
    destination_choices,
    drops_in,
    group_findings,
    may_lose_data,
    needs_fill_value,
)
from schema_comparator.tui.modals import ConfirmModal
from schema_comparator.tui.theme import FAIL, OK, SEPARATOR, kind_style

__all__ = [
    "ColumnResolutionWidget",
    "DecisionScreen",
    "MergedMissingColumn",
    "MergedMissingTable",
]


_KIND_OF_CARD = {
    MergedMissingTable: MissingTable,
    MergedMissingColumn: MissingColumn,
    ColumnMismatch: ColumnMismatch,
}


def _card_symbol(entry: DecisionEntry) -> Text:
    """The symbol of the kind of finding a card resolves, in its colour."""
    style = kind_style(_KIND_OF_CARD[type(entry)])
    return Text(f"{style.symbol} ", style=f"bold {style.color}")


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _drops_markup(drops: tuple[DropItem, ...]) -> str:
    lines = [
        f"  [red]{FAIL}[/] {escape(item.kind)} [bold]{escape(item.name)}[/bold]"
        f" en {escape(', '.join(item.profiles))}"
        for item in drops
    ]
    return (
        "El script va a eliminar:\n"
        + "\n".join(lines)
        + "\n\nAntes de cada DROP copia los datos a un respaldo en el esquema"
        " [bold]bdiff_respaldo[/bold] y genera un script de deshacer."
        " BDIFF no ejecuta nada: revisa los scripts antes de aplicarlos."
    )


def _fill_destinations(
    selection_list: SelectionList, choices: tuple[str, ...], selected: tuple[str, ...]
) -> None:
    selection_list.clear_options()
    for profile_name in choices:
        selection_list.add_option(
            (escape(profile_name), profile_name, profile_name in selected)
        )


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
        width: 100%;
        text-align: center;
        background: $primary;
        color: $text;
        text-style: bold;
        height: 3;
        content-align: center middle;
        border-bottom: tall $primary-darken-2;
    }
    #decision-summary {
        height: 1;
        padding: 0 2;
        background: $surface-darken-1;
        color: $text-muted;
    }
    #decision-body {
        layout: horizontal;
        height: 1fr;
    }
    #left-panel {
        width: 40%;
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
        width: 60%;
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
        Binding("escape", "back", "Cancelar"),
        Binding("g,G", "generate_sql", "Generar SQL"),
        Binding("v,V", "open_sp_verification", "Verificar SPs"),
    ]

    def __init__(
        self,
        entries: tuple[DiffEntry, ...],
        profiles: tuple[ConnectionProfile, ...],
        repo_root: Path,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.entries = entries
        self.profiles = profiles
        self.repo_root = repo_root
        self.profile_names = tuple(p.name for p in self.profiles)
        self.table_by_id: dict[str, str] = {}
        self._table_labels: dict[str, Label] = {}

        # One decision card per merged finding; every decision starts as
        # (None, ()) — "do nothing" — until the user picks a target.
        self.display_groups = group_findings(entries)
        self.table_keys = sorted(self.display_groups)
        self.decisions: dict[DecisionEntry, tuple[object, tuple[str, ...]]] = {
            card: (None, ()) for cards in self.display_groups.values() for card in cards
        }
        # Fill value and accepted data loss of column fixes, by card.
        self.column_options: dict[DecisionEntry, ColumnOptions] = {}

    def compose(self) -> ComposeResult:
        with Container(id="decision-container"):
            yield Label(
                "Consolidar esquemas: decide qué corregir y genera los scripts",
                id="decision-title",
            )
            yield Static("", id="decision-summary")
            with Container(id="decision-body"):
                with Vertical(id="left-panel"):
                    yield Label("Tablas", classes="panel-title")
                    yield ListView(id="findings-list")
                with Vertical(id="right-panel"):
                    yield Label(
                        "Elige una tabla de la lista para decidir cada hallazgo.\n"
                        "Marca la definición correcta y los perfiles donde aplicarla.",
                        id="empty-state-label",
                    )
            with Horizontal(id="footer-panel"):
                yield Button("Cancelar [Esc]", variant="default", id="btn-cancel")
                yield Button(
                    "Verificar SPs [V]",
                    variant="default",
                    id="btn-verify-sps",
                    classes="button-bar",
                )
                yield Button(
                    "Generar SQL [G]",
                    variant="success",
                    id="btn-generate",
                    classes="button-bar",
                )

    def on_mount(self) -> None:
        self.populate_list()
        self.refresh_status()

    def _is_decided(self, card: DecisionEntry) -> bool:
        target, destinations = self.decisions.get(card, (None, ()))
        return target is not None and bool(destinations)

    def _table_label(self, tbl_key: str) -> Text:
        cards = self.display_groups[tbl_key]
        decided = sum(self._is_decided(card) for card in cards)
        label = Text()
        label.append(f"{OK} " if decided else "  ", style="bold green")
        label.append(tbl_key, style="bold")
        label.append(
            f"  {SEPARATOR} {_plural(len(cards), 'hallazgo', 'hallazgos')}",
            style="dim",
        )
        return label

    def refresh_status(self) -> None:
        """Re-draw the table list and the summary line from the decisions."""
        for item_id, tbl_key in self.table_by_id.items():
            self._table_labels[item_id].update(self._table_label(tbl_key))
        total = sum(len(cards) for cards in self.display_groups.values())
        decided = sum(self._is_decided(card) for card in self.decisions)
        drops = len(drops_in(self._resolutions()))
        summary = f"{decided} de {total} hallazgos con decisión"
        if drops:
            summary += f"  {SEPARATOR}  {drops} DROP"
        self.query_one("#decision-summary", Static).update(summary)

    def _resolutions(self):
        return build_resolutions(self.decisions, self.column_options)

    def populate_list(self) -> None:
        list_view = self.query_one("#findings-list", ListView)
        list_view.clear()
        self.table_by_id.clear()
        self._table_labels.clear()

        for i, tbl_key in enumerate(self.table_keys):
            item_id = f"table-item-{i}"
            label = Label(self._table_label(tbl_key))
            list_view.append(ListItem(label, id=item_id))
            self.table_by_id[item_id] = tbl_key
            self._table_labels[item_id] = label

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item and event.item.id in self.table_by_id:
            tbl_key = self.table_by_id[event.item.id]
            self.show_resolution_form(tbl_key)

    def show_resolution_form(self, tbl_key: str) -> None:
        right_panel = self.query_one("#right-panel")
        right_panel.remove_children()

        # Header title for selected table
        right_panel.mount(
            Label(
                Text.assemble(("Tabla  ", "dim"), (tbl_key, "bold cyan")),
                classes="table-header-title",
            )
        )
        right_panel.mount(Label(""))

        entries = self.display_groups[tbl_key]
        for entry in entries:
            right_panel.mount(ColumnResolutionWidget(entry, self))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.action_back()
        elif event.button.id == "btn-verify-sps":
            self.action_open_sp_verification()
        elif event.button.id == "btn-generate":
            self.action_generate_sql()

    def action_back(self) -> None:
        if not any(self._is_decided(card) for card in self.decisions):
            self.dismiss(None)
            return

        def discard(confirmed: bool | None) -> None:
            if confirmed:
                self.dismiss(None)

        self.app.push_screen(
            ConfirmModal(
                "¿Descartar las decisiones?",
                "Has marcado correcciones que todavía no se han generado."
                " Si sales ahora se pierden.",
                confirm_label="Descartar",
                cancel_label="Seguir decidiendo",
                severity="warning",
            ),
            discard,
        )

    def action_open_sp_verification(self) -> None:
        from schema_comparator.tui.procedure_screen import ProcedureVerificationScreen

        exclude_patterns = getattr(self.app, "_exclude_routines", [])
        self.app.push_screen(
            ProcedureVerificationScreen(
                profiles=self.profiles,
                repo_root=self.repo_root,
                exclude_patterns=exclude_patterns,
            )
        )

    def action_generate_sql(self) -> None:
        resolutions = self._resolutions()
        if resolutions.is_empty():
            self.app.notify(
                "No se seleccionó ninguna corrección para generar SQL.",
                severity="warning",
            )
            return

        drops = drops_in(resolutions)
        if not drops:
            self._write_scripts(resolutions)
            return

        def generate(confirmed: bool | None) -> None:
            if confirmed:
                self._write_scripts(resolutions)

        self.app.push_screen(
            ConfirmModal(
                "¿Generar scripts con DROP?",
                _drops_markup(drops),
                confirm_label="Generar",
                cancel_label="Cancelar",
                severity="danger",
                focus_cancel=True,
            ),
            generate,
        )

    def _write_scripts(self, resolutions) -> None:
        from schema_comparator.compare.consolidation import write_sql_scripts

        try:
            generated_files = write_sql_scripts(
                resolutions.columns,
                self.repo_root,
                list(self.profiles),
                table_resolutions=resolutions.tables,
                table_deletions=resolutions.table_deletions,
                column_deletions=resolutions.column_deletions,
            )
            self.dismiss(generated_files)
        except Exception as exc:
            self.app.notify(f"Error al generar scripts: {exc}", severity="error")


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

    def __init__(
        self, entry: DecisionEntry, decision_screen: DecisionScreen, **kwargs
    ) -> None:
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
            options.append(
                (ColumnAction.DROP, "Eliminar columna de perfiles donde existe")
            )
            options.append((None, "Ignorar discrepancia (no generar cambios)"))

        elif isinstance(self.entry, MergedMissingColumn):
            attr_to_profiles = {}
            for prof, attrs in self.entry.present_attributes:
                attr_to_profiles.setdefault(attrs, []).append(prof)

            for attrs, profs in attr_to_profiles.items():
                label = f"Agregar como {format_attributes(attrs)}  (copiar de: {', '.join(profs)})"
                options.append((attrs, label))
            options.append(
                (ColumnAction.DROP, "Eliminar columna de perfiles donde existe")
            )
            options.append((None, "No agregar (Ignorar)"))

        else:
            for prof, cols in self.entry.present_columns:
                col_count = len(cols)
                label = f"Crear con definición de '{prof}' ({col_count} columnas)"
                options.append((prof, label))  # value is the source profile name
            options.append(
                (TableAction.DROP, "Eliminar tabla de perfiles donde existe")
            )
            options.append((None, "Ignorar (no crear)"))

        return options

    def _destination_title(self, target: object) -> str:
        if isinstance(self.entry, MergedMissingTable):
            return (
                "[bold]Eliminar tabla en:[/bold]"
                if target is TableAction.DROP
                else "[bold]Crear tabla en:[/bold]"
            )
        return (
            "[bold]Eliminar columna en:[/bold]"
            if target is ColumnAction.DROP
            else "[bold]Aplicar corrección en:[/bold] (Espacio marca o desmarca)"
        )

    def _radio_set(self, target: object) -> RadioSet:
        active_index = len(self.options) - 1
        for i, (value, _) in enumerate(self.options):
            if value == target:
                active_index = i
                break
        return RadioSet(
            *[
                RadioButton(escape(label), value=(i == active_index))
                for i, (_, label) in enumerate(self.options)
            ]
        )

    def _selection_list(
        self, target: object, selected_profiles: tuple[str, ...]
    ) -> SelectionList:
        selection_list = SelectionList(classes="profile-selection-list")
        _fill_destinations(
            selection_list,
            destination_choices(self.entry, target),
            selected_profiles,
        )
        selection_list.disabled = target is None
        return selection_list

    def compose(self) -> ComposeResult:
        target, selected_profiles = self.decision_screen.decisions.get(
            self.entry, (None, ())
        )

        if isinstance(self.entry, MergedMissingTable):
            absent_str = ", ".join(self.entry.missing_from_profiles)
            yield Label(
                f"Tabla: [bold]{escape(f'{self.entry.schema_name}.{self.entry.table_name}')}[/bold]"
                f" (Tabla Faltante en [bold]{escape(absent_str)}[/bold])",
                classes="column-title",
            )
            yield Label("[bold]Seleccionar perfil fuente para la definición:[/bold]")
            yield self._radio_set(target)

            # Show column preview of the currently selected source
            if target is not None and target is not TableAction.DROP:
                cols = dict(self.entry.present_columns).get(target)
                if cols is not None:
                    col_preview = ", ".join(
                        f"[cyan]{escape(c.name)}[/cyan]" for c in cols[:10]
                    )
                    if len(cols) > 10:
                        col_preview += f" ... (+{len(cols) - 10} más)"
                    yield Label(f"[dim]Columnas: {col_preview}[/dim]")

            yield Label(
                self._destination_title(target), classes="dest-label dest-title"
            )
            yield self._selection_list(target, selected_profiles)
            return

        if isinstance(self.entry, MergedMissingColumn):
            absent_str = ", ".join(self.entry.missing_from_profiles)
            yield Label(
                f"Columna: [bold]{escape(self.entry.column_name)}[/bold] (Columna Faltante en [bold]{escape(absent_str)}[/bold])",
                classes="column-title",
            )
        else:
            yield Label(
                f"Columna: [bold]{escape(self.entry.column_name)}[/bold] (Discrepancia de Atributos)",
                classes="column-title",
            )

        yield Label("[bold]Seleccionar definición correcta:[/bold]")
        yield self._radio_set(target)
        yield Label(self._destination_title(target), classes="dest-label dest-title")
        yield self._selection_list(target, selected_profiles)

        options = self.decision_screen.column_options.get(self.entry, ColumnOptions())
        yield Label(
            "[bold]Valor para filas con NULL[/bold] (vacío: el script aborta si hay)",
            classes="dest-label fill-label",
        )
        yield Input(
            value=options.backfill_value or "",
            placeholder="valor de relleno",
            classes="fill-value",
        )
        yield Checkbox(
            "Aceptar pérdida de datos (truncar, redondear, no convertible)",
            value=options.accept_data_loss,
            classes="accept-loss",
        )

    def on_mount(self) -> None:
        target, selected = self.decision_screen.decisions.get(self.entry, (None, ()))
        self._refresh_data_controls(target, selected)

    def _refresh_data_controls(
        self, target: object, destinations: tuple[str, ...]
    ) -> None:
        if isinstance(self.entry, MergedMissingTable):
            return
        fill = needs_fill_value(target)
        for widget in self.query(".fill-label, .fill-value"):
            widget.display = fill
        self.query_one(".accept-loss", Checkbox).display = may_lose_data(
            self.entry, target, destinations
        )

    def _set_options(self, **changes) -> None:
        current = self.decision_screen.column_options.get(self.entry, ColumnOptions())
        self.decision_screen.column_options[self.entry] = replace(current, **changes)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.has_class("fill-value"):
            self._set_options(backfill_value=event.value)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.has_class("accept-loss"):
            self._set_options(accept_data_loss=event.value)

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self.handle_radio_change(event.index)

    def on_selection_list_selected_changed(
        self, event: SelectionList.SelectedChanged
    ) -> None:
        self.handle_selection_change(event.selection_list.selected)

    def handle_radio_change(self, idx: int) -> None:
        """Handle option changes from the radio button set."""
        if idx < 0 or idx >= len(self.options):
            return

        target, _ = self.options[idx]
        self.query_one(".dest-title", Label).update(self._destination_title(target))
        selection_list = self.query_one(SelectionList)
        if target is None:
            selection_list.disabled = True
            selection_list.deselect_all()
            self.decision_screen.decisions[self.entry] = (None, ())
            self._refresh_data_controls(None, ())
            self.decision_screen.refresh_status()
            return

        defaults = default_destinations(self.entry, target)
        selection_list.disabled = False
        _fill_destinations(
            selection_list,
            destination_choices(self.entry, target),
            defaults,
        )
        self.decision_screen.decisions[self.entry] = (target, defaults)
        self._refresh_data_controls(target, defaults)
        self.decision_screen.refresh_status()

    def handle_selection_change(self, selected_items: list[str]) -> None:
        """Handle selected profiles changes from the selection list."""
        decision = self.decision_screen.decisions.get(self.entry)
        if decision:
            target, _ = decision
            self.decision_screen.decisions[self.entry] = (target, tuple(selected_items))
            self._refresh_data_controls(target, tuple(selected_items))
            self.decision_screen.refresh_status()
