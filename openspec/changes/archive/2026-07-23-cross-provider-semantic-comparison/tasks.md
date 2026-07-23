# Task Breakdown: `cross-provider-semantic-comparison`

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

## Phase 1: Core Implementation
- [x] 1.1 Crear `type_equivalences.py` en `domain/comparison/`.
- [x] 1.2 Extender `compare_snapshots()` en `compare/engine.py` para soportar el parámetro `mode: ComparisonMode`.

## Phase 2: Testing & Verification
- [x] 2.1 Pruebas unitarias para equivalencia semántica de tipos (`test_cross_provider_semantic.py`).
- [x] 2.2 Pruebas de comparación heterogénea entre PostgreSQL, SQL Server, Oracle y MySQL.
- [x] 2.3 Ejecución de la suite completa de pruebas.
