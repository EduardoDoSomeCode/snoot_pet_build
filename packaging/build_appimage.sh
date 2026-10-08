#!/usr/bin/env bash
#
# Empaqueta la pet como AppImage.
#
#   ./packaging/build_appimage.sh
#
# Necesitas: python3 con venv, pyinstaller, pillow y appimagetool.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
BUILD="${BUILD_DIR:-/tmp/snoot-appimage}"

cd "$ROOT"

PYTHON="${PYTHON:-python3}"
VENV="${VENV:-$BUILD/venv}"

# --- 1. Entorno de build ---------------------------------------------------
if [ ! -x "$VENV/bin/python" ]; then
    echo "==> creando venv en $VENV"
    "$PYTHON" -m venv "$VENV"
    "$VENV/bin/python" -m ensurepip --upgrade >/dev/null 2>&1 || true
fi

"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r requirements.txt -r requirements-dev.txt

# --- 2. PyInstaller (one-dir) --------------------------------------------
echo "==> PyInstaller"
"$VENV/bin/pyinstaller" desktop_pet_appimage.spec \
    --distpath "$BUILD/dist" \
    --workpath "$BUILD/build" \
    --noconfirm --clean

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

"$VENV/bin/python" - "$ROOT/fangneutral.ico" "$APPDIR/snoot-pet.png" <<'PY'
import sys
from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
Image.open(src).convert("RGBA").save(dst)
print("icono:", dst)
PY

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