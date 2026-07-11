# Tasks: TUI Run & Report Actions

## Spec/Design Reconciliation

| Requirement / Scenario | Priority | Design Allocation | Status | Notes |
|---|---|---|---|---|
| REQ-interactive-tui-011 Edit excludes in memory | MUST | `widgets.ExcludeEditor`, `app.on_input_submitted` §3-4 | covered-by-design | Seeded from `--exclude-tables`; never persisted |
| REQ-interactive-tui-012 Run comparison from TUI | MUST | `actions.run_comparison`, `app._do_run_comparison`/worker §2, §4 | covered-by-design | Failure leaves `_result` untouched by construction |
| REQ-interactive-tui-013 Generate reports on demand | MUST | `report.write.generate_reports`, `app._do_generate_reports` §4-5 | covered-by-design | `io.StringIO` capture, never `sys.stdout` |
| REQ-reporting-and-output-002 (MODIFIED) Conditional automatic generation | MUST | `write_reports`'s `generate_reports: bool` param, `cli.py` wiring §5-6 | covered-by-design | Scoped to TUI-actually-launched case only |
| REQ-reporting-and-output-001 (MODIFIED, clarifying text only) | MUST | unchanged rendering, §5 | covered-by-design | No functional change, trigger-independence note only |

### Reconciliation Verdict

- MUST coverage: complete
- SHOULD/MAY gaps: none (spec has no SHOULD/MAY-level requirements)
- Ambiguities to track: the exact internal name for the extracted
  HTML/PDF/Excel generation function (`generate_reports` vs.
  `generate_all_reports`, to avoid colliding with `write_reports`'s new
  `generate_reports: bool` parameter name) is left as an
  implementation-time choice — resolved at task 4.1 below by naming the
  function `generate_all_reports`.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~750–950 (10 files: `actions.py` new, `widgets.py`/`app.py`/`write.py`/`cli.py` modified, 5 test files new/modified) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | 2 chained PRs (see below) |
| Delivery strategy | (not yet fixed for this change — decide before `sdd-apply`) |
| Chain strategy | sequential-dependent (PR 1 must land before PR 2) |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: sequential-dependent (PR 1 must land before PR 2)
400-line budget risk: High

### Suggested Work Units / Chained PRs

| PR | Goal | Phases | Notes |
|----|------|--------|-------|
| PR 1 | `report/write.py` extraction (`generate_all_reports`) + `write_reports`'s new `generate_reports: bool` param + `cli.py` conditional wiring (incl. `run_comparison` de-duplication) + their tests | Phases 1–2 | Small, mechanical, independently reviewable; no Textual/TUI code touched. Can land and be verified on its own. |
| PR 2 | `tui/actions.py` (new) + `tui/widgets.py` additions (`StatusLog`, `ExcludeEditor`) + `tui/app.py` bindings/workers + `Pilot` interaction tests | Phases 3–6 | Depends on PR 1's `generate_all_reports` and `cli.py`'s `run_comparison(profiles, exclude_patterns)` helper both existing already. |

This split follows the existing project convention (see the archived
`reporting-and-output` change) of separating a small, mechanical,
low-risk slice from a larger, higher-risk one, rather than shipping all
~750-950 lines as a single oversized review.

### Checklist Status Legend

- `[ ]` Not implemented yet
- `[~]` Implemented but not yet verified locally
- `[x]` Implemented and verified locally

## Phase 1: `report/write.py` — Extract `generate_all_reports`, Add `generate_reports: bool`

- [x] 1.1 (RED) Add `test_generate_all_reports_produces_same_outcomes_as_before_extraction`
      to `tests/unit/report/test_write.py`, asserting the extracted
      function's captured `out` lines match today's inline
      `write_reports` output line-for-line for an all-success case
      (REQ-reporting-and-output-001, regression baseline)
- [x] 1.2 (GREEN) Extract the existing HTML/PDF/Excel try/except blocks
      from `write_reports` into `generate_all_reports(result, *, out=sys.stdout)`
      per design §5, with no behavior change
- [x] 1.3 (RED) Add `test_write_reports_skips_generation_when_generate_reports_false`
      (mock `generate_all_reports`, assert it is never called;
      `render_summary`/console-equivalent IS still called) and
      `test_write_reports_generates_by_default` (regression: default
      `generate_reports=True` still calls it) to `test_write.py`
      (REQ-reporting-and-output-002)
- [x] 1.4 (GREEN) Add the `generate_reports: bool = True` keyword-only
      parameter to `write_reports`, gating the call to
      `generate_all_reports` per design §5
- [x] 1.5 Run `pytest tests/unit/report/test_write.py` and confirm all
      Phase 1 tests pass, plus all pre-existing tests in that file still
      pass unmodified

## Phase 2: `cli.py` — Conditional Wiring + `run_comparison` De-Duplication

- [x] 2.1 (RED) Add `test_tui_on_tty_calls_write_reports_with_generate_reports_false`
      to `tests/unit/test_cli.py` (mock `sys.stdout.isatty`/`sys.stdin.isatty`
      to `True`, patch `write_reports`, assert `generate_reports=False` in
      the call) (REQ-reporting-and-output-002)
- [x] 2.2 (RED) Add `test_tui_on_non_tty_calls_write_reports_with_generate_reports_true`
      and `test_no_tui_calls_write_reports_with_generate_reports_true`
      (regression-style, both asserting `generate_reports=True`)
- [x] 2.3 (GREEN) Implement `_resolve_summary_renderer_and_generate_reports`
      per design §6, replacing `_resolve_summary_renderer`; update
      `main()`'s call site
- [ ] 2.4 (RED) Add `test_main_deduplicates_extract_filter_compare_via_run_comparison`
      (patch `schema_comparator.tui.actions.run_comparison`, assert
      `main()` calls it instead of inlining
      `extract_schema`/`filter_excluded_tables`/`compare_snapshots`
      directly) — deferred to Phase 3 task 3.6 (`tui/actions.py` does not
      exist yet at this point in the sequence)
- [ ] 2.5 (GREEN) Update `main()` to call `run_comparison(profiles, exclude_patterns)`
      (moved to `tui/actions.py` in Phase 3 — for this phase, keep the
      inline sequence in `cli.py` and only complete this de-duplication
      once Phase 3 lands `actions.py`; mark this task in-progress if
      sequenced before Phase 3, or reorder locally so Phase 3 precedes
      this task) — deferred to Phase 3 task 3.6
- [x] 2.6 Run `pytest tests/unit/test_cli.py` and confirm all Phase 2
      tests pass, plus all pre-existing tests in that file still pass

## Phase 3: `tui/actions.py` — Pure `run_comparison`

- [ ] 3.1 (RED) Create `tests/unit/tui/test_actions.py`; write
      `test_run_comparison_calls_extract_filter_compare_in_order` (mock
      `extract_schema`, `filter_excluded_tables`, `compare_snapshots`,
      assert call order/args) and
      `test_run_comparison_skips_filter_when_no_exclude_patterns`
      (REQ-interactive-tui-012)
- [ ] 3.2 (GREEN) Implement `run_comparison(profiles, exclude_patterns)`
      in `src/schema_comparator/tui/actions.py` per design §2
- [ ] 3.3 (RED) Write `test_run_comparison_propagates_extraction_error_unmodified`
      (mock `extract_schema` to raise, assert the same exception type/
      message propagates, no wrapping)
- [ ] 3.4 (GREEN) Confirm `run_comparison` has no `try/except` (already
      satisfied by 3.2's implementation; this task is a verification step)
- [ ] 3.5 Run `pytest tests/unit/tui/test_actions.py` and confirm all pass
- [ ] 3.6 Complete the `cli.py`/`main()` de-duplication deferred from task
      2.5 now that `tui.actions.run_comparison` exists; re-run
      `tests/unit/test_cli.py` in full to confirm no regression

## Phase 4: `tui/widgets.py` — `StatusLog` and `ExcludeEditor`

- [ ] 4.1 (RED) Add `tests/unit/tui/test_widgets.py` tests (or extend it
      if it already exists): `test_status_log_info_writes_message`,
      `test_status_log_error_writes_styled_message`,
      `test_exclude_editor_seeds_value_from_pattern_list`,
      `test_exclude_editor_empty_patterns_seeds_empty_value`
- [ ] 4.2 (GREEN) Implement `StatusLog` and `ExcludeEditor` in
      `src/schema_comparator/tui/widgets.py` per design §3
- [ ] 4.3 Run `pytest tests/unit/tui/test_widgets.py` and confirm all pass

## Phase 5: `tui/app.py` — Bindings, Workers, Wiring

- [ ] 5.1 (RED) Add `test_app_accepts_profiles_and_exclude_patterns_constructor_args`
      to `tests/unit/tui/test_app.py` (REQ-interactive-tui-011)
- [ ] 5.2 (GREEN) Update `SchemaComparatorApp.__init__`/`compose` per
      design §4 (new keyword-only `profiles`/`exclude_patterns` params;
      mount `ExcludeEditor` and `StatusLog`)
- [ ] 5.3 (RED) Write `test_pressing_e_focuses_exclude_editor` (`Pilot`,
      `@pytest.mark.asyncio`) (REQ-interactive-tui-011)
- [ ] 5.4 (GREEN) Implement `action_focus_exclude_editor`
- [ ] 5.5 (RED) Write `test_submitting_exclude_editor_updates_patterns_and_triggers_run`
      (patch `tui.actions.run_comparison` at the `app.py` import site to a
      fast fake, assert `_exclude_patterns` updates and the fake was
      called) (REQ-interactive-tui-011, REQ-interactive-tui-012)
- [ ] 5.6 (GREEN) Implement `on_input_submitted` per design §4
- [ ] 5.7 (RED) Write `test_pressing_r_triggers_run_comparison_without_changing_excludes`
      (REQ-interactive-tui-012)
- [ ] 5.8 (GREEN) Implement `action_run_comparison`/`_do_run_comparison`/
      `_apply_new_result` per design §4, using `run_worker(..., thread=True)`
      and `call_from_thread` for all UI updates
- [ ] 5.9 (RED) Write `test_run_comparison_failure_leaves_previous_result_and_logs_error`
      (patch the fake `run_comparison` to raise; assert
      `app._result`/`_tree_data` unchanged and `StatusLog` received an
      error line) (REQ-interactive-tui-012's failure scenario)
- [ ] 5.10 (GREEN) Confirm/adjust `_do_run_comparison`'s `except` branch
      returns before calling `_apply_new_result` (already satisfied by
      5.8's implementation; verification task)
- [ ] 5.11 (RED) Write `test_pressing_g_calls_generate_reports_with_string_io_and_logs_output`
      (patch `report.write.generate_all_reports` at the `app.py` import
      site to a fake writing a known line to its `out`, assert that line
      appears in `StatusLog`, and assert `sys.stdout` was never touched)
      (REQ-interactive-tui-013)
- [ ] 5.12 (GREEN) Implement `action_generate_reports`/`_do_generate_reports`
      per design §4
- [ ] 5.13 (RED) Write `test_generate_reports_single_format_failure_does_not_crash_app`
      (fake `generate_all_reports` writes an `[ERROR]`-prefixed line for
      one format; assert it reaches `StatusLog` and the app is still
      running/responsive afterward) (REQ-interactive-tui-013's isolation
      scenario)
- [ ] 5.14 (GREEN) Confirm no unhandled exception path exists between
      `_do_generate_reports` and the worker (verification task; adjust if
      the fake surfaces a gap)
- [ ] 5.15 Run `pytest tests/unit/tui/test_app.py` in full and confirm all
      Phase 5 tests pass together with the pre-existing (archived-change)
      tests in that file

## Phase 6: `run_tui` Passthrough + Final Wiring

- [ ] 6.1 (RED) Add `test_run_tui_forwards_profiles_and_exclude_patterns`
      to `tests/unit/tui/test_app.py` (or a dedicated test for `run_tui`),
      asserting `run_tui(result, profiles=..., exclude_patterns=...)`
      constructs `SchemaComparatorApp` with those values
- [ ] 6.2 (GREEN) Update `run_tui`'s signature in `tui/app.py` (and its
      re-export in `tui/__init__.py` if the signature changed) to accept
      and forward `profiles`/`exclude_patterns`; update `cli.py`'s call
      site to pass them through
- [ ] 6.3 Run the full suite with `pytest --cov`; confirm `asyncio_mode =
      "strict"` leaves the synchronous suite unaffected and coverage stays
      at/above the project's 80%+ target on all new/modified modules
- [ ] 6.4 Manual smoke test: run `python run.py --config config.local.yaml --tui`
      (or the pre-launcher `python -m schema_comparator.cli` equivalent
      during development before `cli-distribution` lands), spot-checking
      REQ-interactive-tui-011/012/013 end-to-end against
      `examples/demo_fictitious_comparison.py`'s config
