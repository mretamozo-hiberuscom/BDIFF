# Tasks: Interactive TUI (`--tui` flag)

## Spec/Design Reconciliation

| Requirement / Scenario | Priority | Design Allocation | Status | Notes |
|---|---|---|---|---|
| REQ-001 Launch TUI via `--tui` | MUST | `cli.py` §3.1, `report/write.py` §3.2 | covered-by-design | `_resolve_summary_renderer` + `render_summary` param |
| REQ-002 Fallback on non-TTY | MUST | `cli.py` §3.1 (`isatty()` checks, `[WARN]` message) | covered-by-design | Exit code unaffected (Decision 3) |
| REQ-003 Navigate findings by table | MUST | `formatting.build_tree_data`, `widgets.FindingsTree` §2.1, §4 | covered-by-design | Arrow/`j`/`k` are `Tree` built-ins |
| REQ-004 Filter by table/diff-type/column | MUST | `formatting.entry_matches` §4.1, `FindingsTree.apply_filter` | covered-by-design | Case-insensitive substring match |
| REQ-005 Collapse/expand groups | MUST | `Tree.action_toggle_node` built-in §4 | covered-by-design | No custom binding needed |
| REQ-006 Quit via `q`/`Escape` | MUST | `SchemaComparatorApp.BINDINGS` §4 | covered-by-design | Maps to built-in `action_quit` |
| REQ-007 Clean-comparison message | MUST | `app.py` `on_mount` empty-groups branch §2.4 | covered-by-design | Reuses `console.py` clean-comparison wording |
| REQ-008 TUI failure isolation | MUST | `run_tui` try/except §3.3, `write_reports` outer try/except §3.2 | covered-by-design | Defense-in-depth, two layers |
| REQ-009 Detail panel breakdown | MUST | `formatting.detail_text`, `widgets.DetailPanel.show` §2.2 | covered-by-design | Single-dispatch on entry type |
| REQ-010 Header profiles/counts | MUST | `formatting.header_counts`/`header_text` (imports `console._TYPE_LABELS`) §2.3 | covered-by-design | Structural single-source-of-truth guarantee |

### Reconciliation Verdict
- MUST coverage: complete
- SHOULD/MAY gaps: none (spec has no SHOULD/MAY-level requirements)
- Ambiguities to track: tree-node visibility mechanism for filtering is left as an implementation-time choice between two equivalent approaches (design §4.1, §11) — resolved at task 3.2 below by picking the rebuild-filtered-`TreeData` approach for simplicity and testability.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~950–1300 (12 files: 5 new source/test package files, 4 new modules, 3 modified files) |
| 400-line budget risk | High |
| Chained PRs recommended | No |
| Suggested split | Single PR under `size:exception` (delivery strategy: exception-ok) |
| Delivery strategy | exception-ok |
| Chain strategy | size-exception |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Dependencies + pure `formatting.py` layer + widgets | PR 1 (size-exception) | Phases 1–3 |
| 2 | `app.py` + CLI/`write_reports` wiring + cleanup | PR 1 (size-exception) | Phases 4–7, same PR under approved exception |

### Checklist Status Legend

- `[ ]` Not implemented yet
- `[~]` Implemented but not yet verified locally
- `[x]` Implemented and verified locally

## Phase 1: Foundation — Dependencies & Package Setup

- [x] 1.1 Add `textual>=0.60` to `[project].dependencies` and `pytest-asyncio>=0.24` to `[project.optional-dependencies].dev` in `pyproject.toml`; add `[tool.pytest.ini_options]` with `asyncio_mode = "strict"`
- [x] 1.2 Install updated deps: `pip install -e .[dev]`; confirm `import textual` and `import pytest_asyncio` succeed
- [x] 1.3 Correct the stale docstring in `src/schema_comparator/tui/__init__.py` per Decision 5 (read-only findings-browser scope; no re-exports yet, `app.py` doesn't exist)
- [x] 1.4 Create `tests/unit/tui/__init__.py` (empty package init, mirrors sibling test packages)

## Phase 2: Pure Formatting Layer (`tui/formatting.py`)

- [x] 2.1 RED: write `test_build_tree_data_groups_by_qualified_table_name` and `test_build_tree_data_returns_empty_groups_for_empty_result` in `tests/unit/tui/test_formatting.py` (REQ-003, REQ-007)
- [x] 2.2 GREEN: implement `TableGroup`, `TreeData`, `build_tree_data` in `src/schema_comparator/tui/formatting.py`
- [x] 2.3 RED: write `test_leaf_label_matches_console_missing_table_wording`, `_missing_column_wording`, `_column_mismatch_wording`
- [x] 2.4 GREEN: implement `leaf_label(entry)` mirroring `console.py`'s three `isinstance` branches
- [x] 2.5 RED: write the four `detail_text` tests from design §9.1 (REQ-009, including the negative assertion)
- [x] 2.6 GREEN: implement `detail_text(entry)` (single-dispatch on `ColumnMismatch`/`MissingTable`/`MissingColumn`)
- [x] 2.7 RED: write `test_header_counts_match_console_type_labels_mapping` and `test_header_text_lists_compared_profiles` (REQ-010)
- [x] 2.8 GREEN: implement `header_counts`/`header_text`, importing `_TYPE_LABELS` from `report/console.py`
- [x] 2.9 RED: write the five `entry_matches` tests from design §9.1 (REQ-004)
- [x] 2.10 GREEN: implement `entry_matches(entry, filter_text)`

## Phase 3: Widgets (`tui/widgets.py`)

- [x] 3.1 Implement `SummaryHeader(Static)` rendering `header_text(result)` once at mount time
- [x] 3.2 Implement `FindingsTree(Tree)` with `populate(tree_data)` (one root per `TableGroup`, `leaf_label` leaves, `node.data = entry`) and `apply_filter(filter_text)` using the rebuild-filtered-`TreeData` approach (resolves the §11 open choice), hiding groups with zero remaining matches
- [x] 3.3 Implement `DetailPanel(Static)` with `show(entry: DiffEntry | None)` calling `detail_text`, showing a neutral placeholder message when `entry is None`

## Phase 4: App (`tui/app.py`)

- [x] 4.1 RED: write `test_app_shows_header_with_profiles_and_counts` and `test_app_shows_no_drift_message_for_empty_result` in `tests/unit/tui/test_app.py` (async, `@pytest.mark.asyncio`, `app.run_test()`) (REQ-010, REQ-007)
- [x] 4.2 GREEN: implement `SchemaComparatorApp.__init__`/`compose`/`on_mount` (empty-groups branch mounts `Static("No drift detected...")` instead of `FindingsTree`)
- [x] 4.3 RED: write `test_app_tree_shows_one_group_per_table` and `test_app_expanding_group_reveals_findings` (REQ-003)
- [x] 4.4 GREEN: wire `FindingsTree.populate(self._tree_data)` into `compose`
- [x] 4.5 RED: write `test_app_collapsing_group_hides_findings_keeps_header` (REQ-005)
- [x] 4.6 GREEN: confirm/adjust `Tree.action_toggle_node` behavior against `FindingsTree`'s node structure
- [x] 4.7 RED: write `test_app_filter_input_hides_non_matching_findings` and `test_app_clearing_filter_restores_all_findings` (REQ-004)
- [x] 4.8 GREEN: implement `filter_text` reactive, `on_input_changed`, `watch_filter_text` calling `FindingsTree.apply_filter`
- [x] 4.9 RED: write `test_app_selecting_leaf_updates_detail_panel` (REQ-009)
- [x] 4.10 GREEN: wire the tree's node-highlighted/selected event to `self.detail_panel.show(node.data)`
- [x] 4.11 RED: write `test_app_quit_key_exits_app` and `test_app_escape_key_exits_app` (REQ-006)
- [x] 4.12 GREEN: declare `BINDINGS` (`q`, `escape` → `action_quit`; `slash` → `action_focus_filter`); implement `action_focus_filter`
- [x] 4.13 RED: write a `run_tui` test asserting an app-raising exception is caught, reported to `stderr`, and does not propagate (REQ-008)
- [x] 4.14 GREEN: implement `run_tui(result)` with `app.run()` wrapped in `try/except Exception`

## Phase 5: CLI Integration (`cli.py`)

- [x] 5.1 RED: add `test_tui_flag_defaults_to_false` to `tests/unit/test_cli.py` (REQ-001)
- [x] 5.2 GREEN: add the `--tui` `store_true` argument to `build_arg_parser()`
- [x] 5.3 RED: add `test_tui_flag_on_tty_passes_run_tui_as_render_summary` (mock `sys.stdout.isatty`/`sys.stdin.isatty` to `True`, patch `write_reports`) (REQ-001)
- [x] 5.4 GREEN: implement `_resolve_summary_renderer(use_tui)` and wire it into `main()`'s call to `write_reports`
- [x] 5.5 RED: add `test_tui_flag_on_non_tty_prints_warning_and_uses_default_renderer` and `test_tui_flag_on_non_tty_exit_code_is_zero` (REQ-002, Decision 3)
- [x] 5.6 GREEN: implement the `[WARN] --tui requires an interactive terminal...` `stderr` print and default-renderer fallback path

## Phase 6: `write_reports` Integration (`report/write.py`)

- [x] 6.1 RED: add `test_write_reports_default_render_summary_matches_prior_console_output`, `test_write_reports_calls_custom_render_summary_when_provided`, and `test_write_reports_isolates_render_summary_failure_from_html_pdf` to `tests/unit/report/test_write.py` (REQ-001, REQ-008)
- [x] 6.2 GREEN: add `_default_console_summary(result, *, out=sys.stdout)` and the `render_summary: Callable[[ComparisonResult], None]` keyword-only parameter to `write_reports`; wrap the `render_summary(result)` call in `try/except Exception` without touching the existing HTML/PDF try/except blocks

## Phase 7: Final Wiring & Cleanup

- [x] 7.1 Update `src/schema_comparator/tui/__init__.py` to re-export `SchemaComparatorApp`/`run_tui` from `tui.app` and set `__all__ = ["SchemaComparatorApp", "run_tui"]` (now that `app.py` exists)
- [x] 7.2 Run the full suite with `pytest --cov`; confirm `asyncio_mode = "strict"` leaves the pre-existing synchronous suite unaffected and coverage stays at/above the project's 80%+ target on new modules
- [x] 7.3 Manual smoke test: run the CLI with `--tui` against `examples/demo_fictitious_comparison.py`'s config on an interactive terminal, spot-checking REQ-001–REQ-010 scenarios end-to-end
