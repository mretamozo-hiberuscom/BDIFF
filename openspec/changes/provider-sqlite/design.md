# Design — `provider-sqlite`

## Architecture Overview

SQLite no utiliza un servidor cliente-servidor ni admite múltiples esquemas por omisión (fuera de `main`, `temp` y bases adjuntas mediante `ATTACH`). Además, SQLite tiene limitaciones en `ALTER TABLE` (no soporta `ALTER COLUMN TYPE` ni `ALTER COLUMN SET/DROP NOT NULL`).

Por lo tanto, la arquitectura del adaptador de SQLite se compone de:

1. **`SqliteProvider`**:
   - `provider_id = "sqlite"`
   - `capabilities()`: `supports_schemas=False`, `supports_transactional_ddl=True`, `requires_table_rebuild_for_alter=True`.

2. **Introspección (`introspector.py`)**:
   - Usa `PRAGMA table_list` o `sqlite_schema` para listar tablas base.
   - Usa `PRAGMA table_xinfo(table_name)` para obtener nombre de columna, tipo nativo, nullability, valor por defecto, ordinal, clave primaria y si la columna es generada.
   - Normaliza el tipo declarado nativo conservando parámetros de longitud/precisión.

3. **Estrategia Table Rebuild (`ddl_renderer.py`)**:
   - Para operaciones `ADD COLUMN` simples, emite `ALTER TABLE "table" ADD COLUMN ...`.
   - Para modificaciones de columnas discrepantes, genera la secuencia de migración segura `table rebuild`:
     ```sql
     PRAGMA foreign_keys = OFF;
     BEGIN TRANSACTION;
     CREATE TABLE "table_dg_tmp" AS SELECT * FROM "table";
     DROP TABLE "table";
     ALTER TABLE "table_dg_tmp" RENAME TO "table";
     COMMIT;
     PRAGMA foreign_keys = ON;
     ```

4. **Traducción de Errores (`errors.py`)**:
   - Mapea `sqlite3.OperationalError` y `sqlite3.DatabaseError` a `ConnectionFailedError` y `MetadataAccessError`.
