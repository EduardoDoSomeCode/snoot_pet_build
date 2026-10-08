import sys

from PySide6.QtWidgets import QApplication

APP_NAME = "Snoot pet"


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