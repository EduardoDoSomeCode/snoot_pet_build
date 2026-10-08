#!/usr/bin/env bash
#
# Quita del AppDir las librerias de Qt que la pet no usa.
#
#   ./packaging/trim_qt_libs.sh <AppDir>
#
# PyInstaller y el hook de PySide6 se llevan el directorio lib de Qt entero.
# Los excludes del spec quitan los MODULOS de Python (QtQuick.abi3.so y
# compañía, que ya no estan), pero las librerias nativas se quedan: al final
# viaja 20 MB de QML/Quick/Pdf que no se cargan nunca.
#
# Importante: la lista es de lo que sobra, NO de lo que parece sobrar.
# Tres librerias que un analisis por NEEDED daria por prescindibles hay que
# conservarlas a proposito:
#
#   libQt6WaylandClient.so.6     la pide el plugin de Wayland con NEEDED, y
#                                 sin ella el respaldo a Wayland nativo (para
#                                 maquinas sin XWayland) no arranca
#   libQt6WlShellIntegration.so.6 la carga con dlopen el plugin de Wayland;
#                                 es xdg-shell, o sea el arrastre de la ventana
#   libQt6Svg.so.6 / libQt6OpenGL.so.6
#                                 Qt6Gui las carga con dlopen. No hacen falta
#                                 para el motor de raster, pero son 1.3 MB
#                                 entre las dos y quitarlas solo ahonda en
#                                 "no se ven los iconos"
set -euo pipefail

APPDIR="${1:?falta el AppDir}"

LIBDIR="$APPDIR/_internal/PySide6/Qt/lib"
PLATDIR="$APPDIR/_internal/PySide6/Qt/plugins/platforms"

if [ ! -d "$LIBDIR" ]; then
    echo "!! no existe $LIBDIR: nada que quitar"
    exit 1
fi

# Lo que se puede borrar. Lista explicita a proposito: si mañana aparece otra
# libreria muerta, se añade aqui y se comprueba, en vez de borrar "lo que no
# se use" que es justo como se borra Qt por error.
BORRAR_LIB=(
    libQt6Quick.so.6
    libQt6Qml.so.6
    libQt6QmlMeta.so.6
    libQt6QmlModels.so.6
    libQt6QmlWorkerScript.so.6
    libQt6Pdf.so.6
    libQt6VirtualKeyboard.so.6
    libQt6VirtualKeyboardQml.so.6
    libQt6EglFSDeviceIntegration.so.6
    libQt6EglFsKmsSupport.so.6
)

# Plataformas que no usamos. Se dejan minimal/offscreen: los usan las pruebas.
BORRAR_PLAT=(
    libqeglfs.so
    libqlinuxfb.so
    libqvkkhrdisplay.so
    libqvnc.so
)

# Red de seguridad: si alguno de estos estuviera en la lista, el script para.
# Son las librerias sin las que la app no arranca o pierde una funcion.
PROTEGER_LIB="libQt6Core.so.6 libQt6Gui.so.6 libQt6Widgets.so.6 \
libQt6Network.so.6 libQt6DBus.so.6 libQt6XcbQpa.so.6 \
libQt6WaylandClient.so.6 libQt6WlShellIntegration.so.6"

for nombre in "${BORRAR_LIB[@]}"; do
    for protegido in $PROTEGER_LIB; do
        if [ "$nombre" = "$protegido" ]; then
            echo "!! $nombre esta en la lista de borrar y en la de proteger"
            exit 1
        fi
    done
done

antes=$(du -sb "$LIBDIR" "$PLATDIR" 2>/dev/null | awk '{s+=$1} END {print s}')

quitados=0
for nombre in "${BORRAR_LIB[@]}"; do
    if [ -f "$LIBDIR/$nombre" ]; then
        rm -f "$LIBDIR/$nombre"
        echo "  - lib/$nombre"
        quitados=$((quitados + 1))
    fi
done

for nombre in "${BORRAR_PLAT[@]}"; do
    if [ -f "$PLATDIR/$nombre" ]; then
        rm -f "$PLATDIR/$nombre"
        echo "  - plugins/platforms/$nombre"
        quitados=$((quitados + 1))
    fi
done

despues=$(du -sb "$LIBDIR" "$PLATDIR" 2>/dev/null | awk '{s+=$1} END {print s}')
ahorro=$((antes - despues))

echo "  quitadas $quitados librerias, ${ahorro} bytes de disco ($((ahorro / 1048576)) MB)"