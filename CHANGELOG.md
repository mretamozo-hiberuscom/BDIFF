# Changelog

Todas las modificaciones destacables de este proyecto se documentarán en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/), y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [0.3.0] - 2026-07-21

### Añadido
- Arquitectura desacoplada basada en Hexagonal (Puertos y Adaptadores).
- Hoja de ruta arquitectónica para soporte multitarget (PostgreSQL, Oracle, MySQL, SQLite, SQL Server) y ADRs 0001 a 0005 en `docs/architecture/`.
- Registro interno de proveedores de base de datos (`ProviderRegistry`) con carga diferida (*lazy loading*).
- Formato de configuración v2 (`ConnectionProfile`) compatible con especificación de proveedor y opciones por perfil.
- Modelos de dominio canónicos: `QualifiedName`, `SqlType`, `TypeFamily`, `ProviderCapabilities` y política `native-strict`.
- Adaptador extraído de SQL Server (`SqlServerProvider`) en `infrastructure/providers/sqlserver/`.
- Escapado de seguridad T-SQL (`]` -> `]]`, `'` -> `''`) en el generador de scripts DDL para prevenir inyección SQL.

### Cambiado
- Re-exportación transparente en conectores, discovery y consolidación para garantizar 100% de compatibilidad hacia atrás.

## [0.2.0] - 2026-07-20

### Añadido
- Agrupamiento de entradas de `MissingColumn` en un único bloque de decisión (`MergedMissingColumn`) dentro de `DecisionScreen` en la consolidación del TUI.
- Selección por defecto de todos los perfiles ausentes al agregar columnas faltantes en múltiples perfiles.
- Filtrado automático al seleccionar eliminación (`DROP COLUMN`), mostrando únicamente los perfiles donde la columna sí existe.
- Requisito `REQ-interactive-tui-014` y escenarios en la especificación OpenSpec de `interactive-tui`.
- Pruebas unitarias para validar `MergedMissingColumn` en `tests/unit/tui/test_decision_screen.py`.
