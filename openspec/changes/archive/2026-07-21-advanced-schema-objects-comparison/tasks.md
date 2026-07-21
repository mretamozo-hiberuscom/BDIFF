# Task Breakdown: `advanced-schema-objects-comparison`

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

## Phase 1: Core Implementation
- [x] 1.1 Extender `domain/schema/models.py` con `PrimaryKeySnapshot`, `ForeignKeySnapshot`, `IndexSnapshot` y actualizar `TableSnapshot`.
- [x] 1.2 Actualizar el motor de comparación en `domain/comparison/` para soportar objetos de esquema avanzados.

## Phase 2: Testing & Verification
- [x] 2.1 Pruebas unitarias de dominio para los nuevos modelos y `TableSnapshot`.
- [x] 2.2 Pruebas unitarias del motor de comparación con PKs, FKs e Índices (`test_advanced_schema_objects.py`).
- [x] 2.3 Ejecución de la suite completa de pruebas.
