"""Textual widget subclasses for the interactive findings browser.

Each widget calls into `formatting.py` to build its content but owns no
comparison-specific business logic itself.
"""

from textual.widgets import Static, Tree

from schema_comparator.compare.models import DiffEntry
from schema_comparator.tui.formatting import (
    TreeData,
    detail_text,
    entry_matches,
    header_text,
    leaf_label,
)

_NO_SELECTION_MESSAGE = "Select a finding to see details."


class SummaryHeader(Static):
    """Static header rendering `header_text(result)` once at mount time."""


class DetailPanel(Static):
    """Detail panel for the currently selected finding leaf."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(_NO_SELECTION_MESSAGE, *args, **kwargs)

    def show(self, entry: DiffEntry | None) -> None:
        """Render `detail_text(entry)`, or a neutral placeholder when no
        leaf (e.g. a group header) is selected."""
        if entry is None:
            self.update(_NO_SELECTION_MESSAGE)
            return
        self.update(detail_text(entry))


class FindingsTree(Tree):
    """Tree of findings grouped by table, with live substring filtering.

    Filtering rebuilds the tree from a filtered `TreeData` snapshot
    (rather than toggling per-node visibility flags), per design §4.1 and
    tasks.md 3.2 — this keeps the tree contents simple and directly
    testable.
    """

    def __init__(self, tree_data: TreeData, *args, **kwargs) -> None:
        super().__init__("Findings", *args, **kwargs)
        self._tree_data = tree_data
        self.show_root = False

    def on_mount(self) -> None:
        self.populate(self._tree_data)

    def populate(self, tree_data: TreeData) -> None:
        """Rebuild the tree: one root child per `TableGroup`, one leaf per
        entry in the group, each leaf's `data` set to the originating
        `DiffEntry`."""
        self._tree_data = tree_data
        self.root.remove_children()
        for group in tree_data.groups:
            group_node = self.root.add(group.qualified_label, expand=True)
            for entry in group.entries:
                group_node.add_leaf(leaf_label(entry), data=entry)

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
            group_node = self.root.add(group.qualified_label, expand=True)
            for entry in group.entries:
                if entry_matches(entry, filter_text):
                    group_node.add_leaf(leaf_label(entry), data=entry)
