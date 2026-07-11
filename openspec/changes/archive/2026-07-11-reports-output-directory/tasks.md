# Tasks: Fixed `reportes/` Output Directory for Report Files

## Spec/Design Reconciliation

Lite-mode change: no `design.md` (mechanical path-join + `mkdir`, no new
architectural decisions, no sequence diagrams warranted). Reconciled
directly against `proposal-lite.md` and the spec delta.

| Requirement / Scenario | Priority | Implementation Allocation | Status | Notes |
|---|---|---|---|---|
| REQ-reporting-and-output-002 (MODIFIED): HTML/PDF/Excel written under `reportes/`, timestamp shared | MUST | `report/write.py` — new path-join helper used by all three write blocks | covered-by-proposal | Same timestamp variable already shared across formats today; only the directory join is new |
| Scenario: `reportes/` created automatically when absent | MUST | same helper, `mkdir(parents=True, exist_ok=True)` before each write | covered-by-proposal | Idempotent; called once per format so it's safe even if called 3x per run |
| Scenario: failure creating/writing to `reportes/` for one format doesn't block others | MUST | existing per-format `try/except` blocks in `write_reports` (REQ-007), unchanged structure | covered-by-proposal | No new failure-isolation code needed — the mkdir call lives inside the already-isolated per-format try block |

### Reconciliation Verdict

- MUST coverage: complete
- SHOULD/MAY gaps: none (delta has no SHOULD/MAY-level requirements)
- Ambiguities to track: none outstanding — `reportes/` name is fixed
  per proposal Decision, no clarify-gate question needed

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~50–80 (1 source file: `report/write.py`; 2 test files: `tests/unit/report/test_write.py`, `tests/integration/test_write_reports.py` — mostly glob-path and print-message assertion updates) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | (not yet fixed for this change — decide before `sdd-apply`) |
| Chain strategy | none needed |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: none needed
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | `report/write.py` path-join + `mkdir` helper, updated print messages, updated unit + integration tests | PR 1 | Single phase, small enough for one PR |

### Checklist Status Legend

- `[ ]` Not implemented yet
- `[~]` Implemented but not yet verified locally
- `[x]` Implemented and verified locally

## Phase 1: `reportes/` Output Directory

- [x] 1.1 (RED) In `tests/unit/report/test_write.py`, update every test
      that currently globs `tmp_path.glob("schema-diff-report-*.{html,pdf}")`
      to instead glob `tmp_path.glob("reportes/schema-diff-report-*.{html,pdf}")`
      (or `(tmp_path / "reportes").glob(...)`); rename
      `test_write_reports_writes_to_the_current_working_directory` to
      `test_write_reports_writes_into_reportes_subdirectory_of_cwd` and
      assert the files land under `tmp_path / "reportes"`, not directly in
      `tmp_path` (REQ-reporting-and-output-002)
- [x] 1.2 (RED) Add
      `test_write_reports_creates_reportes_directory_when_absent` to the
      same file: `monkeypatch.chdir(tmp_path)` on a `tmp_path` with no
      `reportes/` subfolder yet, call `write_reports(...)`, assert
      `(tmp_path / "reportes").is_dir()` and that the HTML/PDF files exist
      inside it (REQ-reporting-and-output-002, "created automatically when
      absent" scenario)
- [x] 1.3 (GREEN) In `src/schema_comparator/report/write.py`, add a
      `_REPORTS_DIR = "reportes"` constant and a small helper (e.g.
      `_report_path(filename: str) -> str`) that creates `_REPORTS_DIR`
      via `Path(_REPORTS_DIR).mkdir(parents=True, exist_ok=True)` and
      returns the joined path; call it inside each of the three existing
      per-format `try` blocks (HTML, PDF, Excel) in place of the current
      bare `f"schema-diff-report-{timestamp}.{ext}"` construction, keeping
      each call inside its own existing `try/except` so per-format failure
      isolation (REQ-reporting-and-output-007) is unaffected
- [x] 1.4 (GREEN) Update the three success print messages (`"Reporte HTML
      generado: {path}"`, etc.) so `{path}` reflects the new
      `reportes/schema-diff-report-...` relative path (falls out naturally
      once the helper's return value is used consistently)
- [x] 1.5 (RED) In `tests/integration/test_write_reports.py`, update
      `test_write_reports_creates_paired_html_and_pdf_files_with_matching_timestamp_in_cwd`
      to glob under `tmp_path / "reportes"` instead of `tmp_path` directly;
      rename it to
      `test_write_reports_creates_paired_html_and_pdf_files_with_matching_timestamp_in_reportes_dir`
- [x] 1.6 Run `pytest tests/unit/report/test_write.py
      tests/integration/test_write_reports.py` and confirm all pass
- [x] 1.7 Run the full suite (`pytest --cov`) and confirm no other test
      (e.g. `tests/unit/test_cli.py`, which mocks `write_reports` and does
      not touch the filesystem) regresses
