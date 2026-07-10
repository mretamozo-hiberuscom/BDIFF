# Interactive TUI Specification

## Purpose

Provide an opt-in, read-only interactive terminal browser for a
`ComparisonResult`, launched via the `--tui` CLI flag, that lets a user
navigate, filter, and inspect findings (`MissingTable`, `MissingColumn`,
`ColumnMismatch`) grouped by table, as an alternative to the plain-text
console summary produced by `reporting-and-output`. This capability MUST
consume `ComparisonResult`/`DiffEntry` read-only and MUST NOT reshape or
re-derive any comparison/diff-detection logic, and MUST NOT affect
whether or how HTML/PDF report generation occurs.

## Non-Goals

This capability MUST NOT implement any diff-detection logic, connection
management screens (list/add/edit/delete connections), a "run/re-extract"
action from within the TUI, any write/editing action against
`ComparisonResult` or underlying schemas, or HTML/PDF rendering/theming.
These remain out of scope and are addressed, if ever, by separate future
changes.

## Clarifications

### Session 2026-07-10

- Q: Does `--tui` change whether HTML/PDF reports are generated?
  → A: **No.** HTML and PDF generation are unconditional and run
  identically whether or not `--tui` is passed; `--tui` only selects
  which summary presentation (plain console vs. interactive TUI) is shown
  after HTML/PDF generation completes.
- Q: What happens when `--tui` is passed but stdout/stdin is not a TTY
  (e.g. piped output, CI)?
  → A: The system MUST fall back to the plain console summary, MUST print
  a clear warning message, and MUST exit 0 — this is not treated as an
  error condition.
- Q: What is the v1 interaction scope of the TUI?
  → A: A single-screen, read-only findings browser: a tree of findings
  grouped by table (consistent with the console summary's grouping), a
  live substring filter over diff-type/table/column, collapse/expand of
  table groups, and a quit key binding. No editing or write actions exist.
- Q: What happens when a `ComparisonResult` has no findings?
  → A: The TUI MUST clearly communicate "no drift detected", consistent
  with the equivalent HTML/PDF/console-summary behavior.
- Q: What happens if the TUI itself fails to render/run?
  → A: The failure MUST NOT prevent HTML/PDF report generation, since
  those steps already complete before the summary-presentation step is
  reached in `write_reports`'s existing ordering.

### Session 2026-07-10 (follow-up)

- Q: Is the detail panel showing the full `values_by_profile` breakdown
  for a selected `ColumnMismatch` (proposal Scope, In Scope bullet 3) a
  formal normative requirement, and what does it show for `MissingTable`/
  `MissingColumn` leaves?
  → A: **Yes, formal normative requirement.** For a selected
  `ColumnMismatch`, the detail panel MUST show the full
  `values_by_profile` breakdown, one row/line per profile with its
  `ColumnAttributes`. For a selected `MissingTable` or `MissingColumn`
  leaf, the detail panel MUST show the profile(s) missing the object,
  consistent with each entry type's simpler shape (no `ColumnAttributes`
  breakdown, since neither carries one).
- Q: Is the header showing `compared_profiles` and per-category counts
  (proposal Scope, In Scope bullet 4) a formal normative requirement, and
  must it match the plain console summary's counts?
  → A: **Yes, formal normative requirement.** The header MUST show the
  list of `compared_profiles` and the count of each diff-entry category
  (`MissingTable`/`MissingColumn`/`ColumnMismatch`), consistent with the
  existing plain-console summary's category counts
  (`src/schema_comparator/report/console.py`).

## Requirements

### Requirement: Launch Interactive TUI via Opt-In `--tui` Flag {#REQ-interactive-tui-001}

The system MUST provide an opt-in `--tui` CLI flag, off by default. When
`--tui` is passed and the current process is running on an interactive
terminal (per REQ-interactive-tui-002), the system MUST launch the
interactive TUI in place of the plain console summary as the final
presentation step of the run. HTML and PDF report generation MUST proceed
unchanged and unconditionally regardless of whether `--tui` is passed.

#### Scenario: `--tui` on an interactive terminal launches the TUI instead of the console summary

- GIVEN the CLI is invoked with `--tui` on an interactive terminal (both
  stdout and stdin are TTYs)
- WHEN the run reaches its summary-presentation step
- THEN the interactive TUI SHALL be launched
- AND the plain-text console summary SHALL NOT be printed in its place

#### Scenario: HTML and PDF generation are unaffected by `--tui`

- GIVEN the CLI is invoked with `--tui` on an interactive terminal
- WHEN the run completes
- THEN the HTML report file and PDF report file SHALL be generated
  identically to a run without `--tui`

#### Scenario: Omitting `--tui` preserves the existing plain console summary

- GIVEN the CLI is invoked without `--tui`
- WHEN the run reaches its summary-presentation step
- THEN the plain-text console summary SHALL be printed, as before this
  capability existed
- AND the interactive TUI SHALL NOT be launched

### Requirement: Fall Back to Console Summary on a Non-Interactive Terminal {#REQ-interactive-tui-002}

When `--tui` is passed but stdout or stdin is not a TTY, the system MUST
NOT attempt to launch the interactive TUI. Instead, it MUST print a clear
warning message to `stderr` indicating that `--tui` requires an
interactive terminal and that the plain console summary is being used
instead, and it MUST then print the plain console summary exactly as if
`--tui` had not been passed. This fallback MUST NOT be treated as an
error: the overall process exit code MUST be 0 for an otherwise
successful comparison run.

#### Scenario: `--tui` with piped stdout falls back to the console summary

- GIVEN the CLI is invoked with `--tui` and its stdout is piped to a file
  or another process (not a TTY)
- WHEN the run reaches its summary-presentation step
- THEN a warning message SHALL be printed to `stderr` stating that `--tui`
  requires an interactive terminal and that the plain console summary is
  being used
- AND the plain-text console summary SHALL be printed in place of the TUI

#### Scenario: Fallback does not fail the run

- GIVEN the CLI is invoked with `--tui` in a non-interactive terminal
  (e.g. a CI job) and the comparison itself completes successfully
- WHEN the run completes
- THEN the process exit code SHALL be 0
- AND the fallback SHALL NOT be reported as an error

#### Scenario: `--tui` with piped stdin also triggers fallback

- GIVEN the CLI is invoked with `--tui` and its stdin is not a TTY (e.g.
  redirected from a file), even if stdout is a TTY
- WHEN the run reaches its summary-presentation step
- THEN the system SHALL fall back to the plain console summary with the
  same warning behavior as REQ-interactive-tui-002's other scenarios

### Requirement: Navigate Findings Grouped by Table {#REQ-interactive-tui-003}

Given a `ComparisonResult`, the TUI MUST present findings grouped by
qualified table identity (`schema.table`), consistent with the grouping
already used by the plain console summary, with each table group
expandable to reveal its individual findings (`MissingTable`,
`MissingColumn`, `ColumnMismatch` entries). The user MUST be able to
navigate between groups and findings using keyboard input.

#### Scenario: Findings are grouped by qualified table identity

- GIVEN a `ComparisonResult` with findings for `sales.Invoice` and
  `sales.Payment`
- WHEN the TUI is launched
- THEN the findings browser SHALL present one group per qualified table
  identity, `sales.Invoice` and `sales.Payment`

#### Scenario: A table group expands to reveal its individual findings

- GIVEN a table group for `sales.Invoice` containing a `MissingColumn`
  entry for `notes` and a `ColumnMismatch` entry for `amount`
- WHEN the user expands the `sales.Invoice` group
- THEN both the `notes` missing-column finding and the `amount` mismatch
  finding SHALL become visible as entries under that group

#### Scenario: Keyboard navigation moves focus between findings

- GIVEN the TUI is displaying at least two findings
- WHEN the user presses a navigation key (arrow keys or `j`/`k`)
- THEN keyboard focus SHALL move to the next or previous navigable node in
  the findings tree

### Requirement: Filter Findings by Table or Diff Type {#REQ-interactive-tui-004}

The TUI MUST provide a filter input that performs a live substring match
against each finding's diff-type label (`MissingTable`, `MissingColumn`,
`ColumnMismatch`), qualified table identity, or column name. Findings (and
their table groups, when the group has no remaining matches) that do not
match the current filter text MUST be hidden from the visible tree while
the filter is active.

#### Scenario: Filtering by diff-type label hides non-matching findings

- GIVEN a `ComparisonResult` with `MissingTable`, `MissingColumn`, and
  `ColumnMismatch` findings across several tables
- WHEN the user enters `ColumnMismatch` into the filter input
- THEN only `ColumnMismatch` findings SHALL remain visible in the tree
- AND `MissingTable` and `MissingColumn` findings SHALL be hidden

#### Scenario: Filtering by table name hides unrelated table groups

- GIVEN findings exist for both `sales.Invoice` and `sales.Payment`
- WHEN the user enters `Invoice` into the filter input
- THEN the `sales.Invoice` group and its findings SHALL remain visible
- AND the `sales.Payment` group SHALL be hidden, since none of its
  findings match the filter text

#### Scenario: Clearing the filter restores all findings

- GIVEN a filter has hidden some findings
- WHEN the user clears the filter input
- THEN all findings SHALL become visible again, matching the
  unfiltered state

### Requirement: Collapse and Expand Table Groups {#REQ-interactive-tui-005}

The TUI MUST allow the user to collapse an expanded table group (hiding
its individual findings while keeping the group header visible) and to
re-expand a collapsed group, via a key binding (`Enter`/`Space`).

#### Scenario: Collapsing a group hides its findings but keeps the group visible

- GIVEN an expanded table group for `sales.Invoice` showing its findings
- WHEN the user collapses the group
- THEN the `sales.Invoice` group header SHALL remain visible
- AND its individual findings SHALL no longer be visible

#### Scenario: Re-expanding a collapsed group reveals its findings again

- GIVEN a collapsed table group for `sales.Invoice`
- WHEN the user expands the group again
- THEN its individual findings SHALL become visible again

### Requirement: Quit the TUI via a Key Binding {#REQ-interactive-tui-006}

The TUI MUST provide a key binding (`q` or `Escape`) that exits the TUI
and returns control to the CLI, without performing any write or editing
action against the underlying `ComparisonResult` or any schema.

#### Scenario: Pressing the quit key binding exits the TUI

- GIVEN the TUI is running
- WHEN the user presses `q` or `Escape`
- THEN the TUI SHALL exit
- AND control SHALL return to the CLI without any further TUI interaction

### Requirement: Communicate a Clean Comparison in the TUI {#REQ-interactive-tui-007}

When a `ComparisonResult`'s diff-entry sequence is empty (no drift
detected across all compared profiles), the TUI MUST clearly communicate
that no drift was detected, consistent with the equivalent HTML, PDF, and
plain console summary behavior, rather than rendering an empty or
ambiguous findings tree.

#### Scenario: TUI communicates a clean comparison

- GIVEN a `ComparisonResult` with an empty diff-entry sequence naming
  compared profiles `a` and `b`
- WHEN the TUI is launched
- THEN the TUI SHALL display an explicit "no drift detected" message
- AND SHALL NOT render an empty findings tree with no explanatory content

### Requirement: TUI Failure MUST NOT Prevent Prior Report Generation {#REQ-interactive-tui-008}

If the TUI fails to launch or crashes during rendering for any reason,
this MUST NOT prevent HTML and PDF report generation, since those steps
already complete before the summary-presentation step is reached. A TUI
failure MUST be reported clearly rather than silently swallowed, and MUST
NOT propagate as an unhandled exception that leaves the terminal in a
corrupted state.

#### Scenario: HTML and PDF reports already exist when the TUI fails

- GIVEN a comparison run with `--tui` on an interactive terminal, where
  HTML and PDF report generation both succeed before the summary step
- WHEN the TUI subsequently fails to render
- THEN the HTML and PDF report files SHALL remain written and unaffected
  by the TUI failure

#### Scenario: A TUI failure is reported clearly rather than crashing the run

- GIVEN the TUI encounters an unexpected error while rendering
- WHEN the failure occurs
- THEN the failure SHALL be reported clearly (e.g. via a console message)
- AND the run SHALL NOT terminate with an unhandled/raw stack trace that
  leaves the terminal unusable

### Requirement: Detail Panel Shows Full Attribute Breakdown for a Selected Finding {#REQ-interactive-tui-009}

The TUI MUST provide a detail panel that renders additional information
for the currently selected finding leaf. When the selected leaf is a
`ColumnMismatch`, the detail panel MUST show the full `values_by_profile`
breakdown, with one row/line per profile displaying that profile's
`ColumnAttributes` (`data_type`, `character_maximum_length`,
`numeric_precision`, `numeric_scale`, `is_nullable`). When the selected
leaf is a `MissingTable` or `MissingColumn`, the detail panel MUST instead
show the profile(s) missing the object (`missing_from_profile`),
consistent with each entry type's simpler shape, which carries no
`ColumnAttributes` to break down.

#### Scenario: Selecting a ColumnMismatch leaf shows the full values_by_profile breakdown

- GIVEN a `ColumnMismatch` finding for column `amount` with
  `values_by_profile` entries for profiles `a` and `b`, each with distinct
  `ColumnAttributes`
- WHEN the user selects the `amount` finding leaf in the tree
- THEN the detail panel SHALL show one row/line per profile in
  `values_by_profile`
- AND each row/line SHALL display that profile's `ColumnAttributes`
  (`data_type`, `character_maximum_length`, `numeric_precision`,
  `numeric_scale`, `is_nullable`)

#### Scenario: Selecting a MissingTable leaf shows the profile missing the table

- GIVEN a `MissingTable` finding for `sales.Invoice` with
  `missing_from_profile` set to `b`
- WHEN the user selects that finding leaf in the tree
- THEN the detail panel SHALL show that the table is missing from profile
  `b`
- AND SHALL NOT attempt to render a `values_by_profile`/`ColumnAttributes`
  breakdown, since `MissingTable` carries none

#### Scenario: Selecting a MissingColumn leaf shows the profile missing the column

- GIVEN a `MissingColumn` finding for column `notes` on `sales.Invoice`
  with `missing_from_profile` set to `a`
- WHEN the user selects that finding leaf in the tree
- THEN the detail panel SHALL show that the `notes` column is missing from
  profile `a`
- AND SHALL NOT attempt to render a `values_by_profile`/`ColumnAttributes`
  breakdown, since `MissingColumn` carries none

### Requirement: Header Shows Compared Profiles and Category Counts {#REQ-interactive-tui-010}

The TUI MUST render a header showing the list of `compared_profiles` and
the count of findings in each diff-entry category (`MissingTable`,
`MissingColumn`, `ColumnMismatch`) present in the `ComparisonResult`. These
counts MUST be consistent with the equivalent counts already computed by
the plain console summary (`src/schema_comparator/report/console.py`),
i.e. the header MUST NOT present different totals than a
`render_console` invocation on the same `ComparisonResult` would report
under "Findings by category".

#### Scenario: Header lists compared profiles

- GIVEN a `ComparisonResult` with `compared_profiles` naming `a`, `b`, and
  `c`
- WHEN the TUI is launched
- THEN the header SHALL display the list of compared profiles `a`, `b`,
  and `c`

#### Scenario: Header shows counts per diff-entry category matching the console summary

- GIVEN a `ComparisonResult` with 2 `MissingTable` entries, 1
  `MissingColumn` entry, and 3 `ColumnMismatch` entries
- WHEN the TUI is launched
- THEN the header SHALL show a count of 2 for `MissingTable`, 1 for
  `MissingColumn`, and 3 for `ColumnMismatch`
- AND these counts SHALL match the category counts `render_console` would
  report for the same `ComparisonResult`

## RFC 2119 Keyword Legend

MUST/SHALL denote absolute requirements; MUST NOT/SHALL NOT denote
absolute prohibitions; SHOULD/MAY denote recommended or optional
behavior. No SHOULD/MAY-level requirements apply in this capability.
