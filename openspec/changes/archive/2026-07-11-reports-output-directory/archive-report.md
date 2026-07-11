# Archive Report: Reports Output Directory

**Change**: `reports-output-directory`
**Archive date**: 2026-07-11
**Route**: lite (proposal-lite.md, no design.md)
**Verification verdict**: PASS

## Close Gate

`state.yaml`'s `phases.verify` reports **PASS**: all 4 scenarios in
REQ-reporting-and-output-002 (MODIFIED) verified against implementation —
shared timestamp, `reportes/` subdirectory location, auto-creation on
absence, per-format failure isolation preserved. No CRITICAL/WARNING
findings. Archive is permitted.

## Reconciliation (prerequisite to this archive)

This change's delta modifies `REQ-reporting-and-output-002` concurrently
with the `tui-interactive-actions` change (which also modifies the same
requirement, adding a TUI-launched conditional-skip clause). This
conflict was identified and resolved prior to archiving (see this
change's `state.yaml` `reconciliation:` entry): both changes' change-local
spec deltas were reconciled to an identical merged REQ-002 text combining
the `reportes/`+Excel naming (this change) and the TUI-conditional-skip
clause (`tui-interactive-actions`), matching the already-merged
implementation in `report/write.py`.

## Specification Synchronization

| Domain | Action | Details |
|--------|--------|---------|
| `reporting-and-output` | Modified | [openspec/specs/reporting-and-output/spec.md](../../../specs/reporting-and-output/spec.md)'s `REQ-reporting-and-output-002` replaced with the reconciled merged text (title, body, and 7 scenarios) from this change's delta, already including the `tui-interactive-actions` TUI-conditional-skip clause so the baseline converges correctly regardless of archive order. |

No other capability's baseline was touched by this change.

## Decisions and ADRs

`assumptions` recorded one item ("raiz del proyecto" = CLI invocation
cwd), consistent with the existing REQ-002 baseline's own cwd-relative
convention; no separate ADR was warranted. The single approval
(`approval-reports-output-directory-001`, lite-mode process gate) is a
scope/process decision fully reflected in `proposal-lite.md`.

## Archive Copy

Artifacts moved to
`openspec/changes/archive/2026-07-11-reports-output-directory/`. The
active source directory (`openspec/changes/reports-output-directory/`)
was removed as part of this move.
