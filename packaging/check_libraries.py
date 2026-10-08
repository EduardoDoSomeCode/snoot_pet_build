#!/usr/bin/env python3
"""Comprueba que el AppImage solo necesita librerias de base del sistema.

    python packaging/check_libraries.py <directorio-extraido-del-AppImage>

Que es lo que hay que comprobar
-------------------------------
"ldd no sale con not found" NO sirve, y mas de una vez ha dado una falsa
tranquilidad. ldd resuelve contra el sistema que este corriendo, asi que en un
escritorio con Mesa todo aparece resuelto aunque el AppImage no traiga nada:
libEGL.so.1 y libGL.so.1 salian bien aqui y en un runner de CI, que es un
contenedor sin Mesa, son justo las que faltan.

Ese fallo no es solo del check: el escaner de dependencias de PyInstaller
(bindepend.py) tambien usa ldd para decidir que empaquetar. En una maquina
donde las librerias estan instaladas se las lleva dentro; en un runner minimo
no las encuentra y el paquete sale sin ellas. Por eso este script contrasta
los NEEDED contra el CONTENIDO del bundle y nunca contra el sistema.

Lo que se comprueba aqui es otra cosa: se enumera todo lo que el bundle pide
con NEEDED y se mira si cada nombre esta dentro del propio AppImage. Lo que
no esta, tiene que ser una libreria de base del sistema (libc, libm, el loader,
libgcc), que es legitimo y esta en cualquier maquina con el mismo
arquetipo, o el driver de pantalla, o el protocolo de ventanas (X11/Wayland),
que lo instala el servidor grafico. Si no esta en ninguna de esas, el AppImage
depende de algo que no viaja con el.

Eseason los NEEDED de libQt6Core, Qt6Gui, Qt6Widgets, Qt6Network, Qt6XcbQpa,
Qt6DBus y Qt6Svg, los unicos que quedan tras el recorte.
"""
import os
import subprocess
import sys

# El nombre base del ELF sin la version: libQt6Core.so.6 -> libQt6Core.so
def clave(nombre):
    return nombre.split(".so")[0] + ".so"


# Lo que puede faltar sin romper: son de base o las aporta el driver de
# pantalla, que varia mucho entre AMD, Intel y NVIDIA.
# Lo que puede faltar sin romper. Son de base del sistema, esta en cualquier
# distro con un escritorio, o las pone el driver de pantalla.
PERMITIDAS = {
    # base
    "libc.so",
    "libm.so",
    "libdl.so",
    "librt.so",
    "libpthread.so",
    "libgcc_s.so",
    "libstdc++.so",
    "ld-linux-x86-64.so",
    "libresolv.so",
    "libnsl.so",
    # imagen/GPU: las pone el driver, no Qt
    "libEGL.so",
    "libGL.so",
    "libGLESv2.so",
    "libGLX.so",
    "libOpenGL.so",
    "libdrm.so",
    "libgbm.so",
    "libglapi.so",
    "libglx.so",
    "libGLdispatch.so",
    # Protocolo de ventanas: el servidor X (X11 o XWayland) y el compositor los
    # instalan si hay sesion de escritorio. Todas estas vienen colgando de
    # libxcb1, que a su vez necesita cualquiera que tenga un servidor X, asi
    # que no es algo que deba viajar dentro del AppImage: si no hay servidor,
    # la pet no tiene donde dibujarse igualmente.
    #
    # El prefijo cubre libxcb-*.so* entero (cursor, icccm, image, keysyms,
    # render-util, shape, util, xkb...) mas libxcb.so a secas.
    "libX11-xcb.so",
    "libxcb.so",
    "libwayland-client.so",
    "libwayland-cursor.so",
    "libwayland-egl.so",
    "libxkbcommon.so",
    "libxkbcommon-x11.so",
}

# Prefijos que se permiten entero (por prefijo, no por nombre exacto).
PERMITIDAS_PREFIJO = ("libxcb-",)

# Raices del bundle donde puede estar cualquier .so
def raices(appdir):
    interna = os.path.join(appdir, "_internal")
    dirs = [interna, os.path.join(interna, "PySide6", "Qt", "lib")]

    for d in dirs:
        if os.path.isdir(d):
            yield d

    # PySide6 mete las suyas en subdirectorios (pillow.libs, etc.)
    for nombre in os.listdir(interna):
        d = os.path.join(interna, nombre)
        if os.path.isdir(d) and nombre != "PySide6":
            yield d


def nombres_disponibles(appdir):
    """nombre base -> ruta completa, de todo lo que hay en el bundle."""
    disponibles = {}

    for d in raices(appdir):
        for f in os.listdir(d):
            if ".so" in f:
                disponibles.setdefault(clave(f), os.path.join(d, f))

    return disponibles


def needed_de(ruta):
    try:
        out = subprocess.run(["objdump", "-p", ruta], capture_output=True,
                             text=True).stdout
    except FileNotFoundError:
        print("!! hace falta objdump (binutils) para esto")
        sys.exit(2)

    salida = []
    for linea in out.splitlines():
        partes = linea.split()
        # objdump -p imprime "  NEEDED   libQt6Core.so.6", sin corchetes
        if len(partes) >= 2 and partes[0] == "NEEDED":
            salida.append(partes[1])
    return salida


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    appdir = sys.argv[1]
    if not os.path.isdir(appdir):
        sys.exit(f"no existe {appdir}")

    disponibles = nombres_disponibles(appdir)
    print(f"  .so dentro del bundle: {len(disponibles)}")

    # Las DLL de las que solo quedan en pie tras el recorte
    libdir = os.path.join(appdir, "_internal", "PySide6", "Qt", "lib")
    raices_lib = [os.path.join(libdir, f) for f in sorted(os.listdir(libdir))
                  if f.startswith("libQt6") and ".so." in f]

    if not raices_lib:
        sys.exit(f"!! no encuentro Qt en {libdir}")

    # Cerrado de dependencias: lo que se pide tiene que estar en el bundle o
    # ser una de las permitidas. El cerrado se propaga para pillar tambien lo
    # que pide un .so de segundo nivel (Qt6Gui pide libfreetype, que a su vez
    # pide libpng...).
    pendientes = list(raices_lib)
    vistos = set()
    faltan = {}

    while pendientes:
        actual = pendientes.pop()
        if actual in vistos or not os.path.exists(actual):
            continue
        vistos.add(actual)

        for lib in needed_de(actual):
            k = clave(lib)

            if k in disponibles:
                # esta en el bundle: hay que mirar tambien lo que pide
                destino = disponibles[k]

                if destino not in vistos:
                    pendientes.append(destino)

                continue

            if k in PERMITIDAS or k.startswith(PERMITIDAS_PREFIJO):
                continue

            faltan.setdefault(k, set()).add(os.path.basename(actual))

    if faltan:
        print("\n  FALTAN en el AppImage (no son de base del sistema):")
        for lib, quien in sorted(faltan.items()):
            quien = ", ".join(sorted(quien)[:3])
            print(f"    {lib:28s} pedida por {quien}")
        print(f"\n  {len(faltan)} librerias. El AppImage NO es autonomo.")
        return 1

    print("  el AppImage solo necesita base del sistema y el driver de GPU")
    return 0


if __name__ == "__main__":
    sys.exit(main())