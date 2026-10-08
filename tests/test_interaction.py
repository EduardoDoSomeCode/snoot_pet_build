"""Tests de la logica de gestos. No necesitan Qt ni pantalla.

    python tests/test_interaction.py
"""
import os
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.interaction import ClickDragResolver, Gesture  # noqa: E402

fallos = 0
total = 0


def comprobar(nombre, obtenido, esperado):
    global fallos, total
    total += 1

    if obtenido != esperado:
        fallos += 1
        print(f"  FALLO  {nombre}: esperado {esperado}, obtenido {obtenido}")
    else:
        print(f"  ok     {nombre}")


def click(resolver, pos=(500, 500), temblor=0, window_pos=(100, 100)):
    """Click simple: press, temblor opcional, release."""
    resolver.press(pos, window_pos)

    if temblor:
        for i in range(1, 4):
            resolver.move((pos[0] + temblor * i // 3, pos[1]))

    return resolver.release(window_pos)


print("=== click simple ===")
r = ClickDragResolver()
comprobar("click sin movimiento", click(r), Gesture.CLICK)

r = ClickDragResolver()
comprobar("click con 2px de temblor", click(r, temblor=2), Gesture.CLICK)

r = ClickDragResolver()
comprobar("click con 6px de temblor", click(r, temblor=6), Gesture.CLICK)

r = ClickDragResolver()
comprobar("click con la ventana movida 3px",
          click(r, window_pos=(100, 103)), Gesture.CLICK)

print("\n=== arrastre ===")
r = ClickDragResolver()
r.press((500, 500), (100, 100))
comprobar("move de 8px no es arrastre todavia",
          r.move((508, 500)), Gesture.NONE)
comprobar("move de 40px si es arrastre",
          r.move((540, 500)), Gesture.DRAG)
comprobar("release tras arrastre", r.release((100, 100)), Gesture.DRAG)

r = ClickDragResolver()
r.press((500, 500), (100, 100))
r.move((600, 500))
comprobar("ventana movida por el compositor cuenta como arrastre",
          r.release((260, 100)), Gesture.DRAG)

print("\n=== doble click ===")
r = ClickDragResolver()
r.press((500, 500), (100, 100))
gesto1 = r.release((100, 100))          # primer click: se encola
comprobar("primer click devuelve CLICK", gesto1, Gesture.CLICK)
comprobar("doble click", r.double_click(), Gesture.DOUBLE_CLICK)
r.press((500, 500), (100, 100))
comprobar("el segundo release no encola otro click",
          r.release((100, 100)), Gesture.NONE)

print("\n=== doble click sin release final ===")
# Si el release final del doble click no llega (un compositor puede comerse un
# evento), con un flag permanente todos los clicks posteriores quedarian
# muertos para siempre. El bloqueo es temporal y se caduca solo.
r = ClickDragResolver(double_click_ms=120)
r.press((500, 500), (100, 100))
r.release((100, 100))
r.double_click()
# sin el segundo release...

time.sleep(0.25)                        # ...el bloqueo caduca

r.press((500, 500), (100, 100))
comprobar("click sigue vivo tras doble click sin release final",
          r.release((100, 100)), Gesture.CLICK)

print("\n=== casos raros ===")
r = ClickDragResolver()
comprobar("release sin press no rompe", r.release((0, 0)), Gesture.CLICK)

r = ClickDragResolver()
comprobar("move sin press", r.move((10, 10)), Gesture.NONE)

r = ClickDragResolver()
r.press((0, 0), (0, 0))
comprobar("umbral por debajo no cuenta", r.move((10, 0)), Gesture.NONE)
comprobar("umbral por encima cuenta", r.move((13, 0)), Gesture.DRAG)

r = ClickDragResolver(drag_threshold=40)
r.press((0, 0), (0, 0))
comprobar("umbral configurable se respeta", r.move((30, 0)), Gesture.NONE)

print(f"\n{total - fallos}/{total} pruebas correctas")
sys.exit(1 if fallos else 0)