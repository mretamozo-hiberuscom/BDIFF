# Spec Delta: Reporting and Output (Fixed `reportes/` Output Directory)

Status: extends the existing baseline at
`openspec/specs/reporting-and-output/spec.md` (capability
`reporting-and-output`). This delta MODIFIES one existing requirement
(REQ-reporting-and-output-002, report file location) to write into a
fixed `reportes/` subdirectory instead of loose into the invocation
working directory, and widens its stated scope to explicitly cover the
Excel file (previously implemented in code but not named in this
requirement's text). It does not fork a new domain and does not modify
the baseline file directly; merging happens at archive time.

Note (reconciled 2026-07-11 via sdd-reconcile): a second in-progress
change (`tui-interactive-actions`) also carries a change-local delta
against this same domain. It modifies REQ-reporting-and-output-001
(non-overlapping) but **also modifies this same requirement**,
REQ-reporting-and-output-002 (adding the TUI-launched conditional-skip
clause). The two REQ-002 texts have been reconciled into one merged
version, reproduced identically in both changes' spec deltas below, so
archiving either change first yields the same converged baseline text;
the already-implemented code in `report/write.py` (`_REPORTS_DIR` +
`generate_reports: bool`) already reflects this merged behavior.

## Clarifications

### Session 2026-07-11

- Q: Should the `reportes/` directory name/location be configurable
  (e.g. via `config.local.yaml` or a CLI flag)?
  → A: **No.** The name is fixed for this change. Configurability, if
  ever wanted, is left to a separate future change (see proposal-lite.md
  Out of Scope). No real ambiguity — decided directly in proposal
  scoping, no clarify-gate question needed.

## MODIFIED Requirements

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

## RFC 2119 Keyword Legend

MUST/SHALL denote absolute requirements; MUST NOT/SHALL NOT denote
absolute prohibitions; SHOULD/MAY denote recommended or optional
behavior. No SHOULD/MAY-level requirements apply in this delta.
