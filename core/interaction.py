"""Decision de gestos: ¿esto ha sido un click, un doble click o un arrastre?

Sin widgets, sin Qt, sin ventanas: solo numeros. Toda la logica de umbral vive
aqui, de forma que se puede probar sin montar la GUI y sin adivinar.

El widget (desktop_pet.py) se limita a traducir los eventos del raton a llamadas
de esta clase y a ejecutar lo que devuelva.
"""

from enum import Enum
from time import monotonic


class Gesture(Enum):
    NONE = "none"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    DRAG = "drag"


class ClickDragResolver:
    # ---------------------------------
    def __init__(self, drag_threshold=12, double_click_ms=250):
        # El umbral nativo de la plataforma (Qt da ~10px) con margen. Por debajo
        # hay que considerarlo temblor de la mano: en un click real el raton
        # siempre se mueve unos pixeles.
        self.drag_threshold = max(12, drag_threshold)

        # Margen para el doble click: menos que esto, dos clicks seguidos se
        # tratarian como uno; mas que esto y el click tarda en reaccionar.
        self.double_click_ms = double_click_ms

        self._press_pos = None
        self._press_window_pos = None
        self._moved = False

        # Momento hasta el que un click ya está atendido por un doble click.
        # Es temporal a proposito: con un flag permanent, si el release final
        # del doble click no llegaba (pasa en cuanto un compositor se come un
        # evento) el flag se quedaba puesto y TODOS los clicks posteriores
        # quedaban muertos para siempre.
        self._consumed_until = 0.0

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
    def double_click(self):
        self._consumed_until = monotonic() + (self.double_click_ms / 1000.0)
        return Gesture.DOUBLE_CLICK

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
        elif monotonic() < self._consumed_until:
            gesture = Gesture.NONE      # el doble click ya se ha atendido
        else:
            gesture = Gesture.CLICK     # puede ser doble click: lo decide el timer

        self.reset()

        return gesture

    # ---------------------------------
    @property
    def dragging(self):
        return self._moved

    @property
    def press_pos(self):
        return self._press_pos