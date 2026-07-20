# Changelog

Todas las modificaciones destacables de este proyecto se documentarán en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/), y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [0.2.0] - 2026-07-20

### Añadido
- Agrupamiento de entradas de `MissingColumn` en un único bloque de decisión (`MergedMissingColumn`) dentro de `DecisionScreen` en la consolidación del TUI.
- Selección por defecto de todos los perfiles ausentes al agregar columnas faltantes en múltiples perfiles.
- Filtrado automático al seleccionar eliminación (`DROP COLUMN`), mostrando únicamente los perfiles donde la columna sí existe.
- Requisito `REQ-interactive-tui-014` y escenarios en la especificación OpenSpec de `interactive-tui`.
- Pruebas unitarias para validar `MergedMissingColumn` en `tests/unit/tui/test_decision_screen.py`.
