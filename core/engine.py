import os
import platform
import sys
from typing import NamedTuple

# PySide6 NO se importa aqui a proposito. choose_platform(), xwayland_available()
# y choose_platform() son logica pura y se prueban sin Qt (tests/test_platform.py),
# pero importar QtWidgets en el module scope arrastra QtGui, que va con NEEDED de
# libEGL.so.1: una libreria del sistema que en un runner de CI sin GPU no
# existe, y hacia que las pruebas fallaran al importar en vez de al probar nada.
#
# Lo que si necesita Qt se importa dentro de la funcion que lo usa.

APP_NAME = "Snoot pet"

# Nombre del socket local que usa el guard de instancia unica
INSTANCE_SOCKET = "snoot-pet-unica"


class PlatformDecision(NamedTuple):
    """Lo que se ha decidido sobre el backend, y por que."""

    forced_xcb: bool   # True = hemos fijado QT_QPA_PLATFORM=xcb
    reason: str        # texto para diagnostico


def xwayland_available(env=None):
    """¿Hay un servidor X al que conectarse?

    En una sesion Wayland normal lo que hay es XWayland, y la pet lo necesita
    para el always on top. Pero XWayland no esta en todas partes: hay
    instalaciones de GNOME y de distros minimas donde esta desactivado. Ahi,
    forzar el backend xcb hacia que la app no abra nada en absoluto.

    choose_platform() es pura (no toca os.environ), asi que esto se puede
    probar sin cambiar el entorno del proceso.
    """
    env = os.environ if env is None else env
    display = (env.get("DISPLAY") or "").strip()

    if not display:
        return False

    # ":0", ":0.0" -> se puede comprobar el socket de verdad
    if display.startswith(":"):
        numero = display[1:].split(".")[0]

        if numero.isdigit():
            return os.path.exists(f"/tmp/.X11-unix/X{numero}")

    # "host:0" o por TCP: no hay socket local que mirar, se asume que hay
    return True


def choose_platform(choice, env=None, system=None):
    """Decide el backend de Qt ANTES de crear la QApplication.

    En Linux lo importante: xdg-shell no tiene ningún request de "keep above",
    así que con el backend nativo de Wayland `Qt.WindowStaysOnTopHint` no hace
    nada y la pet se va detrás en cuanto se abre otra ventana. KWin sí honra
    `_NET_WM_STATE_ABOVE`, que es lo que usa el backend XWayland (xcb).

    Pero xcb solo funciona si hay XWayland. Si no lo hay, quedarse sin hacer
    nada no es lo mismo que antes: antes Qt elegia Wayland nativo en silencio y
    la pet abria pero sin always on top; ahora, si el ajuste pide xcb y no hay
    XWayland, se dice explicitamente en el motivo y la app sigue en Wayland
    nativo en vez de no arrancar.

    Pura: no toca os.environ. Devuelve el motivo para poder avisar.
    """
    # "xcb" y "wayland" son backends de Linux. En Windows y macOS el nombre del
    # backend es otro ("windows", "cocoa") y el plugin xcb no viene ni
    # instalado: pedirlo ahi hace que Qt no pueda crear ventana y la app no
    # arranca. El ajuste se guarda en un unico settings.json que comparten
    # todas las plataformas, asi que en Windows sigue valiendo "xcb" y hay que
    # descartarlo explicitamente en vez de fiarse del valor.
    #
    # No se comprueba con env: se pasa platform.system() para poder probarlo.
    system = platform.system() if system is None else system

    if system != "Linux":
        return PlatformDecision(
            False,
            f"{system} no usa backends de Qt con nombre: se deja que Qt "
            f"elija el suyo",
        )

    # Solo se acepta el valor exacto: si el ajuste viene maltypeado (un bool
    # de una version anterior, por ejemplo), quedarse sin hacer nada lleva a Qt
    # a Wayland nativo en silencio, que es justo lo que no queremos.
    if choice != "xcb":
        return PlatformDecision(
            False,
            f"el ajuste de plataforma es {choice!r}, no se fuerza nada "
            f"y Qt elige ({'Wayland nativo' if choice == 'wayland' else 'sin fijar'})",
        )

    if not xwayland_available(env):
        return PlatformDecision(
            False,
            "el ajuste pide XWayland pero no hay servidor X (DISPLAY vacio o "
            "su socket no existe): se usa Wayland nativo y el always on top "
            "NO funcionara",
        )

    return PlatformDecision(True, "hay XWayland: backend xcb fijado")


def configure_platform(choice, env=None, system=None):
    """Aplica la decision de choose_platform al entorno y la devuelve."""
    decision = choose_platform(choice, env, system)

    if decision.forced_xcb:
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

    return decision


def claim_single_instance(app):
    """Devuelve el QLocalServer si esta es la unica instancia, None si ya hay
    otra corriendo.

    Sin esto se acumulan varias pets, todas "always on top" compitiendo por el
    stacking de KWin: la que estas mirando puede quedar tapada por otra y
    parece que la pet desaparece.
    """
    from PySide6.QtNetwork import QLocalServer, QLocalSocket

    probe = QLocalSocket()
    probe.connectToServer(INSTANCE_SOCKET)

    if probe.waitForConnected(400):
        probe.abort()
        return None

    # Socket de una instancia que murio sin limpiarlo
    QLocalServer.removeServer(INSTANCE_SOCKET)

    server = QLocalServer(app)
    if not server.listen(INSTANCE_SOCKET):
        return None

    return server


def create_app(argv=None):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()

    if app is None:
        app = QApplication(argv if argv is not None else sys.argv)

    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)

    # La pet no tiene botones de cerrar: si el usuario cierra un dialogo no
    # queremos que la app se muera.
    app.setQuitOnLastWindowClosed(False)

    return app