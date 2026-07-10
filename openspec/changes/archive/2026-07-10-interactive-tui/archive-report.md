# Archive Report: Interactive TUI (`--tui` flag)

**Change**: `interactive-tui`
**Archive date**: 2026-07-10
**Verification verdict**: PASS (no CRITICAL findings)

## Close Gate

`verify-report.md` reports **PASS**: an independently re-executed `pytest -q`
reproduced 170 passed / 1 skipped, matching `apply-progress.md` exactly —
not stale. All 10 requirements (REQ-interactive-tui-001 through -010) were
traced scenario-by-scenario to passing tests by reading the actual source
and test files, not by trusting the apply narrative. All 3 documented
deviations from design were independently re-verified as accurate and
justified. Zero CRITICAL findings. One WARNING and one SUGGESTION, both
accepted as non-blocking follow-up notes rather than fixed before archive:

1. **WARNING — missing regression test for the `out`-closure fix in
   `write_reports`**: the fix in `report/write.py` for the mutable-default
   `out`-binding defect (a fresh `lambda` closing over the current call's
   local `out`, not a shared/module-level default) is verified correct by
   inspection — no shared mutable state exists, so two sequential
   `write_reports` calls with different `out` targets cannot leak into
   each other. However, no test in `tests/unit/report/test_write.py` calls
   `write_reports` twice in the same test with two different `out` targets
   to pin this as a regression test. **Accepted as non-blocking**: the
   current code is stateless and correct, but a future refactor could
   silently reintroduce the defect without a pinning test. Recommended
   follow-up: add a test calling `write_reports(result, out=io.StringIO())`
   twice with distinct `StringIO` instances, asserting each captures only
   its own call's console summary.
2. **SUGGESTION — `j`/`k` navigation keys are not explicitly bound**: the
   installed Textual version's `Tree` widget binds only `up`/`down` to
   cursor movement, not `j`/`k`; `FindingsTree` does not add extra
   bindings. REQ-interactive-tui-003's scenario wording ("arrow keys or
   `j`/`k`") is a disjunctive (OR) condition, genuinely satisfied by the
   arrow-key path alone, and is exercised and passing in the `Pilot` test
   suite. **Accepted as non-blocking**: not a spec violation. Recommended
   follow-up: if `j`/`k` support is later elevated to a hard requirement,
   add two explicit `Binding` entries mapping to `Tree`'s built-in
   `cursor_up`/`cursor_down` actions.

Non-goals compliance confirmed: no diff-detection logic changes, no
connection-management screens, no run/re-extract action from within the
TUI, no write/editing action against `ComparisonResult` or any schema, and
no HTML/PDF rendering/theming changes. Archive is permitted.

## What Shipped

- A new `textual`-based read-only findings browser under
  `src/schema_comparator/tui/`:
  - `formatting.py` — pure, synchronous functions (`TableGroup`,
    `TreeData`, `build_tree_data`, `leaf_label`, `detail_text`,
    `header_counts`, `header_text`, `entry_matches`), independently
    unit-testable without the `Pilot` harness, and consistent with
    `report/console.py`'s grouping/counting/labelling conventions
    (`header_counts` imports `console._TYPE_LABELS` directly as a
    structural single-source-of-truth guarantee).
  - `widgets.py` — `SummaryHeader(Static)`, `DetailPanel(Static)`
    (`show(entry)` with a neutral placeholder for `None`), and
    `FindingsTree(Tree)` (`populate(tree_data)` / `apply_filter(filter_text)`
    using a rebuild-filtered-`TreeData` approach).
  - `app.py` — `SchemaComparatorApp(App)` with `BINDINGS` for
    `q`/`escape`/`slash`, a `filter_text` reactive attribute, an
    empty-result "no drift detected" branch, and `run_tui(result)`
    wrapping `App.run()` in `try/except Exception` so a TUI failure is
    reported clearly and never propagates as an unhandled exception.
  - `__init__.py` — corrected docstring scoped to the fixed v1 read-only
    findings-browser surface (replacing the stale, aspirational
    connection-management-shell docstring), re-exporting
    `SchemaComparatorApp`/`run_tui`.
- An opt-in `--tui` CLI flag (`cli.py`), off by default, with
  `_resolve_summary_renderer(use_tui)` performing
  `sys.stdout.isatty()`/`sys.stdin.isatty()` detection and printing a
  `[WARN]` fallback message to `stderr` on a non-interactive terminal —
  the fallback never affects the process exit code.
- `write_reports` (`report/write.py`) gained one new keyword-only
  parameter, `render_summary`, resolved internally via a per-call closure
  over `out` (fixing a mutable-default defect present in the design's
  illustrative snippet — see accepted WARNING above), with the existing
  HTML/PDF `try/except` isolation blocks left completely untouched.
- New dependencies: `textual>=0.60` (runtime) and `pytest-asyncio>=0.24`
  (dev), plus `[tool.pytest.ini_options] asyncio_mode = "strict"` so the
  pre-existing fully-synchronous test suite is unaffected by default.
- New tests: `tests/unit/tui/test_formatting.py` (16 synchronous
  pure-function tests), `tests/unit/tui/test_app.py` (11 async
  `Pilot`-driven interaction tests + 1 `run_tui` failure-isolation test),
  4 new `tests/unit/test_cli.py` tests, and 3 new
  `tests/unit/report/test_write.py` tests.
- Full suite: 170 passed, 1 skipped (pre-existing, unrelated live-DB
  integration test) — no regression to `compare/`, `config/`,
  `discovery/`, `connectors/`, or the pre-existing `report/` tests.
  99% overall coverage; new modules at 100% (`formatting.py`,
  `widgets.py`, `__init__.py`) or 93% (`app.py`, missed lines are
  defensive "no query match" branches only reachable before widget
  mount).

## Specification Synchronization

| Domain | Action | Details |
|--------|--------|---------|
| `interactive-tui` | Created | This change introduces a brand-new capability domain with no prior baseline. The change-local spec at [specs/interactive-tui/spec.md](specs/interactive-tui/spec.md) is copied verbatim as the new baseline at [openspec/specs/interactive-tui/spec.md](../../../specs/interactive-tui/spec.md) — no merge was needed since no prior version of this domain existed. |

`reporting-and-output`'s baseline spec was **not** modified: the proposal
documents `write_reports`'s new `render_summary` parameter as an additive,
non-weakening injection point (no existing requirement changed, no new
formal requirement was drafted for it in this change's artifacts), so no
spec delta exists to synchronize for that domain. It is left untouched.

The canonical specification baselines after this archive:

- `openspec/specs/comparison-engine/spec.md`
- `openspec/specs/connection-profile-config/spec.md`
- `openspec/specs/schema-extraction/spec.md`
- `openspec/specs/reporting-and-output/spec.md`
- `openspec/specs/interactive-tui/spec.md` (new)

No other capability baseline was touched; this change only reads
`ComparisonResult`/`DiffEntry` as an already-produced, immutable input and
never reshapes comparison or diff-detection logic.

## Decisions and ADRs

No `open_decisions` entries or change-local ADR files were present to
promote. The four clarification-session Q&A pairs recorded in the
change-local spec (HTML/PDF independence from `--tui`, non-TTY fallback
behavior, v1 interaction scope, empty-result/TUI-failure handling) plus
the two follow-up-session Q&A pairs (detail-panel and header formal
requirement status) are preserved verbatim in the new baseline spec's
Clarifications section; they were resolved without a blocking user
question during the spec-writing phase.

## Archive Copy

Artifacts were copied to
`openspec/changes/archive/2026-07-10-interactive-tui/`. The active source
directory (`openspec/changes/interactive-tui/`) could not be deleted by
this executor — no file-delete/move tool is available in this
environment (same limitation noted in the prior `comparison-engine`,
`diff-detection-completion`, and `reporting-and-output` archives). See the
Residual Cleanup section of the final result for the exact path requiring
manual removal.

## Cost

No per-phase cost data was recorded for this change
(`.ospec/session/interactive-tui/phase-costs.jsonl` missing or empty).

**Total user questions asked**: 0 (all clarifications resolved during the
spec-writing phase without a blocking user question).
