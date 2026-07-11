# Proposal: TUI Run & Report Actions

## Intent

Expand the existing read-only `--tui` findings browser
(`interactive-tui`, archived `openspec/changes/archive/2026-07-10-interactive-tui/`)
with three new interaction modes from within the same TUI session,
explicitly called out as future work in that capability's Non-Goals:

1. Define/edit the list of excluded tables (today only settable via the
   `--exclude-tables` CLI flag) for the current run/session, in memory
   only.
2. Re-run the comparison (extract + compare) from within the TUI using the
   current profiles and the current in-memory exclude list, refreshing
   the displayed findings without exiting the TUI.
3. Generate HTML/PDF/Excel reports on demand from within the TUI for the
   currently displayed `ComparisonResult`, rather than only ever getting
   them unconditionally at CLI startup.

## Scope

### In Scope

- An in-memory exclude-tables editor: an `Input` widget (bound to a new
  key, `e`) pre-seeded with the CLI's initial `--exclude-tables` patterns
  (or empty if none were given), whose committed value both updates
  in-memory exclude state and immediately triggers a comparison re-run
  with the new excludes (Decision 2). This list is **never** written back
  to `config.local.yaml`, `config.example.yaml`, or any file — it exists
  only for the current TUI session (approved constraint).
- A "run comparison" action (bound to a new key, `r`) that re-extracts
  schemas for the profiles the CLI already loaded at launch, re-applies
  the current in-memory exclude patterns, re-compares, and replaces the
  displayed `ComparisonResult` — usable with or without having just
  edited the exclude list (e.g. to observe live schema drift since
  launch).
- A "generate reports" action (bound to a new key, `g`) that produces a
  fresh, timestamped HTML/PDF/Excel report triple for the **currently
  displayed** `ComparisonResult` (which may differ from the one shown at
  launch, if "run comparison" was used), on demand, reusing the same
  per-format-isolated generation logic `write_reports` already uses
  (Decision 1, Decision 4).
- Running blocking extract+compare work (and report generation) on a
  Textual worker, never on the UI thread, so the interface stays
  responsive; a status/log panel communicates progress, success, and
  per-format or extraction failures without corrupting the TUI's owned
  terminal state or crashing the app (Decision 3, Decision 4).
- A narrowly scoped change to when `write_reports`'s automatic HTML/PDF/
  Excel generation happens: when `--tui` is passed **and** the interactive
  TUI actually launches (interactive terminal), that automatic upfront
  generation is skipped — those formats are now produced only via the new
  in-TUI "generate reports" action. Every other invocation shape (no
  `--tui`, or `--tui` falling back to the plain console on a non-TTY)
  keeps today's unconditional-at-startup behavior unchanged (Decision 1).
- Unit tests for the new pure exclude/re-run/report-trigger logic,
  `Pilot`-driven interaction tests for the three new key bindings and
  their status-log feedback, and CLI-level tests for the new conditional
  generation branch.

### Out of Scope

- Persisting the in-memory exclude list back to any YAML config file —
  explicitly rejected per this change's approved scope; excludes edited
  in the TUI apply only to the current session/run.
- Any connection-management screens (list/add/edit/delete connections,
  choosing which profiles to compare) — still out of scope, unchanged
  from the baseline `interactive-tui` spec's Non-Goals; this remains a
  separate, not-yet-started roadmap item.
- Selecting individual report formats to generate (e.g. "only HTML") —
  the "generate reports" action always produces all three formats
  together, per-format isolated, mirroring `write_reports`'s existing
  all-or-nothing-per-run philosophy.
- Any change to the comparison engine, diff-entry shapes, or HTML/PDF/
  Excel rendering internals — all are unchanged, read-only inputs/outputs
  to the new actions.
- Any change to non-`--tui` or fallback (`--tui` on a non-TTY) behavior —
  both continue to generate all three report formats unconditionally at
  startup exactly as today.

## Capabilities

### Modified Capabilities

- `interactive-tui`: gains three new ADDED requirements (exclude editing,
  run comparison, generate reports) and a narrowed Non-Goals section
  (removing the blanket "no run/re-extract action" and "no report
  generation from the TUI" exclusions, which this change now implements
  under the approved in-memory-only/on-demand constraints).
- `reporting-and-output`: one existing requirement (automatic,
  unconditional HTML/PDF generation) is narrowed specifically for the
  case where `--tui` is passed and the interactive TUI actually launches;
  every other invocation shape is unaffected.

## Approach

### Decision 1 — Automatic report generation becomes conditional on the interactive TUI actually launching

**Decision: `write_reports` gains a new keyword-only parameter,
`generate_reports: bool = True`. `cli.py` passes `generate_reports=False`
only when it is about to hand off to the interactive TUI (i.e., `--tui`
was passed and the terminal is interactive); every other case (`--tui`
omitted, or `--tui` falling back on a non-TTY) keeps the default `True`,
preserving today's unconditional-at-startup behavior exactly.**

- Rationale: this was the subject of an explicit clarify-gate question
  during this change's planning. The alternative (keep unconditional
  generation always, treat the TUI's "generate reports" action as purely
  additive on top of it) was rejected in favor of this option, so that a
  user working inside the TUI — especially after editing excludes and
  re-running the comparison — is not left with a stale, launch-time
  report triple sitting alongside a fresher on-demand one with no relation
  between the two filenames. Scoping the change narrowly to "interactive
  TUI actually launched" (not to `--tui` being merely requested) means the
  non-TTY fallback path is untouched — it still behaves exactly like a
  non-`--tui` run, which is the existing REQ-interactive-tui-002 contract
  this change does not revisit.

### Decision 2 — Exclude editing applies immediately and re-runs the comparison

**Decision: the exclude-tables `Input` widget's committed value (`Enter`)
does two things atomically: (a) replaces the in-memory exclude-pattern
list, and (b) immediately triggers a "run comparison" using the new list.
The separate `r` binding exists to re-run comparison without touching
excludes (e.g. to pick up live schema drift since launch).**

- Rationale: an excludes editor whose edits only take effect after a
  second, separate manual action would be a confusing two-step flow for
  what is conceptually one user intent ("show me the comparison with
  these tables excluded"). Collapsing edit+apply into one committed
  action matches how `--exclude-tables` already works today (a single CLI
  argument that takes effect for the whole run) as closely as an
  interactive, session-scoped equivalent can, while `r` still covers the
  materially different intent of "nothing changed about excludes, I just
  want fresh data."

### Decision 3 — Blocking extract+compare and report generation run on a Textual worker

**Decision: both "run comparison" and "generate reports" execute inside a
Textual worker (`@work`/`run_worker`), never directly on the UI/event-loop
thread; a status/log widget shows an in-progress indicator while the
worker runs, and the final success/failure outcome.**

- Rationale: `extract_schema` performs live `pyodbc` network I/O and
  report generation performs file I/O — both are blocking calls that,
  run directly on Textual's single-threaded event loop, would freeze
  keyboard input, rendering, and the quit binding for the call's entire
  duration (this can be tens of seconds against several live databases).
  A dedicated worker keeps the app responsive and is Textual's documented
  mechanism for exactly this kind of blocking-call integration.

### Decision 4 — Report-generation output is captured, not printed to `sys.stdout`

**Decision: the on-demand "generate reports" action calls a reusable
`generate_reports(result, *, out=...)` function (extracted from
`write_reports`'s existing HTML/PDF/Excel try/except blocks, see design)
with an in-memory buffer as `out`, and appends the captured
success/failure lines to the TUI's own status/log widget, rather than
letting them reach `sys.stdout` directly.**

- Rationale: `write_reports` already prints its per-format outcome lines
  to `out` (defaulting to `sys.stdout`); while a Textual `App` owns the
  terminal, anything written directly to real `sys.stdout` would corrupt
  the TUI's rendered screen. Capturing that same, already-isolated output
  into a buffer and rendering it inside a normal Textual widget keeps the
  per-format failure-isolation contract (REQ-reporting-and-output-004)
  intact while presenting it through the TUI's own UI instead of the raw
  terminal stream.

### Decision 5 — Spec ownership: extend `interactive-tui`, narrow `reporting-and-output`, no new capability

**Decision: no new spec domain is created.** The three new interactions
are additional requirements of the existing `interactive-tui` capability
(the TUI is what changed, not a new independent domain), and the single
behavior change to automatic-generation timing is expressed as a MODIFIED
requirement inside `reporting-and-output`, narrowly scoped to the
interactive-TUI-launched case.

- Rationale: matches the one-roadmap-line-per-domain convention only
  where a genuinely new domain of behavior is introduced; here, all three
  additions are new ways of interacting with the same TUI capability
  already documented at `openspec/specs/interactive-tui/spec.md`, and the
  one cross-cutting behavior change belongs textually where the
  unconditional-generation contract already lives
  (`reporting-and-output`), not duplicated or restated inside
  `interactive-tui`.

## Rollback Plan

- The three new key bindings (`e`, `r`, `g`), the exclude-editor `Input`
  widget, and the status/log panel are additive to
  `src/schema_comparator/tui/`; removing them reverts the TUI to today's
  read-only browser with no functional loss to the existing filter/
  navigate/quit/detail-panel behavior.
- `write_reports`'s new `generate_reports` parameter defaults to `True`;
  removing the parameter (and `cli.py`'s single new call site passing
  `generate_reports=False`) fully restores today's unconditional-at-
  startup behavior for every invocation shape, including `--tui`.
- `generate_reports(result, *, out=...)`, extracted from `write_reports`'s
  existing try/except blocks, is a pure refactor with no behavior change
  to the non-TUI path; reverting it (inlining the blocks back into
  `write_reports`) is mechanical and carries no data-loss risk.
- No profile, connection-string, or persisted-config file is ever written
  by this change (excludes remain in-memory only), so there is no
  config-file state to roll back.
