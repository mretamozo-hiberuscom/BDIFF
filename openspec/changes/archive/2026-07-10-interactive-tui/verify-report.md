# Verify Report: Interactive TUI (`--tui` flag)

Change: `interactive-tui`
Phase: verify
Date: 2026-07-10

## Overall Verdict: PASS

All 10 requirements (REQ-interactive-tui-001 through -010, including the
clarify-added REQ-009 detail panel and REQ-010 summary header) are
implemented, tested, and traceable to code. The 3 documented deviations
in `apply-progress.md` were independently re-checked against the actual
source and test files, not just trusted from the narrative. One WARNING
(missing regression test for the `out`-closure fix) is raised; no
CRITICAL issues found.

## Test Run Evidence (re-executed independently)

Command: `pytest -q` (full suite, no mocks/skips forced)

```
170 passed, 1 skipped in 2.52s
```

This matches `apply-progress.md`'s reported "170 passed, 1 skipped"
exactly — not stale. The 1 skip is
`tests/integration/test_extraction_live.py`, pre-existing and unrelated
to this change (requires a live SQL Server DSN via
`SCHEMA_COMPARATOR_TEST_DSN`).

## Requirement-by-Requirement Check

| Requirement | Code location | Test(s) | Verdict |
|---|---|---|---|
| REQ-001 Launch TUI via `--tui` | `cli.py::_resolve_summary_renderer`, `main()` | `test_tui_flag_defaults_to_false`, `test_tui_flag_on_tty_passes_run_tui_as_render_summary` | PASS |
| REQ-002 Fallback on non-TTY | `cli.py::_resolve_summary_renderer` (real `sys.stdout.isatty`/`sys.stdin.isatty` mocks, not just Pilot) | `test_tui_flag_on_non_tty_prints_warning_and_uses_default_renderer`, `test_tui_flag_on_non_tty_exit_code_is_zero` | PASS |
| REQ-003 Navigate findings by table | `formatting.build_tree_data`, `widgets.FindingsTree.populate` | `test_build_tree_data_groups_by_qualified_table_name`, `test_app_tree_shows_one_group_per_table`, `test_app_expanding_group_reveals_findings` | PASS (see deviation-3 note below) |
| REQ-004 Filter by table/diff-type/column | `formatting.entry_matches`, `FindingsTree.apply_filter` | `test_entry_matches_*` (5 tests), `test_app_filter_input_hides_non_matching_findings`, `test_app_clearing_filter_restores_all_findings` | PASS |
| REQ-005 Collapse/expand groups | `Tree.action_toggle_node` built-in, wired via `space` binding | `test_app_collapsing_group_hides_findings_keeps_header` | PASS |
| REQ-006 Quit via `q`/`Escape` | `SchemaComparatorApp.BINDINGS` | `test_app_quit_key_exits_app`, `test_app_escape_key_exits_app` | PASS |
| REQ-007 Clean-comparison message | `app.py::compose` empty-groups branch | `test_app_shows_no_drift_message_for_empty_result`, `test_build_tree_data_returns_empty_groups_for_empty_result` | PASS |
| REQ-008 TUI failure isolation | `run_tui` try/except, `write_reports` outer try/except | `test_run_tui_catches_app_exception_and_reports_to_stderr`, `test_write_reports_isolates_render_summary_failure_from_html_pdf` | PASS |
| REQ-009 Detail panel breakdown | `formatting.detail_text`, `widgets.DetailPanel.show` | `test_detail_text_for_column_mismatch_lists_all_profiles_and_attributes`, `test_detail_text_for_missing_table_shows_missing_from_profile`, `test_detail_text_for_missing_column_shows_missing_from_profile`, `test_detail_text_never_renders_values_by_profile_for_missing_entries`, `test_app_selecting_leaf_updates_detail_panel` | PASS |
| REQ-010 Header profiles/counts | `formatting.header_counts`/`header_text` (imports `console._TYPE_LABELS`) | `test_header_counts_match_console_type_labels_mapping`, `test_header_text_lists_compared_profiles`, `test_app_shows_header_with_profiles_and_counts` | PASS |

## Deviation Review (independently re-verified, not trusted from narrative)

### Deviation 1: `out`-mutable-default fix in `write_reports` (design §3.2)

Reviewed `src/schema_comparator/report/write.py`. The implementation does
**not** use `render_summary: Callable[...] = _default_console_summary`
as a plain parameter default (which would have frozen `out=sys.stdout` at
function-definition time). Instead:

```python
effective_render_summary = (
    render_summary
    if render_summary is not None
    else (lambda result: _default_console_summary(result, out=out))
)
```

The `lambda` is created fresh inside the function body on every call, and
it closes over the current call's local `out` parameter — there is no
shared/module-level mutable state, so two sequential calls to
`write_reports` with different `out` targets cannot leak into each other.
This is correct: each call constructs its own closure over its own local
variable.

**Gap found**: `apply-progress.md` explicitly recommends checking "for a
test that calls `write_reports` twice with different `out` targets."
No such test exists in `tests/unit/report/test_write.py` — every test
uses a single `io.StringIO()` per test function; none exercises two
sequential calls in the same test to pin the no-leak guarantee as a
regression test. The fix itself is verified correct by inspection, but
the specific regression scenario the deviation note calls out is
untested. **WARNING** (see Risks below).

### Deviation 2: Task 7.3 manual smoke test replaced with headless `Pilot`

Confirmed this is a reasonable substitution, not a coverage gap for
REQ-002 itself. Verified `tests/unit/test_cli.py` contains real,
non-Pilot tests that mock `sys.stdout.isatty`/`sys.stdin.isatty`
directly (`test_tui_flag_on_tty_passes_run_tui_as_render_summary`,
`test_tui_flag_on_non_tty_prints_warning_and_uses_default_renderer`,
`test_tui_flag_on_non_tty_exit_code_is_zero`) — these are unit tests
against `cli.py`'s TTY-detection logic, entirely independent of the
`Pilot`/`run_test()` harness used for `tui/app.py`'s scenarios. The
headless `Pilot` tests cover REQ-003 through REQ-010's in-app
interaction scenarios (navigation, filter, collapse/expand, detail
panel, header, quit), which is a legitimate substitute for a
TTY-required manual walkthrough since Textual's headless driver
faithfully emulates key-press/render behavior. No coverage gap: PASS.

### Deviation 3: `j`/`k` navigation keys not bound

Independently inspected the installed Textual version's `Tree.BINDINGS`
directly:

```
up -> cursor_up, down -> cursor_down, space -> toggle_node, enter -> select_cursor, ...
```

Confirmed: no `j`/`k` bindings exist in this Textual version's `Tree`
widget, and `FindingsTree` does not add any. Re-read
REQ-interactive-tui-003's scenario text: "WHEN the user presses a
navigation key (arrow keys or `j`/`k`)" — this is a disjunctive (OR)
condition, not a conjunctive requirement that both bindings must exist.
Arrow-key navigation is implemented, tested
(`test_app_expanding_group_reveals_findings`,
`test_app_selecting_leaf_updates_detail_panel`, both use `pilot.press("down")`),
and passing. The scenario is genuinely satisfied by arrow-key-only
support. Not a spec violation. SUGGESTION only (see below).

## Risks

### WARNING
- **Missing regression test for the `out`-closure fix** (origin:
  `tasks-gap`). The code fix in `write.py` for the mutable-default `out`
  defect is correct by inspection (fresh closure per call, no shared
  state), but no test in `tests/unit/report/test_write.py` calls
  `write_reports` twice in the same test with two different `out`
  targets to pin this as a regression test. Recommend adding one test,
  e.g. calling `write_reports(result, out=io.StringIO())` twice with
  distinct `StringIO` instances and asserting each captures only its own
  call's console summary, before archiving — low risk given the current
  code is stateless, but this is exactly the kind of defect a future
  refactor could silently reintroduce without a pinning test.

### SUGGESTION
- Consider adding explicit `j`/`k` `Binding` entries mapping to
  `Tree`'s `cursor_up`/`cursor_down` actions in a future change if `j`/`k`
  support is later elevated from "one acceptable option in a disjunctive
  scenario" to a hard requirement. Not required now; current
  implementation and spec wording are consistent.

## Skill Resolution

`injected`
