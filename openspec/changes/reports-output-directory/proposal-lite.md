# Proposal (Lite): Fixed `reportes/` Output Directory for Report Files

## Intent

Today, `write_reports` (`report/write.py`) writes the timestamped HTML,
PDF, and Excel report files loose into the current working directory from
which the CLI was invoked (`schema-diff-report-YYYYMMDD-HHMMSS.{html,pdf,xlsx}`
next to `config.local.yaml`, `pyproject.toml`, etc.). This proposal makes
all three report files land inside a fixed `reportes/` subdirectory of
that same invocation working directory instead, creating the directory
first if it does not already exist. The console summary has no file and
is unaffected.

## Why (classification: small)

Bounded, mechanical change confined to one capability
(`reporting-and-output`) and one module (`report/write.py`): join an extra
path segment and ensure the directory exists before each of the three
existing `open(..., "w"/"wb")` calls. No new architectural decisions, no
new dependencies, no cross-module fan-out — lite workflow applies.

## Scope

### In Scope

- Change the HTML, PDF, and Excel file paths written by `write_reports`
  from `schema-diff-report-{timestamp}.{ext}` (cwd-relative) to
  `reportes/schema-diff-report-{timestamp}.{ext}` (still relative to the
  invocation cwd, not an absolute/fixed system path).
- Create `reportes/` (via `mkdir(parents=True, exist_ok=True)` or
  equivalent) before each write attempt, so a first run with no pre-existing
  folder still succeeds.
- Keep the existing per-format failure isolation
  (REQ-reporting-and-output-007): a failure creating/writing to `reportes/`
  for one format MUST NOT prevent the other formats or the console summary
  from being attempted.
- Update the printed success/error messages (`"Reporte HTML generado: {path}"`,
  etc.) to show the new `reportes/...` relative path.
- Update `openspec/specs/reporting-and-output/spec.md` (via a change-local
  spec delta) to reflect the new fixed-subdirectory location, since the
  existing REQ-reporting-and-output-002 and its scenario explicitly say
  "not a fixed [directory]" — this proposal intentionally reverses that,
  now fixing the *name* of a subdirectory while keeping it relative to the
  invocation cwd (not a fixed absolute path).

### Out of Scope

- Making the directory name/location configurable (e.g. via
  `config.local.yaml` or a `--output-dir` flag). The name `reportes/` is
  fixed for this change; configurability, if ever wanted, is a separate
  future change.
- Any change to filename timestamp format, per-format content/rendering,
  or the console summary (which has no file).
- The two other changes already in progress in this session
  (`cli-distribution`, `tui-interactive-actions`) — untouched.

## Decision

Fixed, non-configurable `reportes/` subdirectory name, resolved relative
to the CLI's invocation working directory (this project has no separate
"project root" concept distinct from invocation cwd), created on demand.
No user-facing flag or config key is added.

## Rollback

Revert the `report/write.py` path-join change and the spec delta; no
data migration, no persisted state, no schema change — files simply
resume landing in cwd. Low risk.

## Capabilities

### Modified Capabilities

- `reporting-and-output`: REQ-reporting-and-output-002 (file location)
  narrows from "current working directory" to "a `reportes/` subdirectory
  of the current working directory, created if absent". Also explicitly
  extends this requirement's naming/location coverage to the Excel file
  (previously implemented in code but not covered by this baseline
  requirement's text).
