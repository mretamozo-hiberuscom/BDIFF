# Change Proposal: `provider-oracle`

## Summary
Incorpora soporte para Oracle Database como proveedor de infraestructura de BDIFF (`OracleProvider`). Permite la introspección de esquemas mediante `ALL_TAB_COLUMNS` y `ALL_TABLES` (Thin mode con `oracledb`), mapeo de `OWNER` a nombre de esquema, gestión de tipos nativos (`NUMBER`, `VARCHAR2`, `CLOB`, `TIMESTAMP`), quoting de identificadores con comillas dobles (`"OWNER"."TABLE"`) y generación de scripts DDL de migración Oracle.

## Motivation
Soportar la comparación de esquemas en entornos corporativos que utilizan bases de datos Oracle Database.

## Proposed Scope
- Crear paquete `src/schema_comparator/infrastructure/providers/oracle/`.
- Implementar `OracleProvider` cumpliendo con el puerto `DatabaseProvider`.
- Registro diferido en `ProviderRegistry` para la clave `oracle`.
- Añadir dependencia opcional `oracle = ["oracledb>=2.0"]` en `pyproject.toml`.
- Renderer DDL específico para sintaxis Oracle.
- Pruebas unitarias de introspección, parsing, registro y renderizado DDL.

## Risk & Safety Assessment
- **Risk:** Bajo. El nuevo adaptador está totalmente aislado en su módulo de infraestructura.
- **Rollback:** Eliminar el directorio `oracle` y remover su fábrica de `ProviderRegistry`.
