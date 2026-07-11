# Archive Report: TUI Interactive Actions

**Change**: `tui-interactive-actions`
**Archive date**: 2026-07-11
**Verification verdict**: PASS (one pre-existing WARNING carried over, accepted)

## Close Gate

`state.yaml`'s `phases.verify` reports **PASS**: all 5 requirements
(REQ-interactive-tui-011/012/013, REQ-reporting-and-output-001/002)
covered by implementation and tests. Full suite 300 passed / 1 skipped,
99% coverage, no lint/type errors. One pre-existing WARNING carried over
unresolved (Excel export has no corresponding requirement in the
`reporting-and-output` baseline's Purpose section) — this is resolved by
this same archive step, since `reports-output-directory` (archived
earlier in this same session) already widened REQ-reporting-and-output-002
to explicitly name Excel. Task 6.4 (manual interactive smoke test) was
left unchecked, requiring a real interactive terminal not exercisable in
an automated session; accepted as a non-blocking follow-up. Archive is
permitted.

## Reconciliation (prerequisite to this archive)

This change's delta modifies `REQ-reporting-and-output-002` concurrently
with `reports-output-directory` (archived earlier in this same session,
which also modifies the same requirement to move output into a fixed
`reportes/` directory and name Excel explicitly). This conflict was
identified and resolved prior to archiving either change (see this
change's `state.yaml` `reconciliation:` entry): both changes' change-local
spec deltas were reconciled to an identical merged REQ-002 text, matching
the already-merged implementation in `report/write.py`. Since
`reports-output-directory` archived first and already applied that merged
text to the baseline, this archive step only needed to additionally apply
this change's REQ-reporting-and-output-001 modification (non-overlapping)
and its interactive-tui additions.

## Specification Synchronization

| Domain | Action | Details |
|--------|--------|---------|
| `reporting-and-output` | Modified | [openspec/specs/reporting-and-output/spec.md](../../../specs/reporting-and-output/spec.md)'s `REQ-reporting-and-output-001` gained the trigger-independence clarification (rendering happens whether triggered at startup or on demand from the TUI). `REQ-reporting-and-output-002` was already merged during the `reports-output-directory` archive step; verified it already includes this change's TUI-conditional-skip clause — no further edit needed. |
| `interactive-tui` | Modified | [openspec/specs/interactive-tui/spec.md](../../../specs/interactive-tui/spec.md)'s Non-Goals narrowed per this change's delta; added REQ-interactive-tui-011 (edit excludes in memory), REQ-interactive-tui-012 (run comparison from TUI), REQ-interactive-tui-013 (generate reports on demand), with their Given/When/Then scenarios copied verbatim; appended the change's clarify-gate Q&A as a new "Session 2026-07-11" Clarifications entry. |

## Decisions and ADRs

Three approvals recorded in `state.yaml` (`process`, `excludes-scope`,
`clarify`) are process/scope decisions already fully reflected in
`proposal.md`, `design.md`, and the spec deltas; no separate project-level
ADR was warranted.

## Archive Copy

Artifacts moved to
`openspec/changes/archive/2026-07-11-tui-interactive-actions/`. The
active source directory (`openspec/changes/tui-interactive-actions/`) was
removed as part of this move.
