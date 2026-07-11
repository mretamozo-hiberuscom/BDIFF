# Archive Report: CLI Distribution

**Change**: `cli-distribution`
**Archive date**: 2026-07-11
**Verification verdict**: PASS

## Close Gate

`state.yaml`'s `phases.verify` reports **PASS**: all 5 MUST requirements
(REQ-cli-distribution-001 through -005) verified against implementation
and tests — first-run provisioning, idempotent skip, self-heal after
`.venv` deletion, unmodified argument/exit-code forwarding, and fail-loud
provisioning failure with no partial ready marker. No CRITICAL/WARNING
findings. Archive is permitted.

## Specification Synchronization

| Domain | Action | Details |
|--------|--------|---------|
| `cli-distribution` | Created | New capability baseline created at [openspec/specs/cli-distribution/spec.md](../../../specs/cli-distribution/spec.md) from the change-local spec delta; 5 requirements (REQ-cli-distribution-001 through -005) with their Given/When/Then scenarios copied verbatim, plus a synthesized Purpose/Non-Goals section drawn from `proposal.md`'s Intent and Out of Scope sections. |

No other capability's baseline (`comparison-engine`, `schema-extraction`,
`connection-profile-config`, `interactive-tui`, `reporting-and-output`)
was touched — this change is purely additive and does not modify
`cli.py`'s own behavior.

## Reconciliation Note

Prior to archiving, this change was checked against the two other
concurrently ready-for-archive changes (`tui-interactive-actions`,
`reports-output-directory`) for spec-delta conflicts. `cli-distribution`
does not touch the `reporting-and-output` or `interactive-tui` domains
those two changes modify, so no reconciliation was required for this
change.

## Decisions and ADRs

No `open_decisions` entries or change-local ADR files were present to
promote. The two approvals recorded in `state.yaml`
(`approval-cli-distribution-001` process gate,
`approval-cli-distribution-002` zero-venv-strategy) are process/scope
decisions already fully reflected in `proposal.md` and the implementation;
no separate project-level ADR was warranted.

## Archive Copy

Artifacts moved to `openspec/changes/archive/2026-07-11-cli-distribution/`.
The active source directory (`openspec/changes/cli-distribution/`) was
removed as part of this move.
