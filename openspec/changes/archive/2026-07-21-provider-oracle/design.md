# Design Document: Oracle Provider

## Overview
Implementación del proveedor de infraestructura `oracle` utilizando la biblioteca `oracledb` (Thin mode por defecto).

## Architecture & Components
- `src/schema_comparator/infrastructure/providers/oracle/`:
  - `connection.py`: Conexión mediante `oracledb.connect()` (interpreta DSN, host, port, service_name, user, password).
  - `introspector.py`: Consulta catalog SQL sobre `ALL_TABLES` y `ALL_TAB_COLUMNS`.
  - `profile_parser.py`: Parsea cadenas de conexión ADO.NET/DSN Oracle y opciones de perfil.
  - `errors.py`: Traduce excepciones de `oracledb` a `ConnectionFailedError` y `MetadataAccessError`.
  - `ddl_renderer.py`: Renderizador DDL con comillas dobles y sintaxis Oracle (`ADD (...)`, `MODIFY (...)`).
  - `provider.py`: Implementa `DatabaseProvider` con `provider_id="oracle"`.

## Identifier & Type Rules
- Identificadores: `"OWNER"."TABLE_NAME"`, `"COLUMN_NAME"`
- Mapeo de tipos: `NUMBER`, `VARCHAR2`, `CHAR`, `CLOB`, `DATE`, `TIMESTAMP`
