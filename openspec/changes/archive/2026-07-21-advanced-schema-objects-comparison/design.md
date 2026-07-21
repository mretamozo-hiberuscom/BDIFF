# Design Document: Advanced Schema Objects Comparison

## Overview
Modelado e integración de restricciones de Clave Primaria, Claves Foráneas e Índices en el dominio y motor de comparación de BDIFF.

## Domain Models Design (`domain/schema/models.py`)
- `@dataclass(frozen=True, slots=True) PrimaryKeySnapshot`:
  - `name: str`
  - `columns: tuple[str, ...]`
- `@dataclass(frozen=True, slots=True) ForeignKeySnapshot`:
  - `name: str`
  - `columns: tuple[str, ...]`
  - `referenced_table: str`
  - `referenced_columns: tuple[str, ...]`
  - `on_delete: str | None = None`
  - `on_update: str | None = None`
- `@dataclass(frozen=True, slots=True) IndexSnapshot`:
  - `name: str`
  - `columns: tuple[str, ...]`
  - `is_unique: bool = False`

## TableSnapshot Extensions
- `primary_key: PrimaryKeySnapshot | None = None`
- `foreign_keys: tuple[ForeignKeySnapshot, ...] = ()`
- `indexes: tuple[IndexSnapshot, ...] = ()`

## Comparison Engine (`domain/comparison/engine.py`)
- Extender la comparación N-way para evaluar coincidencia de PKs, FKs e Índices entre la línea base y los perfiles comparados.
