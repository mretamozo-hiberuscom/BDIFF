"""Textual widget subclasses for the interactive findings browser.

Each widget calls into `formatting.py` to build its content but owns no
comparison-specific business logic itself.
"""

from datetime import datetime

from rich.text import Text
from textual.widgets import Input, RichLog, Static, Tree

from schema_comparator.compare.models import ComparisonResult, DiffEntry
from schema_comparator.tui.formatting import (
    TableGroup,
    TreeData,
    detail_markup,
    entry_matches,
    group_markup,
    leaf_parts,
    profiles_markup,
    summary_markup,
)
from schema_comparator.tui.theme import FAIL, kind_style

_NO_SELECTION_MESSAGE = "Selecciona un hallazgo para ver los detalles."

_GUIDE = f"""[dim]{_NO_SELECTION_MESSAGE}[/dim]

[bold]Para empezar[/bold]
  [bold]↑ ↓[/bold]  recorre los hallazgos
  [bold]/[/bold]    filtra por tabla, columna o tipo
  [bold]c[/bold]    decide qué corregir y genera los scripts
  [bold]?[/bold]    ayuda y todos los atajos"""


class SummaryHeader(Static):
    """Title, compared profiles and one chip per kind of finding."""

    def show(self, result: ComparisonResult) -> None:
        self.update(
            Text.from_markup(
                f"[bold]BDIFF[/bold]  [dim]{profiles_markup(result)}[/dim]\n"
                f"{summary_markup(result)}"
            )
        )


class DetailPanel(Static):
    """Detail panel for the currently selected finding or table."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(Text.from_markup(_GUIDE), *args, **kwargs)

    def show(self, selection: DiffEntry | TableGroup | None) -> None:
        """Render the card of a finding, the summary of a table, or the
        guide when nothing is selected."""
        if selection is None:
            markup = _GUIDE
        elif isinstance(selection, TableGroup):
            markup = group_markup(selection)
        else:
            markup = detail_markup(selection)
        self.update(Text.from_markup(markup))


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
        self.border_title = "Hallazgos"

    def on_mount(self) -> None:
        self.populate(self._tree_data)

    def _styled_leaf_label(self, entry: DiffEntry) -> Text:
        """Symbol and subject in the colour of the kind of finding."""
        style = kind_style(entry)
        subject, description = leaf_parts(entry)
        label = Text()
        label.append(f"{style.symbol} ", style=f"bold {style.color}")
        if subject:
            label.append(subject, style="bold")
            label.append(": ")
        label.append(description, style=style.color)
        return label

    def _group_label(self, group: TableGroup, shown: int) -> Text:
        label = Text(group.qualified_label)
        label.append(f"  ({shown})", style="dim")
        return label

    def _fill(self, filter_text: str) -> None:
        self.root.remove_children()
        total = sum(len(group.entries) for group in self._tree_data.groups)
        shown = 0
        for group in self._tree_data.groups:
            entries = [e for e in group.entries if entry_matches(e, filter_text)]
            if not entries:
                continue
            shown += len(entries)
            group_node = self.root.add(
                self._group_label(group, len(entries)), data=group, expand=True
            )
            for entry in entries:
                group_node.add_leaf(self._styled_leaf_label(entry), data=entry)
        self.border_title = (
            f"Hallazgos ({shown} de {total})" if filter_text else f"Hallazgos ({total})"
        )
        self.border_subtitle = "Sin coincidencias" if filter_text and not shown else ""

    def populate(self, tree_data: TreeData) -> None:
        """Rebuild the tree: one root child per `TableGroup`, one leaf per
        entry in the group, each leaf's `data` set to the originating
        `DiffEntry`."""
        self._tree_data = tree_data
        self._fill("")

    def apply_filter(self, filter_text: str) -> None:
        """Rebuild the visible tree from `self._tree_data`, keeping only
        entries matching `filter_text` and hiding groups with zero
        remaining matches."""
        self._fill(filter_text)


class StatusLog(RichLog):
    """Append-only status/progress panel for run-comparison and
    generate-reports outcomes. Never receives raw stdout; only the
    explicit messages `app.py`'s worker methods write to it."""

    def _stamped(self, message: str, marker: str = "", style: str = "") -> Text:
        line = Text(f"{datetime.now():%H:%M:%S}  ", style="dim")
        line.append(f"{marker}{message}", style=style)
        return line

    def info(self, message: str) -> None:
        self.write(self._stamped(message))

    def error(self, message: str) -> None:
        self.write(self._stamped(message, f"{FAIL} ", "red"))


class ExcludeEditor(Input):
    """Input pre-seeded with the current exclude-pattern list, space-
    separated, matching `--exclude-tables`'s existing CLI syntax."""

    def __init__(self, initial_patterns: list[str], **kwargs) -> None:
        kwargs.setdefault(
            "placeholder",
            "Fragmentos de nombre separados por espacio (p. ej. LOG QRTZ)",
        )
        super().__init__(value=" ".join(initial_patterns), **kwargs)
