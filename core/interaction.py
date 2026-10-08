from enum import Enum
from time import monotonic


class Gesture(Enum):
    NONE = "none"
    CLICK = "click"
    DRAG = "drag"


class ClickDragResolver:
    # ---------------------------------
    # ¿Click o arrastre?
    #
    # No hay doble click ni temporizadores a proposito. Antes el click se
    # retrasaba 250ms para poder distinguirlo de un doble click, y cualquier
    # evento que se perdiera dejaba el click sin hacer nada. Aqui solo hay dos
    # estados y nada que pueda tragarse una pulsacion.
    #
    # Recibe tuplas (x, y): sin Qt y sin ventanas, para poder probarlo solo.
    # ---------------------------------
    def __init__(self, drag_threshold=12):
        # El umbral nativo de la plataforma (Qt da ~10px) con margen. Por debajo
        # hay que considerarlo temblor de la mano: en un click real el raton
        # siempre se mueve unos pixeles.
        self.drag_threshold = max(12, drag_threshold)

        # Un segundo release (el del doble click) no debe contar como otro click.
        # Es temporal y no un flag permanente: si ese release no llegara nunca,
        # con un flag se quedarian muertos todos los clicks siguientes.
        self.ignore_release_until = 0.0

        self.reset()

    # ---------------------------------
    @staticmethod
    def _distance(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    def reset(self):
        self._press_pos = None
        self._press_window_pos = None
        self._moved = False

    # ---------------------------------
    def press(self, pos, window_pos=None):
        """pos: posicion global del puntero. window_pos: esquina de la ventana."""
        self._press_pos = pos
        self._press_window_pos = window_pos
        self._moved = False

        return Gesture.NONE

    # ---------------------------------
    def move(self, pos):
        """Devuelve DRAG en cuanto el puntero se aleja lo suficiente."""
        if self._press_pos is None:
            return Gesture.NONE

        if not self._moved:
            if self._distance(pos, self._press_pos) > self.drag_threshold:
                self._moved = True

        return Gesture.DRAG if self._moved else Gesture.NONE

    # ---------------------------------
    def ignore_next_release(self):
        """El release sobrante de un doble click no debe contar como click."""
        self.ignore_release_until = monotonic() + 0.2

    # ---------------------------------
    def release(self, window_pos=None):
        """Decide que ha pasado al soltar el boton y reinicia el estado.

        Se mira tambien si la ventana se ha movido, porque cuando el arrastre
        lo lleva el compositor no nos llegan los eventos de movimiento.
        """
        moved = self._moved

        if self._press_window_pos is not None and window_pos is not None:
            if self._distance(window_pos, self._press_window_pos) > self.drag_threshold:
                moved = True

        if moved:
            gesture = Gesture.DRAG
        elif monotonic() < self.ignore_release_until:
            gesture = Gesture.NONE      # release sobrante de un doble click
        else:
            gesture = Gesture.CLICK

        self.reset()

        return gesture

    # ---------------------------------
    @property
    def dragging(self):
        return self._moved

    @property
    def press_pos(self):
        return self._press_pos