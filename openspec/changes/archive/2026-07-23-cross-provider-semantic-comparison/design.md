# Design Document: Cross-Provider Semantic Comparison

## Overview
Implementación de la matriz de equivalencia semántica de tipos y la política `ComparisonMode.SEMANTIC_EQUIVALENT` para comparación heterogénea entre distintos motores de base de datos.

## Components & Modules
- `src/schema_comparator/domain/comparison/type_equivalences.py`:
  - `TYPE_FAMILY_MAP`: Mapeo de tipos nativos de SQL Server, PostgreSQL, SQLite, MySQL, MariaDB y Oracle a familias de tipos canónicas (`INT`, `STRING`, `FLOAT`, `DECIMAL`, `DATETIME`, `BOOLEAN`, `BINARY`, `JSON`).
  - `are_types_semantically_equivalent(type1: str, type2: str) -> bool`.
- `src/schema_comparator/compare/engine.py`:
  - Firma: `compare_snapshots(snapshots, mode: ComparisonMode = ComparisonMode.NATIVE_STRICT)`.
  - En modo `SEMANTIC_EQUIVALENT`, omitir `ColumnMismatch` si los tipos son semánticamente equivalentes.
