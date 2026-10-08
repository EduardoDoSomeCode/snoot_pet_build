"""El log de gestos solo escribe si se pide con SNOOT_LOG=1.

    python tests/test_debug_log.py
"""
import contextlib
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# La ruta del log sale de HOME, asi que se cambia antes de nada para no tocar
# el archivo de verdad.
HOMEFALSO = tempfile.mkdtemp()
os.environ["HOME"] = HOMEFALSO

# A proposito NO se importa desktop_pet: arrastra PySide6.QtGui, que va con
# NEEDED de libEGL.so.1 (una libreria del sistema que no esta en un runner de
# CI sin GPU). El log de gestos es logica pura y vive en core/debug_log.py,
# precisamente para poder probarlo sin Qt. Antes de moverlo ahi, este test
# fallaba al importar en GitHub Actions en vez de comprobar nada.
import core.debug_log as debug_log  # noqa: E402

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


def ruta_log():
    return os.path.join(HOMEFALSO, ".local", "share", "Snoot_pet", "pet.log")


def disparar(valor, mensaje="press pos=(1, 2)"):
    """Poner SNOOT_LOG a `valor`, llamar a _debug y decir que se ha visto."""
    if valor is None:
        os.environ.pop("SNOOT_LOG", None)
    else:
        os.environ["SNOOT_LOG"] = valor

    salida = io.StringIO()
    with contextlib.redirect_stdout(salida):
        debug_log.debug(mensaje)

    return salida.getvalue()


print("=== sin SNOOT_LOG: ni a stdout ni pet.log ===")
# Antes _debug imprimia siempre en stdout, con lo que cada movimiento del raton
# sobre la pet sacaba una linea aunque no se estuviera depurando nada.
texto = disparar(None)
comprobar("stdout vacio", texto, "")
comprobar("no se crea pet.log", os.path.exists(ruta_log()), False)

print("\n=== SNOOT_LOG apagado: tampoco escribe ===")
texto = disparar("0")
comprobar("stdout vacio", texto, "")
comprobar("no se crea pet.log", os.path.exists(ruta_log()), False)

texto = disparar("")
comprobar("stdout vacio con cadena vacia", texto, "")

print("\n=== SNOOT_LOG=1: escribe en stdout y en el archivo ===")
texto = disparar("1")
comprobar("sale en stdout", "press pos=(1, 2)" in texto, True)
comprobar("lleva el prefijo", texto.startswith("[pet] "), True)
comprobar("se crea pet.log", os.path.exists(ruta_log()), True)

contenido = open(ruta_log(), encoding="utf-8").read()
comprobar("el mensaje esta en el archivo", "press pos=(1, 2)" in contenido, True)
comprobar("con hora delante", len(contenido.split()[0]) == 8, True)  # HH:MM:SS

print("\n=== el archivo no crece sin limite ===")
# El corte mira el tamaño ANTES de escribir, asi que el reinicio se ve en la
# escritura siguiente, no en la que se pasa de 64 KB.
disparar("1", "x" * 70000)
comprobar("la escritura grande si pasa de 64 KB",
          os.path.getsize(ruta_log()) > 65536, True)

disparar("1", "linea normal")
comprobar("la siguiente escritura reinicia el archivo",
          os.path.getsize(ruta_log()) < 65536, True)
comprobar("y solo queda la linea nueva",
          open(ruta_log(), encoding="utf-8").read().strip().endswith("linea normal"),
          True)

print(f"\n{total - fallos}/{total} pruebas correctas")
sys.exit(1 if fallos else 0)