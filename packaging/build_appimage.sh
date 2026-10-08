#!/usr/bin/env bash
#
# Empaqueta la pet como AppImage.
#
#   ./packaging/build_appimage.sh
#
# Necesitas: python3 con venv, pyinstaller, pillow y appimagetool.
#
# En CI se llama con VENV="" para no crear un venv propio y reutilizar el de
# la action:
#
#   VENV= PYTHON=python BUILD_DIR=$PWD/build ./packaging/build_appimage.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
BUILD="${BUILD_DIR:-/tmp/snoot-appimage}"

cd "$ROOT"

PYTHON="${PYTHON:-python3}"
VENV="${VENV-$BUILD/venv}"

# --- 1. Entorno de build ---------------------------------------------------
if [ -z "${VENV:-}" ]; then
    # Sin venv: se usa el interprete de la PATH tal cual (CI).
    PY="$PYTHON"
else
    if [ ! -x "$VENV/bin/python" ]; then
        echo "==> creando venv en $VENV"
        "$PYTHON" -m venv "$VENV"
        "$VENV/bin/python" -m ensurepip --upgrade >/dev/null 2>&1 || true
    fi

    PY="$VENV/bin/python"
fi

if [ "${SKIP_BUILD:-0}" != "1" ]; then
    "$PY" -m pip install --quiet --upgrade pip
    "$PY" -m pip install --quiet -r requirements.txt -r requirements-dev.txt
fi

# --- 2. PyInstaller (one-dir) --------------------------------------------
# Se usa la spec unica de todas las plataformas, no una solo para Linux.
# Con SKIP_BUILD=1 se da por hecho que $BUILD/dist/snoot-pet ya existe: en CI
# conviene compilar una vez y empaquetar AppImage y .deb del mismo dist.
if [ "${SKIP_BUILD:-0}" = "1" ]; then
    echo "==> SKIP_BUILD=1: se reutiliza $BUILD/dist/snoot-pet"
else
    echo "==> PyInstaller"
    "$PY" -m PyInstaller snoot-pet.spec \
        --distpath "$BUILD/dist" \
        --workpath "$BUILD/build" \
        --noconfirm --clean
fi

# --- 3. Montar el AppDir ---------------------------------------------------
echo "==> AppDir"
APPDIR="$BUILD/AppDir"
rm -rf "$APPDIR"
cp -a "$BUILD/dist/snoot-pet" "$APPDIR"

cp "$HERE/AppRun" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"

cp "$HERE/snoot-pet.desktop" "$APPDIR/snoot-pet.desktop"

# PyInstaller se lleva todo el directorio lib de Qt. Los excludes del spec
# quitan los modulos de Python, pero las librerias nativas de QML/Quick/Pdf se
# quedan y no se cargan nunca (~20 MB).
echo "==> quitando librerias de Qt sin usar"
bash "$HERE/trim_qt_libs.sh" "$APPDIR"

"$PY" "$HERE/make_icons.py" "$APPDIR" >/dev/null

ln -sf snoot-pet.png "$APPDIR/.DirIcon"

# --- 4. appimagetool -------------------------------------------------------
if [ ! -x "$BUILD/appimagetool.AppImage" ]; then
    echo "==> descargando appimagetool"
    curl -sSL -o "$BUILD/appimagetool.AppImage" \
        https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$BUILD/appimagetool.AppImage"
fi

echo "==> empaquetando"
cd "$BUILD"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$BUILD/appimagetool.AppImage" "$APPDIR"

mv "$BUILD"/Snoot_pet-x86_64.AppImage "$ROOT/Snoot_pet-x86_64.AppImage" 2>/dev/null || true
echo "==> listo: $ROOT/Snoot_pet-x86_64.AppImage"