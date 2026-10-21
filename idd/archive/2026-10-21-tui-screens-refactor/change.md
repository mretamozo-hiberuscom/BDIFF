# tui-screens-refactor

## Intent and acceptance

decision_screen.py (820 líneas) mezcla lógica de dominio con widgets: fusión de hallazgos y construcción de resoluciones dentro del Screen, ramas muertas para MissingTable/MissingColumn sin fusionar, cálculo de destinos duplicado entre compose y handle_radio_change, BINDINGS declarado dos veces y reenvío de eventos con except: pass; el bucle conectar/enumerar/filtrar rutinas está triplicado en cli.py y procedure_screen.py

Acceptance: La fusión de hallazgos, los destinos por decisión y la construcción de resoluciones viven en un módulo puro probado sin Textual; el bucle de rutinas existe una vez; la suite existente sigue en verde sin cambiar sus expectativas

## Plan

1. `tui/decision_model.py` (sin Textual): tarjetas fusionadas
   (`MergedMissingTable`, `MergedMissingColumn`), `group_findings`,
   `destination_choices`, `default_destinations` y `build_resolutions`.
   `decision_screen.py` solo renderiza (820 → 470 líneas): sin ramas
   muertas para hallazgos sin fusionar, un único `BINDINGS`, cada tarjeta
   maneja sus propios eventos (sin `except: pass`).
2. `sqlserver/routine_runner.py`: el bucle conectar → enumerar → excluir →
   operar existe una vez y lo usan el CLI y la pantalla de rutinas.

## Decisions

### Decision: Efectos visibles de la unificación

Kind: dc

Al compartir código aparecen tres diferencias menores, todas hacia el
comportamiento ya documentado del CLI: la pantalla de rutinas compara los
patrones de exclusión sin distinguir mayúsculas (antes solo el CLI); la
lista de destinos que se rehace al cambiar de opción escapa los nombres de
perfil (el cambio `tui-markup-escape` no cubrió ese punto); y un fallo sin
mensaje se imprime como "Error" en lugar de "None".

### Decision: Sin tests nuevos

Kind: dc

Es un refactor: `ospec check` se ejecutó antes de la primera edición y
`test_decision_screen.py`, `test_procedure_screen.py` y los tests del CLI
fijan el comportamiento que se preserva.

### Decision: Bug pendiente fuera de alcance

Kind: dc

En una discrepancia de columna, la consolidación ofrece como destino todos
los perfiles, también los que no tienen la columna (el UPDATE generado no
compila allí). Corregirlo cambia comportamiento; queda en el roadmap.

## Evidence

<!-- ospec:evidence:start -->
- ev-1: check-run for checks-pass (2026-10-21T11:31:47.110Z)
- ev-2: check-run for checks-pass (2026-10-21T11:34:43.418Z)
- ev-3: adr-impact-declaration for adr-impact-declaration (2026-10-21T11:34:43.418Z)
- ev-4: living-doc-current for living-doc (2026-10-21T11:34:46.099Z)
<!-- ospec:evidence:end -->
