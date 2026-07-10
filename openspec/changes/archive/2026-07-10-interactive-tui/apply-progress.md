# Apply Progress: Interactive TUI (`--tui` flag)

Change: `interactive-tui`
Batch: 1 of 1 (all 7 phases / 36 tasks implemented in this run)

## Summary

All tasks in `tasks.md` were implemented in RED→GREEN order per phase.
Every new test was confirmed to fail for the expected reason (missing
module/attribute) before the corresponding implementation was written,
then re-run to confirm GREEN before moving to the next task.

## Phase 1: Foundation — Dependencies & Package Setup

- 1.1: Added `textual>=0.60` to `[project].dependencies`, `pytest-asyncio>=0.24`
  to `[project.optional-dependencies].dev`, and `[tool.pytest.ini_options]`
  `asyncio_mode = "strict"` in `pyproject.toml`.
- 1.2: Installed `pip install -e .[dev]` in `.venv`; confirmed
  `textual==8.2.8` and `pytest_asyncio==1.4.0` import successfully.
- 1.3: Corrected `src/schema_comparator/tui/__init__.py`'s docstring to the
  read-only findings-browser scope (Decision 5); left without re-exports
  until Phase 7/task 7.1 (done alongside `app.py`'s creation, see below).
- 1.4: Created `tests/unit/tui/__init__.py` (empty package init).

## Phase 2: Pure Formatting Layer (`tui/formatting.py`)

- 2.1–2.10: `tests/unit/tui/test_formatting.py` written first (16 tests
  covering `build_tree_data`, `leaf_label`, `detail_text`,
  `header_counts`/`header_text`, `entry_matches`); confirmed RED via
  `ModuleNotFoundError: No module named 'schema_comparator.tui.formatting'`.
  Implemented `src/schema_comparator/tui/formatting.py` with `TableGroup`,
  `TreeData`, `build_tree_data`, `leaf_label`, `detail_text`,
  `header_counts`, `header_text`, `entry_matches`. All 16 tests GREEN.

## Phase 3: Widgets (`tui/widgets.py`)

- 3.1–3.3: Implemented `src/schema_comparator/tui/widgets.py` with
  `SummaryHeader(Static)`, `DetailPanel(Static)` (`show(entry)` with a
  neutral placeholder for `None`), and `FindingsTree(Tree)`
  (`populate(tree_data)` / `apply_filter(filter_text)` using the
  rebuild-filtered-`TreeData` approach, resolving the design §11/§4.1 open
  choice as instructed by task 3.2). Exercised indirectly via Phase 4's
  `Pilot` tests (no standalone widget-level test file was specified by
  tasks.md for this phase).

## Phase 4: App (`tui/app.py`)

- 4.1–4.14: `tests/unit/tui/test_app.py` written first (11 async
  `Pilot`-driven tests + 1 sync `run_tui` failure-isolation test);
  confirmed RED via `ModuleNotFoundError: No module named
  'schema_comparator.tui.app'`. Implemented
  `src/schema_comparator/tui/app.py` with `SchemaComparatorApp`
  (`BINDINGS` for `q`/`escape`/`slash`, `filter_text` reactive,
  `compose`/`on_mount` empty-groups branch, `on_input_changed`,
  `watch_filter_text`, `on_tree_node_highlighted`) and `run_tui`.
- 7.1 (`tui/__init__.py` re-export) was completed at this point, since
  task 7.1 explicitly depends on `app.py` existing.

### Deviations found and fixed during Phase 4 GREEN

- The installed Textual version (8.2.8) does not support
  `DOMQuery.first(default=...)` (raises `TypeError`); replaced all such
  call sites in `app.py` with `len(query)` / `query.first()` checks.
- `Static` widgets in this Textual version expose no public `.renderable`
  attribute; tests read rendered content via `str(widget.render())`
  instead.
- `Tree`'s cursor starts at `cursor_line == -1` (no node highlighted)
  until the first navigation key is pressed; adjusted the app-level
  `Pilot` tests' `press("down")`/`press("space")` counts to account for
  this (verified empirically with a throwaway debug script, since the
  design's illustrative snippets did not specify this detail).
- Added `k`/`j` were not added as extra bindings: verified `Tree`'s
  built-in bindings in this Textual version bind `up`/`down` (not
  `j`/`k`) to cursor movement out of the box. REQ-003's scenario
  ("arrow keys or `j`/`k`") is satisfied by the arrow-key half of that
  disjunction, which is exercised and passing in
  `test_app_selecting_leaf_updates_detail_panel`; `j`/`k` bindings were
  not added since tasks.md 4.x does not call for a custom binding here
  and the design explicitly states these are `Tree` built-ins requiring
  no override.

## Phase 5: CLI Integration (`cli.py`)

- 5.1–5.6: Added 4 new tests to `tests/unit/test_cli.py`
  (`test_tui_flag_defaults_to_false`,
  `test_tui_flag_on_tty_passes_run_tui_as_render_summary`,
  `test_tui_flag_on_non_tty_prints_warning_and_uses_default_renderer`,
  `test_tui_flag_on_non_tty_exit_code_is_zero`); confirmed RED (missing
  `--tui` argument / `AttributeError`/`SystemExit`). Implemented the
  `--tui` flag, `_resolve_summary_renderer(use_tui)`, and wired it into
  `main()`'s call to `write_reports`. All 6 `test_cli.py` tests GREEN.

## Phase 6: `write_reports` Integration (`report/write.py`)

- 6.1–6.2: Added 3 new tests to `tests/unit/report/test_write.py`
  (`test_write_reports_default_render_summary_matches_prior_console_output`,
  `test_write_reports_calls_custom_render_summary_when_provided`,
  `test_write_reports_isolates_render_summary_failure_from_html_pdf`);
  confirmed RED (`TypeError: write_reports() got an unexpected keyword
  argument 'render_summary'` for the two new-behavior tests). Implemented
  `_default_console_summary` and the `render_summary` parameter.

### Deviation from the literal design snippet (§3.2)

The design's illustrative snippet used
`render_summary: Callable[[ComparisonResult], None] = _default_console_summary`
as a plain parameter default. Implemented literally, this would bind
`_default_console_summary`'s own `out=sys.stdout` default at function-definition
time, so any caller overriding `write_reports`'s `out` (e.g. passing an
`io.StringIO()`, as every existing `test_write.py` test already does)
without also overriding `render_summary` would silently have its console
summary printed to the real `sys.stdout` instead of the passed `out` —
breaking every pre-existing `write_reports` test that asserts summary
text appears in a captured `out`. Implemented instead with
`render_summary: Callable[...] | None = None` and an `effective_render_summary`
resolved inside the function body as `lambda result: _default_console_summary(result, out=out)`
when `render_summary` is not provided, so the current call's `out` is
always respected. This preserves the design's intent (a single-source
default console summary, one keyword-only parameter, no change to the
HTML/PDF `try/except` blocks) while fixing the `out`-binding defect.
All 9 `test_write.py` tests (6 pre-existing + 3 new) GREEN.

## Phase 7: Final Wiring & Cleanup

- 7.1: Completed during Phase 4 (see above) — `tui/__init__.py` now
  re-exports `SchemaComparatorApp`/`run_tui` with `__all__` set.
- 7.2: Full suite run with `--cov` — see Test Run Evidence below.
- 7.3: A genuine interactive-terminal manual smoke test was not
  performed, since this run's execution environment has no attached
  interactive TTY (all commands run through a headless automation
  terminal). As a substitute, the same REQ-001–REQ-010 scenarios (launch,
  grouping, filtering, collapse/expand, quit, detail panel, header
  counts, empty-result messaging) are exercised end-to-end via Textual's
  headless `Pilot`/`run_test()` harness in `tests/unit/tui/test_app.py`,
  which is the same mechanism the design specifies for this v1 TUI. This
  is noted as a risk below rather than silently marked done.

## Test Run Evidence

Command: `pytest --cov=schema_comparator --cov-report=term-missing -q`

```
170 passed, 1 skipped in 3.64s
```

- The 1 skip is pre-existing and unrelated to this change:
  `tests/integration/test_extraction_live.py` skips when
  `SCHEMA_COMPARATOR_TEST_DSN` is not set (requires a live SQL Server DSN).
- Coverage: 99% overall (572 stmts, 6 missed). New modules:
  `tui/formatting.py` 100%, `tui/widgets.py` 100%, `tui/__init__.py` 100%,
  `tui/app.py` 93% (missed lines 48–50: the "no query match" defensive
  branches in `action_focus_filter`/`watch_filter_text`/
  `on_tree_node_highlighted`, which only matter before those widgets are
  mounted). `cli.py` 97% (1 line: the `if __name__ == "__main__":` guard,
  pre-existing and never exercised by unit tests). Both are well above
  the 80%+ target; no critical path is uncovered.

Final confirmation run: `pytest -q` → `170 passed, 1 skipped in 2.46s`.

## Files Changed

### New

- `src/schema_comparator/tui/app.py`
- `src/schema_comparator/tui/widgets.py`
- `src/schema_comparator/tui/formatting.py`
- `tests/unit/tui/__init__.py`
- `tests/unit/tui/test_formatting.py`
- `tests/unit/tui/test_app.py`

### Modified

- `src/schema_comparator/tui/__init__.py`
- `src/schema_comparator/cli.py`
- `src/schema_comparator/report/write.py`
- `pyproject.toml`
- `tests/unit/test_cli.py`
- `tests/unit/report/test_write.py`
- `openspec/changes/interactive-tui/tasks.md` (checklist statuses set to `[x]`)

No other file was touched, matching the design's exact file-change list.

## Risks / Follow-ups

- Task 7.3's manual interactive-terminal smoke test could not be
  performed in this headless environment; the `Pilot`-driven test suite
  is the practical substitute, but a real-terminal check (launching
  `schema-comparator --config ... --tui` from an actual terminal) is
  recommended before this ships to end users, to catch anything Textual's
  headless driver might not surface (terminal resize behavior, real
  keyboard input timing, etc.).
- `j`/`k` navigation keys are not explicitly bound on `FindingsTree`; the
  installed Textual version's `Tree` only binds arrow keys by default.
  REQ-003's disjunctive scenario ("arrow keys or `j`/`k`") is satisfied
  by the arrow-key path. If `j`/`k` support is later found to be a hard
  requirement rather than an either/or scenario, it can be added as two
  extra `Binding` entries mapping to `Tree`'s existing `cursor_up`/
  `cursor_down` actions without further design changes.
