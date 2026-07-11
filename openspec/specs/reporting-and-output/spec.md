# Reporting and Output Specification

## Purpose

Turn a `ComparisonResult` (from `comparison-engine`, including the
`MissingTable`, `MissingColumn`, and `ColumnMismatch` diff-entry variants)
into the three human-facing artifacts committed to for Milestone 1: a
self-contained HTML report, a PDF export derived from that same HTML, and
a plain-text console summary. This capability MUST consume
`ComparisonResult`/`DiffEntry` read-only and MUST NOT reshape or re-derive
any comparison/diff-detection logic.

## Non-Goals

This capability MUST NOT implement any diff-detection logic, likely-rename
heuristics, the interactive Textual TUI shell, configurable HTML/PDF
theming beyond the Pico.css + overlay decision, persistence/versioning of
past reports, or CLI output-format selection (all three outputs are always
generated in v1). These remain out of scope and are addressed, if ever, by
separate future changes.

## Clarifications

### Session 2026-07-10

- Q: What filename/location convention MUST HTML and PDF report files
  follow?
  → A: **Timestamped filenames in the current working directory**, pattern
  `schema-diff-report-YYYYMMDD-HHMMSS.html` and
  `schema-diff-report-YYYYMMDD-HHMMSS.pdf`, both derived from a single run
  timestamp shared by both files so a pair from the same run is
  identifiable by matching suffix. No configurable output directory exists
  in v1.
- Q: How are N-way findings laid out in the HTML/PDF report?
  → A: **One column per compared profile**, in a table whose header row
  lists every `compared_profiles` name in the deterministic order already
  provided by `ComparisonResult`; rows are grouped/sub-headed by qualified
  table identity and ordered per the engine's existing deterministic
  ordering (`MissingTable` < `MissingColumn` < `ColumnMismatch`, then
  column name ascending).
- Q: Does the CLI support selecting a subset of output formats
  (HTML/PDF/console)?
  → A: **No.** v1 always generates all three outputs unconditionally; no
  `--format` flag exists. This is an explicit, reversible v1 scope
  decision, not a permanent constraint.
- Q: What happens if PDF export fails (e.g. `xhtml2pdf` cannot render some
  CSS construct)?
  → A: PDF generation failure MUST be isolated — it MUST NOT prevent HTML
  generation or the console summary from completing, and MUST NOT crash
  the overall run. The failure MUST be surfaced to the user (e.g. as a
  clearly labeled error/warning in console output), not silently dropped.

### Final Review 2026-07-10

No material ambiguities found; reviewed on 2026-07-10. The 7 requirements
and 20 scenarios were checked against the proposal's four decisions
(naming convention, N-way column layout, no-format-selection CLI, new
dependencies) for gaps that would block or mislead `sdd-design`; none
were found. Minor items noted as non-blocking (left to `sdd-design`'s
discretion, not requiring a spec change): the exact compact-string
format for `ColumnAttributes` cells, and the precise console per-table
breakdown layout — both are illustrated by example in the proposal/spec
without being over-constrained, which is intentional.

## Requirements

### Requirement: Render Self-Contained HTML Report {#REQ-reporting-and-output-001}

Given a `ComparisonResult`, the system MUST render a single self-contained
HTML string (inline CSS only, no external asset loads) that includes every
diff entry in the result (`MissingTable`, `MissingColumn`, and
`ColumnMismatch`), grouped/sub-headed by qualified table identity and
ordered per the engine's deterministic ordering (ascending qualified table
identity, then `MissingTable` < `MissingColumn` < `ColumnMismatch`, then
column name ascending). The header row of each table's findings MUST list
every name in `compared_profiles`, in the order provided by the
`ComparisonResult`. This rendering step's output MUST be produced whenever
report generation runs for a given `ComparisonResult`, whether that run
happens automatically at CLI startup (REQ-reporting-and-output-002) or is
triggered on demand from within the interactive TUI
(`interactive-tui` REQ-interactive-tui-013); this requirement governs the
rendering itself, independent of what triggers it.

#### Scenario: HTML includes every diff entry from the result

- GIVEN a `ComparisonResult` with a `MissingTable` entry for
  `sales.Payment`, a `MissingColumn` entry for `sales.Invoice.notes`, and a
  `ColumnMismatch` entry for `sales.Invoice.amount`
- WHEN the HTML report is rendered
- THEN the rendered HTML SHALL contain content representing all three
  entries

#### Scenario: HTML groups and orders findings per the engine's deterministic ordering

- GIVEN a `ComparisonResult` whose diff-entry sequence is already ordered
  per REQ-comparison-engine-004 (`alpha.Customer` before `zeta.Report`, and
  `MissingTable` before `MissingColumn` before `ColumnMismatch` within the
  same table)
- WHEN the HTML report is rendered
- THEN the rendered HTML SHALL present findings grouped by table in that
  same relative order, without re-sorting or reshaping the sequence

#### Scenario: HTML header row lists every compared profile in result order

- GIVEN a `ComparisonResult` naming `compared_profiles` as `alpha`, `mid`,
  `zeta` in that order
- WHEN the HTML report is rendered
- THEN each findings table's header row SHALL list `alpha`, `mid`, `zeta`
  in that order, one column per profile

#### Scenario: MissingTable and MissingColumn rows mark the missing profile distinctly

- GIVEN a `MissingTable` entry for `sales.Payment` missing from profile `c`
  among compared profiles `a`, `b`, `c`
- WHEN the HTML report is rendered
- THEN the row for that entry SHALL show a distinct "missing" marker in
  profile `c`'s column
- AND profiles where the table is present SHALL NOT show that marker

#### Scenario: ColumnMismatch row renders each present profile's attributes

- GIVEN a `ColumnMismatch` entry for column `amount` of `sales.Invoice`
  naming `ColumnAttributes` for profiles `a` and `b` (a table absent from
  profile `c`, so `c` has no attributes for this column)
- WHEN the HTML report is rendered
- THEN the row for that entry SHALL render profile `a`'s and profile `b`'s
  `ColumnAttributes` as a compact string in their respective columns
- AND profile `c`'s column for that row SHALL be blank

### Requirement: Write HTML, PDF, and Excel Report Files to a Fixed `reportes/` Directory Using the Timestamped Naming Convention, Automatically at Startup Unless the Interactive TUI Launches {#REQ-reporting-and-output-002}

When writing HTML, PDF, and Excel report files to disk, the system MUST
name them `schema-diff-report-YYYYMMDD-HHMMSS.html`,
`schema-diff-report-YYYYMMDD-HHMMSS.pdf`, and
`schema-diff-report-YYYYMMDD-HHMMSS.xlsx` respectively, using a single run
timestamp shared by all three filenames, and MUST write all three files
into a `reportes/` subdirectory of the current working directory from
which the CLI was invoked (not a fixed absolute system path). The system
MUST create the `reportes/` subdirectory if it does not already exist
before writing into it. The system MUST NOT overwrite a prior run's
report files, since each run's timestamp MUST produce a distinct filename
set (barring two runs within the same second).

This automatic generation MUST happen unconditionally at CLI startup for
every invocation shape **except** when `--tui` is passed and the
interactive TUI actually launches (i.e. the terminal is interactive); in
that one case, automatic startup generation MUST be skipped, and
HTML/PDF/Excel file writing instead happens only when the user triggers
the "generate reports" action from within the TUI (`interactive-tui`
REQ-interactive-tui-013), still using this same naming convention and
`reportes/` location. When `--tui` is passed but falls back to the plain
console summary on a non-interactive terminal (`interactive-tui`
REQ-interactive-tui-002), automatic startup generation MUST still happen,
identically to a run without `--tui`.

#### Scenario: HTML, PDF, and Excel filenames share the same run timestamp

- GIVEN a comparison run completes at a given moment
- WHEN the HTML, PDF, and Excel report files are written to disk
- THEN all three filenames SHALL contain an identical `YYYYMMDD-HHMMSS`
  timestamp segment, differing only in extension

#### Scenario: Report files are written to a `reportes/` subdirectory of the invocation working directory

- GIVEN the CLI is invoked from a given working directory
- WHEN HTML, PDF, and Excel report files are written
- THEN all three files SHALL be created inside a `reportes/` subdirectory
  of that working directory
- AND that subdirectory SHALL NOT be a fixed absolute path independent of
  where the CLI was invoked from

#### Scenario: `reportes/` is created automatically when absent

- GIVEN the CLI is invoked from a working directory that does not yet
  contain a `reportes/` subdirectory
- WHEN a comparison run completes and report files are written
- THEN the `reportes/` subdirectory SHALL be created automatically
- AND the HTML, PDF, and Excel report files SHALL be written inside it
  without requiring the user to create the directory beforehand

#### Scenario: A failure creating or writing to `reportes/` for one format does not block the others

- GIVEN writing one format's file into `reportes/` fails (e.g. a
  filesystem permission error while creating the directory or writing the
  file)
- WHEN the comparison run completes
- THEN the system SHALL still attempt the other two file formats and the
  console summary, per REQ-reporting-and-output-007
- AND the failure SHALL be reported clearly rather than silently ignored

#### Scenario: Automatic generation still happens at startup without `--tui`

- GIVEN the CLI is invoked without `--tui`
- WHEN the run completes
- THEN the HTML, PDF, and Excel report files SHALL be generated
  automatically at startup into `reportes/`, exactly as before this
  change

#### Scenario: Automatic generation still happens at startup when `--tui` falls back to the console

- GIVEN the CLI is invoked with `--tui` but stdout or stdin is not a TTY
  (fallback per REQ-interactive-tui-002)
- WHEN the run completes
- THEN the HTML, PDF, and Excel report files SHALL be generated
  automatically at startup, identically to a run without `--tui`

#### Scenario: Automatic generation is skipped at startup when the interactive TUI launches

- GIVEN the CLI is invoked with `--tui` on an interactive terminal, so the
  TUI actually launches
- WHEN the run reaches its startup report-generation step
- THEN no HTML, PDF, or Excel file SHALL be written automatically at that
  point
- AND those files SHALL only be written later if and when the user
  triggers the "generate reports" action from within the TUI

### Requirement: Export PDF Derived from the Same HTML Content {#REQ-reporting-and-output-003}

The system MUST derive the PDF export from the exact HTML string produced
for the HTML report (REQ-reporting-and-output-001), passing it unmodified
into the PDF conversion step, without introducing a second/separate PDF
template or re-deriving content from `ComparisonResult` independently.

#### Scenario: PDF and HTML report originate from the same rendered content

- GIVEN a `ComparisonResult` is rendered to an HTML string
- WHEN the PDF export is produced for the same comparison run
- THEN the PDF export SHALL be generated by converting that same HTML
  string, with no independent re-rendering from `ComparisonResult`

### Requirement: Degrade Gracefully on Unsupported CSS During PDF Conversion {#REQ-reporting-and-output-004}

If the PDF conversion step encounters CSS it cannot support, the system
MUST NOT allow that failure to crash the overall run. The system MUST
report the PDF generation failure clearly (e.g. via console output) and
MUST still complete HTML generation and the console summary for that run.

#### Scenario: Unsupported CSS during PDF conversion does not crash the run

- GIVEN the rendered HTML contains a CSS construct the PDF conversion step
  cannot support
- WHEN the PDF export step is executed as part of a comparison run
- THEN the run SHALL NOT terminate with an unhandled/raw stack trace
- AND the HTML report file SHALL still be written successfully
- AND the console summary SHALL still be printed

#### Scenario: PDF conversion failure is clearly reported to the user

- GIVEN PDF conversion fails for a given run
- WHEN the run completes
- THEN the console output SHALL include a clearly labeled message
  indicating PDF generation failed, distinct from the console summary's
  diff-count reporting

### Requirement: Print Console Summary Independent of HTML/PDF Outcome {#REQ-reporting-and-output-005}

Given a `ComparisonResult`, the system MUST print a human-readable console
summary reflecting the same diff entries as the HTML/PDF outputs,
including at minimum: counts of diff entries by category (`MissingTable`,
`MissingColumn`, `ColumnMismatch`), the list of compared profiles, and a
per-table breakdown. The console summary MUST be produced directly from
`ComparisonResult`, independent of whether HTML or PDF generation
succeeded or failed.

#### Scenario: Console summary reports counts by diff category

- GIVEN a `ComparisonResult` with 2 `MissingTable` entries, 3
  `MissingColumn` entries, and 1 `ColumnMismatch` entry
- WHEN the console summary is printed
- THEN the printed output SHALL include a count of 2 for `MissingTable`, 3
  for `MissingColumn`, and 1 for `ColumnMismatch`

#### Scenario: Console summary lists compared profiles and per-table breakdown

- GIVEN a `ComparisonResult` naming compared profiles `a`, `b`, `c` with
  findings for tables `sales.Invoice` and `sales.Payment`
- WHEN the console summary is printed
- THEN the printed output SHALL list `a`, `b`, `c` as compared profiles
- AND SHALL include a breakdown identifying findings per table for
  `sales.Invoice` and `sales.Payment`

#### Scenario: Console summary prints even when HTML and PDF generation both fail

- GIVEN HTML report generation and PDF export both fail for a given run
- WHEN the run completes
- THEN the console summary SHALL still be printed, reflecting the same
  `ComparisonResult` diff entries

### Requirement: Communicate Clean Comparisons Across All Three Outputs {#REQ-reporting-and-output-006}

When a `ComparisonResult`'s diff-entry sequence is empty (no drift
detected across all compared profiles), the HTML report, the PDF export,
and the console summary MUST each clearly communicate that no drift was
detected, rather than rendering an empty or ambiguous findings section.

#### Scenario: HTML report communicates a clean comparison

- GIVEN a `ComparisonResult` with an empty diff-entry sequence naming
  compared profiles `a` and `b`
- WHEN the HTML report is rendered
- THEN the rendered HTML SHALL include an explicit "no drift detected"
  message
- AND SHALL NOT render an empty table with no explanatory content

#### Scenario: PDF export communicates a clean comparison

- GIVEN a `ComparisonResult` with an empty diff-entry sequence
- WHEN the PDF export is produced from the rendered HTML
- THEN the PDF SHALL contain the same explicit "no drift detected" message
  present in the source HTML

#### Scenario: Console summary communicates a clean comparison

- GIVEN a `ComparisonResult` with an empty diff-entry sequence naming
  compared profiles `a` and `b`
- WHEN the console summary is printed
- THEN the printed output SHALL include an explicit "no drift detected"
  message
- AND SHALL NOT print zero-value counts with no accompanying explanation

### Requirement: Isolate Per-Format Report Generation Failures {#REQ-reporting-and-output-007}

The system MUST always attempt all three outputs (HTML file, PDF file,
console summary) for a given comparison run. A failure while generating
one output format MUST NOT prevent the other formats/console output from
being attempted and, where possible, completed. Any such failure MUST be
reported clearly (e.g. via console output) rather than silently swallowed
or allowed to propagate as an unhandled exception that aborts remaining
output generation.

#### Scenario: HTML file-write failure does not prevent PDF or console output

- GIVEN writing the HTML report file to disk fails (e.g. due to a
  filesystem error)
- WHEN the comparison run completes
- THEN the system SHALL still attempt PDF generation and SHALL still print
  the console summary
- AND the HTML failure SHALL be reported clearly rather than silently
  ignored

#### Scenario: PDF generation failure does not prevent HTML or console output

- GIVEN PDF generation fails for a given run
- WHEN the comparison run completes
- THEN the HTML report file SHALL still be written and the console summary
  SHALL still be printed
- AND the PDF failure SHALL be reported clearly rather than silently
  ignored

#### Scenario: Console summary failure does not prevent HTML/PDF file generation

- GIVEN an unexpected error occurs while formatting the console summary
- WHEN the comparison run completes
- THEN the HTML and PDF report files SHALL still be generated and written
  if their own generation steps succeed
- AND the console-summary failure SHALL be reported clearly rather than
  silently ignored

## RFC 2119 Keyword Legend

MUST/SHALL denote absolute requirements; MUST NOT/SHALL NOT denote
absolute prohibitions; SHOULD/MAY denote recommended or optional
behavior. No SHOULD/MAY-level requirements apply in this capability.
