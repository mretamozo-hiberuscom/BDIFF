# Task Breakdown: `provider-oracle`

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

## Phase 1: Core Implementation
- [x] 1.1 Crear paquete `oracle` (`connection`, `profile_parser`, `errors`, `introspector`, `ddl_renderer`, `provider`).
- [x] 1.2 Registrar fábrica `oracle` en `ProviderRegistry`.
- [x] 1.3 Configurar extra opcional `oracle = ["oracledb>=2.0"]` en `pyproject.toml`.

## Phase 2: Testing & Verification
- [x] 2.1 Pruebas unitarias para `OracleProvider` (`test_oracle_provider.py`).
- [x] 2.2 Pruebas de renderizado DDL y quoting de identificadores Oracle.
- [x] 2.3 Ejecución de la suite completa de pruebas.
