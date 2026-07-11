# Spec Delta: Interactive TUI (Run & Report Actions)

Status: extends the existing baseline at
`openspec/specs/interactive-tui/spec.md` (capability `interactive-tui`).
This delta ADDS three new Requirements (in-memory exclude editing, run
comparison, generate reports on demand) and NARROWS the baseline's
Non-Goals section. It does not fork a new domain and does not modify the
baseline file directly; merging happens at archive time.

Scope reminder (per proposal.md): exclude-list edits are in-memory only
for the current session and are never persisted to any YAML file. "Run
comparison" and "generate reports" are additive actions on top of the
existing read-only findings browser; no connection-management screen
(list/add/edit/delete connections, choosing which profiles to compare) is
introduced by this change.

## Clarifications

### Session 2026-07-11

- **Q: When `--tui` is passed and the interactive TUI actually launches,
  does the pre-existing unconditional HTML/PDF/Excel generation at
  startup still happen, in addition to the new on-demand "generate
  reports" action?**
  A: **No.** Per the corresponding MODIFIED requirement in
  `reporting-and-output` below, automatic upfront generation is skipped
  specifically when the interactive TUI launches; those formats are
  produced only via the new in-TUI action. Every other invocation shape
  (`--tui` omitted, or falling back to the plain console on a non-TTY)
  is unaffected and keeps generating all formats unconditionally at
  startup.
- **Q: Does editing the exclude list in the TUI persist back to
  `config.local.yaml` or any other file?**
  A: **No.** The exclude list edited in the TUI exists only in memory for
  the current session/run. No file is read for or written by this
  editing action.
- **Q: Does committing an exclude-list edit automatically re-run the
  comparison, or does the user need a separate action?**
  A: Committing an edit (`Enter`) both updates the in-memory exclude list
  and immediately triggers a comparison re-run using it. A separate
  binding (`r`) re-runs the comparison without changing the exclude list,
  for observing live schema drift since launch.

## MODIFIED Non-Goals

The baseline's Non-Goals section currently reads:

> This capability MUST NOT implement any diff-detection logic, connection
> management screens (list/add/edit/delete connections), a "run/re-extract"
> action from within the TUI, any write/editing action against
> `ComparisonResult` or underlying schemas, or HTML/PDF rendering/theming.
> These remain out of scope and are addressed, if ever, by separate future
> changes.

It is narrowed to:

> This capability MUST NOT implement any diff-detection logic, connection
> management screens (list/add/edit/delete connections, or choosing which
> profiles to compare), any write/editing action against a
> `ComparisonResult`'s diff entries themselves, or HTML/PDF/Excel
> rendering/theming internals. These remain out of scope and are
> addressed, if ever, by separate future changes. A "run/re-extract"
> action, in-memory (session-only, non-persisted) exclude-table-list
> editing, and on-demand HTML/PDF/Excel report generation are in scope as
> of REQ-interactive-tui-011, REQ-interactive-tui-012, and
> REQ-interactive-tui-013; the exclude list edited in the TUI MUST NOT be
> written back to any configuration file.

## ADDED Requirements

### Requirement: Edit the Excluded-Tables List In Memory {#REQ-interactive-tui-011}

The TUI MUST provide an exclude-tables editor, seeded with whatever
patterns were passed via the CLI's `--exclude-tables` flag at launch (or
empty if none were given), that lets the user replace the current
in-memory list of table-name substring exclusion patterns for the
duration of the current session/run only. Committing an edit MUST update
the in-memory exclude list and MUST immediately trigger a comparison
re-run (REQ-interactive-tui-012) using the new list. This editor MUST NOT
read from or write to `config.local.yaml`, `config.example.yaml`, or any
other file.

#### Scenario: Exclude editor is seeded from the CLI flag at launch

- GIVEN the CLI was invoked with `--exclude-tables LOG QRTZ`
- WHEN the TUI's exclude editor is opened
- THEN it SHALL display `LOG` and `QRTZ` as the current exclude patterns

#### Scenario: Committing a new exclude list updates in-memory state and re-runs the comparison

- GIVEN the TUI is displaying a `ComparisonResult` for the current exclude
  list
- WHEN the user opens the exclude editor, replaces the pattern list, and
  commits the edit
- THEN the in-memory exclude list SHALL be updated to the new patterns
- AND a comparison re-run SHALL be triggered using the new list
  (REQ-interactive-tui-012)

#### Scenario: Exclude edits are never persisted to a file

- GIVEN the user has edited the exclude list one or more times during a
  TUI session
- WHEN the TUI session ends
- THEN no configuration file on disk SHALL have been read from or written
  to as a result of any exclude-list edit made during that session

### Requirement: Re-Run Comparison From Within the TUI {#REQ-interactive-tui-012}

The TUI MUST provide a "run comparison" action, bound to a dedicated key
(`r`), that re-extracts schemas for the profiles the CLI loaded at
launch, re-applies the current in-memory exclude-pattern list, re-runs
the comparison, and replaces the displayed `ComparisonResult` with the
new one. This action MUST execute without blocking the TUI's
responsiveness (keyboard input and rendering) for its duration, and MUST
show an in-progress indicator while running. If the re-run fails (e.g. a
connection or extraction error), the TUI MUST report the failure clearly
via a status/log panel and MUST leave the previously displayed
`ComparisonResult` unchanged.

#### Scenario: Running comparison replaces the displayed findings

- GIVEN the TUI is displaying findings for an initial `ComparisonResult`
- WHEN the user triggers the "run comparison" action and it completes
  successfully
- THEN the findings tree SHALL be replaced with the new `ComparisonResult`'s
  findings

#### Scenario: The TUI remains responsive while comparison runs

- GIVEN the user has triggered the "run comparison" action
- WHEN extraction and comparison are still in progress
- THEN the TUI SHALL continue to accept keyboard input (e.g. navigating
  the still-displayed prior findings, or quitting)
- AND an in-progress indicator SHALL be visible

#### Scenario: A failed re-run does not clear or corrupt the displayed findings

- GIVEN the TUI is displaying findings for a `ComparisonResult`
- WHEN the user triggers "run comparison" and it fails (e.g. a database
  connection error)
- THEN the failure SHALL be reported clearly in a status/log panel
- AND the previously displayed `ComparisonResult` and its findings tree
  SHALL remain unchanged

### Requirement: Generate Reports On Demand From Within the TUI {#REQ-interactive-tui-013}

The TUI MUST provide a "generate reports" action, bound to a dedicated
key (`g`), that produces a fresh, timestamped HTML/PDF/Excel report
triple for the currently displayed `ComparisonResult`, using the same
per-format-isolated generation logic and naming convention
`write_reports` uses for its outputs (REQ-reporting-and-output-001
through REQ-reporting-and-output-004, REQ-reporting-and-output-002's
timestamped naming convention). A failure in one format MUST NOT prevent
the other formats from being generated, and MUST NOT crash the TUI.
Generation progress and per-format outcomes MUST be shown via a
status/log panel, never printed directly to the raw terminal stream in a
way that would corrupt the TUI's rendered screen.

#### Scenario: Generating reports produces all three formats for the current result

- GIVEN the TUI is displaying findings for a `ComparisonResult` (whether
  from launch or from a subsequent "run comparison")
- WHEN the user triggers the "generate reports" action and it completes
  successfully
- THEN an HTML file, a PDF file, and an Excel file SHALL be written to
  disk, sharing the same run timestamp

#### Scenario: A single format's failure does not block the others

- GIVEN the user triggers "generate reports" and PDF export fails while
  HTML and Excel generation succeed
- WHEN the action completes
- THEN the HTML and Excel files SHALL still be written
- AND the PDF failure SHALL be reported clearly in the status/log panel
- AND the TUI SHALL NOT crash or exit as a result

#### Scenario: Report generation output does not corrupt the TUI's rendered screen

- GIVEN the "generate reports" action is triggered
- WHEN generation succeeds or fails for any format
- THEN all resulting status/outcome messages SHALL appear within the
  TUI's own status/log panel
- AND no raw text SHALL be printed directly to the terminal in a way that
  disrupts the TUI's rendering
