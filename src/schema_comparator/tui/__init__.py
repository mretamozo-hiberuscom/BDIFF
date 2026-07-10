"""Read-only interactive findings browser for a ComparisonResult.

Launched via the CLI's --tui flag on an interactive terminal (see
schema_comparator.cli): a single-screen Textual app presenting findings
grouped by table, with live substring filtering, collapse/expand of table
groups, a detail panel for the selected finding, and a quit key binding.
No connection-management screens and no run/re-extract action exist here
— those are not implemented by this module. See
openspec/changes/interactive-tui/proposal.md Decision 5 for the scope
correction rationale.
"""

from schema_comparator.tui.app import SchemaComparatorApp, run_tui

__all__ = ["SchemaComparatorApp", "run_tui"]
