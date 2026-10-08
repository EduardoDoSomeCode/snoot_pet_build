#!/usr/bin/env bash
#
# Empaqueta la pet como .deb de Debian/Ubuntu.
#
#   ./packaging/build_deb.sh <VERSION> [directorio-dist-de-pyinstaller]
#
# El AppImage lleva Qt, libxcb, libxkbcommon y X11 dentro, asi que el paquete
# no depende de casi nada: lo unico que hace falta en la maquina destino es un
# servidor de graficos (y XWayland si la sesion es Wayland, porque el always on
# top va por _NET_WM_STATE_ABOVE).
set -euo pipefail

VERSION="${1:?falta la version}"
DIST="${2:-dist}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
BUILD="${BUILD_DIR:-/tmp/snoot-deb}"

if [ ! -d "$DIST/snoot-pet" ]; then
    echo "!! no encuentro $DIST/snoot-pet (¿falta el build de PyInstaller?)"
    exit 1
fi

ARQ="$(dpkg --print-architecture)"
NOMBRE="snoot-pet"
PAQUETE="${NOMBRE}_${VERSION}_${ARQ}"
STAGE="$BUILD/$PAQUETE"

echo "==> preparando $PAQUETE ($ARQ)"
rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN"
mkdir -p "$STAGE/opt/$NOMBRE"
mkdir -p "$STAGE/usr/bin"
mkdir -p "$STAGE/usr/share/applications"
mkdir -p "$STAGE/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$BUILD/icons"

# --- payload ---------------------------------------------------------------
cp -a "$DIST/$NOMBRE/." "$STAGE/opt/$NOMBRE/"

# Los personajes del usuario van a ~/.local/share, asi que /opt va solo con
# lectura y el ejecutable con permiso de ejecucion.
chmod -R a+rX "$STAGE/opt/$NOMBRE"
chmod a+rx "$STAGE/opt/$NOMBRE/$NOMBRE"

ln -sf "/opt/$NOMBRE/$NOMBRE" "$STAGE/usr/bin/$NOMBRE"

"${PYTHON:-python3}" "$AQUI/make_icons.py" "$BUILD/icons" >/dev/null

cp "$AQUI/snoot-pet.desktop" "$STAGE/usr/share/applications/$NOMBRE.desktop"
cp "$BUILD/icons/snoot-pet.png" \
   "$STAGE/usr/share/icons/hicolor/256x256/apps/$NOMBRE.png"

# --- metadatos -------------------------------------------------------------
cat > "$STAGE/DEBIAN/control" <<CONTROL
Package: $NOMBRE
Version: $VERSION
Section: games
Priority: optional
Architecture: $ARQ
Maintainer: Snoot pet <snoot@example.invalid>
Depends: libc6 (>= 2.31), libglib2.0-0 (>= 2.56), libdbus-1-3,
 libfontconfig1, libfreetype6, libx11-6, libxcb1, libxkbcommon0,
 libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-image0,
 libxcb-keysyms1, libxcb-render-util0, libxcb-randr0, libxcb-render0,
 libxcb-shape0, libxcb-sync1, libxcb-util1, libxcb-xfixes0, libxcb-xkb1,
 libegl1, libgl1, libxshmfence1,
 libwayland-client0, libwayland-cursor0, libwayland-egl1
Installed-Size: $(du -ks "$STAGE" | cut -f1)
Homepage: https://github.com/snoot-pet/snoot-pet
Description: Desktop pet that lives on your desktop
 Snoot pet is a small animated pet you keep on the desktop. Click it to
 change what it is doing, drag it to move it, and it stays on top of the
 other windows.
 .
 The animation frames are plain GIFs and new characters can be imported
 from the right click menu.
CONTROL

# Que el menu de aplicaciones y la cache de iconos se enteren
cat > "$STAGE/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
POSTINST
chmod 755 "$STAGE/DEBIAN/postinst"

cat > "$STAGE/DEBIAN/prerm" <<'PRERM'
#!/bin/sh
set -e
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
PRERM
chmod 755 "$STAGE/DEBIAN/prerm"

# --- construir -------------------------------------------------------------
echo "==> dpkg-deb"
mkdir -p "$BUILD"
# --root-owner-group evita necesitar fakeroot y deja el dueño root:root bien
dpkg-deb --root-owner-group --build "$STAGE" "$BUILD/$PAQUETE.deb" >/dev/null

echo "==> comprobaciones"
dpkg-deb --info "$BUILD/$PAQUETE.deb" | sed 's/^/  /'
echo "  --- contenido (resumen) ---"
dpkg-deb --contents "$BUILD/$PAQUETE.deb" | awk '{print $6}' \
    | grep -cE '^' | sed 's/^/  ficheros: /'
dpkg-deb --contents "$BUILD/$PAQUETE.deb" | grep -E '/usr/bin/|/usr/share/' \
    | awk '{printf "  %s\n", $6}'

echo "==> listo: $BUILD/$PAQUETE.deb ($(du -h "$BUILD/$PAQUETE.deb" | cut -f1))"