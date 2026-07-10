# Proposal: Interactive TUI (`--tui` flag)

## Intent

Implement the Milestone 2 roadmap item: an opt-in interactive TUI, built
with `textual`, that replaces the plain-text console summary with a
navigable, filterable findings browser when the user passes `--tui`. HTML
and PDF report generation are unaffected in every case — `--tui` only
changes whether the plain console summary or the interactive TUI is shown
after HTML/PDF generation completes.

## Scope

### In Scope

- A new `textual` `App` in `src/schema_comparator/tui/` that consumes a
  `ComparisonResult` (the same input `render_console` already takes) and
  renders a single-screen, read-only findings browser:
  - A `Tree` widget with one root node per `schema.table`
    (`entry.qualified_name`), expandable to per-finding leaf nodes, labeled
    the same way `render_console` already formats each line.
  - A single filter `Input` bound to a live substring match over the
    diff-type label (`MissingTable`/`MissingColumn`/`ColumnMismatch`) or
    `schema.table`/column name, hiding non-matching tree nodes.
  - A detail panel showing the full `values_by_profile` breakdown for the
    selected `ColumnMismatch` leaf (strictly more detail than the inline
    console line, not a regression).
  - A header showing `compared_profiles` and per-category counts, and a
    `Footer` with key bindings: `q`/`Escape` to quit, `/` to focus the
    filter input, arrow keys/`j`/`k` to navigate, `Enter`/`Space` to
    toggle expand/collapse.
  - The pure "build tree structure from `ComparisonResult`" and "does this
    entry match this filter string" logic extracted into plain, synchronous
    functions the `App` calls, independently unit-testable without the
    `Pilot` harness.
- A `--tui` boolean flag in `cli.py`, opt-in and off by default.
- TTY/non-interactive-terminal detection and fallback (Decision 3 below).
- A way for `cli.py` to select the TUI instead of the plain console summary
  for the *summary step only*, without touching the HTML/PDF try/except
  isolation in `write_reports` (Decision 1 below).
- New dependencies: `textual` (runtime) and `pytest-asyncio` (dev), per
  Decision 2 below.
- A new `interactive-tui` spec domain (Decision 4 below).
- Correcting the stale `tui/__init__.py` docstring to match this change's
  fixed v1 scope (Decision 5 below).
- Unit tests for the pure tree-building/filter-matching functions
  (synchronous, no `Pilot`), plus a small number of `Pilot`-driven
  interaction tests (navigate, filter, quit) for the `App` itself. Unit
  tests for the `cli.py` flag parsing and the non-TTY fallback branch.

### Out of Scope

- Any connection-management screens (list/add/edit/delete connections),
  or a "run/re-extract" action from within the TUI. The existing
  `tui/__init__.py` docstring describes this broader shell; it is not
  built by this change (see Decision 5).
- Any change to `ComparisonResult`/`DiffEntry` shapes, comparison logic, or
  HTML/PDF rendering — all are frozen, read-only inputs to the TUI.
- Snapshot/pixel-level TUI testing (state-based assertions only for v1,
  per the exploration's recommendation).
- A configurable output-format flag beyond `--tui` (e.g. suppressing
  HTML/PDF) — HTML/PDF generation remains unconditional.
- Large-scale (thousands of nodes) performance tuning of the `Tree` widget
  — deferred unless a real scale problem is observed.

## Capabilities

### New Capabilities

- `interactive-tui`: Given a `ComparisonResult` and an opt-in `--tui` flag
  on an interactive terminal, render a navigable/filterable findings
  browser instead of the plain console summary; on a non-interactive
  terminal, fall back to the plain console summary with a warning.

### Modified Capabilities

- `reporting-and-output`: `write_reports` gains a way to swap out the
  console-summary step for the TUI (or the fallback), without changing the
  HTML/PDF per-format isolation contract (REQ-reporting-and-output-007).
  No existing requirement is weakened; this is an additive parameter.

## Approach

### Decision 1 — Where TTY detection/fallback lives

**Decision: in `cli.py`, before calling `write_reports`.**

`cli.py` checks `sys.stdout.isatty()` and `sys.stdin.isatty()` right after
parsing `--tui`. If both are true, it passes a TUI-invoking console
callable into `write_reports`; otherwise it prints the fallback warning to
`stderr` and passes the existing plain `render_console` callable (or
nothing, letting `write_reports` keep its current default).

`write_reports` gains one new parameter,
`render_summary: Callable[[ComparisonResult], None] = _default_console_summary`,
where `_default_console_summary` wraps today's
`print(render_console(result), file=out)` behavior. `write_reports` calls
`render_summary(result)` inside the existing try/except used for the
console step — the per-format failure isolation (HTML/PDF try/except
blocks) is untouched.

- Rationale: `write_reports` currently has no dependency on
  `sys.stdin`/`sys.stdout.isatty()` and its contract ("always attempt
  HTML/PDF, isolate failures") is about *report generation*, not terminal
  capability detection. Keeping the TTY check in `cli.py` — which already
  owns argument parsing and is the only caller that knows `--tui` was
  requested — avoids coupling `write_reports` to terminal-interactivity
  concerns it doesn't otherwise need, and keeps `write_reports`'s existing
  signature growth minimal (one injected callable vs. new TTY-check
  parameters). `cli.py` remains the single place that decides *which*
  summary renderer to use; `write_reports` remains agnostic to what that
  renderer does internally (plain text or interactive TUI).

### Decision 2 — New dev dependency for testing

**Decision: add `pytest-asyncio` (dev-only) alongside `textual` (runtime).**

- `textual` goes into `pyproject.toml` `[project].dependencies` (it is a
  documented, always-available CLI feature, not a dev-only tool), per the
  exploration's Design Question 1 conclusion (pure-Python, no async
  rewrite of `cli.py` required — `App.run()` blocks synchronously from the
  caller's perspective).
- `pytest-asyncio` goes into `pyproject.toml` `[project.optional-dependencies].dev`,
  since `App.run_test()`/`Pilot`-based interaction tests are `async def`
  and need an asyncio-aware pytest runner. Configure
  `asyncio_mode = "strict"` (via `[tool.pytest.ini_options]` or a
  `pytest.ini`/`pyproject.toml` marker section) rather than `"auto"`, so
  the existing fully-synchronous test suite is unaffected by default and
  only tests explicitly marked `@pytest.mark.asyncio` run under the
  asyncio event loop. This avoids surprising the rest of the test suite,
  per the exploration's caveat.
- No separate Textual-specific pytest plugin is needed beyond
  `pytest-asyncio`: `textual.testing`'s `App.run_test()` is a plain async
  context manager usable with any asyncio-aware test runner: no
  `textual-dev` or additional plugin package is required for v1.

### Decision 3 — Exit code / user-facing behavior on fallback

**Decision: fallback exits 0 (success), matching `write_reports`'s
existing "never raise past itself" posture.**

When `--tui` is requested but `sys.stdout.isatty()`/`sys.stdin.isatty()`
is `False`:

1. `cli.py` prints one line to `stderr`:
   `[WARN] --tui requires an interactive terminal; falling back to plain console summary`.
2. `write_reports` runs with the plain `render_console` summary step
   (identical to not passing `--tui` at all).
3. The overall process exit code is unaffected by the fallback — the run
   is considered a successful comparison (HTML/PDF/console all completed),
   not a failure. Only a hard error in schema extraction/comparison (an
   existing concern unrelated to `--tui`) affects the exit code.

- Rationale: this mirrors the existing per-format failure-isolation
  philosophy already established by `write_reports` — a CI pipeline or
  shared script that always passes `--tui` for local-dev convenience must
  not start failing when run headless. The interactive convenience flag
  must not be able to hold the tool's overall success/failure signal
  hostage.

### Decision 4 — Spec ownership: new `interactive-tui` spec domain

**Decision: create a new `interactive-tui` spec domain, not an extension
of `reporting-and-output`.**

- Rationale: the roadmap explicitly tracks this as its own Milestone 2
  item (`docs/roadmap.md`: "Interactive TUI (`textual`), opt-in via
  `--tui` flag"), distinct from Milestone 1's "Console/TUI summary output"
  line, which was folded into `reporting-and-output`. Prior milestone
  items have consistently mapped one roadmap line to one spec domain
  (`comparison-engine`, `connection-profile-config`,
  `schema-extraction`, `reporting-and-output`); giving the interactive
  browser its own domain keeps that one-to-one convention rather than
  overloading `reporting-and-output` with an unrelated interaction model
  (navigation/filtering) that has nothing to do with HTML/PDF/console
  rendering mechanics. `reporting-and-output` gets only the minimal,
  additive `render_summary` injection point described in Decision 1; the
  TUI's own requirements (tree structure, filtering, key bindings, TTY
  fallback trigger) live in `interactive-tui`.

### Decision 5 — Correcting the stale `tui/__init__.py` docstring

**Decision: replace the current docstring** ("Textual App and screens
(connections list, add/edit connection, run/report)") **with one scoped
to this change's fixed v1 surface**: a read-only findings viewer —
navigate, filter, collapse/expand, quit — consuming a `ComparisonResult`.

- Rationale: the existing docstring describes a materially larger,
  unbuilt TUI (connection management, run/re-extract actions) that this
  change does not implement and that Milestone 2 does not commit to. Per
  the exploration's flagged scope-creep risk, leaving the aspirational
  docstring in place risks future readers assuming more was built than
  actually exists. The docstring will be corrected as part of this
  change's implementation, not left as-is.

## Rollback Plan

- `--tui` is a purely additive, opt-in flag; removing it is a revert of
  the `cli.py` flag registration, the `write_reports` `render_summary`
  parameter (default reverts to always calling `render_console` directly,
  restoring today's exact behavior), and the `src/schema_comparator/tui/`
  module.
- Removing `textual`/`pytest-asyncio` from `pyproject.toml` fully reverses
  the dependency footprint; neither package is imported outside
  `src/schema_comparator/tui/` and its tests.
- HTML/PDF generation is never touched by this change or its rollback:
  both are unconditional today and remain unconditional regardless of
  `--tui`'s presence, absence, or removal. Rolling back `--tui` cannot
  regress HTML/PDF output in any scenario.
- No spec requirement in `reporting-and-output` is weakened or removed by
  this change (only the additive `render_summary` injection point is
  added), so rollback of `interactive-tui` requires no compensating change
  to `reporting-and-output`'s spec beyond removing that one additive
  parameter/requirement if it was documented there.
