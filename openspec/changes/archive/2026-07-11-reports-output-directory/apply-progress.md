# Apply Progress: Fixed `reportes/` Output Directory for Report Files

## Summary

All 7 tasks in Phase 1 implemented and verified locally, following strict
RED-GREEN TDD.

## What changed

- `src/schema_comparator/report/write.py`: added `_REPORTS_DIR = "reportes"`
  constant and `_report_path(filename)` helper (creates the directory via
  `Path.mkdir(parents=True, exist_ok=True)`, returns the joined path).
  All three per-format write blocks (HTML, PDF, Excel) now route their
  output path through this helper, inside their existing isolated
  `try/except` blocks. Success print messages now reflect the
  `reportes/...` relative path automatically.
- `tests/unit/report/test_write.py`: updated globs to
  `reportes/schema-diff-report-*.{html,pdf}`; renamed
  `test_write_reports_writes_to_the_current_working_directory` to
  `test_write_reports_writes_into_reportes_subdirectory_of_cwd`; added
  `test_write_reports_creates_reportes_directory_when_absent`.
- `tests/integration/test_write_reports.py`: updated glob paths and renamed
  `test_write_reports_creates_paired_html_and_pdf_files_with_matching_timestamp_in_cwd`
  to `..._in_reportes_dir`.

## Test results

- Targeted (`tests/unit/report/test_write.py` + `tests/integration/test_write_reports.py`):
  11 passed.
- Full suite (`pytest`): 260 passed, 1 skipped (pre-existing skip, unrelated
  to this change).

## Notes

- `tests/unit/test_cli.py` mocks `write_reports` and does not touch the
  filesystem, so it was unaffected (confirmed by full-suite run).
- No chained PRs needed (single, low-risk work unit as forecasted).
