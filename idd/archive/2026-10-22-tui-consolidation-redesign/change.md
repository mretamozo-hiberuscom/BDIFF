# tui-consolidation-redesign

## Intent and acceptance

Rediseñar la pantalla de consolidación de la TUI: tarjetas por tabla con símbolos y estado de decisión, modal de confirmación antes de generar scripts con DROP, destinos de una discrepancia de columna limitados a los perfiles que la tienen y difieren, y confirmación al descartar decisiones

Acceptance: Con un DROP marcado, Generar SQL abre un modal que lista lo que se elimina por perfil y no escribe scripts hasta confirmar; una discrepancia solo ofrece como destino los perfiles que tienen la columna con atributos distintos del elegido; Esc/Cancelar con decisiones pide confirmación; la pantalla usa los símbolos y el tuteo del tema común sin emojis

## Plan

1. Modelo (`decision_model.py`): `destination_choices` sin parámetro de perfiles; una discrepancia ofrece los perfiles que tienen la columna con atributos distintos del elegido; `build_resolutions` filtra siempre con esa regla; `drops_in` resume los DROP a confirmar.
2. Pantalla (`decision_screen.py`, `modals.py`): modal de DROP al generar (foco en Cancelar), confirmación al descartar con decisiones, resumen de avance, lista de tablas con ✔, título de destino que sigue a la acción.
3. Documentación: README, alcance funcional y roadmap.

## Decisions

- El usuario decidió (2026-10-22): el modal de DROP sale una vez al pulsar Generar SQL, no al marcar cada DROP; Esc o Cancelar piden confirmación solo si hay decisiones marcadas.
- La regla de destinos vive en el modelo, sin Textual, y la pantalla solo la pinta (ADR 0001).
- `ConfirmModal` gana `focus_cancel` para acciones irreversibles; el de DROP lo usa.
- La etiqueta «Crear tabla en:» no seguía a la acción DROP; ahora se actualiza al cambiar la opción.

## Evidence

<!-- ospec:evidence:start -->
- ev-1: adr-impact-declaration for adr-impact-declaration (2026-10-22T09:34:49.887Z)
- ev-2: check-run for checks-pass (2026-10-22T09:35:55.417Z)
- ev-3: living-doc-current for living-doc (2026-10-22T09:35:58.239Z)
<!-- ospec:evidence:end -->
