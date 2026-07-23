# Change Proposal: `cross-provider-semantic-comparison`

## Summary
Implementa el modo de comparación semántica heterogénea (`semantic-equivalent`) entre distintos motores de base de datos (SQL Server, PostgreSQL, SQLite, MySQL, MariaDB, Oracle). Permite comparar esquemas entre proveedores diferentes utilizando una matriz de equivalencia de familias de tipos y genera reportes de portabilidad y advertencias semánticas. Con este cambio se consolida la API pública y se alcanza la versión estable 1.0.0.

## Motivation
Permitir a los usuarios comparar la estructura de bases de datos heterogéneas en migraciones o arquitecturas multibase de datos sin falsos positivos derivados de diferencias sintácticas nativas (ej. `VARCHAR2` vs `VARCHAR`, `INT` vs `INTEGER`, `BOOLEAN` vs `TINYINT(1)`).

## Proposed Scope
- Crear `src/schema_comparator/domain/comparison/type_equivalences.py` con la matriz de equivalencia semántica de tipos.
- Extender `compare_snapshots()` para admitir el parámetro opcional `mode: ComparisonMode = ComparisonMode.NATIVE_STRICT`.
- Cuando `mode == ComparisonMode.SEMANTIC_EQUIVALENT`, evaluar compatibilidad semántica entre tipos de proveedores heterogéneos.
- Pruebas unitarias de comparación semántica y portabilidad entre proveedores.

## Risk & Safety Assessment
- **Risk:** Bajo. El modo predeterminado sigue siendo `native-strict`. `semantic-equivalent` es una capacidad opt-in.
- **Rollback:** Eliminar `type_equivalences.py` y deshabilitar el parámetro `mode` en `compare_snapshots`.
