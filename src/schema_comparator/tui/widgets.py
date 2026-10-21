"""Textual widget subclasses for the interactive findings browser.

Each widget calls into `formatting.py` to build its content but owns no
comparison-specific business logic itself.
"""

from rich.markup import escape
from rich.text import Text
from textual.widgets import Input, RichLog, Static, Tree

from schema_comparator.compare.models import (
    ColumnMismatch,
    DiffEntry,
    MissingColumn,
    MissingTable,
)
from schema_comparator.domain.comparison.models import column_label, object_label
from schema_comparator.report.attributes import format_attributes
from schema_comparator.tui.formatting import (
    TreeData,
    detail_text,
    entry_matches,
    leaf_label,
)

_NO_SELECTION_MESSAGE = "Seleccioná un hallazgo para ver los detalles."


class SummaryHeader(Static):
    """Static header rendering `header_text(result)` once at mount time."""


class DetailPanel(Static):
    """Detail panel for the currently selected finding leaf."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(_NO_SELECTION_MESSAGE, *args, **kwargs)

    def show(self, entry: DiffEntry | None) -> None:
        """Render a styled Rich detail card for the selected DiffEntry,
        or a neutral placeholder when no leaf is selected."""
        if entry is None:
            self.update(f"[dim]{_NO_SELECTION_MESSAGE}[/dim]")
            return

        if isinstance(entry, ColumnMismatch):
            markup = [
                "[bold cyan]🔍 Detalle de Discrepancia de Atributos[/]",
                f"[bold]Tabla:[/bold] {escape(object_label(entry))}",
                f"[bold]Columna:[/bold] [yellow]{escape(column_label(entry))}[/]",
                "",
                "[bold underline]Definición por Perfil de Conexión:[/bold underline]",
            ]
            for profile, attrs in entry.values_by_profile:
                markup.append(
                    f"  • [bold]{escape(profile)}:[/bold] [green]{escape(format_attributes(attrs))}[/]"
                )
            self.update("\n".join(markup))

        elif isinstance(entry, MissingColumn):
            markup = [
                "[bold orange3]➖ Detalle de Columna Faltante[/]",
                f"[bold]Tabla:[/bold] {escape(object_label(entry))}",
                f"[bold]Columna:[/bold] [orange3]{escape(column_label(entry))}[/]",
                "",
                f"⚠️ [bold red]Faltante en el perfil:[/bold red] [bold underline]{escape(entry.missing_from_profile)}[/]",
                "",
                "[bold underline]Definición en perfiles presentes:[/bold underline]",
            ]
            for profile, attrs in entry.present_attributes:
                markup.append(
                    f"  • [bold]{escape(profile)}:[/bold] [green]{escape(format_attributes(attrs))}[/]"
                )
            self.update("\n".join(markup))

        elif isinstance(entry, MissingTable):
            markup = [
                "[bold red]✖ Detalle de Tabla Faltante[/]",
                f"[bold]Tabla:[/bold] [red]{escape(object_label(entry))}[/]",
                "",
                f"⚠️ [bold red]Faltante en el perfil:[/bold red] [bold underline]{escape(entry.missing_from_profile)}[/]",
            ]
            self.update("\n".join(markup))
        else:
            self.update(detail_text(entry))


class FindingsTree(Tree):
    """Tree of findings grouped by table, with live substring filtering.

    Filtering rebuilds the tree from a filtered `TreeData` snapshot
    (rather than toggling per-node visibility flags), per design §4.1 and
    tasks.md 3.2 — this keeps the tree contents simple and directly
    testable.
    """

    def __init__(self, tree_data: TreeData, *args, **kwargs) -> None:
        super().__init__("Hallazgos", *args, **kwargs)
        self._tree_data = tree_data
        self.show_root = False

    def on_mount(self) -> None:
        self.populate(self._tree_data)

    def _styled_leaf_label(self, entry: DiffEntry) -> Text:
        """Build a visually rich, colored label for tree leaf nodes."""
        if isinstance(entry, MissingTable):
            return Text.from_markup(
                f"[bold red]✖[/] [red]tabla faltante[/] (de [bold]{escape(entry.missing_from_profile)}[/bold])"
            )
        if isinstance(entry, MissingColumn):
            return Text.from_markup(
                f"[bold orange3]➖[/] [bold orange3]{escape(column_label(entry))}[/]: [orange3]columna faltante[/] (de [bold]{escape(entry.missing_from_profile)}[/bold])"
            )
        if isinstance(entry, ColumnMismatch):
            profiles = ", ".join(p for p, _ in entry.values_by_profile)
            return Text.from_markup(
                f"[bold yellow]≠[/] [bold yellow]{escape(column_label(entry))}[/]: [yellow]discrepancia de atributos[/] entre [bold]{escape(profiles)}[/bold]"
            )
        return Text(leaf_label(entry))

    def populate(self, tree_data: TreeData) -> None:
        """Rebuild the tree: one root child per `TableGroup`, one leaf per
        entry in the group, each leaf's `data` set to the originating
        `DiffEntry`."""
        self._tree_data = tree_data
        self.root.remove_children()
        for group in tree_data.groups:
            group_node = self.root.add(Text(group.qualified_label), expand=True)
            for entry in group.entries:
                group_node.add_leaf(self._styled_leaf_label(entry), data=entry)

    def apply_filter(self, filter_text: str) -> None:
        """Rebuild the visible tree from `self._tree_data`, keeping only
        entries matching `filter_text` and hiding groups with zero
        remaining matches."""
        filtered_groups = tuple(
            group
            for group in self._tree_data.groups
            if any(entry_matches(entry, filter_text) for entry in group.entries)
        )
        self.root.remove_children()
        for group in filtered_groups:
            group_node = self.root.add(Text(group.qualified_label), expand=True)
            for entry in group.entries:
                if entry_matches(entry, filter_text):
                    group_node.add_leaf(self._styled_leaf_label(entry), data=entry)


class StatusLog(RichLog):
    """Append-only status/progress panel for run-comparison and
    generate-reports outcomes. Never receives raw stdout; only the
    explicit messages `app.py`'s worker methods write to it."""

    def info(self, message: str) -> None:
        self.write(Text(message))

    def error(self, message: str) -> None:
        self.write(Text(message, style="red"))


class ExcludeEditor(Input):
    """Input pre-seeded with the current exclude-pattern list, space-
    separated, matching `--exclude-tables`'s existing CLI syntax."""

    def __init__(self, initial_patterns: list[str], **kwargs) -> None:
        kwargs.setdefault(
            "placeholder",
            "Tablas a excluir, separadas por espacio (p. ej. LOG QRTZ) — "
            "Enter para aplicar y re-ejecutar la comparación",
        )
        super().__init__(value=" ".join(initial_patterns), **kwargs)
