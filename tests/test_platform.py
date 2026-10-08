"""Decision del backend de Qt. No necesita pantalla ni QApplication.

    python tests/test_platform.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import choose_platform, xwayland_available  # noqa: E402

fallos = 0
total = 0


def comprobar(nombre, obtenido, esperado):
    global fallos, total
    total += 1

    if obtenido != esperado:
        fallos += 1
        print(f"  FALLO  {nombre}: esperado {esperado!r}, obtenido {obtenido!r}")
    else:
        print(f"  ok     {nombre}")


print("=== xwayland_available: sin X no se puede forzar xcb ===")
comprobar("sin DISPLAY", xwayland_available({}), False)
comprobar("DISPLAY vacio", xwayland_available({"DISPLAY": ""}), False)
comprobar("DISPLAY con espacios", xwayland_available({"DISPLAY": "   "}), False)
comprobar("socket que no existe",
          xwayland_available({"DISPLAY": ":99"}), False)
comprobar("forma host:0 (no comprobable, se asume)",
          xwayland_available({"DISPLAY": "localhost:0"}), True)
comprobar("forma tcp", xwayland_available({"DISPLAY": "192.168.1.5:0"}), True)

# Con un socket real no podemos depender de la maquina: se comprueba solo si el
# numero corresponde a un socket que exista de verdad.
sock = "/tmp/.X11-unix/X0"
existe = os.path.exists(sock)
print(f"  (en esta maquina {sock} {'existe' if existe else 'no existe'})")
comprobar(f"socket :0 presente={existe}",
          xwayland_available({"DISPLAY": ":0"}), existe)

print("\n=== el caso que rompia: piden xcb y no hay XWayland ===")
# Antes esto devolvia False sin mas y Qt se quedaba en Wayland nativo
# sin decir nada. Ahora lo dice, pero la app arranca igual: no reventar es
# justo lo importante.
d = choose_platform("xcb", env={})
comprobar("no se fuerza xcb", d.forced_xcb, False)
comprobar("el motivo lo explica", "no hay servidor X" in d.reason, True)
comprobar("avisa del always on top", "NO funcionara" in d.reason, True)

print("\n=== si hay XWayland, xcb como siempre ===")
d = choose_platform("xcb", env={"DISPLAY": "localhost:0"})
comprobar("se fuerza xcb", d.forced_xcb, True)
comprobar("el motivo lo confirma", "hay XWayland" in d.reason, True)

print("\n=== Windows y macOS: nunca se pide xcb ===")
# Este es el fallo que hacia que el build de Windows no arrancara: el ajuste
# guardado dice "xcb" en todas las plataformas (es el unico settings.json), y
# si se respeta a ciegas se le pide a Qt un plugin que en Windows no existe.
for sistema in ("Windows", "Darwin"):
    d = choose_platform("xcb", env={}, system=sistema)
    comprobar(f"{sistema}: no fuerza xcb", d.forced_xcb, False)
    comprobar(f"{sistema}: lo dice", sistema in d.reason, True)

# Windows con un X server de Cygwin/WSL/Xmingponiendo DISPLAY: antes esto si
# fuerza xcb, y en Windows el plugin xcb no existe.
d = choose_platform(
    "xcb",
    env={"DISPLAY": "localhost:0.0", "SystemRoot": r"C:\Windows"},
    system="Windows",
)
comprobar("Windows con DISPLAY tampoco fuerza xcb", d.forced_xcb, False)

# Y al reves: en Linux si se respeta, que es lo que hace que funcione
d = choose_platform("xcb", env={"DISPLAY": "localhost:0"}, system="Linux")
comprobar("Linux si fuerza xcb", d.forced_xcb, True)

print("\n=== wayland explicito se respeta ===")
d = choose_platform("wayland", env={"DISPLAY": "localhost:0"})
comprobar("no se fuerza xcb", d.forced_xcb, False)
comprobar("menciona Wayland nativo", "Wayland nativo" in d.reason, True)

print("\n=== valores raros: no se fuerzan (el bug del platform: true) ===")
for valor in (True, False, None, "", 1.0, ["xcb"]):
    d = choose_platform(valor, env={"DISPLAY": "localhost:0"})
    comprobar(f"{valor!r} no fuerza xcb", d.forced_xcb, False)

print("\n=== reason siempre informative ===")
for valor in ("xcb", "wayland", True, None):
    d = choose_platform(valor, env={})
    comprobar(f"{valor!r} tiene motivo", bool(d.reason.strip()), True)

print(f"\n{total - fallos}/{total} pruebas correctas")
sys.exit(1 if fallos else 0)