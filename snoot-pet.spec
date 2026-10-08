# -*- mode: python ; coding: utf-8 -*-
#
# Spec unica para todas las plataformas. La usan los cuatro empaquetados:
#
#   Linux   AppImage  (packaging/build_appimage.sh, tras quitar Qt que sobra)
#   Linux   .deb      (packaging/build_deb.sh)
#   Windows instalador con Inno Setup y portable en zip
#   macOS   .app      (LSUIElement, para que no salga en el Dock)
#
#   pyinstaller snoot-pet.spec --noconfirm
#
# Sustituye a desktop_pet.spec, desktop_pet_appimage.spec y
# PetSnootGame.spec, que se quedaron en la epoca de Tkinter: sin excludes
# (viajaban 20 MB de QML/Quick que no se usan) y con upx=True (que a veces
# rompe las DLL de Qt).
import os
import sys

APP = os.path.abspath(SPECPATH)

# Los GIF se decodifican con Pillow, no con los plugins de imagen de Qt.
excludes = [
    'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets',
    'PySide6.QtQuickControls2', 'PySide6.QtQuickTemplates2', 'PySide6.QtQuick3D',
    'PySide6.QtPdf', 'PySide6.QtPdfWidgets',
    'PySide6.QtDesigner', 'PySide6.QtUiTools', 'PySide6.QtHelp', 'PySide6.QtTest',
    'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
    'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtGraphs',
    'PySide6.QtSql', 'PySide6.QtWebSockets', 'PySide6.QtWebChannel',
    'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtPositioning',
    'PySide6.QtSensors', 'PySide6.QtSerialPort', 'PySide6.QtSerialBus',
    'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineQuick',
    'PySide6.QtScxml', 'PySide6.QtStateMachine', 'PySide6.QtRemoteObjects',
    'PySide6.QtSpatialAudio', 'PySide6.QtTextToSpeech',
    'PySide6.QtHttpServer', 'PySide6.QtNetworkAuth', 'PySide6.QtSvgWidgets',
    'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DInput',
    'PySide6.Qt3DLogic', 'PySide6.Qt3DAnimation', 'PySide6.Qt3DExtras',
    'tkinter',
]


def icono(extension):
    """Los iconos los genera packaging/make_icons.py. Si no estan, se sigue
    con el .ico de la raiz en Windows y sin icono en el resto."""
    candidatos = [
        os.path.join(APP, 'packaging', 'icons', 'snoot-pet.' + extension),
        os.path.join(APP, 'fangneutral.ico'),
    ]

    for ruta in candidatos:
        if os.path.exists(ruta):
            return ruta

    return None


a = Analysis(
    [os.path.join(APP, 'desktop_pet.py')],
    pathex=[APP],
    binaries=[],
    datas=[(os.path.join(APP, 'art_assets'), 'art_assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='snoot-pet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='snoot-pet',
)

# En macOS, LSUIElement para que la pet no aparezca en el Dock ni en el
# menu de apps mientras corre: es lo mismo que hace Qt.Tool en el resto de
# plataformas, y aqui no hay forma de pedirlo desde el codigo.
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Snoot pet.app',
        icon=icono('icns'),
        bundle_identifier='com.snoot.pet',
        info_plist={
            'CFBundleName': 'Snoot pet',
            'CFBundleDisplayName': 'Snoot pet',
            'LSUIElement': True,
            'NSHighResolutionCapable': True,
        },
    )