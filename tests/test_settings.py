"""Tests de los ajustes persistidos. No necesitan Qt ni pantalla.

    python tests/test_settings.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.settings import Settings, DEFAULTS  # noqa: E402

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


def nuevo(**valores):
    d = tempfile.mkdtemp()
    ruta = os.path.join(d, "settings.json")

    if valores:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(valores, f)

    return ruta


print("=== los booleanos siguen siendo booleanos ===")
ruta = nuevo()
s = Settings(path=ruta)
s.set("always_on_top", False)
comprobar("always_on_top False", Settings(path=ruta).get("always_on_top"), False)

s.set("always_on_top", 1)
comprobar("always_on_top 1 -> True", Settings(path=ruta).get("always_on_top"), True)

print("\n=== los strings NO se convierten en True ===")
# Este fue el fallo real: set("platform", "xcb") guardaba True, y con ese
# valor la app no aplicaba el backend X11 y Qt se quedaba en Wayland nativo.
ruta = nuevo()
s = Settings(path=ruta)
s.set("platform", "xcb")
guardado = json.load(open(ruta))["platform"]
comprobar("platform guardado tal cual", guardado, "xcb")

s.set("platform", "wayland")
comprobar("platform wayland", Settings(path=ruta).get("platform"), "wayland")

print("\n=== defaults ===")
ruta = nuevo()
s = Settings(path=ruta)
for clave, valor in DEFAULTS.items():
    comprobar(f"default {clave}", s.get(clave), valor)

print("\n=== archivo corrupto o raro ===")
ruta = nuevo()
with open(ruta, "w", encoding="utf-8") as f:
    f.write("{ no es json")
comprobar("json roto -> defaults", Settings(path=ruta).data, DEFAULTS)

# Un platform bool venida de una version anterior
ruta = nuevo(platform=True, always_on_top=False)
s = Settings(path=ruta)
comprobar("platform True se lee como True (no se inventa)", s.get("platform"), True)
comprobar("el resto sigue bien", s.get("always_on_top"), False)

print("\n=== solo lectura ===")
d = tempfile.mkdtemp()
os.chmod(d, 0o500)
ruta = os.path.join(d, "settings.json")
s = Settings(path=ruta)
s.set("always_on_top", False)   # no debe reventar
comprobar("guardar en solo lectura no rompe", s.get("always_on_top"), False)

print(f"\n{total - fallos}/{total} pruebas correctas")
sys.exit(1 if fallos else 0)