import os
import sys

from PySide6.QtWidgets import QApplication

APP_NAME = "Snoot pet"

# Nombre del socket local que usa el guard de instancia unica
INSTANCE_SOCKET = "snoot-pet-unica"


def configure_platform(choice):
    """Elige el backend de Qt ANTES de crear la QApplication.

    En Linux lo importante: xdg-shell no tiene ningún request de "keep above",
    así que con el backend nativo de Wayland `Qt.WindowStaysOnTopHint` no hace
    nada y la pet se va detrás en cuanto se abre otra ventana. KWin sí honra
    `_NET_WM_STATE_ABOVE`, que es lo que usa el backend XWayland (xcb).

    El resto no se pierde: la transparencia sigue siendo alfa real por pixel y
    el arrastre manual con move() funciona en X11.
    """
    # Solo se acepta el valor exacto: si el ajuste viene maltypeado (un bool
    # de una version anterior, por ejemplo), quedarse sin hacer nada lleva a Qt
    # a Wayland nativo en silencio, que es justo lo que no queremos.
    if choice != "xcb":
        return False

    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
    return True


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
    app = QApplication.instance()

    if app is None:
        app = QApplication(argv if argv is not None else sys.argv)

    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)

    # La pet no tiene botones de cerrar: si el usuario cierra un dialogo no
    # queremos que la app se muera.
    app.setQuitOnLastWindowClosed(False)

    return app