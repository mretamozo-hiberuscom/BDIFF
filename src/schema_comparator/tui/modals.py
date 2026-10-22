"""Modal dialogs shared by the TUI screens: a generic yes/no confirmation
and the help card."""

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from schema_comparator.tui.theme import SEPARATOR


class ConfirmModal(ModalScreen[bool]):
    """Asks the user to confirm an action; dismisses with True or False.

    `body` is Rich markup. Enter activates the focused button, which
    starts on the confirm one (on the cancel one with `focus_cancel`, for
    actions that cannot be undone); Esc and N always cancel.
    """

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    ConfirmModal > #confirm-dialog {
        width: 64;
        max-width: 90%;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    ConfirmModal > #confirm-dialog.-warning {
        border: thick $warning;
    }
    ConfirmModal > #confirm-dialog.-danger {
        border: thick $error;
    }
    ConfirmModal #confirm-title {
        text-style: bold;
        margin-bottom: 1;
    }
    ConfirmModal #confirm-buttons {
        margin-top: 1;
        height: auto;
        align-horizontal: right;
    }
    ConfirmModal #confirm-buttons Button {
        margin-left: 2;
    }
    """

    BINDINGS = [
        Binding("escape,n", "cancel", "Cancelar"),
        Binding("y,s", "confirm", "Confirmar"),
    ]

    def __init__(
        self,
        title: str,
        body: str,
        *,
        confirm_label: str = "Aceptar",
        cancel_label: str = "Cancelar",
        severity: str = "primary",
        focus_cancel: bool = False,
    ) -> None:
        super().__init__()
        self._title = title
        self._body = body
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label
        self._severity = severity
        self._focus_cancel = focus_cancel

    def compose(self) -> ComposeResult:
        variant = {"warning": "warning", "danger": "error"}.get(
            self._severity, "primary"
        )
        with Vertical(id="confirm-dialog", classes=f"-{self._severity}"):
            yield Label(self._title, id="confirm-title")
            yield Static(Text.from_markup(self._body), id="confirm-body")
            with Horizontal(id="confirm-buttons"):
                yield Button(self._cancel_label, id="btn-cancel")
                yield Button(self._confirm_label, id="btn-confirm", variant=variant)

    def on_mount(self) -> None:
        self.query_one(
            "#btn-cancel" if self._focus_cancel else "#btn-confirm", Button
        ).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-confirm")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class QuitModal(ConfirmModal):
    """Confirms leaving the app; pressing q again confirms."""

    BINDINGS = [Binding("q", "confirm", "Salir")]

    def __init__(self) -> None:
        super().__init__(
            "¿Salir de BDIFF?",
            "Los reportes y scripts que ya generaste se conservan en disco.",
            confirm_label="Salir",
            cancel_label="Seguir aquí",
        )


_HELP = f"""[bold]Para qué sirve[/bold]
BDIFF compara el esquema de varias bases y muestra dónde se desvían.
Nunca ejecuta cambios por ti: los scripts los revisas y ejecutas tú.

[bold]Flujo recomendado[/bold]
  1. Recorre los hallazgos con [bold]↑ ↓[/bold] y lee el detalle a la derecha.
  2. Si hay ruido, excluye tablas con [bold]e[/bold] y se recompara solo.
  3. Decide qué corregir con [bold]c[/bold]: se generan scripts en scripts-db/.
  4. Guarda los reportes HTML, PDF y Excel con [bold]g[/bold].

[bold]Atajos[/bold]
  [bold]/[/bold]  filtrar            [bold]c[/bold]  consolidar (antes [bold]d[/bold])
  [bold]e[/bold]  excluir tablas     [bold]r[/bold]  recomparar
  [bold]l[/bold]  registro           [bold]g[/bold]  generar reportes
  [bold]v[/bold]  rutinas            [bold]q[/bold]  salir
  [bold]Esc[/bold] cierra lo abierto

[bold]Símbolos[/bold]
  [red]✖[/] tabla faltante   [dark_orange]–[/] columna faltante   [yellow]≠[/] discrepancia
  [dark_orange]ƒ[/] rutina   [dim]{SEPARATOR}[/dim] el número entre paréntesis cuenta hallazgos
"""


ROUTINES_HELP = """[bold]Para qué sirve[/bold]
Comprueba que las rutinas y vistas de SQL Server no tengan dependencias rotas
y, si lo decides, recompila sus metadatos.

[bold]Atajos[/bold]
  [bold]v[/bold]  validar dependencias (solo lectura)
  [bold]r[/bold]  recompilar metadatos (pide confirmación)
  [bold]s[/bold]  guardar el script de reparación en scripts-db/
  [bold]Esc[/bold] volver

[bold]Qué hace cada acción[/bold]
  Validar nunca modifica nada.
  Recompilar ejecuta sp_refreshsqlmodule solo en rutinas sin firma;
  las firmadas se omiten para no perder su firma.
  Guardar script escribe archivos; no los ejecuta.
"""


class HelpModal(ModalScreen[None]):
    """What BDIFF does, the usual flow and every key; any other card of
    help (title and Rich markup) can be shown the same way."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    HelpModal > #help-dialog {
        width: 76;
        max-width: 95%;
        height: auto;
        max-height: 90%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
        overflow-y: auto;
    }
    HelpModal #help-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    HelpModal #help-close {
        margin-top: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [Binding("escape,question_mark,enter,q", "close", "Cerrar")]

    def __init__(self, title: str = "Ayuda de BDIFF", body: str = _HELP) -> None:
        super().__init__()
        self._title = title
        self._body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield Label(self._title, id="help-title")
            yield Static(Text.from_markup(self._body))
            yield Label("Pulsa Esc para cerrar", id="help-close")

    def action_close(self) -> None:
        self.dismiss(None)
