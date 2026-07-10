# Architecture Decision Records

This project uses lightweight ADRs for decisions that need durable
rationale beyond what fits in `docs/architecture/technical-baseline.md`.

For the foundation phase, all initial technical decisions (driver, auth,
discovery method, report format, dependency manager) were resolved
directly in `technical-baseline.md`'s Decisions table, since they were
made together as a single coherent baseline with clear rationale and did
not warrant separate ADR files yet.

## When to add an ADR here

Add a new `NNNN-title.md` file in this directory when a future decision:

- Reverses or significantly changes a baseline decision (e.g. switching
  from pyodbc to another driver, or adding DDL-export discovery as a
  first-class mode).
- Involves a non-obvious tradeoff worth preserving for future readers
  (e.g. choosing a specific rename-detection heuristic algorithm).
- Is made during `sdd-design` for a specific change and should outlive
  that change's folder once archived.

## Format

```markdown
# NNNN. Title

Status: proposed | accepted | superseded by NNNN
Date: YYYY-MM-DD

## Context
## Decision
## Consequences
```

No ADRs exist yet — this is the first entry point, created empty during
`sdd-foundation`.
