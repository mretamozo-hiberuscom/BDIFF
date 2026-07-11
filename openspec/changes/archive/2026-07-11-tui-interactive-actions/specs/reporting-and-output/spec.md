# Spec Delta: Reporting and Output (Conditional Generation for Interactive TUI)

Status: extends the existing baseline at
`openspec/specs/reporting-and-output/spec.md` (capability
`reporting-and-output`). This delta MODIFIES one existing requirement
(automatic, unconditional HTML/PDF generation) to narrow it specifically
for the case where `--tui` is passed and the interactive TUI actually
launches. It does not fork a new domain and does not modify the baseline
file directly; merging happens at archive time.

Scope reminder (per proposal.md): this narrowing applies **only** when the
interactive TUI actually launches (i.e. `--tui` was passed and the
terminal is interactive). Every other invocation shape — no `--tui`, or
`--tui` falling back to the plain console summary on a non-interactive
terminal — is unaffected and keeps generating HTML, PDF, and Excel
unconditionally at startup exactly as today. This delta does not add,
remove, or change Excel generation itself (which is implemented in
`write_reports` but is not otherwise covered by this baseline spec); it
only changes *when* the existing unconditional-generation call happens.

Note (reconciled 2026-07-11 via sdd-reconcile): a second in-progress
change (`reports-output-directory`) also carries a change-local delta
against this same requirement, REQ-reporting-and-output-002 (moving
output location to a fixed `reportes/` subdirectory and widening scope to
name Excel explicitly). Both changes' REQ-002 text has been reconciled
into one merged version, reproduced identically in both changes' spec
deltas, so archiving either change first yields the same converged
baseline text; the already-implemented code in `report/write.py`
(`_REPORTS_DIR` + `generate_reports: bool`) already reflects this merged
behavior.

## Clarifications

### Session 2026-07-11

- **Q: Should automatic HTML/PDF/Excel generation at startup remain
  unconditional even when the interactive TUI launches, given the new
  in-TUI "generate reports" action?**
  A: **No.** When the interactive TUI actually launches, automatic
  upfront generation is skipped; those formats are produced only via the
  new in-TUI "generate reports" action (`interactive-tui`
  REQ-interactive-tui-013). This was resolved via an explicit clarify-gate
  question during this change's planning, given it narrows an existing
  MUST-level contract rather than being purely additive.

## MODIFIED Requirements

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
