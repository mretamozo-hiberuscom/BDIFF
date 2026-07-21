# Change Proposal: `advanced-schema-objects-comparison`

## Summary
Modela y extiende el motor de comparación de BDIFF para soportar objetos de esquema avanzados: Primary Keys (`PrimaryKeySnapshot`), Foreign Keys (`ForeignKeySnapshot`) e Índices (`IndexSnapshot`) en los snapshots de tabla (`TableSnapshot`) y en la detección de diferencias estructurales.

## Motivation
Ofrecer un análisis de esquema integral que detecte no solo discrepancias en tablas y columnas, sino también en claves primarias, foráneas e índices entre perfiles de base de datos.

## Proposed Scope
- Extender `src/schema_comparator/domain/schema/models.py` con `PrimaryKeySnapshot`, `ForeignKeySnapshot` e `IndexSnapshot`.
- Extender `TableSnapshot` para incluir `primary_key`, `foreign_keys` e `indexes`.
- Extender el motor de comparación `domain/comparison/engine.py` para reportar hallazgos de discrepancia en PKs, FKs e Índices.
- Pruebas unitarias de dominio y comparación.

## Risk & Safety Assessment
- **Risk:** Bajo. Se añaden campos opcionales con valores por defecto tuplas vacías en `TableSnapshot`, garantizando 100% de compatibilidad hacia atrás.
- **Rollback:** Revertir los cambios en los dataclasses de dominio y el motor de comparación.
